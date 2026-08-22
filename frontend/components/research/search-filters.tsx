import type { ResearchFilters } from "@/types/research";

type SearchFiltersProps = {
  filters: ResearchFilters;
  onChange: (name: keyof ResearchFilters, value: string) => void;
};

const controlClass = "h-11 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3.5 text-sm text-[var(--ink)] outline-none transition placeholder:text-[var(--muted)] hover:border-[var(--ink-soft)] focus:border-[var(--accent)] focus:ring-4 focus:ring-[var(--accent-soft)]";

export function SearchFilters({ filters, onChange }: SearchFiltersProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <FilterGroup title="Retrieval">
        <div className="col-span-full">
          <span className="mb-2 block text-xs font-semibold text-[var(--ink-soft)]">Maximum papers to retrieve</span>
          <div className="grid grid-cols-4 gap-2" role="group" aria-label="Maximum papers to retrieve">
            {["10", "25", "50", "100"].map((limit) => (
              <button key={limit} type="button" onClick={() => onChange("resultsLimit", limit)} aria-pressed={filters.resultsLimit === limit} className={`h-10 rounded-xl border text-sm font-semibold transition ${filters.resultsLimit === limit ? "border-[var(--accent)] bg-[var(--accent)] text-white shadow-sm" : "border-[var(--line)] bg-[var(--surface)] text-[var(--ink-soft)] hover:border-[var(--accent)] hover:text-[var(--accent)]"}`}>{limit}</button>
            ))}
          </div>
          <p className="mt-2 text-[11px] leading-4 text-[var(--muted)]">All retrieved papers are displayed and considered when Literae composes an answer.</p>
        </div>
        <Field label="Order by"><select className={controlClass} value={filters.sort} onChange={(event) => onChange("sort", event.target.value)}><option value="relevance">Most relevant</option><option value="cited">Most cited</option><option value="newest">Newest first</option><option value="oldest">Oldest first</option></select></Field>
        <Field label="Access"><select className={controlClass} value={filters.openAccess} onChange={(event) => onChange("openAccess", event.target.value)}><option value="all">Any access</option><option value="open">Open access</option><option value="closed">Closed access</option></select></Field>
      </FilterGroup>
      <FilterGroup title="Publication">
        <Field label="From year"><input className={controlClass} type="number" min="1000" max="2100" placeholder="Any year" value={filters.fromYear} onChange={(event) => onChange("fromYear", event.target.value)} /></Field>
        <Field label="To year"><input className={controlClass} type="number" min="1000" max="2100" placeholder="Present" value={filters.toYear} onChange={(event) => onChange("toYear", event.target.value)} /></Field>
        <Field label="Work type"><select className={controlClass} value={filters.workType} onChange={(event) => onChange("workType", event.target.value)}><option value="all">All types</option><option value="article">Article</option><option value="preprint">Preprint</option><option value="conference">Conference paper</option><option value="book">Book or chapter</option><option value="dataset">Dataset</option><option value="review">Review</option></select></Field>
        <Field label="Language"><select className={controlClass} value={filters.language} onChange={(event) => onChange("language", event.target.value)}><option value="all">Any language</option><option value="en">English</option><option value="fr">French</option><option value="de">German</option><option value="es">Spanish</option><option value="nl">Dutch</option></select></Field>
      </FilterGroup>
      <FilterGroup title="Research context" wide>
        <Field label="Author"><input className={controlClass} placeholder="Author name" value={filters.author} onChange={(event) => onChange("author", event.target.value)} /></Field>
        <Field label="Institution"><input className={controlClass} placeholder="University or institute" value={filters.institution} onChange={(event) => onChange("institution", event.target.value)} /></Field>
        <Field label="Journal or source"><input className={controlClass} placeholder="Publication source" value={filters.source} onChange={(event) => onChange("source", event.target.value)} /></Field>
      </FilterGroup>
    </div>
  );
}

function FilterGroup({ title, wide = false, children }: { title: string; wide?: boolean; children: React.ReactNode }) {
  return <section className={`rounded-2xl border border-[var(--line)] bg-[var(--panel-2)] p-4 sm:p-5 ${wide ? "md:col-span-2" : ""}`}><h3 className="text-sm font-bold text-[var(--ink)]">{title}</h3><div className={`mt-4 grid gap-3 ${wide ? "sm:grid-cols-3" : "sm:grid-cols-2"}`}>{children}</div></section>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="grid gap-1.5 text-xs font-semibold text-[var(--ink-soft)]"><span>{label}</span>{children}</label>;
}
