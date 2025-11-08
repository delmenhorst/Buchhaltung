"""
Auto Processor - Background worker for automatic document processing
Watches Inbox folders and automatically processes new files
"""

import time
import threading
from pathlib import Path
from datetime import datetime
import logging
from filename_generator import generate_invoice_filename

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutoProcessor:
    def __init__(self, db, folder_manager, ocr_processor, income_processor, image_converter):
        self.db = db
        self.folder_manager = folder_manager
        self.ocr_processor = ocr_processor
        self.income_processor = income_processor
        self.image_converter = image_converter
        self.running = False
        self.thread = None
        self.check_interval = 10  # Check every 10 seconds

    def start(self):
        """Start the background worker"""
        if self.running:
            logger.warning("Auto processor already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()
        logger.info("✅ Auto processor started - watching Inbox folders")

    def stop(self):
        """Stop the background worker"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Auto processor stopped")

    def _worker_loop(self):
        """Main worker loop - runs in background thread"""
        while self.running:
            try:
                self._process_inbox_files()
            except Exception as e:
                logger.error(f"Error in auto processor: {e}", exc_info=True)

            # Sleep for check_interval seconds
            time.sleep(self.check_interval)

    def _process_inbox_files(self):
        """Scan all inbox folders and process new files"""
        businesses = self.db.get_all_businesses()

        for business in businesses:
            try:
                files_with_type = self.folder_manager.get_inbox_files(business['name'])

                for file_path, doc_type in files_with_type:
                    # Check if file already in database
                    if self.db.file_exists(str(file_path)):
                        file_info = self.db.get_file_by_path(str(file_path))

                        # Skip if already processed
                        if file_info and file_info.get('processed'):
                            continue

                        # Process if in database but not yet processed
                        if file_info and not file_info.get('ocr_text'):
                            self._auto_process_file(file_info['id'], business, doc_type)
                    else:
                        # New file - add to database and process
                        file_id = self.db.add_file(str(file_path), business['id'])
                        if file_id:
                            logger.info(f"📄 New file detected: {file_path.name} (Business: {business['name']}, Type: {doc_type})")
                            self._auto_process_file(file_id, business, doc_type)

            except Exception as e:
                logger.error(f"Error processing business {business['name']}: {e}", exc_info=True)

    def _auto_process_file(self, file_id, business, doc_type_folder):
        """Automatically process a single file with OCR and save"""
        try:
            file_info = self.db.get_file(file_id)
            if not file_info:
                return

            file_path = Path(file_info['file_path'])
            logger.info(f"🔍 Auto-processing: {file_path.name}")

            # Step 1: Convert image to PDF if needed
            if self.image_converter.is_image(file_path):
                logger.info(f"🖼️  Converting image to PDF: {file_path.name}")
                pdf_path = file_path.with_suffix('.pdf')
                self.image_converter.convert_to_pdf(file_path, pdf_path)
                file_path.unlink()  # Delete original image
                file_path = pdf_path

                # Update file path in database
                self.db.update_file_path(file_id, str(file_path), None)
                file_info['file_path'] = str(file_path)

            # Step 2: Use folder type (Einnahmen/Ausgaben) to determine processor
            doc_type = 'income' if doc_type_folder == 'Einnahmen' else 'expense'

            # Step 3: Run OCR + AI extraction
            logger.info(f"🤖 Running OCR + AI extraction...")
            if doc_type == 'income':
                result = self.income_processor.process_file(str(file_path))
            else:
                result = self.ocr_processor.process_file(str(file_path))

            # Update database with OCR results
            self.db.update_ocr_results(file_id, result)

            # Step 4: Check if we have all required fields for auto-archiving
            has_required_fields = result.get('date') and result.get('amount') and result.get('category')

            extracted_data = {
                'date': result.get('date'),
                'amount': result.get('amount'),
                'category': result.get('category'),
                'description': result.get('description'),
                'reviewed': has_required_fields,  # Auto-mark as reviewed if complete
                'processed': True
            }

            # Only update fields that have values
            update_data = {k: v for k, v in extracted_data.items() if v is not None}
            if update_data:
                self.db.update_invoice(file_id, update_data)

            # Step 5: Auto-archive if all required fields are present (like Paperless)
            if has_required_fields:
                try:
                    # Generate invoice ID
                    from datetime import datetime
                    date_obj = datetime.strptime(result['date'], '%Y-%m-%d')

                    if doc_type == 'income':
                        invoice_id = self.db.get_next_income_id(year=date_obj.year, business_id=business['id'])
                    else:
                        invoice_id = self.db.get_next_invoice_id(year=date_obj.year, business_id=business['id'])

                    self.db.update_invoice(file_id, {'invoice_id': invoice_id})

                    # Move file to Archive (Paperless-style) with renamed filename
                    import shutil
                    current_path = Path(file_info['file_path'])

                    if current_path.exists() and '/Inbox/' in str(current_path):
                        year = date_obj.year
                        doc_type_name = 'Einnahmen' if doc_type == 'income' else 'Ausgaben'

                        # Generate new tax-friendly filename
                        # Format: YYYY-MM-DD_InvoiceID_Type_Supplier_Description_Category_Amount.pdf
                        new_filename = generate_invoice_filename(
                            data=result,
                            invoice_id=invoice_id,
                            file_extension=current_path.suffix
                        )

                        # Correct archive path: Archive/BusinessName/Ausgaben|Einnahmen/Year/filename.pdf
                        base_dir = self.folder_manager.base_dir
                        archive_path = base_dir / 'Archive' / business['name'] / doc_type_name / str(year) / new_filename

                        # Create archive directory
                        archive_path.parent.mkdir(parents=True, exist_ok=True)

                        # Move file with new name
                        shutil.move(str(current_path), str(archive_path))

                        # Update database
                        self.db.update_invoice(file_id, {'file_path': str(archive_path), 'is_archived': True})

                        logger.info(f"✅ AUTO-ARCHIVED: {result.get('amount')}€ on {result.get('date')} → {new_filename}")
                    else:
                        logger.info(f"✅ Auto-saved: {result.get('amount')}€ on {result.get('date')} - {result.get('description', 'N/A')}")

                except Exception as e:
                    logger.error(f"Error auto-archiving: {e}")
                    logger.info(f"📋 Ready for manual review: {file_path.name}")
            else:
                missing = []
                if not result.get('date'): missing.append('date')
                if not result.get('amount'): missing.append('amount')
                if not result.get('category'): missing.append('category')
                logger.warning(f"⚠️  Incomplete extraction (missing: {', '.join(missing)}) - stays in Inbox for manual review: {file_path.name}")

        except Exception as e:
            logger.error(f"Error auto-processing file {file_id}: {e}", exc_info=True)
            # Mark file as processed but not reviewed to allow manual intervention
            try:
                self.db.update_invoice(file_id, {'processed': True, 'reviewed': False})
            except Exception as update_error:
                logger.error(f"Failed to mark file as processed: {update_error}")

    def _detect_document_type(self, file_path):
        """
        Detect if document is income or expense
        You can implement smarter detection based on:
        - Filename patterns
        - Folder structure
        - OCR content analysis
        """
        filename = file_path.name.lower()

        # Simple heuristic - check filename
        income_keywords = ['rechnung', 'invoice', 'payment', 'honorar', 'einnahme']
        expense_keywords = ['beleg', 'quittung', 'receipt', 'ausgabe']

        for keyword in income_keywords:
            if keyword in filename:
                return 'income'

        # Default to expense
        return 'expense'
