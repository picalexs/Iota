import { useParams } from "@tanstack/react-router";
import { ChevronLeft } from "lucide-react";

import { COMPONENT_INFO, type InfoComponentId } from "@/content/info/components";
import { useSmartBack } from "@/hooks/use-smart-back";

import { InfoDetailContent } from "./info-detail-content";
import { InfoCollectionHero, InfoRelatedTopicsCard, type RelatedTopic } from "./info-reference";

const COMPONENT_RELATED: Record<InfoComponentId, RelatedTopic[]> = {
  ansatzes: [
    {
      label: "VQE",
      description: "Open the algorithm page that uses these circuit templates most directly.",
      to: "/info/algorithms/$algorithmId",
      params: { algorithmId: "vqe" },
    },
    {
      label: "Classical optimizers",
      description: "Ansatz depth and optimizer behavior should usually be tuned together.",
      to: "/info/components/$componentId",
      params: { componentId: "optimizers" },
    },
    {
      label: "Statevector Simulator",
      description:
        "Best place to compare ansatz families before sampling noise enters the picture.",
      to: "/info/backends/$backendId",
      params: { backendId: "statevector" },
    },
  ],
  optimizers: [
    {
      label: "VQE",
      description:
        "The main variational algorithm page shows where optimizer choices surface in results.",
      to: "/info/algorithms/$algorithmId",
      params: { algorithmId: "vqe" },
    },
    {
      label: "Ansatz families",
      description:
        "Optimizer performance depends strongly on the number and shape of circuit parameters.",
      to: "/info/components/$componentId",
      params: { componentId: "ansatzes" },
    },
    {
      label: "Aer Simulator",
      description: "Useful when you want to compare smooth and shot-noisy objectives locally.",
      to: "/info/backends/$backendId",
      params: { backendId: "aer_simulator" },
    },
  ],
  "basis-sets": [
    {
      label: "Reference states",
      description:
        "Reference-state quality only makes sense relative to the chosen orbital problem.",
      to: "/info/components/$componentId",
      params: { componentId: "reference-states" },
    },
    {
      label: "Molecule parameters",
      description: "The parameter glossary keeps the short field-level wording for form usage.",
      to: "/help/parameters",
    },
    {
      label: "VQE",
      description:
        "Open the main algorithm page to see how basis choices eventually show up in the energy workflow.",
      to: "/info/algorithms/$algorithmId",
      params: { algorithmId: "vqe" },
    },
  ],
  "reference-states": [
    {
      label: "QSE",
      description:
        "QSE depends on the reference choice more directly than any other algorithm in the app.",
      to: "/info/algorithms/$algorithmId",
      params: { algorithmId: "qse" },
    },
    {
      label: "Basis sets",
      description:
        "Basis and active-space setup determine what a reference bitstring actually means.",
      to: "/info/components/$componentId",
      params: { componentId: "basis-sets" },
    },
    {
      label: "VQE",
      description:
        "VQE is both a standalone solver and one of the ways this app can build a stronger reference.",
      to: "/info/algorithms/$algorithmId",
      params: { algorithmId: "vqe" },
    },
  ],
};

const EYEBROW_BY_COMPONENT_ID: Record<InfoComponentId, string> = {
  ansatzes: "Component / Ansatz",
  optimizers: "Component / Optimizer",
  "basis-sets": "Component / Basis set",
  "reference-states": "Component / Reference state",
};

export function InfoComponentDetailPage() {
  const { componentId } = useParams({ from: "/info/components/$componentId" });
  const entry = COMPONENT_INFO[componentId as InfoComponentId];
  const goBack = useSmartBack({ to: "/info/components" }, { forceFallback: true });

  if (!entry) {
    return (
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-4 py-8">
        <button
          type="button"
          onClick={goBack}
          className="flex w-fit items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ChevronLeft className="size-4" />
          Back
        </button>
        <p role="alert" className="text-sm text-destructive">
          Component "{componentId}" not found.
        </p>
      </div>
    );
  }

  const eyebrow = EYEBROW_BY_COMPONENT_ID[componentId as InfoComponentId];

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-5 px-4 py-8">
      <button
        type="button"
        onClick={goBack}
        className="flex w-fit items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ChevronLeft className="size-4" />
        Back
      </button>

      <InfoCollectionHero
        collection="components"
        eyebrow={eyebrow}
        title={entry.title}
        description={entry.summary}
      />

      <div className="min-w-0 space-y-6">
        <InfoDetailContent entry={entry} />
        <InfoRelatedTopicsCard topics={COMPONENT_RELATED[componentId as InfoComponentId] ?? []} />
      </div>
    </div>
  );
}

export default InfoComponentDetailPage;
