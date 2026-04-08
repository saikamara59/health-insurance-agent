from healthflow.tools.document_parser import DocumentParser


SAMPLE_SOB = """SUMMARY OF BENEFITS

INPATIENT HOSPITAL CARE
You pay $250 copay per day for days 1-5.
You pay $0 copay per day for days 6-90.
Prior authorization required.

OUTPATIENT SERVICES
Doctor office visits: $20 copay
Specialist visits: $40 copay

PRESCRIPTION DRUG COVERAGE
Tier 1 (Generic): $10 copay
Tier 2 (Preferred Brand): $45 copay
Tier 3 (Non-Preferred): $90 copay
Tier 4 (Specialty): 25% coinsurance

EMERGENCY CARE
Emergency room: $90 copay (waived if admitted)
Ambulance: $250 copay

MENTAL HEALTH SERVICES
Outpatient: $40 copay per visit
Inpatient: $250 copay per day

PREVENTIVE CARE
Annual wellness visit: $0 copay
Flu shot: $0 copay
"""

SAMPLE_NO_HEADERS = """This plan covers hospital stays at $250 per day.
Doctor visits are $20 and specialists are $40.
Generic drugs cost $10 per prescription.
"""


def test_parse_document_with_headers():
    parser = DocumentParser()
    sections = parser.parse(SAMPLE_SOB)
    assert len(sections) >= 5
    titles = [s.title for s in sections]
    assert "INPATIENT HOSPITAL CARE" in titles
    assert "OUTPATIENT SERVICES" in titles
    assert "PRESCRIPTION DRUG COVERAGE" in titles


def test_parse_document_section_content():
    parser = DocumentParser()
    sections = parser.parse(SAMPLE_SOB)
    inpatient = next(s for s in sections if s.title == "INPATIENT HOSPITAL CARE")
    assert "$250 copay" in inpatient.content
    assert "Prior authorization" in inpatient.content


def test_parse_document_no_headers():
    parser = DocumentParser()
    sections = parser.parse(SAMPLE_NO_HEADERS)
    assert len(sections) == 1
    assert sections[0].title == "Full Document"
    assert "$250 per day" in sections[0].content


def test_parse_empty_document():
    parser = DocumentParser()
    sections = parser.parse("")
    assert len(sections) == 1
    assert sections[0].title == "Full Document"


def test_find_relevant_sections_by_keyword():
    parser = DocumentParser()
    sections = parser.parse(SAMPLE_SOB)
    relevant = parser.find_relevant_sections(sections, "What is the ER copay?")
    titles = [s.title for s in relevant]
    assert "EMERGENCY CARE" in titles


def test_find_relevant_sections_drug_question():
    parser = DocumentParser()
    sections = parser.parse(SAMPLE_SOB)
    relevant = parser.find_relevant_sections(sections, "How much do generic drugs cost?")
    titles = [s.title for s in relevant]
    assert "PRESCRIPTION DRUG COVERAGE" in titles


def test_find_relevant_sections_max_limit():
    parser = DocumentParser()
    sections = parser.parse(SAMPLE_SOB)
    relevant = parser.find_relevant_sections(sections, "copay", max_sections=2)
    assert len(relevant) <= 2


def test_find_relevant_sections_no_match_returns_first():
    parser = DocumentParser()
    sections = parser.parse(SAMPLE_SOB)
    relevant = parser.find_relevant_sections(
        sections, "xyzzy something completely unrelated"
    )
    assert len(relevant) >= 1
