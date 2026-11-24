"""Deterministic, rule-based correction rules for English prose.

Every rule in this module is a hand-written regular expression or lookup
table.  Nothing here uses machine learning, AI models or network services.
"""

import re
from dataclasses import dataclass


@dataclass
class Correction:
    """A single change applied to a piece of text."""

    rule: str
    original: str
    replacement: str


def _sub(pattern, repl, text, rule, corrections):
    """``pattern.sub`` that records every effective replacement.

    ``repl`` is a string template or a callable returning the replacement
    text (or ``None`` to leave the match unchanged).
    """

    def _replace(match):
        old = match.group(0)
        new = repl(match) if callable(repl) else match.expand(repl)
        if new is None:
            return old
        if new != old:
            corrections.append(Correction(rule, old, new))
        return new

    return pattern.sub(_replace, text)


def _match_case(source, target):
    """Return ``target`` with the capitalisation pattern of ``source``."""
    if source.isupper() and len(source) > 1:
        return target.upper()
    if source[:1].isupper():
        return target[:1].upper() + target[1:]
    return target


# ---------------------------------------------------------------------------
# Protection of URLs, e-mail addresses, file names, numbers, ...
# ---------------------------------------------------------------------------

_PLACEHOLDER_START = 0xE000  # Unicode private use area
_PLACEHOLDER_END = 0xF8FF
PLACEHOLDER_CLASS = "[\uE000-\uF8FF]"

_PROTECTED_RE = re.compile(
    r"""
    (?:https?|ftp)://\S+?(?=[.,;:!?)\]'"]*(?:\s|$))   # URLs
    | www\.\S+?(?=[.,;:!?)\]'"]*(?:\s|$))
    | [\w.+-]+@[\w-]+(?:\.[\w-]+)+                     # e-mail addresses
    | [@\#]\w+                                         # mentions / hashtags
    | [^\s,;]*[\\/][^\s,;]*                            # paths, and/or, 1/2
    | \b[\w-]+(?:\.[a-z0-9_][\w-]*)+                   # file.txt, 3.14, e.g
    """,
    re.VERBOSE,
)


def protect(text):
    """Replace spans that must never be modified with placeholder characters.

    Returns the masked text and a function that restores the original spans.
    """
    spans = []

    def _mask(match):
        index = len(spans)
        if _PLACEHOLDER_START + index > _PLACEHOLDER_END:
            return match.group(0)
        spans.append(match.group(0))
        return chr(_PLACEHOLDER_START + index)

    if any(_PLACEHOLDER_START <= ord(c) <= _PLACEHOLDER_END for c in text):
        # The text already uses private-use characters; do not risk
        # confusing them with our placeholders.
        return text, lambda s: s

    masked = _PROTECTED_RE.sub(_mask, text)

    def restore(value):
        if not spans:
            return value
        return "".join(
            spans[ord(c) - _PLACEHOLDER_START]
            if _PLACEHOLDER_START <= ord(c) < _PLACEHOLDER_START + len(spans)
            else c
            for c in value
        )

    return masked, restore


# ---------------------------------------------------------------------------
# Formatting rules (whitespace and punctuation)
# ---------------------------------------------------------------------------

_MULTI_SPACE_RE = re.compile(r"(?<=\S) {2,}(?=\S)")
_LEADING_SPACE_RE = re.compile(r"^ +")
_TRAILING_SPACE_RE = re.compile(r" +$")
_SPACE_BEFORE_PUNCT_RE = re.compile(r"(?<=\S) +([,;:!?]|\.(?=\s|$|[\"'”’)\]]))")
_MISSING_SPACE_AFTER_COMMA_RE = re.compile(r"(?<=[A-Za-z])([,;])(?=[A-Za-z])")
_MISSING_SPACE_AFTER_COLON_RE = re.compile(r"(?<=[a-z])(:)(?=[A-Za-z])")
_MISSING_SPACE_AFTER_SENTENCE_RE = re.compile(r"(?<=[a-z]{2})([.!?])(?=[A-Z][a-z])")
_DUPLICATE_COMMA_RE = re.compile(r"([,;])\1+")
_DOUBLE_PERIOD_RE = re.compile(r"(?<!\.)\.\.(?!\.)")
_SPACE_AFTER_OPEN_BRACKET_RE = re.compile(r"([(\[]) +(?=\S)")
_SPACE_BEFORE_CLOSE_BRACKET_RE = re.compile(r"(?<=\S) +([)\]])")


