import { MoleculesList } from "@/components/molecules/molecules-list";

export function MoleculesPage() {
  return (
    <div className="flex flex-col gap-6 max-w-6xl mx-auto">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold tracking-tight">Molecule Library</h1>
      </div>

      <section aria-label="Molecules list">
        <MoleculesList />
      </section>
    </div>
  );
}

export default MoleculesPage;
