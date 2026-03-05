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
  onRouteReady?: (stops: StopDisplayData[]) => void;
  route?: RouteResponse; // Route data from backend API
  autoGenerate?: boolean; // Auto-generate route from preferences
}

type RouteOption = "hidden" | "popular";

// Icon mapping
const iconMap = {
  Coffee,
  Palette,
  ShoppingBag,
  MapPin,
  Camera,
};

// Default stops - now empty, populated from API
const defaultStops: StopDisplayData[] = [];

function buildSyntheticFallbackStops(
  lat: number,
  lng: number,
  option: RouteOption,
  city: string,
): APIRouteStop[] {
  const hiddenOffsets = [
    { lat: 0.0025, lng: 0.0018, name: `${city} riverside walk`, categories: ["sightseeing"] },
    { lat: 0.0038, lng: -0.0016, name: `${city} local craft corner`, categories: ["culture"] },
    { lat: -0.0029, lng: 0.0022, name: `${city} neighborhood bistro`, categories: ["food"] },
    { lat: -0.0016, lng: -0.0031, name: `${city} sunset viewpoint`, categories: ["landmark"] },
  ];
  const popularOffsets = [
    { lat: 0.002, lng: 0.0026, name: `${city} old town square`, categories: ["landmark"] },
    { lat: 0.0041, lng: -0.0012, name: `${city} city museum`, categories: ["museum"] },
    { lat: -0.0024, lng: 0.002, name: `${city} central avenue`, categories: ["sightseeing"] },
    { lat: -0.0012, lng: -0.0034, name: `${city} signature dinner spot`, categories: ["food"] },
  ];
  const offsets = option === "hidden" ? hiddenOffsets : popularOffsets;

  return offsets.map((offset, index) => ({
    sequence_order: index + 1,
    poi: {
      id: `fallback-${index}`,
      name: offset.name,
      categories: offset.categories,
      latitude: lat + offset.lat,
      longitude: lng + offset.lng,
      rating: option === "popular" ? 4.6 : 4.2,
      price_level: index === 2 ? 2 : 1,
      estimated_duration_minutes: 45,
    },
    estimated_arrival_time: null,
    estimated_departure_time: null,
    estimated_duration_minutes: 45,
    distance_from_previous_km: index === 0 ? 0 : 0.7,
    travel_time_minutes: index === 0 ? 0 : 9,
    transport_mode: "walking",
  }));
}

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

