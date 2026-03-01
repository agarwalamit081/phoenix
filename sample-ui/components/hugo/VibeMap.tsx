import { motion } from "framer-motion";
import { useEffect, useState } from "react";

type AppState = "idle" | "listening" | "thinking" | "confirmed";

interface VibeMapProps {
  appState: AppState;
}

// Stylized Paris landmarks as schematic points
const landmarks = [
  { name: "Eiffel Tower", x: 32, y: 52, size: "lg", vibe: "hot" },
  { name: "Louvre", x: 48, y: 45, size: "md", vibe: "warm" },
  { name: "Sacré-Cœur", x: 55, y: 25, size: "md", vibe: "hot" },
  { name: "Le Marais", x: 58, y: 48, size: "sm", vibe: "warm" },
  { name: "Café de Flore", x: 42, y: 55, size: "sm", vibe: "hot" },
  { name: "Notre-Dame", x: 50, y: 52, size: "md", vibe: "warm" },
  { name: "Montmartre", x: 52, y: 22, size: "sm", vibe: "cool" },
  { name: "Buttes-Chaumont", x: 68, y: 28, size: "sm", vibe: "cool" },
];

// Seine river path
const seinePath = "M 15,48 Q 30,55 42,52 Q 52,48 60,50 Q 70,53 85,48";

// Road grid lines
const roads = [
  "M 20,20 Q 40,35 55,25",
  "M 30,65 Q 45,50 65,55",
  "M 25,35 L 75,35",
  "M 50,15 L 50,70",
  "M 35,20 Q 45,45 35,65",
  "M 65,20 Q 60,40 70,60",
];

const VibeMap = ({ appState }: VibeMapProps) => {
  const dimmed = appState === "listening" || appState === "thinking";

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

        {/* Seine River */}
        <motion.path
          d={seinePath}
          stroke="hsl(var(--sonic-violet) / 0.4)"
          strokeWidth="1.2"
          fill="none"
          strokeLinecap="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 2, delay: 0.3 }}
        />
        <motion.path
          d={seinePath}
          stroke="hsl(var(--sonic-violet) / 0.15)"
          strokeWidth="3"
          fill="none"
          strokeLinecap="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 2, delay: 0.3 }}
        />

        {/* Landmarks */}
        {landmarks.map((lm, i) => {
          const r = lm.size === "lg" ? 2.5 : lm.size === "md" ? 1.8 : 1.2;
          const color = lm.vibe === "hot"
            ? "hsl(var(--neon-mint))"
            : lm.vibe === "warm"
            ? "hsl(var(--sonic-violet))"
            : "hsl(var(--muted-foreground))";

          return (
            <g key={i}>
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
          cx={45}
          cy={50}
          r={1}
          fill="hsl(var(--foreground))"
          initial={{ scale: 0 }}
          animate={{ scale: [1, 1.3, 1] }}
          transition={{ duration: 2, repeat: Infinity }}
        />
        <motion.circle
          cx={45}
          cy={50}
          r={4}
          fill="none"
          stroke="hsl(var(--foreground) / 0.2)"
          strokeWidth="0.4"
          className="pulse-ring-slow"
          style={{ transformOrigin: "45px 50px" }}
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
