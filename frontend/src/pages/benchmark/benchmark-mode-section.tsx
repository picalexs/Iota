import { SlidersHorizontal } from "lucide-react";
import { SelectableCard } from "@/components/ui/selectable-card";
import type { BenchmarkVariantMode } from "./benchmark-variants";

export function BenchmarkModeSection({
  benchmarkMode,
  workspaceLocked,
  onBenchmarkModeChange,
}: Readonly<{
  benchmarkMode: BenchmarkVariantMode;
  workspaceLocked: boolean;
  onBenchmarkModeChange: (mode: BenchmarkVariantMode) => void;
}>) {
  return (
    <section className="space-y-3 rounded-xl border border-border/80 bg-card p-4">
      <div className="space-y-1">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <SlidersHorizontal className="h-4 w-4 text-muted-foreground" />
          Benchmark mode
        </div>
        <p className="text-xs text-muted-foreground">
          Keep the current guided benchmark flow, or switch to row-level advanced controls with
          duplicate algorithm rows.
        </p>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <SelectableCard
          selected={benchmarkMode === "simple"}
          disabled={workspaceLocked}
          onClick={() => onBenchmarkModeChange("simple")}
          className="min-h-[6rem] p-4"
        >
          <div className="space-y-1">
            <p className="text-sm font-semibold">Simple benchmark</p>
            <p className="text-xs text-muted-foreground">
              One guided row per selected algorithm using the shared easy presets.
            </p>
          </div>
        </SelectableCard>
        <SelectableCard
          selected={benchmarkMode === "advanced"}
          disabled={workspaceLocked}
          onClick={() => onBenchmarkModeChange("advanced")}
          className="min-h-[6rem] p-4"
        >
          <div className="space-y-1">
            <p className="text-sm font-semibold">Advanced benchmark</p>
            <p className="text-xs text-muted-foreground">
              Add multiple rows for the same algorithm and tune each one like the manual run form.
            </p>
          </div>
        </SelectableCard>
      </div>
    </section>
  );
}
