import React, { useState } from 'react';
import {
  MapPin, MessageSquare, Globe, Zap, Mic, ArrowRight, Sparkles, Brain, Shield,
  Users, Volume2, ChevronRight, Star, Play, Radio, Eye, RefreshCw, Ear,
  HandMetal, Lock, Layers, Activity, UserCheck, Waypoints
} from 'lucide-react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';

const FeatureCard = ({ icon, title, desc, tag }: { icon: React.ReactNode; title: string; desc: string; tag?: string }) => (
  <motion.div
    className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 hover:border-slate-600 transition-all backdrop-blur-sm group relative"
    whileHover={{ y: -4, borderColor: 'rgba(148,163,184,0.3)' }}
    initial={{ opacity: 0, y: 20 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true }}
  >
    {tag && (
      <span className="absolute top-3 right-3 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
        {tag}
      </span>
    )}
    <div className="mb-4 w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center group-hover:scale-110 transition-transform">{icon}</div>
    <h3 className="text-lg font-bold mb-2 text-white">{title}</h3>
    <p className="text-slate-400 text-sm leading-relaxed">{desc}</p>
  </motion.div>
);

const StepCard = ({ number, title, desc }: { number: string; title: string; desc: string }) => (
  <motion.div
    className="flex gap-4 items-start"
    initial={{ opacity: 0, x: -20 }}
    whileInView={{ opacity: 1, x: 0 }}
    viewport={{ once: true }}
  >
    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-emerald-500 flex items-center justify-center text-sm font-bold text-white flex-shrink-0">
      {number}
    </div>
    <div>
      <h4 className="font-bold text-white text-base">{title}</h4>
      <p className="text-slate-400 text-sm mt-1 leading-relaxed">{desc}</p>
    </div>
  </motion.div>
);

const VoiceStateDemo = ({ state, label, desc, color }: { state: string; label: string; desc: string; color: string }) => (
  <motion.div
    className="flex items-center gap-3 p-3 rounded-xl bg-slate-800/50"
    initial={{ opacity: 0, x: -10 }}
    whileInView={{ opacity: 1, x: 0 }}
    viewport={{ once: true }}
  >
    <div className={`w-3 h-3 rounded-full ${color} flex-shrink-0`} />
    <div>
      <span className="text-xs font-bold text-white">{label}</span>
      <p className="text-[11px] text-slate-500">{desc}</p>
    </div>
  </motion.div>
);

