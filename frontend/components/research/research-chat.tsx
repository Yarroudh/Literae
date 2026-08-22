"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { Header } from "@/components/chat/header";
import { CloseIcon, LoaderIcon, RefreshIcon, SendIcon } from "@/components/ui/icons";
import { ChatApiError, getConversation, streamResearch } from "@/lib/api-chat";
import { INITIAL_FILTERS, MAX_RESEARCH_REQUEST_LENGTH, sampleResearchTopics } from "@/lib/research";
import type { AuthorResult, ResearchFilters, ResearchResult } from "@/types/research";
import { AnswerMarkdown } from "./answer-markdown";
import { AuthorCard } from "./author-card";
import { ResultCard } from "./result-card";
import { FilterPopover } from "./filter-popover";

type ResearchTurn = {
  id: string;
  query: string;
  answer: string;
  results: ResearchResult[];
  showResults: boolean;
  authors: AuthorResult[];
  showAuthors: boolean;
  contextType: "papers" | "authors" | null;
  suggestions: string[];
  includedResultIds: string[];
  failed?: boolean;
  stopped?: boolean;
};

export function ResearchChat() {
  const [filters, setFilters] = useState<ResearchFilters>(INITIAL_FILTERS);
  const [turns, setTurns] = useState<ResearchTurn[]>([]);
  const [draft, setDraft] = useState("");
  const [pendingQuery, setPendingQuery] = useState("");
  const [conversationId, setConversationId] = useState<string>();
  const [isLoading, setIsLoading] = useState(false);
  const [streamStatus, setStreamStatus] = useState("");
  const [streamingAnswer, setStreamingAnswer] = useState("");
  const [includedPaperIds, setIncludedPaperIds] = useState<string[]>([]);
  const [suggestedTopics, setSuggestedTopics] = useState<string[]>([]);
  const endRef = useRef<HTMLDivElement>(null);
  const activeRequestRef = useRef<AbortController | null>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns, isLoading]);
  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setSuggestedTopics(sampleResearchTopics()));
    return () => window.cancelAnimationFrame(frame);
  }, []);

  function updateFilter(name: keyof ResearchFilters, value: string) {
    setFilters((current) => ({ ...current, [name]: value }));
  }

  function resetFilters() {
    setFilters((current) => ({ ...INITIAL_FILTERS, query: current.query }));
  }

  async function send(queryOverride?: string) {
    const query = (queryOverride ?? draft).trim();
    if (!query || isLoading) return;
    setDraft("");
    setPendingQuery(query);
    setStreamStatus("Understanding your request");
    setStreamingAnswer("");
    setIsLoading(true);
    const controller = new AbortController();
    activeRequestRef.current = controller;
    let partialAnswer = "";
    try {
      const response = await streamResearch(query, filters, conversationId, {
        ...(conversationId && includedPaperIds.length > 0 && { includedResultIds: includedPaperIds }),
        signal: controller.signal,
        onStatus: setStreamStatus,
        onAnswerDelta: (delta) => {
          partialAnswer += delta;
          setStreamingAnswer(partialAnswer);
        },
      });
      setConversationId(response.conversationId);
      setIncludedPaperIds(response.includedResultIds ?? response.results.map((result) => result.id));
      setTurns((current) => [...current, {
        id: createTurnId(),
        query,
        answer: response.answer,
        results: response.results,
        showResults: response.showResults ?? true,
        authors: response.authors,
        showAuthors: response.showAuthors ?? false,
        contextType: response.contextType ?? null,
        suggestions: response.suggestions ?? [],
        includedResultIds: response.includedResultIds ?? response.results.map((result) => result.id),
      }]);
    } catch (error) {
      const cancelled = error instanceof ChatApiError && error.code === "cancelled";
      const answer = cancelled
        ? partialAnswer
        : error instanceof ChatApiError
        ? `${error.message} Please try again.`
        : "Literae could not complete this request. Please try again.";
      setTurns((current) => [...current, {
        id: createTurnId(),
        query,
        answer,
        results: [],
        showResults: false,
        authors: [],
        showAuthors: false,
        contextType: null,
        suggestions: [],
        includedResultIds: [],
        failed: !cancelled,
        stopped: cancelled,
      }]);
    } finally {
      if (activeRequestRef.current === controller) activeRequestRef.current = null;
      setPendingQuery("");
      setStreamStatus("");
      setStreamingAnswer("");
      setIsLoading(false);
    }
  }

  function stopGeneration() {
    activeRequestRef.current?.abort();
  }

  function retry(turnId: string, query: string) {
    if (isLoading) return;
    setTurns((current) => current.filter((turn) => turn.id !== turnId));
    void send(query);
  }

  function reset() {
    setTurns([]);
    setDraft("");
    setPendingQuery("");
    setConversationId(undefined);
    setFilters(INITIAL_FILTERS);
    setSuggestedTopics(sampleResearchTopics());
    setIncludedPaperIds([]);
  }

  async function openHistory(id: string) {
    if (isLoading) return;
    setIsLoading(true);
    try {
      const conversation = await getConversation(id);
      setConversationId(conversation.id);
      const restoredTurns = conversation.turns.map((turn) => ({
        id: turn.id,
        query: turn.query,
        answer: turn.answer,
        results: turn.results,
        showResults: turn.showResults ?? true,
        authors: turn.authors,
        showAuthors: turn.showAuthors ?? false,
        contextType: turn.contextType ?? null,
        suggestions: turn.suggestions ?? [],
        includedResultIds: turn.includedResultIds?.length
          ? turn.includedResultIds
          : turn.results.map((result) => result.id),
        stopped: false,
      }));
      setTurns(restoredTurns);
      const latestPaperTurn = [...restoredTurns].reverse().find((turn) => turn.results.length > 0);
      setIncludedPaperIds(
        latestPaperTurn?.includedResultIds.length
          ? latestPaperTurn.includedResultIds
          : latestPaperTurn?.results.map((result) => result.id) ?? [],
      );
    } catch {
      // Keep the current chat intact when a saved conversation cannot be loaded.
    } finally {
      setIsLoading(false);
    }
  }

  const activePaperTurn = [...turns].reverse().find(
    (turn) => !turn.failed && turn.showResults && turn.results.length > 0,
  );
  const activePaperTurnId = activePaperTurn?.id;

  function setPaperIncluded(resultId: string, selected: boolean) {
    setIncludedPaperIds((current) => {
      if (selected) {
        const included = new Set([...current, resultId]);
        return (activePaperTurn?.results ?? []).map((result) => result.id).filter((id) => included.has(id));
      }
      if (current.length <= 1) return current;
      return current.filter((id) => id !== resultId);
    });
  }

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--background)] text-[var(--ink)]">
      <Header canReset={turns.length > 0 && !isLoading} onReset={reset} onSelectHistory={(id) => void openHistory(id)} />
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col px-4 sm:px-6">
        {turns.length === 0 && !isLoading ? (
          <section className="flex flex-1 flex-col justify-center py-12">
            <div className="max-w-2xl">
              <h1 className="text-3xl font-semibold tracking-[-0.04em] sm:text-5xl">Explore the research around any topic</h1>
              <p className="mt-3 max-w-xl text-base leading-7 text-[var(--muted)]">Describe what you are researching. Literae will help you find related academic work and understand how it connects.</p>
            </div>
            <div className="mt-8 max-w-3xl">
              <div className="mb-3 flex items-center gap-2">
                <p className="text-xs font-medium text-[var(--muted)]">Explore a topic</p>
                <button type="button" onClick={() => setSuggestedTopics(sampleResearchTopics())} className="grid size-7 place-items-center rounded-full text-[var(--muted)] transition hover:bg-[var(--panel-2)] hover:text-[var(--accent)]" aria-label="Show different topics" title="Show different topics">
                  <RefreshIcon className="size-4" />
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                {suggestedTopics.map((topic) => (
                  <button key={topic} type="button" onClick={() => send(`Find related research on ${topic}`)} className="rounded-full border border-[var(--line)] bg-[var(--surface)] px-3.5 py-2 text-left text-sm leading-5 text-[var(--ink-soft)] shadow-[0_2px_8px_var(--shadow)] transition hover:-translate-y-0.5 hover:border-[var(--accent)] hover:text-[var(--ink)] hover:shadow-[0_5px_14px_var(--shadow)]">{topic}</button>
                ))}
              </div>
            </div>
          </section>
        ) : (
          <section className="w-full flex-1 space-y-9 py-8 sm:py-10">
            {turns.map((turn, index) => (
              <div key={turn.id} className="space-y-6">
                <div className="flex justify-end"><div className="max-w-[85%] rounded-xl rounded-tr-sm bg-[var(--ink)] px-4 py-3 text-sm leading-6 text-[var(--surface)]">{turn.query}</div></div>
                <article className="flex gap-3 sm:gap-4">
                  <div className="mt-1 hidden size-9 shrink-0 place-items-center rounded-[10px] bg-[var(--accent-soft)] sm:grid"><Image src="/logo.png?v=3" alt="" width={24} height={24} unoptimized /></div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold">Literae</p>
                    <AnswerMarkdown>{turn.answer}</AnswerMarkdown>
                    {turn.stopped && (
                      <div className="mt-2 flex items-center gap-1.5 text-sm italic text-[var(--muted)]">
                        <span>Generation stopped.</span>
                        <button type="button" onClick={() => retry(turn.id, turn.query)} disabled={isLoading} className="grid size-6 place-items-center rounded-full not-italic transition hover:bg-[var(--panel-2)] hover:text-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-50" aria-label="Retry stopped prompt" title="Retry prompt">
                          <RefreshIcon className="size-3.5" />
                        </button>
                      </div>
                    )}
                    {turn.failed ? (
                      <button type="button" onClick={() => retry(turn.id, turn.query)} disabled={isLoading} className="mt-4 rounded-[9px] border border-[var(--line)] bg-[var(--surface)] px-3 py-2 text-xs font-semibold transition hover:border-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-50">Try again</button>
                    ) : turn.showResults && turn.results.length > 0 ? (
                      <div className="mt-5 rounded-[15px] border border-[var(--line)] bg-[var(--surface)] px-4 pt-5 sm:px-5">{turn.results.map((result, resultIndex) => {
                        const selectable = turn.id === activePaperTurnId;
                        const selected = !selectable || includedPaperIds.includes(result.id);
                        const citationNumber = selectable
                          ? (selected ? includedPaperIds.indexOf(result.id) + 1 : null)
                          : resultIndex + 1;
                        return <ResultCard key={result.id} result={result} citationNumber={citationNumber} selectable={selectable} selected={selected} onSelectedChange={(value) => setPaperIncluded(result.id, value)} />;
                      })}</div>
                    ) : turn.showResults ? (
                      <p className="mt-4 rounded-[15px] border border-[var(--line)] p-4 text-sm text-[var(--muted)]">No closely related works were returned. Try broader terms or adjust the research filters.</p>
                    ) : null}
                    {!turn.failed && turn.showAuthors && turn.authors.length > 0 && (
                      <div className="mt-5 grid gap-3">{turn.authors.map((author) => <AuthorCard key={author.id} author={author} />)}</div>
                    )}
                    {!turn.failed && turn.contextType === "papers" && turn.results.length > 0 && index === turns.length - 1 && (
                      <PaperFollowUpSuggestions
                        suggestions={turn.suggestions}
                        selectedCount={includedPaperIds.length}
                        totalCount={turn.results.length}
                        onSelectAll={() => setIncludedPaperIds(turn.results.map((result) => result.id))}
                        onSelect={(suggestion) => void send(suggestion)}
                      />
                    )}
                    {!turn.failed && turn.contextType === "authors" && turn.authors.length > 0 && index === turns.length - 1 && (
                      <AuthorFollowUpSuggestions authors={turn.authors} suggestions={turn.suggestions} onSelect={(suggestion) => void send(suggestion)} />
                    )}
                  </div>
                </article>
              </div>
            ))}
            {isLoading && <><div className="flex justify-end"><div className="max-w-[85%] rounded-xl rounded-tr-sm bg-[var(--ink)] px-4 py-3 text-sm leading-6 text-[var(--surface)]">{pendingQuery}</div></div><ResearchingState status={streamStatus} answer={streamingAnswer} /></>}
            <div ref={endRef} />
          </section>
        )}
      </main>

      <footer className="sticky bottom-0 border-t border-[var(--line)] bg-[color:var(--topbar)] py-3 backdrop-blur sm:py-4">
        <form className="mx-auto w-full max-w-4xl px-4 sm:px-6" onSubmit={(event) => { event.preventDefault(); send(); }}>
          <div className="flex items-end gap-2 rounded-[15px] border border-[var(--line)] bg-[var(--surface)] p-2 shadow-[0_10px_30px_var(--shadow)] focus-within:border-[var(--accent)]">
            <label htmlFor="research-request" className="sr-only">Ask Literae a question</label>
            <textarea id="research-request" rows={1} value={draft} maxLength={MAX_RESEARCH_REQUEST_LENGTH} disabled={isLoading} placeholder="Ask Literae a question" onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); send(); } }} className="block max-h-32 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-sm leading-6 outline-none placeholder:text-[var(--muted)] disabled:opacity-60" />
            <div className="flex shrink-0 items-center gap-1.5 pb-0.5">
              <FilterPopover filters={filters} onChange={updateFilter} onReset={resetFilters} />
              {isLoading ? (
                <button type="button" onClick={stopGeneration} className="grid size-9 place-items-center rounded-[9px] bg-[var(--ink)] text-[var(--surface)] transition hover:opacity-80" aria-label="Stop generating" title="Stop generating">
                  <CloseIcon className="size-4" />
                </button>
              ) : (
                <button type="submit" disabled={!draft.trim()} className="grid size-9 place-items-center rounded-[9px] bg-[var(--accent)] text-white transition hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-50" aria-label="Send message" title="Send message">
                  <SendIcon className="size-[18px]" />
                </button>
              )}
            </div>
          </div>
          <p className="mt-2 text-center text-[11px] leading-4 text-[var(--muted)]">Enter to send · Shift+Enter for a new line</p>
        </form>
      </footer>
    </div>
  );
}

