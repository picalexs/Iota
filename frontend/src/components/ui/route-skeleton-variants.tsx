import { Skeleton } from "./skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "./card";
import { TableSkeletonRow } from "./loading-skeleton-blocks";
import { MoleculeLoader } from "@/components/motion/molecule-loader";
import { MoleculeDetailLoadingSkeleton } from "@/components/molecules/molecule-detail-loading";
import { RunDetailLoadingSkeleton } from "@/components/runs/run-detail-loading";

function placeholderIds(count: number, prefix: string): string[] {
  return Array.from({ length: count }, (_, index) => `${prefix}-${index}`);
}

// Route fallbacks announce loading state to assistive technologies.
function RouteSkeleton({
  children,
  ariaLabel,
}: Readonly<{ children: React.ReactNode; ariaLabel: string }>) {
  return (
    <output className="block" aria-busy={true} aria-label={ariaLabel}>
      {children}
    </output>
  );
}

function RunFormSectionSkeleton({
  titleWidth,
  descriptionWidth,
  children,
}: Readonly<{
  titleWidth: string;
  descriptionWidth: string;
  children: React.ReactNode;
}>) {
  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-start gap-4">
        <Skeleton className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full" />
        <div className="flex flex-col gap-2">
          <Skeleton className={`h-5 ${titleWidth}`} />
          <Skeleton className={`h-4 ${descriptionWidth}`} />
        </div>
      </div>
      <div className="h-px w-full bg-border/70" />
      <div className="flex flex-col gap-4 pl-12 pr-3 sm:pr-12">{children}</div>
    </div>
  );
}

