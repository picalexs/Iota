import { useParams } from "@tanstack/react-router";
import { ChevronLeft } from "lucide-react";
import { useSmartBack } from "@/hooks/use-smart-back";
import { BACKEND_INFO } from "@/content/info/backends";
import type { BackendTarget } from "@/types/run";
import { InfoDetailContent } from "./info-detail-content";
import { InfoCollectionHero, InfoRelatedTopicsCard } from "./info-reference";
import { getBackendRelated } from "./info-reference-data";

export function InfoBackendDetailPage() {
  const { backendId } = useParams({ from: "/info/backends/$backendId" });
  const entry = BACKEND_INFO[backendId as BackendTarget];
  const goBack = useSmartBack({ to: "/info/backends" }, { forceFallback: true });

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
          Backend "{backendId}" not found.
        </p>
      </div>
    );
  }

  const relatedTopics = getBackendRelated(entry.id as BackendTarget);

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
        collection="backends"
        eyebrow={`Backend / ${entry.id}`}
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

export default InfoBackendDetailPage;
