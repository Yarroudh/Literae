"use client";

import { useEffect, useRef, useState } from "react";
import { ExclamationIcon } from "./icons";

export function DisclaimerPopover() {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

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
      <button type="button" onClick={() => setOpen((current) => !current)} className={`grid size-9 place-items-center rounded-[10px] border transition ${open ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]" : "border-[var(--line)] bg-[var(--surface)] text-[var(--muted)] hover:border-[var(--accent)] hover:text-[var(--ink)]"}`} aria-label="Research disclaimer" title="Research disclaimer" aria-expanded={open} aria-haspopup="dialog">
        <ExclamationIcon className="size-[18px]" />
      </button>
      {open && (
        <div role="dialog" aria-label="Research disclaimer" className="fixed inset-x-4 top-[76px] z-50 rounded-[14px] border border-[var(--line)] bg-[var(--surface)] p-4 shadow-[0_18px_50px_var(--shadow)] sm:absolute sm:inset-x-auto sm:right-0 sm:top-12 sm:w-80">
          <div className="flex gap-3">
            <ExclamationIcon className="mt-0.5 size-5 shrink-0 text-[var(--accent)]" />
            <p className="text-sm leading-6 text-[var(--ink-soft)]">Literae helps you discover relevant research, but results and publication details may be incomplete or inaccurate. Review the original source before citing or relying on any finding.</p>
          </div>
        </div>
      )}
    </div>
  );
}
