import { Link } from "@tanstack/react-router";
import { ChevronLeft } from "lucide-react";
import { BACKEND_INFO } from "@/content/info/backends";
import { InfoCollectionHero, InfoEntryCard } from "./info-reference";
import { BACKEND_IDS } from "./info-reference-data";

export function InfoBackendsPage() {
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
        collection="backends"
        eyebrow="Backends"
        title="Execution target reference"
        description="Compare the execution targets available in Quantum Studio."
      />

      <div className="grid gap-4">
        {BACKEND_IDS.map((id) => {
          const entry = BACKEND_INFO[id];

          return (
            <InfoEntryCard
              key={id}
              collection="backends"
              entry={entry}
              code={id}
              to="/info/backends/$backendId"
              params={{ backendId: id }}
            />
          );
        })}
      </div>
    </div>
  );
}

export default InfoBackendsPage;
