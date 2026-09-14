import { RunsList } from "@/features/runs/RunsList";

export function RunsListPage() {
  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto">
      <div className="flex flex-col gap-1 min-w-0">
        <h1 className="text-2xl font-bold tracking-tight">Quantum Runs</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Monitor and manage your quantum algorithm simulations
        </p>
      </div>

      <section aria-label="Runs list">
        <RunsList />
      </section>
    </div>
  );
}

export default RunsListPage;
