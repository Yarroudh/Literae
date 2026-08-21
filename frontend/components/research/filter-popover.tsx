"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { FilterIcon } from "@/components/ui/icons";
import { INITIAL_FILTERS } from "@/lib/research";
import type { ResearchFilters } from "@/types/research";
import { SearchFilters } from "./search-filters";

type FilterPopoverProps = {
  filters: ResearchFilters;
  onChange: (name: keyof ResearchFilters, value: string) => void;
  onReset: () => void;
};

export function FilterPopover({ filters, onChange, onReset }: FilterPopoverProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const activeCount = useMemo(() => (Object.keys(filters) as (keyof ResearchFilters)[]).filter((key) => key !== "query" && key !== "sort" && filters[key] !== INITIAL_FILTERS[key]).length, [filters]);

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button type="button" onClick={() => setOpen((current) => !current)} className={`relative grid size-9 place-items-center rounded-[9px] transition ${open || activeCount > 0 ? "bg-[var(--accent-soft)] text-[var(--accent)]" : "text-[var(--muted)] hover:bg-[var(--panel-2)] hover:text-[var(--ink)]"}`} aria-label="Research filters" title="Research filters" aria-expanded={open} aria-haspopup="dialog">
        <FilterIcon className="size-[18px]" />
        {activeCount > 0 && <span className="absolute -right-1 -top-1 grid size-4 place-items-center rounded-full bg-[var(--accent)] text-[9px] font-bold text-white">{activeCount}</span>}
      </button>
      {open && (
        <div role="dialog" aria-label="Research filters" className="absolute bottom-12 right-0 z-30 w-[min(90vw,760px)] overflow-hidden rounded-[18px] border border-[var(--line)] bg-[var(--surface)] shadow-[0_24px_70px_var(--shadow)]">
          <div className="flex items-start justify-between gap-4 border-b border-[var(--line)] px-5 py-4">
            <div><h2 className="text-sm font-bold">Research filters</h2><p className="mt-1 text-xs text-[var(--muted)]">Narrow the literature Literae considers.</p></div>
            {activeCount > 0 && <button type="button" onClick={onReset} className="rounded-lg px-2.5 py-1.5 text-xs font-semibold text-[var(--accent)] transition hover:bg-[var(--accent-soft)]">Reset</button>}
          </div>
          <div className="max-h-[min(60vh,460px)] overflow-y-auto px-5 py-5"><SearchFilters filters={filters} onChange={onChange} /></div>
          <div className="flex items-center justify-between border-t border-[var(--line)] bg-[var(--panel-2)] px-5 py-3">
            <span className="text-xs text-[var(--muted)]">{activeCount === 0 ? "No filters applied" : `${activeCount} ${activeCount === 1 ? "filter" : "filters"} applied`}</span>
            <button type="button" onClick={() => setOpen(false)} className="h-9 rounded-[9px] bg-[var(--accent)] px-4 text-xs font-bold text-white transition hover:bg-[var(--accent-hover)]">Done</button>
          </div>
        </div>
      )}
    </div>
  );
}
