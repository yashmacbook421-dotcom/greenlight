"""Build small PDFs in memory for tests."""

import io

from fpdf import FPDF
from pypdf import PdfReader, PdfWriter


def text_pdf(*pages: str) -> bytes:
    pdf = FPDF()
    pdf.set_font("Helvetica", size=11)
    for body in pages:
        pdf.add_page()
        pdf.multi_cell(0, 6, body)
    return bytes(pdf.output())


def image_only_pdf() -> bytes:
    """A 'scanned' page: drawn marks, no text layer."""
    pdf = FPDF()
    pdf.add_page()
    pdf.rect(20, 20, 120, 60, style="F")
    return bytes(pdf.output())


def encrypted(data: bytes, *, user_password: str, owner_password: str = "owner") -> bytes:
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(data)))
    writer.encrypt(user_password=user_password, owner_password=owner_password, algorithm="AES-256")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
