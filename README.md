# word-processor

A Python script that automatically corrects **grammar**, **spelling** and
**formatting** issues in DOCX documents.

It runs purely locally and uses only deterministic, rule-based techniques —
no AI/ML models and no network services:

* **Spelling** – an offline word-frequency dictionary
  ([pyspellchecker](https://pypi.org/project/pyspellchecker/), Levenshtein
  edit distance) plus a table of common typos (`teh`, `recieve`, `alot`, …).
* **Grammar** – hand-written regular-expression rules.
* **Formatting** – whitespace and punctuation rules.

Character formatting (bold, italic, fonts, colours, hyperlinks, …) is
preserved: the text is corrected per paragraph and the changes are mapped
back onto the original runs.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Writes report_corrected.docx next to the input
python correct_docx.py report.docx

# Several files or whole folders (searched recursively), written to another
# directory that mirrors the input folder structure
python correct_docx.py docs/ notes.docx --output-dir corrected/

# Choose the output file, or overwrite the input
python correct_docx.py report.docx -o fixed.docx
python correct_docx.py report.docx --in-place

# Only show what would change, and save a change report
python correct_docx.py report.docx --dry-run --report changes.txt
```

Every change is printed (`-q` prints only a summary per file), e.g.

```
report.docx: 3 correction(s) -> report_corrected.docx
  [body, paragraph 2] spelling: "recieved" -> "received"
  [body, paragraph 2] grammar: "the the" -> "the"
  [body, paragraph 4] format: "," -> ", "
```

Useful options (see `python correct_docx.py --help`):

| Option | Effect |
| --- | --- |
| `--no-grammar`, `--no-spelling`, `--no-format` | disable a rule set |
| `--keep-blank-lines` | do not remove consecutive empty paragraphs |
| `--ignore-words FILE` | words (one per line) that must never be changed, e.g. names or jargon |
| `--spell-capitalized` | also spell-check capitalised words (off by default to protect proper nouns) |
| `--max-edit-distance {1,2}` | how far a spelling suggestion may be from the original word |

The package can also be used from Python:

```python
from docx_corrector import DocxCorrector

changes = DocxCorrector().correct_file("in.docx", "out.docx")
```

## What is corrected

**Formatting**
* repeated spaces, leading/trailing spaces in paragraphs
* spaces before `, ; : ! ? .` and missing spaces after `, ; :` and between sentences
* doubled punctuation (`,,` and `..`), spaces inside brackets (`( text )`)
* runs of empty paragraphs are collapsed into one

**Grammar**
* repeated words (`the the`), lowercase pronoun `i`
* `a`/`an` agreement (`a apple`, `an university`, `a hour`)
* sentence and paragraph capitalisation
* common confusions: `could of`, `better then`, `their is`, `your welcome`,
  `its a`, `he don't`, `they was`

**Spelling**
* unknown words are replaced by the most likely dictionary word; British
  spellings (`colour`, `organisation`) are accepted

## What is left untouched

To avoid damaging documents, the corrector does not modify URLs, e-mail
addresses, file names and paths, numbers, acronyms, the article before
words starting with `u` (`a Ukrainian` vs `an umbrella`), mixed-case words
(`iPhone`), proper nouns (capitalised words), contractions, runs set in a
monospace font (code), or runs containing images, fields, symbols and page
breaks; text separated by fields, equations or content controls is
corrected separately on each side. Body text, tables (including nested tables), text boxes, headers and
footers are processed; footnotes, endnotes and comments are not.

Rule-based correction cannot understand meaning, so review the change report
for technical words and add them to an `--ignore-words` file if needed.

## Tests

```bash
pip install pytest
python -m pytest
```
