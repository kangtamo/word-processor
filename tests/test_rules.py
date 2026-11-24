import pytest

from docx_corrector import SpellingCorrector, TextCorrector


@pytest.fixture(scope="module")
def corrector():
    return TextCorrector(spelling=SpellingCorrector())


def fix(corrector, text, **kwargs):
    return corrector.correct(text, **kwargs)[0]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("This  has   extra spaces.", "This has extra spaces."),
        ("  Leading and trailing spaces.  ", "Leading and trailing spaces."),
        ("Space before , comma and period .", "Space before, comma and period."),
        ("Missing space,after comma;and semicolon.", "Missing space, after comma; and semicolon."),
        ("Note:this is it.", "Note: this is it."),
        ("First sentence.Second sentence.", "First sentence. Second sentence."),
        ("Double commas,, and periods.. here", "Double commas, and periods. Here"),
        ("Text ( with spaces ) inside [ brackets ].", "Text (with spaces) inside [brackets]."),
    ],
)
def test_formatting(corrector, text, expected):
    assert fix(corrector, text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("The the cat sat on on the mat.", "The cat sat on the mat."),
        ("We know that that is true.", "We know that that is true."),
        ("Then i said i'm done.", "Then I said I'm done."),
        ("She could of won.", "She could have won."),
        ("It is better then nothing.", "It is better than nothing."),
        ("Their are many.", "There are many."),
        ("Your welcome.", "You're welcome."),
        ("I think its a good idea.", "I think it's a good idea."),
        ("The dog wagged its tail.", "The dog wagged its tail."),
        ("He dont know.", "He doesn't know."),
        ("They was late.", "They were late."),
        ("I ate a apple and an banana.", "I ate an apple and a banana."),
        ("It is a hour and an university.", "It is an hour and a university."),
        ("An FBI agent took a x-ray.", "An FBI agent took a x-ray."),
        ("Vitamin A is useful.", "Vitamin A is useful."),
        ("She bought a Unicode font for a Ukrainian user.", "She bought a Unicode font for a Ukrainian user."),
        ("It was an useful and a unilateral decision.", "It was a useful and a unilateral decision."),
        ("Choose option a or b now.", "Choose option a or b now."),
        ("this is a sentence. this is another! and another?", "This is a sentence. This is another! And another?"),
        ("See e.g. the appendix, etc. and more.", "See e.g. the appendix, etc. and more."),
        ("Mr. smith uses an iPhone. iPhone sales rose.", "Mr. smith uses an iPhone. iPhone sales rose."),
        ("Wait... and then.", "Wait... and then."),
    ],
)
def test_grammar(corrector, text, expected):
    assert fix(corrector, text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("We recieve teh documnet tomorow.", "We receive the document tomorrow."),
        ("Teh end.", "The end."),
        ("I dont like it.", "I don't like it."),
        ("The colour of the organisation.", "The colour of the organisation."),
        ("Ask Kangtamo about it.", "Ask Kangtamo about it."),
        ("The NASA and API teams.", "The NASA and API teams."),
    ],
)
def test_spelling(corrector, text, expected):
    assert fix(corrector, text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Visit https://example.com/some.page,now for details.",
        "Mail john.doe@example.com today.",
        "Open report.txt and C:\\Temp\\file.docx please.",
        "The value is 3.14 and 1,000 at 10:30.",
    ],
)
def test_protected_spans_unchanged(corrector, text):
    assert fix(corrector, text) == text


def test_segment_flags(corrector):
    assert fix(corrector, "  middle  text  ", at_start=False, at_end=False) == "  middle text  "
    assert fix(corrector, "lowercase start of a segment", at_start=False) == "lowercase start of a segment"


def test_short_text_not_capitalised(corrector):
    assert fix(corrector, "kg") == "kg"
    assert fix(corrector, "n/a") == "n/a"


def test_corrections_are_reported(corrector):
    _, corrections = corrector.correct("Teh cat.")
    assert [(c.rule, c.original, c.replacement) for c in corrections] == [
        ("spelling", "Teh", "The")
    ]


def test_ignore_words():
    corrector = TextCorrector(spelling=SpellingCorrector(extra_words=["documnet"]))
    assert fix(corrector, "The documnet is here.") == "The documnet is here."


def test_disabled_rules():
    corrector = TextCorrector(fix_format=False, fix_grammar_rules=False, spelling=None)
    assert fix(corrector, "teh  the the") == "teh  the the"
