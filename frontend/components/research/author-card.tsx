import type { AuthorResult } from "@/types/research";

export function AuthorCard({ author }: { author: AuthorResult }) {
  return (
    <article className="rounded-[15px] border border-[var(--line)] bg-[var(--surface)] p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold tracking-[-0.015em] text-[var(--ink)]">{author.name}</h2>
          {author.affiliations.length > 0 && (
            <p className="mt-1 text-sm text-[var(--muted)]">{author.affiliations.join(" · ")}</p>
          )}
        </div>
        <div className="flex gap-2 text-xs font-medium">
          {author.orcid && <a href={author.orcid} target="_blank" rel="noreferrer" className="rounded-md border border-[var(--line)] px-2.5 py-1.5 text-[var(--ink-soft)] hover:border-[var(--accent)]">ORCID</a>}
          <a href={author.openAlexUrl} target="_blank" rel="noreferrer" className="rounded-md border border-[var(--line)] px-2.5 py-1.5 text-[var(--ink-soft)] hover:border-[var(--accent)]">OpenAlex</a>
        </div>
      </div>
      <dl className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Metric label="Works" value={author.worksCount} />
        <Metric label="Citations" value={author.citedByCount} />
        <Metric label="h-index" value={author.hIndex} />
        <Metric label="i10-index" value={author.i10Index} />
      </dl>
      {author.topics.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {author.topics.map((topic) => <span key={topic} className="rounded-md bg-[var(--panel-2)] px-2.5 py-1 text-xs text-[var(--muted)]">{topic}</span>)}
        </div>
      )}
    </article>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-[10px] bg-[var(--panel-2)] px-3 py-2.5">
      <dt className="text-[11px] text-[var(--muted)]">{label}</dt>
      <dd className="mt-0.5 text-base font-semibold text-[var(--ink)]">{value.toLocaleString()}</dd>
    </div>
  );
}