def fix_formatting(text, corrections, at_start=True, at_end=True):
    """Fix spacing and punctuation formatting issues."""
    rule = "format"
    text = _sub(_MULTI_SPACE_RE, " ", text, rule, corrections)
    if at_start:
        text = _sub(_LEADING_SPACE_RE, "", text, rule, corrections)
    if at_end:
        text = _sub(_TRAILING_SPACE_RE, "", text, rule, corrections)
    text = _sub(_SPACE_BEFORE_PUNCT_RE, r"\1", text, rule, corrections)
    text = _sub(_DUPLICATE_COMMA_RE, r"\1", text, rule, corrections)
    text = _sub(_DOUBLE_PERIOD_RE, ".", text, rule, corrections)
    text = _sub(_MISSING_SPACE_AFTER_COMMA_RE, r"\1 ", text, rule, corrections)
    text = _sub(_MISSING_SPACE_AFTER_COLON_RE, r"\1 ", text, rule, corrections)
    text = _sub(_MISSING_SPACE_AFTER_SENTENCE_RE, r"\1 ", text, rule, corrections)
    text = _sub(_SPACE_AFTER_OPEN_BRACKET_RE, r"\1", text, rule, corrections)
    text = _sub(_SPACE_BEFORE_CLOSE_BRACKET_RE, r"\1", text, rule, corrections)
    return text


# ---------------------------------------------------------------------------
# Grammar rules
# ---------------------------------------------------------------------------

# Words that are legitimately repeated in normal English.
_ALLOWED_REPEATS = {
    "bye", "had", "ha", "haha", "knock", "la", "many", "no", "now", "so",
    "that", "tsk", "very", "really", "well", "yes", "blah", "ho", "boo",
    "chop", "dum", "night", "pom", "there", "tut", "yada", "is", "do",
}

_REPEATED_WORD_RE = re.compile(r"\b([A-Za-z]+)(\s+)\1\b", re.IGNORECASE)


def _fix_repeated_word(match):
    first = match.group(1)
    second = match.group(0)[len(first) + len(match.group(2)):]
    if first.lower() in _ALLOWED_REPEATS:
        return None
    # "The the" / "the the" -> keep the first word's capitalisation.
    if first.lower() != second.lower():
        return None
    return first


_STANDALONE_I_RE = re.compile(r"(?<![\w'’.(\-])i(?=['’](?:m|ve|ll|d)\b|\s+[A-Za-z])")

# (pattern, replacement template) pairs for commonly confused words.
_CONFUSIONS = [
    (r"\b(could|would|should|must|might|may)(\s+)of\b", r"\1\2have"),
    (
        r"\b(more|less|better|worse|rather|greater|fewer|larger|smaller|higher"
        r"|lower|faster|slower|bigger|older|younger)(\s+)then\b",
        r"\1\2than",
    ),
    (r"\btheir(\s+)(is|are|was|were)\b", r"there\1\2"),
    (r"\byour(\s+)welcome\b", r"you're\1welcome"),
    (r"\bits(\s+)(a|an|the|been|not|going)\b", r"it's\1\2"),
    (r"\b(he|she|it)(\s+)don(['’])t\b", r"\1\2doesn\3t"),
    (r"\b(he|she|it)(\s+)dont\b", r"\1\2doesn't"),
    (r"\b(we|you|they)(\s+)was\b", r"\1\2were"),
]
_CONFUSION_RES = [(re.compile(p, re.IGNORECASE), r) for p, r in _CONFUSIONS]


# Words starting with a vowel letter but a consonant sound ("a university").
_CONSONANT_SOUND_PREFIXES = (
    "unique", "unit", "unif", "union", "unicorn", "univers", "unix",
    "unanim", "use", "usu", "usa", "uten", "util", "uto", "ura", "uri",
    "uro", "eu", "ewe", "ubiq", "ufo", "once", "one-", "ukulele",
)
# Words starting with a consonant letter but a vowel sound ("an hour").
_VOWEL_SOUND_PREFIXES = ("hour", "honest", "honor", "honour", "heir")

