import { Link } from "@tanstack/react-router";
import { ChevronLeft } from "lucide-react";
import { ALGORITHM_INFO } from "@/content/info/algorithms";
import { InfoEntryCard, InfoCollectionHero } from "./info-reference";
import { ALGORITHM_IDS } from "./info-reference-data";

export function InfoAlgorithmsPage() {
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
        collection="algorithms"
        eyebrow="Algorithms"
        title="Algorithm reference"
        description="Browse the solver catalog and open the method you want to read about."
      />

      <div className="grid gap-4 sm:grid-cols-2">
        {ALGORITHM_IDS.map((id) => {
          const entry = ALGORITHM_INFO[id];

          return (
            <InfoEntryCard
              key={id}
              collection="algorithms"
              entry={entry}
              code={id}
              to="/info/algorithms/$algorithmId"
              params={{ algorithmId: id }}
            />
          );
        })}
      </div>
    </div>
  );
}

export default InfoAlgorithmsPage;
