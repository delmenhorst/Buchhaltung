#!/usr/bin/env python3
"""
Reset Test Database - Entwicklungs-Tool

Dieses Script resettet die Datenbank und erstellt Testdaten:
- Löscht die bestehende Datenbank
- Erstellt zwei Test-Businesses
- Erstellt wiederkehrende Buchungen
- Optional: Lädt Test-Invoices aus test_invoices/ Ordner

Verwendung:
    python reset_test_db.py                  # Nur DB reset
    python reset_test_db.py --load-invoices  # DB reset + Test-Invoices laden
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime, timedelta

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent / 'app'))

from database import Database
from folder_manager import FolderManager

BASE_DIR = Path(__file__).parent
APP_DIR = BASE_DIR / 'app'
DB_PATH = APP_DIR / 'invoices.db'

def reset_database():
    """Delete and recreate database"""
    print("🗑️  Deleting old database...")
    if DB_PATH.exists():
        DB_PATH.unlink()
    
    print("🔨 Creating new database...")
    db = Database(DB_PATH)
    db.init_db()
    
    return db

def create_test_businesses(db, folder_manager):
    """Create two test businesses"""
    print("🏢 Creating test businesses...")
    
    # Business 1: Medienkunst (MK)
    mk_id = db.create_business(
        name='Medienkunst',
        prefix='MK',
        color='#FF6B6B'
    )
    mk_paths = folder_manager.create_business_folders('Medienkunst')
    db.update_business(mk_id, {
        'name': 'Medienkunst',
        'prefix': 'MK',
        'color': '#FF6B6B',
        'inbox_path': mk_paths['inbox'],
        'archive_path': mk_paths['archive_base']
    })
    print(f"  ✓ Created Medienkunst (ID: {mk_id}, Prefix: MK)")
    
    # Business 2: Fotografie (FT)
    ft_id = db.create_business(
        name='Fotografie',
        prefix='FT',
        color='#4ECDC4'
    )
    ft_paths = folder_manager.create_business_folders('Fotografie')
    db.update_business(ft_id, {
        'name': 'Fotografie',
        'prefix': 'FT',
        'color': '#4ECDC4',
        'inbox_path': ft_paths['inbox'],
        'archive_path': ft_paths['archive_base']
    })
    print(f"  ✓ Created Fotografie (ID: {ft_id}, Prefix: FT)")
    
    return mk_id, ft_id

def create_recurring_transactions(db, mk_id, ft_id):
    """Create sample recurring transactions"""
    print("🔄 Creating recurring transactions...")
    
    today = datetime.now()
    start_of_year = today.replace(month=1, day=1)
    
    # Medienkunst - Monthly rent
    db.create_recurring_transaction({
        'business_id': mk_id,
        'type': 'expense',
        'description': 'Ateliermiete',
        'amount': 450.00,
        'category': 'Raum',
        'frequency': 'monthly',
        'day_of_month': 1,
        'start_date': start_of_year.strftime('%Y-%m-%d'),
        'end_date': None
    })
    print("  ✓ Medienkunst: Monatliche Ateliermiete (450€)")
    
    # Medienkunst - Monthly internet
    db.create_recurring_transaction({
        'business_id': mk_id,
        'type': 'expense',
        'description': 'Internet & Telefon',
        'amount': 39.99,
        'category': 'Telefon',
        'frequency': 'monthly',
        'day_of_month': 15,
        'start_date': start_of_year.strftime('%Y-%m-%d'),
        'end_date': None
    })
    print("  ✓ Medienkunst: Monatlich Internet (39,99€)")
    
    # Fotografie - Quarterly insurance
    db.create_recurring_transaction({
        'business_id': ft_id,
        'type': 'expense',
        'description': 'Berufshaftpflichtversicherung',
        'amount': 120.00,
        'category': 'Versicherung',
        'frequency': 'quarterly',
        'day_of_month': 1,
        'start_date': start_of_year.strftime('%Y-%m-%d'),
        'end_date': None
    })
    print("  ✓ Fotografie: Quartalsweise Versicherung (120€)")
    
    # Generate all recurring entries up to today
    print("  ⏳ Generating recurring entries...")
    generated_ids = db.generate_recurring_transactions()
    print(f"  ✓ Generated {len(generated_ids)} recurring transaction entries")
    
    return generated_ids

def load_test_invoices(db):
    """Load test invoices from test_invoices/ folder if it exists"""
    test_invoices_dir = BASE_DIR / 'test_invoices'
    
    if not test_invoices_dir.exists():
        print("📂 Creating test_invoices/ folder structure...")
        (test_invoices_dir / 'Medienkunst' / 'Ausgaben').mkdir(parents=True, exist_ok=True)
        (test_invoices_dir / 'Medienkunst' / 'Einnahmen').mkdir(parents=True, exist_ok=True)
        (test_invoices_dir / 'Fotografie' / 'Ausgaben').mkdir(parents=True, exist_ok=True)
        (test_invoices_dir / 'Fotografie' / 'Einnahmen').mkdir(parents=True, exist_ok=True)
        print(f"  ✓ Created folder structure in {test_invoices_dir}")
        print(f"\n  💡 Tipp: Legen Sie Test-PDFs in diese Ordner:")
        print(f"     - {test_invoices_dir}/Medienkunst/Ausgaben/")
        print(f"     - {test_invoices_dir}/Medienkunst/Einnahmen/")
        print(f"     - {test_invoices_dir}/Fotografie/Ausgaben/")
        print(f"     - {test_invoices_dir}/Fotografie/Einnahmen/")
        return 0
    
    print("📄 Loading test invoices from test_invoices/...")
    
    # Copy files to Inbox
    copied_count = 0
    for business_folder in test_invoices_dir.iterdir():
        if not business_folder.is_dir():
            continue
        
        business_name = business_folder.name
        
        for type_folder in ['Ausgaben', 'Einnahmen']:
            source_folder = business_folder / type_folder
            if not source_folder.exists():
                continue
            
            dest_folder = BASE_DIR / 'Inbox' / business_name / type_folder
            dest_folder.mkdir(parents=True, exist_ok=True)
            
            for file_path in source_folder.glob('*.[pP][dD][fF]'):
                dest_path = dest_folder / file_path.name
                shutil.copy2(file_path, dest_path)
                
                # Add to database
                business = db.get_business_by_name(business_name)
                if business:
                    db.add_file(str(dest_path), business['id'])
                    copied_count += 1
                    print(f"  ✓ Copied {file_path.name} to {type_folder}")
    
    print(f"  ✓ Loaded {copied_count} test invoices")
    return copied_count

def main():
    """Main reset function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Reset test database')
    parser.add_argument('--load-invoices', action='store_true',
                       help='Load test invoices from test_invoices/ folder')
    args = parser.parse_args()
    
    print("=" * 60)
    print("🧪 RESET TEST DATABASE")
    print("=" * 60)
    print()
    
    # Initialize
    db = reset_database()
    folder_manager = FolderManager(BASE_DIR)
    
    # Create test businesses
    mk_id, ft_id = create_test_businesses(db, folder_manager)
    
    # Create recurring transactions
    generated_ids = create_recurring_transactions(db, mk_id, ft_id)
    
    # Load test invoices if requested
    if args.load_invoices:
        load_test_invoices(db)
    
    print()
    print("=" * 60)
    print("✅ DATABASE RESET COMPLETE!")
    print("=" * 60)
    print()
    print("📊 Summary:")
    print(f"  - 2 Businesses created (Medienkunst, Fotografie)")
    print(f"  - 3 Recurring transactions created")
    print(f"  - {len(generated_ids)} Recurring entries generated")
    print()
    print("🚀 Starten Sie die App mit: python app/app.py")
    print()
    
    if not args.load_invoices:
        print("💡 Tipp: Verwenden Sie --load-invoices um Test-PDFs zu laden:")
        print("   python reset_test_db.py --load-invoices")
        print()

if __name__ == '__main__':
    main()
