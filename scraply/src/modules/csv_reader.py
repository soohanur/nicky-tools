"""
CSV Reader Module

Simple CSV reader that reads all rows as dictionaries.
"""
import csv
from pathlib import Path
from typing import List, Dict
from ..utils.logger import setup_logger

logger = setup_logger('csv_reader')


# Constants
SUPPORTED_CSV_ENCODINGS = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252', 'iso-8859-1']


class CSVReader:
    """
    Simple CSV file reader.
    
    Reads CSV files and returns all rows as dictionaries.
    """
    
    def __init__(self, file_path: Path):
        """
        Initialize CSV reader.
        
        Args:
            file_path: Path to CSV file
        """
        self.file_path = Path(file_path)
        
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")
        
        logger.info(f"CSV file loaded: {self.file_path}")
    
    def read_all(self) -> List[Dict[str, str]]:
        """
        Read all rows from CSV file.
        
        Returns:
            List of dictionaries, one per row (with stripped column names)
        """
        for encoding in SUPPORTED_CSV_ENCODINGS:
            try:
                with open(self.file_path, 'r', encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    # Strip whitespace from column names and rebuild rows
                    rows = []
                    for row in reader:
                        cleaned_row = {key.strip(): value for key, value in row.items() if key}
                        rows.append(cleaned_row)
                    logger.info(f"Read {len(rows)} rows from CSV with encoding: {encoding}")
                    return rows
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.error(f"Error reading CSV with {encoding}: {e}")
                continue
        
        raise ValueError(f"Could not read {self.file_path} with any supported encoding")
    
    def read_all_with_row_numbers(self) -> List[Dict[str, str]]:
        """
        Read all rows with row numbers added.
        
        Returns:
            List of dictionaries with 'row_number' field added
        """
        rows = self.read_all()
        for idx, row in enumerate(rows, 2):  # Start at 2 (after header)
            row['row_number'] = idx
        return rows
