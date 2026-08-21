import re
from dataclasses import dataclass


class InputGuardrailError(ValueError):
    """Raised when a user request should not enter the research workflow."""


@dataclass(frozen=True)
class InputGuard:
    max_length: int = 4_000

    def validate(self, message: str) -> str:
        normalized = _normalize_message(message)
        if not normalized:
            raise InputGuardrailError("Enter a research request to continue.")
        if len(normalized) > self.max_length:
            raise InputGuardrailError(
                f"Keep the request under {self.max_length:,} characters."
            )
        if _contains_prompt_injection(normalized):
            raise InputGuardrailError(
                "This request cannot be processed. Ask Literae directly about the research you need."
            )
        return normalized


def _normalize_message(message: str) -> str:
    cleaned = "".join(
        character
        for character in message
        if character in {"\n", "\t"} or ord(character) >= 32
    )
    return cleaned.strip()


def _contains_prompt_injection(message: str) -> bool:
    normalized = " ".join(message.casefold().split())
    patterns = (
        r"\bignore\b.{0,40}\b(previous|prior|above|system|developer)\b.{0,20}\b(instructions?|prompt|messages?)\b",
        r"\b(reveal|show|print|repeat|dump|expose)\b.{0,35}\b(system|developer|hidden|internal)\b.{0,20}\b(prompt|instructions?|messages?)\b",
        r"\b(?:act|pretend) as\b.{0,40}\b(?:without|no) (?:rules|restrictions|guardrails)\b",
        r"\b(?:disable|bypass|override|circumvent)\b.{0,25}\b(?:safety|guardrails|filters?|instructions?)\b",
        r"\bdeveloper mode\b|\bjailbreak\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)
