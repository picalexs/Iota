import { useTheme } from "@/hooks/use-theme";
import { motion, useTime, useTransform, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { useMoleculeLoaderAnimation, type OrbitConfig } from "./use-molecule-loader-animation";

type MoleculeLoaderSize = "sm" | "md" | "lg";

interface MoleculeLoaderProps {
  readonly className?: string;
  readonly size?: MoleculeLoaderSize;
}

const SIZE_CLASSES: Record<MoleculeLoaderSize, string> = {
  sm: "size-16",
  md: "size-20",
  lg: "size-32",
};

function splitAtomOffset(atomState: string): string {
  if (atomState === "splitting" || atomState === "paired") {
    return "50%";
  }
  return "0%";
}

function StaticAtom() {
  return (
    <svg
      viewBox="0 0 120 120"
      className="h-full w-full overflow-visible"
      aria-hidden="true"
      focusable="false"
    >
      <ellipse
        cx="60"
        cy="60"
        rx="35"
        ry="16"
        fill="none"
        stroke="currentColor"
        className="[stroke-opacity:0.34] dark:[stroke-opacity:0.48]"
      />
      <ellipse
        cx="60"
        cy="60"
        rx="35"
        ry="16"
        transform="rotate(60 60 60)"
        fill="none"
        stroke="currentColor"
        className="[stroke-opacity:0.24] dark:[stroke-opacity:0.36]"
      />
      <ellipse
        cx="60"
        cy="60"
        rx="35"
        ry="16"
        transform="rotate(-60 60 60)"
        fill="none"
        stroke="currentColor"
        className="[stroke-opacity:0.24] dark:[stroke-opacity:0.36]"
      />
      <circle cx="60" cy="60" r="13" className="fill-primary/25" />
      <circle cx="60" cy="60" r="7" className="fill-primary" />
      <circle cx="95" cy="60" r="4" className="fill-primary/80" />
      <circle cx="42" cy="88" r="4" className="fill-primary/80" />
      <circle cx="42" cy="32" r="4" className="fill-primary/80" />
    </svg>
  );
}

function AnimatedOrbit({
  angle,
  phase,
  angularSpeed,
  rx,
  ryPhase,
  opacity,
}: {
  readonly angle: number;
  readonly phase: number;
  readonly angularSpeed: number;
  readonly rx: number;
  readonly ryPhase: number;
  readonly opacity: number;
}) {
  const time = useTime();

  const theta = useTransform(time, (t) => ((t / 1000) * angularSpeed + phase) % (Math.PI * 2));

  // 3D illusion: ry oscillates between 4 and 16 with a slow period (~14 s)
  const ry = useTransform(
    time,
    (t) => 4 + 12 * (0.5 + 0.5 * Math.sin((t / 1000) * ((Math.PI * 2) / 14) + ryPhase)),
  );

  const electronCx = useTransform(theta, (v) => 60 + Math.cos(v) * rx);
  const electronCy = useTransform(
    [theta, ry],
    (values: number[]) => 60 + Math.sin(values[0] ?? 0) * (values[1] ?? 16),
  );

  return (
    <g transform={`rotate(${angle} 60 60)`}>
      <motion.ellipse
        cx="60"
        cy="60"
        rx={rx}
        style={{ ry }}
        fill="none"
        stroke="currentColor"
        strokeOpacity={opacity}
      />
      <motion.circle style={{ cx: electronCx, cy: electronCy }} r="4" className="fill-primary/85" />
    </g>
  );
}

function SingleAtomSVG({ orbitConfigs }: { readonly orbitConfigs: OrbitConfig[] }) {
  return (
    <motion.svg
      viewBox="0 0 120 120"
      className="h-full w-full overflow-visible"
      aria-hidden="true"
      focusable="false"
      initial={false}
    >
      <motion.circle
        cx="60"
        cy="60"
        r="15"
        className="fill-primary/20"
        animate={{ scale: [1, 1.08, 1] }}
        transition={{ duration: 2.8, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.circle
        cx="60"
        cy="60"
        r="8"
        className="fill-primary"
        animate={{ scale: [1, 1.12, 1] }}
        transition={{ duration: 2.8, repeat: Infinity, ease: "easeInOut" }}
      />
      {orbitConfigs.map((orbit) => (
        <AnimatedOrbit
          key={`${orbit.angle}-${orbit.phase}-${orbit.angularSpeed}`}
          angle={orbit.angle}
          phase={orbit.phase}
          angularSpeed={orbit.angularSpeed}
          rx={orbit.rx}
          ryPhase={orbit.ryPhase}
          opacity={orbit.opacity}
        />
      ))}
    </motion.svg>
  );
}

function EntanglementConnection({
  separation,
  angularSpeed,
  phase,
  ryPhase,
}: {
  readonly separation: number;
  readonly angularSpeed: number;
  readonly phase: number;
  readonly ryPhase: number;
}) {
  const time = useTime();
  const cx1 = 50 - separation;
  const cx2 = 50 + separation;
  const cy = 30;
  const bridgeRx = 8;

  const theta = useTransform(time, (t) => ((t / 1000) * angularSpeed + phase) % (Math.PI * 2));
  const ry = useTransform(
    time,
    (t) => 2.5 + 4.5 * (0.5 + 0.5 * Math.sin((t / 1000) * ((Math.PI * 2) / 14) + ryPhase)),
  );

  const leftX = useTransform(theta, (v) => cx1 + Math.cos(v) * bridgeRx);
  const rightX = useTransform(theta, (v) => cx2 + Math.cos(v) * bridgeRx);
  const leftY = useTransform(
    [theta, ry],
    (values: number[]) => cy + Math.sin(values[0] ?? 0) * (values[1] ?? 4),
  );
  const rightY = useTransform(
    [theta, ry],
    (values: number[]) => cy + Math.sin(values[0] ?? 0) * (values[1] ?? 4),
  );

  const endpointStyle = {
    cx: leftX,
    cy: leftY,
  };
  const endpointStyleRight = {
    cx: rightX,
    cy: rightY,
  };

  return (
    <svg
      viewBox="0 0 100 60"
      className="absolute inset-0 w-full overflow-visible pointer-events-none"
      style={{ top: "20%" }}
      aria-hidden="true"
    >
      <motion.line
        x1={leftX}
        y1={leftY}
        x2={rightX}
        y2={rightY}
        stroke="currentColor"
        strokeWidth="0.7"
        strokeDasharray="2.2 3"
        strokeLinecap="round"
        animate={{ strokeOpacity: [0.12, 0.3, 0.12] }}
        transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.circle
        r="1.6"
        className="fill-primary/80"
        style={endpointStyle}
        animate={{ opacity: [0.5, 1, 0.5] }}
        transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.circle
        r="1.6"
        className="fill-primary/80"
        style={endpointStyleRight}
        animate={{ opacity: [0.5, 1, 0.5] }}
        transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut", delay: 0.2 }}
      />
    </svg>
  );
}

export function MoleculeLoader({ className, size = "md" }: MoleculeLoaderProps) {
  const { resolvedTheme } = useTheme();
  const opacityFactor = resolvedTheme === "dark" ? 1.15 : 0.8;
  const { atomState, bridgeOrbit, isSplit, orbitConfigs, reduceMotion } =
    useMoleculeLoaderAnimation({
      mode: "auto",
      opacityFactor,
      speedMultiplier: 1,
    });

  if (reduceMotion) {
    return (
      <div className={cn("relative", SIZE_CLASSES[size], className)}>
        <StaticAtom />
      </div>
    );
  }

  return (
    <div
      className={cn("relative flex items-center justify-center text-primary", className)}
      aria-label="Quantum atom animation"
    >
      <AnimatePresence>
        {atomState === "paired" && (
          <motion.div
            className="absolute inset-0 pointer-events-none"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4 }}
            style={{ width: "200%", left: "-50%" }}
          >
            <EntanglementConnection
              separation={35}
              angularSpeed={bridgeOrbit.angularSpeed}
              phase={bridgeOrbit.phase}
              ryPhase={bridgeOrbit.ryPhase}
            />
          </motion.div>
        )}
      </AnimatePresence>

      <motion.div
        className={cn(SIZE_CLASSES[size], "shrink-0")}
        animate={{
          x: atomState === "splitting" || atomState === "paired" ? "-50%" : "0%",
        }}
        transition={{
          duration: atomState === "splitting" || atomState === "merging" ? 1.5 : 0,
          ease: [0.25, 0.46, 0.45, 0.94],
        }}
      >
        <SingleAtomSVG orbitConfigs={orbitConfigs} />
      </motion.div>

      <AnimatePresence>
        {isSplit && (
          <motion.div
            className={cn(SIZE_CLASSES[size], "absolute shrink-0")}
            initial={{ x: "0%", opacity: 0 }}
            animate={{
              x: splitAtomOffset(atomState),
              opacity: 1,
            }}
            exit={{ x: "0%", opacity: 0 }}
            transition={{
              duration: atomState === "splitting" || atomState === "merging" ? 1.5 : 0,
              ease: [0.25, 0.46, 0.45, 0.94],
              opacity: { duration: 0.3 },
            }}
          >
            <SingleAtomSVG orbitConfigs={orbitConfigs} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export interface LogoAtomProps {
  readonly isEntangled?: boolean;
  readonly size?: number;
  readonly className?: string;
}

export function LogoAtom({ isEntangled = false, size = 32, className }: LogoAtomProps) {
  const { resolvedTheme } = useTheme();
  const opacityFactor = resolvedTheme === "dark" ? 1.15 : 0.8;
  const { atomState, orbitConfigs, reduceMotion, isSplit, isWobbling, splitDuration } =
    useMoleculeLoaderAnimation({
      mode: "controlled",
      opacityFactor,
      speedMultiplier: isEntangled ? 4 : 2.5,
      isEntangled,
    });

  if (reduceMotion) {
    return (
      <div
        className={cn("relative shrink-0", className)}
        style={{ width: size, height: size }}
        aria-hidden="true"
      >
        <StaticAtom />
      </div>
    );
  }

  return (
    <div
      className={cn(
        "relative flex items-center justify-center shrink-0 overflow-visible",
        className,
      )}
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      <motion.div
        className="absolute shrink-0"
        style={{ width: size, height: size }}
        animate={{
          x: atomState === "splitting" || atomState === "paired" ? "-50%" : "0%",
        }}
        transition={{
          duration: atomState === "splitting" || atomState === "merging" ? splitDuration : 0,
          ease: [0.25, 0.46, 0.45, 0.94],
        }}
      >
        <motion.div
          className="h-full w-full"
          animate={
            isWobbling
              ? {
                  x: [0, -1.2, 1, -0.8, 1.2, 0],
                  y: [0, 0.5, -0.5, 0.4, -0.4, 0],
                }
              : { x: 0, y: 0 }
          }
          transition={
            isWobbling
              ? { duration: 0.7, repeat: Infinity, repeatType: "loop", ease: "easeInOut" }
              : { duration: 0 }
          }
        >
          <SingleAtomSVG orbitConfigs={orbitConfigs} />
        </motion.div>
      </motion.div>

      <AnimatePresence>
        {isSplit && (
          <motion.div
            className="absolute shrink-0"
            style={{ width: size, height: size }}
            initial={{ x: "0%", opacity: 0 }}
            animate={{
              x: splitAtomOffset(atomState),
              opacity: 1,
            }}
            exit={{ x: "0%", opacity: 0 }}
            transition={{
              duration: atomState === "splitting" || atomState === "merging" ? splitDuration : 0,
              ease: [0.25, 0.46, 0.45, 0.94],
              opacity: { duration: 0.25 },
            }}
          >
            <motion.div
              className="h-full w-full"
              animate={
                isWobbling
                  ? {
                      x: [0, 1.2, -1, 0.8, -1.2, 0],
                      y: [0, -0.5, 0.5, -0.4, 0.4, 0],
                    }
                  : { x: 0, y: 0 }
              }
              transition={
                isWobbling
                  ? {
                      duration: 0.7,
                      repeat: Infinity,
                      repeatType: "loop",
                      ease: "easeInOut",
                      delay: 0.35,
                    }
                  : { duration: 0 }
              }
            >
              <SingleAtomSVG orbitConfigs={orbitConfigs} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
