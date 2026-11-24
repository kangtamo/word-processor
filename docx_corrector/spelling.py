"""Dictionary-based spelling correction.

Uses `pyspellchecker`, which ships an offline word-frequency dictionary and
ranks candidates by Levenshtein edit distance and word frequency.  No AI
models or network access are involved.
"""

import re

from spellchecker import SpellChecker

from .rules import Correction, _match_case

# Frequent typos that a pure edit-distance search gets wrong or that are too
# short for the dictionary search to be reliable.
COMMON_MISSPELLINGS = {
    "teh": "the", "hte": "the", "adn": "and", "nad": "and", "taht": "that",
    "thier": "their", "recieve": "receive", "recieved": "received",
    "beleive": "believe", "acheive": "achieve", "wich": "which",
    "alot": "a lot", "definately": "definitely", "seperate": "separate",
    "occured": "occurred", "occurence": "occurrence", "untill": "until",
    "accomodate": "accommodate", "goverment": "government",
    "enviroment": "environment", "neccessary": "necessary",
    "tommorow": "tomorrow", "tomorow": "tomorrow", "wierd": "weird",
    "becuase": "because", "becasue": "because", "freind": "friend",
    "beggining": "beginning", "begining": "beginning", "calender": "calendar",
    "comming": "coming", "concious": "conscious", "existance": "existence",
    "foriegn": "foreign", "futher": "further", "independant": "independent",
    "knowlege": "knowledge", "noticable": "noticeable", "occassion": "occasion",
    "persue": "pursue", "posession": "possession", "prefered": "preferred",
    "publically": "publicly", "realy": "really", "refered": "referred",
    "succesful": "successful", "truely": "truly", "writting": "writing",
    "doesnt": "doesn't", "didnt": "didn't", "isnt": "isn't",
    "wasnt": "wasn't", "couldnt": "couldn't", "shouldnt": "shouldn't",
    "wouldnt": "wouldn't", "havent": "haven't", "hasnt": "hasn't",
    "arent": "aren't", "werent": "weren't", "dont": "don't",
}

# Simple British -> American spelling transformations.  A word is accepted
# as correct when one of its American variants is in the dictionary, so
# that "colour" or "organisation" are not "corrected".
_BRITISH_VARIANTS = [
    (re.compile(r"our(s|ed|ing|ful|ite|ites|able)?$"), r"or\1"),
    (re.compile(r"is(e|es|ed|ing|ation|ations|er|ers)$"), r"iz\1"),
    (re.compile(r"ys(e|es|ed|ing)$"), r"yz\1"),
    (re.compile(r"tre(s)?$"), r"ter\1"),
    (re.compile(r"ence(s)?$"), r"ense\1"),
    (re.compile(r"ogue(s)?$"), r"og\1"),
    (re.compile(r"ll(ed|ing|er|ers)$"), r"l\1"),
    (re.compile(r"amme(s)?$"), r"am\1"),
]

_WORD_RE = re.compile(r"(?<![\w])[A-Za-z]+(?:['’][A-Za-z]+)*(?![\w])")


class SpellingCorrector:
    """Correct misspelled words using an offline dictionary."""

    def __init__(
        self,
        language="en",
        distance=2,
        extra_words=(),
        correct_capitalized=False,
        min_length=4,
    ):
        self._checker = SpellChecker(language=language, distance=distance)
        self._ignored = {w.lower() for w in extra_words}
        self._correct_capitalized = correct_capitalized
        self._min_length = min_length
        self._cache = {}

    def _is_known(self, lower):
        if lower in self._ignored or lower in self._checker:
            return True
        for pattern, replacement in _BRITISH_VARIANTS:
            variant = pattern.sub(replacement, lower)
            if variant != lower and variant in self._checker:
                return True
        return False

    def suggest(self, word):
        """Return the corrected word, or ``None`` if no change is needed."""
        lower = word.lower().replace("’", "'")
        if lower in self._ignored:
            return None
        if lower in COMMON_MISSPELLINGS:
            fixed = COMMON_MISSPELLINGS[lower]
            if "’" in word:
                fixed = fixed.replace("'", "’")
            return _match_case(word, fixed)

        # Skip acronyms, mixed case (iPhone, McDonald) and short tokens.
        if len(word) < self._min_length or (len(word) > 1 and word.isupper()):
            return None
        if any(c.isupper() for c in word[1:]):
            return None
        if word[0].isupper() and not self._correct_capitalized:
            return None  # most likely a proper noun
        if "'" in lower:
            return None  # contractions/possessives are left alone

        if lower not in self._cache:
            fixed = None
            if not self._is_known(lower):
                candidate = self._checker.correction(lower)
                if candidate and candidate != lower:
                    fixed = candidate
            self._cache[lower] = fixed
        fixed = self._cache[lower]
        return _match_case(word, fixed) if fixed else None

    def apply(self, text, corrections):
        """Correct every word in ``text`` and record the changes."""

        def _replace(match):
            word = match.group(0)
            fixed = self.suggest(word)
            if fixed is None or fixed == word:
                return word
            corrections.append(Correction("spelling", word, fixed))
            return fixed

        return _WORD_RE.sub(_replace, text)
