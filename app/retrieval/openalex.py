import asyncio
import re
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

import httpx

from app.api.schemas import AuthorResult, ResearchFilters, ResearchResult

_MAX_LINKED_WORKS = 50


class OpenAlexError(RuntimeError):
    """Raised when publication search cannot return usable results."""


class OpenAlexTimeoutError(OpenAlexError):
    """Raised when publication search exceeds its configured timeout."""


class ResearchSearcher(Protocol):
    async def search(
        self, query: str, filters: ResearchFilters, *, page: int = 1
    ) -> list[ResearchResult]: ...

    async def search_authors(self, names: Sequence[str]) -> list[AuthorResult]: ...

    async def get_work(self, work_id: str) -> ResearchResult | None: ...

    async def get_related_works(self, work_id: str) -> list[ResearchResult]: ...

    async def get_citing_works(self, work_id: str) -> list[ResearchResult]: ...

    async def get_referenced_works(self, work_id: str) -> list[ResearchResult]: ...


class OpenAlexClient:
    def __init__(
        self,
        *,
        base_url: str = "https://api.openalex.org",
        api_key: str | None = None,
        email: str | None = None,
        results_limit: int = 10,
        timeout_seconds: float = 15,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._email = email
        self._results_limit = results_limit
        self._timeout_seconds = timeout_seconds
        self._client = client

    async def search(
        self, query: str, filters: ResearchFilters, *, page: int = 1
    ) -> list[ResearchResult]:
        try:
            if self._client is not None:
                return await self._search(self._client, query, filters, page)
            else:
                async with httpx.AsyncClient(
                    base_url=self._base_url,
                    timeout=self._timeout_seconds,
                    headers={"User-Agent": "Literae/0.1"},
                ) as client:
                    return await self._search(client, query, filters, page)
        except httpx.TimeoutException as error:
            raise OpenAlexTimeoutError("OpenAlex request timed out") from error
        except (httpx.HTTPError, ValueError) as error:
            raise OpenAlexError("OpenAlex request failed") from error

    async def search_authors(self, names: Sequence[str]) -> list[AuthorResult]:
        cleaned_names = list(dict.fromkeys(name.strip() for name in names if name.strip()))[:5]
        if not cleaned_names:
            return []
        try:
            if self._client is not None:
                return await self._search_authors(self._client, cleaned_names)
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout_seconds,
                headers={"User-Agent": "Literae/0.1"},
            ) as client:
                return await self._search_authors(client, cleaned_names)
        except httpx.TimeoutException as error:
            raise OpenAlexTimeoutError("OpenAlex request timed out") from error
        except (httpx.HTTPError, ValueError) as error:
            raise OpenAlexError("OpenAlex request failed") from error

    async def get_work(self, work_id: str) -> ResearchResult | None:
        async def operation(client: httpx.AsyncClient) -> ResearchResult | None:
            response = await client.get(
                f"/works/{_clean_openalex_id(work_id, 'W')}", params=self._access_params()
            )
            response.raise_for_status()
            payload = response.json()
            return _normalize_work(payload) if isinstance(payload, Mapping) else None

        return await self._with_client(operation)

    async def get_related_works(self, work_id: str) -> list[ResearchResult]:
        raw_work = await self._get_raw_work(work_id)
        return await self._get_works_by_ids(raw_work.get("related_works"))

    async def get_citing_works(self, work_id: str) -> list[ResearchResult]:
        return await self._get_works_by_filter(f"cites:{_clean_openalex_id(work_id, 'W')}")

    async def get_referenced_works(self, work_id: str) -> list[ResearchResult]:
        raw_work = await self._get_raw_work(work_id)
        return await self._get_works_by_ids(raw_work.get("referenced_works"))

    async def _get_raw_work(self, work_id: str) -> Mapping[str, Any]:
        async def operation(client: httpx.AsyncClient) -> Mapping[str, Any]:
            response = await client.get(
                f"/works/{_clean_openalex_id(work_id, 'W')}", params=self._access_params()
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, Mapping):
                raise OpenAlexError("OpenAlex returned an invalid response")
            return payload

        return await self._with_client(operation)

    async def _get_works_by_ids(self, value: object) -> list[ResearchResult]:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            return []
        ids = [_short_openalex_id(item) for item in value]
        cleaned = [identifier for identifier in ids if identifier.startswith("W")][
            :_MAX_LINKED_WORKS
        ]
        if not cleaned:
            return []
        return await self._get_works_by_filter(f"openalex_id:{'|'.join(cleaned)}")

    async def _get_works_by_filter(self, filter_value: str) -> list[ResearchResult]:
        async def operation(client: httpx.AsyncClient) -> list[ResearchResult]:
            params: dict[str, str | int] = {
                "filter": filter_value,
                "per-page": self._results_limit,
            }
            self._add_access_params(params)
            response = await client.get("/works", params=params)
            response.raise_for_status()
            payload = response.json()
            raw_results = payload.get("results") if isinstance(payload, Mapping) else None
            if not isinstance(raw_results, list):
                raise OpenAlexError("OpenAlex returned an invalid response")
            return [
                result
                for work in raw_results
                if isinstance(work, Mapping)
                if (result := _normalize_work(work)) is not None
            ]

        return await self._with_client(operation)

    async def _with_client(self, operation: Any) -> Any:
        try:
            if self._client is not None:
                return await operation(self._client)
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout_seconds,
                headers={"User-Agent": "Literae/0.1"},
            ) as client:
                return await operation(client)
        except httpx.TimeoutException as error:
            raise OpenAlexTimeoutError("OpenAlex request timed out") from error
        except (httpx.HTTPError, ValueError) as error:
            raise OpenAlexError("OpenAlex request failed") from error

    def _access_params(self) -> dict[str, str | int]:
        params: dict[str, str | int] = {}
        self._add_access_params(params)
        return params

    async def _search_authors(
        self, client: httpx.AsyncClient, names: Sequence[str]
    ) -> list[AuthorResult]:
        authors: list[AuthorResult] = []
        for name in names:
            params: dict[str, str | int] = {"search": name, "per-page": 3}
            self._add_access_params(params)
            response = await client.get("/authors", params=params)
            response.raise_for_status()
            payload = response.json()
            raw_results = payload.get("results") if isinstance(payload, Mapping) else None
            if not isinstance(raw_results, list):
                raise OpenAlexError("OpenAlex returned an invalid response")
            match = _best_author_match(name, raw_results)
            if match is not None:
                normalized = _normalize_author(match)
                if normalized is not None and all(author.id != normalized.id for author in authors):
                    authors.append(normalized)
        return authors

    async def _search(
        self,
        client: httpx.AsyncClient,
        query: str,
        filters: ResearchFilters,
        page: int,
    ) -> list[ResearchResult]:
        entity_ids = await self._resolve_filter_ids(client, filters)
        if any(
            requested and entity_ids[name] is None
            for name, requested in {
                "author": filters.author,
                "institution": filters.institution,
                "source": filters.source,
            }.items()
        ):
            return []

        params = self._build_params(query, filters, entity_ids, page)
        response = await client.get("/works", params=params)
        response.raise_for_status()
        payload = response.json()
        raw_results = payload.get("results") if isinstance(payload, Mapping) else None
        if not isinstance(raw_results, list):
            raise OpenAlexError("OpenAlex returned an invalid response")

        results: list[ResearchResult] = []
        for work in raw_results:
            if not isinstance(work, Mapping):
                continue
            normalized = _normalize_work(work)
            if normalized is not None:
                results.append(normalized)
        return results

    async def _resolve_filter_ids(
        self,
        client: httpx.AsyncClient,
        filters: ResearchFilters,
    ) -> dict[str, str | None]:
        lookups = {
            "author": ("/authors", filters.author),
            "institution": ("/institutions", filters.institution),
            "source": ("/sources", filters.source),
        }
        requested = [(name, path, value) for name, (path, value) in lookups.items() if value]
        resolved = {"author": None, "institution": None, "source": None}
        if not requested:
            return resolved

        ids = await asyncio.gather(
            *(self._resolve_entity_id(client, path, value or "") for _, path, value in requested)
        )
        for (name, _, _), identifier in zip(requested, ids, strict=True):
            resolved[name] = identifier
        return resolved

    async def _resolve_entity_id(
        self, client: httpx.AsyncClient, path: str, display_name: str
    ) -> str | None:
        params: dict[str, str | int] = {
            "search": display_name.strip(),
            "per-page": 1,
            "select": "id",
        }
        self._add_access_params(params)
        response = await client.get(path, params=params)
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results") if isinstance(payload, Mapping) else None
        if not isinstance(results, list) or not results or not isinstance(results[0], Mapping):
            return None
        return _short_openalex_id(results[0].get("id")) or None

    def _build_params(
        self,
        query: str,
        filters: ResearchFilters,
        entity_ids: Mapping[str, str | None],
        page: int,
    ) -> dict[str, str | int]:
        params: dict[str, str | int] = {
            "per-page": self._results_limit,
            "page": max(page, 1),
        }
        if query.strip() and not _is_author_catalog_request(query, filters):
            params["search"] = query.strip()
        openalex_filters = _build_filters(filters, entity_ids)
        if openalex_filters:
            params["filter"] = ",".join(openalex_filters)
        sort = {
            "newest": "publication_date:desc",
            "oldest": "publication_date:asc",
            "cited": "cited_by_count:desc",
        }.get(filters.sort)
        if sort:
            params["sort"] = sort
        self._add_access_params(params)
        return params

    def _add_access_params(self, params: dict[str, str | int]) -> None:
        if self._api_key:
            params["api_key"] = self._api_key
        if self._email:
            params["mailto"] = self._email


