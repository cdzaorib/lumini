"""Output checks for model wording. Anything doubtful is discarded, never edited."""

import re
import unicodedata

MAX_ANSWER = 600

# Promises, clinical advice and individual suitability (plan §4, Cofen 554/2017 for nursing ads).
_FORBIDDEN = (
    "garant",
    "100%",
    "cura",
    "curar",
    "definitiv",
    "permanente",
    "sem risco",
    "sem dor",
    "nao doi",
    "milagr",
    "imediat",
    "infalivel",
    "indicado para voce",
    "indicada para voce",
    "voce pode fazer",
    "e seguro para voce",
    "diagnost",
    "prescrev",
    "receit",
    "remedio",
    "medicament",
    "o melhor tratamento",
    "resultado garantido",
    "antes e depois",
)


def _plain(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in folded if not unicodedata.combining(char))


def safe_answer(answer: str, facts: str) -> bool:
    """Short, no forbidden wording, and every number must come from the approved facts."""
    if not answer.strip() or len(answer) > MAX_ANSWER:
        return False
    plain = _plain(answer)
    if any(term in plain for term in _FORBIDDEN):
        return False
    known = set(re.findall(r"\d+(?:[.,]\d+)?", facts))
    return all(number in known for number in re.findall(r"\d+(?:[.,]\d+)?", answer))
