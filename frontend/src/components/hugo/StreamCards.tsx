import { motion, AnimatePresence } from "framer-motion";
import { Coffee, Palette, ShoppingBag, Sparkles, MessageCircle, ThumbsUp, ThumbsDown, Image as ImageIcon } from "lucide-react";
import { useUserLocation } from "@/contexts/UserLocationContext";

type AppState = "idle" | "listening" | "thinking" | "confirmed";

interface StreamCardsProps {
  appState: AppState;
  onConfirmBooking: () => void;
  // Optional: itinerary data from backend API
  itinerary?: Array<{
    icon: typeof Coffee | typeof Palette | typeof ShoppingBag;
    title: string;
    time: string;
    vibe: string;
    image?: string;
    vibeColor: string;
  }>;
  insight?: {
    title: string;
    content: string;
    waitTime?: string;
  };
  socialProof?: {
    subreddit: string;
    quote: string;
  };
}

// Default itinerary items - used when no data provided from backend
// These should be replaced with real data from the backend API
const defaultItinerary = [
  {
    icon: Coffee,
    title: "Local Café",
    time: "10:00 AM",
    vibe: "🔥 Buzzing right now",
    vibeColor: "text-accent",
  },
  {
    icon: Palette,
    title: "Art Gallery",
    time: "12:30 PM",
    vibe: "✨ Quiet & intimate",
    vibeColor: "text-primary",
  },
  {
    icon: ShoppingBag,
    title: "Local Market",
    time: "2:00 PM",
    vibe: "🔥 Peak hour",
    vibeColor: "text-accent",
  },
];

const StreamCards = ({ appState, onConfirmBooking, itinerary: propItinerary, insight, socialProof }: StreamCardsProps) => {
  // Get user location from context
  const contextLocation = useUserLocation();
  const city = contextLocation.userLocation?.city || "your city";

  // Use props data or fallback to defaults
  const displayItinerary = propItinerary || defaultItinerary;
  const displayInsight = insight || {
    title: "Hugo Note",
    content: `Skip the main entrance. Use the side entrance instead. Current wait: <span class="font-bold text-accent">5 mins</span>.`,
  };
  const displaySocialProof = socialProof || {
    subreddit: `r/${city.replace(/\s+/g, "")}Travel`,
    quote: `Check out the local spots for authentic experiences.`,
  };
  return (
    <div className="flex flex-col gap-4">
      {/* Itinerary Card */}
      <motion.div
        className="glass rounded-2xl p-4 overflow-hidden"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-display font-bold text-sm text-foreground tracking-tight">
            Today's Itinerary
          </h3>
          <span className="text-[10px] font-medium text-muted-foreground bg-secondary px-2 py-0.5 rounded-full">
            3 stops
          </span>
        </div>

        <div className="flex flex-col gap-3">
          {displayItinerary.map((stop, i) => (
            <motion.div
              key={i}
              className="flex gap-3 items-start group"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.8 + i * 0.15 }}
            >
              {/* Timeline */}
              <div className="flex flex-col items-center gap-1 pt-1">
                <div className="w-8 h-8 rounded-xl bg-secondary flex items-center justify-center group-hover:bg-primary/20 transition-colors">
                  <stop.icon size={14} className="text-secondary-foreground group-hover:text-primary transition-colors" />
                </div>
                {i < displayItinerary.length - 1 && (
                  <div className="w-px h-8 bg-border" />
                )}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-muted-foreground font-medium">{stop.time}</span>
                  <span className={`text-[10px] font-semibold ${stop.vibeColor}`}>{stop.vibe}</span>
                </div>
                <h4 className="font-display font-semibold text-sm text-foreground">{stop.title}</h4>
              </div>

              {/* Image */}
              <div className="w-14 h-14 rounded-xl overflow-hidden flex-shrink-0 bg-secondary/50">
                {stop.image ? (
                  <img
                    src={stop.image}
                    alt={stop.title}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-muted-foreground">
                    <ImageIcon size={16} />
                  </div>
                )}
              </div>
            </motion.div>
          ))}
        </div>
      </motion.div>

      {/* AI Insight Card */}
      <motion.div
        className="glass-violet rounded-2xl p-4 relative overflow-hidden"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.0 }}
      >
        <div className="absolute top-0 right-0 w-32 h-32 bg-primary/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
        <div className="flex items-start gap-3 relative">
          <div className="w-8 h-8 rounded-xl bg-primary/20 flex items-center justify-center flex-shrink-0">
            <Sparkles size={14} className="text-primary" />
          </div>
          <div>
            <span className="text-[10px] font-bold text-primary tracking-wider uppercase">{displayInsight.title}</span>
            <p
              className="text-sm text-foreground mt-1 leading-relaxed"
              dangerouslySetInnerHTML={{ __html: displayInsight.content }}
            />
          </div>
        </div>
      </motion.div>

      {/* Social Proof Card */}
      <motion.div
        className="glass rounded-2xl p-4"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.2 }}
      >
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-xl bg-secondary flex items-center justify-center flex-shrink-0">
            <MessageCircle size={14} className="text-secondary-foreground" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-bold text-rose tracking-wider uppercase">
                Trending on Reddit
              </span>
              <span className="text-[10px] text-muted-foreground">{displaySocialProof.subreddit}</span>
            </div>
            <p className="text-sm text-foreground mt-1 leading-relaxed">
              "{displaySocialProof.quote}"
            </p>
            <p className="text-xs text-muted-foreground mt-2">Should we swap?</p>
            <div className="flex gap-2 mt-3">
              <button
                onClick={onConfirmBooking}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-accent text-accent-foreground text-xs font-bold hover:opacity-90 transition-opacity"
              >
                <ThumbsUp size={12} />
                Yes, swap it
              </button>
              <button className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-secondary text-secondary-foreground text-xs font-medium hover:bg-muted transition-colors">
                <ThumbsDown size={12} />
                Keep original
              </button>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default StreamCards;
