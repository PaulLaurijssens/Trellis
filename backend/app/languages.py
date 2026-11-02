"""The one list of languages Trellis speaks. Trellis ships in English only.

Adding a language takes two entries: one here (so prompts, lessons and memory can be written in it)
and one dictionary file in frontend/lib/ (for the screens). The README section "Add your language"
has a ready prompt that lets an AI coding agent do both. Prompts stay English and ask the model to
write in `name(code)`."""
import re
from typing import Annotated

DEFAULT = "en"
LANGUAGES = {
    "en": {"name": "English", "native": "English"},
}
# Optional: unmistakable function words per language, for guessing the language of a short message.
# Leave out words two languages share ("is", "in", "was"). A language without a list is never guessed;
# the mentor then answers in the language of the message by itself.
STOPWORDS = {
    "en": {"the", "a", "an", "and", "i", "you", "not", "what", "that", "of", "how", "why", "give", "explain", "me", "this", "for",
           "can", "could", "are", "also", "still", "but", "then", "if", "to", "about", "with", "it", "do", "does", "there", "here",
           "so", "please", "example", "simpler", "quiz", "missing", "matter", "would", "my"},
}


def valid(code) -> bool:
    return code in LANGUAGES


def check(code: str) -> str:
    """Pydantic validator: only languages in LANGUAGES."""
    if not valid(code):
        raise ValueError(f"unknown language {code!r}; supported: {', '.join(LANGUAGES)}")
    return code


try:
    from pydantic import AfterValidator
except ImportError:  # the pure unit tests import this module without any packages installed
    Code = str
else:
    Code = Annotated[str, AfterValidator(check)]


def name(code) -> str:
    """English name of the language, for prompts ("Write in English")."""
    return LANGUAGES.get(code, LANGUAGES[DEFAULT])["name"]


def native(code) -> str:
    """The language's own name, for screens."""
    return LANGUAGES.get(code, LANGUAGES[DEFAULT])["native"]


def detect(text) -> str | None:
    """'en', ... or None when the text is too short, neutral, or in a language without stopwords."""
    words = re.findall(r"[^\W\d_']+", str(text).lower())
    if len(words) < 3:
        return None
    scores = {code: sum(w in stop for w in words) for code, stop in STOPWORDS.items()}
    best = max(scores, key=scores.get)
    if scores[best] == 0 or list(scores.values()).count(scores[best]) > 1:
        return None
    # With few stopword lists, one English word in a French message must not make it English.
    if len(words) >= 6 and scores[best] / len(words) < 0.15:
        return None
    return best
