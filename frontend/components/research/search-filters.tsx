import type { ResearchFilters } from "@/types/research";

type SearchFiltersProps = {
  filters: ResearchFilters;
  onChange: (name: keyof ResearchFilters, value: string) => void;
};

const controlClass = "h-10 w-full rounded-[10px] border border-[var(--line)] bg-[var(--panel-2)] px-3 text-sm text-[var(--ink)] outline-none transition placeholder:text-[var(--muted)] focus:border-[var(--accent)] focus:bg-[var(--surface)] focus:ring-2 focus:ring-[var(--accent-soft)]";

export function SearchFilters({ filters, onChange }: SearchFiltersProps) {
  return (
    <div className="space-y-5">
      <FilterGroup title="Publication">
        <Field label="From year"><input className={controlClass} type="number" min="1000" max="2100" placeholder="Any year" value={filters.fromYear} onChange={(event) => onChange("fromYear", event.target.value)} /></Field>
        <Field label="To year"><input className={controlClass} type="number" min="1000" max="2100" placeholder="Present" value={filters.toYear} onChange={(event) => onChange("toYear", event.target.value)} /></Field>
        <Field label="Work type"><select className={controlClass} value={filters.workType} onChange={(event) => onChange("workType", event.target.value)}><option value="all">All types</option><option value="article">Article</option><option value="preprint">Preprint</option><option value="conference">Conference paper</option><option value="book">Book or chapter</option><option value="dataset">Dataset</option><option value="review">Review</option></select></Field>
        <Field label="Access"><select className={controlClass} value={filters.openAccess} onChange={(event) => onChange("openAccess", event.target.value)}><option value="all">Any access</option><option value="open">Open access</option><option value="closed">Closed access</option></select></Field>
      </FilterGroup>
      <FilterGroup title="Research context">
        <Field label="Language"><select className={controlClass} value={filters.language} onChange={(event) => onChange("language", event.target.value)}><option value="all">Any language</option><option value="en">English</option><option value="fr">French</option><option value="de">German</option><option value="es">Spanish</option><option value="nl">Dutch</option></select></Field>
        <Field label="Author"><input className={controlClass} placeholder="Author name" value={filters.author} onChange={(event) => onChange("author", event.target.value)} /></Field>
        <Field label="Institution"><input className={controlClass} placeholder="University or institute" value={filters.institution} onChange={(event) => onChange("institution", event.target.value)} /></Field>
        <Field label="Journal or source"><input className={controlClass} placeholder="Publication source" value={filters.source} onChange={(event) => onChange("source", event.target.value)} /></Field>
      </FilterGroup>
    </div>
  );
}

function FilterGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return <section><p className="mb-3 text-[11px] font-bold uppercase tracking-[.08em] text-[var(--muted)]">{title}</p><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{children}</div></section>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="grid gap-1.5 text-xs font-semibold text-[var(--ink-soft)]"><span>{label}</span>{children}</label>;
}
