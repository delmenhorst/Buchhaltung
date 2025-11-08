from flask import Flask, render_template, request, jsonify, send_file
from pathlib import Path
import os
from datetime import datetime, timedelta
from ocr_processor import OCRProcessor
from income_processor import IncomeProcessor
from database import Database
from excel_export import ExcelExporter
from image_converter import ImageConverter
from folder_manager import FolderManager
from auto_processor import AutoProcessor
from pdf_generator import PDFGenerator
from full_exporter import FullExporter

app = Flask(__name__)

# Load SECRET_KEY from environment or use default (dev only)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# Session configuration for better security and stability
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access (XSS protection)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
app.config['SESSION_REFRESH_EACH_REQUEST'] = True

# Only set SECURE in production (requires HTTPS)
if os.environ.get('FLASK_ENV') != 'development':
    app.config['SESSION_COOKIE_SECURE'] = True

# Paths
BASE_DIR = Path(__file__).parent.parent  # Go up to FINANZEN folder

# Initialize components
APP_DIR = Path(__file__).parent
db = Database(APP_DIR / 'invoices.db')
ocr_processor = OCRProcessor()
income_processor = IncomeProcessor()
excel_exporter = ExcelExporter(db)
folder_manager = FolderManager(BASE_DIR)
image_converter = ImageConverter()
pdf_generator = PDFGenerator()
full_exporter = FullExporter(db, excel_exporter)

# Initialize auto processor (starts background worker)
auto_processor = AutoProcessor(
    db=db,
    folder_manager=folder_manager,
    ocr_processor=ocr_processor,
    income_processor=income_processor,
    image_converter=image_converter
)

# Template filters for German number formatting
@app.template_filter('currency')
def format_currency(value):
    """Format number as German currency with thousand separators: 1.234,56 €"""
    try:
        if value is None:
            return '0,00 €'
        # Convert to float if string
        if isinstance(value, str):
            value = float(value)
        # Format with German locale: thousand separator = . and decimal separator = ,
        formatted = f"{value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        return f"{formatted} €"
    except (ValueError, TypeError):
        return '0,00 €'

