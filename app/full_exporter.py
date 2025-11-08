import zipfile
import shutil
from pathlib import Path
from datetime import datetime
from pdf_generator import PDFGenerator

class FullExporter:
    """Export complete accounting package for tax advisor"""

    def __init__(self, database, excel_exporter):
        self.db = database
        self.excel_exporter = excel_exporter
        self.pdf_generator = PDFGenerator()

    def export_full_package(self, output_file, year=None, business_id=None):
        """
        Create a ZIP file containing:
        - Excel table with all documents
        - All archived PDFs organized by category
        - Placeholder PDFs for virtual invoices

        Args:
            output_file: Path for the output ZIP file
            year: Optional year filter (default: current year)
            business_id: Optional business filter
        """
        if year is None:
            year = datetime.now().year

        # Create temporary directory for export preparation
        temp_dir = output_file.parent / f'temp_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. Prepare filters
            filters = {'year': year}
            if business_id:
                filters['business_id'] = business_id

            # 2. Generate Excel file with filters
            excel_path = temp_dir / f'Buchhaltung_{year}.xlsx'
            self.excel_exporter.export_to_excel(excel_path, filters)

            # 3. Get all processed invoices for the year

            invoices = self.db.get_all_processed(filters)

            # 4. Create folder structure and copy files
            # Einnahmen/
            #   Honorar/
            #   Lizenzgebühren/
            #   ...
            # Ausgaben/
            #   Büro/
            #   Raum/
            #   ...

            for invoice in invoices:
                invoice_id = invoice.get('invoice_id', '')
                is_income = invoice_id.startswith('ERE')
                category = invoice.get('category', 'Sonstiges')

                # Determine folder path
                type_folder = 'Einnahmen' if is_income else 'Ausgaben'
                category_folder = temp_dir / type_folder / category
                category_folder.mkdir(parents=True, exist_ok=True)

                # Check if physical file exists
                file_path = invoice.get('file_path')
                has_physical_file = file_path and Path(file_path).exists() and not file_path.endswith('.virtual')

                if has_physical_file:
                    # Copy existing PDF
                    source_path = Path(file_path)
                    dest_path = category_folder / source_path.name
                    shutil.copy2(source_path, dest_path)
                else:
                    # Generate placeholder PDF for virtual invoice
                    placeholder_filename = f"{invoice_id}.pdf"
                    placeholder_path = category_folder / placeholder_filename

                    # Get business name
                    business = self.db.get_business(invoice.get('business_id'))
                    business_name = business['name'] if business else 'N/A'

                    invoice_data = {
                        'invoice_id': invoice_id,
                        'date': invoice.get('date'),
                        'amount': invoice.get('amount'),
                        'category': category,
                        'description': invoice.get('description'),
                        'business_name': business_name,
                        'is_recurring_generated': invoice.get('is_recurring_generated', False)
                    }

                    self.pdf_generator.generate_placeholder_pdf(invoice_data, placeholder_path)

            # 5. Create README with instructions
            readme_path = temp_dir / 'README.txt'
            self._create_readme(readme_path, year, len(invoices), business_id)

            # 6. Create ZIP file
            with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in temp_dir.rglob('*'):
                    if file_path.is_file():
                        arcname = file_path.relative_to(temp_dir)
                        zipf.write(file_path, arcname)

            return len(invoices)

        finally:
            # Clean up temporary directory
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def _create_readme(self, readme_path, year, doc_count, business_id):
        """Create README file with export information"""
        business_info = ""
        if business_id:
            business = self.db.get_business(business_id)
            if business:
                business_info = f"\nGeschäft: {business['name']}"

        content = f"""Buchhaltungs-Export {year}
{'=' * 50}

Exportiert am: {datetime.now().strftime('%d.%m.%Y um %H:%M Uhr')}
Steuerjahr: {year}{business_info}
Anzahl Belege: {doc_count}

STRUKTUR:
---------
Buchhaltung_{year}.xlsx  - Excel-Tabelle mit allen Buchungen
Einnahmen/               - Einnahmenbelege nach Kategorie sortiert
Ausgaben/                - Ausgabenbelege nach Kategorie sortiert
README.txt               - Diese Datei

KATEGORIEN:
-----------
Einnahmen:
  - Honorar
  - Lizenzgebühren
  - Workshops
  - Stipendien
  - Verkäufe
  - Sonstiges

Ausgaben:
  - Büro (Hardware, Software, Bürobedarf)
  - Raum (Miete, Nebenkosten)
  - Telefon (Telefon, Internet)
  - Fahrtkosten (Auto, Öffentliche Verkehrsmittel)
  - Fortbildung (Kurse, Fachliteratur)
  - Versicherung (Berufshaftpflicht, etc.)
  - Porto (Versand, Porti)
  - Werbung (Marketing, Anzeigen)
  - Sonstiges

HINWEISE:
---------
• Alle Belege sind chronologisch nach Datum sortiert
• Belege mit der Endung ".pdf" sind physische Originalbelege
• Automatisch generierte Platzhalter-PDFs sind entsprechend gekennzeichnet
• Die Excel-Tabelle enthält alle Buchungen mit laufenden Salden
• Bei Fragen wenden Sie sich bitte an Ihren Buchhalter

Dieses Export-Paket wurde automatisch von der Buchhaltungs-App generiert.
"""

        readme_path.write_text(content, encoding='utf-8')
