#Location practice.
import unicodedata

ALIASES = {
    "usa": "United States", "us": "United States", "america": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom", "great britain": "United Kingdom", "britain": "United Kingdom",
    "uae": "United Arab Emirates", "emirates": "United Arab Emirates",
    "czech republic": "Czechia", "czech": "Czechia",
    "holland": "Netherlands",
    "korea": "South Korea", "republic of korea": "South Korea",
    "turkiye": "Turkey",
    "russian federation": "Russia",
    "republic of ireland": "Ireland",
}

#normalizing guesses
def normalize(text: str) -> str:
    """Lower case, no accents or punctuation, single spaces, no leading 'the'. 'The Netherlands!' -> 'netherlands'."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower().replace("&", " and ")
    text = text.replace(".", "").replace("'", "").replace("\u2019", "")   # 'U.S.A.' -> 'usa', "Cote d'Ivoire" -> 'cote divoire'
    text = "".join(ch if ch.isalnum() else " " for ch in text)
    words = text.split()
    if words and words[0] == "the":
        words = words[1:]
    return " ".join(words)


#checking if guess is correct
def is_correct(answer: str, country: str) -> bool:
    """Case-insensitive check. Accepts the aliases above, but does no fuzzy matching on purpose:
    a typo-tolerant check would let 'Austria' pass for 'Australia'."""
    typed = normalize(answer)
    return typed == normalize(country) or ALIASES.get(typed) == country