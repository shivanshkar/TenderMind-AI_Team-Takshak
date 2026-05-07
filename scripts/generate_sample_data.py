from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = ROOT / "data" / "sample"


TENDER_LINES = [
    "Government of Bharat",
    "Tender: AI-enabled Citizen Service Analytics Platform",
    "",
    "Eligibility Criteria",
    "Mandatory Criteria:",
    "1. The bidder must have minimum 3 years of experience in AI, data analytics, or software implementation.",
    "2. The bidder must have average annual turnover of INR 50 lakh during the last three financial years.",
    "3. The bidder must have completed at least 2 similar projects for government, PSU, or large enterprise clients.",
    "4. The bidder must hold valid GST registration.",
    "5. ISO 9001 certification is required for quality management.",
    "6. ISO 9001 certificate valid until 2026-12-31.",
    "7. The bidder must not be blacklisted or debarred by any government department.",
    "8. The bidder must have positive net worth as per latest audited financial statements.",
    "9. Bid security valid until 2026-12-31.",
    "10. Data residency: bidder must host and process tender data within India.",
    "11. Technical proposal must describe a cloud-native AI analytics platform with API integration, role-based access control, and audit reporting.",
    "",
    "Optional Criteria:",
    "12. Optional: local language support in Hindi or regional language is desirable for officer-facing workflows.",
    "",
    "Submission Requirements:",
    "A. Company profile may be submitted as typed PDF.",
    "B. Compliance declarations may be PDF or TXT.",
    "C. Technical proposal may be DOCX.",
    "D. Certificates or bid security may be scanned PDFs or photographs.",
]


BIDDERS = {
    "BharatTech_Solutions": {
        "company_profile.pdf": [
            "BharatTech Solutions Pvt Ltd",
            "Years of experience: 6 years",
            "Average annual turnover: INR 120 lakh",
            "Similar projects: 5",
            "Net worth: positive",
        ],
        "compliance_declaration.txt": [
            "Compliance Declaration",
            "GSTIN: 27ABCDE1234F1Z5",
            "ISO 9001 certification: valid",
            "ISO 9001 certificate valid until: 2027-03-31",
            "Blacklisted: no",
            "Data residency: within India",
            "Local language support: Hindi and regional language available",
        ],
        "technical_proposal.docx": [
            "Technical Proposal: BharatTech proposes a cloud-native AI analytics platform with API integration, role-based access control, audit reporting, searchable evidence trails, and officer dashboards.",
        ],
        "bid_security.pdf": [
            "Bid Security Certificate",
            "Bid security valid until: 2027-01-31",
        ],
        "gst_certificate_photo.png": [
            "GST registration: registered",
            "GSTIN: 27ABCDE1234F1Z5",
        ],
    },
    "NewWave_Analytics": {
        "company_profile.pdf": [
            "NewWave Analytics LLP",
            "Experience: 2 years",
            "Average annual turnover: INR 45 lakh",
            "Similar projects: 3",
            "Net worth: positive",
        ],
        "compliance_declaration.pdf": [
            "Compliance Declaration",
            "GST registration: registered",
            "ISO 9001 certificate: available",
            "ISO 9001 certificate valid until: 2026-06-30",
            "Blacklisted: no",
            "Data residency: outside India",
            "Local language support: no",
        ],
        "technical_proposal.docx": [
            "Technical Proposal: NewWave offers dashboards, model monitoring, API integration, role-based access control, and audit reporting for analytics users.",
        ],
        "bid_security.pdf": [
            "EMD valid until: 2027-02-15",
        ],
    },
    "RuralLogic_Innovations": {
        "company_profile.pdf": [
            "RuralLogic Innovations",
            "Experience: 3 years",
            "Average annual turnover: INR 52 lakh",
            "Similar projects: 2",
            "Net worth: positive",
        ],
        "declaration.pdf": [
            "Self declaration",
            "Blacklisted: no",
            "ISO 9001 certification: not available",
            "Data residency: compliant",
            "Local language support: Hindi available",
            "GST registration evidence is attached as scanned image.",
            "Bid security evidence is attached as photograph.",
        ],
        "technical_proposal.docx": [
            "Technical Proposal: RuralLogic proposes a cloud-native AI analytics platform with API integration, role-based access control, and audit reporting for procurement officers.",
        ],
        "gst_certificate_photo.png": [
            "GST registration: registered",
            "GSTIN: 09ABCDE1234F1Z1",
        ],
        "bid_security_photo.jpg": [
            "Bid security valid until: 2027-01-15",
        ],
    },
    "CivicAI_Labs": {
        "company_profile.pdf": [
            "CivicAI Labs Private Limited",
            "Years of experience: 4 years",
            "Average annual turnover: INR 70 lakh",
            "Similar projects: 2",
            "GST registration: registered",
            "Net worth: positive",
        ],
        "compliance_declaration.txt": [
            "Compliance Declaration",
            "ISO 9001 certification: valid",
            "ISO 9001 certificate valid until: 2027-08-20",
            "Blacklisted: no",
            "Bid security valid until: 2027-01-05",
            "Data residency: India",
            "Local language support: no",
        ],
        "technical_proposal.docx": [
            "Technical Proposal: CivicAI Labs will deliver a cloud-native AI analytics platform with API integration, role-based access control, audit reporting, and exportable evaluation reports.",
        ],
    },
}


