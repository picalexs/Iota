import { Badge } from "@/components/ui/badge";
import type React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { formatConfigRows } from "@/lib/run-config-display";
import type { RunResponse } from "@/types/run";

interface RunSettingsCardProps {
  run: RunResponse;
}

export function RunSettingsCard({ run }: RunSettingsCardProps) {
  const configRows = formatConfigRows(run);
  const moleculeRows = configRows.filter((row) => row.group === "Molecule");
  const algorithmRows = configRows.filter((row) => row.group === "Algorithm");
  const backendRows = configRows.filter((row) => row.group === "Backend");
  const optionsRows = configRows.filter((row) => row.group === "Options");
  const hasSettingsRows =
    moleculeRows.length > 0 ||
    algorithmRows.length > 0 ||
    backendRows.length > 0 ||
    optionsRows.length > 0;

  if (!hasSettingsRows) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Run Settings</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <dl className="grid gap-3">
          {moleculeRows.map((row) => (
            <SettingsRow key={row.label} label={row.label} value={row.value} />
          ))}
          {moleculeRows.length > 0 && algorithmRows.length > 0 && <SettingsSeparator />}
          {algorithmRows.map((row) => (
            <SettingsRow key={row.label} label={row.label} value={row.value} />
          ))}
          {(moleculeRows.length > 0 || algorithmRows.length > 0) && backendRows.length > 0 && (
            <SettingsSeparator />
          )}
          {backendRows.map((row) => (
            <SettingsRow key={row.label} label={row.label} value={row.value} />
          ))}
          {(moleculeRows.length > 0 || algorithmRows.length > 0 || backendRows.length > 0) &&
            optionsRows.length > 0 && <SettingsSeparator />}
          {optionsRows.length > 0 && (
            <div className="col-span-full">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Options
              </p>
            </div>
          )}
          {optionsRows.map((row) => (
            <SettingsRow key={row.label} label={row.label} value={row.value} />
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}

interface SettingsRowProps {
  label: string;
  value: React.ReactNode;
}

function SettingsRow({ label, value }: SettingsRowProps) {
  return (
    <div className="grid gap-1 sm:grid-cols-[minmax(10rem,14rem)_minmax(0,1fr)] sm:gap-4">
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="text-sm">{value}</dd>
    </div>
  );
}

function SettingsSeparator() {
  return (
    <div className="col-span-full">
      <Separator />
    </div>
  );
}

interface RunDependencyVersionsCardProps {
  run: RunResponse;
}

export function RunDependencyVersionsCard({ run }: RunDependencyVersionsCardProps) {
  if (!run.versions || Object.keys(run.versions).length === 0) {
    return null;
  }

  return (
    <Card className="md:col-span-2">
      <CardHeader>
        <CardTitle className="text-sm">Dependency Versions</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2">
          {Object.entries(run.versions).map(([pkg, version]) => (
            <Badge key={pkg} variant="secondary" className="font-mono text-xs">
              {pkg}=={version}
            </Badge>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
