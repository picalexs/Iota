import { useMemo, useRef } from "react";
import { useTheme } from "@/context/theme-context";
import { useViewerPreferences } from "@/context/viewer-preferences-context";
import {
  atomsToXyz,
  calculateBonds,
  calculateFormula,
  calculateMolecularWeight,
} from "@/lib/chemistry-utils";
import type { AtomSchema, MoleculeResponse } from "@/types/run";
import type { MoleculeViewer3DRef } from "@/components/molecules/molecule-viewer-3d";

function isSafeStemCharacter(char: string): boolean {
  const code = char.codePointAt(0);
  if (code == null) return false;

  return (
    (code >= 48 && code <= 57) ||
    (code >= 65 && code <= 90) ||
    (code >= 97 && code <= 122) ||
    char === "_" ||
    char === "-"
  );
}

function moleculeFileStem(moleculeName: string): string {
  let stem = "";
  let pendingSeparator = false;

  for (const char of moleculeName.trim()) {
    if (isSafeStemCharacter(char)) {
      if (pendingSeparator && stem.length > 0) {
        stem += "-";
      }
      stem += char.toLowerCase();
      pendingSeparator = false;
    } else if (stem.length > 0) {
      pendingSeparator = true;
    }
  }

  return stem || "molecule";
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function downloadXyz(moleculeName: string, atoms: AtomSchema[]) {
  const xyz = atomsToXyz(atoms);
  const blob = new Blob([xyz], { type: "text/plain;charset=utf-8" });
  downloadBlob(blob, `${moleculeFileStem(moleculeName)}.xyz`);
}

export function downloadViewerImage(
  moleculeName: string,
  viewMode: "2d" | "3d",
  container: HTMLElement | null,
) {
  if (container == null) return;

  if (viewMode === "2d") {
    const svg = container.querySelector("svg");
    if (svg == null) return;
    const source = new XMLSerializer().serializeToString(svg);
    const blob = new Blob([source], { type: "image/svg+xml;charset=utf-8" });
    downloadBlob(blob, `${moleculeFileStem(moleculeName)}-2d.svg`);
    return;
  }

  const canvas = container.querySelector("canvas");
  canvas?.toBlob((blob) => {
    if (blob == null) return;
    downloadBlob(blob, `${moleculeFileStem(moleculeName)}-3d.png`);
  }, "image/png");
}

export function useMoleculeViewer(molecule: MoleculeResponse | null) {
  const { resolvedTheme } = useTheme();
  const viewer3DRef = useRef<MoleculeViewer3DRef>(null);
  const preferencesApi = useViewerPreferences();

  const chemistry = useMemo(() => {
    if (!molecule) {
      return { formula: "", mw: 0, bondCount: 0 };
    }

    return {
      formula: calculateFormula(molecule.atoms),
      mw: calculateMolecularWeight(molecule.atoms),
      bondCount: calculateBonds(molecule.atoms).length,
    };
  }, [molecule]);

  return {
    ...preferencesApi,
    ...chemistry,
    isDark: resolvedTheme === "dark",
    viewer3DRef,
  };
}