def _build_filters(filters: ResearchFilters, entity_ids: Mapping[str, str | None]) -> list[str]:
    values: list[str] = []
    if filters.from_year is not None:
        values.append(f"from_publication_date:{filters.from_year}-01-01")
    if filters.to_year is not None:
        values.append(f"to_publication_date:{filters.to_year}-12-31")
    if filters.work_type:
        values.append(f"type:{_clean_filter_value(filters.work_type)}")
    if filters.open_access:
        values.append(f"is_oa:{str(filters.open_access == 'open').lower()}")
    if filters.language:
        values.append(f"language:{_clean_filter_value(filters.language.lower())}")
    if entity_ids.get("author"):
        values.append(f"author.id:{entity_ids['author']}")
    if entity_ids.get("institution"):
        values.append(f"institution.id:{entity_ids['institution']}")
    if entity_ids.get("source"):
        values.append(f"primary_location.source.id:{entity_ids['source']}")
    return values


def _clean_filter_value(value: str) -> str:
    return value.strip().replace(",", " ")


def _is_author_catalog_request(query: str, filters: ResearchFilters) -> bool:
    if not filters.author:
        return False
    normalized = " ".join(query.casefold().split())
    publication_terms = r"papers?|works?|publications?|articles?|research"
    return bool(
        re.search(rf"\b{publication_terms}\b.*\b(this|the|that) author\b", normalized)
        or re.search(rf"\b(all|list|show|find|get)\b.*\b{publication_terms}\b.*\bby\b", normalized)
        or re.fullmatch(rf"(?:find|show|list|get)?\s*(?:all\s*)?{publication_terms}", normalized)
    )


