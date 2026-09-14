import { useCallback, useEffect, useState } from "react";
import { Plus, Search } from "lucide-react";
import { fetchMolecules } from "@/api/molecules";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";
import type { MoleculeResponse } from "@/types/run";

type MoleculeSearchPopoverProps = Readonly<{
  onAdd: (mol: MoleculeResponse) => void;
  disabled?: boolean;
  triggerClassName?: string;
}>;

export function MoleculeSearchPopover({
  onAdd,
  disabled = false,
  triggerClassName,
}: MoleculeSearchPopoverProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<MoleculeResponse[]>([]);
  const [searching, setSearching] = useState(false);

  const search = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([]);
      return;
    }
    setSearching(true);
    try {
      const resp = await fetchMolecules({ q, limit: 8 });
      setResults(resp.items);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  }, []);

  useEffect(() => {
    const timeout = setTimeout(() => void search(query), 300);
    return () => clearTimeout(timeout);
  }, [query, search]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className={cn("h-9 gap-1.5 text-sm", triggerClassName)}
          disabled={disabled}
        >
          <Plus className="h-3.5 w-3.5" />
          Add from library
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-3" align="start">
        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium">Search molecule library</p>
          <div className="relative">
            <Search className="absolute left-2 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              placeholder="Name or formula..."
              className="pl-7 h-8 text-xs"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              autoFocus
            />
          </div>
          {searching && (
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Spinner className="size-3 border-[1.5px]" />
              Searching...
            </div>
          )}
          {results.length > 0 && (
            <div className="flex flex-col gap-0.5 max-h-52 overflow-y-auto">
              {results.map((mol) => (
                <button
                  key={mol.id}
                  className="flex flex-col gap-0.5 rounded px-2 py-1.5 text-left hover:bg-muted text-xs transition-colors"
                  onClick={() => {
                    onAdd(mol);
                    setOpen(false);
                    setQuery("");
                    setResults([]);
                  }}
                >
                  <span className="font-medium">{mol.name}</span>
                  {mol.description && (
                    <span className="text-muted-foreground line-clamp-1">{mol.description}</span>
                  )}
                </button>
              ))}
            </div>
          )}
          {!searching && query.trim() && results.length === 0 && (
            <p className="text-xs text-muted-foreground">No molecules found.</p>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
