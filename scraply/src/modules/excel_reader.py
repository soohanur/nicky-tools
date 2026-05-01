"""
Excel and CSV Reader Module

Reads data from Excel/CSV files without converting numbers to floats.
All data is kept as strings to preserve original formatting.
"""
import openpyxl
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
from ..utils.logger import setup_logger

logger = setup_logger('excel_reader')


# Constants
SUPPORTED_CSV_ENCODINGS = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
EXCEL_HEADER_OFFSET = 2


class ExcelReader:
    """
    Excel and CSV file reader that preserves original data formatting.
    
    Reads all data as strings to prevent automatic type conversion
    (no 1 -> 1.0 conversion).
    """
    
    def __init__(self, file_path: str, sheet_name: str = 'Sheet1'):
        """
        Initialize file reader.
        
        Args:
            file_path: Path to Excel or CSV file
            sheet_name: Sheet name for Excel files
        """
        self.file_path = Path(file_path)
        self.sheet_name = sheet_name
        self.workbook = None
        self.worksheet = None
        self.is_csv = self.file_path.suffix.lower() == '.csv'
        self.df = None
        
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")
        
        logger.info(f"{'CSV' if self.is_csv else 'Excel'} file loaded: {self.file_path}")
    
    def open(self) -> None:
        """Open file for reading."""
        try:
            if self.is_csv:
                self._open_csv()
            else:
                self._open_excel()
        except Exception as e:
            logger.error(f"Failed to open file: {e}")
            raise
    
    def _open_csv(self) -> None:
        """Open CSV file with string data type to prevent float conversion."""
        for encoding in SUPPORTED_CSV_ENCODINGS:
            try:
                # CRITICAL: dtype=str prevents 1 -> 1.0 conversion
                # keep_default_na=False prevents empty strings -> NaN
                self.df = pd.read_csv(
                    self.file_path, 
                    encoding=encoding, 
                    dtype=str,
                    keep_default_na=False
                )
                logger.info(f"Opened CSV file with {len(self.df)} rows (encoding: {encoding})")
                return
            except UnicodeDecodeError:
                continue
        
        raise ValueError("Could not decode CSV file with any supported encoding")
    
    def _open_excel(self) -> None:
        """Open Excel workbook."""
        self.workbook = openpyxl.load_workbook(self.file_path)
        self.worksheet = self.workbook[self.sheet_name]
        logger.info(f"Opened sheet: {self.sheet_name}")
    
    def close(self) -> None:
        """Close file and release resources."""
        if self.workbook:
            self.workbook.close()
            logger.info("Workbook closed")
        if self.df is not None:
            self.df = None
            logger.info("CSV data cleared")
    
    def read_row_data(
        self, 
        row_number: int, 
        col_company: str, 
        col_addr1: str, 
        col_addr2: str, 
        col_addr3: str
    ) -> Dict[str, str]:
        """
        Read data from specific row.
        
        Args:
            row_number: Row number (1-based, Excel format)
            col_company: Company name column
            col_addr1: Address part 1 (street)
            col_addr2: Address part 2 (house number)
            col_addr3: Address part 3 (city)
        
        Returns:
            Dictionary with row_number, company, and address
        """
        try:
            if self.is_csv:
                return self._read_csv_row(row_number, col_company, col_addr1, col_addr2, col_addr3)
            else:
                return self._read_excel_row(row_number, col_company, col_addr1, col_addr2, col_addr3)
        except Exception as e:
            logger.error(f"Error reading row {row_number}: {e}")
            return {'row_number': row_number, 'company': '', 'address': ''}
    
    def _read_csv_row(
        self, 
        row_number: int, 
        col_company: str, 
        col_addr1: str, 
        col_addr2: str, 
        col_addr3: str
    ) -> Dict[str, str]:
        """Read data from CSV row (already strings, no conversion needed)."""
        idx = row_number - EXCEL_HEADER_OFFSET
        
        if idx < 0 or idx >= len(self.df):
            return {'row_number': row_number, 'company': '', 'address': ''}
        
        row = self.df.iloc[idx]
        
        # Get values (already strings from dtype=str)
        company = str(row.get(col_company, '')).strip() if col_company in self.df.columns else ''
        addr1 = str(row.get(col_addr1, '')).strip() if col_addr1 in self.df.columns else ''
        addr2 = str(row.get(col_addr2, '')).strip() if col_addr2 in self.df.columns else ''
        addr3 = str(row.get(col_addr3, '')).strip() if col_addr3 in self.df.columns else ''
        
        # Combine address parts
        address = ' '.join(filter(None, [addr1, addr2, addr3])).strip()
        
        return {
            'row_number': row_number,
            'company': company,
            'address': address
        }
    
    def _read_excel_row(
        self, 
        row_number: int, 
        col_company: str, 
        col_addr1: str, 
        col_addr2: str, 
        col_addr3: str
    ) -> Dict[str, str]:
        """Read data from Excel row."""
        company = self.worksheet[f'{col_company}{row_number}'].value or ''
        addr1 = self.worksheet[f'{col_addr1}{row_number}'].value or ''
        addr2 = self.worksheet[f'{col_addr2}{row_number}'].value or ''
        addr3 = self.worksheet[f'{col_addr3}{row_number}'].value or ''
        
        # Convert to strings
        company = str(company).strip() if company else ''
        addr1 = str(addr1).strip() if addr1 else ''
        addr2 = str(addr2).strip() if addr2 else ''
        addr3 = str(addr3).strip() if addr3 else ''
        
        # Combine address
        address = ' '.join(filter(None, [addr1, addr2, addr3])).strip()
        
        return {
            'row_number': row_number,
            'company': company,
            'address': address
        }
    
    def get_all_rows(
        self, 
        col_company: str, 
        col_addr1: str, 
        col_addr2: str, 
        col_addr3: str, 
        start_row: int = 2,
        phone_col: str = None
    ) -> List[Dict[str, str]]:
        """
        Read all rows from file.
        
        Args:
            col_company: Company name column
            col_addr1: Address part 1
            col_addr2: Address part 2
            col_addr3: Address part 3
            start_row: First row to read (1-based)
            phone_col: Phone column to check if already processed
        
        Returns:
            List of row data dictionaries
        """
        rows = []
        
        if self.is_csv:
            total_rows = len(self.df) + EXCEL_HEADER_OFFSET
        else:
            total_rows = self.worksheet.max_row + 1
        
        logger.info(f"Reading {total_rows - start_row} rows from {'CSV' if self.is_csv else 'Excel'}")
        
        skipped_processed = 0
        skipped_empty = 0
        
        for row_num in range(start_row, total_rows):
            # Check if entire row is empty
            if self.is_csv:
                idx = row_num - EXCEL_HEADER_OFFSET
                if 0 <= idx < len(self.df):
                    row = self.df.iloc[idx]
                    # Check if all values in row are empty
                    all_empty = all(
                        str(val).strip() in ['', 'nan', 'null', 'none'] 
                        for val in row.values
                    )
                    if all_empty:
                        skipped_empty += 1
                        continue
            
            row_data = self.read_row_data(row_num, col_company, col_addr1, col_addr2, col_addr3)
            
            # Skip rows with no company or address
            if not (row_data['company'] or row_data['address']):
                skipped_empty += 1
                continue
            
            # Skip rows that already have phone number (already processed)
            if phone_col and self.is_csv:
                idx = row_num - EXCEL_HEADER_OFFSET
                if 0 <= idx < len(self.df) and phone_col in self.df.columns:
                    existing_phone = str(self.df.iloc[idx].get(phone_col, '')).strip()
                    if existing_phone and existing_phone.lower() not in ['null', 'nan', '', 'none']:
                        skipped_processed += 1
                        continue
            
            rows.append(row_data)
        
        if skipped_processed > 0:
            logger.info(f"Skipped {skipped_processed} rows that already have phone numbers")
        if skipped_empty > 0:
            logger.info(f"Skipped {skipped_empty} completely empty rows")
        logger.info(f"Found {len(rows)} rows to process")
        return rows
    
    def __enter__(self):
        """Context manager entry."""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
