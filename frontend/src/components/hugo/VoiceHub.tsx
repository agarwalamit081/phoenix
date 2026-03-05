import { motion, AnimatePresence } from "framer-motion";
import { Keyboard, Camera } from "lucide-react";
import { useEffect, useState } from "react";

type AppState = "idle" | "listening" | "thinking" | "confirmed";

interface VoiceHubProps {
  appState: AppState;
  onTap: () => void;
}

const WaveformBars = ({ active, thinking }: { active: boolean; thinking: boolean }) => {
  const barCount = 24;

  return (
    <div className="flex items-center justify-center gap-[2px] h-12">
      {Array.from({ length: barCount }).map((_, i) => {
        const baseDelay = i * 0.06;
        const height = active
          ? `${20 + Math.sin(i * 0.8) * 28}px`
          : thinking
          ? `${8 + Math.sin(i * 0.5) * 6}px`
          : "4px";

        return (
          <motion.div
            key={i}
            className={`w-[2.5px] rounded-full ${
              active
                ? "bg-gradient-to-t from-primary to-accent"
                : thinking
                ? "bg-primary/60"
                : "bg-muted-foreground/30"
            }`}
            animate={{
              height: active
                ? [
                    `${12 + Math.random() * 36}px`,
                    `${4 + Math.random() * 24}px`,
                    `${16 + Math.random() * 32}px`,
                  ]
                : thinking
                ? [
                    `${6 + Math.sin(i * 0.4) * 8}px`,
                    `${10 + Math.cos(i * 0.3) * 6}px`,
                    `${6 + Math.sin(i * 0.4) * 8}px`,
                  ]
                : "4px",
            }}
            transition={{
              duration: active ? 0.4 : thinking ? 1.5 : 0.6,
              repeat: active || thinking ? Infinity : 0,
              repeatType: "reverse",
              delay: baseDelay,
              ease: "easeInOut",
            }}
          />
        );
      })}
    </div>
  );
};

const Tesseract = () => (
  <motion.div
    className="w-12 h-12 relative rotate-slow"
    style={{ perspective: 200 }}
  >
    {[0, 45, 90, 135].map((deg, i) => (
      <motion.div
        key={i}
        className="absolute inset-2 border border-primary/40 rounded-sm"
        style={{ transform: `rotate(${deg}deg)` }}
        animate={{ rotate: [deg, deg + 360] }}
        transition={{ duration: 8, repeat: Infinity, ease: "linear", delay: i * 0.3 }}
      />
    ))}
  </motion.div>
);

const VoiceHub = ({ appState, onTap }: VoiceHubProps) => {
  const isListening = appState === "listening";
  const isThinking = appState === "thinking";

  return (
    <motion.div
      className="fixed bottom-0 left-0 right-0 z-50 pb-6 pt-3 px-4"
      style={{
        background: "linear-gradient(to top, hsl(var(--void-black)) 60%, transparent)",
      }}
      initial={{ y: 60, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ delay: 0.4 }}
    >
      <div className="max-w-2xl mx-auto flex items-end justify-center gap-4">
        {/* Keyboard icon */}
        <motion.button
          className="w-10 h-10 rounded-full bg-secondary flex items-center justify-center mb-1"
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.95 }}
        >
          <Keyboard size={16} className="text-secondary-foreground" />
        </motion.button>

        {/* Main Waveform Button */}
        <motion.button
          onClick={onTap}
          className={`relative flex items-center justify-center rounded-[2rem] px-6 py-3 min-w-[180px] transition-all ${
            isListening
              ? "glass-violet glow-violet"
              : isThinking
              ? "glass-violet"
              : "glass"
          }`}
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          layout
        >
          {isThinking ? (
            <div className="flex items-center gap-3">
              <Tesseract />
              <span className="text-xs text-primary font-medium">Thinking...</span>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-1">
              <WaveformBars active={isListening} thinking={false} />
              <AnimatePresence mode="wait">
                {!isListening && (
                  <motion.span
                    className="text-[11px] text-muted-foreground font-medium"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                  >
                    Where to, Alex?
                  </motion.span>
                )}
              </AnimatePresence>
            </div>
          )}

          {/* Glow ring when listening */}
          {isListening && (
            <motion.div
              className="absolute inset-0 rounded-[2rem] border-2 border-primary/40"
              animate={{ scale: [1, 1.08, 1], opacity: [0.5, 0.2, 0.5] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
          )}
        </motion.button>

        {/* Camera icon */}
        <motion.button
          className="w-10 h-10 rounded-full bg-secondary flex items-center justify-center mb-1"
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.95 }}
        >
          <Camera size={16} className="text-secondary-foreground" />
        </motion.button>
      </div>
    </motion.div>
  );
};

export default VoiceHub;
