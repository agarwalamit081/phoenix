/**
 * Custom hook for managing voice input with microphone capture.
 * Captures audio from the microphone and streams it to the backend via WebSocket.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { voiceWS } from "@/lib/websocket";

export type VoiceState = "idle" | "connecting" | "listening" | "thinking" | "speaking" | "error";

export interface VoiceTranscript {
  text: string;
  is_final: boolean;
  timestamp: number;
}

export interface UseVoiceInputOptions {
  language?: string;
  onTranscript?: (transcript: VoiceTranscript) => void;
  onResponse?: (text: string) => void;
  onError?: (error: Error) => void;
  sessionId?: string;
}

export interface UseVoiceInputReturn {
  state: VoiceState;
  transcript: string;
  isListening: boolean;
  startListening: () => Promise<void>;
  stopListening: () => void;
  clearTranscript: () => void;
  error: Error | null;
}

/**
 * Custom hook for capturing microphone audio and streaming to backend voice service.
 *
 * @param options - Configuration options
 * @returns Voice input state and control functions
 *
 * @example
 * ```tsx
 * const { state, startListening, stopListening, transcript } = useVoiceInput({
 *   language: 'en',
 *   onTranscript: (t) => console.log(t.text),
 *   sessionId: 'session-123',
 * });
 * ```
 */
