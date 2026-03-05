import { motion, AnimatePresence } from "framer-motion";
import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import { X, RotateCcw, Sparkles } from "lucide-react";
import { useUserLocation } from "@/contexts/UserLocationContext";
import { useVoiceInput } from "@/hooks/useVoiceInput";

interface PreferenceScreenProps {
  onGenerateRoute: () => void;
}

interface Entity {
  label: string;
  category: string;
  confirmed: boolean;
}

interface ConversationTurn {
  role: "user" | "assistant";
  text: string;
}

const categoryColors: Record<string, string> = {
  Interest: "bg-primary/15 text-primary border-primary/30",
  Food: "bg-accent/15 text-accent border-accent/30",
  Time: "bg-rose/15 text-rose border-rose/30",
  Pace: "bg-muted text-foreground border-border",
  Crowd: "bg-muted text-foreground border-border",
  Budget: "bg-muted text-foreground border-border",
};

const PreferenceScreen = ({ onGenerateRoute }: PreferenceScreenProps) => {
  // Get user location from context
  const contextLocation = useUserLocation();
  const city = contextLocation.userLocation?.city || "this city";

  const autoStartedRef = useRef(false);
  const isMountedRef = useRef(true);
  const isSpeakingRef = useRef(false);
  const lastAssistantResponseRef = useRef("");
  const pendingUserTurnRef = useRef("");
  const finalizeTurnTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const normalizeForComparison = useCallback((text: string) => {
    return text
      .toLowerCase()
      .replace(/[^\w\s]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }, []);

  const sanitizeForSpeech = useCallback((text: string) => {
    return text
      .replace(/```[\s\S]*?```/g, " ")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/\*\*([^*]+)\*\*/g, "$1")
      .replace(/\*([^*]+)\*/g, "$1")
      .replace(/__([^_]+)__/g, "$1")
      .replace(/_([^_]+)_/g, "$1")
      .replace(/^\s{0,3}#{1,6}\s+/gm, "")
      .replace(/^\s*[-*+]\s+/gm, "")
      .replace(/^\s*\d+\.\s+/gm, "")
      .replace(/[*_~`#>|[\]]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }, []);

  const mergeTranscript = useCallback((existing: string, incoming: string) => {
    const left = existing.trim();
    const right = incoming.trim();
    if (!right) return left;
    if (!left) return right;
    if (left.includes(right)) return left;
    if (right.includes(left)) return right;

    const maxOverlap = Math.min(left.length, right.length);
    for (let overlap = maxOverlap; overlap > 0; overlap -= 1) {
      if (left.endsWith(right.slice(0, overlap))) {
        return `${left}${right.slice(overlap)}`.trim();
      }
    }
    return `${left} ${right}`.trim();
  }, []);

  const pickBestVoice = useCallback(() => {
    const voices = window.speechSynthesis.getVoices();
    if (!voices.length) return undefined;
    const preferred = voices.find((voice) =>
      /(en-us|en-gb|natural|neural|siri|google us english)/i.test(
        `${voice.lang} ${voice.name}`,
      ),
    );
    return preferred ?? voices.find((voice) => /^en/i.test(voice.lang)) ?? voices[0];
  }, []);

  const speakWithBrowserFallback = useCallback(async (text: string) => {
    if (!("speechSynthesis" in window) || !text.trim()) return;
    window.speechSynthesis.cancel();

    await new Promise<void>((resolve) => {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.98;
      utterance.pitch = 1;
      utterance.voice = pickBestVoice() ?? null;
      utterance.onend = () => resolve();
      utterance.onerror = () => resolve();
      window.speechSynthesis.speak(utterance);
    });
  }, [pickBestVoice]);

  const speakResponse = useCallback(async (text: string) => {
    const spokenText = sanitizeForSpeech(text);
    if (!spokenText) return;

    const playAudioBlob = async (audioBlob: Blob) => {
      if (!audioBlob.size) {
        throw new Error("Empty TTS audio");
      }
      const objectUrl = URL.createObjectURL(audioBlob);
      try {
        await new Promise<void>((resolve, reject) => {
          const audio = new Audio(objectUrl);
          audio.onended = () => resolve();
          audio.onerror = () => reject(new Error("Audio playback failed"));
          void audio.play().catch((err) => reject(err));
        });
      } finally {
        URL.revokeObjectURL(objectUrl);
      }
    };

    const params = new URLSearchParams({
      text: spokenText,
      language: "en",
    });

    try {
      let response = await fetch(`/api/v1/voice/tts?${params.toString()}`, {
        method: "POST",
      });

      if (response.status === 422) {
        response = await fetch("/api/v1/voice/tts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text: spokenText,
            language: "en",
          }),
        });
      }

      if (!response.ok) {
        throw new Error(`TTS failed with status ${response.status}`);
      }

      const contentType = response.headers.get("content-type") ?? "";
      if (contentType.includes("audio")) {
        const audioBlob = await response.blob();
        await playAudioBlob(audioBlob);
        return;
      }

      const payload = await response.json().catch(() => null) as
        | { audio_base64?: string; audio_url?: string; url?: string; audio_size?: number }
        | null;

      if (payload?.audio_base64) {
        const binary = atob(payload.audio_base64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i += 1) {
          bytes[i] = binary.charCodeAt(i);
        }
        await playAudioBlob(new Blob([bytes], { type: "audio/mpeg" }));
        return;
      }

      const audioUrl = payload?.audio_url ?? payload?.url;
      if (audioUrl) {
        const proxyResponse = await fetch(audioUrl);
        if (!proxyResponse.ok) {
          throw new Error(`Failed loading audio URL (${proxyResponse.status})`);
        }
        await playAudioBlob(await proxyResponse.blob());
        return;
      }

      if (typeof payload?.audio_size === "number" && payload.audio_size === 0) {
        throw new Error("Backend TTS returned empty audio payload");
      }

      throw new Error(`TTS response had no playable audio (size=${payload?.audio_size ?? "unknown"})`);
    } catch {
      // Guaranteed fallback so user always hears a response even if backend TTS fails.
      await speakWithBrowserFallback(spokenText);
    }
  }, [sanitizeForSpeech, speakWithBrowserFallback]);

  const [entities, setEntities] = useState<Entity[]>([]);
  const [showEntities, setShowEntities] = useState(false);
  const [conversationTurns, setConversationTurns] = useState<ConversationTurn[]>([]);
  const [currentPartial, setCurrentPartial] = useState("");
  const spokenText = useMemo(() => {
    const userTurns = conversationTurns
      .filter((turn) => turn.role === "user")
      .map((turn) => turn.text);
    return [...userTurns, currentPartial].join(" ").trim();
  }, [conversationTurns, currentPartial]);

  const appendTurn = useCallback((role: "user" | "assistant", text: string) => {
    const cleaned = text.trim();
    if (!cleaned) return;
    setConversationTurns((prev) => {
      const last = prev[prev.length - 1];
      if (last && last.role === role && normalizeForComparison(last.text) === normalizeForComparison(cleaned)) {
        return prev;
      }
      return [...prev.slice(-19), { role, text: cleaned }];
    });
  }, [normalizeForComparison]);

  const updateCityFromText = useCallback((text: string) => {
    const compact = text.replace(/\s+/g, " ").trim();
    const match = compact.match(/\b(?:in|at|from)\s+([A-Za-z][A-Za-z\s'-]{1,60})/i);
    if (!match?.[1]) return;
    const candidate = match[1]
      .split(/\b(?:and|for|with|where|which|that|who|i|we)\b/i)[0]
      .split(",")[0]
      .replace(/[^A-Za-z\s'-]/g, "")
      .trim()
      .split(/\s+/)
      .slice(0, 3)
      .join(" ");
    if (!candidate) return;
    const cityName = candidate
      .toLowerCase()
      .split(" ")
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
    contextLocation.updateCity(cityName);
  }, [contextLocation]);

  const pushPendingUserTurn = useCallback(() => {
    const pending = pendingUserTurnRef.current.trim();
    if (!pending) return;
    appendTurn("user", pending);
    updateCityFromText(pending);
    pendingUserTurnRef.current = "";
    setCurrentPartial("");
  }, [appendTurn, updateCityFromText]);

  useEffect(() => {
    return () => {
      if (finalizeTurnTimerRef.current !== null) {
        window.clearTimeout(finalizeTurnTimerRef.current);
      }
    };
  }, []);

  // Voice input hook via backend websocket path (Speechmatics + LLM)
  const {
    state: voiceState,
    isListening,
    startListening,
    stopListening,
    clearTranscript,
  } = useVoiceInput({
    language: "en",
    onTranscript: (data) => {
      console.log('[PreferenceScreen] Transcript:', data);
      const cleaned = data.text.trim();
      if (!cleaned) return;
      if (data.is_final) {
        const merged = mergeTranscript(pendingUserTurnRef.current, cleaned);
        pendingUserTurnRef.current = merged;
        setCurrentPartial(merged);
        if (finalizeTurnTimerRef.current !== null) {
          window.clearTimeout(finalizeTurnTimerRef.current);
        }
        finalizeTurnTimerRef.current = window.setTimeout(() => {
          pushPendingUserTurn();
        }, 900);
      } else {
        const mergedPartial = mergeTranscript(pendingUserTurnRef.current, cleaned);
        setCurrentPartial(mergedPartial);
      }
    },
    onResponse: (text) => {
      console.log("[PreferenceScreen] Response:", text);
      const cleaned = text.trim();
      if (!cleaned) return;

      const normalized = normalizeForComparison(cleaned);
      const lastNormalized = lastAssistantResponseRef.current;
      if (
        normalized &&
        lastNormalized &&
        (normalized === lastNormalized ||
          normalized.includes(lastNormalized) ||
          lastNormalized.includes(normalized))
      ) {
        return;
      }
      lastAssistantResponseRef.current = normalized;
      pushPendingUserTurn();
      appendTurn("assistant", cleaned);

      if (isSpeakingRef.current) return;
      isSpeakingRef.current = true;
      stopListening();
      window.speechSynthesis.cancel();

      void speakResponse(cleaned).finally(() => {
        if (!isMountedRef.current) return;
        isSpeakingRef.current = false;
        startListening();
      });
    },
    onError: (error) => console.error('[PreferenceScreen] Voice error:', error),
  });

  // Log state changes for debugging
  useEffect(() => {
    console.log('[PreferenceScreen] voiceState changed:', voiceState);
  }, [voiceState]);

  // Simulate entity extraction from transcript (in production, this would come from backend)
  useEffect(() => {
    if (!spokenText.trim()) return;
    const keywords = spokenText
      .split(/\s+/)
      .map((w) => w.replace(/[^\w-]/g, "").trim())
      .filter((w) => w.length > 3)
      .slice(-6);
    if (!keywords.length) return;
    setEntities(
      keywords.map((label) => ({
        label,
        category: "Mention",
        confirmed: true,
      })),
    );
    setShowEntities(true);
  }, [spokenText]);

  // Auto-start listening once on mount
  useEffect(() => {
    if (!autoStartedRef.current) {
      autoStartedRef.current = true;
      console.log("[PreferenceScreen] Auto-starting voice input once");
      startListening();
    }
  }, [startListening]);

  const removeEntity = (indexToRemove: number) => {
    setEntities((prev) => prev.filter((_, index) => index !== indexToRemove));
  };

  const handleRedo = () => {
    clearTranscript();
    window.speechSynthesis?.cancel();
    pendingUserTurnRef.current = "";
    setCurrentPartial("");
    setConversationTurns([]);
    lastAssistantResponseRef.current = "";
    setShowEntities(false);
    setEntities([]);
    startListening();
  };

  // Display transcript with tap-to-listen
  const handleTapToListen = () => {
    if (!isListening) {
      clearTranscript();
      window.speechSynthesis?.cancel();
      pendingUserTurnRef.current = "";
      setCurrentPartial("");
      setConversationTurns([]);
      lastAssistantResponseRef.current = "";
      setShowEntities(false);
      setEntities([]);
      startListening();
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col relative overflow-hidden">
      {/* Header */}
      <motion.div
        className="pt-14 pb-4 px-5 relative z-10"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      >
        <h2 className="font-display font-bold text-xl text-foreground">
          Tell Hugo what you're into
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Speak naturally — Hugo picks up the details.
        </p>
      </motion.div>

      {/* Transcript area */}
      <div className="flex-1 px-5 pb-4 overflow-y-auto">
        {/* Voice status */}
        <motion.div
          className="flex items-center gap-2 mb-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
        >
          <div className={`w-2 h-2 rounded-full ${
            voiceState === "listening" ? "bg-accent animate-pulse" :
            voiceState === "thinking" ? "bg-primary animate-pulse" :
            voiceState === "error" ? "bg-destructive" :
            "bg-primary"
          }`} />
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            {voiceState === "connecting" && "Connecting..."}
            {voiceState === "listening" && "Listening..."}
            {voiceState === "thinking" && "Processing..."}
            {voiceState === "idle" && showEntities && "Got it!"}
            {voiceState === "error" && "Error - tap to retry"}
          </span>
          {voiceState === "listening" && (
            <div className="flex gap-[2px] ml-2">
              {[0, 1, 2, 3, 4].map((i) => (
                <motion.div
                  key={i}
                  className="w-[3px] rounded-full bg-accent"
                  animate={{ height: ["4px", "16px", "4px"] }}
                  transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.1 }}
                />
              ))}
            </div>
          )}
        </motion.div>

        {/* Live transcript */}
        <div
          className="glass rounded-2xl p-4 mb-5 cursor-pointer"
          onClick={handleTapToListen}
        >
          <AnimatePresence>
            {conversationTurns.length > 0 || currentPartial ? (
              <div className="space-y-2">
                {conversationTurns.map((turn, i) => (
                  <motion.p
                    key={`${turn.role}-${i}`}
                    className={`text-sm leading-relaxed ${
                      turn.role === "assistant" ? "text-primary" : "text-foreground"
                    }`}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                  >
                    <span className="text-muted-foreground">{turn.role === "assistant" ? "Hugo" : "You"}:</span>{" "}
                    {turn.text}
                  </motion.p>
                ))}
                {currentPartial && (
                  <motion.p
                    key="u-partial"
                    className="text-sm text-foreground/80 leading-relaxed italic"
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <span className="text-muted-foreground">You:</span> {currentPartial}
                  </motion.p>
                )}
              </div>
            ) : voiceState === "connecting" ? (
              <motion.p
                className="text-sm text-muted-foreground leading-relaxed"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                Connecting to voice service...
              </motion.p>
            ) : voiceState === "listening" ? (
              <motion.p
                className="text-sm text-muted-foreground leading-relaxed"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.3 }}
              >
                Listening... Speak now.
              </motion.p>
            ) : voiceState === "speaking" ? (
              <motion.p
                className="text-sm text-muted-foreground leading-relaxed"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                Hugo is responding...
              </motion.p>
            ) : (
              <motion.p
                className="text-sm text-muted-foreground leading-relaxed"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                Tap to start speaking...
              </motion.p>
            )}
          </AnimatePresence>
          {voiceState === "listening" && (
            <motion.span
              className="inline-block w-1.5 h-4 bg-primary rounded-full ml-1"
              animate={{ opacity: [1, 0] }}
              transition={{ duration: 0.6, repeat: Infinity }}
            />
          )}
        </div>

        {/* Detected entities */}
        <AnimatePresence>
          {showEntities && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
            >
              <div className="flex items-center gap-2 mb-3">
                <Sparkles size={14} className="text-primary" />
                <span className="text-xs font-bold text-primary uppercase tracking-wider">
                  Detected preferences
                </span>
              </div>

              <div className="flex flex-wrap gap-2 mb-6">
                {entities.map((entity, i) => (
                  <motion.div
                    key={`${entity.label}-${i}`}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-semibold ${categoryColors[entity.category] || "bg-muted text-foreground border-border"}`}
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: i * 0.08 }}
                    layout
                  >
                    <span className="text-[10px] text-muted-foreground mr-0.5">{entity.category}</span>
                    {entity.label}
                    <button onClick={() => removeEntity(i)} className="ml-1 opacity-50 hover:opacity-100">
                      <X size={10} />
                    </button>
                  </motion.div>
                ))}
              </div>

              <div className="flex items-center gap-2 mb-4">
                <button
                  onClick={handleRedo}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-secondary text-secondary-foreground text-xs font-medium"
                >
                  <RotateCcw size={12} />
                  Redo
                </button>
                <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-secondary text-secondary-foreground text-xs font-medium">
                  + Add more
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Bottom CTA */}
      <div className="sticky bottom-0 px-5 pb-8 pt-4" style={{ background: "linear-gradient(to top, hsl(var(--void-black)) 70%, transparent)" }}>
        <motion.button
          onClick={onGenerateRoute}
          disabled={!showEntities}
          className={`w-full py-4 rounded-2xl font-display font-bold text-base flex items-center justify-center gap-2 transition-all ${
            showEntities
              ? "bg-primary text-primary-foreground glow-violet"
              : "bg-muted text-muted-foreground"
          }`}
          whileHover={showEntities ? { scale: 1.02 } : {}}
          whileTap={showEntities ? { scale: 0.98 } : {}}
        >
          <Sparkles size={18} />
          Generate my route
        </motion.button>
      </div>
    </div>
  );
};

export default PreferenceScreen;