const RouteMap = ({ stops, totalDistanceKm, totalDurationMinutes, bounds }: RouteMapProps) => {
  const latitudes = stops.map((s) => s.latitude);
  const longitudes = stops.map((s) => s.longitude);
  const fallbackBounds = bounds;
  const minLat = latitudes.length ? Math.min(...latitudes) - 0.01 : fallbackBounds.minLat;
  const maxLat = latitudes.length ? Math.max(...latitudes) + 0.01 : fallbackBounds.maxLat;
  const minLng = longitudes.length ? Math.min(...longitudes) - 0.01 : fallbackBounds.minLng;
  const maxLng = longitudes.length ? Math.max(...longitudes) + 0.01 : fallbackBounds.maxLng;
  const mapBounds: LatLngBounds = { minLat, maxLat, minLng, maxLng };
  const mapSrc = `https://www.openstreetmap.org/export/embed.html?bbox=${mapBounds.minLng}%2C${mapBounds.minLat}%2C${mapBounds.maxLng}%2C${mapBounds.maxLat}&layer=mapnik`;
  const routePath = stops.length > 1
    ? createRoutePath(stops.map((s) => ({ lat: s.latitude, lng: s.longitude })), mapBounds)
    : "";
  const userDot = stops.length > 0
    ? latLngToSvg(stops[0].latitude, stops[0].longitude, mapBounds)
    : null;

  return (
    <div className="w-full aspect-[16/9] rounded-2xl overflow-hidden glass relative">
      <iframe
        title="Route map"
        src={mapSrc}
        className="absolute inset-0 w-full h-full border-0"
        loading="lazy"
        referrerPolicy="no-referrer"
      />
      <div className="absolute inset-0 bg-gradient-to-b from-primary/10 to-background/10" />
      <svg viewBox="0 0 100 65" className="absolute inset-0 w-full h-full pointer-events-none" preserveAspectRatio="none">
        {routePath && (
          <motion.path
            d={routePath}
            stroke="hsl(var(--neon-mint))"
            strokeWidth="1.2"
            fill="none"
            strokeLinecap="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 1.6, delay: 0.2 }}
          />
        )}
        {userDot && (
          <motion.circle
            cx={userDot.x}
            cy={userDot.y}
            r="1.6"
            fill="hsl(var(--foreground))"
            animate={{ scale: [1, 1.3, 1] }}
            transition={{ duration: 1.6, repeat: Infinity }}
          />
        )}
        {stops.map((stop, i) => {
          const marker = latLngToSvg(stop.latitude, stop.longitude, mapBounds);
          return (
            <g key={`${stop.title}-${i}`}>
              <circle cx={marker.x} cy={marker.y} r="2.7" fill="hsl(var(--sonic-violet) / 0.25)" />
              <circle cx={marker.x} cy={marker.y} r="1.8" fill="hsl(var(--sonic-violet))" />
              <text x={marker.x} y={marker.y + 0.8} textAnchor="middle" fill="hsl(var(--primary-foreground))" fontSize="2.1" fontWeight="700" fontFamily="Inter">
                {i + 1}
              </text>
            </g>
          );
        })}
      </svg>
      {/* ETA badge */}
      <div className="absolute top-3 right-3 glass rounded-xl px-3 py-1.5 flex items-center gap-1.5">
        <Clock size={12} className="text-muted-foreground" />
        <span className="text-xs font-semibold text-foreground">
          {totalDurationMinutes ? `~${totalDurationMinutes} min` : "--"}
        </span>
      </div>
      <div className="absolute top-3 left-3 glass rounded-xl px-3 py-1.5 flex items-center gap-1.5">
        <Footprints size={12} className="text-muted-foreground" />
        <span className="text-xs font-semibold text-foreground">
          {totalDistanceKm ? `${totalDistanceKm.toFixed(1)} km` : "--"}
        </span>
      </div>
    </div>
  );
};

