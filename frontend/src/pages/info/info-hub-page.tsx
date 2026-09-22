import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { InfoCollectionCard, InfoCollectionHero } from "./info-reference";
import { INFO_COLLECTIONS } from "./info-reference-data";

export function InfoHubPage() {
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-8">
      <InfoCollectionHero
        eyebrow="Reference"
        title="Reference"
        description="Browse the algorithms, components, backends, and noise models used by the application."
        actions={
          <Button asChild variant="outline" size="sm">
            <Link to="/help/parameters">Parameter glossary</Link>
          </Button>
        }
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {INFO_COLLECTIONS.map((item) => (
          <InfoCollectionCard key={item.key} item={item} />
        ))}
      </div>
    </div>
  );
}

export default InfoHubPage;
