#!/usr/bin/env python3
"""Correct grammar, spelling and formatting issues in DOCX documents.

Usage: python correct_docx.py document.docx [more.docx | folder ...]
Run with --help for all options.
"""

import sys

from docx_corrector.cli import main

if __name__ == "__main__":
    sys.exit(main())
