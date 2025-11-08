from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from datetime import datetime
from pathlib import Path

class PDFGenerator:
    """Generate placeholder PDFs for virtual invoices (recurring/manual bookings)"""

    def __init__(self):
        self.page_width, self.page_height = A4

    def generate_placeholder_pdf(self, invoice_data, output_path):
        """
        Generate a placeholder PDF for a virtual invoice

        Args:
            invoice_data: dict with keys: invoice_id, date, amount, category, description, business_name
            output_path: Path where to save the PDF
        """
        c = canvas.Canvas(str(output_path), pagesize=A4)

        # Set up fonts and colors
        title_font = "Helvetica-Bold"
        body_font = "Helvetica"
        small_font = "Helvetica-Oblique"

        # Starting Y position (from top)
        y_pos = self.page_height - 40*mm

        # Header
        c.setFont(title_font, 18)
        c.drawString(30*mm, y_pos, "Buchhaltungs-Beleg")

        y_pos -= 10*mm
        c.setFont(small_font, 10)
        c.setFillColor(colors.grey)
        c.drawString(30*mm, y_pos, "(Automatisch generierter Platzhalter)")
        c.setFillColor(colors.black)

        # Line separator
        y_pos -= 8*mm
        c.setStrokeColor(colors.grey)
        c.setLineWidth(0.5)
        c.line(30*mm, y_pos, self.page_width - 30*mm, y_pos)

        # Invoice details
        y_pos -= 12*mm
        c.setFont(title_font, 12)
        c.drawString(30*mm, y_pos, f"Belegnummer: {invoice_data.get('invoice_id', 'N/A')}")

        # Details section
        y_pos -= 10*mm
        c.setFont(body_font, 11)

        details = [
            ("Geschäft:", invoice_data.get('business_name', 'N/A')),
            ("Datum:", self._format_date(invoice_data.get('date'))),
            ("Betrag:", self._format_currency(invoice_data.get('amount', 0))),
            ("Kategorie:", invoice_data.get('category', 'N/A')),
            ("Beschreibung:", invoice_data.get('description', 'N/A')),
        ]

        for label, value in details:
            c.setFont(title_font, 10)
            c.drawString(30*mm, y_pos, label)
            c.setFont(body_font, 10)
            c.drawString(60*mm, y_pos, str(value))
            y_pos -= 7*mm

        # Additional info section
        y_pos -= 10*mm
        c.setFont(title_font, 11)
        c.drawString(30*mm, y_pos, "Art der Buchung:")

        y_pos -= 6*mm
        c.setFont(body_font, 10)

        if invoice_data.get('is_recurring_generated'):
            c.drawString(30*mm, y_pos, "✓ Wiederkehrende Buchung (automatisch erstellt)")
        else:
            c.drawString(30*mm, y_pos, "✓ Manuelle Buchung (ohne physischen Beleg)")

        # Footer warning
        y_pos = 40*mm
        c.setFont(small_font, 9)
        c.setFillColor(colors.grey)

        footer_text = [
            "Hinweis: Dies ist ein automatisch generierter Platzhalter-Beleg.",
            "Dieser Beleg dient ausschließlich der internen Dokumentation.",
            "Bei Bedarf kann ein physischer Beleg nachgereicht werden.",
            "",
            f"Generiert am: {datetime.now().strftime('%d.%m.%Y um %H:%M Uhr')}"
        ]

        for line in footer_text:
            c.drawString(30*mm, y_pos, line)
            y_pos -= 5*mm

        # Save PDF
        c.save()

    def _format_date(self, date_str):
        """Format date string to DD.MM.YYYY"""
        if not date_str:
            return "N/A"
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            return date_obj.strftime('%d.%m.%Y')
        except:
            return date_str

    def _format_currency(self, amount):
        """Format amount as German currency: 1.234,56 €"""
        try:
            if amount is None:
                return "0,00 €"
            formatted = f"{float(amount):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            return f"{formatted} €"
        except:
            return "0,00 €"
