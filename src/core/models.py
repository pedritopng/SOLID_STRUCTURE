"""
Modelos de dados e configurações para o sistema SOLID_STRUCTURE.
Implementa o princípio Single Responsibility Principle (SRP).
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class ConversionConfig:
    """Configuration for the conversion process."""
    required_columns: List[str] = None
    max_file_size_mb: int = 100
    supported_extensions: List[str] = None
    encoding: str = 'utf-8-sig'
    separator: str = ';'
    
    def __post_init__(self):
        if self.required_columns is None:
            self.required_columns = ['ITEM', 'QTD', 'N° DESENHO', 'CODIGO MP20']
        if self.supported_extensions is None:
            self.supported_extensions = ['.xlsx', '.xls']


@dataclass
class ValidationResult:
    """Result of validation operations."""
    is_valid: bool
    errors: List[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


@dataclass
class ProcessingStats:
    """Statistics from processing operations."""
    total_rows: int = 0
    valid_rows: int = 0
    excluded_rows: int = 0
    duplicate_rows: int = 0
    consolidated_rows: int = 0
    generated_relationships: int = 0
    warnings: List[str] = field(default_factory=list)


@dataclass
class ConversionRequest:
    """Request object for conversion operations."""
    input_file: str
    output_file: str
    assembly_code: str


@dataclass
class ConversionResult:
    """Result object for conversion operations."""
    success: bool
    message: str
    output_file: Optional[str] = None
    stats: Optional[ProcessingStats] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


class FileProcessingError(Exception):
    """Custom exception for file processing errors."""
    pass
