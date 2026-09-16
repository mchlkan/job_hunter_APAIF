from profiles.parser import (
    extract_text,
    match_keywords,
    parse_cv,
    parse_experience_block,
    split_sections,
)


def test_extract_text_from_sample_cv(sample_cv_pdf):
    text = extract_text(sample_cv_pdf)
    assert "Jane Doe" in text
    assert "SKILLS" in text


def test_match_keywords_word_boundary():
    matches = match_keywords("We use NoSQLite for experiments", ["sql", "r"])
    assert matches == []


def test_match_keywords_against_skills_json():
    text = "Looking for Python, SQL and Docker experience."
    matches = match_keywords(text, ["Python", "SQL", "Docker", "AWS"])
    assert matches == ["Python", "SQL", "Docker"]


def test_split_sections_finds_experience_and_skills(sample_cv_pdf):
    text = extract_text(sample_cv_pdf)
    sections = split_sections(text)
    assert "experience" in sections
    assert "skills" in sections
    assert "Acme Corp" in sections["experience"]
    assert "Python" in sections["skills"]


def test_parse_experience_block_date_ranges():
    block = (
        "Data Scientist at Acme Corp, 01/2021 - present\n"
        "Built pipelines.\n"
        "\n"
        "Backend Engineer at Example GmbH, 2018 - 2020\n"
        "Maintained services."
    )
    entries = parse_experience_block(block)
    assert len(entries) == 2
    assert entries[0].date_range == "01/2021 - present"
    assert entries[0].company == "Acme Corp"
    assert entries[1].date_range == "2018 - 2020"
    assert entries[1].company == "Example GmbH"


def test_parse_cv_end_to_end(sample_cv_pdf):
    candidate = parse_cv(sample_cv_pdf)
    assert len(candidate.id) == 12
    assert candidate.name == "Jane Doe"
    assert set(candidate.skills) <= {
        "Python", "SQL", "Pandas", "Docker", "AWS", "Machine Learning", "JavaScript",
    }
    assert "Python" in candidate.skills
    assert "SQL" in candidate.skills
    assert len(candidate.experience) == 2