@app.route('/')
def index():
    """Dashboard - Main overview page"""
    from datetime import datetime

    business_id = request.args.get('business_id', type=int)
    selected_year = request.args.get('year', type=int, default=datetime.now().year)

    stats = db.get_dashboard_stats(business_id=business_id, year=selected_year)
    stats['selected_year'] = selected_year

    # Get available years from database for year selector
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT strftime('%Y', date) as year
        FROM invoices
        WHERE date IS NOT NULL
        ORDER BY year DESC
    ''')
    available_years = [int(row['year']) for row in cursor.fetchall()]
    conn.close()

    # Always include current year even if no data exists yet
    current_year = datetime.now().year
    if current_year not in available_years:
        available_years.insert(0, current_year)

    stats['available_years'] = available_years

    return render_template('dashboard_new.html', stats=stats)

@app.route('/expenses')
def expenses():
    """Expenses inbox - Shows all expense documents (Inbox + Archive)"""
    business_id = request.args.get('business_id', type=int)

    # Get all expense documents from both Inbox/*/Ausgaben/ and Archive/*/Ausgaben/
    conn = db.get_connection()
    cursor = conn.cursor()

    if business_id:
        cursor.execute('''
            SELECT * FROM invoices
            WHERE (file_path LIKE '%/Ausgaben/%' OR file_path LIKE '%Ausgaben/%')
            AND business_id = ?
            ORDER BY
                CASE WHEN unread = 1 THEN 0 ELSE 1 END,
                processed ASC,
                created_at DESC
        ''', (business_id,))
    else:
        cursor.execute('''
            SELECT * FROM invoices
            WHERE file_path LIKE '%/Ausgaben/%' OR file_path LIKE '%Ausgaben/%'
            ORDER BY
                CASE WHEN unread = 1 THEN 0 ELSE 1 END,
                processed ASC,
                created_at DESC
        ''')

    all_expenses = [dict(row) for row in cursor.fetchall()]
    conn.close()

    # Mark documents as archived or inbox based on file path
    for expense in all_expenses:
        expense['is_archived'] = '/Archive/' in expense['file_path']

    return render_template('inbox_expenses.html', invoices=all_expenses)


@app.route('/process/<int:file_id>')
def process_file(file_id):
    """Process a single file with OCR"""
    file_info = db.get_file(file_id)
    if not file_info:
        return jsonify({'error': 'File not found'}), 404

    file_path = file_info['file_path']

    # Check if a specific model was requested
    model = request.args.get('model')

    # Run OCR (with custom model if specified)
    if model:
        # Create temporary processor with custom model
        from llm_extractor import LLMExtractor
        temp_llm = LLMExtractor(model=model)

        # Use existing OCR processor but override LLM
        original_llm = ocr_processor.llm
        ocr_processor.llm = temp_llm
        result = ocr_processor.process_file(file_path)
        ocr_processor.llm = original_llm  # Restore
    else:
        result = ocr_processor.process_file(file_path)

    # Update database with OCR results
    db.update_ocr_results(file_id, result)

    return jsonify(result)

@app.route('/review')
def review():
    """Page to review and correct OCR results"""
    pending = db.get_pending_review()
    return render_template('review.html', invoices=pending)

@app.route('/api/invoice/<int:file_id>', methods=['GET'])
def get_invoice(file_id):
    """Get invoice details"""
    invoice = db.get_file(file_id)
    if not invoice:
        return jsonify({'error': 'Invoice not found'}), 404
    return jsonify(invoice)

@app.route('/file/<int:file_id>')
def serve_file(file_id):
    """Serve the original file for preview"""
    file_info = db.get_file(file_id)
    if not file_info:
        return "File not found", 404

    # Resolve file_path relative to BASE_DIR (file paths in DB are relative)
    file_path = BASE_DIR / file_info['file_path']

    # Check if it's a placeholder PDF
    if file_info.get('is_placeholder_pdf'):
        # Serve the placeholder PDF if it exists
        if file_path.exists():
            mimetype = 'application/pdf' if file_path.suffix.lower() == '.pdf' else None
            return send_file(file_path, mimetype=mimetype)
        else:
            # No file yet - upload is now handled inline in EAR table
            return "Placeholder PDF not yet generated. Please use the upload button in the table.", 404

    if not file_path.exists():
        return "File not found on disk", 404

    # Safari needs explicit mimetype for PDF preview
    mimetype = 'application/pdf' if file_path.suffix.lower() == '.pdf' else None
    return send_file(file_path, mimetype=mimetype)

@app.route('/api/invoice/<int:file_id>', methods=['POST'])
def update_invoice(file_id):
    """Update invoice details after user review - BUSINESS AWARE"""
    try:
        data = request.json

        # Get file info to determine business AND for rename functionality
        file_info = db.get_file(file_id)
        if not file_info:
            return jsonify({'error': 'File not found'}), 404

        business_id = file_info['business_id']

        # Check if this is an update to an already archived file
        is_updating_archived = file_info.get('is_archived') and '/Archive/' in file_info.get('file_path', '')

        # Check if this is a bulk/partial update (only some fields provided)
        is_bulk_update = not all([data.get('date'), data.get('amount'), data.get('category')])

        # For full updates (initial review), validate required fields
        if not is_bulk_update and not file_info.get('reviewed'):
            if not data.get('date'):
                return jsonify({'error': 'Datum ist erforderlich'}), 400
            if not data.get('amount'):
                return jsonify({'error': 'Betrag ist erforderlich'}), 400
            if not data.get('category'):
                return jsonify({'error': 'Kategorie ist erforderlich'}), 400

        # Update database - only update provided fields
        update_data = {}
        if data.get('date'):
            update_data['date'] = data.get('date')
        if data.get('amount') is not None:
            update_data['amount'] = data.get('amount')
        if data.get('category'):
            update_data['category'] = data.get('category')
        if data.get('description') is not None:
            update_data['description'] = data.get('description')

        # Handle status fields (always respect explicit values)
        if 'unread' in data:
            update_data['unread'] = data.get('unread')
        if 'reviewed' in data:
            update_data['reviewed'] = data.get('reviewed')
        if 'is_archived' in data:
            update_data['is_archived'] = data.get('is_archived')

        # Only mark as reviewed/processed for full updates (if not already set)
        if not is_bulk_update:
            if 'reviewed' not in update_data:
                update_data['reviewed'] = True
            if 'processed' not in update_data:
                update_data['processed'] = True

        # If updating archived file, try to rename it
        if is_updating_archived and not is_bulk_update:
            new_path = db.rename_archived_file(file_id, file_info, data)
            if new_path:
                update_data['file_path'] = new_path

        db.update_invoice(file_id, update_data)

        # For bulk updates, regenerate placeholder PDF if it's a placeholder
        if is_bulk_update and file_info.get('is_placeholder_pdf'):
            file_path = file_info.get('file_path', '')
            if file_path and (BASE_DIR / file_path).exists():
                # Get updated invoice data
                updated_invoice = db.get_file(file_id)
                if updated_invoice.get('invoice_id'):
                    # Regenerate placeholder PDF with updated data
                    try:
                        _regenerate_placeholder_pdf(updated_invoice, pdf_generator, db)
                    except Exception as e:
                        print(f"Warning: Could not regenerate placeholder PDF: {e}")

        # For bulk updates, just return success
        if is_bulk_update:
            return jsonify({'success': True})

        # Generate invoice ID for display (full update only)
        from datetime import datetime
        date_obj = datetime.strptime(data['date'], '%Y-%m-%d')
        next_id = db.get_next_invoice_id(year=date_obj.year, business_id=business_id)

        # Update invoice_id in database
        db.update_invoice(file_id, {'invoice_id': next_id})

        # Move file to Archive after successful save with renamed filename
        try:
            from pathlib import Path
            import shutil

            current_path = Path(file_info['file_path'])
            is_virtual = file_info['file_path'].endswith('.virtual')

            # Get business name for archive path
            business = db.get_business(business_id)
            if not business:
                raise Exception("Business not found")

            year = date_obj.year

            # Generate new filename: YYMMDD_InvoiceID_Category_Description_Amount.pdf
            date_str = date_obj.strftime('%y%m%d')
            category_safe = data.get('category', 'Unknown').replace('/', '-')
            description_safe = (data.get('description', '')[:30]
                              .replace('/', '-')
                              .replace(' ', '_')
                              .strip('_'))
            amount_safe = f"{float(data.get('amount', 0)):.2f}".replace('.', '_')

            new_filename = f"{date_str}_{next_id}_{category_safe}_{description_safe}_{amount_safe}.pdf"
            new_filename = new_filename.replace('__', '_')  # Clean double underscores

            # Correct path: Archive/BusinessName/Ausgaben/Year/filename.pdf
            archive_path = BASE_DIR / 'Archive' / business['name'] / 'Ausgaben' / str(year) / new_filename

            # Create archive directory if needed
            archive_path.parent.mkdir(parents=True, exist_ok=True)

            if is_virtual or not current_path.exists():
                # Generate placeholder PDF for virtual/missing invoices
                invoice_data = {
                    'invoice_id': next_id,
                    'date': data.get('date'),
                    'amount': data.get('amount'),
                    'category': data.get('category'),
                    'description': data.get('description'),
                    'business_name': business['name'],
                    'is_recurring_generated': file_info.get('is_recurring_generated', False)
                }
                pdf_generator.generate_placeholder_pdf(invoice_data, archive_path)
                print(f"✅ Generated placeholder PDF for {next_id} at {archive_path}")
            elif '/Inbox/' in str(current_path):
                # Move physical file to archive with new name
                shutil.move(str(current_path), str(archive_path))

            # Update database with new path and set placeholder flag if PDF was generated
            update_data = {'file_path': str(archive_path), 'is_archived': True}
            if is_virtual or not current_path.exists():
                update_data['is_placeholder_pdf'] = True
            db.update_invoice(file_id, update_data)
        except Exception as e:
            print(f"Warning: Could not archive file: {e}")
            # Continue anyway - data is saved

        return jsonify({
            'success': True,
            'invoice_id': next_id
        })
    except ValueError as e:
        return jsonify({'error': f'Ungültiges Datumsformat: {str(e)}'}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Fehler beim Speichern: {str(e)}'}), 500

@app.route('/api/categories')
def get_categories():
    """Get list of available categories - Steuer-relevante Kategorien"""
    categories = [
        'Büro',           # Bürobedarf, Hardware, Software
        'Raum',           # Miete, Nebenkosten
        'Telefon',        # Telefon, Internet
        'Fahrtkosten',    # Auto, Öffentliche Verkehrsmittel
        'Fortbildung',    # Kurse, Literatur
        'Versicherung',   # Berufshaftpflicht, etc.
        'Porto',          # Versand, Porti
        'Werbung',        # Marketing, Anzeigen
        'Sonstiges'       # Andere abzugsfähige Kosten
    ]
    return jsonify(categories)

@app.route('/export/excel')
def export_excel():
    """Export all processed invoices to Excel"""
    from datetime import datetime

    # Get filter parameters (same as /documents route)
    business_id = request.args.get('business_id', type=int)
    selected_year = request.args.get('year', type=int, default=datetime.now().year)

    filters = {
        'type': request.args.get('type'),
        'category': request.args.get('category'),
        'date_from': request.args.get('date_from'),
        'date_to': request.args.get('date_to'),
        'search': request.args.get('search'),
        'business_id': business_id,
        'year': selected_year
    }

    # Remove None values
    filters = {k: v for k, v in filters.items() if v}

    output_file = APP_DIR / 'export' / 'ausgaben_export.xlsx'
    output_file.parent.mkdir(exist_ok=True)

    excel_exporter.export_to_excel(output_file, filters)

    return send_file(output_file, as_attachment=True)

@app.route('/export/full')
def export_full():
    """Export complete package: Excel + all PDFs + placeholders (for tax advisor)"""
    from datetime import datetime

    # Get filter parameters
    year = request.args.get('year', type=int, default=datetime.now().year)
    business_id = request.args.get('business_id', type=int)

    # Create export
    output_file = APP_DIR / 'export' / f'Buchhaltung_{year}.zip'
    output_file.parent.mkdir(exist_ok=True)

    full_exporter.export_full_package(output_file, year=year, business_id=business_id)

    return send_file(output_file, as_attachment=True, download_name=f'Buchhaltung_{year}.zip')

@app.route('/stats')
def stats():
    """Show statistics"""
    stats = db.get_statistics()
    return render_template('stats.html', stats=stats)

@app.route('/search')
def search():
    """Search page for documents"""
    query = request.args.get('q', '')
    business_id = request.args.get('business_id', type=int)
    
    results = []
    if query:
        filters = {
            'search': query,
            'business_id': business_id
        }
        filters = {k: v for k, v in filters.items() if v}
        results = db.get_all_processed(filters)
    
    return render_template('search.html', query=query, results=results)

@app.route('/documents')
def documents():
    """Combined EAR table - All documents (Einnahmen + Ausgaben)"""
    from datetime import datetime

    # Get filter parameters
    business_id = request.args.get('business_id', type=int)
    selected_year = request.args.get('year', type=int, default=datetime.now().year)

    filters = {
        'type': request.args.get('type'),
        'category': request.args.get('category'),
        'date_from': request.args.get('date_from'),
        'date_to': request.args.get('date_to'),
        'search': request.args.get('search'),
        'business_id': business_id,
        'year': selected_year
    }

    # Remove None values
    filters = {k: v for k, v in filters.items() if v}

    documents = db.get_all_processed(filters)

    # Calculate running balance (overall)
    balance = 0
    for doc in reversed(documents):
        if doc['invoice_id'] and doc['invoice_id'].startswith('ERE'):
            balance += doc['amount'] or 0
        elif doc['invoice_id'] and doc['invoice_id'].startswith('ARE'):
            balance -= doc['amount'] or 0
        doc['balance'] = balance

    # Calculate category balances (running sum per category for the year)
    category_balances = {}
    for doc in reversed(documents):
        category = doc.get('category')
        if category:
            if category not in category_balances:
                category_balances[category] = 0

            # Add to category balance
            if doc['invoice_id'] and doc['invoice_id'].startswith('ERE'):
                category_balances[category] += doc['amount'] or 0
            elif doc['invoice_id'] and doc['invoice_id'].startswith('ARE'):
                category_balances[category] += doc['amount'] or 0

            doc['category_balance'] = category_balances[category]
        else:
            doc['category_balance'] = 0

    # Reverse back to show newest first
    documents.reverse()

    # Calculate totals
    total_income = sum(doc['amount'] for doc in documents if doc['invoice_id'] and doc['invoice_id'].startswith('ERE'))
    total_expenses = sum(doc['amount'] for doc in documents if doc['invoice_id'] and doc['invoice_id'].startswith('ARE'))
    final_balance = documents[0]['balance'] if documents else 0

    # Get all categories for filter (filtered by business if applicable)
    all_docs = db.get_all_processed({'business_id': business_id} if business_id else {})
    categories = sorted(set(doc['category'] for doc in all_docs if doc['category']))

    # Get available years from database for year selector
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT strftime('%Y', date) as year
        FROM invoices
        WHERE date IS NOT NULL
        ORDER BY year DESC
    ''')
    available_years = [int(row['year']) for row in cursor.fetchall()]
    conn.close()

    # Always include current year even if no data exists yet
    current_year = datetime.now().year
    if current_year not in available_years:
        available_years.insert(0, current_year)

    return render_template('ear_table.html',
                         documents=documents,
                         categories=categories,
                         filters=filters,
                         total_income=total_income,
                         total_expenses=total_expenses,
                         final_balance=final_balance,
                         selected_year=selected_year,
                         available_years=available_years)

