import type { AuthorResult, ResearchFilters, ResearchResult } from "@/types/research";

export type ChatResponse = {
  conversationId: string;
  answer: string;
  results: ResearchResult[];
  showResults?: boolean;
  authors: AuthorResult[];
  showAuthors?: boolean;
  contextType?: "papers" | "authors" | null;
  suggestions?: string[];
};

export type ConversationSummary = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
};

export type ConversationHistory = ConversationSummary & {
  turns: Array<Omit<ChatResponse, "conversationId"> & { id: string; query: string; createdAt: string }>;
};

type RequestOptions = {
  baseUrl?: string;
  fetcher?: typeof fetch;
  timeoutMs?: number;
};

export type ChatApiErrorCode = "timeout" | "network" | "server" | "invalid-response";

export class ChatApiError extends Error {
  constructor(
    public readonly code: ChatApiErrorCode,
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = "ChatApiError";
  }
}

export async function requestResearch(
  message: string,
  filters: ResearchFilters,
  conversationId?: string,
  options: RequestOptions = {},
): Promise<ChatResponse> {
  const fetcher = options.fetcher ?? fetch;
  const baseUrl = (options.baseUrl ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort(), options.timeoutMs ?? 120_000);

  try {
    const response = await fetcher(`${baseUrl}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: message.trim(),
        filters: toApiFilters(filters),
        ...(conversationId && { conversationId }),
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const body: unknown = await response.json().catch(() => null);
      if (isErrorDetail(body)) {
        throw new ChatApiError("server", body.detail, response.status);
      }
      throw new ChatApiError("server", "The research service could not complete this request.", response.status);
    }

    const data: unknown = await response.json();
    if (!isChatResponse(data)) {
      throw new ChatApiError("invalid-response", "The research service returned an unexpected response.");
    }
    return data;
  } catch (error) {
    if (error instanceof ChatApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ChatApiError("timeout", "The research request took too long.");
    }
    throw new ChatApiError("network", "Literae could not reach the research service.");
  } finally {
    globalThis.clearTimeout(timeout);
  }
}

export async function listConversations(options: RequestOptions = {}): Promise<ConversationSummary[]> {
  const data = await historyRequest("/conversations", options);
  if (!Array.isArray(data)) throw new ChatApiError("invalid-response", "Conversation history is unavailable.");
  return data as ConversationSummary[];
}

export async function getConversation(
  conversationId: string,
  options: RequestOptions = {},
): Promise<ConversationHistory> {
  return await historyRequest(`/conversations/${encodeURIComponent(conversationId)}`, options) as ConversationHistory;
}

export async function deleteConversation(
  conversationId: string,
  options: RequestOptions = {},
): Promise<void> {
  await historyRequest(`/conversations/${encodeURIComponent(conversationId)}`, options, "DELETE");
}

async function historyRequest(path: string, options: RequestOptions, method = "GET"): Promise<unknown> {
  const fetcher = options.fetcher ?? fetch;
  const baseUrl = (options.baseUrl ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
  const response = await fetcher(`${baseUrl}${path}`, { method });
  if (!response.ok) throw new ChatApiError("server", "Conversation history could not be loaded.", response.status);
  if (response.status === 204) return undefined;
  return await response.json();
}

function isErrorDetail(value: unknown): value is { detail: string } {
  return Boolean(
    value
    && typeof value === "object"
    && "detail" in value
    && typeof value.detail === "string",
  );
}

function toApiFilters(filters: ResearchFilters) {
  return {
    ...(filters.fromYear && { fromYear: Number(filters.fromYear) }),
    ...(filters.toYear && { toYear: Number(filters.toYear) }),
    ...(filters.workType !== "all" && { workType: filters.workType }),
    ...(filters.openAccess !== "all" && { openAccess: filters.openAccess }),
    ...(filters.language !== "all" && { language: filters.language }),
    ...(filters.author.trim() && { author: filters.author.trim() }),
    ...(filters.institution.trim() && { institution: filters.institution.trim() }),
    ...(filters.source.trim() && { source: filters.source.trim() }),
    sort: filters.sort,
    resultsLimit: Number(filters.resultsLimit),
  };
}

function isChatResponse(value: unknown): value is ChatResponse {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<ChatResponse>;
  return typeof candidate.conversationId === "string"
    && typeof candidate.answer === "string"
    && (candidate.showResults === undefined || typeof candidate.showResults === "boolean")
    && Array.isArray(candidate.results)
    && candidate.results.every(isResearchResult)
    && Array.isArray(candidate.authors)
    && candidate.authors.every(isAuthorResult)
    && (candidate.showAuthors === undefined || typeof candidate.showAuthors === "boolean")
    && (candidate.suggestions === undefined || (Array.isArray(candidate.suggestions) && candidate.suggestions.every((item) => typeof item === "string")))
    && (candidate.contextType == null || candidate.contextType === "papers" || candidate.contextType === "authors");
}

function isAuthorResult(value: unknown): value is AuthorResult {
  if (!value || typeof value !== "object") return false;
  const author = value as Partial<AuthorResult>;
  return typeof author.id === "string"
    && typeof author.name === "string"
    && (author.orcid == null || typeof author.orcid === "string")
    && typeof author.worksCount === "number"
    && typeof author.citedByCount === "number"
    && typeof author.hIndex === "number"
    && typeof author.i10Index === "number"
    && Array.isArray(author.affiliations)
    && author.affiliations.every((item) => typeof item === "string")
    && Array.isArray(author.topics)
    && author.topics.every((item) => typeof item === "string")
    && typeof author.openAlexUrl === "string";
}

function isResearchResult(value: unknown): value is ResearchResult {
  if (!value || typeof value !== "object") return false;
  const result = value as Partial<ResearchResult>;
  return typeof result.id === "string"
    && typeof result.title === "string"
    && Array.isArray(result.authors)
    && result.authors.every((author) => typeof author === "string")
    && typeof result.year === "number"
    && typeof result.source === "string"
    && typeof result.type === "string"
    && typeof result.openAccess === "boolean"
    && typeof result.citedByCount === "number"
    && Array.isArray(result.topics)
    && result.topics.every((topic) => typeof topic === "string")
    && typeof result.summary === "string"
    && (result.doi == null || typeof result.doi === "string");
}
