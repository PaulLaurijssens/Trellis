"""The one list of languages Trellis speaks. Adding a language = one entry here + one dictionary
file in frontend/lib/. Prompts are English and ask the model to write in `name(code)`."""

DEFAULT = "en"
LANGUAGES = {
    "en": {"name": "English", "native": "English"},
    "nl": {"name": "Dutch", "native": "Nederlands"},
}
# Unmistakable function words per language, for guessing the language of a short message. Words
# shared by two languages ("is", "in", "was") are left out on purpose. Other languages: no guess.
STOPWORDS = {
    "nl": {"de", "het", "een", "en", "ik", "je", "jij", "niet", "wat", "dat", "van", "hoe", "waarom", "geef", "leg", "uit", "mij",
           "dit", "voor", "kun", "kan", "zijn", "ook", "nog", "maar", "dan", "als", "wel", "naar", "over", "bij", "met", "om", "hier",
           "dus", "eenvoudiger", "voorbeeld", "overhoor", "belangrijk", "mis", "weer", "zou"},
    "en": {"the", "a", "an", "and", "i", "you", "not", "what", "that", "of", "how", "why", "give", "explain", "me", "this", "for",
           "can", "could", "are", "also", "still", "but", "then", "if", "to", "about", "with", "it", "do", "does", "there", "here",
           "so", "please", "example", "simpler", "quiz", "missing", "matter", "would", "my"},
}


def valid(code) -> bool:
    return code in LANGUAGES


def name(code) -> str:
    """English name of the language, for prompts ("Write in Dutch")."""
    return LANGUAGES.get(code, LANGUAGES[DEFAULT])["name"]


def detect(text) -> str | None:
    """'nl', 'en', ... or None when the text is too short, neutral, or in a language without stopwords."""
    import re
    words = re.findall(r"[a-zA-Z']+", str(text).lower())
    if len(words) < 3:
        return None
    scores = {code: sum(w in stop for w in words) for code, stop in STOPWORDS.items()}
    best = max(scores, key=scores.get)
    if scores[best] == 0 or list(scores.values()).count(scores[best]) > 1:
        return None
    return best
