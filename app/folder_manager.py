"""
Folder Manager - Handles Inbox and Archive folder structure for businesses
"""

from pathlib import Path
import shutil

class FolderManager:
    def __init__(self, base_dir):
        """
        Initialize FolderManager

        base_dir: Path to FINANZEN folder
        """
        self.base_dir = Path(base_dir)
        self.inbox_dir = self.base_dir / 'Inbox'
        self.archive_dir = self.base_dir / 'Archive'

        # Ensure base directories exist
        self.inbox_dir.mkdir(exist_ok=True)
        self.archive_dir.mkdir(exist_ok=True)

    def create_business_folders(self, business_name):
        """
        Create folder structure for a new business
        
        Creates:
        - Inbox/BusinessName/Einnahmen/
        - Inbox/BusinessName/Ausgaben/
        - Archive/BusinessName/Ausgaben/2025/
        - Archive/BusinessName/Einnahmen/2025/
        """
        from datetime import datetime
        current_year = datetime.now().year
        
        # Create inbox folders with Einnahmen/Ausgaben subfolders
        inbox_base = self.inbox_dir / business_name
        inbox_einnahmen = inbox_base / 'Einnahmen'
        inbox_ausgaben = inbox_base / 'Ausgaben'
        
        inbox_einnahmen.mkdir(parents=True, exist_ok=True)
        inbox_ausgaben.mkdir(parents=True, exist_ok=True)
        
        # Create archive folders (with year)
        archive_base = self.archive_dir / business_name
        ausgaben_path = archive_base / 'Ausgaben' / str(current_year)
        einnahmen_path = archive_base / 'Einnahmen' / str(current_year)
        
        ausgaben_path.mkdir(parents=True, exist_ok=True)
        einnahmen_path.mkdir(parents=True, exist_ok=True)
        
        return {
            'inbox': str(inbox_base),
            'inbox_einnahmen': str(inbox_einnahmen),
            'inbox_ausgaben': str(inbox_ausgaben),
            'archive_base': str(archive_base),
            'ausgaben': str(ausgaben_path),
            'einnahmen': str(einnahmen_path)
        }

    def get_inbox_files(self, business_name, doc_type=None):
        """
        Get all files from a business's inbox folder
        
        Args:
            business_name: Name of the business
            doc_type: 'Einnahmen' or 'Ausgaben' or None for both

        Returns: list of tuples (file_path, doc_type)
        """
        inbox_path = self.inbox_dir / business_name

        if not inbox_path.exists():
            return []

        files = []
        
        # Scan Einnahmen folder
        if doc_type is None or doc_type == 'Einnahmen':
            einnahmen_path = inbox_path / 'Einnahmen'
            if einnahmen_path.exists():
                for file_path in einnahmen_path.glob('*'):
                    if file_path.suffix.lower() in ['.pdf', '.jpg', '.jpeg', '.png', '.heic']:
                        files.append((file_path, 'Einnahmen'))
        
        # Scan Ausgaben folder
        if doc_type is None or doc_type == 'Ausgaben':
            ausgaben_path = inbox_path / 'Ausgaben'
            if ausgaben_path.exists():
                for file_path in ausgaben_path.glob('*'):
                    if file_path.suffix.lower() in ['.pdf', '.jpg', '.jpeg', '.png', '.heic']:
                        files.append((file_path, 'Ausgaben'))

        return sorted(files, key=lambda x: x[0].stat().st_mtime, reverse=True)

    def get_all_inbox_files(self):
        """
        Get all files from all business inbox folders

        Returns: dict with business_name as key and list of files as value
        """
        result = {}

        if not self.inbox_dir.exists():
            return result

        for business_folder in self.inbox_dir.iterdir():
            if business_folder.is_dir():
                files = self.get_inbox_files(business_folder.name)
                if files:
                    result[business_folder.name] = files

        return result

    def move_to_archive(self, file_path, business_name, doc_type, new_filename):
        """
        Move file from Inbox to Archive with new name

        file_path: Current path to file
        business_name: Name of business
        doc_type: 'income' or 'expense'
        new_filename: New filename (e.g., 251101_ARE-MK-2025001_Buro_Laptop_1299_99.pdf)

        Returns: new file path
        """
        from datetime import datetime
        current_year = datetime.now().year

        file_path = Path(file_path)

        # Determine target folder
        folder_name = 'Einnahmen' if doc_type == 'income' else 'Ausgaben'
        target_dir = self.archive_dir / business_name / folder_name / str(current_year)
        target_dir.mkdir(parents=True, exist_ok=True)

        # New file path
        new_path = target_dir / new_filename

        # Move file
        shutil.move(str(file_path), str(new_path))

        return str(new_path)

    def ensure_archive_year(self, business_name, year):
        """
        Ensure archive folders exist for a specific year
        """
        ausgaben_path = self.archive_dir / business_name / 'Ausgaben' / str(year)
        einnahmen_path = self.archive_dir / business_name / 'Einnahmen' / str(year)

        ausgaben_path.mkdir(parents=True, exist_ok=True)
        einnahmen_path.mkdir(parents=True, exist_ok=True)

    def get_business_folders(self):
        """
        Get list of all business folders in Inbox

        Returns: list of business names
        """
        if not self.inbox_dir.exists():
            return []

        return [
            folder.name
            for folder in self.inbox_dir.iterdir()
            if folder.is_dir()
        ]

    def get_archive_files(self, business_name, doc_type=None, year=None):
        """
        Get all files from a business's archive folder

        Args:
            business_name: Name of the business
            doc_type: 'Einnahmen' or 'Ausgaben' or None for both
            year: Specific year or None for all years

        Returns: list of tuples (file_path, doc_type)
        """
        archive_path = self.archive_dir / business_name

        if not archive_path.exists():
            return []

        files = []

        # Scan Einnahmen folder
        if doc_type is None or doc_type == 'Einnahmen':
            einnahmen_base = archive_path / 'Einnahmen'
            if einnahmen_base.exists():
                # Get all year folders or specific year
                year_folders = [einnahmen_base / str(year)] if year else list(einnahmen_base.iterdir())
                for year_folder in year_folders:
                    if year_folder.is_dir():
                        for file_path in year_folder.glob('*'):
                            if file_path.suffix.lower() in ['.pdf', '.jpg', '.jpeg', '.png', '.heic']:
                                files.append((file_path, 'Einnahmen'))

        # Scan Ausgaben folder
        if doc_type is None or doc_type == 'Ausgaben':
            ausgaben_base = archive_path / 'Ausgaben'
            if ausgaben_base.exists():
                # Get all year folders or specific year
                year_folders = [ausgaben_base / str(year)] if year else list(ausgaben_base.iterdir())
                for year_folder in year_folders:
                    if year_folder.is_dir():
                        for file_path in year_folder.glob('*'):
                            if file_path.suffix.lower() in ['.pdf', '.jpg', '.jpeg', '.png', '.heic']:
                                files.append((file_path, 'Ausgaben'))

        return sorted(files, key=lambda x: x[0].stat().st_mtime, reverse=True)

    def delete_business_folders(self, business_name):
        """
        Delete all folders for a business (Inbox + Archive)

        WARNING: This permanently deletes all files!
        """
        inbox_path = self.inbox_dir / business_name
        archive_path = self.archive_dir / business_name

        if inbox_path.exists():
            shutil.rmtree(inbox_path)

        if archive_path.exists():
            shutil.rmtree(archive_path)
