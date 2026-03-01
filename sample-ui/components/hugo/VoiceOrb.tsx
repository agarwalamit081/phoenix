import { motion, AnimatePresence } from "framer-motion";
import { Mic, Keyboard, Camera } from "lucide-react";

type VoiceState = "idle" | "listening" | "thinking" | "speaking" | "error";

interface VoiceOrbProps {
  state: VoiceState;
  onTap: () => void;
  transcript?: string;
  className?: string;
}

const VoiceOrb = ({ state, onTap, transcript, className = "" }: VoiceOrbProps) => {
  const isActive = state === "listening" || state === "speaking";

  return (
    <motion.div className={`flex items-center justify-center gap-4 ${className}`}>
      {/* Keyboard */}
      <motion.button
        className="w-10 h-10 rounded-full bg-secondary flex items-center justify-center"
        whileTap={{ scale: 0.95 }}
      >
        <Keyboard size={16} className="text-secondary-foreground" />
      </motion.button>

      {/* Main orb */}
      <motion.button
        onClick={onTap}
        className="relative w-16 h-16 rounded-full flex items-center justify-center"
        whileTap={{ scale: 0.93 }}
      >
        {/* Background rings */}
        {isActive && (
          <>
            <motion.div
              className="absolute inset-0 rounded-full border-2 border-primary/30"
              animate={{ scale: [1, 1.5, 1], opacity: [0.5, 0, 0.5] }}
              transition={{ duration: 2, repeat: Infinity }}
            />
            <motion.div
              className="absolute inset-0 rounded-full border border-primary/20"
              animate={{ scale: [1, 1.8, 1], opacity: [0.3, 0, 0.3] }}
              transition={{ duration: 2, repeat: Infinity, delay: 0.5 }}
            />
          </>
        )}

        {/* Core */}
        <motion.div
          className={`w-full h-full rounded-full flex items-center justify-center ${
            state === "listening"
              ? "bg-primary glow-violet"
              : state === "thinking"
              ? "bg-primary/50"
              : state === "speaking"
              ? "bg-accent glow-mint"
              : state === "error"
              ? "bg-destructive"
              : "glass-violet"
          }`}
          animate={
            state === "thinking"
              ? { scale: [1, 1.05, 1], rotate: [0, 180, 360] }
              : state === "listening"
              ? { scale: [1, 1.08, 1] }
              : {}
          }
          transition={
            state === "thinking"
              ? { duration: 3, repeat: Infinity, ease: "linear" }
              : { duration: 1.5, repeat: Infinity }
          }
        >
          <Mic size={24} className={
            state === "speaking" ? "text-accent-foreground" : "text-primary-foreground"
          } />
        </motion.div>
      </motion.button>

      {/* Camera */}
      <motion.button
        className="w-10 h-10 rounded-full bg-secondary flex items-center justify-center"
        whileTap={{ scale: 0.95 }}
      >
        <Camera size={16} className="text-secondary-foreground" />
      </motion.button>
    </motion.div>
  );
};

export default VoiceOrb;
