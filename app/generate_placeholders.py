#!/usr/bin/env python3
"""
Generate placeholder PDFs for all invoices in the database
"""
import sys
from pathlib import Path
from database import Database
from pdf_generator import PDFGenerator

def main():
    # Initialize
    db_path = Path(__file__).parent / 'invoices.db'
    db = Database(str(db_path))
    pdf_gen = PDFGenerator()

    # Get all processed invoices
    invoices = db.get_all_processed()

    print(f"Found {len(invoices)} processed invoices")

    generated = 0
    skipped = 0

    for invoice in invoices:
        invoice_id = invoice.get('invoice_id')
        if not invoice_id:
            print(f"⚠️  Skipping invoice {invoice.get('id')} - no invoice_id")
            skipped += 1
            continue

        # Determine type and folder
        is_income = invoice_id.startswith('ERE')
        doc_type = 'Einnahmen' if is_income else 'Ausgaben'

        # Get year from date
        date_str = invoice.get('date', '2025-01-01')
        year = date_str[:4] if date_str else '2025'

        # Get business
        business = db.get_business(invoice.get('business_id'))
        business_name = business['name'] if business else 'Unknown'

        # Create archive path
        archive_base = Path('/Users/denis/Developer/Buchhaltung/Archive')
        pdf_dir = archive_base / business_name / doc_type / year
        pdf_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename using minimal format: YYYY-MM-DD_InvoiceID.pdf
        pdf_filename = f"{date_str}_{invoice_id}.pdf"
        pdf_path = pdf_dir / pdf_filename

        # Check if PDF already exists
        if pdf_path.exists():
            print(f"⏭️  Skipping {invoice_id} - PDF already exists")
            skipped += 1
            continue

        # Prepare invoice data
        invoice_data = {
            'invoice_id': invoice_id,
            'date': invoice.get('date'),
            'amount': invoice.get('amount'),
            'category': invoice.get('category'),
            'description': invoice.get('description'),
            'business_name': business_name,
            'is_recurring_generated': invoice.get('is_recurring_generated', False)
        }

        # Generate PDF
        try:
            pdf_gen.generate_placeholder_pdf(invoice_data, pdf_path)
            print(f"✅ Generated {pdf_filename} in {pdf_dir}")

            # Update database with correct path and placeholder flag
            db.update_invoice(invoice['id'], {
                'file_path': str(pdf_path),
                'is_placeholder_pdf': True
            })

            generated += 1
        except Exception as e:
            print(f"❌ Error generating PDF for {invoice_id}: {e}")

    print(f"\n📊 Summary:")
    print(f"  Generated: {generated}")
    print(f"  Skipped: {skipped}")
    print(f"  Total: {len(invoices)}")

if __name__ == '__main__':
    main()
