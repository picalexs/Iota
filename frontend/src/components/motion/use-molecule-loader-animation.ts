import { useEffect, useMemo, useState } from "react";
import { useReducedMotion } from "framer-motion";

type AtomState = "single" | "splitting" | "paired" | "merging";

export type OrbitConfig = {
  readonly angle: number;
  readonly phase: number;
  readonly angularSpeed: number;
  readonly rx: number;
  readonly ryPhase: number;
  readonly opacity: number;
};

interface UseMoleculeLoaderAnimationOptions {
  readonly mode: "auto" | "controlled";
  readonly opacityFactor: number;
  readonly speedMultiplier: number;
  readonly isEntangled?: boolean;
}

interface MoleculeLoaderAnimation {
  readonly reduceMotion: boolean;
  readonly atomState: AtomState;
  readonly orbitConfigs: OrbitConfig[];
  readonly bridgeOrbit: OrbitConfig;
  readonly isSplit: boolean;
  readonly isWobbling: boolean;
  readonly splitDuration: number;
}

type MoleculeLoaderMode = UseMoleculeLoaderAnimationOptions["mode"];

const AUTO_DURATIONS: Record<AtomState, number> = {
  single: 8000,
  splitting: 1500,
  paired: 4000,
  merging: 1500,
};

const AUTO_NEXT: Record<AtomState, AtomState> = {
  single: "splitting",
  splitting: "paired",
  paired: "merging",
  merging: "single",
};

export function buildOrbitConfigs(speedMultiplier = 1, opacityFactor = 1) {
  return [0, 60, -60].map((angle, index) => {
    const baseDuration = 7 + index * 1.5;
    const durationSeconds = baseDuration / speedMultiplier;
    return {
      angle,
      phase: (index * Math.PI * 2) / 3,
      angularSpeed: (Math.PI * 2) / durationSeconds,
      rx: 35,
      // Each ring gets a different phase so they don't all compress at the same time.
      ryPhase: (index * Math.PI * 2) / 3 + Math.PI / 4,
      opacity: (index === 0 ? 0.42 : 0.3) * opacityFactor,
    };
  });
}

function resolveDisplayAtomState(
  mode: MoleculeLoaderMode,
  isEntangled: boolean,
  atomState: AtomState,
): AtomState {
  if (mode !== "controlled") {
    return atomState;
  }
  if (isEntangled) {
    return atomState === "single" ? "splitting" : atomState;
  }
  if (atomState === "paired" || atomState === "splitting") {
    return "merging";
  }
  return atomState;
}

export function useMoleculeLoaderAnimation({
  mode,
  opacityFactor,
  speedMultiplier,
  isEntangled = false,
}: UseMoleculeLoaderAnimationOptions): MoleculeLoaderAnimation {
  const reduceMotion = useReducedMotion() ?? false;
  const orbitConfigs = useMemo(
    () => buildOrbitConfigs(speedMultiplier, opacityFactor),
    [opacityFactor, speedMultiplier],
  );
  const bridgeOrbit = orbitConfigs[0] ?? {
    angularSpeed: (Math.PI * 2) / 7,
    phase: 0,
    ryPhase: 0,
    angle: 0,
    rx: 35,
    opacity: 0.42,
  };

  const [atomState, setAtomState] = useState<AtomState>("single");
  const displayAtomState = resolveDisplayAtomState(mode, isEntangled, atomState);

  useEffect(() => {
    if (reduceMotion || mode !== "auto") {
      return;
    }

    const timer = globalThis.setTimeout(() => {
      setAtomState((prev) => AUTO_NEXT[prev]);
    }, AUTO_DURATIONS[atomState]);

    return () => globalThis.clearTimeout(timer);
  }, [atomState, mode, reduceMotion]);

  useEffect(() => {
    if (reduceMotion || mode !== "controlled") {
      return;
    }

    if (displayAtomState === "splitting") {
      const timer = globalThis.setTimeout(() => setAtomState("paired"), 550);
      return () => globalThis.clearTimeout(timer);
    }

    if (displayAtomState === "merging") {
      const timer = globalThis.setTimeout(() => setAtomState("single"), 550);
      return () => globalThis.clearTimeout(timer);
    }
  }, [displayAtomState, mode, reduceMotion]);

  return {
    reduceMotion,
    atomState: displayAtomState,
    orbitConfigs,
    bridgeOrbit,
    isSplit:
      displayAtomState === "splitting" ||
      displayAtomState === "paired" ||
      displayAtomState === "merging",
    isWobbling: displayAtomState === "splitting" || displayAtomState === "paired",
    splitDuration: mode === "controlled" ? 0.55 : 1.5,
  };
}
