"""
Filename Generator - Creates tax-friendly, structured filenames

Format: YYYY-MM-DD_InvoiceID_Type_Supplier_Description_Category_Amount.pdf
Example: 2025-11-02_ARE-MK-001_Ausgabe_Apple_MacBook-Pro-14_Büro_1299-99.pdf
"""

from datetime import datetime
from pathlib import Path


def generate_invoice_filename(data, invoice_id, file_extension='.pdf'):
    """
    Generate structured, tax-friendly filename

    Args:
        data: dict with keys: date, supplier, description, category, amount
        invoice_id: str like "ARE-MK-2025001"
        file_extension: str like ".pdf"

    Returns:
        str: formatted filename

    NOTE: Using MINIMAL format (YYYY-MM-DD_InvoiceID.pdf) as recommended in PDF_NAMING_RECOMMENDATION.md
    All metadata is stored in the database and easily searchable.
    """
    # Parse date
    if isinstance(data.get('date'), str):
        date_obj = datetime.strptime(data['date'], '%Y-%m-%d')
    else:
        date_obj = data.get('date', datetime.now())

    date_str = date_obj.strftime('%Y-%m-%d')  # ISO format: 2025-11-02

    # MINIMAL FORMAT: YYYY-MM-DD_InvoiceID.pdf
    # Keeps filenames short and manageable
    # All details (supplier, category, amount) are in the database
    filename = f"{date_str}_{invoice_id}{file_extension}"

    return filename


def sanitize_filename_part(text):
    """
    Sanitize text for use in filename

    - Replace spaces with hyphens
    - Remove special characters
    - Keep umlauts (ä, ö, ü) and common punctuation
    """
    if not text:
        return ''

    # Replace problematic characters
    replacements = {
        ' ': '-',
        '/': '-',
        '\\': '-',
        ':': '-',
        '*': '',
        '?': '',
        '"': '',
        '<': '',
        '>': '',
        '|': '',
        '\n': '-',
        '\r': '',
        '\t': '-',
        '  ': '-',  # Double spaces
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Remove leading/trailing hyphens
    text = text.strip('-')

    # Collapse multiple hyphens
    while '--' in text:
        text = text.replace('--', '-')

    return text


def format_amount(amount):
    """
    Format amount for filename: 1299.99 → 1299-99

    Uses hyphen instead of dot for better compatibility
    """
    if amount is None or amount == 0:
        return '0-00'

    # Format to 2 decimal places
    amount_str = f"{float(amount):.2f}"

    # Replace dot with hyphen
    amount_str = amount_str.replace('.', '-')

    return amount_str


def parse_filename_to_data(filename):
    """
    Parse filename back to data dict (for reverse lookup)

    Example:
        2025-11-02_ARE-MK-001_Ausgabe_Apple_MacBook-Pro_Büro_1299-99.pdf
        →
        {
            'date': '2025-11-02',
            'invoice_id': 'ARE-MK-001',
            'type': 'Ausgabe',
            'supplier': 'Apple',
            'description': 'MacBook-Pro',
            'category': 'Büro',
            'amount': 1299.99
        }
    """
    # Remove extension
    name = Path(filename).stem

    # Split by underscore
    parts = name.split('_')

    if len(parts) < 7:
        return None  # Invalid format

    data = {
        'date': parts[0],
        'invoice_id': parts[1],
        'type': parts[2],
        'supplier': parts[3],
        'description': parts[4],
        'category': parts[5],
        'amount': float(parts[6].replace('-', '.'))
    }

    return data
