from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import requests
from pathlib import Path as PathLib

from config import INVOICES_DIR, DEFAULT_CURRENCY
from database import Invoice


def register_inter_fonts():
    """Register Inter fonts for use in PDFs."""
    base_dir = PathLib(__file__).parent
    inter_static_dir = base_dir / "fonts" / "Inter" / "static"
    
    if not inter_static_dir.exists():
        print("Warning: Inter fonts directory not found, using fallback fonts")
        return
    
    # Map the font names we want to use to the actual font file patterns
    font_mappings = {
        'Inter-Regular': 'Inter_18pt-Regular.ttf',
        'Inter-Medium': 'Inter_18pt-Medium.ttf', 
        'Inter-SemiBold': 'Inter_18pt-SemiBold.ttf',
        'Inter-Bold': 'Inter_18pt-Bold.ttf'
    }
    
    for font_name, file_pattern in font_mappings.items():
        font_path = inter_static_dir / file_pattern
        if font_path.exists():
            try:
                pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
                print(f"✓ Registered {font_name}")
            except Exception as e:
                print(f"Warning: Could not register {font_name}: {e}")
        else:
            print(f"Warning: Font file not found: {file_pattern}")


def generate_invoice_pdf(cycle: Dict, events: List[Dict], profile: Dict,
                         hourly_rate: float, detailed: bool = False,
                         invoice_date: Optional[str] = None,
                         due_days: int = 30) -> str:
    """Generate PDF invoice in the style of the sample."""
    
    # Register Inter fonts
    register_inter_fonts()
    
    # Generate invoice details
    invoice_number = Invoice.get_next_invoice_number()
    if not invoice_date:
        invoice_date = datetime.now().strftime('%Y-%m-%d')
    
    invoice_dt = datetime.strptime(invoice_date, '%Y-%m-%d')
    due_date = (invoice_dt + timedelta(days=due_days)).strftime('%Y-%m-%d')
    
    # Calculate totals
    total_hours = sum(e['duration_hours'] for e in events)
    total_amount = total_hours * hourly_rate
    
    # Create PDF filename
    pdf_filename = f"invoice-{invoice_number.replace('#', '')}-{invoice_date}.pdf"
    pdf_path = INVOICES_DIR / pdf_filename
    
    # Create the PDF
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=1*inch,
        bottomMargin=1*inch
    )
    
    # Build the document content
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles - using Inter fonts to match sample
    try:
        title_font = 'Inter-Bold'
        # Test if font is available
        pdfmetrics.getFont(title_font)
    except:
        title_font = 'Helvetica-Bold'
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=28,
        fontName=title_font,
        textColor=colors.HexColor('#000000'),
        spaceAfter=30,
        alignment=TA_LEFT
    )
    
    try:
        heading_font = 'Inter-SemiBold'
        pdfmetrics.getFont(heading_font)
    except:
        heading_font = 'Helvetica-Bold'
    
    heading_style = ParagraphStyle(
        'Heading',
        parent=styles['Heading2'],
        fontSize=12,
        fontName=heading_font,
        textColor=colors.HexColor('#000000'),
        spaceBefore=20,
        spaceAfter=10,
    )
    
    try:
        normal_font = 'Inter-Regular'
        pdfmetrics.getFont(normal_font)
    except:
        normal_font = 'Helvetica'
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        fontName=normal_font
    )
    
    # Invoice Title
    story.append(Paragraph("Invoice", title_style))
    
    # Invoice details table - using bold fonts for labels
    try:
        bold_font = 'Inter-Bold'
        pdfmetrics.getFont(bold_font)
    except:
        bold_font = 'Helvetica-Bold'
    
    invoice_details = [
        ['Invoice ID:', invoice_number],
        ['Invoice Date:', format_date(invoice_date)],
        ['Due date:', format_date(due_date)],
        ['Payment terms:', f'Net {due_days}']
    ]
    
    details_table = Table(invoice_details, colWidths=[1.5*inch, 3*inch])
    details_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), bold_font),  # Labels in bold
        ('FONTNAME', (1, 0), (1, -1), normal_font),  # Values in regular
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    details_table.hAlign = 'LEFT'  # Force left alignment of the entire table
    story.append(details_table)
    story.append(Spacer(1, 0.5*inch))
    
    # Billing information
    billing_data = []
    
    # Create styles for billing section
    billing_header_style = ParagraphStyle(
        'BillingHeader',
        parent=normal_style,
        fontName=bold_font,
        fontSize=10
    )
    
    billing_text_style = ParagraphStyle(
        'BillingText',
        parent=normal_style,
        fontName=normal_font,
        fontSize=10
    )
    
    # Billed to - make header bold, keep content normal
    billed_to_text = f"<font face='{bold_font}' size='10'><b>Billed to:</b></font><br/>"
    if cycle.get('client_name'):
        billed_to_text += f"{cycle['client_name']}<br/>"
    if cycle.get('client_address'):
        # Replace \n with <br/> for multi-line addresses
        address = cycle['client_address'].replace('\\n', '<br/>').replace('\n', '<br/>')
        billed_to_text += f"{address}<br/>"
    if cycle.get('client_gstin'):
        billed_to_text += f"GSTIN - {cycle['client_gstin']}"
    
    # Pay to - make header bold, keep content normal
    pay_to_text = f"<font face='{bold_font}' size='10'><b>Pay to:</b></font><br/>"
    pay_to_text += f"{profile['full_name']}<br/>"
    if profile.get('address'):
        address = profile['address'].replace('\\n', '<br/>').replace('\n', '<br/>')
        pay_to_text += f"{address}"
    
    billing_table = Table(
        [[Paragraph(billed_to_text, normal_style), 
          Paragraph(pay_to_text, normal_style)]],
        colWidths=[3.5*inch, 3.5*inch]
    )
    billing_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(billing_table)
    story.append(Spacer(1, 0.5*inch))
    
    # Line items table
    if detailed:
        # Detailed invoice with individual line items
        table_data = [['DESCRIPTION', 'DATE', 'HOURS', 'RATE', 'AMOUNT']]
        
        for event in events:
            event_date = datetime.fromisoformat(event['start_time']).strftime('%m/%d')
            description = event['title'][:50]  # Truncate long titles
            hours = f"{event['duration_hours']:.1f}"
            rate = f"{hourly_rate:,.0f}"
            amount = f"{event['duration_hours'] * hourly_rate:,.2f}"
            table_data.append([description, event_date, hours, rate, amount])
        
        # Add subtotal row
        table_data.append(['', '', '', 'SUBTOTAL', f"{total_amount:,.2f} {DEFAULT_CURRENCY}"])
        
        col_widths = [3.5*inch, 0.8*inch, 0.8*inch, 0.8*inch, 1.1*inch]
    else:
        # Summary invoice with single line item
        table_data = [['DESCRIPTION', 'QUANTITY', 'AMOUNT']]
        
        # Format period for description
        cycle_start = datetime.strptime(cycle['start_date'], '%Y-%m-%d').strftime('%b %Y')
        description = f"Consulting Charges - {cycle_start} ({total_hours:.1f} hours * {hourly_rate:,.0f} {DEFAULT_CURRENCY}/hour)"
        
        table_data.append([description, f"{total_hours:.1f}", f"{total_amount:,.2f}"])
        table_data.append(['', 'SUBTOTAL', f"{total_amount:,.2f} {DEFAULT_CURRENCY}"])
        
        col_widths = [4.5*inch, 1.25*inch, 1.25*inch]
    
    items_table = Table(table_data, colWidths=col_widths)
    items_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
        ('FONTNAME', (0, 0), (-1, 0), heading_font),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
        
        # Data rows
        ('FONTNAME', (0, 1), (-1, -2), normal_font),
        ('FONTSIZE', (0, 1), (-1, -2), 9),
        ('ALIGN', (1, 1), (-1, -2), 'RIGHT'),
        ('ALIGN', (0, 1), (0, -2), 'LEFT'),
        
        # Subtotal row
        ('FONTNAME', (-2, -1), (-1, -1), heading_font),
        ('ALIGN', (-2, -1), (-1, -1), 'RIGHT'),
        
        # Grid
        ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
        ('LINEBELOW', (0, -1), (-1, -1), 1, colors.black),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Total
    total_table = Table(
        [['', 'TOTAL'], ['', f"{total_amount:,.2f} {DEFAULT_CURRENCY}"]],
        colWidths=[4.5*inch, 2.5*inch]
    )
    total_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('ALIGN', (1, 1), (1, 1), 'RIGHT'),
        ('FONTNAME', (1, 0), (1, 0), normal_font),
        ('FONTNAME', (1, 1), (1, 1), heading_font),
        ('FONTSIZE', (1, 0), (1, 0), 10),
        ('FONTSIZE', (1, 1), (1, 1), 18),
        ('TOPPADDING', (1, 1), (1, 1), 5),
    ]))
    story.append(total_table)
    story.append(Spacer(1, 0.5*inch))
    
    # Payment Information  
    payment_header_style = ParagraphStyle(
        'PaymentHeader',
        parent=heading_style,
        fontName=bold_font,
        fontSize=12
    )
    story.append(Paragraph("Payment Information", payment_header_style))
    
    payment_info = []
    if profile.get('account_name'):
        payment_info.append(f"Account Name: {profile['account_name']}")
    if profile.get('account_number'):
        payment_info.append(f"Account Number: {profile['account_number']}")
    if profile.get('ifsc_code'):
        payment_info.append(f"IFSC: {profile['ifsc_code']}")
    if profile.get('bank_name'):
        payment_info.append(f"Bank: {profile['bank_name']}")
    if profile.get('account_type'):
        payment_info.append(f"Account Type: {profile['account_type']}")
    if profile.get('pan'):
        payment_info.append(f"PAN: {profile['pan']}")
    
    for info in payment_info:
        story.append(Paragraph(info, normal_style))
    
    # Build PDF
    doc.build(story, onFirstPage=add_logo, onLaterPages=add_logo)
    
    # Save invoice record to database
    Invoice.create(
        cycle_id=cycle['id'],
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        due_date=due_date,
        total_hours=total_hours,
        hourly_rate=hourly_rate,
        total_amount=total_amount,
        pdf_path=str(pdf_path)
    )
    
    return pdf_path


def add_logo(canvas_obj, doc):
    """Add PS logo to the top right of the page."""
    from pathlib import Path
    from config import BASE_DIR
    
    canvas_obj.saveState()
    
    # Logo positioning
    logo_width = 1.2*inch
    logo_height = 1.2*inch
    x = letter[0] - logo_width - 0.75*inch
    y = letter[1] - logo_height - 0.75*inch
    
    # Path to the PS logo
    logo_path = BASE_DIR / "PS.png"
    
    if logo_path.exists():
        # Draw the actual PS logo image
        canvas_obj.drawImage(
            str(logo_path),
            x, y,
            width=logo_width,
            height=logo_height,
            preserveAspectRatio=True,
            mask='auto'
        )
    else:
        # Fallback to text-based logo if image not found
        canvas_obj.setFont("Times-Bold", 42)
        canvas_obj.drawCentredString(x + logo_width/2, y + logo_height/2 - 8, "PS")
    
    canvas_obj.restoreState()


def format_date(date_str: str) -> str:
    """Format date from YYYY-MM-DD to MM/DD/YYYY."""
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    return dt.strftime('%m/%d/%Y')