import docx
import pytest
from docx.enum.text import WD_BREAK
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from docx_corrector import DocxCorrector
from docx_corrector.cli import main


@pytest.fixture(scope="module")
def corrector():
    return DocxCorrector()


def _add_hyperlink(paragraph, text, url):
    part = paragraph.part
    r_id = part.relate_to(url, docx.opc.constants.RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)
    run = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    run.append(t)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def test_run_formatting_is_preserved(corrector):
    document = docx.Document()
    paragraph = document.add_paragraph()
    paragraph.add_run("this is ")
    bold = paragraph.add_run("teh  bold")
    bold.bold = True
    paragraph.add_run(" text ,with errors.")

    changes = corrector.correct_document(document)

    assert paragraph.text == "This is the bold text, with errors."
    assert [r.text for r in paragraph.runs] == ["This is ", "the bold", " text, with errors."]
    assert [r.bold for r in paragraph.runs] == [None, True, None]
    rules = {c.rule for c in changes}
    assert rules == {"format", "spelling", "grammar"}


def test_tables_headers_and_hyperlinks(corrector):
    document = docx.Document()
    cell = document.add_table(rows=1, cols=1).cell(0, 0)
    cell.paragraphs[0].text = "a apple in teh table."
    document.sections[0].header.paragraphs[0].text = "header  text with errror"
    paragraph = document.add_paragraph("Read ")
    _add_hyperlink(paragraph, "teh manual", "https://example.com")
    paragraph.add_run(" now.")

    corrector.correct_document(document)

    assert cell.paragraphs[0].text == "An apple in the table."
    assert document.sections[0].header.paragraphs[0].text == "Header text with error"
    hyperlink_text = "".join(t.text for t in paragraph._p.iter(qn("w:t")))
    assert hyperlink_text == "Read the manual now."
    assert paragraph._p.find(qn("w:hyperlink")) is not None


def test_non_text_runs_are_untouched(corrector):
    document = docx.Document()
    paragraph = document.add_paragraph("first line teh")
    paragraph.runs[0].add_break(WD_BREAK.PAGE)
    paragraph.add_run("second  part")

    corrector.correct_document(document)

    assert paragraph.runs[0]._r.find(qn("w:br")) is not None
    assert paragraph.runs[0].text == "first line teh"
    assert paragraph.runs[1].text == "second part"


@pytest.mark.parametrize(
    "xml",
    [
        '<w:fldSimple w:instr="PAGE"><w:r><w:t>1</w:t></w:r></w:fldSimple>',
        '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
        "<m:r><m:t>x</m:t></m:r></m:oMath>",
        "<w:sdt><w:sdtContent><w:r><w:t>John</w:t></w:r></w:sdtContent></w:sdt>",
    ],
)
def test_unsupported_elements_split_segments(corrector, xml):
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls

    document = docx.Document()
    paragraph = document.add_paragraph("Let ")
    element = parse_xml(xml.replace(">", f" {nsdecls('w')}>", 1))
    paragraph._p.append(element)
    paragraph.add_run(" signed  teh value.")

    corrector.correct_document(document)

    assert paragraph.runs[0].text == "Let "
    assert paragraph.runs[-1].text == " signed the value."
    assert paragraph._p[-2].tag == element.tag


def test_blank_paragraphs_are_collapsed(corrector):
    document = docx.Document()
    document.add_paragraph("One paragraph here.")
    for _ in range(3):
        document.add_paragraph("")
    document.add_paragraph("Another paragraph here.")

    corrector.correct_document(document)

    assert [p.text for p in document.paragraphs] == [
        "One paragraph here.", "", "Another paragraph here."
    ]


def test_cli_writes_corrected_copy(tmp_path):
    source = tmp_path / "input.docx"
    document = docx.Document()
    document.add_paragraph("this is teh  first sentence ,it has errors.")
    document.save(source)
    report = tmp_path / "report.txt"

    assert main([str(source), "--report", str(report), "--quiet"]) == 0

    output = tmp_path / "input_corrected.docx"
    assert docx.Document(output).paragraphs[0].text == "This is the first sentence, it has errors."
    assert docx.Document(source).paragraphs[0].text.startswith("this is teh")
    assert "spelling" in report.read_text(encoding="utf-8")


def test_cli_dry_run_and_directory(tmp_path):
    document = docx.Document()
    document.add_paragraph("teh end")
    document.save(tmp_path / "a.docx")

    assert main([str(tmp_path), "--dry-run", "--quiet"]) == 0
    assert not (tmp_path / "a_corrected.docx").exists()

    assert main([str(tmp_path), "--output-dir", str(tmp_path / "out"), "--quiet"]) == 0
    assert docx.Document(tmp_path / "out" / "a_corrected.docx").paragraphs[0].text == "the end"


def test_cli_output_dir_keeps_folder_structure(tmp_path):
    for sub in ("a", "b"):
        (tmp_path / "in" / sub).mkdir(parents=True)
        document = docx.Document()
        document.add_paragraph(f"teh {sub}")
        document.save(tmp_path / "in" / sub / "report.docx")

    assert main([str(tmp_path / "in"), "--output-dir", str(tmp_path / "out"), "-q"]) == 0
    assert docx.Document(tmp_path / "out" / "a" / "report_corrected.docx").paragraphs[0].text == "the a"
    assert docx.Document(tmp_path / "out" / "b" / "report_corrected.docx").paragraphs[0].text == "the b"


def test_cli_refuses_to_overwrite_input(tmp_path):
    source = tmp_path / "doc.docx"
    docx.Document().save(source)
    with pytest.raises(SystemExit):
        main([str(source), "--suffix", ""])
