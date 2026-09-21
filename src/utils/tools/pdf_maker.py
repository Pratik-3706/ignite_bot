import asyncio
import time
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from src.config import TEMP_MEDIA_DIR

async def create_pdf_document(title: str, body_text: str, filename_prefix: str = "ignite") -> Path:
    def _build_pdf() -> Path:
        safe_prefix = "".join(c for c in filename_prefix if c.isalnum() or c in ("-", "_")).rstrip()
        filename = f"{safe_prefix}_{int(time.time())}.pdf"
        output_path = TEMP_MEDIA_DIR / filename

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=54,
            leftMargin=54,
            topMargin=54,
            bottomMargin=54
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            name="ClubTitle",
            parent=styles["Heading1"],
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#FF4500"),
            spaceAfter=12
        )
        body_style = ParagraphStyle(
            name="ClubBody",
            parent=styles["Normal"],
            fontSize=11,
            leading=16,
            textColor=colors.HexColor("#222222"),
            spaceAfter=10
        )

        story = [
            Paragraph(title, title_style),
            Spacer(1, 10)
        ]

        paragraphs = body_text.split("\n\n")
        for p in paragraphs:
            clean_p = p.strip().replace("\n", "<br/>")
            if clean_p:
                story.append(Paragraph(clean_p, body_style))
                story.append(Spacer(1, 6))

        doc.build(story)
        return output_path

    return await asyncio.to_thread(_build_pdf)
