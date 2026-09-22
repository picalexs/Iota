import { useSearch } from "@tanstack/react-router";
import { ChevronLeft } from "lucide-react";
import { RunForm } from "@/components/forms/run-form";
import { useSmartBack } from "@/hooks/use-smart-back";

export function RunCreatePage() {
  const goBack = useSmartBack({ to: "/runs" });
  const { molecule_id: initialMoleculeId } = useSearch({ from: "/runs/new" });
  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
      <div className="flex flex-col gap-2">
        <button
          type="button"
          onClick={goBack}
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors w-fit"
          aria-label="Go back"
        >
          <ChevronLeft className="size-4" />
          Back
        </button>
        <h1 className="text-2xl font-bold tracking-tight">New Simulation Run</h1>
      </div>

      <RunForm key={initialMoleculeId ?? "__no-molecule__"} initialMoleculeId={initialMoleculeId} />
    </div>
  );
}

export default RunCreatePage;
