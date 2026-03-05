import { motion, AnimatePresence } from "framer-motion";
import { useState, useEffect } from "react";
import {
  Coffee, Palette, ShoppingBag, MapPin, Clock, Footprints,
  Sparkles, ArrowRight, Shuffle, ChevronDown, Navigation
} from "lucide-react";
import parisCafe from "@/assets/paris-cafe.jpg";
import parisGallery from "@/assets/paris-gallery.jpg";
import parisMarket from "@/assets/paris-market.jpg";

interface RouteScreenProps {
  onStartTour: () => void;
  onSwapStop: (index: number) => void;
}

type RouteOption = "hidden" | "popular";

const activityLog = [
  { text: "Finding hidden cafés nearby…", delay: 300 },
  { text: "Checking crowd levels…", delay: 900 },
  { text: "Calculating walking route…", delay: 1500 },
  { text: "Summarising landmark stories…", delay: 2100 },
  { text: "Route ready ✓", delay: 2800 },
];

const stops = [
  {
    icon: Coffee,
    title: "Café Lomi",
    subtitle: "Hidden specialty coffee in the 18th",
    time: "10 min",
    image: parisCafe,
    vibe: "Quiet · 3 people inside",
    vibeColor: "text-accent",
  },
  {
    icon: Palette,
    title: "Rue Dénoyez",
    subtitle: "Ever-changing street art gallery",
    time: "18 min",
    image: parisGallery,
    vibe: "Calm · Great light right now",
    vibeColor: "text-primary",
  },
  {
    icon: ShoppingBag,
    title: "Marché des Enfants Rouges",
    subtitle: "Paris' oldest covered market",
    time: "12 min",
    image: parisMarket,
    vibe: "Moderate · Pre-lunch sweet spot",
    vibeColor: "text-accent",
  },
];

// SVG map with route path
const RouteMap = () => {
  const stopPositions = [
    { x: 30, y: 35 },
    { x: 55, y: 28 },
    { x: 72, y: 50 },
  ];
  const routePath = `M ${stopPositions[0].x},${stopPositions[0].y} Q 42,25 ${stopPositions[1].x},${stopPositions[1].y} Q 65,35 ${stopPositions[2].x},${stopPositions[2].y}`;

  return (
    <div className="w-full aspect-[16/9] rounded-2xl overflow-hidden glass relative">
      <div className="absolute inset-0 bg-gradient-to-b from-primary/5 to-transparent" />
      <svg viewBox="0 0 100 65" className="w-full h-full" preserveAspectRatio="xMidYMid slice">
        {/* Grid roads */}
        {["M 10,20 L 90,20", "M 10,40 L 90,40", "M 25,5 L 25,60", "M 50,5 L 50,60", "M 75,5 L 75,60"].map((d, i) => (
          <path key={i} d={d} stroke="hsl(var(--muted-foreground) / 0.08)" strokeWidth="0.3" fill="none" />
        ))}
        {/* Seine */}
        <motion.path
          d="M 5,45 Q 30,50 50,42 Q 70,35 95,40"
          stroke="hsl(var(--sonic-violet) / 0.3)"
          strokeWidth="1.5"
          fill="none"
          strokeLinecap="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.5 }}
        />
        {/* Walking route */}
        <motion.path
          d={routePath}
          stroke="hsl(var(--neon-mint))"
          strokeWidth="1"
          fill="none"
          strokeLinecap="round"
          strokeDasharray="2 2"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 2, delay: 0.5 }}
        />
        {/* User dot */}
        <motion.circle cx={stopPositions[0].x - 5} cy={stopPositions[0].y + 3} r="1.5" fill="hsl(var(--foreground))" animate={{ scale: [1, 1.3, 1] }} transition={{ duration: 2, repeat: Infinity }} />
        {/* Stop markers */}
        {stopPositions.map((pos, i) => (
          <g key={i}>
            <circle cx={pos.x} cy={pos.y} r="3.5" fill="hsl(var(--sonic-violet) / 0.2)" />
            <circle cx={pos.x} cy={pos.y} r="2" fill="hsl(var(--sonic-violet))" />
            <text x={pos.x} y={pos.y + 1} textAnchor="middle" fill="hsl(var(--primary-foreground))" fontSize="2.2" fontWeight="700" fontFamily="Inter">
              {i + 1}
            </text>
          </g>
        ))}
      </svg>
      {/* ETA badge */}
      <div className="absolute top-3 right-3 glass rounded-xl px-3 py-1.5 flex items-center gap-1.5">
        <Clock size={12} className="text-muted-foreground" />
        <span className="text-xs font-semibold text-foreground">~85 min</span>
      </div>
      <div className="absolute top-3 left-3 glass rounded-xl px-3 py-1.5 flex items-center gap-1.5">
        <Footprints size={12} className="text-muted-foreground" />
        <span className="text-xs font-semibold text-foreground">2.4 km</span>
      </div>
    </div>
  );
};

