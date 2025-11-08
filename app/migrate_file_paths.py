#!/usr/bin/env python3
"""
Migration script to fix file paths in database

Problem: Old database entries have absolute paths or paths starting with 'app/'
Solution: Convert all paths to relative paths (relative to FINANZEN folder)

Usage: python migrate_file_paths.py
"""

import sqlite3
from pathlib import Path
import re

# Database path
DB_PATH = Path(__file__).parent / 'invoices.db'

def migrate_file_paths():
    """Migrate all file paths in database to relative paths"""

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all invoices with file paths
    cursor.execute('SELECT id, file_path FROM invoices WHERE file_path IS NOT NULL AND file_path != ""')
    invoices = cursor.fetchall()

    print(f"📊 Found {len(invoices)} invoices with file paths")

    updated_count = 0

    for invoice in invoices:
        invoice_id = invoice['id']
        old_path = invoice['file_path']

        # Skip if already a relative path in correct format
        if old_path.startswith('Archive/') or old_path.startswith('Inbox/'):
            continue

        # Convert path to string for manipulation
        path_str = str(old_path)
        new_path = path_str

        # Remove 'app/' prefix if exists
        if path_str.startswith('app/'):
            new_path = path_str[4:]  # Remove 'app/'
            print(f"  ✏️  ID {invoice_id}: {old_path} → {new_path}")

        # Convert absolute paths to relative
        # Match patterns like /Users/denis/Developer/Buchhaltung/Archive/...
        absolute_pattern = r'^/(?:Users|home)/[^/]+/[^/]+/[^/]+/((?:Archive|Inbox)/.+)$'
        match = re.match(absolute_pattern, path_str)
        if match:
            new_path = match.group(1)
            print(f"  ✏️  ID {invoice_id}: {old_path} → {new_path}")

        # Update database if path changed
        if new_path != old_path:
            cursor.execute('UPDATE invoices SET file_path = ? WHERE id = ?', (new_path, invoice_id))
            updated_count += 1

    # Commit changes
    conn.commit()
    conn.close()

    print(f"\n✅ Migration complete! Updated {updated_count} file paths")

    if updated_count == 0:
        print("   No paths needed updating - all paths are already in correct format")

if __name__ == '__main__':
    migrate_file_paths()
