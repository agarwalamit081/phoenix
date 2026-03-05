import { motion, AnimatePresence } from "framer-motion";
import { useState, useEffect } from "react";
import { Mic, X, RotateCcw, Sparkles } from "lucide-react";

interface PreferenceScreenProps {
  onGenerateRoute: () => void;
}

interface Entity {
  label: string;
  category: string;
  confirmed: boolean;
}

const simulatedTranscript = [
  { text: "I'm visiting Paris for the first time...", delay: 800 },
  { text: "I like hidden spots, local cafés, and street art.", delay: 2200 },
  { text: "Not too touristy. I have about 90 minutes.", delay: 3800 },
  { text: "I walk at a moderate pace. Budget is flexible.", delay: 5200 },
];

const detectedEntities: Entity[] = [
  { label: "Hidden spots", category: "Interest", confirmed: true },
  { label: "Local cafés", category: "Food", confirmed: true },
  { label: "Street art", category: "Interest", confirmed: true },
  { label: "90 minutes", category: "Time", confirmed: true },
  { label: "Moderate pace", category: "Pace", confirmed: true },
  { label: "Low crowds", category: "Crowd", confirmed: true },
  { label: "Flexible budget", category: "Budget", confirmed: true },
];

const categoryColors: Record<string, string> = {
  Interest: "bg-primary/15 text-primary border-primary/30",
  Food: "bg-accent/15 text-accent border-accent/30",
  Time: "bg-rose/15 text-rose border-rose/30",
  Pace: "bg-muted text-foreground border-border",
  Crowd: "bg-muted text-foreground border-border",
  Budget: "bg-muted text-foreground border-border",
};

const PreferenceScreen = ({ onGenerateRoute }: PreferenceScreenProps) => {
  const [transcriptIndex, setTranscriptIndex] = useState(0);
  const [showEntities, setShowEntities] = useState(false);
  const [entities, setEntities] = useState<Entity[]>([]);
  const [isListening, setIsListening] = useState(true);

  useEffect(() => {
    // Simulate transcript appearing
    const timers = simulatedTranscript.map((item, i) =>
      setTimeout(() => setTranscriptIndex(i + 1), item.delay)
    );
    // Show entities after transcript
    const entityTimer = setTimeout(() => {
      setShowEntities(true);
      setIsListening(false);
      setEntities(detectedEntities);
    }, 6500);

    return () => {
      timers.forEach(clearTimeout);
      clearTimeout(entityTimer);
    };
  }, []);

  const removeEntity = (label: string) => {
    setEntities((prev) => prev.filter((e) => e.label !== label));
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
          <div className={`w-2 h-2 rounded-full ${isListening ? "bg-accent animate-pulse" : "bg-primary"}`} />
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            {isListening ? "Listening..." : "Got it!"}
          </span>
          {isListening && (
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
        <div className="glass rounded-2xl p-4 mb-5">
          <AnimatePresence>
            {simulatedTranscript.slice(0, transcriptIndex).map((item, i) => (
              <motion.p
                key={i}
                className="text-sm text-foreground leading-relaxed mb-1.5 last:mb-0"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
              >
                {item.text}
              </motion.p>
            ))}
          </AnimatePresence>
          {isListening && transcriptIndex > 0 && (
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
                    key={entity.label}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-semibold ${categoryColors[entity.category] || "bg-muted text-foreground border-border"}`}
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: i * 0.08 }}
                    layout
                  >
                    <span className="text-[10px] text-muted-foreground mr-0.5">{entity.category}</span>
                    {entity.label}
                    <button onClick={() => removeEntity(entity.label)} className="ml-1 opacity-50 hover:opacity-100">
                      <X size={10} />
                    </button>
                  </motion.div>
                ))}
              </div>

              <div className="flex items-center gap-2 mb-4">
                <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-secondary text-secondary-foreground text-xs font-medium">
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
