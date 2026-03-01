import { useState } from "react";
import { motion } from "framer-motion";
import { Mic, MicOff, MapPin } from "lucide-react";

const Index = () => {
  const [isRecording, setIsRecording] = useState(false);

  return (
    <div className="h-screen w-screen flex flex-col relative overflow-hidden">
      {/* Map area */}
      <div className="flex-1 relative bg-slate-900">
        {/* Placeholder map */}
        <div className="absolute inset-0 bg-gradient-to-b from-slate-800 to-slate-900">
          <div className="absolute inset-0 opacity-20" style={{
            backgroundImage: `radial-gradient(circle at 25% 35%, hsl(160 60% 40%) 0px, transparent 60%),
              radial-gradient(circle at 70% 60%, hsl(210 60% 40%) 0px, transparent 50%),
              radial-gradient(circle at 50% 80%, hsl(180 50% 30%) 0px, transparent 40%)`
          }} />
          {/* Map grid lines */}
          <div className="absolute inset-0 opacity-[0.06]" style={{
            backgroundImage: `linear-gradient(hsl(210 20% 60%) 1px, transparent 1px), linear-gradient(90deg, hsl(210 20% 60%) 1px, transparent 1px)`,
            backgroundSize: '60px 60px'
          }} />
          {/* Center pin */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-full">
            <motion.div animate={{ y: [0, -6, 0] }} transition={{ duration: 2, repeat: Infinity }}>
              <MapPin size={36} className="text-emerald-400 drop-shadow-lg" fill="hsl(160 60% 40% / 0.3)" />
            </motion.div>
          </div>
          {/* Hugo label */}
          <div className="absolute top-6 left-1/2 -translate-x-1/2 bg-slate-950/70 backdrop-blur-md border border-slate-700/50 rounded-full px-5 py-2 flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-sm font-medium text-slate-200">Hugo is listening…</span>
          </div>
        </div>
      </div>

      {/* Voice recording box */}
      <div className="bg-slate-950 border-t border-slate-800 p-6 pb-8 flex flex-col items-center gap-4">
        <motion.button
          onClick={() => setIsRecording(!isRecording)}
          className={`w-24 h-24 rounded-full flex items-center justify-center transition-colors ${
            isRecording
              ? "bg-red-500/20 border-2 border-red-400 text-red-400"
              : "bg-emerald-500/20 border-2 border-emerald-400 text-emerald-400"
          }`}
          whileTap={{ scale: 0.92 }}
          animate={isRecording ? { scale: [1, 1.06, 1] } : {}}
          transition={isRecording ? { duration: 1.5, repeat: Infinity } : {}}
        >
          {isRecording ? <MicOff size={36} /> : <Mic size={36} />}
        </motion.button>
        <p className="text-sm text-slate-400">
          {isRecording ? "Tap to stop" : "Tap to talk to Hugo"}
        </p>
      </div>
    </div>
  );
};

export default Index;
