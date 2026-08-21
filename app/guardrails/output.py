import re
from dataclasses import dataclass
from typing import Protocol


class PublicationLike(Protocol):
    id: str


class OutputGuardrailError(ValueError):
    """Raised when a generated response is incomplete or cannot be grounded."""


@dataclass(frozen=True)
class OutputGuard:
    def validate(
        self,
        *,
        request: str,
        answer: str,
        publications: list[PublicationLike],
    ) -> str:
        cleaned = answer.strip()
        if not cleaned:
            raise OutputGuardrailError("Literae produced an empty response.")
        if _contains_internal_details(cleaned):
            raise OutputGuardrailError("The response exposed internal processing details.")
        if cleaned.count("```") % 2:
            raise OutputGuardrailError("The response contains an incomplete code block.")

        citation_numbers = [int(value) for value in re.findall(r"\[(\d+)\]", cleaned)]
        if any(number < 1 or number > len(publications) for number in citation_numbers):
            raise OutputGuardrailError("The response contains an unsupported citation.")

        if _is_reference_format_request(request):
            _validate_reference_output(request, cleaned, len(publications))
        return cleaned


def _contains_internal_details(answer: str) -> bool:
    normalized = " ".join(answer.casefold().split())
    patterns = (
        r"\b(system|developer) prompt\b",
        r"\bhidden instructions?\b",
        r"\binternal (?:processing|workflow|node|route|state)\b",
        r"\bsupplied evidence\b|\bprovided evidence\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def _is_reference_format_request(request: str) -> bool:
    normalized = request.casefold()
    return any(
        term in normalized
        for term in (
            "format these references",
            "format the references",
            "bibtex",
            "ris code",
        )
    )


def _validate_reference_output(request: str, answer: str, publication_count: int) -> None:
    if publication_count == 0:
        raise OutputGuardrailError("References cannot be generated without publications.")
    normalized_request = request.casefold()
    if "bibtex" in normalized_request:
        entries = len(re.findall(r"(?m)^@\w+\s*\{", answer))
        if entries != publication_count or not answer.endswith("```"):
            raise OutputGuardrailError("The BibTeX export is incomplete.")
        return
    if "ris code" in normalized_request:
        starts = len(re.findall(r"(?m)^TY  - ", answer))
        ends = len(re.findall(r"(?m)^ER  -\s*$", answer))
        if starts != publication_count or ends != publication_count:
            raise OutputGuardrailError("The RIS export is incomplete.")
        return

    references = {int(value) for value in re.findall(r"(?m)^\[(\d+)\]\s", answer)}
    expected = set(range(1, publication_count + 1))
    if references != expected or answer.rstrip().endswith((",", ";", ":")):
        raise OutputGuardrailError("The formatted reference list is incomplete.")
