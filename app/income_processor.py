"""
Income Processor - Handles income document processing
Analog zu ocr_processor.py, aber für Einnahmen
"""

import pytesseract
from PIL import Image
from pdf2image import convert_from_path
import re
from pathlib import Path
from dateutil import parser as date_parser
from llm_extractor import LLMExtractor


class IncomeProcessor:
    def __init__(self, use_llm=True):
        # Initialize LLM extractor with better model (gemma3:4b for improved accuracy)
        self.use_llm = use_llm
        if use_llm:
            self.llm = LLMExtractor(model='gemma3:4b')
            if self.llm.is_available():
                print("✅ Ollama LLM available (gemma3:4b) - using AI-enhanced extraction")
            else:
                print("⚠️  Ollama not available - falling back to regex extraction")
                self.use_llm = False
        else:
            self.llm = None

    def process_file(self, file_path):
        """Process an income file and extract text via OCR"""
        file_path = Path(file_path)

        import sys

        print(f"\n{'='*60}", file=sys.stderr)
        print(f"💰 Processing Income: {Path(file_path).name}", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)

        # Extract text
        text = self._extract_text(file_path)
        print(f"📄 OCR Text length: {len(text)} chars", file=sys.stderr)

        # Try LLM extraction first
        if self.use_llm and self.llm:
            print(f"🤖 Trying LLM extraction...", file=sys.stderr)
            llm_result = self.llm.extract_income_data(text)

            if llm_result and llm_result.get('date') and llm_result.get('amount'):
                print(f"✅ LLM extraction SUCCESSFUL!", file=sys.stderr)
                print(f"   Date: {llm_result.get('date')}", file=sys.stderr)
                print(f"   Amount: {llm_result.get('amount')}", file=sys.stderr)
                print(f"   Category: {llm_result.get('category')}", file=sys.stderr)
                print(f"   Description: {llm_result.get('description')}", file=sys.stderr)
                return {
                    'text': text,
                    'date': llm_result.get('date'),
                    'amount': llm_result.get('amount'),
                    'description': llm_result.get('description') or self._extract_description(text),
                    'category': llm_result.get('category') or self._predict_category(text)
                }
            else:
                print(f"⚠️  LLM extraction returned incomplete data", file=sys.stderr)

        # Fallback to regex extraction
        print("📝 Using REGEX extraction (fallback)", file=sys.stderr)
        result = {
            'text': text,
            'date': self._extract_date(text),
            'amount': self._extract_amount(text),
            'description': self._extract_description(text),
            'category': self._predict_category(text)
        }

        print(f"   Date: {result['date']}", file=sys.stderr)
        print(f"   Amount: {result['amount']}", file=sys.stderr)
        print(f"   Category: {result['category']}", file=sys.stderr)

        return result

    def _extract_text(self, file_path):
        """Extract text from PDF or image"""
        suffix = file_path.suffix.lower()

        if suffix == '.pdf':
            # Convert PDF to images
            images = convert_from_path(str(file_path), dpi=300)
            text = ''
            for image in images:
                text += pytesseract.image_to_string(image, lang='deu+eng')
            return text

        elif suffix in ['.jpg', '.jpeg', '.png']:
            # Process image directly
            image = Image.open(file_path)
            return pytesseract.image_to_string(image, lang='deu+eng')

        else:
            raise ValueError(f"Unsupported file type: {suffix}")

    def _extract_date(self, text):
        """Extract invoice date from text"""
        # Common German date patterns
        date_patterns = [
            r'\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b',  # DD.MM.YYYY or DD/MM/YYYY
            r'\b(\d{4})[./-](\d{1,2})[./-](\d{1,2})\b',  # YYYY-MM-DD
            r'Datum:?\s*(\d{1,2})[./-](\d{1,2})[./-](\d{4})',
            r'Rechnungsdatum:?\s*(\d{1,2})[./-](\d{1,2})[./-](\d{4})',
            r'Invoice Date:?\s*(\d{1,2})[./-](\d{1,2})[./-](\d{4})',
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    date_str = match.group(0).split(':')[-1].strip()
                    parsed_date = date_parser.parse(date_str, dayfirst=True)
                    return parsed_date.strftime('%Y-%m-%d')
                except:
                    continue

        return None

    def _extract_amount(self, text):
        """Extract total amount from text - handles German number format with thousands separator"""
        # Look for EUR amounts - improved patterns for German format (1.299,99)
        amount_patterns = [
            # With keywords (Gesamt, Total, etc.)
            r'(?:Gesamt|Total|Summe|Betrag|Amount|Netto|Brutto).*?(\d{1,3}(?:\.\d{3})*,\d{2})\s*€',
            # Direct € prefix/suffix with thousands separator
            r'€\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
            r'(\d{1,3}(?:\.\d{3})*,\d{2})\s*€',
            # EUR prefix/suffix with thousands separator
            r'EUR\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
            r'(\d{1,3}(?:\.\d{3})*,\d{2})\s*EUR',
            # Fallback: Simple format without thousands separator
            r'(?:Gesamt|Total|Summe|Betrag|Amount|Netto|Brutto).*?(\d+,\d{2})\s*€',
            r'€\s*(\d+,\d{2})',
            r'(\d+,\d{2})\s*€',
        ]

        amounts = []
        for pattern in amount_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                amount_str = match.group(1)
                # Convert German format to float: 1.299,99 -> 1299.99
                amount_str = amount_str.replace('.', '').replace(',', '.')
                try:
                    amount = float(amount_str)
                    amounts.append(amount)
                except:
                    continue

        # Return the largest amount found (usually the total)
        return max(amounts) if amounts else None

    def _extract_description(self, text):
        """Extract a short description from text"""
        # Get first meaningful line
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        # Skip common header words
        skip_words = ['rechnung', 'invoice', 'beleg', 'quittung', 'receipt']

        for line in lines[:10]:  # Check first 10 lines
            line_lower = line.lower()
            if len(line) > 10 and not any(word in line_lower for word in skip_words):
                # Truncate if too long
                return line[:50]

        return lines[0][:50] if lines else "Unbekannt"

    def _predict_category(self, text):
        """
        Predict income category based on keywords
        Categories for income (Einnahmen)
        """
        text_lower = text.lower()

        categories = {
            'Lizenzgebühren': [
                'lizenz', 'license', 'nutzungsrecht', 'urheberrecht', 'copyright',
                'verwertung', 'gema', 'royalty', 'royalties'
            ],
            'Workshops': [
                'workshop', 'seminar', 'schulung', 'training', 'kurs', 'lehre',
                'unterricht', 'vortrag', 'presentation', 'lecture'
            ],
            'Stipendien': [
                'stipendium', 'förderung', 'grant', 'scholarship', 'preis',
                'award', 'auszeichnung', 'subvention', 'zuschuss'
            ],
            'Verkäufe': [
                'verkauf', 'sale', 'artwork', 'kunstwerk', 'galerie', 'gallery',
                'edition', 'print', 'skulptur', 'installation'
            ],
            'Honorar': [
                'honorar', 'fee', 'dienstleistung', 'service', 'projekt',
                'auftrag', 'beratung', 'consulting', 'freelance', 'werk',
                'rechnung', 'invoice'
            ],
        }

        for category, keywords in categories.items():
            if any(keyword in text_lower for keyword in keywords):
                return category

        return 'Sonstiges'