def main() -> None:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    tender_path = SAMPLE_DIR / "sample_tender_ai_services.pdf"
    write_simple_pdf(tender_path, TENDER_LINES)

    work_dir = SAMPLE_DIR / "bidders"
    reset_dir(work_dir)

    for bidder, documents in BIDDERS.items():
        bidder_dir = work_dir / bidder
        bidder_dir.mkdir(parents=True, exist_ok=True)
        for filename, lines in documents.items():
            target = bidder_dir / filename
            suffix = target.suffix.lower()
            if suffix == ".pdf":
                write_simple_pdf(target, lines)
            elif suffix == ".docx":
                write_simple_docx(target, lines)
            elif suffix in {".png", ".jpg", ".jpeg"}:
                write_sample_image(target, lines)
            elif suffix == ".txt":
                target.write_text("\n".join(lines), encoding="utf-8")
            else:
                target.write_text("\n".join(lines), encoding="utf-8")

    zip_path = SAMPLE_DIR / "sample_bidders.zip"
    if zip_path.exists():
        zip_path.unlink()
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in work_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(work_dir))

    print(f"Created {tender_path}")
    print(f"Created {zip_path}")
    print("Covered scenarios: typed PDF, TXT, DOCX, image/photo OCR path, number, money, date, boolean, text/semantic, mandatory, optional, missing/ambiguous evidence.")


def reset_dir(path: Path) -> None:
    if path.exists():
        for child in sorted(path.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            else:
                child.rmdir()
    path.mkdir(parents=True, exist_ok=True)


def write_simple_pdf(path: Path, lines) -> None:
    content_lines = ["BT", "/F1 9 Tf", "42 800 Td", "12 TL"]
    for line in lines:
        content_lines.append(f"({escape_pdf_text(line)}) Tj")
        content_lines.append("T*")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    output = bytearray(b"%PDF-1.4\n")
    offsets = []
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{idx} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(output)


def write_simple_docx(path: Path, lines) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document_body = "".join(
        f"<w:p><w:r><w:t>{escape_xml(line)}</w:t></w:r></w:p>"
        for line in lines
    )
    files = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>"
        ),
        "word/document.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{document_body}<w:sectPr/></w:body>"
            "</w:document>"
        ),
    }
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as docx:
        for name, content in files.items():
            docx.writestr(name, content)


def write_sample_image(path: Path, lines) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        path.with_suffix(".txt").write_text("\n".join(lines), encoding="utf-8")
        return

    image = Image.new("RGB", (1100, 320), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 34)
    except Exception:
        font = ImageFont.load_default()
    y = 42
    for line in lines:
        draw.text((45, y), line, fill="black", font=font)
        y += 68
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def escape_xml(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


if __name__ == "__main__":
    main()
