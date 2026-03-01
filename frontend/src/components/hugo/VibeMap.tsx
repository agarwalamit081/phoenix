import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { latLngToSvg, getVibeColor, DEFAULT_BOUNDS, type LatLngBounds } from "@/lib/coordinate-utils";
import { useUserLocation } from "@/contexts/UserLocationContext";
import { POI, POIDisplayData, UserLocation, categoryToVibe, ratingToSize, POI_API_BASE } from "@/types/poi";

type AppState = "idle" | "listening" | "thinking" | "confirmed";

interface VibeMapProps {
  appState: AppState;
  pois?: POI[]; // POIs from backend API
  userLocation?: UserLocation; // User's GPS location
  autoFetch?: boolean; // Auto-fetch POIs from API
  fetchRadius?: number; // Search radius in km (default: 5)
}

/**
 * Convert POIs to display data with SVG coordinates.
 * Uses dynamic bounds from UserLocationContext.
 */
function poisToDisplayData(pois: POI[], bounds: LatLngBounds): POIDisplayData[] {
  return pois.map((poi) => {
    const svg = latLngToSvg(poi.latitude, poi.longitude, bounds);
    return {
      id: poi.id,
      name: poi.name,
      x: svg.x,
      y: svg.y,
      size: ratingToSize(poi.rating),
      vibe: categoryToVibe(poi.categories),
      categories: poi.categories,
      rating: poi.rating ?? undefined,
    };
  });
}

// Default road grid lines (stylized)
const roads = [
  "M 20,20 Q 40,35 55,25",
  "M 30,65 Q 45,50 65,55",
  "M 25,35 L 75,35",
  "M 50,15 L 50,70",
  "M 35,20 Q 45,45 35,65",
  "M 65,20 Q 60,40 70,60",
];