const RouteScreen = ({
  onStartTour,
  onSwapStop,
  onRouteReady,
  route: externalRoute,
  autoGenerate = false,
}: RouteScreenProps) => {
  // Get user location from context
  const contextLocation = useUserLocation();
  const bounds = contextLocation.userLocation?.bounds || DEFAULT_BOUNDS;
  const city = contextLocation.userLocation?.city || "Unknown";
  const country = contextLocation.userLocation?.country || "";

  const [progressLogs, setProgressLogs] = useState<string[]>([]);
  const [routeReady, setRouteReady] = useState(false);
  const [selectedOption, setSelectedOption] = useState<RouteOption>("hidden");
  const [stops, setStops] = useState<StopDisplayData[]>(defaultStops);
  const [totalDistanceKm, setTotalDistanceKm] = useState<number | null>(null);
  const [totalDurationMinutes, setTotalDurationMinutes] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [generationError, setGenerationError] = useState<string | null>(null);

  // Update stops when external route changes
  useEffect(() => {
    if (externalRoute && externalRoute.stops.length > 0) {
      const displayStops = routeStopsToDisplay(externalRoute.stops, bounds);
      setStops(displayStops);
      setTotalDistanceKm(externalRoute.total_distance_km);
      setTotalDurationMinutes(externalRoute.total_duration_minutes);
      setRouteReady(true);
      onRouteReady?.(displayStops);
    }
  }, [externalRoute, bounds, onRouteReady]);

  useEffect(() => {
    if (!autoGenerate) return;
    setRouteReady(false);
  }, [selectedOption, autoGenerate]);

  // Auto-generate route if enabled
  useEffect(() => {
    if (!autoGenerate || routeReady) return;

    const generateRoute = async () => {
      setIsLoading(true);
      setGenerationError(null);
      setProgressLogs(["Preparing route request..."]);
      try {
        const lat = contextLocation.userLocation?.latitude;
        const lng = contextLocation.userLocation?.longitude;

        if (!lat || !lng) {
          console.warn("No user location available for route generation");
          setGenerationError("Location is unavailable. Please enable location access and try again.");
          setProgressLogs((prev) => [...prev, "Location unavailable"]);
          setRouteReady(false);
          return;
        }

        setProgressLogs((prev) => [...prev, "Searching nearby points of interest..."]);
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
          if (displayStops.length === 0) {
            setGenerationError("No matching places found for your request. Try broadening preferences.");
            setProgressLogs((prev) => [...prev, "No route candidates found"]);
            setRouteReady(false);
          } else {
            setStops(displayStops);
            setTotalDistanceKm(route.total_distance_km);
            setTotalDurationMinutes(route.total_duration_minutes);
            setProgressLogs((prev) => [...prev, "Route ready"]);
            setRouteReady(true);
            onRouteReady?.(displayStops);
          }
        } else {
          if (response.status === 401) {
            setProgressLogs((prev) => [...prev, "Route API requires auth, generating local fallback route..."]);
            const fallbackStops = buildSyntheticFallbackStops(lat, lng, selectedOption, city || "Nearby");
            const displayStops = routeStopsToDisplay(fallbackStops, bounds);
            setStops(displayStops);
            setTotalDistanceKm(Math.max(0, (displayStops.length - 1) * 0.7));
            setTotalDurationMinutes(displayStops.length * 45 + Math.max(0, (displayStops.length - 1) * 9));
            setGenerationError(null);
            setProgressLogs((prev) => [...prev, "Route ready (fallback mode)"]);
            setRouteReady(true);
            onRouteReady?.(displayStops);
          } else {
            const message = `Route generation failed (${response.status}).`;
            setProgressLogs((prev) => [...prev, `${message} Building local fallback route...`]);
            const fallbackStops = buildSyntheticFallbackStops(lat, lng, selectedOption, city || "Nearby");
            const displayStops = routeStopsToDisplay(fallbackStops, bounds);
            setStops(displayStops);
            setTotalDistanceKm(Math.max(0, (displayStops.length - 1) * 0.7));
            setTotalDurationMinutes(displayStops.length * 45 + Math.max(0, (displayStops.length - 1) * 9));
            setGenerationError(null);
            setProgressLogs((prev) => [...prev, "Route ready (fallback mode)"]);
            setRouteReady(true);
            onRouteReady?.(displayStops);
          }
        }
      } catch (error) {
        console.error("Failed to generate route:", error);
        setProgressLogs((prev) => [...prev, "Network error while generating route. Building local fallback route..."]);
        const lat = contextLocation.userLocation?.latitude;
        const lng = contextLocation.userLocation?.longitude;
        if (lat && lng) {
          const fallbackStops = buildSyntheticFallbackStops(lat, lng, selectedOption, city || "Nearby");
          const displayStops = routeStopsToDisplay(fallbackStops, bounds);
          setStops(displayStops);
          setTotalDistanceKm(Math.max(0, (displayStops.length - 1) * 0.7));
          setTotalDurationMinutes(displayStops.length * 45 + Math.max(0, (displayStops.length - 1) * 9));
          setGenerationError(null);
          setProgressLogs((prev) => [...prev, "Route ready (fallback mode)"]);
          setRouteReady(true);
          onRouteReady?.(displayStops);
        } else {
          setGenerationError("Unable to generate route right now. Please try again.");
          setRouteReady(false);
        }
      } finally {
        setIsLoading(false);
      }
    };

    generateRoute();
  }, [autoGenerate, routeReady, contextLocation.userLocation, selectedOption, city, country, bounds, onRouteReady]);

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
          {progressLogs.map((line, i) => (
            <motion.div
              key={i}
              className="flex items-center gap-2 py-1"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2 }}
            >
              <Sparkles size={10} className={isLoading && i === progressLogs.length - 1 ? "text-primary animate-pulse" : "text-accent"} />
              <span className={`text-xs font-medium ${isLoading && i === progressLogs.length - 1 ? "text-foreground" : "text-muted-foreground"}`}>
                {line}
              </span>
            </motion.div>
          ))}
          {generationError && (
            <p className="text-xs text-destructive mt-2">{generationError}</p>
          )}
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
              <div className="mt-5 flex flex-col gap-3">
                {stops.map((stop, i) => (
                  <motion.div
                    key={i}
                    className="glass rounded-2xl p-3 flex gap-3"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.12 }}
                  >
                    <div className="w-16 h-16 rounded-xl overflow-hidden flex-shrink-0 bg-secondary/50">
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
