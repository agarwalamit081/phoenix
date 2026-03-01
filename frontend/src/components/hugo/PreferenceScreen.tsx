import { motion, AnimatePresence } from "framer-motion";
import { useState, useEffect, useRef } from "react";
import { Mic, MicOff, X, RotateCcw, Sparkles } from "lucide-react";
import { useUserLocation } from "@/contexts/UserLocationContext";
import { useVoiceInput } from "@/hooks/useVoiceInput";

interface PreferenceScreenProps {
  onGenerateRoute: () => void;
}

interface Entity {
  label: string;
  category: string;
}

const DEFAULT_ENTITIES: Entity[] = [
  { label: "Hidden spots", category: "Interest" },
  { label: "Local cafés", category: "Food" },
  { label: "Street art", category: "Interest" },
  { label: "90 minutes", category: "Time" },
  { label: "Moderate pace", category: "Pace" },
  { label: "Low crowds", category: "Crowd" },
  { label: "Flexible budget", category: "Budget" },
];

// Colours cycling through speakers S1, S2, S3 …
const SPEAKER_PALETTE = [
  { dot: "bg-primary",     label: "text-primary",     bubble: "bg-primary/10 border-primary/20" },
  { dot: "bg-accent",      label: "text-accent",      bubble: "bg-accent/10 border-accent/20" },
  { dot: "bg-rose-400",    label: "text-rose-400",    bubble: "bg-rose-400/10 border-rose-400/20" },
  { dot: "bg-amber-400",   label: "text-amber-400",   bubble: "bg-amber-400/10 border-amber-400/20" },
];

function speakerStyle(speaker: string) {
  // "S1" → 0, "S2" → 1, etc.  Anything else → 0
  const idx = /^S(\d+)$/.test(speaker) ? (parseInt(speaker.slice(1), 10) - 1) : 0;
  return SPEAKER_PALETTE[idx % SPEAKER_PALETTE.length];
}

const CATEGORY_COLORS: Record<string, string> = {
  Interest: "bg-primary/15 text-primary border-primary/30",
  Food: "bg-accent/15 text-accent border-accent/30",
  Time: "bg-rose-500/15 text-rose-400 border-rose-500/30",
  Pace: "bg-muted text-foreground border-border",
  Crowd: "bg-muted text-foreground border-border",
  Budget: "bg-muted text-foreground border-border",
};

