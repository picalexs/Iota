import { Fragment } from "react";
import katex from "katex";
import { ExternalLink, Play } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { InfoBlock, InfoEntry } from "@/content/info/types";

interface InfoDetailContentProps {
  readonly entry: InfoEntry;
}

const MAX_EQUATION_LATEX_LENGTH = 5_000;

function blockKey(block: InfoBlock, index: number): string {
  switch (block.kind) {
    case "text":
      return `${block.kind}-${block.heading ?? "body"}-${block.body.slice(0, 32)}`;
    case "equation":
      return `${block.kind}-${block.label ?? block.latex.slice(0, 32)}`;
    case "image":
      return `${block.kind}-${block.src}`;
    case "video":
      return `${block.kind}-${block.src}`;
    case "callout":
      return `${block.kind}-${block.title}-${block.body.slice(0, 32)}`;
    case "list":
      return `${block.kind}-${block.heading ?? "items"}-${block.items[0] ?? index}`;
  }
}

export function InfoDetailContent({ entry }: InfoDetailContentProps) {
  const blocks =
    entry.blocks ??
    entry.sections?.map<InfoBlock>((section) => ({
      kind: "text",
      heading: section.heading,
      body: section.body,
    })) ??
    [];
  const keyedBlocks = blocks.map((block, index) => ({
    id: blockKey(block, index),
    block,
    index,
  }));

  return (
    <>
      <div className="grid gap-4">
        {keyedBlocks.map(({ id, block, index }) => (
          <InfoBlockCard key={id} block={block} index={index} />
        ))}
      </div>

      {entry.references && entry.references.length > 0 && (
        <Card className="border-border/60">
          <CardHeader className="gap-1 pb-3">
            <CardTitle className="text-base">References</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {entry.references.map((ref, index) => (
              <a
                key={ref.href}
                href={ref.href}
                target="_blank"
                rel="noopener noreferrer"
                className="group flex items-start justify-between gap-3 rounded-xl border border-border/60 bg-muted/20 px-4 py-3 transition-colors hover:border-primary/35 hover:bg-primary/5"
              >
                <div className="space-y-1">
                  <p className="font-mono text-xs text-muted-foreground">
                    {String(index + 1).padStart(2, "0")}
                  </p>
                  <p className="text-sm font-medium text-foreground">{ref.label}</p>
                </div>
                <ExternalLink className="mt-0.5 size-4 shrink-0 text-primary transition-transform group-hover:translate-x-0.5" />
              </a>
            ))}
          </CardContent>
        </Card>
      )}
    </>
  );
}

