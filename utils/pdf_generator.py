"""
utils/pdf_generator.py — Convert Markdown text to PDF using reportlab
"""
import html
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def markdown_to_pdf(markdown_text: str, title: str = "Document") -> bytes:
    """
    Convert a markdown-like text to a PDF byte stream.
    Supports headings (# ## ###) and bullet lists (- ).
    All text is HTML-escaped to prevent parsing errors.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Title'],
        fontSize=18,
        textColor=colors.blue,
        spaceAfter=12
    )
    story.append(Paragraph(html.escape(title, quote=False), title_style))
    story.append(Spacer(1, 12))

    # Process lines
    lines = markdown_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            story.append(Spacer(1, 6))
            continue

        # Headings
        if line.startswith('# '):
            content = html.escape(line[2:], quote=False)
            story.append(Paragraph(content, styles['Heading1']))
        elif line.startswith('## '):
            content = html.escape(line[3:], quote=False)
            story.append(Paragraph(content, styles['Heading2']))
        elif line.startswith('### '):
            content = html.escape(line[4:], quote=False)
            story.append(Paragraph(content, styles['Heading3']))

        # Bullet list
        elif line.startswith('- '):
            content = html.escape(line[2:], quote=False)
            story.append(ListFlowable(
                [ListItem(Paragraph(content, styles['Normal']))],
                bulletType='bullet'
            ))

        # Separator
        elif line.startswith('---'):
            story.append(Spacer(1, 6))

        # Plain text
        else:
            content = html.escape(line, quote=False)
            story.append(Paragraph(content, styles['Normal']))

        story.append(Spacer(1, 6))

    doc.build(story)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data