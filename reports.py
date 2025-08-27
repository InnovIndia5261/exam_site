# reports.py
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

def make_pdf(user, overall_pct: float, topic_rows, comp_rows) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Mock Test Report", styles['Title']))
    story.append(Paragraph(f"Student: <b>{user['full_name']}</b> ({user['username']})", styles['Normal']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Overall Accuracy: <b>{overall_pct:.1f}%</b>", styles['Heading2']))

    story.append(Spacer(1, 8))
    story.append(Paragraph("Accuracy by Topic", styles['Heading3']))
    tbl_data = [["Topic", "Accuracy %"]] + [[t, f"{acc*100:.1f}"] for t, acc in topic_rows]
    t = Table(tbl_data, hAlign='LEFT')
    t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                           ('BACKGROUND', (0,0), (-1,0), colors.lightgrey)]))
    story.append(t)

    story.append(Spacer(1, 12))
    story.append(Paragraph("You vs Class (Accuracy by Topic)", styles['Heading3']))
    comp_data = [["Topic", "You %", "Class %"]] + [[r[0], f"{r[1]*100:.1f}", f"{r[2]*100:.1f}"] for r in comp_rows]
    tc = Table(comp_data, hAlign='LEFT')
    tc.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey)]))
    story.append(tc)

    doc.build(story)
    buf.seek(0)
    return buf.read()
