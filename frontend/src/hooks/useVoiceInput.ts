/**
 * useVoiceInput — captures microphone audio and streams PCM-16 at 16 kHz
 * to the backend via a dedicated WebSocket per session.
 *
 * Audio pipeline (preferred order):
 *   1. AudioWorkletNode  (modern, reliable, no deprecated API)
 *   2. ScriptProcessorNode (legacy fallback)
 *
 * Handshake:
 *   WS connect → session_ready → start_listening → listening_started → send PCM-16 binary frames
 */

import { useCallback, useEffect, useRef, useState } from "react";

export type VoiceState =
  | "idle"
  | "connecting"
  | "listening"
  | "thinking"
  | "speaking"
  | "error";

export interface VoiceTranscript {
  text: string;
  is_final: boolean;
  timestamp: number;
  speaker?: string | null; // e.g. "S1", "S2" from Speechmatics diarization
}

export interface Utterance {
  speaker: string;       // "S1", "S2", … or "?" for unknown
  text: string;
  timestamp: number;
}

export interface UseVoiceInputOptions {
  language?: string;
  onTranscript?: (transcript: VoiceTranscript) => void;
  onResponse?: (text: string) => void;  // called when Hugo speaks back
  onError?: (error: Error) => void;
  sessionId?: string;
}

export interface UseVoiceInputReturn {
  state: VoiceState;
  transcript: string;       // accumulated final text (plain string, backwards compat)
  partialText: string;      // live interim words
  micLevel: number;         // 0-1 RMS amplitude
  isListening: boolean;
  startListening: () => Promise<void>;
  stopListening: () => void;
  clearTranscript: () => void;
  error: Error | null;
  utterances: Utterance[];  // diarized conversation history
  partialSpeaker: string | null; // speaker of current partial
}

const WS_BASE_URL =
  (import.meta.env.VITE_WS_BASE_URL as string | undefined) ||
  "ws://localhost:8001";

/**
 * Get a microphone stream, preferring a real built-in/USB mic over
 * a headset-jack device (which returns silence when no headset is plugged in).
 *
 * Strategy:
 *  1. Try the system default first.
 *  2. If it produces silence for >500 ms, enumerate other devices and try each
 *     one until we find one with a non-zero signal, then switch to it.
 */
async function getPreferredMicStream(): Promise<MediaStream> {
  const audioConstraints = {
    channelCount: 1,
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
  };

  // First get default stream
  const defaultStream = await navigator.mediaDevices.getUserMedia({
    audio: audioConstraints,
  });

  // Quick silence check: sample 500 ms and measure RMS
  const isSilent = await checkStreamSilent(defaultStream, 500);
  if (!isSilent) return defaultStream;

  console.warn("[voice] Default mic appears silent — trying other devices...");

  // Enumerate all audio inputs
  let devices: MediaDeviceInfo[] = [];
  try {
    devices = (await navigator.mediaDevices.enumerateDevices()).filter(
      (d) => d.kind === "audioinput" && d.deviceId !== "default"
    );
  } catch {
    return defaultStream; // fallback
  }

  const defaultId = defaultStream.getAudioTracks()[0]?.getSettings().deviceId;

  for (const device of devices) {
    if (device.deviceId === defaultId) continue;
    try {
      const alt = await navigator.mediaDevices.getUserMedia({
        audio: { ...audioConstraints, deviceId: { exact: device.deviceId } },
      });
      const silent = await checkStreamSilent(alt, 400);
      if (!silent) {
        console.log(`[voice] Switched to non-silent mic: ${device.label}`);
        defaultStream.getTracks().forEach((t) => t.stop());
        return alt;
      }
      alt.getTracks().forEach((t) => t.stop());
    } catch {
      // device unavailable
    }
  }

  // Nothing better found — return default
  console.warn("[voice] All mics appear silent, using default");
  return defaultStream;
}

/** Returns true if a stream produces near-silence over the given duration. */
async function checkStreamSilent(
  stream: MediaStream,
  durationMs: number
): Promise<boolean> {
  return new Promise((resolve) => {
    try {
      const AudioCtx =
        window.AudioContext ||
        (window as Window & { webkitAudioContext?: typeof AudioContext })
          .webkitAudioContext;
      if (!AudioCtx) { resolve(false); return; }

      const ctx = new AudioCtx();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);

      const buf = new Float32Array(analyser.fftSize);
      let maxRms = 0;

      const interval = setInterval(() => {
        analyser.getFloatTimeDomainData(buf);
        const rms = Math.sqrt(buf.reduce((s, v) => s + v * v, 0) / buf.length);
        if (rms > maxRms) maxRms = rms;
      }, 50);

      setTimeout(() => {
        clearInterval(interval);
        source.disconnect();
        ctx.close().catch(() => {});
        resolve(maxRms < 0.001); // silent if RMS < 0.1%
      }, durationMs);
    } catch {
      resolve(false);
    }
  });
}

