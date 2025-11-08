# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Flask-based accounting application (Buchhaltungs-App) designed for freelancers, artists, and self-employed individuals in Germany. The app automates document processing through OCR and local LLM extraction, organizing financial documents in a tax-compliant manner.

**Key Features:**
- Multi-business support with separate invoice ID sequences
- Automatic OCR processing via Tesseract
- AI-enhanced data extraction via Ollama (local LLM)
- Background auto-processing of incoming documents
- Tax-friendly filename generation and folder structure
- Excel export for accounting (EAR system)
- Fully local/offline operation (privacy-first)

## Tech Stack

- **Backend**: Python 3.14+, Flask 3.0+
- **Database**: SQLite3 (invoices.db)
- **OCR**: Pytesseract (requires Tesseract binary with German language support)
- **LLM**: Ollama (local, recommended: gemma3:4b)
- **Frontend**: Jinja2 templates, Alpine.js, Tailwind CSS (CDN)
- **Image Processing**: Pillow, pdf2image (HEIC → PDF conversion)
- **Export**: openpyxl (Excel generation)

## Development Commands

### Initial Setup
```bash
cd /Users/denis/Developer/Buchhaltung/app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install system dependencies (macOS)
brew install tesseract tesseract-lang

# Optional: Install Ollama for AI features
brew install ollama
ollama serve &
ollama pull gemma3:4b
```

### Daily Development
```bash
# Activate environment
cd /Users/denis/Developer/Buchhaltung/app
source venv/bin/activate

# Run development server (http://localhost:5000)
python app.py

# Run tests
python test/test_basic_functionality.py        # Basic DB tests (no OCR)
python test/test_document_processing.py        # Integration tests
python test/test_ocr_extraction.py             # OCR extraction tests (29 tests)

# Run all tests
python -m pytest test/

# Database access
sqlite3 app/invoices.db
```

### Common Database Queries
```sql
SELECT * FROM businesses;
SELECT * FROM invoices WHERE business_id = 1 ORDER BY date DESC LIMIT 10;
SELECT COUNT(*) FROM invoices WHERE processed = 1 AND is_archived = 1;
```

## Architecture Overview

### Core Modules

**app.py** (Flask Routes)
- Main web server and route definitions
- Key routes: `/` (dashboard), `/expenses`, `/income`, `/inbox`, `/documents`, `/settings`
- API endpoints: `/api/invoice/<id>`, `/api/auto-processor/toggle`, `/export/excel`

**database.py** (Data Layer)
- SQLite interface with two main tables: `businesses` and `invoices`
- `init_db()` handles schema migrations automatically
- `update_invoice(file_id, data)` uses whitelisted fields to prevent SQL injection
- `get_next_invoice_id(business_id, is_income)` generates unique IDs per business

**auto_processor.py** (Background Worker)
- Daemon thread running in background
- Checks Inbox folders every 10 seconds
- Converts images to PDF if needed (HEIC → PDF)
- Runs OCR + LLM extraction pipeline
- Auto-archives documents if all required fields present
- Marks incomplete documents for manual review

**ocr_processor.py / income_processor.py** (OCR Pipeline)
- Extracts text via Tesseract (German + English)
- Attempts LLM extraction via Ollama (gemma3:4b)
- Falls back to regex patterns if LLM unavailable
- Expense categories: Büro, Raum, Telefon, Fahrtkosten, Fortbildung, Versicherung, Porto, Werbung, Sonstiges
- Income categories: Honorar, Lizenzgebühren, Workshops, Stipendien, Verkäufe, Sonstiges

**llm_extractor.py** (AI Enhancement)
- Uses local Ollama API for intelligent extraction
- Better at understanding context (Netto vs Brutto amounts)
- Handles complex document layouts
- Fully offline, no external API calls

**folder_manager.py** (File Organization)
- Manages Inbox/Archive folder structure
- Creates business-specific directories
- Moves processed files to year-based archives
- Generates tax-friendly filenames

### Data Flow: Document Processing

```
1. User drops file → Inbox/BusinessName/Ausgaben/
                ↓
2. Auto Processor detects (10s interval)
                ↓
3. Convert to PDF if needed (HEIC/JPG → PDF)
                ↓
4. OCR text extraction (Tesseract: deu+eng)
                ↓
5. LLM extraction (Ollama) OR Regex fallback
                ↓
6. Database update with extracted data
                ↓
7. Check completeness (date + amount + category)
                ↓
   Complete?          Incomplete?
      ↓                    ↓
8. Generate ID      Mark for review
   (ARE-MK-2025001)  (stays in Inbox)
      ↓
9. Generate filename
   (YYYY-MM-DD_InvoiceID_Type_Supplier_Description_Category_Amount.pdf)
      ↓
10. Move to Archive/BusinessName/Ausgaben/2025/
      ↓
11. Mark as archived ✓
```

## Key Patterns and Conventions

### Invoice ID Format
- **Expenses**: `ARE-{PREFIX}-{YEAR}{NUMBER}` (e.g., ARE-MK-2025001)
  - ARE = Ausgaben-Rechnung-Eingang (Expense Receipt Incoming)
- **Income**: `ERE-{PREFIX}-{YEAR}{NUMBER}` (e.g., ERE-MK-2025001)
  - ERE = Einnahmen-Rechnung-Eingang (Income Receipt Incoming)
