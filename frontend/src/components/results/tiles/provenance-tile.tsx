import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { DashboardTile } from "@/components/results/dashboard-tile";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { RunResponse } from "@/types/run";

interface ProvenanceTileProps {
  readonly run: RunResponse;
  readonly editMode?: boolean;
}

function safePrimitiveLabel(value: unknown): string | null {
  return ["string", "number", "boolean"].includes(typeof value) ? String(value) : null;
}

function buildBibTeX(run: RunResponse): string {
  const year = new Date(run.created_at).getFullYear();
  return `@misc{vqe_run_${run.id.slice(0, 8)},
  title  = {Quantum Studio Run (${run.algorithm?.toUpperCase() ?? "Unknown"})},
  year   = {${year}},
  note   = {Run ID: ${run.id}, Backend: ${run.backend_target ?? "unknown"}},
}`;
}

export function ProvenanceTile({ run, editMode }: ProvenanceTileProps) {
  const [copied, setCopied] = useState(false);
  const versions = run.versions ?? {};
  const basisSet = safePrimitiveLabel(run.config_json?.["basis_set"]);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(buildBibTeX(run));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <DashboardTile
      title="Provenance"
      helpText="Algorithm, software versions, and a BibTeX citation snippet for reproducibility."
      editMode={editMode}
    >
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-1.5">
          {run.algorithm && (
            <Badge variant="secondary" className="uppercase">
              {run.algorithm}
            </Badge>
          )}
          {run.mode && <Badge variant="outline">{run.mode}</Badge>}
          {run.backend_target && <Badge variant="outline">{run.backend_target}</Badge>}
          {basisSet && <Badge variant="outline">{basisSet}</Badge>}
        </div>

        {Object.keys(versions).length > 0 && (
          <div>
            <p className="mb-1 text-xs font-medium text-muted-foreground">Versions</p>
            <div className="flex flex-wrap gap-1">
              {Object.entries(versions).map(([pkg, ver]) => (
                <span
                  key={pkg}
                  className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground"
                >
                  {pkg}={safePrimitiveLabel(ver) ?? "-"}
                </span>
              ))}
            </div>
          </div>
        )}

        <Button
          variant="outline"
          size="sm"
          className="w-fit gap-1.5"
          onClick={handleCopy}
          aria-label="Copy BibTeX citation"
        >
          {copied ? <Check className="size-3.5 text-success" /> : <Copy className="size-3.5" />}
          Copy BibTeX
        </Button>
      </div>
    </DashboardTile>
  );
}