_ARTICLE_RE = re.compile(r"\b(a|an|A|An)(\s+)([A-Za-z][\w'’-]*)")
_SENTENCE_BOUNDARY_RE = re.compile(r"(?:^|[.!?][\"'”’)\]]*\s+)$")


def _needs_an(word):
    lower = word.lower()
    if lower.startswith(_VOWEL_SOUND_PREFIXES):
        return True
    if lower == "one" or lower.startswith(_CONSONANT_SOUND_PREFIXES):
        return False
    return lower[0] in "aeiou"


def _fix_article(match):
    article, space, word = match.groups()
    if article[0].isupper():
        # "A"/"An" may be a letter or label ("vitamin A is") unless it
        # starts a sentence.
        if not _SENTENCE_BOUNDARY_RE.search(match.string[: match.start()]):
            return None
    if len(word) > 1 and (word.isupper() or word[1] == "-"):
        return None  # acronyms and letter compounds ("an FBI", "x-ray")
    if any(ch.isdigit() for ch in word):
        return None
    wanted = "an" if _needs_an(word) else "a"
    if article.lower() == wanted:
        return None
    return _match_case(article, wanted) + space + word


_ABBREVIATIONS = {
    "al", "approx", "cf", "co", "dept", "dr", "etc", "fig", "inc", "jr",
    "ltd", "mr", "mrs", "ms", "no", "nos", "pp", "prof", "sr", "st", "viz",
    "vs", "vol",
}
_SENTENCE_START_RE = re.compile(
    r"(?P<before>(?P<punct>\.{1,3}|[!?])[\"'”’)\]]*\s+)"
    r"(?P<first>[a-z])(?=(?P<rest>[\w'’-]*))"
)
_PARAGRAPH_START_RE = re.compile(r"^(?P<lead>[\"'“‘(\[]*)(?P<target>[a-z][\w'’-]*)")


def _is_plain_lower_word(word):
    return not any(c.isupper() or c.isdigit() for c in word[1:])


_PRECEDING_WORD_RE = re.compile(r"[\w\uE000-\uF8FF]*$")


def _capitalize_sentence(match):
    word = _PRECEDING_WORD_RE.search(match.string, 0, match.start()).group(0)
    punct = match.group("punct")
    target = match.group("first") + match.group("rest")
    if len(punct) > 1:
        return None  # ellipsis: the sentence probably continues
    if punct == ".":
        if not word or re.search(PLACEHOLDER_CLASS, word):
            return None  # follows a URL, file name, number, ...
        if word.lower() in _ABBREVIATIONS or len(word) == 1:
            return None  # "etc. and", initials such as "J. smith"
    if not _is_plain_lower_word(target):
        return None
    return match.group("before") + target[0].upper()


def _capitalize_paragraph_start(match):
    target = match.group("target")
    # Only treat the text as prose when it has several words, so that
    # table cells or list entries like "kg" or "n/a" are left alone.
    if len(match.string.split()) < 3 or not _is_plain_lower_word(target):
        return None
    return match.group("lead") + target[0].upper() + target[1:]


def fix_grammar(text, corrections, at_start=True):
    """Apply rule-based grammar corrections."""
    rule = "grammar"
    text = _sub(_REPEATED_WORD_RE, _fix_repeated_word, text, rule, corrections)
    text = _sub(_STANDALONE_I_RE, "I", text, rule, corrections)
    for pattern, replacement in _CONFUSION_RES:
        text = _sub(
            pattern,
            lambda m, r=replacement: _match_case(m.group(0), m.expand(r)),
            text,
            rule,
            corrections,
        )
    text = _sub(_ARTICLE_RE, _fix_article, text, rule, corrections)
    text = _sub(_SENTENCE_START_RE, _capitalize_sentence, text, rule, corrections)
    if at_start:
        text = _sub(
            _PARAGRAPH_START_RE, _capitalize_paragraph_start, text, rule, corrections
        )
    return text
