"""
utils/pdf_generator.py — Convert Markdown text to PDF using reportlab
"""
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def markdown_to_pdf(markdown_text: str, title: str = "Document") -> bytes:
    """
    Convert a markdown-like text to a PDF byte stream.
    Supports headings (# ## ###), bullet lists (- ), and plain text.
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
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 12))

    # Parse lines
    lines = markdown_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            story.append(Spacer(1, 6))
            continue

        # Headings
        if line.startswith('# '):
            story.append(Paragraph(line[2:], styles['Heading1']))
        elif line.startswith('## '):
            story.append(Paragraph(line[3:], styles['Heading2']))
        elif line.startswith('### '):
            story.append(Paragraph(line[4:], styles['Heading3']))
        # Bullet list
        elif line.startswith('- '):
            story.append(ListFlowable(
                [ListItem(Paragraph(line[2:], styles['Normal']))],
                bulletType='bullet'
            ))
        # Separator
        elif line.startswith('---'):
            story.append(Spacer(1, 6))
        else:
            # Normal text
            story.append(Paragraph(line, styles['Normal']))

        story.append(Spacer(1, 6))

    doc.build(story)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data