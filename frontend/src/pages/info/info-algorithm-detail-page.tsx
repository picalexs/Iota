import { useParams } from "@tanstack/react-router";
import { ChevronLeft } from "lucide-react";
import { useSmartBack } from "@/hooks/use-smart-back";
import { ALGORITHM_INFO } from "@/content/info/algorithms";
import type { RunAlgorithm } from "@/types/run";
import { InfoDetailContent } from "./info-detail-content";
import { InfoCollectionHero, InfoRelatedTopicsCard } from "./info-reference";
import { getAlgorithmRelated } from "./info-reference-data";

export function InfoAlgorithmDetailPage() {
  const { algorithmId } = useParams({ from: "/info/algorithms/$algorithmId" });
  const entry = ALGORITHM_INFO[algorithmId as RunAlgorithm];
  const goBack = useSmartBack({ to: "/info/algorithms" }, { forceFallback: true });

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
          Algorithm "{algorithmId}" not found.
        </p>
      </div>
    );
  }

  const relatedTopics = getAlgorithmRelated(entry.id as RunAlgorithm);

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
        collection="algorithms"
        eyebrow={`Algorithm / ${entry.id.toUpperCase()}`}
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

export default InfoAlgorithmDetailPage;
