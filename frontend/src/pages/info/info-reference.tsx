import type { ComponentType, ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { ArrowRight, Atom, BookMarked, Cpu, SlidersHorizontal, Zap } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { prominentSurfaceHoverClassName } from "@/lib/interactive-styles";
import { cn } from "@/lib/utils";
import type { InfoComponentId } from "@/content/info/components";
import type { NoiseModelId } from "@/content/info/noise-models";
import type { InfoEntry } from "@/content/info/types";
import type { BackendTarget, RunAlgorithm } from "@/types/run";

export type InfoCollectionKey = "algorithms" | "components" | "backends" | "noise-models";

export interface InfoCollectionDefinition {
  readonly key: InfoCollectionKey;
  readonly title: string;
  readonly description: string;
  readonly to: "/info/algorithms" | "/info/components" | "/info/backends" | "/info/noise-models";
  readonly icon: ComponentType<{ className?: string }>;
  readonly highlights: readonly string[];
  readonly detailsMinHeightClassName?: string;
}

export interface RelatedTopic {
  readonly label: string;
  readonly description: string;
  readonly to:
    | "/info/algorithms"
    | "/info/components"
    | "/info/backends"
    | "/info/noise-models"
    | "/help/parameters"
    | "/info/algorithms/$algorithmId"
    | "/info/components/$componentId"
    | "/info/backends/$backendId"
    | "/info/noise-models/$noiseModelId";
  readonly params?: {
    readonly algorithmId?: RunAlgorithm;
    readonly componentId?: InfoComponentId;
    readonly backendId?: BackendTarget;
    readonly noiseModelId?: NoiseModelId;
  };
}

interface InfoCollectionTone {
  readonly badgeClassName: string;
  readonly iconClassName: string;
}

type InfoCollectionHeroProps = Readonly<{
  collection?: InfoCollectionKey;
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
}>;

type InfoCollectionTabsProps = Readonly<{
  current: InfoCollectionKey;
}>;

type InfoCollectionCardProps = Readonly<{
  item: InfoCollectionDefinition;
}>;

type InfoEntryRoute =
  | "/info/algorithms/$algorithmId"
  | "/info/components/$componentId"
  | "/info/backends/$backendId"
  | "/info/noise-models/$noiseModelId";

type InfoEntryParams = Readonly<{
  algorithmId?: RunAlgorithm;
  componentId?: InfoComponentId;
  backendId?: BackendTarget;
  noiseModelId?: NoiseModelId;
}>;

type InfoEntryCardProps = Readonly<{
  collection: InfoCollectionKey;
  entry: InfoEntry;
  code: string;
  to: InfoEntryRoute;
  params: InfoEntryParams;
}>;

type InfoRelatedTopicsCardProps = Readonly<{
  title?: string;
  description?: string;
  topics: readonly RelatedTopic[];
}>;

const COLLECTION_TONES: Record<InfoCollectionKey, InfoCollectionTone> = {
  algorithms: {
    badgeClassName: "border-info/25 bg-info/10 text-info",
    iconClassName: "border-info/25 bg-info/10 text-info",
  },
  components: {
    badgeClassName: "border-border/70 bg-muted/40 text-foreground",
    iconClassName: "border-border/70 bg-muted/40 text-foreground",
  },
  backends: {
    badgeClassName: "border-success/25 bg-success/10 text-success",
    iconClassName: "border-success/25 bg-success/10 text-success",
  },
  "noise-models": {
    badgeClassName: "border-warning/25 bg-warning/10 text-warning",
    iconClassName: "border-warning/25 bg-warning/10 text-warning",
  },
};

const INFO_COLLECTIONS: InfoCollectionDefinition[] = [
  {
    key: "algorithms",
    title: "Algorithms",
    description:
      "Reference notes for the chemistry solvers, subspace methods, and sample-based workflows available in Quantum Studio.",
    to: "/info/algorithms",
    icon: Atom,
    highlights: ["Ground-state baselines", "Projected subspaces", "Sample-driven diagonalization"],
  },
  {
    key: "components",
    title: "Components",
    description:
      "Longer notes for ansatzes, optimizers, basis sets, and reference-state choices that shape how the algorithms behave.",
    to: "/info/components",
    icon: SlidersHorizontal,
    highlights: ["Ansatz depth", "Optimizer behavior", "Chemistry setup"],
  },
  {
    key: "backends",
    title: "Backends",
    description:
      "Execution targets covering exact simulation, local shot-based studies, and managed IBM hardware primitives.",
    to: "/info/backends",
    icon: Cpu,
    highlights: ["Ideal verification", "Shot-based simulation", "Hardware routing"],
    detailsMinHeightClassName: "sm:min-h-[10rem]",
  },
  {
    key: "noise-models",
    title: "Noise Models",
    description:
      "Error presets and backend-derived calibration models for studying how noise changes algorithm behavior.",
    to: "/info/noise-models",
    icon: Zap,
    highlights: ["Gate errors", "Relaxation and readout", "Calibration snapshots"],
    detailsMinHeightClassName: "sm:min-h-[10rem]",
  },
];

function getCollectionTone(collection: InfoCollectionKey) {
  return COLLECTION_TONES[collection];
}

function getCollectionIcon(collection?: InfoCollectionKey) {
  return INFO_COLLECTIONS.find((item) => item.key === collection)?.icon ?? BookMarked;
}

export function InfoCollectionHero({
  collection,
  eyebrow,
  title,
  description,
  actions,
}: InfoCollectionHeroProps) {
  const Icon = getCollectionIcon(collection);
  const tone = collection ? getCollectionTone(collection) : null;

  return (
    <div className="space-y-4">
      <div className="space-y-3">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
          {eyebrow}
        </p>
        <div className="flex items-start gap-3">
          {tone ? (
            <div
              className={cn(
                "mt-1 flex size-9 shrink-0 items-center justify-center rounded-lg border",
                tone.iconClassName,
              )}
            >
              <Icon className="size-4" />
            </div>
          ) : null}
          <div className="min-w-0 space-y-2">
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{title}</h1>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground sm:text-[15px]">
              {description}
            </p>
          </div>
        </div>
      </div>
      {collection ? <InfoCollectionTabs current={collection} /> : null}
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </div>
  );
}

export function InfoCollectionTabs({ current }: InfoCollectionTabsProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {INFO_COLLECTIONS.map((item) => {
        const Icon = item.icon;
        const isCurrent = item.key === current;

        return (
          <Link
            key={item.key}
            to={item.to}
            aria-current={isCurrent ? "page" : undefined}
            className={cn(
              "inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm",
              isCurrent
                ? "border-interactive-selected-border bg-interactive-selected text-interactive-selected-foreground shadow-[var(--shadow-interactive-selected)]"
                : cn(
                    "border-border/70 bg-card text-muted-foreground hover:text-foreground",
                    prominentSurfaceHoverClassName,
                  ),
            )}
          >
            <Icon className="size-4" />
            <span>{item.title}</span>
          </Link>
        );
      })}
    </div>
  );
}

