"""Local, rule-based grammar, spelling and format corrector for DOCX files."""

from .corrector import TextCorrector
from .processor import DocumentChange, DocxCorrector
from .rules import Correction
from .spelling import SpellingCorrector

__all__ = [
    "Correction",
    "DocumentChange",
    "DocxCorrector",
    "SpellingCorrector",
    "TextCorrector",
]