const RouteScreen = ({ onStartTour, onSwapStop }: RouteScreenProps) => {
  const [logIndex, setLogIndex] = useState(0);
  const [routeReady, setRouteReady] = useState(false);
  const [selectedOption, setSelectedOption] = useState<RouteOption>("hidden");

  useEffect(() => {
    const timers = activityLog.map((item, i) =>
      setTimeout(() => {
        setLogIndex(i + 1);
        if (i === activityLog.length - 1) setRouteReady(true);
      }, item.delay)
    );
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <div className="min-h-screen bg-background flex flex-col relative">
      {/* Header */}
      <motion.div className="pt-14 pb-3 px-5 relative z-10" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <h2 className="font-display font-bold text-xl text-foreground">Your route</h2>
        <p className="text-sm text-muted-foreground mt-0.5">Crafted for your vibe · Paris</p>
      </motion.div>

      <div className="flex-1 px-5 pb-32 overflow-y-auto">
        {/* Activity log */}
        <div className="mb-4">
          {activityLog.slice(0, logIndex).map((item, i) => (
            <motion.div
              key={i}
              className="flex items-center gap-2 py-1"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2 }}
            >
              <Sparkles size={10} className={i === logIndex - 1 && !routeReady ? "text-primary animate-pulse" : "text-accent"} />
              <span className={`text-xs font-medium ${i === logIndex - 1 && !routeReady ? "text-foreground" : "text-muted-foreground"}`}>
                {item.text}
              </span>
            </motion.div>
          ))}
        </div>

        {/* Route option selector */}
        <AnimatePresence>
          {routeReady && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
              <div className="flex gap-2 mb-4">
                {[
                  { key: "hidden" as RouteOption, label: "Hidden gems", emoji: "✨" },
                  { key: "popular" as RouteOption, label: "Must-sees", emoji: "🏛️" },
                ].map((opt) => (
                  <button
                    key={opt.key}
                    onClick={() => setSelectedOption(opt.key)}
                    className={`flex-1 py-2.5 rounded-xl text-xs font-bold transition-all ${
                      selectedOption === opt.key
                        ? "glass-violet glow-violet text-foreground"
                        : "glass text-muted-foreground"
                    }`}
                  >
                    {opt.emoji} {opt.label}
                  </button>
                ))}
              </div>

              {/* Map */}
              <RouteMap />

              {/* Stops */}
              <div className="mt-5 flex flex-col gap-3">
                {stops.map((stop, i) => (
                  <motion.div
                    key={i}
                    className="glass rounded-2xl p-3 flex gap-3"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.12 }}
                  >
                    <div className="w-16 h-16 rounded-xl overflow-hidden flex-shrink-0">
                      <img src={stop.image} alt={stop.title} className="w-full h-full object-cover" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="w-5 h-5 rounded-full bg-primary text-primary-foreground text-[10px] font-bold flex items-center justify-center flex-shrink-0">
                          {i + 1}
                        </span>
                        <h4 className="font-display font-bold text-sm text-foreground truncate">{stop.title}</h4>
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">{stop.subtitle}</p>
                      <div className="flex items-center gap-3 mt-1.5">
                        <span className={`text-[10px] font-semibold ${stop.vibeColor}`}>{stop.vibe}</span>
                        <span className="text-[10px] text-muted-foreground flex items-center gap-0.5">
                          <Footprints size={10} /> {stop.time}
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={() => onSwapStop(i)}
                      className="self-center w-8 h-8 rounded-full bg-secondary flex items-center justify-center flex-shrink-0"
                    >
                      <Shuffle size={12} className="text-secondary-foreground" />
                    </button>
                  </motion.div>
                ))}
              </div>

              {/* Quick adjustments */}
              <div className="mt-4 flex flex-wrap gap-2">
                {["Less crowded", "Add coffee", "Shorten to 45 min", "Wheelchair-friendly"].map((chip) => (
                  <button key={chip} className="px-3 py-1.5 rounded-full bg-secondary text-secondary-foreground text-xs font-medium hover:bg-muted transition-colors">
                    {chip}
                  </button>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Start tour CTA */}
      <AnimatePresence>
        {routeReady && (
          <motion.div
            className="fixed bottom-0 left-0 right-0 px-5 pb-8 pt-4 z-30"
            style={{ background: "linear-gradient(to top, hsl(var(--void-black)) 70%, transparent)" }}
            initial={{ y: 60 }}
            animate={{ y: 0 }}
          >
            <motion.button
              onClick={onStartTour}
              className="w-full py-4 rounded-2xl bg-gradient-to-r from-primary to-accent text-accent-foreground font-display font-bold text-base flex items-center justify-center gap-2"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
            >
              <Navigation size={18} />
              Start guided tour
            </motion.button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default RouteScreen;
