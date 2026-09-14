import { Link } from "@tanstack/react-router";
import { ChevronLeft } from "lucide-react";

import { COMPONENT_IDS, COMPONENT_INFO, type InfoComponentId } from "@/content/info/components";

import { InfoCollectionHero, InfoEntryCard } from "./info-reference";

const CODE_BY_COMPONENT_ID: Record<InfoComponentId, string> = {
  ansatzes: "ANSATZ",
  optimizers: "OPT",
  "basis-sets": "BASIS",
  "reference-states": "REF",
};

export function InfoComponentsPage() {
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-5 px-4 py-8">
      <Link
        to="/info"
        className="flex w-fit items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ChevronLeft className="size-4" />
        Reference
      </Link>

      <InfoCollectionHero
        collection="components"
        eyebrow="Components"
        title="Component reference"
        description="Open the pages that explain what your chemistry and variational controls are actually changing."
      />

      <div className="grid gap-4 sm:grid-cols-2">
        {COMPONENT_IDS.map((id) => {
          const entry = COMPONENT_INFO[id];
          const code = CODE_BY_COMPONENT_ID[id];

          return (
            <InfoEntryCard
              key={id}
              collection="components"
              entry={entry}
              code={code}
              to="/info/components/$componentId"
              params={{ componentId: id }}
            />
          );
        })}
      </div>
    </div>
  );
}

export default InfoComponentsPage;
