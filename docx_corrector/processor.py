"""Apply text corrections to DOCX documents while preserving formatting."""

from dataclasses import dataclass
from difflib import SequenceMatcher

from docx import Document
from docx.oxml.ns import qn
from docx.text.run import Run

from .corrector import TextCorrector
from .spelling import SpellingCorrector

# Run children that only carry text; runs containing anything else (images,
# fields, footnote references, symbols, ...) are never rewritten.
_TEXT_TAGS = {qn("w:rPr"), qn("w:t"), qn("w:tab"), qn("w:cr"), qn("w:lastRenderedPageBreak")}
_BR_TAG = qn("w:br")
_BR_TYPE = qn("w:type")
_RUN_TAG = qn("w:r")
# Containers whose runs are visible, ordinary document text.
_WRAPPER_TAGS = {qn("w:hyperlink"), qn("w:smartTag"), qn("w:ins"), qn("w:customXml")}
# Invisible markers that neither carry text nor interrupt it.
_MARKER_TAGS = {
    qn("w:pPr"), qn("w:proofErr"), qn("w:bookmarkStart"), qn("w:bookmarkEnd"),
    qn("w:commentRangeStart"), qn("w:commentRangeEnd"), qn("w:permStart"),
    qn("w:permEnd"),
}
_LOCKED = object()
_MONOSPACE_FONTS = {
    "consolas", "courier", "courier new", "lucida console", "menlo", "monaco",
    "source code pro", "cascadia code", "cascadia mono", "fira code",
    "dejavu sans mono", "liberation mono",
}
_BLANK_PARAGRAPH_KEEP = {qn("w:sectPr"), qn("w:numPr"), qn("w:pageBreakBefore")}


@dataclass
class DocumentChange:
    """A correction applied at a specific location of a document."""

    location: str
    rule: str
    original: str
    replacement: str

    def __str__(self):
        return f'[{self.location}] {self.rule}: "{self.original}" -> "{self.replacement}"'


def _is_editable_run(r):
    for child in r:
        if child.tag in _TEXT_TAGS:
            continue
        if child.tag == _BR_TAG and child.get(_BR_TYPE) in (None, "textWrapping"):
            continue
        return False
    rpr = r.rPr
    if rpr is not None and rpr.rFonts is not None:
        font = rpr.rFonts.get(qn("w:ascii")) or ""
        if font.lower() in _MONOSPACE_FONTS:
            return False  # looks like source code
    return True


