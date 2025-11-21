"""
Robust Excel Parser for Analytics Dashboard
Handles messy, amateur-created spreadsheets with intelligence and grace
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import re
from difflib import SequenceMatcher
import warnings
warnings.filterwarnings('ignore')


class RobustExcelParser:
    """
    Enterprise-grade Excel parser that handles real-world messy data
    """
    
    def __init__(self, config: Dict[str, Any], debug: bool = False):
        """
        Initialize parser with configuration
        
        Args:
            config: Dashboard configuration dictionary
            debug: Enable detailed logging
        """
        self.config = config
        self.debug = debug
        self.validation_warnings = []
        self.parsing_log = []
        
        # Extract expected branches from config
        self.expected_branches = config.get('data', {}).get('branches', [])
        
        # Fuzzy matching threshold (0.0 to 1.0, higher = more strict)
        self.fuzzy_threshold = 0.75
        
    def log(self, message: str, level: str = "INFO"):
        """Log parsing activity"""
        log_entry = f"[{level}] {message}"
        self.parsing_log.append(log_entry)
        if self.debug:
            print(log_entry)
    
    def add_warning(self, warning: str):
        """Add validation warning"""
        self.validation_warnings.append(warning)
        self.log(warning, "WARNING")
    
    def fuzzy_match(self, text: str, target: str) -> float:
        """
        Calculate similarity ratio between two strings
        
        Args:
            text: Input text to match
            target: Target text to match against
            
        Returns:
            Similarity ratio (0.0 to 1.0)
        """
        # Normalize strings
        text_norm = str(text).lower().strip()
        target_norm = str(target).lower().strip()
        
        # Check exact match first
        if text_norm == target_norm:
            return 1.0
        
        # Check if target is contained in text or vice versa
        if target_norm in text_norm or text_norm in target_norm:
            return 0.9
        
        # Use sequence matcher for fuzzy comparison
        return SequenceMatcher(None, text_norm, target_norm).ratio()
    
    def find_best_match(self, text: str, candidates: List[str]) -> Optional[Tuple[str, float]]:
        """
        Find best matching candidate for given text
        
        Args:
            text: Text to match
            candidates: List of candidate strings
            
        Returns:
            Tuple of (best_match, similarity_score) or None
        """
        if not candidates or pd.isna(text):
            return None
        
        text_str = str(text).strip()
        if not text_str:
            return None
        
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            score = self.fuzzy_match(text_str, candidate)
            if score > best_score:
                best_score = score
                best_match = candidate
        
        if best_score >= self.fuzzy_threshold:
            return (best_match, best_score)
        
        return None
    
    def detect_merged_cells(self, df: pd.DataFrame, start_row: int, end_row: int) -> pd.DataFrame:
        """
        Detect and handle merged cells by forward-filling
        
        Args:
            df: DataFrame to process
            start_row: Start row index
            end_row: End row index
            
        Returns:
            DataFrame with merged cells handled
        """
        self.log(f"Checking for merged cells in rows {start_row} to {end_row}")
        
        # Forward fill to handle merged cells
        df_section = df.iloc[start_row:end_row+1].copy()
        
        # Count NaN values before
        nan_count_before = df_section.isna().sum().sum()
        
        # Forward fill along rows (axis=1) to handle horizontally merged cells
        df_section = df_section.fillna(method='ffill', axis=1)
        
        # Forward fill along columns (axis=0) to handle vertically merged cells
        df_section = df_section.fillna(method='ffill', axis=0)
        
        nan_count_after = df_section.isna().sum().sum()
        
        if nan_count_before > nan_count_after:
            self.log(f"Filled {nan_count_before - nan_count_after} merged cells")
        
        return df_section
    
    def find_header_row(self, df: pd.DataFrame, keywords: List[str], 
                       search_start: int = 0, search_end: int = 20) -> Optional[int]:
        """
        Intelligently find header row by searching for keywords
        
        Args:
            df: DataFrame to search
            keywords: List of keywords to search for (case-insensitive)
            search_start: Row to start searching from
            search_end: Row to end searching at
            
        Returns:
            Row index of header or None
        """
        self.log(f"Searching for header with keywords: {keywords}")
        
        for idx in range(search_start, min(search_end, len(df))):
            row_values = df.iloc[idx].astype(str).str.lower().str.strip()
            
            # Count how many keywords match
            matches = sum(1 for kw in keywords 
                         if any(kw.lower() in val for val in row_values))
            
            # If we find at least 2 keywords, consider it the header
            if matches >= min(2, len(keywords)):
                self.log(f"Found header row at index {idx} with {matches} keyword matches")
                return idx
        
        self.log("Could not find header row automatically", "WARNING")
        return None
    
    def detect_data_boundaries(self, df: pd.DataFrame, header_row: int, 
                              expected_cols: int = 4) -> Tuple[int, int]:
        """
        Automatically detect where data starts and ends
        
        Args:
            df: DataFrame to analyze
            header_row: Index of header row
            expected_cols: Minimum number of expected columns with data
            
        Returns:
            Tuple of (start_row, end_row)
        """
        self.log(f"Detecting data boundaries after header row {header_row}")
        
        start_row = header_row + 1
        end_row = None
        
        # Find where data ends (look for rows with too many empty cells)
        for idx in range(start_row, len(df)):
            row = df.iloc[idx]
            non_empty = row.notna().sum()
            
            # If row has fewer than expected columns with data, might be end
            if non_empty < expected_cols:
                # Check next 2 rows to confirm
                if idx + 2 < len(df):
                    next_rows_empty = all(
                        df.iloc[i].notna().sum() < expected_cols 
                        for i in range(idx, min(idx + 3, len(df)))
                    )
                    if next_rows_empty:
                        end_row = idx - 1
                        break
                else:
                    end_row = idx - 1
                    break
        
        if end_row is None:
            end_row = len(df) - 1
        
        self.log(f"Detected data boundaries: rows {start_row} to {end_row}")
        return start_row, end_row
    
    def clean_numeric_value(self, value: Any) -> float:
        """
        Clean and convert value to numeric, handling various formats
        
        Args:
            value: Value to clean
            
        Returns:
            Cleaned numeric value or NaN
        """
        if pd.isna(value):
            return np.nan
        
        # Convert to string
        val_str = str(value).strip()
        
        # Remove currency symbols and commas
        val_str = re.sub(r'[£$€,\s]', '', val_str)
        
        # Handle parentheses as negative
        if '(' in val_str and ')' in val_str:
            val_str = '-' + val_str.replace('(', '').replace(')', '')
        
        # Try to convert to float
        try:
            return float(val_str)
        except (ValueError, TypeError):
            return np.nan
    
    def remove_total_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Remove rows that contain 'Total' or 'Sum' keywords
        
        Args:
            df: DataFrame to clean
            
        Returns:
            Cleaned DataFrame
        """
        self.log("Checking for embedded total/sum rows")
        
        # Check first column for total indicators
        if len(df.columns) > 0:
            first_col = df.iloc[:, 0].astype(str).str.lower().str.strip()
            total_keywords = ['total', 'sum', 'grand total', 'subtotal', 'overall']
            
            mask = first_col.apply(
                lambda x: any(keyword in x for keyword in total_keywords)
            )
            
            removed_count = mask.sum()
            if removed_count > 0:
                self.log(f"Removed {removed_count} total/sum rows")
                df = df[~mask].copy()
        
        return df
    
    def standardize_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Standardize column names using fuzzy matching
        
        Args:
            df: DataFrame with columns to standardize
            
        Returns:
            DataFrame with standardized column names
        """
        self.log("Standardizing column names with fuzzy matching")
        
        new_columns = []
        for col in df.columns:
            col_str = str(col).strip()
            
            # Try to match against expected branches
            match_result = self.find_best_match(col_str, self.expected_branches)
            
            if match_result:
                matched_name, score = match_result
                if score < 1.0:
                    self.log(f"Fuzzy matched '{col_str}' → '{matched_name}' (score: {score:.2f})")
                new_columns.append(matched_name)
            else:
                # Keep original if no match
                self.log(f"No match found for column '{col_str}'", "WARNING")
                new_columns.append(col_str)
        
        df.columns = new_columns
        return df
    
    def remove_comment_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Remove rows that appear to be comments (mostly text, few numbers)
        
        Args:
            df: DataFrame to clean
            
        Returns:
            Cleaned DataFrame
        """
        self.log("Checking for comment rows")
        
        # Skip first column (labels), check remaining columns
        if len(df.columns) <= 1:
            return df
        
        data_cols = df.iloc[:, 1:]
        
        # Count numeric values per row
        numeric_counts = data_cols.apply(
            lambda row: sum(1 for val in row if isinstance(val, (int, float, np.number))),
            axis=1
        )
        
        # If row has fewer than 50% numeric values, might be a comment
        threshold = len(data_cols.columns) * 0.5
        comment_mask = numeric_counts < threshold
        
        removed_count = comment_mask.sum()
        if removed_count > 0:
            self.log(f"Removed {removed_count} potential comment rows")
            df = df[~comment_mask].copy()
        
        return df
    
    def parse_revenue_section(self, df_raw: pd.DataFrame, config: Dict) -> pd.DataFrame:
        """
        Parse revenue section with intelligent detection
        
        Args:
            df_raw: Raw DataFrame from Excel
            config: Configuration dictionary
            
        Returns:
            Cleaned DataFrame with revenue data
        """
        self.log("=" * 60)
        self.log("PARSING REVENUE SECTION")
        self.log("=" * 60)
        
        # Step 1: Find header row
        revenue_keywords = ['period', 'month', 'week'] + self.expected_branches
        header_row = self.find_header_row(df_raw, revenue_keywords)
        
        if header_row is None:
            # Fall back to config if provided
            header_row = config.get('data', {}).get('revenue_header_row', 0)
            self.log(f"Using config header row: {header_row}")
        
        # Step 2: Detect data boundaries
        start_row, end_row = self.detect_data_boundaries(df_raw, header_row)
        
        # Override with config if provided and seems reasonable
        config_start = config.get('data', {}).get('revenue_start_row')
        config_end = config.get('data', {}).get('revenue_end_row')
        
        if config_start is not None and config_end is not None:
            if config_end - config_start >= 2:  # Sanity check
                self.log(f"Using config boundaries: {config_start} to {config_end}")
                start_row = config_start
                end_row = config_end
        
        # Step 3: Extract and handle merged cells
        df_section = self.detect_merged_cells(df_raw, start_row, end_row)
        
        # Step 4: Set proper headers
        if header_row < start_row:
            headers = df_raw.iloc[header_row].fillna('Unnamed')
            df_section.columns = headers
        
        # Step 5: Remove total rows
        df_section = self.remove_total_rows(df_section)
        
        # Step 6: Remove comment rows
        df_section = self.remove_comment_rows(df_section)
        
        # Step 7: Standardize column names with fuzzy matching
        df_section = self.standardize_column_names(df_section)
        
        # Step 8: Clean numeric columns
        for col in df_section.columns:
            if col not in ['Period', 'Month', 'Week', 'Date']:
                df_section[col] = df_section[col].apply(self.clean_numeric_value)
        
        # Step 9: Remove rows with all NaN values
        df_section = df_section.dropna(how='all')
        
        # Step 10: Reset index
        df_section = df_section.reset_index(drop=True)
        
        self.log(f"Revenue section parsed: {len(df_section)} rows × {len(df_section.columns)} columns")
        
        return df_section
    
    def parse_costs_section(self, df_raw: pd.DataFrame, config: Dict) -> pd.DataFrame:
        """
        Parse costs section with intelligent detection
        
        Args:
            df_raw: Raw DataFrame from Excel
            config: Configuration dictionary
            
        Returns:
            Cleaned DataFrame with costs data
        """
        self.log("=" * 60)
        self.log("PARSING COSTS SECTION")
        self.log("=" * 60)
        
        # Very similar to revenue parsing
        costs_keywords = ['period', 'month', 'week', 'cost', 'expense'] + self.expected_branches
        header_row = self.find_header_row(df_raw, costs_keywords)
        
        if header_row is None:
            header_row = config.get('data', {}).get('costs_header_row', 0)
            self.log(f"Using config header row: {header_row}")
        
        start_row, end_row = self.detect_data_boundaries(df_raw, header_row)
        
        config_start = config.get('data', {}).get('costs_start_row')
        config_end = config.get('data', {}).get('costs_end_row')
        
        if config_start is not None and config_end is not None:
            if config_end - config_start >= 2:
                self.log(f"Using config boundaries: {config_start} to {config_end}")
                start_row = config_start
                end_row = config_end
        
        df_section = self.detect_merged_cells(df_raw, start_row, end_row)
        
        if header_row < start_row:
            headers = df_raw.iloc[header_row].fillna('Unnamed')
            df_section.columns = headers
        
        df_section = self.remove_total_rows(df_section)
        df_section = self.remove_comment_rows(df_section)
        df_section = self.standardize_column_names(df_section)
        
        for col in df_section.columns:
            if col not in ['Period', 'Month', 'Week', 'Date']:
                df_section[col] = df_section[col].apply(self.clean_numeric_value)
        
        df_section = df_section.dropna(how='all')
        df_section = df_section.reset_index(drop=True)
        
        self.log(f"Costs section parsed: {len(df_section)} rows × {len(df_section.columns)} columns")
        
        return df_section
    
    def parse_hours_section(self, df_raw: pd.DataFrame, config: Dict) -> Optional[pd.DataFrame]:
        """
        Parse hours section if present
        
        Args:
            df_raw: Raw DataFrame from Excel
            config: Configuration dictionary
            
        Returns:
            Cleaned DataFrame with hours data or None
        """
        self.log("=" * 60)
        self.log("PARSING HOURS SECTION (if present)")
        self.log("=" * 60)
        
        # Check if hours section is configured
        config_start = config.get('data', {}).get('hours_start_row')
        config_end = config.get('data', {}).get('hours_end_row')
        
        if config_start is None or config_end is None:
            self.log("Hours section not configured, skipping")
            return None
        
        hours_keywords = ['period', 'month', 'week', 'hour', 'hours'] + self.expected_branches
        header_row = self.find_header_row(df_raw, hours_keywords, 
                                          search_start=max(0, config_start - 5))
        
        if header_row is None:
            header_row = config.get('data', {}).get('hours_header_row', config_start - 1)
            self.log(f"Using config header row: {header_row}")
        
        start_row = config_start
        end_row = config_end
        
        df_section = self.detect_merged_cells(df_raw, start_row, end_row)
        
        if header_row < start_row:
            headers = df_raw.iloc[header_row].fillna('Unnamed')
            df_section.columns = headers
        
        df_section = self.remove_total_rows(df_section)
        df_section = self.remove_comment_rows(df_section)
        df_section = self.standardize_column_names(df_section)
        
        for col in df_section.columns:
            if col not in ['Period', 'Month', 'Week', 'Date']:
                df_section[col] = df_section[col].apply(self.clean_numeric_value)
        
        df_section = df_section.dropna(how='all')
        df_section = df_section.reset_index(drop=True)
        
        self.log(f"Hours section parsed: {len(df_section)} rows × {len(df_section.columns)} columns")
        
        return df_section
    
    def validate_dataframe(self, df: pd.DataFrame, section_name: str) -> bool:
        """
        Validate parsed DataFrame
        
        Args:
            df: DataFrame to validate
            section_name: Name of section for logging
            
        Returns:
            True if valid, False otherwise
        """
        self.log(f"Validating {section_name} section")
        
        is_valid = True
        
        # Check if DataFrame is empty
        if df is None or df.empty:
            self.add_warning(f"{section_name}: DataFrame is empty")
            return False
        
        # Check for expected branches
        missing_branches = []
        for branch in self.expected_branches:
            if branch not in df.columns:
                missing_branches.append(branch)
        
        if missing_branches:
            self.add_warning(f"{section_name}: Missing branches: {missing_branches}")
            is_valid = False
        
        # Check for data completeness
        for branch in self.expected_branches:
            if branch in df.columns:
                nan_count = df[branch].isna().sum()
                total_count = len(df[branch])
                nan_pct = (nan_count / total_count) * 100 if total_count > 0 else 0
                
                if nan_pct > 50:
                    self.add_warning(
                        f"{section_name}: Branch '{branch}' has {nan_pct:.1f}% missing data"
                    )
                elif nan_pct > 25:
                    self.log(
                        f"{section_name}: Branch '{branch}' has {nan_pct:.1f}% missing data",
                        "WARNING"
                    )
        
        return is_valid
    
    def generate_validation_report(self) -> str:
        """
        Generate human-readable validation report
        
        Returns:
            Formatted validation report
        """
        report = []
        report.append("=" * 60)
        report.append("EXCEL PARSING VALIDATION REPORT")
        report.append("=" * 60)
        
        if not self.validation_warnings:
            report.append("✅ All validations passed - data looks good!")
        else:
            report.append(f"⚠️  Found {len(self.validation_warnings)} warnings:")
            report.append("")
            for i, warning in enumerate(self.validation_warnings, 1):
                report.append(f"  {i}. {warning}")
        
        report.append("")
        report.append("=" * 60)
        report.append("PARSING LOG SUMMARY")
        report.append("=" * 60)
        
        # Show key log entries
        key_entries = [log for log in self.parsing_log 
                      if any(keyword in log for keyword in 
                            ['Found', 'Detected', 'Removed', 'Fuzzy matched'])]
        
        for entry in key_entries[-20:]:  # Last 20 key entries
            report.append(f"  {entry}")
        
        return "\n".join(report)