def _normalize_work(work: Mapping[str, Any]) -> ResearchResult | None:
    identifier = _short_openalex_id(work.get("id"))
    title = _string(work.get("display_name") or work.get("title"))
    year = work.get("publication_year")
    if not identifier or not title or not isinstance(year, int):
        return None

    return ResearchResult(
        id=identifier,
        title=title,
        authors=_authors(work.get("authorships")),
        year=year,
        source=_source_name(work),
        type=_string(work.get("type")) or "publication",
        openAccess=_is_open_access(work.get("open_access")),
        citedByCount=_non_negative_int(work.get("cited_by_count")),
        topics=_topics(work.get("topics")),
        summary=_abstract(work.get("abstract_inverted_index")),
        doi=_doi(work.get("doi")),
    )


def _best_author_match(name: str, candidates: Sequence[object]) -> Mapping[str, Any] | None:
    valid = [candidate for candidate in candidates if isinstance(candidate, Mapping)]
    if not valid:
        return None
    normalized_name = name.casefold().strip()
    return next(
        (
            candidate
            for candidate in valid
            if _string(candidate.get("display_name")).casefold() == normalized_name
        ),
        valid[0],
    )


def _normalize_author(author: Mapping[str, Any]) -> AuthorResult | None:
    identifier = _short_openalex_id(author.get("id"))
    name = _string(author.get("display_name"))
    if not identifier or not name:
        return None
    summary_stats = author.get("summary_stats")
    stats = summary_stats if isinstance(summary_stats, Mapping) else {}
    openalex_url = f"https://openalex.org/{identifier}"
    return AuthorResult(
        id=identifier,
        name=name,
        orcid=_orcid(author),
        worksCount=_non_negative_int(author.get("works_count")),
        citedByCount=_non_negative_int(author.get("cited_by_count")),
        hIndex=_non_negative_int(stats.get("h_index")),
        i10Index=_non_negative_int(stats.get("i10_index")),
        affiliations=_affiliations(author.get("affiliations")),
        topics=_topics(author.get("topics")),
        openAlexUrl=openalex_url,
    )


