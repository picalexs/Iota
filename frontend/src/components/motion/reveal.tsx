import type { ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";

interface RevealProps {
  readonly delay?: number;
  readonly children: ReactNode;
  readonly className?: string;
}

export function Reveal({ delay = 0, children, className }: RevealProps) {
  const reduce = useReducedMotion();
  if (reduce) return <div className={className}>{children}</div>;
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 10 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.32, delay, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}
