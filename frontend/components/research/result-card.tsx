import type { ResearchResult } from "@/types/research";
import { ChevronDownIcon } from "@/components/ui/icons";

type ResultCardProps = {
  result: ResearchResult;
  citationNumber: number | null;
  selectable?: boolean;
  selected?: boolean;
  onSelectedChange?: (selected: boolean) => void;
};

export function ResultCard({ result, citationNumber, selectable = false, selected = true, onSelectedChange }: ResultCardProps) {
  return (
    <article id={citationNumber ? `reference-${citationNumber}` : undefined} className={`border-b border-[var(--line)] py-5 first:pt-0 last:border-b-0 ${selected ? "" : "opacity-55"}`}>
      <div className="flex items-start gap-3">
        <span className="mt-0.5 min-w-7 shrink-0 text-sm font-semibold text-[var(--accent)]" aria-label={citationNumber ? `Reference ${citationNumber}` : "Excluded from follow-up analysis"}>
          {citationNumber ? `[${citationNumber}]` : "—"}
        </span>
        <div className="min-w-0 flex-1">
          <div className="mb-1.5 flex items-center gap-2 text-xs text-[var(--muted)]">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <span>{result.type}</span><span aria-hidden="true">·</span><span>{result.year}</span>
              {result.openAccess && <span className="rounded bg-[var(--accent-soft)] px-2 py-0.5 font-medium text-[var(--accent)]">Open access</span>}
            </div>
            {selectable && (
              <label className="ml-auto flex shrink-0 cursor-pointer items-center" title={selected ? "Included in follow-up analysis" : "Ignored in follow-up analysis"}>
                <input type="checkbox" checked={selected} onChange={(event) => onSelectedChange?.(event.target.checked)} className="size-3.5 accent-[var(--accent)]" aria-label={`${selected ? "Ignore" : "Include"} ${result.title}`} />
              </label>
            )}
          </div>
          <h2 className="text-base font-semibold leading-6 tracking-[-0.01em] text-[var(--ink)] sm:text-[17px]">
            {result.doi ? <a href={result.doi} target="_blank" rel="noreferrer" className="hover:text-[var(--accent)] hover:underline">{result.title}</a> : result.title}
          </h2>
          <p className="mt-1 text-sm leading-5 text-[var(--muted)]">{result.authors.join(", ")}</p>
          <p className="mt-1 text-xs text-[var(--muted)]">{result.source} · Cited by {result.citedByCount.toLocaleString()}</p>
          {result.summary && (
            <details className="group mt-3">
              <summary className="flex w-fit cursor-pointer list-none items-center gap-1.5 text-xs font-medium text-[var(--ink-soft)] transition hover:text-[var(--accent)] [&::-webkit-details-marker]:hidden">
                <span className="group-open:hidden">Show abstract</span>
                <span className="hidden group-open:inline">Hide abstract</span>
                <ChevronDownIcon className="size-4 transition-transform group-open:rotate-180" />
              </summary>
              <p className="mt-2 max-w-3xl border-l-2 border-[var(--line)] pl-3 text-sm leading-6 text-[var(--ink-soft)]">{result.summary}</p>
            </details>
          )}
          {result.topics.length > 0 && <div className="mt-3 flex flex-wrap gap-1.5">{result.topics.slice(0, 3).map((topic, topicIndex) => <span key={`${result.id}-topic-${topicIndex}`} className="rounded-md bg-[var(--panel-2)] px-2 py-1 text-[11px] text-[var(--muted)]">{topic}</span>)}</div>}
        </div>
      </div>
    </article>
  );
}