def _redistribute(runs, old_texts, new_text):
    """Write ``new_text`` back into ``runs`` keeping each run's formatting.

    Every character of the original text belongs to one run.  A character
    level diff maps unchanged characters to their original run; inserted or
    replaced characters go to the run of the text they replace (or of the
    preceding character for pure insertions).
    """
    old_text = "".join(old_texts)
    owners = [i for i, t in enumerate(old_texts) for _ in t]
    parts = [[] for _ in runs]
    matcher = SequenceMatcher(None, old_text, new_text, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                parts[owners[i1 + k]].append(new_text[j1 + k])
        elif tag in ("replace", "insert"):
            for k in range(j2 - j1):
                if i2 > i1:
                    owner = owners[i1 + min(k, i2 - i1 - 1)]
                else:
                    owner = owners[i1 - 1] if i1 > 0 else owners[0]
                parts[owner].append(new_text[j1 + k])
    for run, old, chars in zip(runs, old_texts, parts):
        new = "".join(chars)
        if new != old:
            run.text = new


def _correct_segment(runs, corrector, at_start, at_end):
    old_texts = [run.text for run in runs]
    original = "".join(old_texts)
    if not original.strip():
        return []
    corrected, corrections = corrector.correct(original, at_start, at_end)
    if corrected != original:
        _redistribute(runs, old_texts, corrected)
    return corrections


def _iter_paragraph_items(parent):
    """Yield editable ``w:r`` elements in order, or ``_LOCKED`` for content
    that must not be edited (images, fields, equations, content controls,
    deleted text, ...)."""
    for child in parent:
        if child.tag == _RUN_TAG:
            yield child if _is_editable_run(child) else _LOCKED
        elif child.tag in _WRAPPER_TAGS:
            yield from _iter_paragraph_items(child)
        elif child.tag not in _MARKER_TAGS:
            yield _LOCKED


def correct_paragraph(p, corrector):
    """Correct a ``w:p`` element in place and return the corrections."""
    segments = []  # (runs, at_start, at_end)
    current = []
    locked_before = False
    for item in _iter_paragraph_items(p):
        if item is not _LOCKED:
            current.append(Run(item, None))
            continue
        if current:
            segments.append([current, not locked_before, False])
            current = []
        locked_before = True
    if current:
        segments.append([current, not locked_before, True])

    corrections = []
    for runs, at_start, at_end in segments:
        corrections.extend(_correct_segment(runs, corrector, at_start, at_end))
    return corrections


def _is_blank_paragraph(p):
    ppr = p.pPr
    if ppr is not None and any(child.tag in _BLANK_PARAGRAPH_KEEP for child in ppr):
        return False
    for child in p:
        if child.tag in (qn("w:pPr"), qn("w:proofErr")):
            continue
        if child.tag == qn("w:r") and _is_editable_run(child) and not child.text.strip():
            continue
        return False
    return True


def _collapse_blank_paragraphs(container):
    """Remove consecutive empty paragraphs, keeping a single one."""
    removed = 0
    previous_blank = False
    for child in list(container):
        if child.tag != qn("w:p"):
            previous_blank = False
            continue
        blank = _is_blank_paragraph(child)
        if blank and previous_blank:
            container.remove(child)
            removed += 1
            continue
        previous_blank = blank
    return removed


def _story_roots(document):
    """Yield ``(name, element)`` for the body, headers and footers."""
    yield "body", document.element.body
    seen = set()
    for index, section in enumerate(document.sections, start=1):
        for kind in (
            "header", "first_page_header", "even_page_header",
            "footer", "first_page_footer", "even_page_footer",
        ):
            hf = getattr(section, kind)
            if not hf._has_definition:
                continue
            part = hf._definition
            if id(part) in seen:
                continue
            seen.add(id(part))
            yield f"section {index} {kind.replace('_', ' ')}", part.element


class DocxCorrector:
    """Correct grammar, spelling and formatting issues in DOCX files."""

    def __init__(
        self,
        fix_format=True,
        fix_spelling=True,
        fix_grammar=True,
        collapse_blank_paragraphs=True,
        language="en",
        extra_words=(),
        correct_capitalized=False,
        max_edit_distance=2,
    ):
        spelling = None
        if fix_spelling:
            spelling = SpellingCorrector(
                language=language,
                distance=max_edit_distance,
                extra_words=extra_words,
                correct_capitalized=correct_capitalized,
            )
        self.text_corrector = TextCorrector(fix_format, fix_grammar, spelling)
        self.collapse_blank_paragraphs = fix_format and collapse_blank_paragraphs

    def correct_document(self, document):
        """Correct a ``docx.Document`` in place and return the changes."""
        changes = []
        for name, root in _story_roots(document):
            for number, p in enumerate(root.iter(qn("w:p")), start=1):
                for c in correct_paragraph(p, self.text_corrector):
                    changes.append(
                        DocumentChange(f"{name}, paragraph {number}", c.rule, c.original, c.replacement)
                    )
            if self.collapse_blank_paragraphs:
                containers = [root] + list(root.iter(qn("w:tc")))
                removed = sum(_collapse_blank_paragraphs(c) for c in containers)
                if removed:
                    changes.append(
                        DocumentChange(name, "format", f"{removed} extra blank paragraph(s)", "removed")
                    )
        return changes

    def correct_file(self, input_path, output_path, dry_run=False):
        """Correct ``input_path`` and save the result to ``output_path``."""
        document = Document(input_path)
        changes = self.correct_document(document)
        if not dry_run:
            document.save(output_path)
        return changes
