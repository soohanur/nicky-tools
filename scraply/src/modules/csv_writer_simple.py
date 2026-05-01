"""
CSV Writer Module

Simple CSV writer for output results.
"""
import csv
from pathlib import Path
from typing import List, Dict
from ..utils.logger import setup_logger

logger = setup_logger('csv_writer')


class CSVWriter:
    """
    Simple CSV file writer.
    
    Creates output CSV with specified columns.
    """
    
    def __init__(self, file_path: Path, columns: List[str]):
        """
        Initialize CSV writer.
        
        Args:
            file_path: Path to output CSV file
            columns: List of column names
        """
        self.file_path = Path(file_path)
        self.columns = columns
        
        # Ensure output directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"CSV Writer initialized: {self.file_path}")
        logger.info(f"Columns: {columns}")
    
    def write_header(self):
        """Write header row to CSV file."""
        with open(self.file_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=self.columns)
            writer.writeheader()
        logger.info(f"Header written to {self.file_path}")
    
    def append_row(self, row: Dict[str, str]):
        """
        Append a single row to CSV file.
        
        Args:
            row: Dictionary with row data
        """
        with open(self.file_path, 'a', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=self.columns)
            writer.writerow(row)
    
    def write_all(self, rows: List[Dict[str, str]]):
        """
        Write all rows at once (overwrites file).
        
        Args:
            rows: List of dictionaries with row data
        """
        with open(self.file_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=self.columns)
            writer.writeheader()
            writer.writerows(rows)
        logger.info(f"Wrote {len(rows)} rows to {self.file_path}")