- Each business has its own prefix (2 chars) and independent number sequence
- Numbers reset annually (001 starts each year)

### Tax-Friendly Filename Structure
Format: `YYYY-MM-DD_InvoiceID_Type_Supplier_Description_Category_Amount.pdf`

Example: `2025-11-02_ARE-MK-001_Ausgabe_Apple_MacBook-Pro_Büro_1299-99.pdf`

Benefits:
- Chronological sorting by date prefix
- All metadata embedded in filename
- Searchable without opening files
- Tax audit compliant

### Database Update Pattern
The `update_invoice()` function uses a whitelist approach for security:

```python
allowed_fields = {
    'date', 'amount', 'category', 'description', 'invoice_id',
    'reviewed', 'processed', 'flagged', 'unread', 'ocr_text',
    # ... plus all expense/income specific fields
}

# Only update whitelisted fields
fields_to_update = {k: v for k, v in data.items() if k in allowed_fields}
```

This prevents SQL injection and ensures only valid fields can be modified.

### Business Filter Pattern
All list queries support optional business filtering:

```python
business_id = request.args.get('business_id', type=int)

if business_id:
    cursor.execute('SELECT * FROM invoices WHERE business_id = ?', (business_id,))
else:
    cursor.execute('SELECT * FROM invoices')
```

### Background Processing Pattern
The auto-processor runs independently of web requests:

```python
# Daemon thread - won't block app shutdown
self.thread = threading.Thread(target=self._worker_loop, daemon=True)

# Non-blocking check every 10 seconds
def _worker_loop(self):
    while self.running:
        self._process_inbox_files()
        time.sleep(10)  # CHECK_INTERVAL
```

### Graceful Degradation Strategy
The app has multiple fallback layers:

1. **LLM Extraction** → Regex Fallback → Manual Review
2. **Auto-Archive** (complete data) → Manual Review (incomplete data)
3. **Automatic Processing** → Manual Processing API endpoint
4. **Ollama Available** → Works Without (regex only)

### Error Handling Convention
```python
try:
    # Attempt operation
    result = process_document(file_path)
except Exception as e:
    logger.error(f"Processing failed for {file_path}: {e}", exc_info=True)
    # Mark for manual review instead of failing
    mark_for_review(file_id)
```

## File Organization

### Directory Structure
```
Inbox/
  ├── BusinessName/
  │   ├── Einnahmen/       # Income documents (unprocessed)
  │   └── Ausgaben/        # Expense documents (unprocessed)
Archive/
  ├── BusinessName/
  │   ├── Einnahmen/
  │   │   ├── 2024/
  │   │   └── 2025/
  │   └── Ausgaben/
  │       ├── 2024/
  │       └── 2025/
```

- **Inbox**: Monitored by auto-processor, files removed after processing
- **Archive**: Organized by year, files renamed with semantic structure
- **Year-based**: Simplifies tax filing (one folder per tax year)

## Database Schema

### businesses table
- `id`, `name`, `prefix` (2-char unique), `color` (UI), `inbox_path`, `archive_path`, `created_at`

### invoices table (unified for income + expenses)
Core fields: `id`, `business_id`, `file_path`, `original_filename`, `invoice_id`, `date`, `amount`, `category`, `description`, `ocr_text`

Status flags: `reviewed`, `processed`, `is_archived`, `flagged`, `unread`

Income-specific: `invoice_number`, `customer_name`, `customer_address`, `payment_due_date`, `payment_terms`, `tax_rate`, `tax_amount`, `net_amount`

Expense-specific: Standard accounting categories (14 fields like `büro`, `raum`, `telefon`, etc.)

## Important Notes

### German Language Context
- Documentation is primarily in German
- OCR configured for German text (Tesseract: deu+eng)
- Categories and field names use German terminology
- Tax compliance follows German EAR (Einnahmen-Ausgaben-Rechnung) system

### Privacy and Security
- All processing local (no external APIs for OCR or LLM)
- SQLite database with parameterized queries
- File paths validated to prevent directory traversal
- Whitelisted field updates to prevent SQL injection
- No API keys or external services required

### Multi-Business Design
- Single application instance serves multiple businesses
- Separate invoice ID sequences per business (independent counters)
- Business-scoped queries throughout the application
- Color-coded UI elements for visual distinction
- Cascade/reassign options for business deletion

### Testing Philosophy
- Basic tests run without OCR dependencies (test_basic_functionality.py)
- Integration tests cover full workflow (test_document_processing.py)
- OCR tests validate extraction accuracy (test_ocr_extraction.py: 29/29 passing)
- Can run individual test files or full suite with pytest

### Auto-Processor Behavior
- Starts automatically when Flask app starts
- Can be toggled on/off via `/api/auto-processor/toggle`
- Status check via `/api/auto-processor/status`
- Daemon thread (non-blocking, won't prevent shutdown)
- Logs all processing activity to console

## Relevant Documentation

- **PROJEKT_DOKUMENTATION.md**: Complete project documentation (German)
- **CHANGELOG.md**: Detailed changelog with technical details (German)
- **IMPROVEMENTS_TODO.md**: Feature tracking and status (German)
- **API_DELETE_BUSINESS.md**: Business deletion API documentation (German)
- **app/OLLAMA_SETUP.md**: Ollama installation and configuration (German)
