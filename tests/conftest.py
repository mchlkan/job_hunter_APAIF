import pytest


def _pdf_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def make_pdf(lines: list) -> bytes:
    """Build a minimal single-page PDF containing the given lines of text.

    Handwritten (no reportlab/fpdf in the venv) — just enough PDF structure
    for pdfminer to extract the text back out, used as a synthetic CV fixture.
    """
    content_ops = ["BT", "/F1 11 Tf", "50 750 Td"]
    for i, line in enumerate(lines):
        if i > 0:
            content_ops.append("0 -14 Td")
        content_ops.append(f"({_pdf_escape(line)}) Tj")
    content_ops.append("ET")
    content_stream = "\n".join(content_ops).encode("latin-1", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 612 792] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content_stream)).encode() + b" >>\nstream\n"
        + content_stream + b"\nendstream",
    ]

    out = bytearray()
    out += b"%PDF-1.4\n"
    offsets = [0]
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode()
        out += body
        out += b"\nendobj\n"

    xref_offset = len(out)
    n = len(objects) + 1
    out += f"xref\n0 {n}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += b"trailer\n"
    out += f"<< /Size {n} /Root 1 0 R >>\n".encode()
    out += b"startxref\n"
    out += f"{xref_offset}\n".encode()
    out += b"%%EOF"

    return bytes(out)


SAMPLE_CV_LINES = [
    "Jane Doe",
    "",
    "SKILLS",
    "Python, SQL, Docker, Machine Learning",
    "",
    "EXPERIENCE",
    "Data Scientist at Acme Corp, 01/2021 - present",
    "Built pipelines and dashboards using Python and SQL.",
    "",
    "Backend Engineer at Example GmbH, 2018 - 2020",
    "Maintained services in Python with Docker.",
    "",
    "EDUCATION",
    "M.Sc. Computer Science, Technical University Berlin, 2018",
]


@pytest.fixture
def sample_cv_pdf(tmp_path):
    pdf_path = tmp_path / "cv_sample.pdf"
    pdf_path.write_bytes(make_pdf(SAMPLE_CV_LINES))
    return str(pdf_path)
