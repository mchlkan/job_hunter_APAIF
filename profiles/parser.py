import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from pdfminer.high_level import extract_text as _pdf_extract_text

# .docx support (python-docx is installed) is intentionally out of scope — PDF only, per spec.

SECTION_HEADERS = {
    "experience": [r"berufserfahrung", r"werdegang", r"work(?:ing)?\s+experience", r"experience"],
    "education": [r"ausbildung", r"bildung", r"education"],
    "skills": [r"kenntnisse", r"fähigkeiten", r"skills", r"qualifikationen"],
}

_MONTH = (
    r"(?:Jan(?:uary|uar)?|Feb(?:ruary|ruar)?|M(?:a|ä)r(?:ch|z)?|Apr(?:il)?|Ma(?:y|i)|"
    r"Jun(?:e|i)?|Jul(?:y|i)?|Aug(?:ust)?|Sep(?:tember)?|Okt(?:ober)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|De(?:c|z)(?:ember)?)"
)
_DATE_TOKEN = rf"(?:{_MONTH}\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\d{{4}})"
DATE_RANGE_RE = re.compile(
    rf"{_DATE_TOKEN}\s*(?:to|bis|[-–—])\s*(?:{_DATE_TOKEN}|heute|present|now|aktuell|current)",
    re.IGNORECASE,
)

_NLP = {}


@dataclass
class Experience:
    title: Optional[str]
    company: Optional[str]
    date_range: Optional[str]
    description: str


@dataclass
class Candidate:
    id: str
    source_file: str
    name: Optional[str]
    skills: list = field(default_factory=list)
    roles: list = field(default_factory=list)
    experience: list = field(default_factory=list)
    education: list = field(default_factory=list)
    raw_text: str = ""
    parsed_at: str = ""


def extract_text(pdf_path: str) -> str:
    return _pdf_extract_text(pdf_path)


def load_skills(path: str = "taxonomy/skills.json") -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_roles(path: str = "taxonomy/roles.json") -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def match_keywords(text: str, canonical: list) -> list:
    text_lower = text.lower()
    matches = []
    for term in canonical:
        pattern = r"\b" + re.escape(term.lower()) + r"\b"
        if re.search(pattern, text_lower):
            matches.append(term)
    return matches


def _header_letters(line: str) -> str:
    # Resume PDFs often prefix section headers with icon glyphs from an icon font
    # (private-use-area code points) — keep letters/spaces only for header matching.
    return re.sub(r"[^A-Za-zÀ-ɏ\s]", "", line).strip()


def split_sections(text: str) -> dict:
    lines = text.splitlines()
    header_positions = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or len(stripped) > 40:
            continue
        letters = _header_letters(stripped).lower()
        if not letters:
            continue
        for section, patterns in SECTION_HEADERS.items():
            if any(re.fullmatch(p + r"s?", letters) for p in patterns):
                header_positions.append((i, section))
                break

    sections = {}
    for idx, (line_no, section) in enumerate(header_positions):
        start = line_no + 1
        end = header_positions[idx + 1][0] if idx + 1 < len(header_positions) else len(lines)
        sections[section] = "\n".join(lines[start:end]).strip()
    return sections


def _get_nlp(lang: str):
    if lang not in _NLP:
        import spacy

        model = "en_core_web_sm" if lang == "en" else "de_core_news_sm"
        _NLP[lang] = spacy.load(model)
    return _NLP[lang]


def _guess_title_company(header_line: str) -> tuple:
    for sep in (" at ", " bei ", " – ", " - ", ","):
        if sep in header_line:
            left, right = header_line.split(sep, 1)
            return left.strip(" –-,") or None, right.strip(" –-,") or None
    return header_line.strip() or None, None


def _ner_company(header_line: str) -> Optional[str]:
    for lang in ("en", "de"):
        try:
            nlp = _get_nlp(lang)
        except OSError:
            continue
        doc = nlp(header_line)
        for ent in doc.ents:
            if ent.label_ == "ORG":
                return ent.text
    return None


_LABEL_LINES = {"responsibilities", "aufgaben", "tasks"}
_LOCATION_LINE_RE = re.compile(r"^[A-Z][\w.\s]+,\s*[A-Z][\w.\s]+$")