function createTurnId() {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }

  return `turn-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

const FOLLOW_UP_SUGGESTIONS = [
  "Give me BibTeX code for these papers",
  "Give me RIS code for these papers",
  "Draft a concise state-of-the-art synthesis from these papers",
  "Compare the main methods and findings across these papers",
  "Give me an overview of the authors represented here",
];

const REFERENCE_STYLES = ["APA 7", "MLA 9", "IEEE", "Chicago", "Harvard", "Vancouver"];

function PaperFollowUpSuggestions({ suggestions, selectedCount, totalCount, onSelectAll, onSelect }: { suggestions: string[]; selectedCount: number; totalCount: number; onSelectAll: () => void; onSelect: (suggestion: string) => void }) {
  const [referenceStyle, setReferenceStyle] = useState(REFERENCE_STYLES[0]);

  return (
    <div className="mt-5" aria-label="Suggested follow-up questions">
      <p className="mb-2 text-xs font-medium text-[var(--muted)]">Continue exploring</p>
      <div className="mb-2 flex max-w-md items-center justify-between gap-3 rounded-[11px] border border-[var(--line)] bg-[var(--surface)] px-3 py-2.5">
        <div>
          <p className="text-xs font-semibold text-[var(--ink)]">Papers considered</p>
          <p className="text-[11px] text-[var(--muted)]">{selectedCount} of {totalCount} selected · use the checkboxes above to ignore papers</p>
        </div>
        {selectedCount < totalCount && <button type="button" onClick={onSelectAll} className="shrink-0 text-xs font-semibold text-[var(--accent)] hover:underline">Select all</button>}
      </div>
      <div className="mb-2 flex max-w-md items-center gap-2 rounded-[11px] border border-[var(--line)] bg-[var(--surface)] p-1.5">
        <label htmlFor="reference-style" className="sr-only">Reference style</label>
        <select
          id="reference-style"
          value={referenceStyle}
          onChange={(event) => setReferenceStyle(event.target.value)}
          className="min-w-0 flex-1 rounded-[8px] bg-[var(--panel-2)] px-2.5 py-2 text-xs font-medium text-[var(--ink)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
        >
          {REFERENCE_STYLES.map((style) => <option key={style}>{style}</option>)}
        </select>
        <button
          type="button"
          onClick={() => onSelect(`Format these references in ${referenceStyle}`)}
          className="shrink-0 rounded-[8px] bg-[var(--ink)] px-3 py-2 text-xs font-medium text-[var(--surface)] transition hover:opacity-85"
        >
          Format references
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        {(suggestions.length > 0 ? suggestions : FOLLOW_UP_SUGGESTIONS).map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => onSelect(suggestion)}
            className="rounded-full border border-[var(--line)] bg-[var(--surface)] px-3 py-2 text-left text-xs leading-5 text-[var(--ink-soft)] transition hover:border-[var(--accent)] hover:text-[var(--ink)]"
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}

function AuthorFollowUpSuggestions({ authors, suggestions: generatedSuggestions, onSelect }: { authors: AuthorResult[]; suggestions: string[]; onSelect: (suggestion: string) => void }) {
  const primaryName = authors[0].name;
  const fallbackSuggestions = authors.length === 1
    ? [
        `Show the most cited papers by ${primaryName}`,
        `Show the newest papers by ${primaryName}`,
        `Find all papers by ${primaryName}`,
      ]
    : [
        "Compare these researcher profiles",
        "Which researcher has the highest h-index?",
        "Summarize each researcher's main topics",
      ];
  const suggestions = generatedSuggestions.length > 0 ? generatedSuggestions : fallbackSuggestions;

  return (
    <div className="mt-5" aria-label="Suggested author follow-up questions">
      <p className="mb-2 text-xs font-medium text-[var(--muted)]">Explore this researcher</p>
      <div className="flex flex-wrap gap-2">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => onSelect(suggestion)}
            className="rounded-full border border-[var(--line)] bg-[var(--surface)] px-3 py-2 text-left text-xs leading-5 text-[var(--ink-soft)] transition hover:border-[var(--accent)] hover:text-[var(--ink)]"
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}

function ResearchingState({ status, answer }: { status: string; answer: string }) {
  return (
    <article className="flex gap-3 sm:gap-4" aria-live="polite">
      <div className="mt-1 hidden size-9 shrink-0 place-items-center rounded-[10px] bg-[var(--accent-soft)] sm:grid"><Image src="/logo.png?v=3" alt="" width={24} height={24} unoptimized /></div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold">Literae</p>
        {answer ? <AnswerMarkdown>{answer}</AnswerMarkdown> : (
          <div className="mt-3 flex items-center gap-3 text-sm text-[var(--muted)]" role="status">
            <LoaderIcon className="size-4 animate-spin text-[var(--accent)]" />
            <span>{status || "Working on your research"}</span>
            <span className="flex items-center gap-1" aria-hidden="true"><span className="loading-dot" /><span className="loading-dot" /><span className="loading-dot" /></span>
          </div>
        )}
      </div>
    </article>
  );
}
