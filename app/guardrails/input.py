import re
from dataclasses import dataclass


class InputGuardrailError(ValueError):
    """Raised when a user request should not enter the research workflow."""


MAX_RESEARCH_REQUEST_LENGTH = 4_000


@dataclass(frozen=True)
class InputGuard:
    max_length: int = MAX_RESEARCH_REQUEST_LENGTH

    def validate(self, message: str) -> str:
        normalized = _normalize_message(message)
        if not normalized:
            raise InputGuardrailError("Enter a research request to continue.")
        if len(normalized) > self.max_length:
            raise InputGuardrailError(f"Keep the request under {self.max_length:,} characters.")
        if _contains_explicit_instruction_override(normalized):
            raise InputGuardrailError(
                "This request cannot be processed. Ask Literae directly about the research you need."
            )
        return normalized


def _normalize_message(message: str) -> str:
    cleaned = "".join(
        character for character in message if character in {"\n", "\t"} or ord(character) >= 32
    )
    return cleaned.strip()


def _contains_explicit_instruction_override(message: str) -> bool:
    """Block only explicit imperative attempts to replace governing instructions."""
    normalized = " ".join(message.casefold().split())
    return bool(
        re.match(
            r"^(?:please\s+)?(?:forget|ignore|disregard|discard)\s+"
            r"(?:(?:all|any|the)\s+)?"
            r"(?:(?:previous|prior|earlier|above|system|developer)\s+)?"
            r"(?:instructions?|rules?|prompts?)\b",
            normalized,
        )
    )
