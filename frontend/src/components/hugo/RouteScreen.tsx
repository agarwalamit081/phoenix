import { motion, AnimatePresence } from "framer-motion";
import { useState, useEffect } from "react";
import {
  Coffee, Palette, ShoppingBag, MapPin, Camera, Clock, Footprints,
  Sparkles, ArrowRight, Shuffle, ChevronDown, Navigation, Image as ImageIcon
} from "lucide-react";
import { latLngToSvg, createRoutePath, DEFAULT_BOUNDS, type LatLngBounds } from "@/lib/coordinate-utils";
import { useUserLocation } from "@/contexts/UserLocationContext";
import {
  RouteResponse, RouteStop as APIRouteStop, StopDisplayData,
  categoryToIcon, generateSubtitle, ROUTE_API_BASE
} from "@/types/route";

interface RouteScreenProps {
  onStartTour: () => void;
  onSwapStop: (index: number) => void;
  route?: RouteResponse; // Route data from backend API
  autoGenerate?: boolean; // Auto-generate route from preferences
}

type RouteOption = "hidden" | "popular";

const activityLog = [
  { text: "Finding hidden gems nearby…", delay: 300 },
  { text: "Checking crowd levels…", delay: 900 },
  { text: "Calculating walking route…", delay: 1500 },
  { text: "Summarising landmark stories…", delay: 2100 },
  { text: "Route ready ✓", delay: 2800 },
];

// Icon mapping
const iconMap = {
  Coffee,
  Palette,
  ShoppingBag,
  MapPin,
  Camera,
};

// Default stops - fake monument data for display when API is unavailable
const defaultStops: StopDisplayData[] = [
  {
    sequence_order: 1,
    title: "Eiffel Tower",
    subtitle: "Iconic iron lattice tower on the Champ de Mars",
    time: "5 min",
    image: "https://images.unsplash.com/photo-1511739001486-6bfe10ce785f?w=400&q=80",
    vibe: "4.8★ · Popular",
    vibeColor: "text-accent",
    x: 20, y: 25,
    latitude: 48.8584, longitude: 2.2945,
    icon: "Camera",
  },
  {
    sequence_order: 2,
    title: "Louvre Museum",
    subtitle: "World's largest art museum & historic monument",
    time: "12 min",
    image: "https://images.unsplash.com/photo-1499856871958-5b9627545d1a?w=400&q=80",
    vibe: "4.7★ · Popular",
    vibeColor: "text-accent",
    x: 45, y: 20,
    latitude: 48.8606, longitude: 2.3376,
    icon: "Palette",
  },
  {
    sequence_order: 3,
    title: "Notre-Dame Cathedral",
    subtitle: "Medieval Catholic cathedral on the Île de la Cité",
    time: "8 min",
    image: "https://images.unsplash.com/photo-1522093007474-d86e9bf7ba6f?w=400&q=80",
    vibe: "4.9★ · Must-see",
    vibeColor: "text-accent",
    x: 55, y: 40,
    latitude: 48.8530, longitude: 2.3499,
    icon: "MapPin",
  },
  {
    sequence_order: 4,
    title: "Sacré-Cœur Basilica",
    subtitle: "Roman Catholic church atop the Montmartre hill",
    time: "15 min",
    image: "https://images.unsplash.com/photo-1550340499-a6c60fc8287c?w=400&q=80",
    vibe: "4.6★ · Hidden gem",
    vibeColor: "text-primary",
    x: 35, y: 10,
    latitude: 48.8867, longitude: 2.3431,
    icon: "Camera",
  },
];

/**
 * Convert API route stops to display data.
 * Uses dynamic bounds from UserLocationContext.
 */
function routeStopsToDisplay(stops: APIRouteStop[], bounds: LatLngBounds): StopDisplayData[] {
  return stops.map((stop, index) => {
    const svg = latLngToSvg(stop.poi.latitude, stop.poi.longitude, bounds);
    const icon = categoryToIcon(stop.poi.categories);

    return {
      sequence_order: stop.sequence_order,
      title: stop.poi.name,
      subtitle: generateSubtitle(stop.poi),
      time: stop.travel_time_minutes ? `${stop.travel_time_minutes} min` : "Unknown",
      vibe: stop.poi.rating ? `${stop.poi.rating}★ · Popular` : "New discovery",
      vibeColor: stop.poi.rating && stop.poi.rating >= 4.5 ? "text-accent" : "text-primary",
      x: svg.x,
      y: svg.y,
      latitude: stop.poi.latitude,
      longitude: stop.poi.longitude,
      icon: icon,
      estimated_duration_minutes: stop.estimated_duration_minutes ?? undefined,
    };
  });
}

// SVG map with route path
interface RouteMapProps {
  stops: StopDisplayData[];
  totalDistanceKm?: number | null;
  totalDurationMinutes?: number | null;
  bounds: LatLngBounds;
}

const RouteMap = ({ stops, totalDistanceKm, totalDurationMinutes }: RouteMapProps) => {
  return (
    <div className="w-full aspect-[16/9] rounded-2xl overflow-hidden glass relative">
      <img
        src="https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=800&q=80"
        alt="Paris map"
        className="w-full h-full object-cover opacity-80"
      />
      <div className="absolute inset-0 bg-gradient-to-t from-background/60 to-transparent" />
      {/* ETA badge */}
      <div className="absolute top-3 right-3 glass rounded-xl px-3 py-1.5 flex items-center gap-1.5">
        <Clock size={12} className="text-muted-foreground" />
        <span className="text-xs font-semibold text-foreground">
          {totalDurationMinutes ? `~${totalDurationMinutes} min` : "~40 min"}
        </span>
      </div>
      <div className="absolute top-3 left-3 glass rounded-xl px-3 py-1.5 flex items-center gap-1.5">
        <Footprints size={12} className="text-muted-foreground" />
        <span className="text-xs font-semibold text-foreground">
          {totalDistanceKm ? `${totalDistanceKm.toFixed(1)} km` : "3.2 km"}
        </span>
      </div>
    </div>
  );
};