const PreferenceScreen = ({ onGenerateRoute }: PreferenceScreenProps) => {
  const { userLocation } = useUserLocation();
  const sessionId = useRef(crypto.randomUUID()).current;

  const { state, transcript, partialText, partialSpeaker, micLevel, startListening, stopListening, clearTranscript, error, utterances } =
    useVoiceInput({
      language: "en",
      sessionId,
      onTranscript: (t) => {
        if (t.is_final) console.log("[Hugo] transcript:", t.speaker, t.text);
      },
      onError: (e) => console.error("[Hugo] voice error:", e.message),
    });

  const [entities, setEntities] = useState<Entity[]>([]);
  const [showEntities, setShowEntities] = useState(false);
  const startedRef = useRef(false);

  // Auto-start microphone on mount (only once)
  useEffect(() => {
    if (!startedRef.current && state === "idle") {
      startedRef.current = true;
      startListening();
    }
  }, [state, startListening]);

  // Reveal entity tags after enough speech has been collected
  const totalText = transcript + " " + partialText;
  useEffect(() => {
    if (totalText.trim().length > 20 && !showEntities) {
      const timer = setTimeout(() => {
        setEntities(DEFAULT_ENTITIES);
        setShowEntities(true);
      }, 800);
      return () => clearTimeout(timer);
    }
  }, [totalText, showEntities]);

  const handleRedo = () => {
    clearTranscript();
    setEntities([]);
    setShowEntities(false);
    startListening();
  };

  const handleMicToggle = () => {
    if (state === "listening" || state === "connecting") {
      stopListening();
    } else {
      clearTranscript();
      setEntities([]);
      setShowEntities(false);
      startListening();
    }
  };

  const removeEntity = (label: string) =>
    setEntities((prev) => prev.filter((e) => e.label !== label));

  // ── status indicator ──────────────────────────────────────────────────────
  const statusText =
    state === "connecting" ? "Connecting…" :
    state === "listening" ? (transcript ? "Listening… Speak now" : "Listening…") :
    state === "error" ? (error?.message ?? "Error — tap mic to retry") :
    showEntities ? "Got it!" :
    "Tap the mic to speak";

  const dotColor =
    state === "listening" ? "bg-accent animate-pulse" :
    state === "connecting" ? "bg-primary animate-pulse" :
    state === "error" ? "bg-destructive" :
    "bg-muted-foreground";

  return (
    <div className="min-h-screen bg-background flex flex-col relative overflow-hidden">
      {/* Header */}
      <motion.div
        className="pt-14 pb-4 px-5 relative z-10"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h2 className="font-display font-bold text-xl text-foreground">
          Tell Hugo what you're into
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Speak naturally — Hugo picks up the details.
        </p>
      </motion.div>

      {/* Main content */}
      <div className="flex-1 px-5 pb-4 overflow-y-auto">

        {/* Mic level bar — visible when listening */}
        {state === "listening" && (
          <div className="w-full h-1.5 rounded-full bg-muted mb-3 overflow-hidden">
            <div
              className="h-full bg-accent rounded-full transition-all duration-75"
              style={{ width: `${Math.min(100, micLevel * 600)}%` }}
            />
          </div>
        )}

        {/* Status row */}
        <motion.div
          className="flex items-center gap-2 mb-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
        >
          <div className={`w-2 h-2 rounded-full flex-shrink-0 ${dotColor}`} />
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            {statusText}
          </span>
          {state === "listening" && (
            <div className="flex gap-[2px] ml-1">
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

        {/* Diarized conversation thread */}
        <motion.div
          className="glass rounded-2xl p-4 mb-5 min-h-[80px] flex flex-col gap-3 cursor-pointer"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          onClick={handleMicToggle}
        >
          {utterances.length === 0 && !partialText ? (
            <p className="text-sm text-muted-foreground leading-relaxed self-center my-auto">
              {state === "connecting"
                ? "Connecting to voice service…"
                : state === "listening"
                ? "Listening… Speak now"
                : state === "error"
                ? error?.message ?? "Something went wrong"
                : "Tap to start speaking…"}
            </p>
          ) : (
            <>
              <AnimatePresence initial={false}>
                {utterances.map((u, i) => {
                  const s = speakerStyle(u.speaker);
                  return (
                    <motion.div
                      key={i}
                      className="flex items-start gap-2"
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.2 }}
                    >
                      {/* Speaker dot + label */}
                      <div className="flex flex-col items-center gap-1 pt-0.5 flex-shrink-0">
                        <div className={`w-2 h-2 rounded-full ${s.dot}`} />
                      </div>
                      <div className="flex flex-col min-w-0">
                        <span className={`text-[10px] font-bold uppercase tracking-wider mb-0.5 ${s.label}`}>
                          {u.speaker}
                        </span>
                        <div className={`rounded-xl px-3 py-2 border text-sm text-foreground leading-relaxed ${s.bubble}`}>
                          {u.text}
                        </div>
                      </div>
                    </motion.div>
                  );
                })}
              </AnimatePresence>

              {/* Live partial text with speaker indicator */}
              {partialText && (
                <motion.div
                  className="flex items-start gap-2"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                >
                  <div className="flex flex-col items-center gap-1 pt-0.5 flex-shrink-0">
                    <div className={`w-2 h-2 rounded-full ${speakerStyle(partialSpeaker ?? "S1").dot} animate-pulse`} />
                  </div>
                  <div className="flex flex-col min-w-0">
                    <span className={`text-[10px] font-bold uppercase tracking-wider mb-0.5 ${speakerStyle(partialSpeaker ?? "S1").label}`}>
                      {partialSpeaker ?? "…"}
                    </span>
                    <div className={`rounded-xl px-3 py-2 border text-sm text-muted-foreground leading-relaxed ${speakerStyle(partialSpeaker ?? "S1").bubble}`}>
                      {partialText}
                      <motion.span
                        className="inline-block w-1 h-3.5 bg-current rounded-full ml-1 align-middle opacity-70"
                        animate={{ opacity: [0.7, 0] }}
                        transition={{ duration: 0.5, repeat: Infinity }}
                      />
                    </div>
                  </div>
                </motion.div>
              )}
            </>
          )}
        </motion.div>

        {/* Mic button */}
        <div className="flex justify-center mb-6">
          <motion.button
            onClick={handleMicToggle}
            className={`w-16 h-16 rounded-full flex items-center justify-center transition-colors ${
              state === "listening"
                ? "bg-accent text-white shadow-lg shadow-accent/30"
                : state === "connecting"
                ? "bg-primary/40 text-white"
                : state === "error"
                ? "bg-destructive/80 text-white"
                : "bg-muted text-muted-foreground"
            }`}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            {state === "listening" || state === "connecting" ? (
              <Mic size={24} />
            ) : (
              <MicOff size={24} />
            )}
          </motion.button>
        </div>

        {/* Detected entities */}
        <AnimatePresence>
          {showEntities && (
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
            >
              <div className="flex items-center gap-2 mb-3">
                <Sparkles size={14} className="text-primary" />
                <span className="text-xs font-bold text-primary uppercase tracking-wider">
                  Detected preferences
                </span>
              </div>

              <div className="flex flex-wrap gap-2 mb-4">
                {entities.map((entity, i) => (
                  <motion.div
                    key={entity.label}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-semibold ${
                      CATEGORY_COLORS[entity.category] ?? "bg-muted text-foreground border-border"
                    }`}
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: i * 0.07 }}
                    layout
                  >
                    <span className="text-[10px] text-muted-foreground mr-0.5">
                      {entity.category}
                    </span>
                    {entity.label}
                    <button
                      onClick={() => removeEntity(entity.label)}
                      className="ml-1 opacity-50 hover:opacity-100"
                    >
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
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Bottom CTA */}
      <div
        className="sticky bottom-0 px-5 pb-8 pt-4"
        style={{
          background:
            "linear-gradient(to top, hsl(var(--void-black)) 70%, transparent)",
        }}
      >
        <motion.button
          onClick={onGenerateRoute}
          disabled={!showEntities}
          className={`w-full py-4 rounded-2xl font-display font-bold text-base flex items-center justify-center gap-2 transition-all ${
            showEntities
              ? "bg-primary text-primary-foreground glow-violet"
              : "bg-muted text-muted-foreground cursor-not-allowed"
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