export function useVoiceInput(options: UseVoiceInputOptions = {}): UseVoiceInputReturn {
  const { language = "en", onTranscript, onResponse, onError, sessionId } = options;

  const [state, setState] = useState<VoiceState>("idle");
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<Error | null>(null);
  const [isListening, setIsListening] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const unsubscribeRef = useRef<(() => void) | null>(null);
  const finalTranscriptRef = useRef("");
  const isActiveRef = useRef(false); // Track if we're already in the process of starting
  const stateRef = useRef<VoiceState>("idle"); // Ref to track current state for audio processor callback
  const lastStateLogRef = useRef(0); // Track last state log time to avoid spam

  // Update state ref when state changes
  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  // WebSocket transcript handler
  useEffect(() => {
    const unsubscribe = voiceWS.onTranscript((data: VoiceTranscript) => {
      if (data.is_final) {
        finalTranscriptRef.current += " " + data.text;
        setTranscript(finalTranscriptRef.current.trim());
      }

      onTranscript?.(data);
    });

    const unsubscribeResponse = voiceWS.on('response' as any, (event: any) => {
      const text = event?.text ?? event?.data?.text ?? "";
      if (text) {
        onResponse?.(text);
      }
    });

    const unsubscribeError = voiceWS.on('error' as any, (event: any) => {
      const message = event?.message ?? event?.data?.message ?? "Voice service error";
      const err = new Error(message);
      setError(err);
      setState("error");
      onError?.(err);
    });

    unsubscribeRef.current = unsubscribe;

    return () => {
      unsubscribe();
      unsubscribeResponse();
      unsubscribeError();
    };
  }, [onTranscript, onResponse]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      isActiveRef.current = false; // Reset ref on unmount
      setIsListening(false);
      // Stop all media stream tracks
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
      // Close audio context
      if (audioContextRef.current && audioContextRef.current.state !== "closed") {
        audioContextRef.current.close();
        audioContextRef.current = null;
      }
      // Disconnect processor
      if (processorRef.current) {
        processorRef.current.disconnect();
        processorRef.current = null;
      }
    };
  }, []);

  /**
   * Convert Float32Array audio data to PCM 16-bit.
   * Speechmatics requires PCM 16-bit, 16kHz mono format.
   */
  const convertToPCM16 = useCallback((float32Array: Float32Array): ArrayBuffer => {
    const pcm16 = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
      const sample = Math.max(-1, Math.min(1, float32Array[i]));
      pcm16[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    }
    return pcm16.buffer;
  }, []);

  /**
   * Start capturing audio from microphone and streaming to backend.
   */
  const startListening = useCallback(async () => {
    // Prevent multiple simultaneous connections using ref
    if (isActiveRef.current) {
      console.log('[useVoiceInput] Already active (ref), skipping...');
      return;
    }

    // Mark as active immediately
    isActiveRef.current = true;
    setIsListening(true);

    console.log('[useVoiceInput] startListening called, setting state to connecting');

    try {
      setState("connecting");
      setError(null);
      finalTranscriptRef.current = "";
      setTranscript("");

      // Check if browser supports necessary APIs
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error("Microphone access not supported in this browser");
      }
      if (!window.AudioContext && !(window as any).webkitAudioContext) {
        throw new Error("Web Audio API not supported in this browser");
      }

      // List available devices for debugging
      const devices = await navigator.mediaDevices.enumerateDevices();
      const audioInputs = devices.filter(d => d.kind === 'audioinput');
      console.log('[useVoiceInput] Available audio inputs:', audioInputs.map(d => ({ id: d.deviceId, label: d.label || 'Unknown Device' })));

      // Request microphone access - don't force sampleRate, let browser use default
      // The AudioContext will handle resampling to 16kHz
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1, // Mono
          // Keep raw capture to avoid driver/browser DSP zeroing out input on some devices.
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      });

      // Log which device was selected
      const audioTrack = stream.getAudioTracks()[0];
      const settings = audioTrack.getSettings();
      console.log('[useVoiceInput] Selected microphone:', {
        deviceId: audioTrack.label,
        sampleRate: settings.sampleRate,
        channelCount: settings.channelCount,
        enabled: audioTrack.enabled,
        muted: audioTrack.muted,
      });

      // Check if track is muted or disabled
      if (audioTrack.muted) {
        console.warn('[useVoiceInput] WARNING: Audio track is MUTED!');
      }
      if (!audioTrack.enabled) {
        console.warn('[useVoiceInput] WARNING: Audio track is DISABLED!');
      }

      streamRef.current = stream;

      // Clear any stale auth token before connecting
      // Voice WebSocket doesn't require authentication
      localStorage.removeItem('access_token');

      // Connect to WebSocket with session_id as query parameter
      // Note: Connection happens asynchronously
      voiceWS.connect(undefined, sessionId);

      // Start listening on backend
      voiceWS.startListening(language);

      // Set up AudioContext for processing
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      const audioContext = new AudioContextClass({ sampleRate: 16000 });
      audioContextRef.current = audioContext;

      // CRITICAL: Resume AudioContext - browsers suspend it by default
      if (audioContext.state === 'suspended') {
        console.log('[useVoiceInput] Resuming suspended AudioContext');
        await audioContext.resume();
      }
      console.log('[useVoiceInput] AudioContext state:', audioContext.state);

      const source = audioContext.createMediaStreamSource(stream);

      // Create script processor for audio data
      const bufferSize = 4096;
      const processor = audioContext.createScriptProcessor(bufferSize, 1, 1);
      processorRef.current = processor;

      // Process audio chunks - only send when WebSocket is actually connected
      // Add a flag to track first call
      let firstCall = true;
      let logCounter = 0;
      processor.onaudioprocess = (e) => {
        if (firstCall) {
          console.log('[useVoiceInput] Audio processor called for first time!');
          // Check if there's actual audio data
          const float32Data = e.inputBuffer.getChannelData(0);
          const hasAudio = float32Data.some(sample => Math.abs(sample) > 0.001);
          console.log('[useVoiceInput] Audio data present:', hasAudio, 'Buffer length:', float32Data.length);
          firstCall = false;
        }
        // Log every 100th call to see activity without spam
        logCounter++;
        if (logCounter % 100 === 0) {
          console.log('[useVoiceInput] Audio processor called', logCounter, 'times');
        }

        const currentState = stateRef.current;
        const isConnected = voiceWS.isConnected();

        // Log detailed state every 100 calls or when state changes
        const now = Date.now();
        if (now - lastStateLogRef.current > 5000) {
          console.log('[useVoiceInput] State check:', {
            currentState,
            isConnected,
            activeRef: isActiveRef.current,
            listening: isListening,
          });
          lastStateLogRef.current = now;
        }

        // Only send audio when we're in listening state AND WebSocket is connected
        if (currentState === 'listening' && isConnected) {
          const float32Data = e.inputBuffer.getChannelData(0);
          const pcm16Data = convertToPCM16(float32Data);
          voiceWS.sendAudioChunk(pcm16Data);
        }
      };

      // Connect the audio pipeline
      // Important: Connect processor to destination through a muted gain node
      // to avoid feedback loop while still processing audio
      const gainNode = audioContext.createGain();
      gainNode.gain.value = 0; // Mute to prevent feedback
      source.connect(processor);
      processor.connect(gainNode);
      gainNode.connect(audioContext.destination);

      console.log('[useVoiceInput] Audio pipeline connected, waiting for WebSocket connection...');

      // Update state once WebSocket is connected
      const checkConnection = setInterval(() => {
        if (voiceWS.isConnected() && stateRef.current === 'connecting') {
          clearInterval(checkConnection);
          setState('listening');
          console.log('[useVoiceInput] WebSocket connected, now listening');
        }
      }, 100);

    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      console.error('[useVoiceInput] Error starting voice input:', error);
      setError(error);
      setState("error");
      setIsListening(false);
      isActiveRef.current = false;
      onError?.(error);
    }
  }, [sessionId, language, onError, onTranscript, convertToPCM16, isListening]);

  /**
   * Stop capturing audio.
   */
  const stopListening = useCallback(() => {
    console.log('[useVoiceInput] stopListening called');

    // Stop sending audio
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }

    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    // Tell backend to stop listening
    voiceWS.stopListening();

    setState("idle");
    setIsListening(false);
    isActiveRef.current = false;
  }, []);

  /**
   * Clear accumulated transcript.
   */
  const clearTranscript = useCallback(() => {
    finalTranscriptRef.current = "";
    setTranscript("");
  }, []);

  return {
    state,
    transcript,
    isListening,
    startListening,
    stopListening,
    clearTranscript,
    error,
  };
}
