import { Link } from "@tanstack/react-router";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { MoleculeResponse, RunResponse } from "@/types/run";

function formatEnumValue(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

interface RunOverviewCardProps {
  run: RunResponse;
  molecule: MoleculeResponse | null;
}

export function RunOverviewCard({ run, molecule }: RunOverviewCardProps) {
  const configJson = run.config_json as Record<string, unknown>;
  const algorithmValue =
    run.algorithm ?? (typeof configJson.algorithm === "string" ? configJson.algorithm : null);
  const backendValue =
    run.backend_target ??
    (typeof configJson.backend_target === "string" ? configJson.backend_target : null);
  const overviewRows = [
    {
      label: "Molecule",
      value:
        run.molecule_id && molecule ? (
          <Link
            to="/molecules/$moleculeId"
            params={{ moleculeId: run.molecule_id }}
            className="text-primary font-medium underline-offset-2 hover:underline"
          >
            {molecule.name}
          </Link>
        ) : (
          <span className="font-medium">{molecule?.name ?? "—"}</span>
        ),
    },
    {
      label: "Run ID",
      value: <code className="font-mono text-xs break-all">{run.id}</code>,
    },
    algorithmValue
      ? {
          label: "Algorithm",
          value: (
            <Link
              to="/info/algorithms/$algorithmId"
              params={{ algorithmId: String(algorithmValue) }}
              className="text-primary font-medium underline-offset-2 hover:underline"
            >
              {String(algorithmValue).toUpperCase()}
            </Link>
          ),
        }
      : null,
    backendValue
      ? {
          label: "Backend",
          value: (
            <Link
              to="/info/backends/$backendId"
              params={{ backendId: String(backendValue) }}
              className="text-primary font-medium underline-offset-2 hover:underline"
            >
              {formatEnumValue(String(backendValue))}
            </Link>
          ),
        }
      : null,
    {
      label: "Created",
      value: <span>{new Date(run.created_at).toLocaleString()}</span>,
    },
    {
      label: "Updated",
      value: <span>{new Date(run.updated_at).toLocaleString()}</span>,
    },
    run.ibm_job_id
      ? {
          label: "IBM Job",
          value: <code className="font-mono text-xs break-all">{run.ibm_job_id}</code>,
        }
      : null,
  ].filter((row): row is NonNullable<typeof row> => row !== null);

  return (
    <Card className="md:col-span-2">
      <CardHeader>
        <CardTitle className="text-sm">Overview</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {overviewRows.map((row) => (
          <div key={row.label} className="rounded-lg border border-border/80 bg-muted/30 px-4 py-3">
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {row.label}
            </div>
            <div className="mt-1 text-sm">{row.value}</div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