function InfoBlockCard({ block, index }: Readonly<{ block: InfoBlock; index: number }>) {
  if (block.kind === "image") {
    return (
      <figure className="overflow-hidden rounded-xl border border-border/60 bg-card">
        <div className="border-b border-border/50 px-4 py-3">
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
            Figure {String(index + 1).padStart(2, "0")}
          </p>
        </div>
        <img src={block.src} alt={block.alt} className="w-full bg-muted/20 object-contain" />
        {block.caption && (
          <figcaption className="border-t px-4 py-3 text-xs leading-relaxed text-muted-foreground">
            <InlineRichText text={block.caption} />
          </figcaption>
        )}
      </figure>
    );
  }

  if (block.kind === "video") {
    return (
      <Card className="border-border/60 overflow-hidden">
        <CardHeader className="gap-2 border-b border-border/50 pb-4">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            <Play className="size-3.5" />
            Method video
          </div>
          <CardTitle className="text-base leading-snug">{block.title}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 pt-4">
          <div className="overflow-hidden rounded-lg border border-border/60 bg-muted/20">
            <div className="aspect-video">
              <iframe
                src={block.src}
                title={block.title}
                className="h-full w-full"
                allow="autoplay; encrypted-media; picture-in-picture"
                allowFullScreen
                loading="lazy"
                referrerPolicy="strict-origin-when-cross-origin"
                sandbox="allow-same-origin allow-scripts allow-presentation"
              />
            </div>
          </div>
          {block.caption && (
            <p className="text-sm leading-relaxed text-muted-foreground">
              <InlineRichText text={block.caption} />
            </p>
          )}
          {block.href && (
            <a
              href={block.href}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
            >
              {block.linkLabel ?? "Open source lesson"}
              <ExternalLink className="size-4" />
            </a>
          )}
        </CardContent>
      </Card>
    );
  }

  if (block.kind === "equation") {
    const renderedEquation = renderEquation(block.latex);
    const fallbackText = block.displayText ?? simplifyLatex(block.latex);

    return (
      <Card className="border-border/60">
        <CardContent className="space-y-3 pt-4">
          {block.label && (
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {block.label}
            </p>
          )}
          <div className="overflow-x-auto rounded-lg border border-border/60 bg-muted/25 px-4 py-3">
            {renderedEquation ? (
              <div
                className="info-equation min-w-fit text-foreground"
                aria-label={fallbackText}
                dangerouslySetInnerHTML={{ __html: renderedEquation }}
              />
            ) : (
              <p className="min-w-fit whitespace-pre text-sm font-medium tracking-tight text-foreground">
                {fallbackText}
              </p>
            )}
          </div>
          {block.caption && (
            <p className="text-xs leading-relaxed text-muted-foreground">
              <InlineRichText text={block.caption} />
            </p>
          )}
        </CardContent>
      </Card>
    );
  }

  if (block.kind === "callout") {
    return (
      <Card
        className={cn(
          "border-border/60",
          block.tone === "success" && "border-success/30 bg-success/8",
          block.tone === "warning" && "border-warning/30 bg-warning/8",
          (!block.tone || block.tone === "info") && "border-info/25 bg-info/8",
        )}
      >
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold">{block.title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-relaxed text-muted-foreground">
            <InlineRichText text={block.body} />
          </p>
        </CardContent>
      </Card>
    );
  }

  if (block.kind === "list") {
    return (
      <Card className="border-border/60">
        {block.heading && (
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold">{block.heading}</CardTitle>
          </CardHeader>
        )}
        <CardContent className={block.heading ? "pt-0" : "pt-4"}>
          <ul className="list-disc space-y-2 pl-4 text-sm leading-relaxed text-muted-foreground">
            {block.items.map((item) => (
              <li key={item}>
                <InlineRichText text={item} />
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border/60">
      {block.heading && (
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold">{block.heading}</CardTitle>
        </CardHeader>
      )}
      <CardContent className={block.heading ? undefined : "pt-4"}>
        <p className="text-sm leading-relaxed text-muted-foreground">
          <InlineRichText text={block.body} />
        </p>
      </CardContent>
    </Card>
  );
}

function InlineRichText({ text }: Readonly<{ text: string }>) {
  return (
    <>
      {splitInlineText(text).map((segment, index) => {
        const segmentKey = `${segment.kind}-${segment.text}-${index}`;
        return segment.kind === "code" ? (
          <code
            key={segmentKey}
            className="rounded bg-muted px-1 py-0.5 font-mono text-[0.92em] font-semibold text-foreground"
          >
            {segment.text}
          </code>
        ) : (
          <Fragment key={segmentKey}>{segment.text}</Fragment>
        );
      })}
    </>
  );
}

function splitInlineText(text: string) {
  const parts = text.split(/(`[^`]+`)/g).filter((part) => part.length > 0);

  return parts.map((part) =>
    part.startsWith("`") && part.endsWith("`")
      ? { kind: "code" as const, text: part.slice(1, -1) }
      : { kind: "text" as const, text: part },
  );
}

function renderEquation(latex: string) {
  if (latex.length > MAX_EQUATION_LATEX_LENGTH) {
    return null;
  }

  try {
    return katex.renderToString(latex, {
      displayMode: true,
      output: "htmlAndMathml",
      strict: "ignore",
      trust: false,
      throwOnError: false,
    });
  } catch {
    return null;
  }
}

function simplifyLatex(input: string) {
  return input
    .replaceAll(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, "($1)/($2)")
    .replaceAll(String.raw`\boldsymbol{\theta}`, "θ")
    .replaceAll(String.raw`\boldsymbol{\psi}`, "ψ")
    .replaceAll(/\\mathcal\{([A-Za-z])\}/g, "$1")
    .replaceAll(/\\mathbf\{([^}]+)\}/g, "$1")
    .replaceAll(/\\mathrm\{([^}]+)\}/g, "$1")
    .replaceAll(/\\text\{([^}]+)\}/g, "$1")
    .replaceAll(/\\operatorname\{([^}]+)\}/g, "$1")
    .replaceAll(String.raw`\langle`, "⟨")
    .replaceAll(String.raw`\rangle`, "⟩")
    .replaceAll(/\\leq?|\\le/g, "≤")
    .replaceAll(/\\geq?|\\ge/g, "≥")
    .replaceAll(/\\to|\\rightarrow/g, "→")
    .replaceAll(String.raw`\mid`, "|")
    .replaceAll(String.raw`\times`, "×")
    .replaceAll(String.raw`\cdot`, "·")
    .replaceAll(String.raw`\propto`, "∝")
    .replaceAll(String.raw`\sum`, "∑")
    .replaceAll(String.raw`\min`, "min")
    .replaceAll(String.raw`\max`, "max")
    .replaceAll(String.raw`\psi`, "ψ")
    .replaceAll(String.raw`\phi`, "φ")
    .replaceAll(String.raw`\theta`, "θ")
    .replaceAll(String.raw`\Delta`, "Δ")
    .replaceAll(String.raw`\rho`, "ρ")
    .replaceAll(String.raw`\alpha`, "α")
    .replaceAll(String.raw`\beta`, "β")
    .replaceAll(String.raw`\gamma`, "γ")
    .replaceAll(String.raw`\delta`, "δ")
    .replaceAll(String.raw`\Gamma`, "Γ")
    .replaceAll(/\\ldots|\\dots/g, "…")
    .replaceAll(String.raw`\quad`, "    ")
    .replaceAll(String.raw`\begin{pmatrix}`, "[")
    .replaceAll(String.raw`\end{pmatrix}`, "]")
    .replaceAll(String.raw`\\`, "; ")
    .replaceAll("&", ", ")
    .replaceAll(String.raw`\{`, "{")
    .replaceAll(String.raw`\}`, "}")
    .replaceAll(/[{}]/g, "")
    .replaceAll(/\s+/g, " ")
    .trim();
}
