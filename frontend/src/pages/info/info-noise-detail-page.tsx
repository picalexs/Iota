import { useParams } from "@tanstack/react-router";
import { ChevronLeft } from "lucide-react";
import { useSmartBack } from "@/hooks/use-smart-back";
import { NOISE_MODEL_INFO } from "@/content/info/noise-models";
import type { NoiseModelId } from "@/content/info/noise-models";
import { InfoDetailContent } from "./info-detail-content";
import { InfoCollectionHero, InfoRelatedTopicsCard } from "./info-reference";
import { getNoiseRelated } from "./info-reference-data";

export function InfoNoiseDetailPage() {
  const { noiseModelId } = useParams({ from: "/info/noise-models/$noiseModelId" });
  const entry = NOISE_MODEL_INFO[noiseModelId as NoiseModelId];
  const goBack = useSmartBack({ to: "/info/noise-models" }, { forceFallback: true });

  if (!entry) {
    return (
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-4 py-8">
        <button
          type="button"
          onClick={goBack}
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors w-fit"
        >
          <ChevronLeft className="size-4" />
          Back
        </button>
        <p role="alert" className="text-destructive text-sm">
          Noise model "{noiseModelId}" not found.
        </p>
      </div>
    );
  }

  const relatedTopics = getNoiseRelated(entry.id as NoiseModelId);

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-5 px-4 py-8">
      <button
        type="button"
        onClick={goBack}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors w-fit"
      >
        <ChevronLeft className="size-4" />
        Back
      </button>

      <InfoCollectionHero
        collection="noise-models"
        eyebrow={`Noise Model / ${entry.id}`}
        title={entry.title}
        description={entry.summary}
      />

      <div className="min-w-0 space-y-6">
        <InfoDetailContent entry={entry} />
        <InfoRelatedTopicsCard topics={relatedTopics} />
      </div>
    </div>
  );
}

export default InfoNoiseDetailPage;
