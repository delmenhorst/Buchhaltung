"""
pytest configuration and fixtures for Buchhaltungs-App tests

This file provides shared fixtures for all test files.
"""

import pytest
import shutil
from pathlib import Path
from app.database import Database
from app.folder_manager import FolderManager


@pytest.fixture
def test_data_dir(tmp_path):
    """Temporary test data directory"""
    test_dir = tmp_path / 'test_data'
    test_dir.mkdir(exist_ok=True)
    yield test_dir

    # Cleanup after test
    if test_dir.exists():
        shutil.rmtree(test_dir)


@pytest.fixture
def test_db(test_data_dir):
    """Test database fixture"""
    test_db_path = test_data_dir / 'test_pytest.db'

    db = Database(str(test_db_path))
    yield db

    # Cleanup
    if test_db_path.exists():
        test_db_path.unlink()


@pytest.fixture
def folder_manager(test_data_dir):
    """FolderManager fixture with test directories"""
    # FolderManager takes only base_dir parameter
    fm = FolderManager(str(test_data_dir))

    yield fm


@pytest.fixture
def test_business(test_db, test_data_dir):
    """Create a test business with folder structure"""
    business_name = 'TestBusiness'
    prefix = 'TB'

    business_id = test_db.create_business(
        name=business_name,
        prefix=prefix,
        color='#3B82F6'
    )

    # Create folder structure
    for folder_type in ['Einnahmen', 'Ausgaben']:
        inbox_path = test_data_dir / 'Inbox' / business_name / folder_type
        inbox_path.mkdir(parents=True, exist_ok=True)

        for year in [2024, 2025]:
            archive_path = test_data_dir / 'Archive' / business_name / folder_type / str(year)
            archive_path.mkdir(parents=True, exist_ok=True)

    yield business_id, business_name, prefix, test_db, test_data_dir


@pytest.fixture
def create_test_invoice(test_db):
    """Factory fixture for creating test invoices"""
    def _create_invoice(business_id, invoice_type='Ausgabe', amount=1299.50,
                       category='Büro', description='Test Invoice'):
        from datetime import datetime

        date_str = datetime.now().strftime('%Y-%m-%d')
        year = datetime.now().year

        # Get next invoice ID
        next_id = test_db.get_next_invoice_id(year=year, business_id=business_id)

        # Get business details
        conn = test_db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name, prefix FROM businesses WHERE id = ?', (business_id,))
        business = cursor.fetchone()

        if not business:
            raise ValueError(f"Business {business_id} not found")

        business_name = business['name']
        prefix = business['prefix']

        # Generate invoice ID
        type_prefix = 'ARE' if invoice_type == 'Ausgabe' else 'ERE'
        invoice_id = f"{type_prefix}-{prefix}-{year}{next_id:03d}"

        # Generate filename
        date_obj = datetime.now()
        date_str_short = date_obj.strftime('%y%m%d')
        category_safe = category.replace('/', '-')
        description_safe = description[:30].replace('/', '-').replace(' ', '_').strip('_')
        amount_safe = f"{float(amount):.2f}".replace('.', '_')

        filename = f"{date_str_short}_{invoice_id}_{category_safe}_{description_safe}_{amount_safe}.pdf"
        filename = filename.replace('__', '_')

        folder_type = 'Ausgaben' if invoice_type == 'Ausgabe' else 'Einnahmen'
        file_path = f"Archive/{business_name}/{folder_type}/{year}/{filename}"

        # Insert invoice
        cursor.execute('''
            INSERT INTO invoices (
                business_id, file_path, original_filename, invoice_id,
                date, amount, category, description, type,
                processed, is_archived, reviewed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            business_id, file_path, filename, invoice_id,
            date_str, amount, category, description, invoice_type,
            1, 1, 1
        ))

        invoice_pk_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return invoice_pk_id, invoice_id, filename

    return _create_invoice