export function useVoiceInput(
  options: UseVoiceInputOptions = {}
): UseVoiceInputReturn {
  const { language = "en", onTranscript, onResponse, onError, sessionId } = options;

  const [state, setState] = useState<VoiceState>("idle");
  const [transcript, setTranscript] = useState("");
  const [partialText, setPartialText] = useState("");
  const [partialSpeaker, setPartialSpeaker] = useState<string | null>(null);
  const [micLevel, setMicLevel] = useState(0); // 0-1 RMS amplitude
  const [error, setError] = useState<Error | null>(null);
  const [utterances, setUtterances] = useState<Utterance[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const scriptNodeRef = useRef<ScriptProcessorNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const finalRef = useRef("");
  const activeRef = useRef(false);

  // ── cleanup helpers ────────────────────────────────────────────────────────

  const cleanupAudio = useCallback(() => {
    workletNodeRef.current?.disconnect();
    workletNodeRef.current = null;
    scriptNodeRef.current?.disconnect();
    scriptNodeRef.current = null;
    if (audioCtxRef.current && audioCtxRef.current.state !== "closed") {
      audioCtxRef.current.close().catch(() => {});
    }
    audioCtxRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const cleanupWS = useCallback(() => {
    const ws = wsRef.current;
    wsRef.current = null;
    if (!ws) return;
    try {
      if (ws.readyState === WebSocket.OPEN)
        ws.send(JSON.stringify({ type: "stop_listening" }));
    } catch {}
    try {
      ws.close(1000, "client stop");
    } catch {}
  }, []);

  // ── audio pipelines ────────────────────────────────────────────────────────

  /** Send an ArrayBuffer chunk to the open WebSocket */
  const sendChunk = useCallback((ws: WebSocket, buf: ArrayBuffer) => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(buf);
    }
  }, []);

  /**
   * Try AudioWorklet pipeline (preferred).
   * Returns true if successfully started, false if not supported.
   */
  const tryWorklet = useCallback(
    async (stream: MediaStream, ws: WebSocket): Promise<boolean> => {
      if (typeof AudioWorkletNode === "undefined") return false;

      try {
        const AudioCtx =
          window.AudioContext || (window as Window & { webkitAudioContext?: typeof AudioContext })
            .webkitAudioContext;
        if (!AudioCtx) return false;

        // Use the browser's native sample rate; the worklet resamples to 16 kHz
        const ctx = new AudioCtx();
        audioCtxRef.current = ctx;

        // Resume MUST happen inside (or triggered by) a user-gesture chain
        if (ctx.state === "suspended") {
          await ctx.resume();
        }
        console.log("[audio] AudioContext state:", ctx.state, "sampleRate:", ctx.sampleRate);

        await ctx.audioWorklet.addModule("/audio-processor.js");

        const source = ctx.createMediaStreamSource(stream);
        const worklet = new AudioWorkletNode(ctx, "pcm16-processor");
        workletNodeRef.current = worklet;

        let chunkCount = 0;
        worklet.port.onmessage = (e: MessageEvent<ArrayBuffer>) => {
          if (!activeRef.current) return;
          sendChunk(ws, e.data);
          chunkCount++;
          // Compute RMS for level meter
          const samples = new Int16Array(e.data);
          let sum = 0;
          for (let i = 0; i < samples.length; i++) sum += (samples[i] / 32768) ** 2;
          setMicLevel(Math.sqrt(sum / samples.length));
          if (chunkCount % 20 === 1) {
            console.log(`[audio-worklet] chunk #${chunkCount}, bytes=${e.data.byteLength}, ws=${ws.readyState}`);
          }
        };

        // Connect: source → worklet (no output needed — worklet posts messages)
        source.connect(worklet);
        // AudioWorklet processes even without connecting to destination
        worklet.connect(ctx.destination); // keeps graph alive in some browsers

        console.log("[audio] AudioWorklet pipeline started");
        return true;
      } catch (err) {
        console.warn("[audio] AudioWorklet failed, will try ScriptProcessorNode:", err);
        cleanupAudio();
        return false;
      }
    },
    [sendChunk, cleanupAudio]
  );

  /**
   * ScriptProcessorNode fallback (deprecated but widely supported).
   */
  const tryScriptProcessor = useCallback(
    async (stream: MediaStream, ws: WebSocket): Promise<boolean> => {
      try {
        const AudioCtx =
          window.AudioContext || (window as Window & { webkitAudioContext?: typeof AudioContext })
            .webkitAudioContext;
        if (!AudioCtx) return false;

        const ctx = new AudioCtx();
        audioCtxRef.current = ctx;

        if (ctx.state === "suspended") {
          await ctx.resume();
        }
        console.log(
          "[audio] ScriptProcessor AudioContext state:",
          ctx.state,
          "sampleRate:",
          ctx.sampleRate
        );

        const nativeRate = ctx.sampleRate;
        const targetRate = 16000;
        const ratio = nativeRate / targetRate;

        const source = ctx.createMediaStreamSource(stream);
        const processor = ctx.createScriptProcessor(4096, 1, 1);
        scriptNodeRef.current = processor;

        let residual: number[] = [];

        let spChunkCount = 0;
        processor.onaudioprocess = (e) => {
          if (!activeRef.current) return;
          spChunkCount++;
          if (spChunkCount % 20 === 1) {
            console.log(`[audio-sp] chunk #${spChunkCount}, ws=${ws.readyState}`);
          }
          const input = e.inputBuffer.getChannelData(0); // Float32 at nativeRate

          // Downsample nativeRate → 16 kHz via linear interpolation
          const outLen = Math.round(input.length / ratio);
          const resampled: number[] = [];
          for (let i = 0; i < outLen; i++) {
            const srcIdx = i * ratio;
            const lo = Math.floor(srcIdx);
            const hi = Math.min(lo + 1, input.length - 1);
            const frac = srcIdx - lo;
            resampled.push(input[lo] * (1 - frac) + input[hi] * frac);
          }

          residual = residual.concat(resampled);
          const chunkSize = 1280; // 80 ms at 16 kHz
          while (residual.length >= chunkSize) {
            const chunk = residual.splice(0, chunkSize);
            const pcm16 = new Int16Array(chunk.length);
            let sum = 0;
            for (let i = 0; i < chunk.length; i++) {
              const s = Math.max(-1, Math.min(1, chunk[i]));
              pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
              sum += s * s;
            }
            setMicLevel(Math.sqrt(sum / chunk.length));
            sendChunk(ws, pcm16.buffer);
          }
        };

        // Muted gain keeps graph alive without feedback
        const gain = ctx.createGain();
        gain.gain.value = 0;
        source.connect(processor);
        processor.connect(gain);
        gain.connect(ctx.destination);

        console.log("[audio] ScriptProcessorNode pipeline started");
        return true;
      } catch (err) {
        console.error("[audio] ScriptProcessorNode failed:", err);
        cleanupAudio();
        return false;
      }
    },
    [sendChunk, cleanupAudio]
  );

  // ── public API ─────────────────────────────────────────────────────────────

  const stopListening = useCallback(() => {
    if (!activeRef.current) return;
    activeRef.current = false;
    cleanupAudio();
    cleanupWS();
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    setState("idle");
  }, [cleanupAudio, cleanupWS]);

  const startListening = useCallback(async () => {
    if (activeRef.current) {
      console.log("[voice] Already active, skipping");
      return;
    }
    activeRef.current = true;
    setState("connecting");
    setError(null);
    console.log("[voice] startListening()");

    try {
      // 1. Check browser support
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("Microphone not supported in this browser");
      }

      // 2. Request microphone — prefer built-in mic over headset jack
      console.log("[voice] Requesting microphone...");
      const stream = await getPreferredMicStream();
      streamRef.current = stream;
      const track = stream.getAudioTracks()[0];
      console.log("[voice] Microphone acquired:", track.label, "muted:", track.muted);

      // 3. Open dedicated WebSocket
      const sid = sessionId ?? crypto.randomUUID();
      const wsUrl = `${WS_BASE_URL}/api/v1/voice/ws?session_id=${sid}`;
      console.log("[voice] Connecting WebSocket:", wsUrl);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      // 4. Message handler — drives the handshake and processes transcripts
      ws.onmessage = async (event) => {
        let msg: Record<string, unknown>;
        try {
          msg = JSON.parse(event.data as string);
        } catch {
          return;
        }

        const type = msg.type as string;
        console.log("[voice] WS message:", type);

        if (type === "session_ready") {
          ws.send(JSON.stringify({ type: "start_listening", language }));

        } else if (type === "listening_started") {
          setState("listening");
          console.log("[voice] Speechmatics ready — starting audio pipeline");

          // Try AudioWorklet first, fall back to ScriptProcessorNode
          const ok =
            (await tryWorklet(stream, ws)) ||
            (await tryScriptProcessor(stream, ws));

          if (!ok) {
            const err = new Error("Could not start audio capture in this browser");
            setError(err);
            setState("error");
            onError?.(err);
            activeRef.current = false;
            cleanupAudio();
            cleanupWS();
          }

        } else if (type === "transcript") {
          const data = msg.data as { text: string; is_final: boolean; speaker?: string | null };
          const speaker = data.speaker ?? "S1";
          const t: VoiceTranscript = {
            text: data.text,
            is_final: data.is_final,
            timestamp: Date.now(),
            speaker,
          };
          if (data.is_final && data.text.trim()) {
            finalRef.current = (finalRef.current + " " + data.text).trim();
            setTranscript(finalRef.current);
            setPartialText("");
            setPartialSpeaker(null);
            // Merge into utterances: append to last utterance if same speaker, else new entry
            setUtterances((prev) => {
              const last = prev[prev.length - 1];
              if (last && last.speaker === speaker) {
                return [...prev.slice(0, -1), { ...last, text: last.text + " " + data.text }];
              }
              return [...prev, { speaker, text: data.text, timestamp: Date.now() }];
            });
          } else if (!data.is_final && data.text.trim()) {
            setPartialText(data.text);
            setPartialSpeaker(speaker);
          }
          onTranscript?.(t);

        } else if (type === "response") {
          // Hugo's LLM reply — speak it aloud via Web Speech API
          const text = (msg.text as string) || "";
          if (!text) return;
          console.log("[voice] Hugo response:", text);
          onResponse?.(text);
          setState("speaking");
          if ("speechSynthesis" in window) {
            window.speechSynthesis.cancel(); // stop any previous speech
            const utt = new SpeechSynthesisUtterance(text);
            utt.lang = language;
            utt.rate = 1.0;
            utt.pitch = 1.0;
            utt.onend = () => setState("listening");
            utt.onerror = () => setState("listening");
            window.speechSynthesis.speak(utt);
          } else {
            setState("listening");
          }

        } else if (type === "error") {
          const err = new Error((msg.message as string) || "Voice error");
          console.error("[voice] Backend error:", err.message);
          setError(err);
          setState("error");
          onError?.(err);
          activeRef.current = false;
          cleanupAudio();
        }
      };

      ws.onerror = (e) => {
        console.error("[voice] WebSocket error:", e);
        if (!activeRef.current) return;
        const err = new Error("WebSocket connection failed");
        setError(err);
        setState("error");
        onError?.(err);
        activeRef.current = false;
        cleanupAudio();
      };

      ws.onclose = (e) => {
        console.log("[voice] WebSocket closed:", e.code, e.reason);
        if (!activeRef.current) return;
        activeRef.current = false;
        cleanupAudio();
        if (e.code !== 1000) {
          const err = new Error(`Connection closed (${e.code})`);
          setError(err);
          setState("error");
          onError?.(err);
        } else {
          setState("idle");
        }
      };
    } catch (err) {
      const e = err instanceof Error ? err : new Error(String(err));
      console.error("[voice] startListening error:", e.message);
      setError(e);
      setState("error");
      onError?.(e);
      activeRef.current = false;
      cleanupAudio();
    }
  }, [
    sessionId,
    language,
    onTranscript,
    onResponse,
    onError,
    tryWorklet,
    tryScriptProcessor,
    cleanupAudio,
    cleanupWS,
  ]);

  const clearTranscript = useCallback(() => {
    finalRef.current = "";
    setTranscript("");
    setPartialText("");
    setPartialSpeaker(null);
    setUtterances([]);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      activeRef.current = false;
      cleanupAudio();
      cleanupWS();
    };
  }, [cleanupAudio, cleanupWS]);

  return {
    state,
    transcript,
    partialText,
    partialSpeaker,
    micLevel,
    isListening: state === "listening",
    startListening,
    stopListening,
    clearTranscript,
    error,
    utterances,
  };
}