def load_excel_data(file_path: str, config: Dict, debug: bool = False) -> Dict[str, pd.DataFrame]:
    """
    Main function to load and parse Excel data robustly
    
    Args:
        file_path: Path to Excel file
        config: Configuration dictionary
        debug: Enable debug logging
        
    Returns:
        Dictionary with 'revenue', 'costs', 'hours', 'validation_report'
    """
    parser = RobustExcelParser(config, debug=debug)
    
    parser.log(f"Loading Excel file: {file_path}")
    
    # Load raw data
    df_raw = pd.read_excel(file_path, sheet_name=config.get('data', {}).get('revenue_sheet', 0), 
                          header=None)
    
    parser.log(f"Loaded raw data: {df_raw.shape[0]} rows × {df_raw.shape[1]} columns")
    
    # Parse sections
    revenue_df = parser.parse_revenue_section(df_raw, config)
    costs_df = parser.parse_costs_section(df_raw, config)
    hours_df = parser.parse_hours_section(df_raw, config)
    
    # Validate
    parser.validate_dataframe(revenue_df, "Revenue")
    parser.validate_dataframe(costs_df, "Costs")
    if hours_df is not None:
        parser.validate_dataframe(hours_df, "Hours")
    
    # Generate report
    validation_report = parser.generate_validation_report()
    
    if debug:
        print("\n" + validation_report)
    
    return {
        'revenue': revenue_df,
        'costs': costs_df,
        'hours': hours_df,
        'validation_report': validation_report,
        'warnings': parser.validation_warnings
    }
