import { motion, AnimatePresence } from "framer-motion";
import { X, Brain, Clock, Footprints, Coffee, Eye, Volume2, Users, Shield } from "lucide-react";

interface MemoryDrawerProps {
  open: boolean;
  onClose: () => void;
  privacyMode?: boolean;
}

const preferences = [
  { icon: Coffee, label: "Local cafés", category: "Likes" },
  { icon: Eye, label: "Street art", category: "Likes" },
  { icon: Users, label: "Low crowds", category: "Crowd" },
  { icon: Footprints, label: "Moderate pace", category: "Pace" },
  { icon: Volume2, label: "Quick narrations", category: "Style" },
];

const todayConstraints = [
  { label: "Time budget", value: "90 minutes" },
  { label: "Walking speed", value: "Moderate" },
  { label: "Start point", value: "18th Arrondissement" },
];

const recentUpdates = [
  { text: "Prefers street art & quiet neighbourhoods", time: "2 min ago" },
  { text: "Likes hidden specialty coffee", time: "8 min ago" },
  { text: "Avoids crowded tourist areas", time: "12 min ago" },
];

const MemoryDrawer = ({ open, onClose, privacyMode = false }: MemoryDrawerProps) => {
  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 bg-background/60 backdrop-blur-sm z-40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />

          {/* Drawer */}
          <motion.div
            className="fixed bottom-0 left-0 right-0 z-50 bg-card rounded-t-3xl max-h-[85vh] overflow-y-auto"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
          >
            {/* Handle */}
            <div className="flex justify-center pt-3 pb-2">
              <div className="w-10 h-1 rounded-full bg-muted" />
            </div>

            <div className="px-5 pb-10">
              {/* Header */}
              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-2">
                  <Brain size={18} className="text-primary" />
                  <h3 className="font-display font-bold text-lg text-foreground">Your vibe</h3>
                </div>
                <button onClick={onClose} className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center">
                  <X size={14} className="text-secondary-foreground" />
                </button>
              </div>

              {privacyMode ? (
                <div className="glass rounded-2xl p-6 flex flex-col items-center gap-3 text-center">
                  <Shield size={32} className="text-muted-foreground" />
                  <h4 className="font-display font-semibold text-foreground">Incognito mode</h4>
                  <p className="text-xs text-muted-foreground">Memory is off. Hugo won't remember anything from this session.</p>
                </div>
              ) : (
                <>
                  {/* Long-term preferences */}
                  <div className="mb-5">
                    <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Preferences</span>
                    <div className="flex flex-wrap gap-2 mt-2">
                      {preferences.map((pref) => (
                        <div key={pref.label} className="flex items-center gap-1.5 px-3 py-1.5 rounded-full glass text-xs font-medium text-foreground">
                          <pref.icon size={12} className="text-primary" />
                          {pref.label}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Today's constraints */}
                  <div className="mb-5">
                    <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Today</span>
                    <div className="glass rounded-xl p-3 mt-2">
                      {todayConstraints.map((c) => (
                        <div key={c.label} className="flex items-center justify-between py-1.5 border-b border-border last:border-0">
                          <span className="text-xs text-muted-foreground">{c.label}</span>
                          <span className="text-xs font-semibold text-foreground">{c.value}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Recent memory updates */}
                  <div>
                    <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Recent updates</span>
                    <div className="mt-2 flex flex-col gap-2">
                      {recentUpdates.map((update, i) => (
                        <motion.div
                          key={i}
                          className="flex items-start gap-2 glass rounded-xl p-3"
                          initial={{ opacity: 0, x: 20 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: i * 0.1 }}
                        >
                          <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 flex-shrink-0" />
                          <div>
                            <p className="text-xs text-foreground">{update.text}</p>
                            <span className="text-[10px] text-muted-foreground">{update.time}</span>
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  </div>
                </>
              )}

              {/* Powered by */}
              <p className="text-[10px] text-muted-foreground text-center mt-6">
                Memory powered by Blackboard
              </p>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

export default MemoryDrawer;
