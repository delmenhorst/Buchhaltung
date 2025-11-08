#!/usr/bin/env python3
"""
Reset Test Database - Helper Script

Löscht die Test-Datenbank und erstellt eine frische mit Sample-Daten.
Nützlich zum Zurücksetzen der Testumgebung.

Usage:
    python reset_test_db.py
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import Database
from app.folder_manager import FolderManager

def reset_test_database():
    """Löscht und erstellt Test-Datenbank neu"""
    print("🔄 Resetting Test Database...")
    print("="*60)

    # Paths
    test_dir = Path(__file__).parent / 'test' / 'test_data'
    test_db_path = test_dir / 'test_invoices.db'

    # Create test_data directory if it doesn't exist
    test_dir.mkdir(exist_ok=True, parents=True)

    # Delete old database
    if test_db_path.exists():
        test_db_path.unlink()
        print("✅ Old database deleted")

    # Create new database
    db = Database(str(test_db_path))
    print("✅ New database created")

    # Create test businesses
    print("\n📊 Creating test businesses...")

    business1_id = db.add_business(
        name='TestBusiness1',
        inbox_path=str(test_dir / 'Inbox' / 'TestBusiness1'),
        archive_path=str(test_dir / 'Archive' / 'TestBusiness1'),
        prefix='TB',
        color='#3B82F6'
    )
    print(f"  ✅ TestBusiness1 (ID: {business1_id}, Prefix: TB)")

    business2_id = db.add_business(
        name='TestBusiness2',
        inbox_path=str(test_dir / 'Inbox' / 'TestBusiness2'),
        archive_path=str(test_dir / 'Archive' / 'TestBusiness2'),
        prefix='T2',
        color='#10B981'
    )
    print(f"  ✅ TestBusiness2 (ID: {business2_id}, Prefix: T2)")

    # Create folder structure
    print("\n📁 Creating test folder structure...")

    base_dir = test_dir
    for business_name in ['TestBusiness1', 'TestBusiness2']:
        # Inbox folders
        inbox_ausgaben = base_dir / 'Inbox' / business_name / 'Ausgaben'
        inbox_einnahmen = base_dir / 'Inbox' / business_name / 'Einnahmen'
        inbox_ausgaben.mkdir(parents=True, exist_ok=True)
        inbox_einnahmen.mkdir(parents=True, exist_ok=True)

        # Archive folders with years
        for year in [2024, 2025]:
            archive_ausgaben = base_dir / 'Archive' / business_name / 'Ausgaben' / str(year)
            archive_einnahmen = base_dir / 'Archive' / business_name / 'Einnahmen' / str(year)
            archive_ausgaben.mkdir(parents=True, exist_ok=True)
            archive_einnahmen.mkdir(parents=True, exist_ok=True)

        print(f"  ✅ {business_name} folders created")

    print("\n🎉 Test database reset complete!")
    print("="*60)
    print(f"Database location: {test_db_path}")
    print(f"Test data directory: {test_dir}")
    print("\nYou can now run tests:")
    print("  python test/test_basic_functionality.py")
    print("  python test/test_business_management.py")
    print("  python test/test_manual_invoices.py")
    print("  python test/test_recurring_invoices.py")
    print("  python test/test_filename_format.py")

    return db, business1_id, business2_id


def reset_with_sample_data():
    """Erstellt Test-DB mit Sample-Daten"""
    db, business1_id, business2_id = reset_test_database()

    print("\n📝 Adding sample data...")

    # Add sample expense
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO invoices (
            business_id, file_path, original_filename, invoice_id,
            date, amount, category, description, type,
            processed, is_archived, reviewed
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        business1_id,
        'Archive/TestBusiness1/Ausgaben/2025/251108_ARE-TB-2025001_Büro_Test_1299_50.pdf',
        'test_invoice.pdf',
        'ARE-TB-2025001',
        '2025-11-08',
        1299.50,
        'Büro',
        'Test Laptop',
        'Ausgabe',
        1,
        1,
        1
    ))

    # Add sample income
    cursor.execute('''
        INSERT INTO invoices (
            business_id, file_path, original_filename, invoice_id,
            date, amount, category, description, type,
            processed, is_archived, reviewed
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        business1_id,
        'Archive/TestBusiness1/Einnahmen/2025/251108_ERE-TB-2025001_Honorar_Test_2500_00.pdf',
        'test_income.pdf',
        'ERE-TB-2025001',
        '2025-11-08',
        2500.00,
        'Honorar',
        'Test Projekt',
        'Einnahme',
        1,
        1,
        1
    ))

    conn.commit()
    conn.close()

    print("  ✅ Sample expense: ARE-TB-2025001 (1299.50 €)")
    print("  ✅ Sample income: ERE-TB-2025001 (2500.00 €)")
    print("\n✨ Sample data added!")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Reset test database')
    parser.add_argument('--with-data', action='store_true',
                        help='Add sample data to the database')

    args = parser.parse_args()

    if args.with_data:
        reset_with_sample_data()
    else:
        reset_test_database()
