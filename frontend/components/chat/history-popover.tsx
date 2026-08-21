"use client";

import { useEffect, useRef, useState } from "react";
import { deleteConversation, listConversations, type ConversationSummary } from "@/lib/api-chat";
import { HistoryIcon, LoaderIcon, TrashIcon } from "@/components/ui/icons";

export function HistoryPopover({ onSelect }: { onSelect: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [deletingId, setDeletingId] = useState<string>();
  const [deleteError, setDeleteError] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function close(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function closeWithKeyboard(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", closeWithKeyboard);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", closeWithKeyboard);
    };
  }, [open]);

  async function load() {
    setLoading(true);
    setDeleteError("");
    try {
      setItems(await listConversations());
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next) void load();
  }

  async function remove(event: React.MouseEvent<HTMLButtonElement>, id: string) {
    event.preventDefault();
    event.stopPropagation();
    if (deletingId) return;
    setDeletingId(id);
    setDeleteError("");
    try {
      await deleteConversation(id);
      setItems((current) => current.filter((item) => item.id !== id));
    } catch {
      setDeleteError("This chat could not be deleted. Please try again.");
    } finally {
      setDeletingId(undefined);
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <button type="button" onClick={toggle} className="grid size-9 place-items-center rounded-[10px] border border-[var(--line)] bg-[var(--surface)] text-[var(--ink-soft)] transition hover:border-[var(--accent)] hover:text-[var(--accent)]" aria-label="Conversation history" title="Conversation history">
        <HistoryIcon className="size-[18px]" />
      </button>
      {open && (
        <div className="fixed inset-x-4 top-[76px] z-50 overflow-hidden rounded-[14px] border border-[var(--line)] bg-[var(--surface)] shadow-[0_18px_55px_var(--shadow)] sm:absolute sm:inset-x-auto sm:right-0 sm:top-11 sm:w-[22rem]">
          <div className="border-b border-[var(--line)] px-4 py-3"><p className="text-sm font-semibold">Recent chats</p></div>
          {deleteError && <p role="alert" className="border-b border-[var(--line)] bg-red-500/10 px-4 py-2.5 text-xs text-red-600 dark:text-red-400">{deleteError}</p>}
          <div className="max-h-80 overflow-y-auto p-2">
            {loading ? <div className="grid h-20 place-items-center"><LoaderIcon className="size-5 animate-spin text-[var(--accent)]" /></div> : items.length === 0 ? <p className="px-3 py-6 text-center text-xs text-[var(--muted)]">No saved chats yet.</p> : items.map((item) => (
              <div key={item.id} className="group flex items-center gap-1 rounded-[9px] hover:bg-[var(--panel-2)]">
                <button type="button" onClick={() => { onSelect(item.id); setOpen(false); }} className="min-w-0 flex-1 px-3 py-2.5 text-left"><span className="block truncate text-xs font-medium">{item.title}</span><span className="mt-0.5 block text-[10px] text-[var(--muted)]">{new Date(item.updatedAt).toLocaleDateString()}</span></button>
                <button type="button" onClick={(event) => void remove(event, item.id)} disabled={Boolean(deletingId)} className="mr-2 grid size-8 shrink-0 place-items-center rounded-md text-[var(--muted)] opacity-100 transition hover:bg-[var(--surface)] hover:text-red-500 disabled:cursor-wait disabled:opacity-40 sm:size-7 sm:opacity-0 sm:group-hover:opacity-100 sm:focus:opacity-100" aria-label={`Delete ${item.title}`} title={`Delete ${item.title}`}>{deletingId === item.id ? <LoaderIcon className="size-4 animate-spin" /> : <TrashIcon className="size-4" />}</button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
