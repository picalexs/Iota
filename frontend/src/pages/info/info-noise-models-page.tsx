import { Link } from "@tanstack/react-router";
import { ChevronLeft } from "lucide-react";
import { NOISE_MODEL_INFO, NOISE_MODEL_IDS } from "@/content/info/noise-models";
import { InfoCollectionHero, InfoEntryCard } from "./info-reference";

export function InfoNoiseModelsPage() {
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-5 px-4 py-8">
      <Link
        to="/info"
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors w-fit"
      >
        <ChevronLeft className="size-4" />
        Reference
      </Link>

      <InfoCollectionHero
        collection="noise-models"
        eyebrow="Noise Models"
        title="Noise model reference"
        description="Review the error models available for local studies and comparisons."
      />

      <div className="grid gap-4">
        {NOISE_MODEL_IDS.map((id) => {
          const entry = NOISE_MODEL_INFO[id];

          return (
            <InfoEntryCard
              key={id}
              collection="noise-models"
              entry={entry}
              code={id}
              to="/info/noise-models/$noiseModelId"
              params={{ noiseModelId: id }}
            />
          );
        })}
      </div>
    </div>
  );
}

export default InfoNoiseModelsPage;
