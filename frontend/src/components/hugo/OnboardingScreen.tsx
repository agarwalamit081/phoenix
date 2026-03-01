import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";
import { MapPin, Shield, Brain, ChevronRight, Globe, Mic } from "lucide-react";

interface OnboardingScreenProps {
  onComplete: () => void;
}

const languages = [
  { code: "en", label: "English", flag: "🇬🇧", preview: "Hey, I'm Hugo!" },
  { code: "zh", label: "中文", flag: "🇨🇳", preview: "嗨，我是Hugo！" },
  { code: "ja", label: "日本語", flag: "🇯🇵", preview: "やぁ、Hugoだよ！" },
  { code: "ko", label: "한국어", flag: "🇰🇷", preview: "안녕, 나는 Hugo야!" },
];

type Step = "language" | "location" | "privacy" | "start";

const OnboardingScreen = ({ onComplete }: OnboardingScreenProps) => {
  const [step, setStep] = useState<Step>("language");
  const [selectedLang, setSelectedLang] = useState("en");
  const [memoryOn, setMemoryOn] = useState(true);

  const currentLang = languages.find((l) => l.code === selectedLang)!;

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center px-6 relative overflow-hidden">
      {/* Ambient glow */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[400px] h-[400px] rounded-full bg-primary/8 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-[200px] h-[200px] rounded-full bg-accent/5 blur-[80px] pointer-events-none" />

      <AnimatePresence mode="wait">
        {/* LANGUAGE */}
        {step === "language" && (
          <motion.div
            key="language"
            className="w-full max-w-sm flex flex-col items-center gap-8"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -30 }}
          >
            <div className="flex flex-col items-center gap-2">
              <div className="w-14 h-14 rounded-2xl bg-primary/15 flex items-center justify-center glow-violet">
                <Globe size={24} className="text-primary" />
              </div>
              <h1 className="font-display font-bold text-2xl text-foreground mt-4">
                Choose your language
              </h1>
              <p className="text-sm text-muted-foreground text-center">
                Hugo speaks your language, naturally.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3 w-full">
              {languages.map((lang) => (
                <motion.button
                  key={lang.code}
                  onClick={() => setSelectedLang(lang.code)}
                  className={`relative p-4 rounded-2xl text-left transition-all ${
                    selectedLang === lang.code
                      ? "glass-violet glow-violet"
                      : "glass hover:bg-muted/50"
                  }`}
                  whileTap={{ scale: 0.97 }}
                >
                  <span className="text-2xl">{lang.flag}</span>
                  <p className="font-display font-semibold text-sm text-foreground mt-2">
                    {lang.label}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5 italic">
                    "{lang.preview}"
                  </p>
                </motion.button>
              ))}
            </div>

            <motion.button
              onClick={() => setStep("location")}
              className="w-full py-4 rounded-2xl bg-primary text-primary-foreground font-display font-bold text-base flex items-center justify-center gap-2"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              Continue
              <ChevronRight size={18} />
            </motion.button>
          </motion.div>
        )}

        {/* LOCATION */}
        {step === "location" && (
          <motion.div
            key="location"
            className="w-full max-w-sm flex flex-col items-center gap-8"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -30 }}
          >
            <div className="flex flex-col items-center gap-2">
              <div className="w-14 h-14 rounded-2xl bg-accent/15 flex items-center justify-center glow-mint">
                <MapPin size={24} className="text-accent" />
              </div>
              <h1 className="font-display font-bold text-2xl text-foreground mt-4">
                Enable location
              </h1>
              <p className="text-sm text-muted-foreground text-center max-w-xs">
                Hugo uses your location to build walking routes, give real-time directions, and find spots nearby.
              </p>
            </div>

            <div className="glass rounded-2xl p-4 w-full">
              <div className="flex items-start gap-3">
                <MapPin size={16} className="text-accent mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm font-semibold text-foreground">Precise location</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Only used while Hugo is active. Never shared or stored on servers.
                  </p>
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-3 w-full">
              <motion.button
                onClick={() => setStep("privacy")}
                className="w-full py-4 rounded-2xl bg-primary text-primary-foreground font-display font-bold text-base flex items-center justify-center gap-2"
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                Allow location
                <MapPin size={16} />
              </motion.button>
              <button
                onClick={() => setStep("privacy")}
                className="text-xs text-muted-foreground font-medium underline underline-offset-2"
              >
                Skip for now
              </button>
            </div>
          </motion.div>
        )}

        {/* PRIVACY */}
        {step === "privacy" && (
          <motion.div
            key="privacy"
            className="w-full max-w-sm flex flex-col items-center gap-8"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -30 }}
          >
            <div className="flex flex-col items-center gap-2">
              <div className="w-14 h-14 rounded-2xl bg-primary/15 flex items-center justify-center">
                <Shield size={24} className="text-primary" />
              </div>
              <h1 className="font-display font-bold text-2xl text-foreground mt-4">
                Your privacy
              </h1>
              <p className="text-sm text-muted-foreground text-center max-w-xs">
                Hugo can remember your vibe to personalise future trips.
              </p>
            </div>

            <div className="flex flex-col gap-3 w-full">
              <motion.button
                onClick={() => setMemoryOn(true)}
                className={`p-4 rounded-2xl text-left transition-all ${
                  memoryOn ? "glass-violet glow-violet" : "glass"
                }`}
                whileTap={{ scale: 0.97 }}
              >
                <div className="flex items-center gap-3">
                  <Brain size={20} className={memoryOn ? "text-primary" : "text-muted-foreground"} />
                  <div>
                    <p className="font-display font-semibold text-sm text-foreground">
                      Remember my vibe
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Recommended · Hugo learns your pace, interests & preferences
                    </p>
                  </div>
                </div>
              </motion.button>

              <motion.button
                onClick={() => setMemoryOn(false)}
                className={`p-4 rounded-2xl text-left transition-all ${
                  !memoryOn ? "glass-violet glow-violet" : "glass"
                }`}
                whileTap={{ scale: 0.97 }}
              >
                <div className="flex items-center gap-3">
                  <Shield size={20} className={!memoryOn ? "text-primary" : "text-muted-foreground"} />
                  <div>
                    <p className="font-display font-semibold text-sm text-foreground">
                      Incognito mode
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      No memory stored · Fresh start every time
                    </p>
                  </div>
                </div>
              </motion.button>
            </div>

            <motion.button
              onClick={() => setStep("start")}
              className="w-full py-4 rounded-2xl bg-primary text-primary-foreground font-display font-bold text-base flex items-center justify-center gap-2"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              Continue
              <ChevronRight size={18} />
            </motion.button>
          </motion.div>
        )}

        {/* START */}
        {step === "start" && (
          <motion.div
            key="start"
            className="w-full max-w-sm flex flex-col items-center gap-8"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
          >
            <motion.div
              className="w-24 h-24 rounded-full bg-primary/15 flex items-center justify-center relative"
              animate={{ boxShadow: ["0 0 0 0px hsl(271 76% 53% / 0.3)", "0 0 0 30px hsl(271 76% 53% / 0)", "0 0 0 0px hsl(271 76% 53% / 0.3)"] }}
              transition={{ duration: 2.5, repeat: Infinity }}
            >
              <Mic size={40} className="text-primary" />
            </motion.div>

            <div className="flex flex-col items-center gap-2">
              <h1 className="font-display font-bold text-3xl text-foreground">
                Hey, I'm <span className="text-gradient">Hugo</span>
              </h1>
              <p className="text-sm text-muted-foreground text-center max-w-xs leading-relaxed">
                Your voice-first city guide. Tell me what you're into and I'll build you the perfect walk.
              </p>
            </div>

            <div className="glass rounded-2xl p-3 w-full">
              <p className="text-xs text-muted-foreground text-center italic">
                "I like hidden cafés, street art, and avoiding crowds. I have about 2 hours."
              </p>
            </div>

            <motion.button
              onClick={onComplete}
              className="w-full py-5 rounded-2xl bg-gradient-to-r from-primary to-accent text-accent-foreground font-display font-bold text-lg flex items-center justify-center gap-3"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
            >
              <Mic size={22} />
              Start talking to Hugo
            </motion.button>

            <p className="text-[10px] text-muted-foreground text-center">
              Powered by Speechmatics · Memory by Blackboard
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Step indicator */}
      <div className="absolute bottom-8 flex gap-2">
        {(["language", "location", "privacy", "start"] as Step[]).map((s) => (
          <div
            key={s}
            className={`h-1 rounded-full transition-all duration-300 ${
              s === step ? "w-8 bg-primary" : "w-2 bg-muted"
            }`}
          />
        ))}
      </div>
    </div>
  );
};

export default OnboardingScreen;
