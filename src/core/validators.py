"""
Módulo de validação para o sistema SOLID_STRUCTURE.
Implementa o princípio Single Responsibility Principle (SRP).
"""

import re
import os
from pathlib import Path
from typing import Tuple

from .models import ValidationResult, ValidationError, ConversionConfig


class FileValidator:
    """Classe responsável por validar arquivos."""
    
    def __init__(self, config: ConversionConfig = None):
        self.config = config or ConversionConfig()
    
    def validate_file_path(self, file_path: str) -> ValidationResult:
        """
        Validate file path and existence.
        
        Args:
            file_path: Path to the file to validate
            
        Returns:
            ValidationResult with validation status and any errors
        """
        errors = []
        warnings = []
        
        if not file_path:
            errors.append("Caminho do arquivo não fornecido")
            return ValidationResult(False, errors, warnings)
        
        path = Path(file_path)
        
        if not path.exists():
            errors.append(f"Arquivo não encontrado: {file_path}")
            return ValidationResult(False, errors, warnings)
        
        if not path.is_file():
            errors.append(f"Caminho não é um arquivo: {file_path}")
            return ValidationResult(False, errors, warnings)
        
        # Check file extension
        if path.suffix.lower() not in self.config.supported_extensions:
            errors.append(f"Tipo de arquivo não suportado: {path.suffix}. Suportados: {self.config.supported_extensions}")
            return ValidationResult(False, errors, warnings)
        
        # Check file size
        file_size_mb = path.stat().st_size / (1024 * 1024)
        if file_size_mb > self.config.max_file_size_mb:
            warnings.append(f"Arquivo muito grande: {file_size_mb:.1f}MB (máximo recomendado: {self.config.max_file_size_mb}MB)")
        
        return ValidationResult(len(errors) == 0, errors, warnings)


class DataFrameValidator:
    """Classe responsável por validar DataFrames."""
    
    def __init__(self, config: ConversionConfig = None):
        self.config = config or ConversionConfig()
    
    def validate_dataframe_structure(self, df) -> ValidationResult:
        """
        Validate DataFrame structure and required columns.
        
        Args:
            df: DataFrame to validate
            
        Returns:
            ValidationResult with validation status and any errors
        """
        errors = []
        warnings = []
        
        if df.empty:
            errors.append("Arquivo Excel está vazio")
            return ValidationResult(False, errors, warnings)
        
        missing_columns = [col for col in self.config.required_columns if col not in df.columns]
        
        if missing_columns:
            errors.append(f"Colunas obrigatórias ausentes: {missing_columns}")
            errors.append(f"Colunas encontradas: {list(df.columns)}")
            return ValidationResult(False, errors, warnings)
        
        # Check for completely empty columns
        for col in self.config.required_columns:
            if df[col].isna().all():
                warnings.append(f"Coluna '{col}' está completamente vazia")
        
        # Check for reasonable data volume
        if len(df) > 10000:
            warnings.append(f"Arquivo muito grande com {len(df)} linhas. Processamento pode ser lento.")
        
        return ValidationResult(len(errors) == 0, errors, warnings)


class AssemblyCodeValidator:
    """Classe responsável por validar códigos de montagem."""
    
    def validate_assembly_code(self, assembly_code: str) -> ValidationResult:
        """
        Validate assembly code format.
        
        Args:
            assembly_code: Assembly code to validate
            
        Returns:
            ValidationResult with validation status and any errors
        """
        errors = []
        warnings = []
        
        if not assembly_code:
            errors.append("Código da montagem principal é obrigatório")
            return ValidationResult(False, errors, warnings)
        
        assembly_code = str(assembly_code).strip()
        
        if len(assembly_code) < 1:
            errors.append("Código da montagem não pode estar vazio")
            return ValidationResult(False, errors, warnings)
        
        if len(assembly_code) > 50:
            warnings.append("Código da montagem muito longo (máximo recomendado: 50 caracteres)")
        
        # Allow letters, numbers, and periods
        if not re.match(r'^[A-Za-z0-9\.]+$', assembly_code):
            errors.append("Código da montagem contém caracteres inválidos. Use apenas letras, números e ponto (.)")
            return ValidationResult(False, errors, warnings)
        
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    def sanitize_assembly_code(self, text: str) -> str:
        """
        Sanitize assembly code input by keeping only letters and numbers,
        and converting to uppercase.
        
        Args:
            text: Input text to sanitize
            
        Returns:
            Sanitized text with only letters and numbers in uppercase
        """
        if not text:
            return ""
        
        # Keep only letters, numbers, and periods, convert to uppercase
        sanitized = re.sub(r'[^A-Za-z0-9\.]', '', str(text)).upper()
        return sanitized
    
    def validate_assembly_code_input(self, text: str) -> Tuple[str, bool]:
        """
        Validate and sanitize assembly code input in real-time.
        
        Args:
            text: Input text to validate
            
        Returns:
            Tuple of (sanitized_text, is_valid)
        """
        if not text:
            return "", False
        
        # Sanitize the input
        sanitized = self.sanitize_assembly_code(text)
        
        # Check if it's valid (at least 1 character)
        is_valid = len(sanitized) >= 1
        
        return sanitized, is_valid


class ValidationService:
    """Serviço principal de validação que orquestra todos os validadores."""
    
    def __init__(self, config: ConversionConfig = None):
        self.config = config or ConversionConfig()
        self.file_validator = FileValidator(self.config)
        self.dataframe_validator = DataFrameValidator(self.config)
        self.assembly_validator = AssemblyCodeValidator()
    
    def validate_conversion_request(self, input_file: str, assembly_code: str) -> ValidationResult:
        """
        Validate a complete conversion request.
        
        Args:
            input_file: Path to input file
            assembly_code: Assembly code to validate
            
        Returns:
            ValidationResult with overall validation status
        """
        errors = []
        warnings = []
        
        # Validate file
        file_validation = self.file_validator.validate_file_path(input_file)
        if not file_validation.is_valid:
            errors.extend(file_validation.errors)
        warnings.extend(file_validation.warnings)
        
        # Validate assembly code (only if provided)
        if assembly_code:
            assembly_validation = self.assembly_validator.validate_assembly_code(assembly_code)
            if not assembly_validation.is_valid:
                errors.extend(assembly_validation.errors)
            warnings.extend(assembly_validation.warnings)
        # Note: assembly_code is not always required, so we don't add error if it's empty
        
        return ValidationResult(len(errors) == 0, errors, warnings)
