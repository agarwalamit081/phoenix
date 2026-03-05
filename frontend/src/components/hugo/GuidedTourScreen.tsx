import { motion, AnimatePresence } from "framer-motion";
import { useState, useEffect, useMemo } from "react";
import {
  Pause, Play, RotateCcw, MessageCircle, Languages, Bookmark,
  Mic, ChevronUp, Volume2, Clock, Footprints, Navigation, MapPin, Image as ImageIcon
} from "lucide-react";
import { useUserLocation } from "@/contexts/UserLocationContext";
import { StopDisplayData } from "@/types/route";

interface GuidedTourScreenProps {
  onOpenMemory: () => void;
  routeStops?: StopDisplayData[];
}

interface TourStop {
  title: string;
  done: boolean;
  active?: boolean;
  description?: string;
  image?: string;
}

type NarrationDepth = "30s" | "2min" | "deep";

function stopsForTour(routeStops: StopDisplayData[]): TourStop[] {
  if (!routeStops.length) {
    return [
      { title: "City welcome point", done: true },
      { title: "Local discovery stop", done: false, active: true, description: "We will adapt this stop once your route is generated." },
      { title: "Dinner recommendation", done: false },
    ];
  }
  return routeStops.slice(0, 4).map((stop, index) => ({
    title: stop.title,
    done: index === 0,
    active: index === 1 || (index === 0 && routeStops.length === 1),
    description: stop.subtitle,
    image: stop.image,
  }));
}

function narrationForDepth(stop: TourStop, depth: NarrationDepth, city: string): string {
  const place = stop.title;
  const desc = stop.description || "local highlight";
  if (depth === "30s") {
    return `${place} is a great quick stop in ${city}. Focus on ${desc.toLowerCase()} and keep moving to stay on schedule.`;
  }
  if (depth === "2min") {
    return `${place} is one of the stronger picks on this route. You can spend about 20 to 30 minutes here, then continue toward the next stop. It is especially good for ${desc.toLowerCase()}, and tends to fit well into an afternoon plan.`;
  }
  return `${place} is included because it balances your itinerary with a different vibe from the previous stop. In ${city}, this kind of place usually works best when you arrive slightly before peak time, walk the surrounding streets, and then continue toward your dinner segment. It helps keep the route varied without adding long detours.`;
}

const GuidedTourScreen = ({ onOpenMemory, routeStops = [] }: GuidedTourScreenProps) => {
  // Get user location from context
  const contextLocation = useUserLocation();
  const city = contextLocation.userLocation?.city || "this city";

  const [isPaused, setIsPaused] = useState(false);
  const [depth, setDepth] = useState<NarrationDepth>("30s");
  const [isSpeaking, setIsSpeaking] = useState(true);
  const [progress, setProgress] = useState(45); // percent through route
  const [showActions, setShowActions] = useState(false);
  const stops = useMemo(() => stopsForTour(routeStops), [routeStops]);

  // Get active stop
  const activeStop = stops.find(s => s.active) || stops[1];

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
                  Stop {stops.findIndex(s => s.active) + 1} of {stops.length}
                </span>
              </div>
              <h2 className="font-display font-bold text-lg text-foreground">{activeStop.title}</h2>
              <p className="text-xs text-muted-foreground">{activeStop.description || "Point of Interest"}</p>
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
                {narrationForDepth(activeStop, depth, city)}
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
            <span className="font-semibold text-foreground">Memory saved:</span> Prefers {activeStop.title.toLowerCase()} and nearby local experiences
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