// Expandable stop list with detail view
const StopList = ({ stops, onSwapStop }: { stops: StopDisplayData[]; onSwapStop: (i: number) => void }) => {
  const [expanded, setExpanded] = useState<number | null>(null);

  return (
    <div className="mt-5 flex flex-col gap-3">
      {stops.map((stop, i) => (
        <motion.div
          key={i}
          className="glass rounded-2xl overflow-hidden"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.08 }}
        >
          {/* Collapsed row */}
          <button
            className="w-full p-3 flex gap-3 text-left"
            onClick={() => setExpanded(expanded === i ? null : i)}
          >
            <div className="w-20 h-20 rounded-xl overflow-hidden flex-shrink-0 bg-secondary/50">
              {stop.image ? (
                <img src={stop.image} alt={stop.title} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-muted-foreground">
                  <ImageIcon size={20} />
                </div>
              )}
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
            <div className="flex flex-col items-center gap-2 self-center">
              <motion.div animate={{ rotate: expanded === i ? 180 : 0 }} transition={{ duration: 0.2 }}>
                <ChevronDown size={14} className="text-muted-foreground" />
              </motion.div>
            </div>
          </button>

          {/* Expanded detail */}
          <AnimatePresence>
            {expanded === i && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.25 }}
                className="overflow-hidden"
              >
                <div className="px-3 pb-3 flex gap-2 border-t border-border/30 pt-3">
                  <button className="flex-1 py-2 rounded-xl bg-primary/10 text-primary text-xs font-semibold flex items-center justify-center gap-1.5">
                    <Navigation size={12} /> Navigate
                  </button>
                  <button className="flex-1 py-2 rounded-xl bg-secondary text-secondary-foreground text-xs font-semibold flex items-center justify-center gap-1.5">
                    <ArrowRight size={12} /> Skip
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); onSwapStop(i); }}
                    className="flex-1 py-2 rounded-xl bg-secondary text-secondary-foreground text-xs font-semibold flex items-center justify-center gap-1.5"
                  >
                    <Shuffle size={12} /> Swap
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      ))}
    </div>
  );
};

const RouteScreen = ({
  onStartTour,
  onSwapStop,
  route: externalRoute,
  autoGenerate = false,
}: RouteScreenProps) => {
  // Get user location from context
  const contextLocation = useUserLocation();
  const bounds = contextLocation.userLocation?.bounds || DEFAULT_BOUNDS;
  const city = contextLocation.userLocation?.city || "Unknown";
  const country = contextLocation.userLocation?.country || "";

  const [logIndex, setLogIndex] = useState(activityLog.length);
  const [routeReady, setRouteReady] = useState(true);
  const [selectedOption, setSelectedOption] = useState<RouteOption>("hidden");
  const [stops, setStops] = useState<StopDisplayData[]>(defaultStops);
  const [totalDistanceKm, setTotalDistanceKm] = useState<number | null>(null);
  const [totalDurationMinutes, setTotalDurationMinutes] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Update stops when external route changes
  useEffect(() => {
    if (externalRoute && externalRoute.stops.length > 0) {
      const displayStops = routeStopsToDisplay(externalRoute.stops, bounds);
      setStops(displayStops);
      setTotalDistanceKm(externalRoute.total_distance_km);
      setTotalDurationMinutes(externalRoute.total_duration_minutes);
      setRouteReady(true);
    }
  }, [externalRoute, bounds]);

  // Auto-generate route if enabled
  useEffect(() => {
    if (!autoGenerate || routeReady) return;

    const generateRoute = async () => {
      setIsLoading(true);
      try {
        const lat = contextLocation.userLocation?.latitude;
        const lng = contextLocation.userLocation?.longitude;

        if (!lat || !lng) {
          console.warn("No user location available for route generation");
          setRouteReady(true);
          return;
        }

        const response = await fetch(`${ROUTE_API_BASE}/generate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            start_location: {
              latitude: lat,
              longitude: lng,
              city: city,
              country: country,
            },
            transport_mode: "walking",
            optimize_for: selectedOption === "hidden" ? "satisfaction" : "time",
            max_duration_minutes: 180,
          }),
        });

        if (response.ok) {
          const route: RouteResponse = await response.json();
          const displayStops = routeStopsToDisplay(route.stops, bounds);
          setStops(displayStops);
          setTotalDistanceKm(route.total_distance_km);
          setTotalDurationMinutes(route.total_duration_minutes);
          setRouteReady(true);
        }
      } catch (error) {
        console.error("Failed to generate route:", error);
        // Keep default stops on error
        setRouteReady(true);
      } finally {
        setIsLoading(false);
      }
    };

    generateRoute();
  }, [autoGenerate, contextLocation.userLocation, selectedOption, city, country, bounds]);

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
        <p className="text-sm text-muted-foreground mt-0.5">
          Crafted for your vibe · {city}
        </p>
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
              <RouteMap
                stops={stops}
                totalDistanceKm={totalDistanceKm}
                totalDurationMinutes={totalDurationMinutes}
                bounds={bounds}
              />

              {/* Stops */}
              <StopList stops={stops} onSwapStop={onSwapStop} />

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
