"""Combine the formatting, spelling and grammar rules for a piece of text."""

from .rules import Correction, fix_formatting, fix_grammar, protect


class TextCorrector:
    """Correct a plain-text string with the enabled rule sets."""

    def __init__(self, fix_format=True, fix_grammar_rules=True, spelling=None):
        self.fix_format = fix_format
        self.fix_grammar = fix_grammar_rules
        self.spelling = spelling

    def correct(self, text, at_start=True, at_end=True):
        """Return ``(corrected_text, corrections)``.

        ``at_start``/``at_end`` tell whether ``text`` is at the very start or
        end of its paragraph (leading/trailing spaces are only trimmed there
        and only a paragraph start is capitalised).
        """
        masked, restore = protect(text)
        corrections = []
        if self.fix_format:
            masked = fix_formatting(masked, corrections, at_start, at_end)
        if self.spelling is not None:
            masked = self.spelling.apply(masked, corrections)
        if self.fix_grammar:
            masked = fix_grammar(masked, corrections, at_start)
        corrections = [
            Correction(c.rule, restore(c.original), restore(c.replacement))
            for c in corrections
        ]
        return restore(masked), corrections
