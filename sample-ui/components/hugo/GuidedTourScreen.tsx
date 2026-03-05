import { motion, AnimatePresence } from "framer-motion";
import { useState, useEffect } from "react";
import {
  Pause, Play, RotateCcw, MessageCircle, Languages, Bookmark,
  Mic, ChevronUp, Volume2, Clock, Footprints, Navigation, MapPin
} from "lucide-react";
import parisCafe from "@/assets/paris-cafe.jpg";

interface GuidedTourScreenProps {
  onOpenMemory: () => void;
}

type NarrationDepth = "30s" | "2min" | "deep";

const stops = [
  { title: "Café Lomi", done: true },
  { title: "Rue Dénoyez", done: false, active: true },
  { title: "Marché des Enfants Rouges", done: false },
];

const narrationText: Record<NarrationDepth, string> = {
  "30s": "Rue Dénoyez is a living street-art canvas in Belleville. Artists repaint the walls monthly — what you see today won't exist next week.",
  "2min": "Rue Dénoyez started as an ordinary Belleville street until the early 2000s, when local artists began covering its walls with murals. Today it's Paris' most dynamic open-air gallery — the artwork changes every few weeks as new pieces go up over old ones. It's become a symbol of how art can transform a neighbourhood. Walk slowly and look for the smaller stencils hidden between the big murals.",
  "deep": "Rue Dénoyez is a living testament to Paris' evolving relationship with street art. In the early 2000s, as Belleville gentrified, local artists began using this quiet residential street as a canvas — partly in protest, partly in celebration. The walls are repainted so frequently that photographers have documented the same spots over years to track the evolution. Notable artists like Jérôme Mesnager and C215 have left marks here. The street also hosts the annual Fête de la Rue Dénoyez. Today, it sits at the intersection of grassroots culture and tourism — a microcosm of how cities balance authenticity with popularity.",
};