const VibeMap = ({
  appState,
  pois: externalPois,
  userLocation,
  autoFetch = false,
  fetchRadius = 5,
}: VibeMapProps) => {
  // Get user location from context
  const contextLocation = useUserLocation();
  const bounds = contextLocation.userLocation?.bounds || DEFAULT_BOUNDS;
  const city = contextLocation.userLocation?.city || "Unknown";

  const [landmarks, setLandmarks] = useState<POIDisplayData[]>([]);
  const [userSvgLocation, setUserSvgLocation] = useState<{ x: number; y: number }>({ x: 50, y: 40 });
  const [isLoading, setIsLoading] = useState(false);

  const dimmed = appState === "listening" || appState === "thinking";

  // Fetch POIs from API if autoFetch is enabled
  useEffect(() => {
    if (!autoFetch) return;

    const fetchPOIs = async () => {
      setIsLoading(true);
      try {
        const lat = contextLocation.userLocation?.latitude;
        const lng = contextLocation.userLocation?.longitude;

        if (!lat || !lng) {
          console.warn("No user location available for POI fetch");
          return;
        }

        const params = new URLSearchParams({
          latitude: lat.toString(),
          longitude: lng.toString(),
          radius: fetchRadius.toString(),
          limit: "20",
        });

        const response = await fetch(`${POI_API_BASE}/nearby?${params}`);
        if (response.ok) {
          const data: POI[] = await response.json();
          const displayData = poisToDisplayData(data, bounds);
          setLandmarks(displayData);
        }
      } catch (error) {
        console.error("Failed to fetch POIs:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchPOIs();
  }, [autoFetch, contextLocation.userLocation, fetchRadius, bounds]);

  // Update landmarks when external POIs change
  useEffect(() => {
    if (externalPois && externalPois.length > 0) {
      setLandmarks(poisToDisplayData(externalPois, bounds));
    }
  }, [externalPois, bounds]);

  // Update user location when prop changes
  useEffect(() => {
    if (userLocation) {
      const svg = latLngToSvg(userLocation.latitude, userLocation.longitude, bounds);
      setUserSvgLocation(svg);
    }
  }, [userLocation, bounds]);

  // Update center location based on context
  useEffect(() => {
    if (contextLocation.userLocation) {
      const svg = latLngToSvg(
        contextLocation.userLocation.latitude,
        contextLocation.userLocation.longitude,
        bounds
      );
      setUserSvgLocation(svg);
    }
  }, [contextLocation.userLocation, bounds]);

  return (
    <motion.div
      className="relative w-full aspect-[4/3] max-h-[320px] rounded-2xl overflow-hidden glass"
      animate={{ opacity: dimmed ? 0.4 : 1, filter: dimmed ? "blur(4px)" : "blur(0px)" }}
      transition={{ duration: 0.5 }}
    >
      {/* Background glow */}
      <div className="absolute inset-0 bg-gradient-to-b from-primary/5 to-transparent" />

      <svg viewBox="0 0 100 80" className="w-full h-full" preserveAspectRatio="xMidYMid slice">
        {/* Road grid */}
        {roads.map((d, i) => (
          <motion.path
            key={i}
            d={d}
            stroke="hsl(var(--muted-foreground) / 0.12)"
            strokeWidth="0.3"
            fill="none"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 1.5, delay: i * 0.1 }}
          />
        ))}

        {/* City River (if applicable) - would be dynamic based on city features */}
        {/* Note: River display could be enabled per-city via configuration */}

        {/* Landmarks */}
        {landmarks.map((lm, i) => {
          const r = lm.size === "lg" ? 2.5 : lm.size === "md" ? 1.8 : 1.2;
          const color = getVibeColor(lm.categories[0] || lm.vibe);

          return (
            <g key={lm.id || i}>
              {/* Pulse ring */}
              <motion.circle
                cx={lm.x}
                cy={lm.y}
                r={r * 2.5}
                fill="none"
                stroke={color}
                strokeWidth="0.3"
                className="pulse-ring"
                style={{ transformOrigin: `${lm.x}px ${lm.y}px` }}
                initial={{ opacity: 0 }}
                animate={{ opacity: 0.5 }}
                transition={{ delay: 1 + i * 0.15 }}
              />
              {/* Glow */}
              <motion.circle
                cx={lm.x}
                cy={lm.y}
                r={r * 1.5}
                fill={color}
                opacity={0.15}
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.8 + i * 0.1, type: "spring" }}
              />
              {/* Core dot */}
              <motion.circle
                cx={lm.x}
                cy={lm.y}
                r={r}
                fill={color}
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.8 + i * 0.1, type: "spring" }}
              />
              {/* Label */}
              <motion.text
                x={lm.x}
                y={lm.y - r - 2}
                textAnchor="middle"
                fill="hsl(var(--foreground) / 0.7)"
                fontSize="2"
                fontWeight="500"
                fontFamily="Inter, sans-serif"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 1.2 + i * 0.1 }}
              >
                {lm.name}
              </motion.text>
            </g>
          );
        })}

        {/* User location */}
        <motion.circle
          cx={userSvgLocation.x}
          cy={userSvgLocation.y}
          r={1}
          fill="hsl(var(--foreground))"
          initial={{ scale: 0 }}
          animate={{ scale: [1, 1.3, 1] }}
          transition={{ duration: 2, repeat: Infinity }}
        />
        <motion.circle
          cx={userSvgLocation.x}
          cy={userSvgLocation.y}
          r={4}
          fill="none"
          stroke="hsl(var(--foreground) / 0.2)"
          strokeWidth="0.4"
          className="pulse-ring-slow"
          style={{ transformOrigin: `${userSvgLocation.x}px ${userSvgLocation.y}px` }}
        />
      </svg>

      {/* Legend */}
      <div className="absolute bottom-3 left-3 flex gap-3">
        {[
          { color: "bg-accent", label: "🔥 Hot" },
          { color: "bg-primary", label: "Warm" },
        ].map((l, i) => (
          <div key={i} className="flex items-center gap-1">
            <div className={`w-2 h-2 rounded-full ${l.color}`} />
            <span className="text-[10px] text-muted-foreground font-medium">{l.label}</span>
          </div>
        ))}
      </div>
    </motion.div>
  );
};

export default VibeMap;