# ============================================================
# EINNAHMEN ROUTES
# ============================================================


@app.route('/income/process/<int:file_id>')
def process_income_file(file_id):
    """Process a single income file with OCR"""
    file_info = db.get_file(file_id)
    if not file_info:
        return jsonify({'error': 'File not found'}), 404

    file_path = file_info['file_path']

    # Check if a specific model was requested
    model = request.args.get('model')

    # Run OCR with income processor (with custom model if specified)
    if model:
        # Create temporary processor with custom model
        from llm_extractor import LLMExtractor
        temp_llm = LLMExtractor(model=model)

        # Use existing income processor but override LLM
        original_llm = income_processor.llm
        income_processor.llm = temp_llm
        result = income_processor.process_file(file_path)
        income_processor.llm = original_llm  # Restore
    else:
        result = income_processor.process_file(file_path)

    # Update database with OCR results
    db.update_ocr_results(file_id, result)

    return jsonify(result)

@app.route('/income')
def income_inbox():
    """Income inbox - Shows all income documents (Inbox + Archive)"""
    business_id = request.args.get('business_id', type=int)

    # Get all income documents from both Inbox/*/Einnahmen/ and Archive/*/Einnahmen/
    conn = db.get_connection()
    cursor = conn.cursor()

    if business_id:
        cursor.execute('''
            SELECT * FROM invoices
            WHERE (file_path LIKE '%/Einnahmen/%' OR file_path LIKE '%Einnahmen/%')
            AND business_id = ?
            ORDER BY
                CASE WHEN unread = 1 THEN 0 ELSE 1 END,
                processed ASC,
                created_at DESC
        ''', (business_id,))
    else:
        cursor.execute('''
            SELECT * FROM invoices
            WHERE file_path LIKE '%/Einnahmen/%' OR file_path LIKE '%Einnahmen/%'
            ORDER BY
                CASE WHEN unread = 1 THEN 0 ELSE 1 END,
                processed ASC,
                created_at DESC
        ''')

    all_income = [dict(row) for row in cursor.fetchall()]
    conn.close()

    # Mark documents as archived or inbox based on file path
    for income in all_income:
        income['is_archived'] = '/Archive/' in income['file_path']

    return render_template('inbox_income.html', invoices=all_income)