const GuidedTourScreen = ({ onOpenMemory }: GuidedTourScreenProps) => {
  const [isPaused, setIsPaused] = useState(false);
  const [depth, setDepth] = useState<NarrationDepth>("30s");
  const [isSpeaking, setIsSpeaking] = useState(true);
  const [progress, setProgress] = useState(45); // percent through route
  const [showActions, setShowActions] = useState(false);

  // Simulate speaking
  useEffect(() => {
    if (!isPaused) {
      const timer = setInterval(() => {
        setProgress((p) => Math.min(p + 0.3, 100));
      }, 300);
      return () => clearInterval(timer);
    }
  }, [isPaused]);

  return (
    <div className="min-h-screen bg-background flex flex-col relative">
      {/* Route progress bar */}
      <div className="fixed top-0 left-0 right-0 z-40">
        <div className="h-1 bg-muted">
          <motion.div
            className="h-full bg-gradient-to-r from-primary to-accent"
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.3 }}
          />
        </div>
      </div>

      {/* Now guiding header */}
      <motion.div
        className="pt-6 pb-3 px-5 glass-strong relative z-30"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-accent animate-pulse" />
            <span className="text-xs font-bold text-accent uppercase tracking-wider">Now guiding</span>
          </div>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1"><Clock size={11} /> 42 min left</span>
            <span className="flex items-center gap-1"><Footprints size={11} /> 1.2 km</span>
          </div>
        </div>

        {/* Stop progress */}
        <div className="flex items-center gap-1.5 mt-3">
          {stops.map((stop, i) => (
            <div key={i} className="flex items-center gap-1.5">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold ${
                stop.done ? "bg-accent text-accent-foreground" : stop.active ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
              }`}>
                {stop.done ? "✓" : i + 1}
              </div>
              {i < stops.length - 1 && (
                <div className={`w-8 h-0.5 rounded-full ${stop.done ? "bg-accent" : "bg-muted"}`} />
              )}
            </div>
          ))}
        </div>
      </motion.div>

      {/* Main content */}
      <div className="flex-1 px-5 pb-48 pt-4 overflow-y-auto">
        {/* Current stop card */}
        <motion.div
          className="glass rounded-2xl overflow-hidden"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="relative h-40">
            <img src={parisCafe} alt="Rue Dénoyez" className="w-full h-full object-cover" />
            <div className="absolute inset-0 bg-gradient-to-t from-background/90 to-transparent" />
            <div className="absolute bottom-3 left-3 right-3">
              <div className="flex items-center gap-2">
                <MapPin size={14} className="text-accent" />
                <span className="text-xs text-muted-foreground">Stop 2 of 3</span>
              </div>
              <h2 className="font-display font-bold text-lg text-foreground">Rue Dénoyez</h2>
              <p className="text-xs text-muted-foreground">Street art gallery · Belleville</p>
            </div>
          </div>

          {/* Narration depth selector */}
          <div className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <Volume2 size={14} className={isSpeaking ? "text-primary animate-pulse" : "text-muted-foreground"} />
              <span className="text-xs font-semibold text-foreground">Narration depth</span>
            </div>
            <div className="flex gap-2 mb-4">
              {(["30s", "2min", "deep"] as NarrationDepth[]).map((d) => (
                <button
                  key={d}
                  onClick={() => setDepth(d)}
                  className={`flex-1 py-2 rounded-xl text-xs font-bold transition-all ${
                    depth === d ? "glass-violet text-foreground" : "bg-secondary text-muted-foreground"
                  }`}
                >
                  {d === "30s" ? "Quick" : d === "2min" ? "Standard" : "Deep dive"}
                </button>
              ))}
            </div>

            {/* Narration text */}
            <AnimatePresence mode="wait">
              <motion.p
                key={depth}
                className="text-sm text-foreground/80 leading-relaxed"
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -5 }}
              >
                {narrationText[depth]}
              </motion.p>
            </AnimatePresence>
          </div>
        </motion.div>

        {/* Memory update notification */}
        <motion.div
          className="mt-4 glass rounded-xl p-3 flex items-center gap-2"
          initial={{ opacity: 0, x: 30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 2 }}
        >
          <div className="w-1.5 h-1.5 rounded-full bg-primary" />
          <span className="text-xs text-muted-foreground">
            <span className="font-semibold text-foreground">Memory saved:</span> Prefers street art & quiet neighbourhoods
          </span>
        </motion.div>
      </div>

      {/* Bottom controls */}
      <motion.div
        className="fixed bottom-0 left-0 right-0 z-30 px-5 pb-8 pt-4"
        style={{ background: "linear-gradient(to top, hsl(var(--void-black)) 80%, transparent)" }}
        initial={{ y: 60 }}
        animate={{ y: 0 }}
      >
        {/* Quick action bar */}
        <AnimatePresence>
          {showActions && (
            <motion.div
              className="flex gap-2 mb-3 flex-wrap"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 20 }}
            >
              {[
                { icon: RotateCcw, label: "Reroute" },
                { icon: MessageCircle, label: "Ask Hugo" },
                { icon: Languages, label: "Translate" },
                { icon: Bookmark, label: "Save stop" },
              ].map((action) => (
                <button key={action.label} className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-secondary text-secondary-foreground text-xs font-medium">
                  <action.icon size={12} />
                  {action.label}
                </button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        <div className="flex items-center gap-3">
          {/* Expand actions */}
          <motion.button
            onClick={() => setShowActions(!showActions)}
            className="w-10 h-10 rounded-full bg-secondary flex items-center justify-center"
            animate={{ rotate: showActions ? 180 : 0 }}
          >
            <ChevronUp size={16} className="text-secondary-foreground" />
          </motion.button>

          {/* Play/Pause */}
          <motion.button
            onClick={() => setIsPaused(!isPaused)}
            className="flex-1 py-4 rounded-2xl bg-primary text-primary-foreground font-display font-bold text-sm flex items-center justify-center gap-2"
            whileTap={{ scale: 0.97 }}
          >
            {isPaused ? <Play size={18} /> : <Pause size={18} />}
            {isPaused ? "Resume guidance" : "Pause guidance"}
          </motion.button>

          {/* Voice */}
          <motion.button
            onClick={onOpenMemory}
            className="w-10 h-10 rounded-full glass-violet flex items-center justify-center"
            whileTap={{ scale: 0.95 }}
          >
            <Mic size={16} className="text-primary" />
          </motion.button>
        </div>
      </motion.div>
    </div>
  );
};

export default GuidedTourScreen;
