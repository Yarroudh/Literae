import Image from "next/image";
import { PlusIcon } from "@/components/ui/icons";
import { DisclaimerPopover } from "@/components/ui/disclaimer-popover";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { HistoryPopover } from "./history-popover";

type HeaderProps = { canReset: boolean; onReset: () => void; onSelectHistory: (id: string) => void };

export function Header({ canReset, onReset, onSelectHistory }: HeaderProps) {
  return (
    <header className="sticky top-0 z-20 border-b border-[var(--line)] bg-[color:var(--topbar)] backdrop-blur">
      <div className="mx-auto flex h-[68px] w-full max-w-4xl items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-2.5">
          <Image src="/logo.png?v=3" alt="" width={32} height={32} priority unoptimized />
          <strong className="text-[17px] tracking-[-0.02em]">Literae</strong>
        </div>
        <div className="flex items-center gap-2">
          <HistoryPopover onSelect={onSelectHistory} />
          <DisclaimerPopover />
          <button type="button" onClick={onReset} disabled={!canReset} className="inline-flex h-9 items-center gap-2 rounded-[10px] border border-[var(--line)] bg-[var(--surface)] px-3 text-xs font-semibold transition hover:border-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-40" aria-label="Start a new chat">
            <PlusIcon className="size-4" /><span className="hidden sm:inline">New chat</span>
          </button>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