def _guess_experience_header(lines: list) -> tuple:
    """Guess (title, company, lines_consumed) from an entry's accumulated header
    lines — either a single "Title at/– Company" line, or two separate lines
    (company, then title), the two conventions real CVs use."""
    lines = [l for l in lines if l.strip()]
    if not lines:
        return None, None, 0

    first = lines[0].strip(" •-*\t")
    title, company = _guess_title_company(first)
    if company:
        return title, company, 1

    if len(lines) > 1:
        second = lines[1].strip(" •-*\t")
        if second and not second.startswith(("●", "-", "*")) and len(second) < 100 and not second.endswith("."):
            return second, first, 2

    return first or None, None, 1


def _trim_trailing_location(description_lines: list) -> list:
    while description_lines and _LOCATION_LINE_RE.match(description_lines[-1]):
        description_lines = description_lines[:-1]
    return description_lines


def parse_experience_block(block: str) -> list:
    if not block.strip():
        return []

    # CVs anchor experience entries on a date range, but in two different ways:
    #   "opening" style  — date shares the line with title/company, body follows
    #                       in later lines (e.g. "Jan 2024 – Jul 2025  Title – Company").
    #   "closing" style   — company/title/bullets come first, a short location+date
    #                       block trails at the end to close the entry.
    # Which style a line is uses one signal: how much non-date text is left on
    # that same line — a lot (a title) means opening, none/little means closing.
    lines = block.strip("\n").splitlines()
    entries = []
    pending = []
    open_idx = None  # index of an "opening"-style entry still collecting its description

    def close_open_entry():
        nonlocal open_idx, pending
        if open_idx is not None:
            desc_lines = [l for l in pending if l.strip().lower() not in _LABEL_LINES]
            desc_lines = _trim_trailing_location(desc_lines)
            entries[open_idx].description = "\n".join(desc_lines).strip()
            open_idx = None
        pending = []

    for line in lines:
        date_match = DATE_RANGE_RE.search(line)
        if not date_match:
            if line.strip():
                pending.append(line.strip(" •-*\t"))
            continue

        date_range = date_match.group(0)
        remainder = (line[: date_match.start()] + line[date_match.end():]).strip(" ,–—-\t")

        if len(remainder) >= 8:
            close_open_entry()
            title, company = _guess_title_company(remainder)
            if not company:
                company = _ner_company(remainder)
            entries.append(Experience(title=title, company=company, date_range=date_range, description=""))
            open_idx = len(entries) - 1
        else:
            content = [l for l in pending if l.strip().lower() not in _LABEL_LINES]
            title, company, consumed = _guess_experience_header(content)
            if not company and content:
                company = _ner_company(content[0])
            description_lines = _trim_trailing_location(content[consumed:])
            entries.append(Experience(
                title=title, company=company, date_range=date_range,
                description="\n".join(description_lines).strip(),
            ))
            pending = []
            open_idx = None

    close_open_entry()
    return entries


def extract_name(text: str) -> Optional[str]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines[:5]:
        try:
            nlp = _get_nlp("en")
        except OSError:
            break
        # All-caps CV header lines ("VANESSA WEISS") trip up spaCy's PERSON
        # detection — title-casing first restores the casing signal it relies on.
        doc = nlp(line.title() if line.isupper() else line)
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                return ent.text
    return lines[0] if lines else None


def parse_cv(pdf_path: str) -> Candidate:
    text = extract_text(pdf_path)
    sections = split_sections(text)

    skills_canonical = load_skills()
    roles_canonical = load_roles()

    skills_text = sections.get("skills", "") + "\n" + text
    skills = match_keywords(skills_text, skills_canonical)
    roles = match_keywords(text, roles_canonical)

    experience = parse_experience_block(sections.get("experience", ""))
    education_block = sections.get("education", "")
    education = [l.strip(" •-*\t") for l in education_block.splitlines() if l.strip()]

    name = extract_name(text)
    candidate_id = hashlib.sha1(f"{pdf_path}{text}".encode("utf-8")).hexdigest()[:12]

    return Candidate(
        id=candidate_id,
        source_file=pdf_path,
        name=name,
        skills=skills,
        roles=roles,
        experience=experience,
        education=education,
        raw_text=text,
        parsed_at=datetime.now(timezone.utc).isoformat(),
    )


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "samples/cv_sample.pdf"
    candidate = parse_cv(path)
    print(f"name: {candidate.name}")
    print(f"skills: {candidate.skills}")
    print(f"roles: {candidate.roles}")
    print(f"experience entries: {len(candidate.experience)}")
    for exp in candidate.experience:
        print(f"  {exp.title!r} @ {exp.company!r} ({exp.date_range})")
    print(f"education: {candidate.education}")
