import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import OnboardingScreen from "@/components/hugo/OnboardingScreen";
import PreferenceScreen from "@/components/hugo/PreferenceScreen";
import RouteScreen from "@/components/hugo/RouteScreen";
import GuidedTourScreen from "@/components/hugo/GuidedTourScreen";
import MemoryDrawer from "@/components/hugo/MemoryDrawer";
import { StopDisplayData } from "@/types/route";

type Screen = "onboarding" | "preferences" | "route" | "guided";

const Index = () => {
  const [screen, setScreen] = useState<Screen>("onboarding");
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [routeStops, setRouteStops] = useState<StopDisplayData[]>([]);

  const goToPreferences = useCallback(() => {
    setRouteStops([]);
    setScreen("preferences");
  }, []);
  const goToRoute = useCallback(() => {
    setRouteStops([]);
    setScreen("route");
  }, []);
  const goToGuided = useCallback(() => setScreen("guided"), []);

  return (
    <div className="min-h-screen bg-background relative overflow-x-hidden">
      <AnimatePresence mode="wait">
        {screen === "onboarding" && (
          <motion.div key="onboarding" exit={{ opacity: 0 }} transition={{ duration: 0.3 }}>
            <OnboardingScreen onComplete={goToPreferences} />
          </motion.div>
        )}
        {screen === "preferences" && (
          <motion.div key="preferences" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.3 }}>
            <PreferenceScreen onGenerateRoute={goToRoute} />
          </motion.div>
        )}
        {screen === "route" && (
          <motion.div key="route" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.3 }}>
            <RouteScreen
              onStartTour={goToGuided}
              onSwapStop={(i) => console.log("swap", i)}
              onRouteReady={setRouteStops}
              autoGenerate
            />
          </motion.div>
        )}
        {screen === "guided" && (
          <motion.div key="guided" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.3 }}>
            <GuidedTourScreen onOpenMemory={() => setMemoryOpen(true)} routeStops={routeStops} />
          </motion.div>
        )}
      </AnimatePresence>

      <MemoryDrawer open={memoryOpen} onClose={() => setMemoryOpen(false)} />
    </div>
  );
};

export default Index;
