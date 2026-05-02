import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from django.utils import timezone

def generate_invoice_pdf(deposit_request):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor("#7c3aed"),
        alignment=1,
        spaceAfter=20
    )
    
    content = []
    
    # Header
    content.append(Paragraph("Namvibe Official Invoice", title_style))
    content.append(Spacer(1, 12))
    
    # User & Request Info
    data = [
        ["User:", f"{deposit_request.user.profile.display_name or deposit_request.user.username}"],
        ["Email:", deposit_request.user.email],
        ["Reference:", deposit_request.request_id],
        ["Amount:", f"NAD {deposit_request.amount}"],
        ["Date:", deposit_request.created_at.strftime("%Y-%m-%d %H:%M")],
        ["Status:", deposit_request.status.upper()],
    ]
    
    table = Table(data, colWidths=[100, 300])
    table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    content.append(table)
    content.append(Spacer(1, 24))
    
    # Payment Instructions
    content.append(Paragraph("Payment Instructions", styles['Heading2']))
    instr = [
        "Please use your unique Reference Code when making payment:",
        f"<b>{deposit_request.request_id}</b>",
        "",
        "<b>FNB Account:</b> 64290441458",
        "<b>PayToCell:</b> 0812613261",
        "<b>MTC Maris:</b> 0812613261",
        "",
        "After payment, please wait for admin approval. Funds will be credited once verified."
    ]
    for line in instr:
        content.append(Paragraph(line, styles['Normal']))
        content.append(Spacer(1, 4))
        
    doc.build(content)
    buffer.seek(0)
    return buffer
