export type InfoBlock =
  | { kind: "text"; heading?: string; body: string }
  | { kind: "equation"; label?: string; latex: string; displayText?: string; caption?: string }
  | { kind: "image"; src: string; alt: string; caption?: string }
  | {
      kind: "video";
      src: string;
      title: string;
      caption?: string;
      href?: string;
      linkLabel?: string;
    }
  | { kind: "callout"; title: string; body: string; tone?: "info" | "success" | "warning" }
  | { kind: "list"; heading?: string; items: string[] };

export interface InfoEntry {
  id: string;
  title: string;
  summary: string;
  sections?: { heading: string; body: string }[];
  blocks?: InfoBlock[];
  references?: { label: string; href: string }[];
}
