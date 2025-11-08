import sqlite3
from pathlib import Path
from datetime import datetime

class Database:
    def __init__(self, db_path):
        self.db_path = db_path

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initialize database schema"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Businesses table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS businesses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                prefix TEXT NOT NULL UNIQUE,
                color TEXT DEFAULT '#007AFF',
                inbox_path TEXT,
                archive_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Check if business_id column exists in invoices table
        cursor.execute("PRAGMA table_info(invoices)")
        columns = [column[1] for column in cursor.fetchall()]

        needs_migration = 'business_id' not in columns

        if needs_migration:
            # Create new invoices table with business_id and all fields
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS invoices_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_id INTEGER,
                    file_path TEXT UNIQUE,
                    original_filename TEXT,
                    invoice_id TEXT,
                    date TEXT,
                    amount REAL,
                    category TEXT,
                    description TEXT,
                    ocr_text TEXT,
                    reviewed BOOLEAN DEFAULT 0,
                    processed BOOLEAN DEFAULT 0,
                    is_archived BOOLEAN DEFAULT 0,
                    flagged BOOLEAN DEFAULT 0,
                    supplier TEXT,
                    unread BOOLEAN DEFAULT 1,
                    recurring_transaction_id INTEGER,
                    is_recurring_generated BOOLEAN DEFAULT 0,
                    is_placeholder_pdf BOOLEAN DEFAULT 0,
                    -- Income-specific fields
                    invoice_number TEXT,
                    customer_name TEXT,
                    customer_address TEXT,
                    payment_due_date TEXT,
                    payment_terms TEXT,
                    tax_rate REAL,
                    tax_amount REAL,
                    net_amount REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (business_id) REFERENCES businesses(id)
                )
            ''')

            # Copy data from old table if it exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='invoices'")
            if cursor.fetchone():
                cursor.execute('''
                    INSERT INTO invoices_new
                    (id, file_path, original_filename, invoice_id, date, amount, category,
                     description, ocr_text, reviewed, processed, created_at, updated_at)
                    SELECT id, file_path, original_filename, invoice_id, date, amount, category,
                           description, ocr_text, reviewed, processed, created_at, updated_at
                    FROM invoices
                ''')
                cursor.execute('DROP TABLE invoices')

            cursor.execute('ALTER TABLE invoices_new RENAME TO invoices')
        else:
            # Table already has business_id - check if income fields exist
            if 'invoice_number' not in columns:
                # Add income-specific columns
                cursor.execute('ALTER TABLE invoices ADD COLUMN invoice_number TEXT')
                cursor.execute('ALTER TABLE invoices ADD COLUMN customer_name TEXT')
                cursor.execute('ALTER TABLE invoices ADD COLUMN customer_address TEXT')
                cursor.execute('ALTER TABLE invoices ADD COLUMN payment_due_date TEXT')
                cursor.execute('ALTER TABLE invoices ADD COLUMN payment_terms TEXT')
                cursor.execute('ALTER TABLE invoices ADD COLUMN tax_rate REAL')
                cursor.execute('ALTER TABLE invoices ADD COLUMN tax_amount REAL')
                cursor.execute('ALTER TABLE invoices ADD COLUMN net_amount REAL')

            # Add missing columns for archiving and flagging
            if 'is_archived' not in columns:
                cursor.execute('ALTER TABLE invoices ADD COLUMN is_archived BOOLEAN DEFAULT 0')
            if 'flagged' not in columns:
                cursor.execute('ALTER TABLE invoices ADD COLUMN flagged BOOLEAN DEFAULT 0')

            # Add supplier/company field for better filename
            if 'supplier' not in columns:
                cursor.execute('ALTER TABLE invoices ADD COLUMN supplier TEXT')

            # Add unread status (like email)
            if 'unread' not in columns:
                cursor.execute('ALTER TABLE invoices ADD COLUMN unread BOOLEAN DEFAULT 1')

            # Add recurring transaction reference
            if 'recurring_transaction_id' not in columns:
                cursor.execute('ALTER TABLE invoices ADD COLUMN recurring_transaction_id INTEGER')
            if 'is_recurring_generated' not in columns:
                cursor.execute('ALTER TABLE invoices ADD COLUMN is_recurring_generated BOOLEAN DEFAULT 0')

            # Add placeholder PDF flag
            if 'is_placeholder_pdf' not in columns:
                cursor.execute('ALTER TABLE invoices ADD COLUMN is_placeholder_pdf BOOLEAN DEFAULT 0')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoice_counter (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_id INTEGER DEFAULT 0,
                prefix TEXT DEFAULT 'ARE'
            )
        ''')

        # Initialize counter if not exists
        cursor.execute('INSERT OR IGNORE INTO invoice_counter (id, last_id) VALUES (1, 0)')

        # Recurring transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recurring_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER,
                type TEXT NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                frequency TEXT NOT NULL,
                day_of_month INTEGER,
                start_date TEXT NOT NULL,
                end_date TEXT,
                active BOOLEAN DEFAULT 1,
                last_generated_date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES businesses(id)
            )
        ''')

        conn.commit()
        conn.close()

    def add_file(self, file_path, business_id=None):
        """Add a new expense file to process"""
        conn = self.get_connection()
        cursor = conn.cursor()

        original_filename = Path(file_path).name

        try:
            cursor.execute(
                'INSERT INTO invoices (file_path, original_filename, business_id) VALUES (?, ?, ?)',
                (file_path, original_filename, business_id)
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None
        finally:
            conn.close()

    def add_income_file(self, file_path, business_id=None):
        """Add a new income file to process (same table, different logic)"""
        return self.add_file(file_path, business_id)

    def file_exists(self, file_path):
        """Check if file already exists in database"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id FROM invoices WHERE file_path = ?', (file_path,))
        result = cursor.fetchone()
        conn.close()

        return result is not None

    def get_file(self, file_id):
        """Get file by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM invoices WHERE id = ?', (file_id,))
        result = cursor.fetchone()
        conn.close()

        return dict(result) if result else None

    def get_file_by_path(self, file_path):
        """Get file by path"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM invoices WHERE file_path = ?', (file_path,))
        result = cursor.fetchone()
        conn.close()

        return dict(result) if result else None

    def get_unprocessed_invoices(self):
        """Get all unprocessed invoices"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM invoices
            WHERE processed = 0
            ORDER BY created_at ASC
        ''')
        results = cursor.fetchall()
        conn.close()

        return [dict(row) for row in results]

    def get_pending_review(self):
        """Get expense invoices pending review"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM invoices
            WHERE reviewed = 0 AND ocr_text IS NOT NULL
            AND file_path LIKE '%/Ausgaben/%'
            ORDER BY created_at ASC
        ''')
        results = cursor.fetchall()
        conn.close()

        return [dict(row) for row in results]

    def get_pending_income_review(self):
        """Get income invoices pending review"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM invoices
            WHERE reviewed = 0 AND ocr_text IS NOT NULL
            AND file_path LIKE '%/Einnahmen/%'
            ORDER BY created_at ASC
        ''')
        results = cursor.fetchall()
        conn.close()

        return [dict(row) for row in results]

    def update_ocr_results(self, file_id, ocr_result):
        """Update file with OCR results"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE invoices
            SET ocr_text = ?,
                date = ?,
                amount = ?,
                category = ?,
                description = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            ocr_result.get('text'),
            ocr_result.get('date'),
            ocr_result.get('amount'),
            ocr_result.get('category'),
            ocr_result.get('description'),
            file_id
        ))

        conn.commit()
        conn.close()

    def update_invoice(self, file_id, data):
        """
        Update invoice with flexible fields

        Args:
            file_id: Invoice ID to update
            data: Dict with fields to update (only known fields are updated)
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # Define allowed fields (prevents SQL injection)
        allowed_fields = {
            'date', 'amount', 'category', 'description', 'reviewed', 'processed',
            'invoice_id', 'invoice_number', 'customer_name', 'customer_address',
            'payment_due_date', 'payment_terms', 'tax_rate', 'tax_amount',
            'net_amount', 'file_path', 'is_archived', 'flagged', 'ocr_text',
            'supplier', 'unread', 'is_placeholder_pdf'
        }

        # Build dynamic UPDATE query
        updates = []
        values = []

        for field, value in data.items():
            if field in allowed_fields:
                updates.append(f"{field} = ?")
                values.append(value)

        if not updates:
            conn.close()
            return  # Nothing to update

        # Always update timestamp
        updates.append("updated_at = CURRENT_TIMESTAMP")
        values.append(file_id)  # For WHERE clause

        query = f"UPDATE invoices SET {', '.join(updates)} WHERE id = ?"

        try:
            cursor.execute(query, values)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise Exception(f"Failed to update invoice {file_id}: {e}")
        finally:
            conn.close()

    def get_next_invoice_id(self, year=None, business_id=None):
        """
        Get next expense invoice ID with year-based numbering
        Format: ARE-{PREFIX}-{YEAR}{NUMBER} e.g. ARE-MK-2025001
        If no business_id, uses old format: ARE2025001
        """
        from datetime import datetime

        if year is None:
            year = datetime.now().year

        conn = self.get_connection()
        cursor = conn.cursor()

        # Get business prefix if business_id provided
        prefix = ""
        if business_id:
            cursor.execute('SELECT prefix FROM businesses WHERE id = ?', (business_id,))
            business = cursor.fetchone()
            if business:
                prefix = f"-{business['prefix']}-"

        # Get the highest number for this year and business
        search_pattern = f'ARE{prefix}{year}%'
        cursor.execute('''
            SELECT invoice_id FROM invoices
            WHERE invoice_id LIKE ?
            ORDER BY invoice_id DESC
            LIMIT 1
        ''', (search_pattern,))

        result = cursor.fetchone()

        if result:
            # Extract number from ARE-MK-2025001 -> 001
            last_number = int(result['invoice_id'][-3:])
            next_number = last_number + 1
        else:
            # First invoice of this year
            next_number = 1

        # Generate new ID and ensure uniqueness
        while True:
            new_id = f"ARE{prefix}{year}{next_number:03d}"

            # Double check: Make sure this ID doesn't exist in database
            cursor.execute('SELECT id FROM invoices WHERE invoice_id = ?', (new_id,))
            if not cursor.fetchone():
                break  # ID is unique, we can use it

            # ID exists, try next number
            next_number += 1

        conn.close()

        return new_id

    def get_next_income_id(self, year=None, business_id=None):
        """
        Get next income ID with year-based numbering
        Format: ERE-{PREFIX}-{YEAR}{NUMBER} e.g. ERE-MK-2025001
        ERE = Einnahmen-Rechnung-Eingang
        If no business_id, uses old format: ERE2025001
        """
        from datetime import datetime

        if year is None:
            year = datetime.now().year

        conn = self.get_connection()
        cursor = conn.cursor()

        # Get business prefix if business_id provided
        prefix = ""
        if business_id:
            cursor.execute('SELECT prefix FROM businesses WHERE id = ?', (business_id,))
            business = cursor.fetchone()
            if business:
                prefix = f"-{business['prefix']}-"

        # Get the highest number for this year and business
        search_pattern = f'ERE{prefix}{year}%'
        cursor.execute('''
            SELECT invoice_id FROM invoices
            WHERE invoice_id LIKE ?
            ORDER BY invoice_id DESC
            LIMIT 1
        ''', (search_pattern,))

        result = cursor.fetchone()

        if result:
            # Extract number from ERE-MK-2025001 -> 001
            last_number = int(result['invoice_id'][-3:])
            next_number = last_number + 1
        else:
            # First income of this year
            next_number = 1

        # Generate new ID and ensure uniqueness
        while True:
            new_id = f"ERE{prefix}{year}{next_number:03d}"

            # Double check: Make sure this ID doesn't exist in database
            cursor.execute('SELECT id FROM invoices WHERE invoice_id = ?', (new_id,))
            if not cursor.fetchone():
                break  # ID is unique, we can use it

            # ID exists, try next number
            next_number += 1

        conn.close()

        return new_id

    def update_file_path(self, file_id, new_path, invoice_id):
        """Update file path after renaming"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE invoices
            SET file_path = ?,
                invoice_id = ?,
                processed = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (new_path, invoice_id, file_id))

        conn.commit()
        conn.close()

    def get_all_processed(self, filters=None):
        """
        Get all processed invoices with optional filtering

        filters: dict with optional keys:
            - type: 'income' or 'expense'
            - category: category name
            - date_from: YYYY-MM-DD
            - date_to: YYYY-MM-DD
            - search: search term for description
            - business_id: business ID to filter by
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        query = '''
            SELECT * FROM invoices
            WHERE processed = 1
        '''
        params = []

        if filters:
            if filters.get('type') == 'income':
                query += " AND invoice_id LIKE 'ERE%'"
            elif filters.get('type') == 'expense':
                query += " AND invoice_id LIKE 'ARE%'"

            if filters.get('category'):
                query += " AND category = ?"
                params.append(filters['category'])

            if filters.get('date_from'):
                query += " AND date >= ?"
                params.append(filters['date_from'])

            if filters.get('date_to'):
                query += " AND date <= ?"
                params.append(filters['date_to'])

            if filters.get('year'):
                query += " AND strftime('%Y', date) = ?"
                params.append(str(filters['year']))

            if filters.get('search'):
                query += " AND (description LIKE ? OR invoice_id LIKE ?)"
                search_term = f"%{filters['search']}%"
                params.append(search_term)
                params.append(search_term)

            if filters.get('business_id'):
                query += " AND business_id = ?"
                params.append(filters['business_id'])

        query += " ORDER BY date DESC"

        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        return [dict(row) for row in results]

    def get_statistics(self):
        """Get statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) as total FROM invoices')
        total = cursor.fetchone()['total']

        cursor.execute('SELECT COUNT(*) as processed FROM invoices WHERE processed = 1')
        processed = cursor.fetchone()['processed']

        cursor.execute('SELECT COUNT(*) as pending FROM invoices WHERE processed = 0')
        pending = cursor.fetchone()['pending']

        cursor.execute('SELECT SUM(amount) as total_amount FROM invoices WHERE processed = 1')
        total_amount = cursor.fetchone()['total_amount'] or 0

        cursor.execute('''
            SELECT category, COUNT(*) as count, SUM(amount) as total
            FROM invoices
            WHERE processed = 1
            GROUP BY category
        ''')
        by_category = [dict(row) for row in cursor.fetchall()]

        conn.close()

        return {
            'total': total,
            'processed': processed,
            'pending': pending,
            'total_amount': total_amount,
            'by_category': by_category
        }

    def get_dashboard_stats(self, business_id=None, year=None):
        """Get comprehensive dashboard statistics

        Args:
            business_id: Optional business ID to filter stats
            year: Optional year to filter stats (default: current year)
        """
        from datetime import datetime

        conn = self.get_connection()
        cursor = conn.cursor()

        current_year = year if year is not None else datetime.now().year
        current_month = datetime.now().month
        
        # Build WHERE clause for business filter
        business_filter = ''
        business_params = []
        if business_id:
            business_filter = ' AND business_id = ?'
            business_params = [business_id]

        # Total income for selected year (ERE prefix)
        cursor.execute(f'''
            SELECT SUM(amount) as total
            FROM invoices
            WHERE processed = 1 AND invoice_id LIKE 'ERE%'
            AND strftime('%Y', date) = ?{business_filter}
        ''', [str(current_year)] + business_params)
        total_income = cursor.fetchone()['total'] or 0

        # Total expenses for selected year (ARE prefix)
        cursor.execute(f'''
            SELECT SUM(amount) as total
            FROM invoices
            WHERE processed = 1 AND invoice_id LIKE 'ARE%'
            AND strftime('%Y', date) = ?{business_filter}
        ''', [str(current_year)] + business_params)
        total_expenses = cursor.fetchone()['total'] or 0

        # Monthly income
        cursor.execute(f'''
            SELECT SUM(amount) as total
            FROM invoices
            WHERE processed = 1
            AND invoice_id LIKE 'ERE%'
            AND strftime('%Y', date) = ?
            AND strftime('%m', date) = ?{business_filter}
        ''', [str(current_year), f'{current_month:02d}'] + business_params)
        monthly_income = cursor.fetchone()['total'] or 0

        # Monthly expenses
        cursor.execute(f'''
            SELECT SUM(amount) as total
            FROM invoices
            WHERE processed = 1
            AND invoice_id LIKE 'ARE%'
            AND strftime('%Y', date) = ?
            AND strftime('%m', date) = ?{business_filter}
        ''', [str(current_year), f'{current_month:02d}'] + business_params)
        monthly_expenses = cursor.fetchone()['total'] or 0

        # Yearly income
        cursor.execute(f'''
            SELECT SUM(amount) as total
            FROM invoices
            WHERE processed = 1
            AND invoice_id LIKE 'ERE%'
            AND strftime('%Y', date) = ?{business_filter}
        ''', [str(current_year)] + business_params)
        yearly_income = cursor.fetchone()['total'] or 0

        # Yearly expenses
        cursor.execute(f'''
            SELECT SUM(amount) as total
            FROM invoices
            WHERE processed = 1
            AND invoice_id LIKE 'ARE%'
            AND strftime('%Y', date) = ?{business_filter}
        ''', [str(current_year)] + business_params)
        yearly_expenses = cursor.fetchone()['total'] or 0

        # Pending reviews
        cursor.execute(f'''
            SELECT COUNT(*) as count
            FROM invoices
            WHERE reviewed = 0 AND ocr_text IS NOT NULL{business_filter}
        ''', business_params)
        pending_reviews = cursor.fetchone()['count']

        # Income by category (for selected year)
        cursor.execute(f'''
            SELECT category, SUM(amount) as total, COUNT(*) as count
            FROM invoices
            WHERE processed = 1 AND invoice_id LIKE 'ERE%'
            AND strftime('%Y', date) = ?{business_filter}
            GROUP BY category
            ORDER BY total DESC
        ''', [str(current_year)] + business_params)
        income_by_category = [dict(row) for row in cursor.fetchall()]

        # Expenses by category (for selected year)
        cursor.execute(f'''
            SELECT category, SUM(amount) as total, COUNT(*) as count
            FROM invoices
            WHERE processed = 1 AND invoice_id LIKE 'ARE%'
            AND strftime('%Y', date) = ?{business_filter}
            GROUP BY category
            ORDER BY total DESC
        ''', [str(current_year)] + business_params)
        expenses_by_category = [dict(row) for row in cursor.fetchall()]

        # Recent activity (last 10 processed from selected year)
        cursor.execute(f'''
            SELECT id, invoice_id, date, amount, category, description, file_path
            FROM invoices
            WHERE processed = 1
            AND strftime('%Y', date) = ?{business_filter}
            ORDER BY updated_at DESC
            LIMIT 10
        ''', [str(current_year)] + business_params)
        recent_activity = [dict(row) for row in cursor.fetchall()]

        conn.close()

        return {
            'total_income': total_income,
            'total_expenses': total_expenses,
            'profit': total_income - total_expenses,
            'monthly_income': monthly_income,
            'monthly_expenses': monthly_expenses,
            'monthly_profit': monthly_income - monthly_expenses,
            'yearly_income': yearly_income,
            'yearly_expenses': yearly_expenses,
            'yearly_profit': yearly_income - yearly_expenses,
            'pending_reviews': pending_reviews,
            'income_by_category': income_by_category,
            'expenses_by_category': expenses_by_category,
            'recent_activity': recent_activity,
        }

    # ============================================================
    # BUSINESS MANAGEMENT
    # ============================================================

    def create_business(self, name, prefix, color='#007AFF'):
        """Create a new business"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO businesses (name, prefix, color)
                VALUES (?, ?, ?)
            ''', (name, prefix, color))
            conn.commit()
            business_id = cursor.lastrowid
            conn.close()
            return business_id
        except sqlite3.IntegrityError as e:
            conn.close()
            raise ValueError(f"Business with name '{name}' or prefix '{prefix}' already exists")

    def get_all_businesses(self):
        """Get all businesses"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM businesses ORDER BY created_at ASC')
        results = cursor.fetchall()
        conn.close()

        return [dict(row) for row in results]

    def get_business(self, business_id):
        """Get business by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM businesses WHERE id = ?', (business_id,))
        result = cursor.fetchone()
        conn.close()

        return dict(result) if result else None

    def get_business_by_name(self, name):
        """Get business by name"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM businesses WHERE name = ?', (name,))
        result = cursor.fetchone()
        conn.close()

        return dict(result) if result else None

    def update_business(self, business_id, data):
        """Update business"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE businesses
            SET name = ?,
                prefix = ?,
                color = ?,
                inbox_path = ?,
                archive_path = ?
            WHERE id = ?
        ''', (
            data.get('name'),
            data.get('prefix'),
            data.get('color'),
            data.get('inbox_path'),
            data.get('archive_path'),
            business_id
        ))

        conn.commit()
        conn.close()

    def delete_business(self, business_id, cascade=False, reassign_to=None):
        """
        Delete business with options for handling associated invoices and recurring transactions

        Args:
            business_id: ID of business to delete
            cascade: If True, delete all associated invoices, recurring transactions and their files
            reassign_to: If set, reassign all invoices and recurring transactions to this business_id instead of deleting

        Raises:
            ValueError: If invoices or recurring transactions exist and neither cascade nor reassign_to is set
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # Check if any invoices exist for this business
        cursor.execute('SELECT COUNT(*) as count FROM invoices WHERE business_id = ?', (business_id,))
        invoice_count = cursor.fetchone()['count']

        # Check if any recurring transactions exist for this business
        cursor.execute('SELECT COUNT(*) as count FROM recurring_transactions WHERE business_id = ?', (business_id,))
        recurring_count = cursor.fetchone()['count']

        if invoice_count > 0 or recurring_count > 0:
            if cascade:
                # CASCADE DELETE: Delete all invoices and their physical files
                if invoice_count > 0:
                    cursor.execute('SELECT file_path FROM invoices WHERE business_id = ?', (business_id,))
                    files = cursor.fetchall()

                    # Delete physical files
                    from pathlib import Path
                    deleted_files = 0
                    for row in files:
                        file_path = Path(row['file_path'])
                        if file_path.exists():
                            try:
                                file_path.unlink()
                                deleted_files += 1
                            except Exception as e:
                                print(f"Warning: Could not delete file {file_path}: {e}")

                    # Delete invoices from database
                    cursor.execute('DELETE FROM invoices WHERE business_id = ?', (business_id,))
                    print(f"✓ Deleted {invoice_count} invoices ({deleted_files} files)")

                # CASCADE DELETE: Delete all recurring transactions
                if recurring_count > 0:
                    cursor.execute('DELETE FROM recurring_transactions WHERE business_id = ?', (business_id,))
                    print(f"✓ Deleted {recurring_count} recurring transactions")

            elif reassign_to is not None:
                # REASSIGN: Move invoices to another business
                if invoice_count > 0:
                    cursor.execute('UPDATE invoices SET business_id = ? WHERE business_id = ?',
                                 (reassign_to, business_id))
                    print(f"✓ Reassigned {invoice_count} invoices to business {reassign_to}")

                # REASSIGN: Move recurring transactions to another business
                if recurring_count > 0:
                    cursor.execute('UPDATE recurring_transactions SET business_id = ? WHERE business_id = ?',
                                 (reassign_to, business_id))
                    print(f"✓ Reassigned {recurring_count} recurring transactions to business {reassign_to}")

            else:
                # BLOCK: Neither cascade nor reassign specified
                conn.close()
                raise ValueError(f"Cannot delete business: {invoice_count} invoices and {recurring_count} recurring transactions still associated. "
                               f"Use cascade=True to delete all, or reassign_to=<id> to move them.")

        # Delete the business
        cursor.execute('DELETE FROM businesses WHERE id = ?', (business_id,))
        conn.commit()
        conn.close()

    def rename_archived_file(self, file_id, old_data, new_data):
        """
        Rename archived file when metadata changes

        Args:
            file_id: Invoice ID
            old_data: Dict with old invoice data (from database)
            new_data: Dict with new invoice data (from update request)

        Returns:
            str: New file path if renamed, None if no rename needed
        """
        from pathlib import Path
        import shutil
        from datetime import datetime

        # Only rename archived files
        if not old_data.get('is_archived') or '/Archive/' not in old_data.get('file_path', ''):
            return None

        old_path = Path(old_data['file_path'])
        if not old_path.exists():
            return None

        # Get business info
        business_id = old_data['business_id']
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM businesses WHERE id = ?', (business_id,))
        business = cursor.fetchone()
        conn.close()

        if not business:
            return None

        # Build new filename based on updated data
        # Use new data if provided, otherwise fall back to old data
        date_str = new_data.get('date', old_data.get('date'))
        invoice_id = old_data.get('invoice_id')  # Invoice ID never changes
        category = new_data.get('category', old_data.get('category', 'Unknown'))
        description = new_data.get('description', old_data.get('description', ''))
        amount = new_data.get('amount', old_data.get('amount', 0))

        if not date_str or not invoice_id:
            return None  # Can't build filename without date or invoice_id

        # Parse date
        try:
            if isinstance(date_str, str):
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            else:
                date_obj = date_str
        except:
            return None

        # Generate new filename: YYMMDD_InvoiceID_Category_Description_Amount.pdf
        date_part = date_obj.strftime('%y%m%d')
        category_safe = category.replace('/', '-')
        description_safe = (description[:30]
                          .replace('/', '-')
                          .replace(' ', '_')
                          .strip('_'))
        amount_safe = str(amount).replace('.', '_')

        new_filename = f"{date_part}_{invoice_id}_{category_safe}_{description_safe}_{amount_safe}{old_path.suffix}"
        new_filename = new_filename.replace('__', '_')  # Clean double underscores

        # Build new path (same directory, new filename)
        new_path = old_path.parent / new_filename

        # Check if rename is needed
        if old_path == new_path:
            return None  # No change needed

        # Rename the file
        try:
            shutil.move(str(old_path), str(new_path))
            return str(new_path)
        except Exception as e:
            print(f"Warning: Could not rename file: {e}")
            return None

    # ============================================================
    # RECURRING TRANSACTIONS
    # ============================================================

    def create_recurring_transaction(self, data):
        """Create a new recurring transaction"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO recurring_transactions
            (business_id, type, description, amount, category, frequency,
             day_of_month, start_date, end_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('business_id'),
            data['type'],
            data['description'],
            data['amount'],
            data['category'],
            data['frequency'],
            data.get('day_of_month', 1),
            data['start_date'],
            data.get('end_date')
        ))

        conn.commit()
        recurring_id = cursor.lastrowid
        conn.close()
        return recurring_id

    def get_recurring_transactions(self, business_id=None, active_only=True):
        """Get all recurring transactions with count of generated invoices"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if business_id:
            if active_only:
                cursor.execute('''
                    SELECT rt.*,
                           COUNT(i.id) as generated_count
                    FROM recurring_transactions rt
                    LEFT JOIN invoices i ON i.recurring_transaction_id = rt.id
                    WHERE rt.business_id = ? AND rt.active = 1
                    GROUP BY rt.id
                    ORDER BY rt.created_at DESC
                ''', (business_id,))
            else:
                cursor.execute('''
                    SELECT rt.*,
                           COUNT(i.id) as generated_count
                    FROM recurring_transactions rt
                    LEFT JOIN invoices i ON i.recurring_transaction_id = rt.id
                    WHERE rt.business_id = ?
                    GROUP BY rt.id
                    ORDER BY rt.created_at DESC
                ''', (business_id,))
        else:
            if active_only:
                cursor.execute('''
                    SELECT rt.*,
                           COUNT(i.id) as generated_count
                    FROM recurring_transactions rt
                    LEFT JOIN invoices i ON i.recurring_transaction_id = rt.id
                    WHERE rt.active = 1
                    GROUP BY rt.id
                    ORDER BY rt.created_at DESC
                ''')
            else:
                cursor.execute('''
                    SELECT rt.*,
                           COUNT(i.id) as generated_count
                    FROM recurring_transactions rt
                    LEFT JOIN invoices i ON i.recurring_transaction_id = rt.id
                    GROUP BY rt.id
                    ORDER BY rt.created_at DESC
                ''')

        results = cursor.fetchall()
        conn.close()
        return [dict(row) for row in results]

    def get_recurring_transaction(self, recurring_id):
        """Get a single recurring transaction"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM recurring_transactions WHERE id = ?', (recurring_id,))
        result = cursor.fetchone()
        conn.close()

        return dict(result) if result else None

    def update_recurring_transaction(self, recurring_id, data):
        """Update a recurring transaction"""
        conn = self.get_connection()
        cursor = conn.cursor()

        allowed_fields = {
            'description', 'amount', 'category', 'frequency', 'day_of_month',
            'start_date', 'end_date', 'active', 'last_generated_date'
        }

        updates = []
        values = []

        for field, value in data.items():
            if field in allowed_fields:
                updates.append(f"{field} = ?")
                values.append(value)

        if not updates:
            conn.close()
            return

        values.append(recurring_id)
        query = f"UPDATE recurring_transactions SET {', '.join(updates)} WHERE id = ?"

        cursor.execute(query, values)
        conn.commit()
        conn.close()

    def delete_recurring_transaction(self, recurring_id):
        """Delete a recurring transaction"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM recurring_transactions WHERE id = ?', (recurring_id,))
        conn.commit()
        conn.close()

    def generate_recurring_transactions(self):
        """
        Generate invoice entries from active recurring transactions
        Returns list of generated invoice IDs
        """
        from datetime import datetime, timedelta
        from dateutil.relativedelta import relativedelta

        today = datetime.now().date()
        generated_ids = []

        # Get all active recurring transactions
        recurring = self.get_recurring_transactions(active_only=True)

        for rec in recurring:
            # Parse dates
            start_date = datetime.strptime(rec['start_date'], '%Y-%m-%d').date()
            last_generated = None
            if rec['last_generated_date']:
                last_generated = datetime.strptime(rec['last_generated_date'], '%Y-%m-%d').date()

            # Calculate starting point for generation
            if last_generated:
                current_date = last_generated
            else:
                current_date = start_date

            # Get business info for path
            business = self.get_business(rec['business_id']) if rec['business_id'] else None

            # Generate ALL missing entries from start_date (or last_generated) to today
            max_iterations = 1000  # Safety limit to prevent infinite loops
            iterations = 0

            while iterations < max_iterations:
                # Calculate next due date
                if iterations == 0 and not last_generated:
                    # First iteration, starting from start_date
                    next_due = start_date
                else:
                    # Add period based on frequency
                    if rec['frequency'] == 'monthly':
                        current_date = current_date + relativedelta(months=1)
                    elif rec['frequency'] == 'quarterly':
                        current_date = current_date + relativedelta(months=3)
                    elif rec['frequency'] == 'yearly':
                        current_date = current_date + relativedelta(years=1)

                    next_due = current_date

                # Adjust to day_of_month if specified
                if rec['day_of_month']:
                    try:
                        next_due = next_due.replace(day=rec['day_of_month'])
                    except ValueError:
                        # Day doesn't exist in month (e.g. Feb 31), use last day
                        next_due = next_due.replace(day=1) + relativedelta(months=1) - timedelta(days=1)

                # Check if this date should be generated
                if next_due > today:
                    break  # Stop when we reach future dates

                # Check if end_date has passed
                if rec['end_date']:
                    end_date = datetime.strptime(rec['end_date'], '%Y-%m-%d').date()
                    if next_due > end_date:
                        break

                # Check if this entry already exists (avoid duplicates)
                conn = self.get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id FROM invoices
                    WHERE recurring_transaction_id = ? AND date = ?
                ''', (rec['id'], next_due.strftime('%Y-%m-%d')))
                existing = cursor.fetchone()
                conn.close()

                if not existing:
                    # Create a virtual invoice entry
                    invoice_id = self._create_virtual_invoice(rec, next_due, business)
                    if invoice_id:
                        generated_ids.append(invoice_id)

                # Update current_date for next iteration
                current_date = next_due
                iterations += 1

            # Update last_generated_date to the last date we processed
            if current_date:
                self.update_recurring_transaction(rec['id'], {
                    'last_generated_date': current_date.strftime('%Y-%m-%d')
                })

        return generated_ids

    def _create_virtual_invoice(self, recurring, date, business):
        """Create invoice entry with invoice_id (placeholder will be created later)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Generate invoice_id based on type
            year = date.year
            if recurring['type'] == 'income':
                invoice_id = self.get_next_income_id(year=year, business_id=recurring['business_id'])
            else:  # expense
                invoice_id = self.get_next_invoice_id(year=year, business_id=recurring['business_id'])

            # Create entry with invoice_id but NO file_path yet
            # The placeholder PDF and file_path will be created by generate_missing_placeholders()
            cursor.execute('''
                INSERT INTO invoices
                (invoice_id, business_id, date, amount, category, description,
                 reviewed, processed, recurring_transaction_id, is_recurring_generated, unread, is_placeholder_pdf)
                VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, 1, 1, 1)
            ''', (
                invoice_id,
                recurring['business_id'],
                date.strftime('%Y-%m-%d'),
                recurring['amount'],
                recurring['category'],
                recurring['description'],
                recurring['id']
            ))

            conn.commit()
            db_id = cursor.lastrowid
            conn.close()
            print(f"✅ Created virtual invoice {invoice_id} for recurring transaction {recurring['id']}")
            return db_id
        except Exception as e:
            print(f"Error creating virtual invoice: {e}")
            import traceback
            traceback.print_exc()
            conn.close()
            return None
