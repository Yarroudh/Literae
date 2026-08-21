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
  const dialogRef = useRef<HTMLDivElement>(null);
  const activeCount = useMemo(() => (Object.keys(filters) as (keyof ResearchFilters)[]).filter((key) => key !== "query" && filters[key] !== INITIAL_FILTERS[key]).length, [filters]);

  useEffect(() => {
    if (!open) return;
    function handleKeyDown(event: KeyboardEvent) { if (event.key === "Escape") setOpen(false); }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open]);

  return (
    <div className="relative">
      <button type="button" onClick={() => setOpen(true)} className={`relative grid size-9 place-items-center rounded-[9px] transition ${open || activeCount > 0 ? "bg-[var(--accent-soft)] text-[var(--accent)]" : "text-[var(--muted)] hover:bg-[var(--panel-2)] hover:text-[var(--ink)]"}`} aria-label="Research filters" title="Research filters" aria-expanded={open} aria-haspopup="dialog">
        <FilterIcon className="size-[18px]" />
        {activeCount > 0 && <span className="absolute -right-1 -top-1 grid size-4 place-items-center rounded-full bg-[var(--accent)] text-[9px] font-bold text-white">{activeCount}</span>}
      </button>
      {open && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/30 p-0 backdrop-blur-[2px] sm:items-center sm:p-6" onPointerDown={(event) => { if (!dialogRef.current?.contains(event.target as Node)) setOpen(false); }}>
          <div ref={dialogRef} role="dialog" aria-modal="true" aria-label="Research filters" className="flex max-h-[92dvh] w-full flex-col overflow-hidden rounded-t-[24px] border border-[var(--line)] bg-[var(--surface)] shadow-[0_28px_90px_rgba(0,0,0,.22)] sm:max-w-4xl sm:rounded-[24px]">
            <div className="flex items-start justify-between gap-4 border-b border-[var(--line)] px-5 py-5 sm:px-6">
              <div><p className="text-[10px] font-bold uppercase tracking-[.14em] text-[var(--accent)]">Discovery settings</p><h2 className="mt-1 text-lg font-bold">Refine your search</h2><p className="mt-1 text-xs text-[var(--muted)]">Control what OpenAlex retrieves without overloading the generated answer.</p></div>
              <button type="button" onClick={() => setOpen(false)} className="grid size-9 shrink-0 place-items-center rounded-full border border-[var(--line)] text-lg leading-none text-[var(--muted)] transition hover:bg-[var(--panel-2)] hover:text-[var(--ink)]" aria-label="Close filters">×</button>
            </div>
            <div className="overflow-y-auto px-4 py-4 sm:px-6 sm:py-5"><SearchFilters filters={filters} onChange={onChange} /></div>
            <div className="flex items-center justify-between gap-3 border-t border-[var(--line)] bg-[var(--surface)] px-5 py-4 sm:px-6">
              <button type="button" onClick={onReset} disabled={activeCount === 0} className="h-10 rounded-xl px-3 text-xs font-semibold text-[var(--muted)] transition hover:bg-[var(--panel-2)] hover:text-[var(--ink)] disabled:cursor-not-allowed disabled:opacity-40">Reset all</button>
              <div className="flex items-center gap-3"><span className="hidden text-xs text-[var(--muted)] sm:inline">{activeCount === 0 ? "Default settings" : `${activeCount} ${activeCount === 1 ? "change" : "changes"}`}</span><button type="button" onClick={() => setOpen(false)} className="h-10 rounded-xl bg-[var(--accent)] px-5 text-xs font-bold text-white shadow-sm transition hover:bg-[var(--accent-hover)]">Apply filters</button></div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