export function InfoCollectionCard({ item }: InfoCollectionCardProps) {
  const Icon = item.icon;
  const tone = getCollectionTone(item.key);
  const detailsMinHeightClassName = item.detailsMinHeightClassName ?? "sm:min-h-[8.5rem]";

  return (
    <Link
      to={item.to}
      className="group block h-full rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
    >
      <Card className={cn("h-full min-w-0 border-border/75", prominentSurfaceHoverClassName)}>
        <CardHeader className="gap-3">
          <div
            className={cn(
              "flex size-9 items-center justify-center rounded-lg border",
              tone.iconClassName,
            )}
          >
            <Icon className="size-4" />
          </div>
          <div className={cn("space-y-2", detailsMinHeightClassName)}>
            <CardTitle className="text-lg tracking-tight">{item.title}</CardTitle>
            <CardDescription className="leading-6">{item.description}</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="flex flex-1 flex-col space-y-3 pt-0">
          <p className="text-sm leading-6 text-muted-foreground">
            {item.highlights.slice(0, 2).join(" · ")}
          </p>
          <div className="mt-auto inline-flex items-center gap-2 text-sm font-medium text-primary">
            Open collection
            <ArrowRight className="size-4" />
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

export function InfoEntryCard({ collection, entry, code, to, params }: InfoEntryCardProps) {
  const tone = getCollectionTone(collection);

  return (
    <Link
      to={to}
      params={params as never}
      className="group block rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
    >
      <Card className={cn("h-full min-w-0 border-border/75", prominentSurfaceHoverClassName)}>
        <CardHeader className="gap-3">
          <div className="flex items-center gap-2">
            <Badge
              variant="outline"
              className={cn(
                "rounded-full font-mono text-[11px] uppercase tracking-[0.2em]",
                tone.badgeClassName,
              )}
            >
              {code}
            </Badge>
          </div>
          <div className="space-y-2">
            <CardTitle className="text-lg leading-snug tracking-tight">{entry.title}</CardTitle>
            <CardDescription className="line-clamp-4 leading-6">{entry.summary}</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="inline-flex items-center gap-2 text-sm font-medium text-primary">
            Open article
            <ArrowRight className="size-4" />
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

export function InfoRelatedTopicsCard({
  title = "Continue with",
  description = "Related pages that usually matter next.",
  topics,
}: InfoRelatedTopicsCardProps) {
  if (topics.length === 0) {
    return null;
  }

  return (
    <Card className="min-w-0 border-border/75">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {topics.map((topic) => (
          <Link
            key={topic.label}
            to={topic.to as never}
            params={topic.params as never}
            className={cn(
              "group block rounded-lg border border-border/70 bg-card px-4 py-3",
              prominentSurfaceHoverClassName,
            )}
          >
            <div className="space-y-1.5">
              <p className="text-sm font-medium">{topic.label}</p>
              <p className="text-sm leading-5 text-muted-foreground">{topic.description}</p>
              <div className="inline-flex items-center gap-2 text-sm font-medium text-primary">
                Open page
                <ArrowRight className="size-4" />
              </div>
            </div>
          </Link>
        ))}
      </CardContent>
    </Card>
  );
}