const Landing = () => {
  const [showModeChoice, setShowModeChoice] = useState(false);
  return (
    <div className="bg-slate-950 text-white min-h-screen overflow-x-hidden">
      {/* Nav */}
      <nav className="fixed top-0 left-0 right-0 z-50 px-6 py-4 backdrop-blur-xl bg-slate-950/70 border-b border-slate-800/50">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-emerald-500 flex items-center justify-center">
              <span className="font-bold text-sm text-white">H</span>
            </div>
            <span className="font-bold text-lg text-white tracking-tight">Hugo</span>
            <span className="text-[10px] font-medium text-slate-500 bg-slate-800 px-2 py-0.5 rounded-full ml-1">group-aware · learning-aware</span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-sm text-slate-400">
            <a href="#voice" className="hover:text-white transition">Voice UX</a>
            <a href="#features" className="hover:text-white transition">Features</a>
            <a href="#how" className="hover:text-white transition">How it works</a>
            <a href="#tech" className="hover:text-white transition">Technology</a>
          </div>
          <Link
            to="/app"
            className="bg-white text-black px-5 py-2 rounded-full text-sm font-semibold hover:bg-slate-200 transition"
          >
            Try Hugo
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="min-h-screen flex flex-col items-center justify-center px-6 pt-20 relative">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full bg-blue-500/8 blur-[150px] pointer-events-none" />
        <div className="absolute bottom-1/4 right-1/3 w-[300px] h-[300px] rounded-full bg-emerald-500/5 blur-[100px] pointer-events-none" />

        <motion.div
          className="max-w-4xl text-center relative z-10"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7 }}
        >
          <motion.div
            className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-slate-700 text-xs text-slate-400 mb-8 bg-slate-900/50"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            <Sparkles size={12} className="text-emerald-400" />
            Group-aware · Learning-aware · Powered by Speechmatics + Blackboard
          </motion.div>

          <p className="text-lg md:text-xl text-slate-400 mb-4 uppercase tracking-widest font-medium">The world's first</p>
          <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-4 leading-tight">
            <span className="bg-gradient-to-r from-blue-400 via-cyan-300 to-emerald-400 bg-clip-text text-transparent">Group-aware</span>
            <span className="text-slate-500 mx-2">·</span>
            <span className="bg-gradient-to-r from-emerald-400 via-cyan-300 to-blue-400 bg-clip-text text-transparent">Learning-aware</span>
          </h1>
          <p className="text-2xl md:text-3xl font-semibold text-slate-300 mb-2">AI Tour Guide</p>

          <p className="text-lg md:text-xl text-slate-400 mb-4 max-w-2xl mx-auto leading-relaxed">
            The voice-first travel companion that listens, learns, and guides you through any city — hands-free, with ultra-fast conversation feel.
          </p>

          <p className="text-sm text-slate-500 mb-10 max-w-xl mx-auto">
            Works for solo travellers, couples, families, and friend groups. Hugo builds compromise routes, remembers your vibe, and adapts in real time.
          </p>

          {!showModeChoice ? (
            <div className="flex flex-col sm:flex-row gap-4 justify-center mb-6">
              <button
                onClick={() => setShowModeChoice(true)}
                className="bg-white text-black px-8 py-4 rounded-full font-semibold hover:bg-slate-200 transition flex items-center justify-center gap-2 text-base"
              >
                <Mic size={18} />
                Start Your Journey
              </button>
              <button className="border border-slate-700 px-8 py-4 rounded-full font-semibold hover:bg-slate-900 transition flex items-center justify-center gap-2 text-base text-white">
                <Play size={18} />
                Watch Demo
              </button>
            </div>
          ) : (
            <motion.div
              className="flex flex-col sm:flex-row gap-4 justify-center mb-6"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
            >
              <Link
                to="/app?mode=solo"
                className="group relative px-8 py-5 rounded-2xl bg-slate-900 border border-slate-700 hover:border-emerald-500/50 transition-all flex flex-col items-center gap-2 min-w-[180px]"
              >
                <UserCheck size={24} className="text-emerald-400" />
                <span className="font-bold text-white text-base">Solo Mode</span>
                <span className="text-xs text-slate-400">Just you & Hugo</span>
              </Link>
              <Link
                to="/app?mode=group"
                className="group relative px-8 py-5 rounded-2xl bg-slate-900 border border-slate-700 hover:border-blue-500/50 transition-all flex flex-col items-center gap-2 min-w-[180px]"
              >
                <Users size={24} className="text-blue-400" />
                <span className="font-bold text-white text-base">Group Mode</span>
                <span className="text-xs text-slate-400">Friends, couples, families</span>
              </Link>
            </motion.div>
          )}
        </motion.div>

        <motion.div className="absolute bottom-8" animate={{ y: [0, 8, 0] }} transition={{ duration: 2, repeat: Infinity }}>
          <ChevronRight size={20} className="text-slate-600 rotate-90" />
        </motion.div>
      </section>

      {/* Product story */}
      <section className="py-20 px-6">
        <motion.div className="max-w-3xl mx-auto text-center" initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }}>
          <div className="glass-violet rounded-2xl p-8 md:p-12 border border-slate-700/50">
            <p className="text-lg md:text-xl text-slate-300 leading-relaxed italic">
              "Hugo is for travellers who want a great city walk; it builds and guides a personalised route hands‑free, and <span className="text-emerald-400 font-semibold not-italic">voice is best because you're moving</span> and your attention is on the street—not on your screen."
            </p>
          </div>
        </motion.div>
      </section>

      {/* Conversation Feel & Voice UX */}
      <section id="voice" className="py-20 px-6 bg-slate-900/30">
        <div className="max-w-5xl mx-auto">
          <motion.div className="text-center mb-16" initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }}>
            <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider mb-3 block">Conversation Feel & UX</span>
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
              Voice that feels like talking to a friend
            </h2>
            <p className="text-slate-400 max-w-2xl mx-auto">
              Ultra-fast partial transcripts, clear state indicators, and natural barge-in. Hugo's voice loop is designed to feel instant and effortless — minimal screens, maximum conversation.
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 gap-8">
            {/* Voice states */}
            <motion.div
              className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800"
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
            >
              <div className="flex items-center gap-2 mb-4">
                <Radio size={16} className="text-blue-400" />
                <h3 className="font-bold text-white">Voice Orb States</h3>
              </div>
              <div className="flex flex-col gap-2">
                <VoiceStateDemo state="idle" label="Idle" desc="Tap to talk — minimal UI, map stays visible" color="bg-slate-500" />
                <VoiceStateDemo state="listening" label="Listening" desc="Audio level animation + live partial transcript" color="bg-emerald-400 animate-pulse" />
                <VoiceStateDemo state="thinking" label="Thinking" desc="Agent reasoning — tool calls shown as activity log" color="bg-blue-400 animate-pulse" />
                <VoiceStateDemo state="speaking" label="Speaking" desc="TTS playback — tap to interrupt (barge-in)" color="bg-cyan-400" />
                <VoiceStateDemo state="interrupted" label="Interrupted" desc="Barge-in detected — Hugo stops and listens" color="bg-yellow-400" />
                <VoiceStateDemo state="error" label="Error" desc="Graceful fallback: 'Try holding phone closer'" color="bg-red-400" />
              </div>
            </motion.div>

            {/* Conversation principles */}
            <motion.div
              className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800"
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1 }}
            >
              <div className="flex items-center gap-2 mb-4">
                <Ear size={16} className="text-cyan-400" />
                <h3 className="font-bold text-white">Conversation Principles</h3>
              </div>
              <div className="flex flex-col gap-4">
                {[
                  { title: "Ultra-fast partials", desc: "Speechmatics streams partial transcripts in real-time. You see your words appear as you speak — zero perceived lag." },
                  { title: "Natural interruption", desc: "Barge-in support means you can cut Hugo off mid-sentence. It stops, listens, and responds — like a real conversation." },
                  { title: "Lightweight confirmations", desc: "Hugo confirms understanding without being annoying: a subtle chip, a brief 'Got it', never a modal." },
                  { title: "Escalating fallbacks", desc: "If Hugo doesn't catch something, it escalates in clarity — not blame. 'Could you say that again?' → 'Try holding phone closer.'" },
                  { title: "Minimal screens", desc: "The UI stays quiet. Map + route + voice orb. No walls of text. Your attention stays on the street." },
                ].map((item, i) => (
                  <div key={i}>
                    <h4 className="text-sm font-bold text-white">{item.title}</h4>
                    <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">{item.desc}</p>
                  </div>
                ))}
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Task Completion & Autonomy */}
      <section className="py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <motion.div className="text-center mb-16" initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }}>
            <span className="text-xs font-bold text-blue-400 uppercase tracking-wider mb-3 block">Task Completion & Autonomy</span>
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
              Hugo doesn't just chat — it gets things done
            </h2>
            <p className="text-slate-400 max-w-2xl mx-auto">
              Autonomous tool calls, real-time route building, and guided mode — all triggered by voice, completed end-to-end without hand-holding.
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { icon: <MapPin size={20} className="text-emerald-400" />, title: "Fetch POIs", desc: "Hugo calls tools to find cafés, landmarks, and hidden gems based on your vibe." },
              { icon: <Waypoints size={20} className="text-blue-400" />, title: "Build routes", desc: "Produces a walking route with stops, distances, ETAs, and live crowd data." },
              { icon: <RefreshCw size={20} className="text-cyan-400" />, title: "Recalculate", desc: "'Less crowded' or 'add coffee' — Hugo recalculates the route instantly on command." },
              { icon: <Activity size={20} className="text-purple-400" />, title: "Guided mode", desc: "Switches to live narration. Progress bar, depth controls, and fast-access buttons." },
            ].map((item, i) => (
              <motion.div
                key={i}
                className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.08 }}
              >
                <div className="mb-3">{item.icon}</div>
                <h4 className="font-bold text-sm text-white mb-1">{item.title}</h4>
                <p className="text-xs text-slate-400 leading-relaxed">{item.desc}</p>
              </motion.div>
            ))}
          </div>

          {/* Activity log example */}
          <motion.div
            className="mt-8 max-w-md mx-auto p-4 rounded-2xl bg-slate-900/80 border border-slate-800"
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
          >
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Live activity log</span>
            <div className="mt-2 flex flex-col gap-1.5">
              {[
                { text: "Finding cafés nearby…", done: true },
                { text: "Checking crowd levels…", done: true },
                { text: "Calculating walking route…", done: true },
                { text: "Summarising landmark story…", done: false },
              ].map((item, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div className={`w-1.5 h-1.5 rounded-full ${item.done ? "bg-emerald-400" : "bg-blue-400 animate-pulse"}`} />
                  <span className={`text-xs ${item.done ? "text-slate-500" : "text-white"}`}>{item.text}</span>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* Memory & Adaptivity */}
      <section className="py-20 px-6 bg-slate-900/30">
        <div className="max-w-5xl mx-auto">
          <motion.div className="text-center mb-16" initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }}>
            <span className="text-xs font-bold text-purple-400 uppercase tracking-wider mb-3 block">Memory & Adaptivity</span>
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
              Hugo learns. Hugo remembers.
            </h2>
            <p className="text-slate-400 max-w-2xl mx-auto">
              Powered by Blackboard's persistent memory. Hugo notices patterns, adapts mid-walk, and recalls your preferences across sessions and cities.
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 gap-8">
            {/* Memory updates example */}
            <motion.div
              className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800"
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
            >
              <div className="flex items-center gap-2 mb-4">
                <Brain size={16} className="text-purple-400" />
                <h3 className="font-bold text-white">Live memory updates</h3>
              </div>
              <div className="flex flex-col gap-3">
                {[
                  { text: "Saved: prefers quiet neighbourhoods", time: "2 min ago", type: "write" },
                  { text: "I noticed you keep skipping museums — adjusting your next stops", time: "8 min ago", type: "adapt" },
                  { text: "Recalled: you liked street art in Barcelona last trip", time: "on start", type: "recall" },
                  { text: "Updated: walking pace → moderate (was: fast)", time: "12 min ago", type: "write" },
                ].map((item, i) => (
                  <motion.div
                    key={i}
                    className="flex items-start gap-3 p-3 rounded-xl bg-slate-800/50"
                    initial={{ opacity: 0, x: 20 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.1 }}
                  >
                    <div className={`w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${
                      item.type === "adapt" ? "bg-yellow-400" : item.type === "recall" ? "bg-cyan-400" : "bg-purple-400"
                    }`} />
                    <div>
                      <p className="text-xs text-white">{item.text}</p>
                      <span className="text-[10px] text-slate-500">{item.time}</span>
                    </div>
                  </motion.div>
                ))}
              </div>
            </motion.div>

            {/* Memory modes */}
            <motion.div
              className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800"
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1 }}
            >
              <div className="flex items-center gap-2 mb-4">
                <Lock size={16} className="text-rose-400" />
                <h3 className="font-bold text-white">Memory modes (Blackboard SDK)</h3>
              </div>
              <div className="flex flex-col gap-4">
                {[
                  { mode: "Auto", desc: "Full memory: search past preferences + write new learnings. Best experience — Hugo gets smarter every trip.", color: "bg-emerald-400", tag: "Recommended" },
                  { mode: "Readonly", desc: "Search only: Hugo recalls past preferences but doesn't save anything new. Good for shared devices.", color: "bg-blue-400", tag: null },
                  { mode: "Off (Incognito)", desc: "No memory reads or writes. Completely private session. Fresh start every time.", color: "bg-slate-500", tag: "Privacy" },
                ].map((item, i) => (
                  <div key={i} className="p-3 rounded-xl bg-slate-800/50">
                    <div className="flex items-center gap-2 mb-1">
                      <div className={`w-2 h-2 rounded-full ${item.color}`} />
                      <span className="text-sm font-bold text-white">{item.mode}</span>
                      {item.tag && <span className="text-[10px] font-medium text-slate-500 bg-slate-700 px-1.5 py-0.5 rounded">{item.tag}</span>}
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">{item.desc}</p>
                  </div>
                ))}
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Group Mode */}
      <section className="py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <motion.div className="text-center mb-16" initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }}>
            <span className="text-xs font-bold text-yellow-400 uppercase tracking-wider mb-3 block">Group-Aware</span>
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
              Built for friends, couples & families
            </h2>
            <p className="text-slate-400 max-w-2xl mx-auto">
              Speechmatics diarization identifies who's talking. Hugo builds compromise routes that balance everyone's interests — fairly.
            </p>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-6">
            <FeatureCard
              icon={<Users size={20} className="text-yellow-400" />}
              title="Speaker Diarization"
              desc="Speechmatics identifies individual speakers in a group. Each person gets a chip (S1, S2 → custom names) with their own preference profile."
              tag="Speechmatics"
            />
            <FeatureCard
              icon={<Layers size={20} className="text-orange-400" />}
              title="Compromise Routes"
              desc="Hugo builds routes that satisfy multiple profiles: '2 stops for Alex, 2 stops for Sam'. A 'keep it balanced' toggle ensures fairness."
              tag="Group AI"
            />
            <FeatureCard
              icon={<UserCheck size={20} className="text-emerald-400" />}
              title="Per-Person Memory"
              desc="Each group member's preferences are tracked separately via Blackboard. Next trip together? Hugo already knows the group dynamic."
              tag="Blackboard"
            />
          </div>
        </div>
      </section>

      {/* Core Features */}
      <section id="features" className="py-20 px-6 bg-slate-900/30">
        <div className="max-w-6xl mx-auto">
          <motion.div className="text-center mb-16" initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }}>
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
              Everything a guide should be
            </h2>
            <p className="text-slate-400 max-w-xl mx-auto">
              Voice-first. Hands-free. Adapts to you — not the other way around.
            </p>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-6">
            <FeatureCard icon={<Zap size={20} className="text-yellow-400" />} title="Dynamic Capture" desc="Learns your vibe through voice — interests, pace, food, crowd tolerance, budget. No typing, no forms." />
            <FeatureCard icon={<Globe size={20} className="text-blue-400" />} title="Global Context" desc="Synthesizes Reddit, Google Maps, and local forums for authentic 'non-tourist' spots." />
            <FeatureCard icon={<MessageSquare size={20} className="text-emerald-400" />} title="Interactive Routes" desc="'Less crowded', 'add coffee', 'shorten to 45 min' — Hugo recalculates the route instantly." />
            <FeatureCard icon={<Volume2 size={20} className="text-cyan-400" />} title="Live Narration" desc="30-second summaries or deep-dive storytelling. Interrupt anytime. Control narration depth on the fly." />
            <FeatureCard icon={<Eye size={20} className="text-purple-400" />} title="Proactive Insights" desc="Hugo surfaces tips before you need them: 'Skip the main entrance, use the side door — 5 min wait.'" />
            <FeatureCard icon={<Shield size={20} className="text-rose-400" />} title="Privacy Controls" desc="Three memory modes: Auto, Readonly, or Off. Your data, your choice. Fully GDPR-aware." />
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="py-20 px-6">
        <div className="max-w-3xl mx-auto">
          <motion.h2 className="text-3xl md:text-4xl font-bold text-white mb-12 text-center" initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }}>
            90 seconds to your perfect walk
          </motion.h2>
          <div className="flex flex-col gap-8">
            <StepCard number="1" title="Tell Hugo what you're into" desc="Speak naturally. Hugo picks up your interests, time budget, pace, and crowd tolerance. Partial transcripts appear in real-time via Speechmatics." />
            <StepCard number="2" title="Hugo calls tools autonomously" desc="Fetches POIs, checks crowd levels, calculates walking routes, summarises landmarks. You see every action in the live activity log." />
            <StepCard number="3" title="Pick your route and go" desc="Choose 'Hidden gems' or 'Must-sees'. Swap any stop, adjust constraints. One tap to start guided mode." />
            <StepCard number="4" title="Walk with live narration" desc="Hugo talks you through each stop. Choose depth (quick / standard / deep dive). Interrupt anytime — barge-in just works." />
            <StepCard number="5" title="Hugo adapts and remembers" desc="Mid-walk: 'I noticed you keep skipping museums — adjusting.' Next trip: Hugo already knows your vibe via Blackboard memory." />
          </div>
        </div>
      </section>

      {/* Tech stack */}
      <section id="tech" className="py-20 px-6 bg-slate-900/30">
        <div className="max-w-5xl mx-auto text-center">
          <motion.div className="mb-12" initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }}>
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">Built with best-in-class tech</h2>
            <p className="text-slate-400 max-w-xl mx-auto">Partner technology is core to Hugo, not bolted on.</p>
          </motion.div>

          <div className="grid md:grid-cols-2 gap-6 mb-8">
            {/* Speechmatics */}
            <motion.div
              className="p-6 rounded-2xl bg-slate-900/80 border border-blue-500/20 text-left"
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
            >
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
                  <Radio size={18} className="text-white" />
                </div>
                <div>
                  <h3 className="font-bold text-white">Speechmatics</h3>
                  <span className="text-xs text-blue-400">Real-time voice engine</span>
                </div>
              </div>
              <ul className="flex flex-col gap-2">
                {[
                  "Ultra-fast partial transcripts for instant conversation feel",
                  "End-of-utterance detection for natural turn-taking",
                  "Speaker diarization for group/couple mode",
                  "Multi-language support (EN, 中文, 日本語, 한국어)",
                  "Barge-in detection for natural interruption",
                ].map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-slate-400">
                    <div className="w-1 h-1 rounded-full bg-blue-400 mt-1.5 flex-shrink-0" />
                    {item}
                  </li>
                ))}
              </ul>
            </motion.div>

            {/* Blackboard */}
            <motion.div
              className="p-6 rounded-2xl bg-slate-900/80 border border-purple-500/20 text-left"
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1 }}
            >
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                  <Brain size={18} className="text-white" />
                </div>
                <div>
                  <h3 className="font-bold text-white">Blackboard</h3>
                  <span className="text-xs text-purple-400">Persistent memory SDK</span>
                </div>
              </div>
              <ul className="flex flex-col gap-2">
                {[
                  "Long-term preference recall across sessions and cities",
                  "Memory modes: Auto (search + write), Readonly, Off",
                  "Privacy toggle maps directly to SDK memory modes",
                  "Per-user and per-group memory profiles",
                  "Real-time memory updates visible in the UI",
                ].map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-slate-400">
                    <div className="w-1 h-1 rounded-full bg-purple-400 mt-1.5 flex-shrink-0" />
                    {item}
                  </li>
                ))}
              </ul>
            </motion.div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { name: "React", role: "Frontend", color: "from-cyan-500 to-blue-500" },
              { name: "Framer Motion", role: "Animations", color: "from-pink-500 to-rose-500" },
              { name: "TypeScript", role: "Type safety", color: "from-blue-600 to-blue-400" },
              { name: "Tailwind", role: "Styling", color: "from-teal-500 to-cyan-500" },
            ].map((tech) => (
              <motion.div
                key={tech.name}
                className="p-4 rounded-xl bg-slate-900 border border-slate-800"
                whileHover={{ borderColor: 'rgba(148,163,184,0.3)' }}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
              >
                <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${tech.color} mx-auto mb-3 flex items-center justify-center`}>
                  <Star size={14} className="text-white" />
                </div>
                <p className="font-bold text-sm text-white">{tech.name}</p>
                <p className="text-xs text-slate-500 mt-0.5">{tech.role}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-6">
        <motion.div className="max-w-2xl mx-auto text-center" initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
          <h2 className="text-3xl md:text-5xl font-bold text-white mb-4">
            Ready to explore?
          </h2>
          <p className="text-slate-400 mb-3 text-lg">
            Just tap, talk, and walk. Hugo handles the rest.
          </p>
          <p className="text-sm text-slate-500 mb-8">
            Solo, duo, or group. Hugo adapts to everyone.
          </p>
          <Link
            to="/app"
            className="inline-flex items-center gap-2 bg-gradient-to-r from-blue-500 to-emerald-500 text-white px-10 py-5 rounded-full font-bold text-lg hover:opacity-90 transition"
          >
            <Mic size={22} />
            Start Your Journey
            <ArrowRight size={18} />
          </Link>
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-800 py-8 px-6">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-gradient-to-br from-blue-500 to-emerald-500 flex items-center justify-center">
              <span className="font-bold text-[10px] text-white">H</span>
            </div>
            <span className="text-sm font-semibold text-slate-400">Hugo</span>
            <span className="text-[10px] text-slate-600">group-aware · learning-aware</span>
          </div>
          <p className="text-xs text-slate-600">
            Built for Voice AI Hackathon 2026 · Powered by Speechmatics & Blackboard
          </p>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