export function HomePageSkeleton() {
  return (
    <RouteSkeleton ariaLabel="Loading home page">
      <div className="flex flex-col gap-6 max-w-6xl mx-auto">
        <div className="flex flex-col items-center gap-4 text-center">
          <MoleculeLoader size="sm" />
          <div className="flex w-full max-w-xl flex-col gap-2">
            <Skeleton className="h-8 w-2/3 mx-auto" />
            <Skeleton className="h-4 w-1/2 mx-auto" />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          {placeholderIds(3, "home-stat").map((id) => (
            <div key={id} className="flex flex-col gap-3">
              <Skeleton className="h-20 w-full rounded-lg" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {placeholderIds(3, "home-feature").map((id) => (
            <div key={id} className="flex flex-col gap-3 p-4 border rounded-lg">
              <Skeleton className="size-6" />
              <Skeleton className="h-5 w-2/3" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-8 w-1/3 mt-2" />
            </div>
          ))}
        </div>
      </div>
    </RouteSkeleton>
  );
}

export function MoleculesListSkeleton() {
  return (
    <RouteSkeleton ariaLabel="Loading molecule library">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <div className="flex flex-col gap-1">
          <Skeleton className="h-8 w-56" />
        </div>

        <section aria-label="Molecules list">
          <Card aria-busy={true}>
            <CardHeader className="flex flex-row items-center justify-between gap-4">
              <CardTitle className="text-base font-semibold">
                <Skeleton className="h-5 w-32" />
              </CardTitle>
              <Skeleton className="h-9 w-36 shrink-0" />
            </CardHeader>

            <div className="flex flex-col gap-3 px-4 pb-3 pt-4">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <Skeleton className="h-10 w-full sm:max-w-md" />
              </div>
              <Skeleton className="h-4 w-32" />
            </div>

            <CardContent className="p-0">
              <table aria-label="Molecules library" className="w-full border-t">
                <thead>
                  <tr className="grid grid-cols-[minmax(0,2fr)_minmax(0,0.9fr)_64px] items-center gap-4 border-b bg-muted/40 px-4 py-2">
                    <th scope="col" className="font-normal">
                      <Skeleton className="h-4 w-16" />
                    </th>
                    <th scope="col" className="font-normal">
                      <Skeleton className="ml-auto h-4 w-16" />
                    </th>
                    <th scope="col" className="font-normal">
                      <Skeleton className="ml-auto h-4 w-12" />
                    </th>
                  </tr>
                </thead>
                <tbody aria-label="Loading molecules">
                  <TableSkeletonRow
                    gridClassName="grid-cols-[minmax(0,2fr)_minmax(0,0.9fr)_64px]"
                    cellWidths={["w-32", "w-16", "w-8"]}
                    rightAlignedIndices={[1, 2]}
                  />
                  <TableSkeletonRow
                    gridClassName="grid-cols-[minmax(0,2fr)_minmax(0,0.9fr)_64px]"
                    cellWidths={["w-24", "w-20", "w-10"]}
                    rightAlignedIndices={[1, 2]}
                  />
                  <TableSkeletonRow
                    gridClassName="grid-cols-[minmax(0,2fr)_minmax(0,0.9fr)_64px]"
                    cellWidths={["w-36", "w-14", "w-8"]}
                    rightAlignedIndices={[1, 2]}
                  />
                </tbody>
              </table>
              <div className="flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3">
                <Skeleton className="h-4 w-28" />
                <div className="flex items-center gap-2">
                  <Skeleton className="h-8 w-24" />
                  <Skeleton className="h-8 w-20" />
                  <Skeleton className="h-8 w-20" />
                </div>
              </div>
            </CardContent>
          </Card>
        </section>
      </div>
    </RouteSkeleton>
  );
}

export function MoleculeDetailSkeleton() {
  return (
    <RouteSkeleton ariaLabel="Loading molecule details">
      <div className="w-full max-w-7xl mx-auto px-2 sm:px-4 lg:px-6 overflow-x-hidden">
        <div className="flex flex-col gap-6">
          <Skeleton className="h-4 w-16" />
          <MoleculeDetailLoadingSkeleton />
        </div>
      </div>
    </RouteSkeleton>
  );
}

export function RunsListSkeleton() {
  return (
    <RouteSkeleton ariaLabel="Loading runs">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <div className="flex items-center justify-between gap-6">
          <div className="flex min-w-0 flex-col gap-1">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="mt-1 h-4 w-72 max-w-full" />
          </div>
          <Skeleton className="h-10 w-28 shrink-0" />
        </div>

        <section aria-label="Runs list">
          <Card aria-busy={true}>
            <CardHeader>
              <CardTitle className="text-base font-semibold">
                <Skeleton className="h-5 w-20" />
              </CardTitle>
            </CardHeader>
            <CardContent className="px-0 pb-0">
              <div className="flex flex-wrap items-center gap-2 border-b px-4 py-3">
                <Skeleton className="h-8 w-20" />
                <Skeleton className="h-8 w-20" />
                <Skeleton className="h-8 w-24" />
                <Skeleton className="h-7 w-24" />
                <Skeleton className="h-7 w-28" />
                <Skeleton className="h-7 w-20" />
              </div>

              <table aria-label="Quantum runs" className="w-full">
                <thead>
                  <tr className="grid grid-cols-[9rem_minmax(0,1fr)_7rem_5rem_7rem_9rem_8rem_minmax(0,12rem)] items-center gap-4 border-b bg-muted/40 px-4 py-2">
                    <th scope="col" className="font-normal">
                      <Skeleton className="h-4 w-12" />
                    </th>
                    <th scope="col" className="font-normal">
                      <Skeleton className="h-4 w-16" />
                    </th>
                    <th scope="col" className="font-normal">
                      <Skeleton className="h-4 w-14" />
                    </th>
                    <th scope="col" className="font-normal">
                      <Skeleton className="mx-auto size-4 rounded-full" />
                    </th>
                    <th scope="col" className="font-normal">
                      <Skeleton className="h-4 w-14" />
                    </th>
                    <th scope="col" className="font-normal">
                      <Skeleton className="h-4 w-16" />
                    </th>
                    <th scope="col" className="font-normal">
                      <Skeleton className="h-4 w-16" />
                    </th>
                    <th scope="col" className="font-normal">
                      <Skeleton className="h-4 w-16" />
                    </th>
                  </tr>
                </thead>
                <tbody aria-label="Loading runs">
                  <TableSkeletonRow
                    gridClassName="grid-cols-[9rem_minmax(0,1fr)_7rem_5rem_7rem_9rem_8rem_minmax(0,12rem)]"
                    cellWidths={["w-24", "w-20", "w-14", "w-4", "w-14", "w-20", "w-16", "w-32"]}
                    centeredIndices={[3]}
                  />
                  <TableSkeletonRow
                    gridClassName="grid-cols-[9rem_minmax(0,1fr)_7rem_5rem_7rem_9rem_8rem_minmax(0,12rem)]"
                    cellWidths={["w-20", "w-28", "w-12", "w-4", "w-16", "w-24", "w-16", "w-28"]}
                    centeredIndices={[3]}
                  />
                  <TableSkeletonRow
                    gridClassName="grid-cols-[9rem_minmax(0,1fr)_7rem_5rem_7rem_9rem_8rem_minmax(0,12rem)]"
                    cellWidths={["w-24", "w-24", "w-16", "w-4", "w-20", "w-20", "w-24", "w-24"]}
                    centeredIndices={[3]}
                  />
                </tbody>
              </table>

              <div className="flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3">
                <Skeleton className="h-4 w-28" />
                <div className="flex items-center gap-2">
                  <Skeleton className="h-8 w-24" />
                  <Skeleton className="h-4 w-12" />
                  <Skeleton className="h-8 w-20" />
                </div>
              </div>
            </CardContent>
          </Card>
        </section>
      </div>
    </RouteSkeleton>
  );
}

export function RunDetailSkeleton() {
  return (
    <RouteSkeleton ariaLabel="Loading run details">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <Skeleton className="h-4 w-16" />
        <RunDetailLoadingSkeleton />
      </div>
    </RouteSkeleton>
  );
}

export function BenchmarkRunsSkeleton() {
  return (
    <RouteSkeleton ariaLabel="Loading benchmark runs">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-8">
        <div className="flex items-center justify-between gap-6">
          <div className="flex min-w-0 flex-col gap-1">
            <Skeleton className="h-8 w-52 max-w-full" />
            <Skeleton className="h-4 w-80 max-w-full" />
          </div>
          <Skeleton className="h-10 w-36 shrink-0 rounded-lg" />
        </div>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-3">
            <CardTitle className="text-base font-semibold">
              <Skeleton className="h-5 w-40" />
            </CardTitle>
            <Skeleton className="h-6 w-10 rounded-full" />
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-hidden border-t">
              <div className="grid grid-cols-[minmax(0,1.7fr)_6rem_7rem_9rem_7rem_5rem] gap-4 bg-muted/40 px-4 py-3">
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-12" />
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-14" />
                <Skeleton className="h-4 w-12" />
                <Skeleton className="ml-auto h-4 w-14" />
              </div>

              {placeholderIds(3, "benchmark-runs-row").map((id) => (
                <div
                  key={id}
                  className="grid grid-cols-[minmax(0,1.7fr)_6rem_7rem_9rem_7rem_5rem] gap-4 border-t px-4 py-4"
                >
                  <div className="min-w-0 space-y-2">
                    <Skeleton className="h-4 w-44 max-w-full" />
                    <Skeleton className="h-4 w-60 max-w-full" />
                  </div>
                  <Skeleton className="h-4 w-10" />
                  <Skeleton className="h-4 w-12" />
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-6 w-16 rounded-full" />
                  <div className="flex justify-end">
                    <Skeleton className="size-8 rounded-md" />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </RouteSkeleton>
  );
}

export function BenchmarkPageSkeleton() {
  return (
    <RouteSkeleton ariaLabel="Loading benchmark workspace">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-8">
        <div className="flex flex-col gap-3">
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-9 w-64 max-w-full" />
          <Skeleton className="h-4 w-full max-w-3xl" />
          <Skeleton className="h-4 w-2/3 max-w-2xl" />
        </div>

        <section className="rounded-2xl border bg-card p-5">
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.8fr)]">
            <div className="space-y-5">
              <div className="space-y-3">
                <Skeleton className="h-4 w-28" />
                <div className="flex flex-wrap gap-2">
                  <Skeleton className="h-9 w-28 rounded-full" />
                  <Skeleton className="h-9 w-32 rounded-full" />
                  <Skeleton className="h-9 w-28 rounded-full" />
                </div>
              </div>

              <div className="space-y-3">
                <Skeleton className="h-4 w-24" />
                <div className="grid gap-2 sm:grid-cols-3">
                  <Skeleton className="h-9 w-full" />
                  <Skeleton className="h-9 w-full" />
                  <Skeleton className="h-9 w-full" />
                </div>
              </div>

              <div className="space-y-3">
                <Skeleton className="h-4 w-36" />
                <Skeleton className="h-11 w-full" />
              </div>
            </div>

            <div className="flex flex-col justify-between gap-4 rounded-xl border border-border/70 bg-muted/20 p-4">
              <div className="space-y-3">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-20 w-full rounded-xl" />
              </div>
              <div className="space-y-3">
                <div className="grid gap-2 sm:grid-cols-2">
                  <Skeleton className="h-9 w-full" />
                  <Skeleton className="h-9 w-full" />
                </div>
                <div className="grid gap-2 sm:grid-cols-3">
                  <Skeleton className="h-9 w-full" />
                  <Skeleton className="h-9 w-full" />
                  <Skeleton className="h-9 w-full" />
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-xl border border-border/80 bg-card p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap gap-2">
              <Skeleton className="h-8 w-20 rounded-full" />
              <Skeleton className="h-8 w-24 rounded-full" />
              <Skeleton className="h-8 w-28 rounded-full" />
              <Skeleton className="h-8 w-24 rounded-full" />
            </div>
            <div className="flex flex-wrap gap-2">
              <Skeleton className="h-8 w-28 rounded-full" />
              <Skeleton className="h-8 w-32 rounded-full" />
              <Skeleton className="h-8 w-32 rounded-full" />
            </div>
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-2">
          <div className="rounded-2xl border bg-card p-5">
            <div className="flex items-center justify-between gap-4">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-8 w-24" />
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <Skeleton className="h-28 w-full rounded-xl" />
              <Skeleton className="h-28 w-full rounded-xl" />
              <Skeleton className="h-28 w-full rounded-xl" />
            </div>
            <Skeleton className="mt-4 h-56 w-full rounded-xl" />
          </div>

          <div className="rounded-2xl border bg-card p-5">
            <div className="flex items-center justify-between gap-4">
              <Skeleton className="h-5 w-36" />
              <Skeleton className="h-8 w-24" />
            </div>
            <div className="mt-5 space-y-4">
              <Skeleton className="h-10 w-full rounded-xl" />
              <Skeleton className="h-10 w-full rounded-xl" />
              <Skeleton className="h-10 w-full rounded-xl" />
              <Skeleton className="h-64 w-full rounded-xl" />
            </div>
          </div>
        </section>

        <section className="rounded-2xl border bg-card p-5">
          <div className="flex items-center justify-between gap-4">
            <Skeleton className="h-5 w-44" />
            <Skeleton className="h-8 w-20" />
          </div>
          <div className="mt-5 overflow-hidden rounded-xl border">
            <div className="grid grid-cols-[minmax(0,1.2fr)_9rem_9rem_8rem_9rem_8rem] gap-4 border-b bg-muted/40 px-4 py-3">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 w-14" />
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-4 w-16" />
            </div>
            <div className="space-y-0">
              {placeholderIds(4, "benchmark-table-row").map((id) => (
                <div
                  key={id}
                  className="grid grid-cols-[minmax(0,1.2fr)_9rem_9rem_8rem_9rem_8rem] gap-4 border-b px-4 py-4 last:border-b-0"
                >
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-4 w-14" />
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-4 w-16" />
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>
    </RouteSkeleton>
  );
}

export function SettingsPageSkeleton() {
  return (
    <RouteSkeleton ariaLabel="Loading settings">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-col gap-1">
            <Skeleton className="h-8 w-28" />
            <Skeleton className="h-4 w-52 max-w-full" />
          </div>
          <Skeleton className="h-10 w-28 rounded-lg" />
        </div>

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Skeleton className="size-4 rounded-sm" />
                <Skeleton className="h-5 w-16" />
                <Skeleton className="ml-2 h-4 w-28 max-w-full" />
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-hidden rounded-md border">
                <div className="grid grid-cols-[minmax(0,1.2fr)_minmax(0,0.9fr)_7rem] gap-4 border-b bg-muted/40 px-4 py-3">
                  <Skeleton className="h-4 w-14" />
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="ml-auto h-4 w-14" />
                </div>
                <div className="space-y-0">
                  {placeholderIds(4, "settings-profile-row").map((id) => (
                    <div
                      key={id}
                      className="grid grid-cols-[minmax(0,1.2fr)_minmax(0,0.9fr)_7rem] gap-4 border-b px-4 py-4 last:border-b-0"
                    >
                      <div className="space-y-2">
                        <Skeleton className="h-4 w-28" />
                        <Skeleton className="h-4 w-20" />
                      </div>
                      <Skeleton className="h-4 w-28" />
                      <div className="flex justify-end gap-2">
                        <Skeleton className="size-8 rounded-md" />
                        <Skeleton className="size-8 rounded-md" />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="flex flex-col gap-5">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Skeleton className="size-4 rounded-sm" />
                  <Skeleton className="h-5 w-24" />
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                {placeholderIds(4, "settings-field").map((id) => (
                  <div key={id} className="space-y-2">
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-10 w-full rounded-md" />
                  </div>
                ))}

                <div className="flex gap-2">
                  <Skeleton className="h-10 flex-1 rounded-md" />
                  <Skeleton className="h-10 w-24 rounded-md" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Skeleton className="size-4 rounded-sm" />
                  <Skeleton className="h-5 w-20" />
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <div className="grid grid-cols-[auto_minmax(0,1fr)] gap-3">
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-6 w-full rounded-sm" />
                </div>
                <Skeleton className="h-14 w-full rounded-md" />
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </RouteSkeleton>
  );
}

export function HelpParametersSkeleton() {
  return (
    <RouteSkeleton ariaLabel="Loading parameter glossary">
      <main className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-4 py-12 md:px-8">
        <header className="space-y-3">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-9 w-80 max-w-full" />
          <div className="space-y-2">
            <Skeleton className="h-4 w-full max-w-3xl" />
            <Skeleton className="h-4 w-full max-w-3xl" />
            <Skeleton className="h-4 w-2/3 max-w-2xl" />
          </div>
        </header>

        <div className="grid gap-4">
          {placeholderIds(6, "help-parameter-card").map((id) => (
            <Card key={id}>
              <CardHeader>
                <CardTitle className="text-lg">
                  <Skeleton className="h-6 w-36" />
                </CardTitle>
                <Skeleton className="h-4 w-48 max-w-full" />
              </CardHeader>
              <CardContent className="space-y-2">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-4/5" />
              </CardContent>
            </Card>
          ))}
        </div>
      </main>
    </RouteSkeleton>
  );
}

export function RunCreateSkeleton() {
  return (
    <RouteSkeleton ariaLabel="Loading form">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <Skeleton className="size-4 rounded-sm" />
            <Skeleton className="h-5 w-12" />
          </div>
          <Skeleton className="h-10 w-80 max-w-full" />
          <Skeleton className="h-5 w-[28rem] max-w-full" />
        </div>

        <Card>
          <CardHeader className="space-y-3">
            <CardTitle>
              <Skeleton className="h-8 w-56 max-w-full" />
            </CardTitle>
            <Skeleton className="h-5 w-80 max-w-full" />
          </CardHeader>

          <CardContent className="flex flex-col gap-8">
            <RunFormSectionSkeleton titleWidth="w-24" descriptionWidth="w-48">
              <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
                <div className="space-y-6">
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <Skeleton className="h-5 w-20" />
                      <Skeleton className="size-4 rounded-full" />
                    </div>
                    <Skeleton className="h-10 w-full rounded-md" />
                  </div>
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <Skeleton className="h-5 w-16" />
                      <Skeleton className="size-4 rounded-full" />
                    </div>
                    <Skeleton className="h-10 w-full rounded-md" />
                  </div>
                </div>
                <div className="rounded-2xl border p-3">
                  <Skeleton className="h-40 w-full rounded-xl" />
                </div>
              </div>
            </RunFormSectionSkeleton>

            <RunFormSectionSkeleton titleWidth="w-16" descriptionWidth="w-56">
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <Skeleton className="h-5 w-16" />
                  <Skeleton className="size-4 rounded-full" />
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  <Skeleton className="h-28 w-full rounded-2xl" />
                  <Skeleton className="h-28 w-full rounded-2xl" />
                </div>
              </div>
            </RunFormSectionSkeleton>

            <RunFormSectionSkeleton titleWidth="w-20" descriptionWidth="w-64">
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <Skeleton className="h-5 w-28" />
                  <Skeleton className="size-4 rounded-full" />
                </div>
                <div className="grid gap-3 md:grid-cols-3">
                  {placeholderIds(3, "run-create-backend-card").map((id) => (
                    <div key={id} className="rounded-2xl border p-4">
                      <Skeleton className="size-8 rounded-lg" />
                      <Skeleton className="mt-5 h-6 w-24" />
                      <Skeleton className="mt-4 h-4 w-full" />
                      <Skeleton className="mt-2 h-4 w-4/5" />
                    </div>
                  ))}
                </div>
              </div>
            </RunFormSectionSkeleton>

            <RunFormSectionSkeleton titleWidth="w-48" descriptionWidth="w-72">
              <div className="space-y-6">
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Skeleton className="h-5 w-20" />
                    <Skeleton className="size-4 rounded-full" />
                  </div>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
                    {placeholderIds(6, "run-create-algorithm-card").map((id) => (
                      <Skeleton key={id} className="h-24 w-full rounded-2xl" />
                    ))}
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Skeleton className="h-5 w-14" />
                    <Skeleton className="size-4 rounded-full" />
                  </div>
                  <div className="grid gap-3 xl:grid-cols-3">
                    <Skeleton className="h-40 w-full rounded-2xl" />
                    <Skeleton className="h-40 w-full rounded-2xl" />
                    <Skeleton className="h-40 w-full rounded-2xl" />
                  </div>
                </div>
              </div>
            </RunFormSectionSkeleton>

            <div className="rounded-xl border border-border/70 bg-muted/15 p-4">
              <div className="flex items-center justify-between gap-4">
                <div className="space-y-2">
                  <Skeleton className="h-5 w-28" />
                  <Skeleton className="h-4 w-44 max-w-full" />
                </div>
                <Skeleton className="h-8 w-24 rounded-full" />
              </div>
            </div>
          </CardContent>

          <div className="flex flex-col gap-3 p-6 pt-0">
            <Skeleton className="h-11 w-full rounded-md" />
          </div>
        </Card>
      </div>
    </RouteSkeleton>
  );
}

export function InfoListSkeleton() {
  return (
    <RouteSkeleton ariaLabel="Loading reference list">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-4 py-8">
        <Skeleton className="h-4 w-24" />
        <div className="flex flex-col gap-2">
          <Skeleton className="h-7 w-1/3" />
          <Skeleton className="h-4 w-1/2" />
        </div>
        <div className="flex flex-col gap-4">
          {placeholderIds(4, "info-list-item").map((id) => (
            <div key={id} className="flex flex-col gap-2 rounded-lg border p-4">
              <Skeleton className="h-5 w-2/5" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
            </div>
          ))}
        </div>
      </div>
    </RouteSkeleton>
  );
}

export function InfoDetailSkeleton() {
  return (
    <RouteSkeleton ariaLabel="Loading reference detail">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-4 py-8">
        <Skeleton className="h-4 w-24" />
        <div className="flex flex-col gap-3">
          <Skeleton className="h-5 w-12" />
          <Skeleton className="h-7 w-1/2" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </div>
        {placeholderIds(3, "info-detail-section").map((id) => (
          <div key={id} className="flex flex-col gap-2 rounded-lg border p-4">
            <Skeleton className="h-5 w-1/4" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        ))}
      </div>
    </RouteSkeleton>
  );
}
