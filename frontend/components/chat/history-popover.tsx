"use client";

import { useEffect, useRef, useState } from "react";
import { deleteConversation, listConversations, type ConversationSummary } from "@/lib/api-chat";
import { HistoryIcon, LoaderIcon, TrashIcon } from "@/components/ui/icons";

export function HistoryPopover({ onSelect }: { onSelect: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function close(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  async function load() {
    setLoading(true);
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

  async function remove(id: string) {
    await deleteConversation(id);
    setItems((current) => current.filter((item) => item.id !== id));
  }

  return (
    <div ref={rootRef} className="relative">
      <button type="button" onClick={toggle} className="grid size-9 place-items-center rounded-[10px] border border-[var(--line)] bg-[var(--surface)] text-[var(--ink-soft)] transition hover:border-[var(--accent)] hover:text-[var(--accent)]" aria-label="Conversation history" title="Conversation history">
        <HistoryIcon className="size-[18px]" />
      </button>
      {open && (
        <div className="absolute right-0 top-11 z-50 w-[min(22rem,calc(100vw-2rem))] overflow-hidden rounded-[14px] border border-[var(--line)] bg-[var(--surface)] shadow-[0_18px_55px_var(--shadow)]">
          <div className="border-b border-[var(--line)] px-4 py-3"><p className="text-sm font-semibold">Recent chats</p></div>
          <div className="max-h-80 overflow-y-auto p-2">
            {loading ? <div className="grid h-20 place-items-center"><LoaderIcon className="size-5 animate-spin text-[var(--accent)]" /></div> : items.length === 0 ? <p className="px-3 py-6 text-center text-xs text-[var(--muted)]">No saved chats yet.</p> : items.map((item) => (
              <div key={item.id} className="group flex items-center gap-1 rounded-[9px] hover:bg-[var(--panel-2)]">
                <button type="button" onClick={() => { onSelect(item.id); setOpen(false); }} className="min-w-0 flex-1 px-3 py-2.5 text-left"><span className="block truncate text-xs font-medium">{item.title}</span><span className="mt-0.5 block text-[10px] text-[var(--muted)]">{new Date(item.updatedAt).toLocaleDateString()}</span></button>
                <button type="button" onClick={() => void remove(item.id)} className="mr-2 grid size-7 place-items-center rounded-md text-[var(--muted)] opacity-0 transition hover:bg-[var(--surface)] hover:text-red-500 group-hover:opacity-100 focus:opacity-100" aria-label={`Delete ${item.title}`}><TrashIcon className="size-4" /></button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