@app.route('/income/review')
def income_review():
    """Page to review and correct income OCR results (OLD - keep for compatibility)"""
    pending = db.get_pending_income_review()
    return render_template('income/review.html', invoices=pending)

@app.route('/api/income/<int:file_id>', methods=['GET'])
def get_income(file_id):
    """Get income details"""
    income = db.get_file(file_id)
    if not income:
        return jsonify({'error': 'Income not found'}), 404
    return jsonify(income)

@app.route('/api/income/<int:file_id>', methods=['POST'])
def update_income(file_id):
    """Update income details after user review - BUSINESS AWARE"""
    try:
        data = request.json

        # Validate required fields
        if not data.get('date'):
            return jsonify({'error': 'Datum ist erforderlich'}), 400
        if not data.get('amount'):
            return jsonify({'error': 'Betrag ist erforderlich'}), 400
        if not data.get('category'):
            return jsonify({'error': 'Kategorie ist erforderlich'}), 400

        # Get file info to determine business AND for rename functionality
        file_info = db.get_file(file_id)
        if not file_info:
            return jsonify({'error': 'File not found'}), 404

        business_id = file_info['business_id']

        # Check if this is an update to an already archived file
        is_updating_archived = file_info.get('is_archived') and '/Archive/' in file_info.get('file_path', '')

        # Update database with income-specific fields - mark as reviewed (file stays in Inbox)
        update_data = {
            'date': data.get('date'),
            'amount': data.get('amount'),
            'category': data.get('category'),
            'description': data.get('description'),
            'reviewed': True,
            'processed': True,
            # Income-specific fields
            'invoice_number': data.get('invoice_number'),
            'customer_name': data.get('customer_name'),
            'customer_address': data.get('customer_address'),
            'payment_due_date': data.get('payment_due_date'),
            'payment_terms': data.get('payment_terms'),
            'tax_rate': data.get('tax_rate'),
            'tax_amount': data.get('tax_amount'),
            'net_amount': data.get('net_amount')
        }

        # Handle status fields (always respect explicit values)
        if 'unread' in data:
            update_data['unread'] = data.get('unread')
        if 'is_archived' in data:
            update_data['is_archived'] = data.get('is_archived')

        # If updating archived file, try to rename it
        if is_updating_archived:
            new_path = db.rename_archived_file(file_id, file_info, data)
            if new_path:
                update_data['file_path'] = new_path

        db.update_invoice(file_id, update_data)

        # Generate income ID for display
        from datetime import datetime
        date_obj = datetime.strptime(data['date'], '%Y-%m-%d')
        next_id = db.get_next_income_id(year=date_obj.year, business_id=business_id)

        # Update invoice_id in database
        db.update_invoice(file_id, {'invoice_id': next_id})

        # Move file to Archive after successful save with renamed filename
        try:
            from pathlib import Path
            import shutil

            current_path = Path(file_info['file_path'])
            is_virtual = file_info['file_path'].endswith('.virtual')

            # Get business name for archive path
            business = db.get_business(business_id)
            if not business:
                raise Exception("Business not found")

            year = date_obj.year

            # Generate new filename: YYMMDD_InvoiceID_Category_Description_Amount.pdf
            date_str = date_obj.strftime('%y%m%d')
            category_safe = data.get('category', 'Unknown').replace('/', '-')
            description_safe = (data.get('description', '')[:30]
                              .replace('/', '-')
                              .replace(' ', '_')
                              .strip('_'))
            amount_safe = f"{float(data.get('amount', 0)):.2f}".replace('.', '_')

            new_filename = f"{date_str}_{next_id}_{category_safe}_{description_safe}_{amount_safe}.pdf"
            new_filename = new_filename.replace('__', '_')  # Clean double underscores

            # Correct path: Archive/BusinessName/Einnahmen/Year/filename.pdf
            archive_path = BASE_DIR / 'Archive' / business['name'] / 'Einnahmen' / str(year) / new_filename

            # Create archive directory if needed
            archive_path.parent.mkdir(parents=True, exist_ok=True)

            if is_virtual or not current_path.exists():
                # Generate placeholder PDF for virtual/missing invoices
                invoice_data = {
                    'invoice_id': next_id,
                    'date': data.get('date'),
                    'amount': data.get('amount'),
                    'category': data.get('category'),
                    'description': data.get('description'),
                    'business_name': business['name'],
                    'is_recurring_generated': file_info.get('is_recurring_generated', False)
                }
                pdf_generator.generate_placeholder_pdf(invoice_data, archive_path)
                print(f"✅ Generated placeholder PDF for income {next_id} at {archive_path}")
            elif '/Inbox/' in str(current_path):
                # Move physical file to archive with new name
                shutil.move(str(current_path), str(archive_path))

            # Update database with new path and set placeholder flag if PDF was generated
            update_data = {'file_path': str(archive_path), 'is_archived': True}
            if is_virtual or not current_path.exists():
                update_data['is_placeholder_pdf'] = True
            db.update_invoice(file_id, update_data)
        except Exception as e:
            print(f"Warning: Could not archive file: {e}")
            # Continue anyway - data is saved

        return jsonify({
            'success': True,
            'invoice_id': next_id
        })
    except ValueError as e:
        return jsonify({'error': f'Ungültiges Datumsformat: {str(e)}'}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Fehler beim Speichern: {str(e)}'}), 500

@app.route('/api/income/categories')
def get_income_categories():
    """Get list of available income categories"""
    categories = [
        'Honorar',              # Haupteinnahmequelle
        'Lizenzgebühren',       # Für Wiederverwendung
        'Workshops',            # Lehrtätigkeiten
        'Stipendien',           # Förderungen
        'Verkäufe',             # Materieller Verkauf
        'Sonstiges'
    ]
    return jsonify(categories)

@app.route('/api/invoice/<int:file_id>/flag', methods=['POST'])
def flag_invoice(file_id):
    """Toggle flag status for a document"""
    try:
        data = request.json
        flagged = data.get('flagged', False)

        db.update_invoice(file_id, {'flagged': flagged})

        return jsonify({'success': True, 'flagged': flagged})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/invoice/<int:file_id>/mark-read', methods=['POST'])
def mark_invoice_read(file_id):
    """Mark invoice as read"""
    try:
        db.update_invoice(file_id, {'unread': False})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/invoice/<int:file_id>/toggle-flag', methods=['POST'])
def toggle_invoice_flag(file_id):
    """Toggle flagged status"""
    try:
        invoice = db.get_file(file_id)
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404

        new_status = not invoice.get('flagged', False)
        db.update_invoice(file_id, {'flagged': new_status})
        return jsonify({'success': True, 'flagged': new_status})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/invoice/<int:file_id>', methods=['DELETE'])
def delete_invoice(file_id):
    """Delete an invoice"""
    try:
        from pathlib import Path

        invoice = db.get_file(file_id)
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404

        # Delete physical file if it exists and is not a virtual file
        if invoice['file_path'] and not invoice.get('is_recurring_generated'):
            file_path = BASE_DIR / invoice['file_path']
            if file_path.exists():
                file_path.unlink()

        # Delete from database
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM invoices WHERE id = ?', (file_id,))
        conn.commit()
        conn.close()

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/invoice/<int:file_id>/upload', methods=['POST'])
def upload_file_to_invoice(file_id):
    """Upload or replace file for an invoice"""
    try:
        from werkzeug.utils import secure_filename
        import os
        from datetime import datetime

        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # Get invoice
        invoice = db.get_file(file_id)
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404

        # Validate file extension
        allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.heic'}
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            return jsonify({'error': 'Invalid file type. Allowed: PDF, JPG, PNG, HEIC'}), 400

        # Get business info
        business = db.get_business(invoice['business_id']) if invoice.get('business_id') else None
        business_folder = business['name'] if business else 'Default'

        # Determine if income or expense
        is_income = invoice.get('invoice_id', '').startswith('ERE')
        type_folder = 'Einnahmen' if is_income else 'Ausgaben'

        # Check if this invoice is already archived
        is_archived = invoice.get('is_archived') and '/Archive/' in invoice.get('file_path', '')

        if is_archived:
            # Save directly to Archive with semantic filename
            # Extract year from invoice date
            date_str = invoice.get('date')
            if date_str:
                try:
                    if isinstance(date_str, str):
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    else:
                        date_obj = date_str
                    year = date_obj.year
                except:
                    year = datetime.now().year
            else:
                year = datetime.now().year

            # Create Archive folder path with year
            archive_path = BASE_DIR / 'Archive' / business_folder / type_folder / str(year)
            archive_path.mkdir(parents=True, exist_ok=True)

            # Generate semantic filename: YYMMDD_InvoiceID_Category_Description_Amount.pdf
            if date_str:
                try:
                    date_part = date_obj.strftime('%y%m%d')
                except:
                    date_part = datetime.now().strftime('%y%m%d')
            else:
                date_part = datetime.now().strftime('%y%m%d')

            invoice_id = invoice.get('invoice_id', 'UNKNOWN')
            category = invoice.get('category', 'Unknown')
            description = invoice.get('description', '')
            amount = invoice.get('amount', 0)

            # Sanitize filename components
            category_safe = category.replace('/', '-')
            description_safe = (description[:30]
                              .replace('/', '-')
                              .replace(' ', '_')
                              .strip('_'))
            amount_safe = str(amount).replace('.', '_')

            new_filename = f"{date_part}_{invoice_id}_{category_safe}_{description_safe}_{amount_safe}{file_ext}"
            new_filename = new_filename.replace('__', '_')  # Clean double underscores

            file_path = archive_path / new_filename
        else:
            # Save to Inbox for processing
            inbox_path = BASE_DIR / 'Inbox' / business_folder / type_folder
            inbox_path.mkdir(parents=True, exist_ok=True)

            # Generate timestamped filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_description = secure_filename(invoice.get('description', 'document'))[:30]
            new_filename = f"{timestamp}_{safe_description}{file_ext}"
            file_path = inbox_path / new_filename

        # Save file
        file.save(str(file_path))

        # Convert to PDF if needed (HEIC, JPG, PNG → PDF)
        if file_ext in {'.heic', '.jpg', '.jpeg', '.png'}:
            pdf_path = image_converter.convert_to_pdf(file_path)
            if pdf_path:
                # Remove original image
                file_path.unlink()
                file_path = pdf_path

        # Delete old file if it exists
        if invoice.get('file_path'):
            old_path = Path(invoice['file_path'])
            if old_path.exists() and old_path != file_path:
                try:
                    old_path.unlink()
                except Exception as e:
                    print(f"Warning: Could not delete old file: {e}")

        # Update database with new file path and clear placeholder flag
        update_data = {
            'file_path': str(file_path),
            'is_placeholder_pdf': False
        }
        # Preserve is_archived status if file was already archived
        if is_archived:
            update_data['is_archived'] = True

        db.update_invoice(file_id, update_data)

        # Run OCR automatically after upload (use correct processor based on type)
        try:
            # Use income processor for ERE invoices, expense processor for ARE invoices
            if is_income:
                result = income_processor.process_file(str(file_path))
            else:
                result = ocr_processor.process_file(str(file_path))

            db.update_ocr_results(file_id, result)

            return jsonify({
                'success': True,
                'file_path': str(file_path),
                'filename': file_path.name,
                'ocr_result': result
            })
        except Exception as ocr_error:
            print(f"OCR error: {ocr_error}")
            # Return success even if OCR fails - file is uploaded
            return jsonify({
                'success': True,
                'file_path': str(file_path),
                'filename': file_path.name,
                'ocr_error': str(ocr_error)
            })

    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/invoice', methods=['POST'])
def create_manual_invoice():
    """Create a manual invoice entry without PDF"""
    try:
        data = request.json

        # Validate required fields
        required = ['date', 'amount', 'category', 'description', 'type']
        for field in required:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400

        # Get business_id from request body (not query params)
        business_id = data.get('business_id')

        # Get business info
        business = db.get_business(business_id) if business_id else None
        business_folder = business['name'] if business else 'Default'
        type_folder = 'Einnahmen' if data['type'] == 'income' else 'Ausgaben'

        # Create virtual file path - manual entries go directly to Archive
        from datetime import datetime
        date_obj = datetime.strptime(data['date'], '%Y-%m-%d')
        date_str = date_obj.strftime('%y%m%d')  # YY format for archive
        year = date_obj.year

        # Generate invoice_id immediately
        next_id = db.get_next_invoice_id(year=year, business_id=business_id)

        # Create filename with invoice_id like archived files
        category_safe = data.get('category', 'Unknown').replace('/', '-')
        description_safe = (data.get('description', '')[:30]
                          .replace('/', '-')
                          .replace(' ', '_')
                          .strip('_'))
        amount_safe = f"{float(data.get('amount', 0)):.2f}".replace('.', '_')

        filename = f"{date_str}_{next_id}_{category_safe}_{description_safe}_{amount_safe}.virtual"
        filename = filename.replace('__', '_')  # Clean double underscores

        # Put directly in Archive since it's already complete
        file_path = f"Archive/{business_folder}/{type_folder}/{year}/{filename}"

        # Create archive directory if it doesn't exist
        from pathlib import Path
        archive_dir = BASE_DIR / 'Archive' / business_folder / type_folder / str(year)
        archive_dir.mkdir(parents=True, exist_ok=True)

        # Insert into database
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO invoices
            (file_path, original_filename, business_id, date, amount, category,
             description, reviewed, processed, unread, invoice_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, 0, ?)
        ''', (
            file_path,
            filename,
            business_id,
            data['date'],
            data['amount'],
            data['category'],
            data['description'],
            next_id
        ))

        conn.commit()
        invoice_id = cursor.lastrowid
        conn.close()

        # Generate placeholder PDF automatically
        try:
            # Determine if income or expense
            is_income = data['type'] == 'income'

            # Create semantic PDF filename: YYMMDD_InvoiceID_Category_Description_Amount.pdf
            pdf_filename = f"{date_str}_{next_id}_{category_safe}_{description_safe}_{amount_safe}.pdf"
            pdf_filename = pdf_filename.replace('__', '_')  # Clean double underscores
            pdf_path = archive_dir / pdf_filename

            # Prepare invoice data for PDF generation
            invoice_data = {
                'invoice_id': next_id,
                'date': data['date'],
                'amount': data['amount'],
                'category': data['category'],
                'description': data['description'],
                'business_name': business_folder,
                'is_recurring_generated': False
            }

            # Generate placeholder PDF
            pdf_generator.generate_placeholder_pdf(invoice_data, str(pdf_path))

            # Update database with real PDF path and placeholder flag
            new_file_path = f"Archive/{business_folder}/{type_folder}/{year}/{pdf_filename}"
            db.update_invoice(invoice_id, {
                'file_path': new_file_path,
                'is_placeholder_pdf': True
            })

            print(f"✅ Generated placeholder PDF: {pdf_filename}")
        except Exception as pdf_error:
            print(f"⚠️  Warning: Could not generate placeholder PDF: {pdf_error}")
            # Don't fail the request if PDF generation fails

        return jsonify({'success': True, 'id': invoice_id, 'invoice_number': next_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ollama/models', methods=['GET'])
def get_ollama_models():
    """Get list of available Ollama models"""
    try:
        import subprocess
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=5)

        if result.returncode == 0:
            # Parse ollama list output
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            models = []
            for line in lines:
                parts = line.split()
                if parts:
                    model_name = parts[0]
                    models.append({
                        'name': model_name,
                        'display_name': model_name.split(':')[0].title()
                    })
            return jsonify({'models': models, 'available': True})
        else:
            return jsonify({'models': [], 'available': False, 'error': 'Ollama not running'})
    except FileNotFoundError:
        return jsonify({'models': [], 'available': False, 'error': 'Ollama not installed'})
    except Exception as e:
        return jsonify({'models': [], 'available': False, 'error': str(e)})

@app.route('/api/inbox-counts')
def get_inbox_counts():
    """Get unprocessed document counts for sidebar badges - only Inbox items (not archived)"""
    business_id = request.args.get('business_id', type=int)

    # Get all pending items
    all_income = db.get_pending_income_review()
    all_expenses = db.get_pending_review()

    # Filter by business if specified AND exclude archived items
    if business_id:
        income_count = sum(1 for item in all_income
                          if item.get('business_id') == business_id
                          and '/Archive/' not in item.get('file_path', ''))
        expense_count = sum(1 for item in all_expenses
                           if item.get('business_id') == business_id
                           and '/Archive/' not in item.get('file_path', ''))
    else:
        # Exclude archived items (those with /Archive/ in path)
        income_count = sum(1 for item in all_income if '/Archive/' not in item.get('file_path', ''))
        expense_count = sum(1 for item in all_expenses if '/Archive/' not in item.get('file_path', ''))

    return jsonify({
        'income': income_count,
        'expenses': expense_count
    })

# ============================================================
# BUSINESS MANAGEMENT API
# ============================================================

@app.route('/settings')
def settings():
    """Settings page - manage businesses"""
    return render_template('settings.html')

@app.route('/api/businesses', methods=['GET'])
def get_businesses():
    """Get all businesses"""
    businesses = db.get_all_businesses()
    return jsonify(businesses)

@app.route('/api/businesses', methods=['POST'])
def create_business():
    """Create a new business"""
    data = request.json

    try:
        # Create business in database
        business_id = db.create_business(
            name=data['name'],
            prefix=data['prefix'],
            color=data.get('color', '#007AFF')
        )

        # Create folder structure
        paths = folder_manager.create_business_folders(data['name'])

        # Update business with paths
        db.update_business(business_id, {
            'name': data['name'],
            'prefix': data['prefix'],
            'color': data.get('color', '#007AFF'),
            'inbox_path': paths['inbox'],
            'archive_path': paths['archive_base']
        })

        return jsonify({
            'success': True,
            'id': business_id,
            'paths': paths
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Fehler beim Erstellen: {str(e)}'}), 500

@app.route('/api/businesses/<int:business_id>', methods=['PUT'])
def update_business(business_id):
    """Update a business"""
    data = request.json

    try:
        db.update_business(business_id, data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/businesses/<int:business_id>', methods=['DELETE'])
def delete_business(business_id):
    """
    Delete a business with optional cascade or reassign

    Query params:
        cascade=true  - Delete all associated invoices and files
        reassign_to=<id> - Move all invoices to another business
    """
    try:
        # Get business info for folder deletion
        business = db.get_business(business_id)
        if not business:
            return jsonify({'error': 'Business not found'}), 404

        # Get query parameters
        cascade = request.args.get('cascade', 'false').lower() == 'true'
        reassign_to = request.args.get('reassign_to', type=int)

        # Delete from database with options
        db.delete_business(business_id, cascade=cascade, reassign_to=reassign_to)

        # Delete folders only if cascade (otherwise invoices might still reference them)
        if cascade:
            folder_manager.delete_business_folders(business['name'])

        return jsonify({'success': True})

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================
# UNIFIED INBOX API
# ============================================================

@app.route('/inbox')
def unified_inbox():
    """Unified inbox - shows all documents from all businesses"""
    return render_template('inbox_unified.html')

@app.route('/api/inbox', methods=['GET'])
def get_inbox_documents():
    """Get all documents from all business inbox folders (Einnahmen + Ausgaben)"""
    all_docs = []

    # Get all businesses
    businesses = db.get_all_businesses()

    # Scan each business's inbox folder (both Einnahmen and Ausgaben)
    for business in businesses:
        files_with_type = folder_manager.get_inbox_files(business['name'])

        for file_path, doc_type in files_with_type:
            # Check if already in database
            if db.file_exists(str(file_path)):
                # Get from database
                file_info = db.get_file_by_path(str(file_path))
                if file_info:
                    file_info['business'] = business
                    file_info['doc_type'] = doc_type  # Einnahmen or Ausgaben
                    all_docs.append(file_info)
            else:
                # Add to database
                file_id = db.add_file(str(file_path), business['id'])
                if file_id:
                    file_info = db.get_file(file_id)
                    if file_info:
                        file_info['business'] = business
                        file_info['doc_type'] = doc_type  # Einnahmen or Ausgaben
                        file_info['filename'] = Path(file_path).name
                        file_info['size'] = file_path.stat().st_size
                        all_docs.append(file_info)

    return jsonify(all_docs)

@app.route('/api/inbox/scan', methods=['POST'])
def scan_all_inboxes():
    """Scan all business inbox folders for new files"""
    total_new = 0
    businesses = db.get_all_businesses()

    for business in businesses:
        files_with_type = folder_manager.get_inbox_files(business['name'])
        for file_path, doc_type in files_with_type:
            if not db.file_exists(str(file_path)):
                db.add_file(str(file_path), business['id'])
                total_new += 1

    return jsonify({
        'success': True,
        'message': f'{total_new} neue Dateien gefunden'
    })

@app.route('/api/auto-processor/status')
def get_auto_processor_status():
    """Get status of auto processor"""
    return jsonify({
        'running': auto_processor.running,
        'check_interval': auto_processor.check_interval
    })

@app.route('/api/auto-processor/toggle', methods=['POST'])
def toggle_auto_processor():
    """Start/stop auto processor"""
    if auto_processor.running:
        auto_processor.stop()
        return jsonify({'status': 'stopped'})
    else:
        auto_processor.start()
        return jsonify({'status': 'started'})

if __name__ == '__main__':
    # Initialize database
    db.init_db()

    # Start auto processor background worker
    auto_processor.start()

# ============================================================
# RECURRING TRANSACTIONS ROUTES
# ============================================================

@app.route('/recurring')
def recurring_transactions_page():
    """Page to manage recurring transactions"""
    business_id = request.args.get('business_id', type=int)
    recurring_list = db.get_recurring_transactions(business_id=business_id, active_only=False)
    return render_template('recurring.html', recurring_transactions=recurring_list)

@app.route('/api/recurring', methods=['GET'])
def get_recurring_transactions_api():
    """Get all recurring transactions"""
    business_id = request.args.get('business_id', type=int)
    active_only = request.args.get('active_only', 'true').lower() == 'true'
    recurring = db.get_recurring_transactions(business_id=business_id, active_only=active_only)
    return jsonify(recurring)

@app.route('/api/recurring', methods=['POST'])
def create_recurring_transaction():
    """Create a new recurring transaction"""
    try:
        data = request.json

        # Validate required fields
        required = ['type', 'description', 'amount', 'category', 'frequency', 'start_date']
        for field in required:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400

        # Get business_id from query params or JSON
        if 'business_id' not in data:
            data['business_id'] = request.args.get('business_id', type=int)

        recurring_id = db.create_recurring_transaction(data)

        # Immediately generate entries for this recurring transaction
        generated_ids = db.generate_recurring_transactions()
        print(f"✅ Created recurring transaction {recurring_id}, generated {len(generated_ids)} entries")

        # Generate placeholders with invoice_ids for all new entries
        if generated_ids:
            placeholder_ids = generate_missing_placeholders()
            print(f"✅ Generated {len(placeholder_ids)} placeholders with invoice IDs")

        return jsonify({'success': True, 'id': recurring_id, 'generated': len(generated_ids)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/recurring/<int:recurring_id>', methods=['GET'])
def get_recurring_transaction(recurring_id):
    """Get a single recurring transaction"""
    recurring = db.get_recurring_transaction(recurring_id)
    if not recurring:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(recurring)

@app.route('/api/recurring/<int:recurring_id>', methods=['PUT'])
def update_recurring_transaction_api(recurring_id):
    """Update a recurring transaction"""
    try:
        data = request.json
        db.update_recurring_transaction(recurring_id, data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/recurring/<int:recurring_id>', methods=['DELETE'])
def delete_recurring_transaction_api(recurring_id):
    """Delete a recurring transaction"""
    try:
        db.delete_recurring_transaction(recurring_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/recurring/generate', methods=['POST'])
def generate_recurring():
    """Manually trigger generation of recurring transactions"""
    try:
        generated_ids = db.generate_recurring_transactions()
        return jsonify({'success': True, 'generated': len(generated_ids), 'ids': generated_ids})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _regenerate_placeholder_pdf(invoice_data, pdf_gen, database):
    """Helper function to regenerate placeholder PDF after updates"""
    file_path = invoice_data.get('file_path', '')
    if not file_path:
        return

    # Resolve relative path to absolute path
    absolute_path = BASE_DIR / file_path
    if not absolute_path.exists():
        return

    # Get business name
    business = database.get_business(invoice_data.get('business_id'))
    business_name = business['name'] if business else 'N/A'

    # Prepare data for PDF generation
    pdf_data = {
        'invoice_id': invoice_data.get('invoice_id'),
        'date': invoice_data.get('date'),
        'amount': invoice_data.get('amount'),
        'category': invoice_data.get('category'),
        'description': invoice_data.get('description'),
        'business_name': business_name,
        'is_recurring_generated': invoice_data.get('is_recurring_generated', False)
    }

    # Regenerate PDF at the same location
    pdf_gen.generate_placeholder_pdf(pdf_data, absolute_path)
    print(f"✅ Regenerated placeholder PDF for {invoice_data.get('invoice_id')}")

# ============================================================
# STARTUP
# ============================================================

def generate_missing_placeholders():
    """Generate placeholder PDFs for all invoices without a file"""
    try:
        # Get all invoices
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, business_id, invoice_id, date, amount, category, description, file_path, is_archived, is_recurring_generated
            FROM invoices
            WHERE invoice_id IS NOT NULL AND (file_path IS NULL OR file_path = '' OR NOT EXISTS (
                SELECT 1 WHERE file_path LIKE '%.pdf'
            ))
        ''')
        invoices_without_pdf = cursor.fetchall()
        conn.close()

        if not invoices_without_pdf:
            return []

        generated = []
        for invoice in invoices_without_pdf:
            invoice_dict = dict(invoice)

            # Skip if already has a placeholder or no invoice_id
            if not invoice_dict.get('invoice_id'):
                continue

            # Get business info
            business = db.get_business(invoice_dict['business_id'])
            if not business:
                continue

            # Determine if income or expense
            is_income = invoice_dict['invoice_id'].startswith('ERE')
            type_folder = 'Einnahmen' if is_income else 'Ausgaben'

            # Extract year from date
            try:
                date_obj = datetime.strptime(invoice_dict['date'], '%Y-%m-%d')
                year = date_obj.year
            except:
                date_obj = datetime.now()
                year = date_obj.year

            # Create archive path
            archive_folder = BASE_DIR / 'Archive' / business['name'] / type_folder / str(year)
            archive_folder.mkdir(parents=True, exist_ok=True)

            # Generate filename with correct format: YYMMDD_InvoiceID_Category_Description_Amount.pdf
            date_str = date_obj.strftime('%y%m%d')
            category_safe = (invoice_dict.get('category', 'Unknown') or 'Unknown').replace('/', '-')
            description_safe = (invoice_dict.get('description', '')[:30]
                              .replace('/', '-')
                              .replace(' ', '_')
                              .strip('_'))
            amount_safe = f"{float(invoice_dict.get('amount', 0)):.2f}".replace('.', '_')

            pdf_filename = f"{date_str}_{invoice_dict['invoice_id']}_{category_safe}_{description_safe}_{amount_safe}.pdf"
            pdf_filename = pdf_filename.replace('__', '_')  # Clean double underscores
            pdf_path = archive_folder / pdf_filename

            # Generate placeholder PDF
            pdf_data = {
                'invoice_id': invoice_dict['invoice_id'],
                'date': invoice_dict['date'],
                'amount': invoice_dict['amount'],
                'category': invoice_dict['category'],
                'description': invoice_dict['description'],
                'business_name': business['name'],
                'is_recurring_generated': invoice_dict.get('is_recurring_generated', False)
            }

            pdf_generator.generate_placeholder_pdf(pdf_data, pdf_path)

            # Update database with RELATIVE path (relative to BASE_DIR)
            relative_path = f"Archive/{business['name']}/{type_folder}/{year}/{pdf_filename}"
            db.update_invoice(invoice_dict['id'], {
                'file_path': relative_path,
                'is_placeholder_pdf': True,
                'is_archived': True
            })

            generated.append(invoice_dict['id'])
            print(f"✅ Generated placeholder for {invoice_dict['invoice_id']} at {pdf_filename}")

        return generated

    except Exception as e:
        print(f"⚠️  Error generating placeholders: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == '__main__':
    # Generate recurring transactions on app start
    try:
        generated = db.generate_recurring_transactions()
        if generated:
            print(f"✅ Generated {len(generated)} recurring transactions")
    except Exception as e:
        print(f"⚠️  Error generating recurring transactions: {e}")

    # Generate missing placeholder PDFs
    try:
        placeholders = generate_missing_placeholders()
        if placeholders:
            print(f"✅ Generated {len(placeholders)} placeholder PDFs")
    except Exception as e:
        print(f"⚠️  Error generating placeholders: {e}")

    try:
        app.run(debug=True, port=5000, use_reloader=False)  # use_reloader=False to prevent double-start
    finally:
        auto_processor.stop()
