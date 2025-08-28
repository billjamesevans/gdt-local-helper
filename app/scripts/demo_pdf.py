from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

def create_demo_pdf(path: str, title: str='Demo Drawing', pages: int=3):
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    for i in range(pages):
        c.setTitle(title)
        c.setFont('Helvetica-Bold', 16)
        c.drawString(30*mm, h-30*mm, f"{title} — Page {i+1}")
        c.setFont('Helvetica', 10)
        c.drawString(30*mm, h-40*mm, "This is a demo drawing generated for seeding.")
        # Simple shapes to make it look like a drawing
        c.rect(25*mm, 100*mm, 60*mm, 40*mm, stroke=1, fill=0)
        c.circle(120*mm, 160*mm, 15*mm, stroke=1, fill=0)
        c.line(25*mm, 90*mm, 160*mm, 90*mm)
        c.drawString(25*mm, 20*mm, "Confidential — For demo use only")
        c.showPage()
    c.save()
