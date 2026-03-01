import { motion, AnimatePresence } from "framer-motion";
import { useState, useEffect, useRef } from "react";
import {
  Pause, Play, RotateCcw, MessageCircle, Languages, Bookmark,
  Mic, ChevronUp, Volume2, VolumeX, Clock, Footprints, Navigation, MapPin, Image as ImageIcon
} from "lucide-react";
import { useUserLocation } from "@/contexts/UserLocationContext";

interface GuidedTourScreenProps {
  onOpenMemory: () => void;
}

interface TourStop {
  title: string;
  done: boolean;
  active?: boolean;
  description?: string;
  image?: string;
}

type NarrationDepth = "30s" | "2min" | "deep";

// Default tour stops - fake monument data for display
const defaultStops: TourStop[] = [
  { title: "Eiffel Tower", done: true, image: "https://images.unsplash.com/photo-1511739001486-6bfe10ce785f?w=800&q=80" },
  { title: "Louvre Museum", done: false, active: true, description: "World's largest art museum, home to the Mona Lisa and Venus de Milo.", image: "https://images.unsplash.com/photo-1499856871958-5b9627545d1a?w=800&q=80" },
  { title: "Notre-Dame", done: false, image: "https://images.unsplash.com/photo-1522093007474-d86e9bf7ba6f?w=800&q=80" },
  { title: "Sacré-Cœur", done: false, image: "https://images.unsplash.com/photo-1550340499-a6c60fc8287c?w=800&q=80" },
];

const defaultNarrationText: Record<NarrationDepth, string> = {
  "30s": "This street art district is a living canvas. Artists repaint the walls monthly — what you see today won't exist next week.",
  "2min": "This area started as an ordinary street until local artists began covering its walls with murals. Today it's the city's most dynamic open-air gallery — the artwork changes every few weeks as new pieces go up over old ones. Walk slowly and look for the smaller stencils hidden between the big murals.",
  "deep": "This district is a living testament to the city's evolving relationship with street art. As the neighborhood gentrified, local artists began using this quiet street as a canvas — partly in protest, partly in celebration. The walls are repainted so frequently that photographers have documented the same spots over years to track the evolution. Today, it sits at the intersection of grassroots culture and tourism — a microcosm of how cities balance authenticity with popularity.",
};

const GuidedTourScreen = ({ onOpenMemory }: GuidedTourScreenProps) => {
  // Get user location from context
  const contextLocation = useUserLocation();
  const city = contextLocation.userLocation?.city || "this city";

  const [isPaused, setIsPaused] = useState(false);
  const [depth, setDepth] = useState<NarrationDepth>("30s");
  const [ttsPlaying, setTtsPlaying] = useState(false);
  const [progress, setProgress] = useState(25);
  const [showActions, setShowActions] = useState(false);
  const [stops, setStops] = useState<TourStop[]>(defaultStops);
  const [narrationText] = useState<Record<NarrationDepth, string>>(defaultNarrationText);
  const uttRef = useRef<SpeechSynthesisUtterance | null>(null);

  const activeStopIndex = stops.findIndex(s => s.active);
  const activeStop = stops[activeStopIndex] || stops[1];

  const speakNarration = () => {
    if (!("speechSynthesis" in window)) return;
    if (ttsPlaying) {
      window.speechSynthesis.cancel();
      setTtsPlaying(false);
      return;
    }
    window.speechSynthesis.cancel();
    const utt = new SpeechSynthesisUtterance(narrationText[depth]);
    utt.lang = "en-US";
    utt.rate = 0.95;
    utt.onend = () => setTtsPlaying(false);
    utt.onerror = () => setTtsPlaying(false);
    uttRef.current = utt;
    window.speechSynthesis.speak(utt);
    setTtsPlaying(true);
  };

  // Stop TTS when depth changes or component unmounts
  useEffect(() => {
    window.speechSynthesis?.cancel();
    setTtsPlaying(false);
  }, [depth, activeStop.title]);

  const goToStop = (i: number) => {
    setStops(stops.map((s, idx) => ({
      ...s,
      active: idx === i,
      done: idx < i,
    })));
    setProgress(Math.round((i / (stops.length - 1)) * 100));
  };

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

        {/* Stop progress — tap to jump to stop */}
        <div className="flex items-center gap-1.5 mt-3">
          {stops.map((stop, i) => (
            <div key={i} className="flex items-center gap-1.5">
              <button
                onClick={() => goToStop(i)}
                className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold transition-all ${
                  stop.done ? "bg-accent text-accent-foreground" : stop.active ? "bg-primary text-primary-foreground ring-2 ring-primary/40" : "bg-muted text-muted-foreground"
                }`}
              >
                {stop.done ? "✓" : i + 1}
              </button>
              {i < stops.length - 1 && (
                <div className={`flex-1 h-0.5 rounded-full ${stop.done ? "bg-accent" : "bg-muted"}`} style={{ width: 24 }} />
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
            {activeStop.image ? (
              <img src={activeStop.image} alt={activeStop.title} className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full bg-secondary/30 flex items-center justify-center">
                <ImageIcon size={40} className="text-muted-foreground/30" />
              </div>
            )}
            <div className="absolute inset-0 bg-gradient-to-t from-background/90 to-transparent" />
            <div className="absolute bottom-3 left-3 right-3">
              <div className="flex items-center gap-2">
                <MapPin size={14} className="text-accent" />
                <span className="text-xs text-muted-foreground">
                  Stop {activeStopIndex + 1} of {stops.length}
                </span>
              </div>
              <h2 className="font-display font-bold text-lg text-foreground">{activeStop.title}</h2>
              <p className="text-xs text-muted-foreground">{activeStop.description || "Point of Interest"}</p>
            </div>
          </div>

          {/* Narration depth selector */}
          <div className="p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Volume2 size={14} className={ttsPlaying ? "text-primary animate-pulse" : "text-muted-foreground"} />
                <span className="text-xs font-semibold text-foreground">Narration depth</span>
              </div>
              {/* TTS speak button */}
              <motion.button
                onClick={speakNarration}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${
                  ttsPlaying
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary text-secondary-foreground"
                }`}
                whileTap={{ scale: 0.95 }}
              >
                {ttsPlaying ? <VolumeX size={12} /> : <Volume2 size={12} />}
                {ttsPlaying ? "Stop" : "Listen"}
              </motion.button>
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