def _orcid(author: Mapping[str, Any]) -> str | None:
    direct = _string(author.get("orcid"))
    if direct:
        return direct
    ids = author.get("ids")
    return _string(ids.get("orcid")) or None if isinstance(ids, Mapping) else None


def _affiliations(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    names: list[str] = []
    for affiliation in value:
        if not isinstance(affiliation, Mapping):
            continue
        institution = affiliation.get("institution")
        if isinstance(institution, Mapping):
            name = _string(institution.get("display_name"))
            if name and name not in names:
                names.append(name)
    return names[:3]


def _short_openalex_id(value: object) -> str:
    text = _string(value)
    return text.rsplit("/", 1)[-1] if text else ""


def _clean_openalex_id(value: str, prefix: str) -> str:
    identifier = _short_openalex_id(value).upper()
    if not re.fullmatch(rf"{re.escape(prefix)}\d+", identifier):
        raise ValueError(f"Invalid OpenAlex {prefix} identifier")
    return identifier


def _authors(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    names: list[str] = []
    for authorship in value:
        if not isinstance(authorship, Mapping):
            continue
        author = authorship.get("author")
        if isinstance(author, Mapping):
            name = _string(author.get("display_name"))
            if name:
                names.append(name)
    return names


def _source_name(work: Mapping[str, Any]) -> str:
    primary_location = work.get("primary_location")
    if isinstance(primary_location, Mapping):
        source = primary_location.get("source")
        if isinstance(source, Mapping):
            name = _string(source.get("display_name"))
            if name:
                return name
    return "Unknown source"


def _is_open_access(value: object) -> bool:
    return bool(value.get("is_oa")) if isinstance(value, Mapping) else False


def _topics(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    topics: list[str] = []
    for topic in value[:3]:
        if isinstance(topic, Mapping):
            name = _string(topic.get("display_name"))
            if name:
                topics.append(name)
    return topics


def _abstract(value: object) -> str:
    if not isinstance(value, Mapping):
        return "No abstract is available for this publication."
    positioned_words: list[tuple[int, str]] = []
    for word, positions in value.items():
        if not isinstance(word, str) or not isinstance(positions, Sequence):
            continue
        for position in positions:
            if isinstance(position, int):
                positioned_words.append((position, word))
    if not positioned_words:
        return "No abstract is available for this publication."
    positioned_words.sort(key=lambda item: item[0])
    return " ".join(word for _, word in positioned_words)


def _doi(value: object) -> str | None:
    doi = _string(value)
    if not doi:
        return None
    if doi.startswith("https://doi.org/"):
        return doi
    return f"https://doi.org/{doi.removeprefix('doi:')}"


def _non_negative_int(value: object) -> int:
    return max(value, 0) if isinstance(value, int) else 0


def _string(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""
