import { HelpCircle } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

type FieldHelpProps = Readonly<{
  short: string;
  anchor?: string;
  href?: string;
  label?: string;
}>;

export function FieldHelp({ short, anchor, href, label = "field help" }: FieldHelpProps) {
  const resolvedHref = href ?? getParameterHelpHref(anchor);

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <a
          href={resolvedHref}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`Learn more about ${label}`}
          className="inline-flex rounded-full text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        >
          <HelpCircle className="size-3.5" />
        </a>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-56 text-xs">
        {short}
      </TooltipContent>
    </Tooltip>
  );
}

function getParameterHelpHref(anchor: string | undefined) {
  if (anchor === undefined) {
    return "/help/parameters";
  }

  return `/help/parameters#${anchor}`;
}
