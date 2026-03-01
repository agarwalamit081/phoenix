import { motion } from "framer-motion";
import { Check, QrCode, X } from "lucide-react";

interface BookingPassProps {
  onClose: () => void;
}

const BookingPass = ({ onClose }: BookingPassProps) => {
  return (
    <motion.div
      className="fixed inset-0 z-[60] flex items-center justify-center px-6"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      {/* Backdrop */}
      <motion.div
        className="absolute inset-0 bg-background/80 backdrop-blur-xl"
        onClick={onClose}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      />

      {/* Pass */}
      <motion.div
        className="relative w-full max-w-sm glass-strong rounded-3xl overflow-hidden"
        initial={{ scale: 0.85, y: 40, opacity: 0 }}
        animate={{ scale: 1, y: 0, opacity: 1 }}
        exit={{ scale: 0.85, y: 40, opacity: 0 }}
        transition={{ type: "spring", damping: 25, stiffness: 300 }}
      >
        {/* Shimmer overlay */}
        <div className="absolute inset-0 shimmer pointer-events-none" />

        {/* Close */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 w-8 h-8 rounded-full bg-secondary flex items-center justify-center z-10 hover:bg-muted transition-colors"
        >
          <X size={14} className="text-secondary-foreground" />
        </button>

        {/* Content */}
        <div className="p-6 flex flex-col items-center text-center relative">
          {/* Success icon */}
          <motion.div
            className="w-16 h-16 rounded-full bg-accent/20 flex items-center justify-center mb-4"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.2, type: "spring" }}
          >
            <div className="w-10 h-10 rounded-full bg-accent flex items-center justify-center">
              <Check size={20} className="text-accent-foreground" strokeWidth={3} />
            </div>
          </motion.div>

          <motion.h2
            className="font-display font-bold text-xl text-foreground"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            Booking Confirmed
          </motion.h2>

          <motion.p
            className="text-sm text-muted-foreground mt-1"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
          >
            Parc des Buttes-Chaumont · Sunset Session
          </motion.p>

          {/* Divider */}
          <div className="w-full border-t border-dashed border-border my-5 relative">
            <div className="absolute -left-6 top-1/2 w-5 h-5 rounded-full bg-background -translate-y-1/2" />
            <div className="absolute -right-6 top-1/2 w-5 h-5 rounded-full bg-background -translate-y-1/2" />
          </div>

          {/* Details */}
          <motion.div
            className="w-full grid grid-cols-2 gap-3 text-left"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
          >
            {[
              { label: "Date", value: "Today" },
              { label: "Time", value: "6:30 PM" },
              { label: "Type", value: "Sunset Viewing" },
              { label: "Guests", value: "2 people" },
            ].map((item, i) => (
              <div key={i}>
                <span className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider">
                  {item.label}
                </span>
                <p className="text-sm font-semibold text-foreground">{item.value}</p>
              </div>
            ))}
          </motion.div>

          {/* QR Code placeholder */}
          <motion.div
            className="mt-6 w-36 h-36 rounded-2xl bg-foreground/5 border border-border flex flex-col items-center justify-center gap-2"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.6 }}
          >
            <QrCode size={64} className="text-foreground/30" />
            <span className="text-[10px] text-muted-foreground">Scan to check in</span>
          </motion.div>

          <motion.p
            className="text-[10px] text-muted-foreground mt-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.7 }}
          >
            Powered by Hugo · Ref #HGO-2026-PAR
          </motion.p>
        </div>
      </motion.div>
    </motion.div>
  );
};

export default BookingPass;
