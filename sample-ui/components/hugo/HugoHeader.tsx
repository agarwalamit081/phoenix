import { motion } from "framer-motion";
import { User, Wifi } from "lucide-react";

type AppState = "idle" | "listening" | "thinking" | "confirmed";

interface HugoHeaderProps {
  appState: AppState;
}

const statusLabels: Record<AppState, string> = {
  idle: "Online",
  listening: "Listening",
  thinking: "Thinking",
  confirmed: "Online",
};

const statusColors: Record<AppState, string> = {
  idle: "bg-accent",
  listening: "bg-primary",
  thinking: "bg-primary",
  confirmed: "bg-accent",
};

const HugoHeader = ({ appState }: HugoHeaderProps) => {
  const now = new Date();
  const parisTime = now.toLocaleTimeString("en-US", {
    timeZone: "Europe/Paris",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  const parisDate = now.toLocaleDateString("en-US", {
    timeZone: "Europe/Paris",
    weekday: "short",
    month: "short",
    day: "numeric",
  });

  return (
    <motion.header
      className="fixed top-0 left-0 right-0 z-50 glass-strong px-5 py-3"
      initial={{ y: -40, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      <div className="flex items-center justify-between max-w-2xl mx-auto">
        {/* Logo */}
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center glow-violet">
            <span className="text-gradient font-bold text-sm tracking-tight">H</span>
          </div>
          <span className="font-display font-bold text-foreground tracking-tight text-lg">
            Hugo
          </span>
        </div>

        {/* Paris Time */}
        <div className="flex flex-col items-center">
          <span className="text-xs text-muted-foreground font-medium tracking-wider uppercase">
            Paris
          </span>
          <span className="text-sm font-semibold text-foreground tabular-nums">
            {parisTime}
          </span>
          <span className="text-[10px] text-muted-foreground">{parisDate}</span>
        </div>

        {/* Profile + Status */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-secondary">
            <div className={`w-1.5 h-1.5 rounded-full ${statusColors[appState]} ${appState === "listening" || appState === "thinking" ? "animate-pulse" : ""}`} />
            <span className="text-[10px] font-medium text-secondary-foreground tracking-wide uppercase">
              {statusLabels[appState]}
            </span>
          </div>
          <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center">
            <User size={14} className="text-secondary-foreground" />
          </div>
        </div>
      </div>
    </motion.header>
  );
};

export default HugoHeader;
