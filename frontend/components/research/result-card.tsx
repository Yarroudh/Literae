import type { ResearchResult } from "@/types/research";
import { ChevronDownIcon } from "@/components/ui/icons";

export function ResultCard({ result, citationNumber }: { result: ResearchResult; citationNumber: number }) {
  return (
    <article id={`reference-${citationNumber}`} className="border-b border-[var(--line)] py-5 first:pt-0 last:border-b-0">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 shrink-0 text-sm font-semibold text-[var(--accent)]" aria-label={`Reference ${citationNumber}`}>
          [{citationNumber}]
        </span>
        <div className="min-w-0 flex-1">
          <div className="mb-1.5 flex flex-wrap items-center gap-2 text-xs text-[var(--muted)]">
            <span>{result.type}</span><span aria-hidden="true">·</span><span>{result.year}</span>
            {result.openAccess && <span className="rounded bg-[var(--accent-soft)] px-2 py-0.5 font-medium text-[var(--accent)]">Open access</span>}
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
          {result.topics.length > 0 && <div className="mt-3 flex flex-wrap gap-1.5">{result.topics.slice(0, 3).map((topic) => <span key={topic} className="rounded-md bg-[var(--panel-2)] px-2 py-1 text-[11px] text-[var(--muted)]">{topic}</span>)}</div>}
        </div>
      </div>
    </article>
  );
}
