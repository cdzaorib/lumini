"""Remove obvious identifiers before any text leaves for a model.

This is minimization, not anonymization: names and indirect identifiers can survive (ADR-007).
Health mentions are routed to the team locally before this point and never reach a model.
"""

import re

MAX_CHARS = 300

_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
    (re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE), "[link]"),
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[documento]"),
    (re.compile(r"\b\d{5}-?\d{3}\b"), "[cep]"),
    (re.compile(r"(?:\+?55[\s-]*)?\(?\d{2}\)?[\s-]*9?\d{4}[\s-]*\d{4}\b"), "[telefone]"),
    (re.compile(r"\d{6,}"), "[número]"),
    (re.compile(r"(?<![\w])@[\w.]{2,}"), "[perfil]"),
)


def redact(text: str) -> str:
    result = text
    for pattern, replacement in _RULES:
        result = pattern.sub(replacement, result)
    return re.sub(r"\s+", " ", result).strip()[:MAX_CHARS]


def leaks(text: str) -> bool:
    """True when something that looks like a direct identifier is still present."""
    return any(pattern.search(text) for pattern, _ in _RULES[:6])
