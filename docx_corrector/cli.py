"""Command line interface for the DOCX corrector."""

import argparse
import sys
from pathlib import Path

from .processor import DocxCorrector


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="correct_docx",
        description=(
            "Automatically correct grammar, spelling and formatting issues in "
            "DOCX documents using local, rule-based checks (no AI, no network)."
        ),
    )
    parser.add_argument(
        "inputs", nargs="+", type=Path,
        help="DOCX files or folders containing DOCX files",
    )
    output = parser.add_mutually_exclusive_group()
    output.add_argument(
        "-o", "--output", type=Path,
        help="output file (only valid with a single input file)",
    )
    output.add_argument(
        "--output-dir", type=Path, help="directory to write corrected files to",
    )
    output.add_argument(
        "--in-place", action="store_true", help="overwrite the input files",
    )
    parser.add_argument(
        "--suffix", default="_corrected",
        help="suffix added to corrected file names (default: %(default)s)",
    )
    parser.add_argument(
        "--report", type=Path,
        help="write a report of every change to this text file",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="only report the changes, do not write any file",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="only print a summary")
    parser.add_argument("--no-grammar", action="store_true", help="disable grammar rules")
    parser.add_argument("--no-spelling", action="store_true", help="disable spelling correction")
    parser.add_argument("--no-format", action="store_true", help="disable formatting rules")
    parser.add_argument(
        "--keep-blank-lines", action="store_true",
        help="do not remove consecutive empty paragraphs",
    )
    parser.add_argument(
        "--ignore-words", type=Path, action="append", default=[],
        help="text file with words (one per line) that must never be changed",
    )
    parser.add_argument(
        "--spell-capitalized", action="store_true",
        help="also spell-check capitalised words (may alter proper nouns)",
    )
    parser.add_argument(
        "--max-edit-distance", type=int, choices=(1, 2), default=2,
        help="maximum edit distance for spelling suggestions (default: %(default)s)",
    )
    parser.add_argument(
        "--language", default="en",
        help="pyspellchecker dictionary language (default: %(default)s)",
    )
    return parser


def _collect_inputs(paths, suffix):
    files = []
    for path in paths:
        if path.is_dir():
            files.extend(
                p for p in sorted(path.rglob("*.docx"))
                if not p.name.startswith("~$") and not p.stem.endswith(suffix)
            )
        else:
            files.append(path)
    return files


def _read_words(paths):
    words = []
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                words.append(line)
    return words


def _output_path(source, args):
    if args.in_place:
        return source
    if args.output:
        return args.output
    name = f"{source.stem}{args.suffix}{source.suffix}"
    if args.output_dir:
        return args.output_dir / name
    return source.with_name(name)


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)

    files = _collect_inputs(args.inputs, args.suffix)
    if not files:
        parser.error("no DOCX files found")
    if args.output and len(files) != 1:
        parser.error("--output can only be used with a single input file")
    if not args.in_place and not args.dry_run and args.suffix == "" and not (
        args.output or args.output_dir
    ):
        parser.error("an empty --suffix would overwrite the inputs; use --in-place")
    for path in files:
        if not path.is_file():
            parser.error(f"file not found: {path}")
        if path.suffix.lower() != ".docx":
            parser.error(f"not a .docx file: {path}")

    try:
        extra_words = _read_words(args.ignore_words)
    except OSError as exc:
        parser.error(f"cannot read word list: {exc}")

    corrector = DocxCorrector(
        fix_format=not args.no_format,
        fix_spelling=not args.no_spelling,
        fix_grammar=not args.no_grammar,
        collapse_blank_paragraphs=not args.keep_blank_lines,
        language=args.language,
        extra_words=extra_words,
        correct_capitalized=args.spell_capitalized,
        max_edit_distance=args.max_edit_distance,
    )

    if args.output_dir and not args.dry_run:
        args.output_dir.mkdir(parents=True, exist_ok=True)

    report_lines = []
    exit_code = 0
    for source in files:
        destination = _output_path(source, args)
        try:
            changes = corrector.correct_file(source, destination, dry_run=args.dry_run)
        except Exception as exc:  # report and continue with the next file
            print(f"error: {source}: {exc}", file=sys.stderr)
            exit_code = 1
            continue
        header = f"{source}: {len(changes)} correction(s)"
        if not args.dry_run:
            header += f" -> {destination}"
        report_lines.append(header)
        report_lines.extend(f"  {change}" for change in changes)
        print(header)
        if not args.quiet:
            for change in changes:
                print(f"  {change}")

    if args.report:
        args.report.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return exit_code
