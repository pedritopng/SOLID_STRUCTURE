import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import os
import shutil
import re
import logging
import sys
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass
from pathlib import Path
import traceback


# Configuration and Data Classes
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


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


class FileProcessingError(Exception):
    """Custom exception for file processing errors."""
    pass


# Setup logging
def setup_logging():
    """Setup logging configuration.

    In frozen (packaged) builds, disable file logging and suppress output by
    elevating the level to CRITICAL so no log file is created.
    In development, log to stdout only.
    """
    root_logger = logging.getLogger()
    if root_logger.handlers:
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

    if getattr(sys, 'frozen', False):  # running as packaged EXE
        logging.basicConfig(level=logging.CRITICAL)
    else:  # development/run from source
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
    return logging.getLogger(__name__)


def validate_file_path(file_path: str) -> ValidationResult:
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
    config = ConversionConfig()
    if path.suffix.lower() not in config.supported_extensions:
        errors.append(f"Tipo de arquivo não suportado: {path.suffix}. Suportados: {config.supported_extensions}")
        return ValidationResult(False, errors, warnings)
    
    # Check file size
    file_size_mb = path.stat().st_size / (1024 * 1024)
    if file_size_mb > config.max_file_size_mb:
        warnings.append(f"Arquivo muito grande: {file_size_mb:.1f}MB (máximo recomendado: {config.max_file_size_mb}MB)")
    
    return ValidationResult(len(errors) == 0, errors, warnings)


def validate_dataframe_structure(df: pd.DataFrame) -> ValidationResult:
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
    
    config = ConversionConfig()
    missing_columns = [col for col in config.required_columns if col not in df.columns]
    
    if missing_columns:
        errors.append(f"Colunas obrigatórias ausentes: {missing_columns}")
        errors.append(f"Colunas encontradas: {list(df.columns)}")
        return ValidationResult(False, errors, warnings)
    
    # Check for completely empty columns
    for col in config.required_columns:
        if df[col].isna().all():
            warnings.append(f"Coluna '{col}' está completamente vazia")
    
    # Check for reasonable data volume
    if len(df) > 10000:
        warnings.append(f"Arquivo muito grande com {len(df)} linhas. Processamento pode ser lento.")
    
    return ValidationResult(len(errors) == 0, errors, warnings)


def validate_assembly_code(assembly_code: str) -> ValidationResult:
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


def sanitize_assembly_code(text: str) -> str:
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


def validate_assembly_code_input(text: str) -> Tuple[str, bool]:
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
    sanitized = sanitize_assembly_code(text)
    
    # Check if it's valid (at least 1 character)
    is_valid = len(sanitized) >= 1
    
    return sanitized, is_valid


def convert_olg_code(olg_code: Any) -> Optional[str]:
    """
    Converts OL* codes by removing "OL" prefix and cleaning up formatting.
    Examples: 
    - 'OLG12-06-1001' -> 'G12061001'
    - 'OLZ-03-058-032' -> 'Z03058032'
    - 'OLC15-02-2001' -> 'C15022001'
    - 'OLY08-11-3005' -> 'Y08113005'
    
    Args:
        olg_code: The code to convert (can be any type)
        
    Returns:
        Converted code string or None if invalid
        
    Raises:
        ValidationError: If code format is invalid
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Handle None, NaN, empty values
        if pd.isna(olg_code) or olg_code is None:
            return None
        
        # Convert to string and clean
        code_str = str(olg_code).strip()
        
        if not code_str:
            return None
        
        # Validate minimum length
        if len(code_str) < 3:
            logger.warning(f"Código muito curto para conversão: '{code_str}'")
            return code_str
        
        # Check if code starts with "OL" followed by any letter
        if code_str.startswith('OL') and len(code_str) >= 3 and code_str[2].isalpha():
            # Remove "OL" prefix, keeping the third character and rest
            converted_code = code_str[2:]  # Keep letter + numbers (e.g., "G12-06-1001")
            logger.debug(f"Convertido código OL: '{code_str}' -> '{converted_code}'")
        else:
            # If it doesn't match OL* pattern, use as is
            converted_code = code_str
            logger.debug(f"Código não-OL mantido como está: '{code_str}'")
        
        # Remove all dashes and spaces for consistency
        converted_code = converted_code.replace('-', '').replace(' ', '')
        
        # Validate result
        if not converted_code or len(converted_code) < 1:
            logger.warning(f"Código convertido vazio resultante de: '{code_str}'")
            return None
        
        # Check for reasonable length
        if len(converted_code) > 50:
            logger.warning(f"Código convertido muito longo: '{converted_code}' (original: '{code_str}')")
        
        return converted_code
        
    except Exception as e:
        logger.error(f"Erro ao converter código '{olg_code}': {str(e)}")
        raise ValidationError(f"Erro na conversão do código '{olg_code}': {str(e)}")


def parse_hierarchy_level(item_str: Any) -> int:
    """
    Parses hierarchy level from ITEM column.
    Examples: '1' -> 0, '1.0' -> 0, '2.0' -> 0, '1.1' -> 1, '2.1' -> 1, '1.1.1' -> 2
    
    Args:
        item_str: The item string to parse
        
    Returns:
        Hierarchy level (0-based) or -1 if invalid
        
    Raises:
        ValidationError: If item format is invalid
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Handle None, NaN, empty values
        if pd.isna(item_str) or item_str is None:
            return -1
        
        # Convert to string and clean
        item_str = str(item_str).strip()
        if not item_str:
            return -1
        
        # Validate basic format (should contain only numbers, dots, and spaces)
        if not re.match(r'^[0-9\.\s]+$', item_str):
            logger.warning(f"Formato de item inválido: '{item_str}' (contém caracteres não numéricos)")
            return -1
        
        # Split by dots to analyze structure
        parts = item_str.split('.')
        
        # Validate that all parts are numeric
        for part in parts:
            part_clean = part.strip()
            if part_clean and not part_clean.isdigit():
                logger.warning(f"Parte não numérica em item: '{item_str}' (parte: '{part_clean}')")
                return -1
        
        # Level 0: single number (1, 2, 3) or number.0 (1.0, 2.0, 3.0)
        if len(parts) == 1:
            level = 0  # Single number like '1', '2', '3'
        elif len(parts) == 2 and parts[1].strip() == '0':
            level = 0  # Number.0 like '1.0', '2.0', '3.0'
        else:
            # All other cases: count dots to determine level
            # Level 1: one dot (1.1, 1.2, 2.1, 2.2, etc.)
            # Level 2: two dots (1.1.1, 1.1.2, etc.)
            level = item_str.count('.')
        
        # Validate reasonable level (not too deep)
        if level > 10:
            logger.warning(f"Nível de hierarquia muito profundo: {level} para item '{item_str}'")
        
        logger.debug(f"Item '{item_str}' -> Nível {level}")
        return level
        
    except Exception as e:
        logger.error(f"Erro ao analisar nível de hierarquia para '{item_str}': {str(e)}")
        raise ValidationError(f"Erro na análise do nível de hierarquia: {str(e)}")


def detect_z_in_generated_csv(csv_file_path):
    """
    Detects if there are any 'Z' characters in column B (MTG) of the generated CSV file.
    The generated CSV has columns: EMP, MTG, COD, QTD, PER (with header)
    
    Args:
        csv_file_path: Path to the generated CSV file
        
    Returns:
        dict: Detection result with count, positions, and details
    """
    try:
        # Read the generated CSV file (with header, semicolon separated)
        df = pd.read_csv(csv_file_path, sep=';', header=0, encoding='utf-8-sig')
        
        if df.empty or df.shape[1] < 2:
            return {
                'has_z': False,
                'count': 0,
                'positions': [],
                'details': 'No data or insufficient columns in generated CSV'
            }
        
        # Column B is MTG (index 1) - columns are: 0=EMP, 1=MTG, 2=COD, 3=QTD, 4=PER
        mtg_column = df.iloc[:, 1].astype(str)  # Column B (index 1) - MTG
        z_mask = mtg_column.str.contains('Z', case=False, na=False)
        z_count = z_mask.sum()
        
        if z_count > 0:
            # Get positions and details of rows with 'Z'
            z_positions = df[z_mask].index.tolist()
            z_details = []
            
            for idx in z_positions:
                row = df.iloc[idx]
                z_details.append({
                    'row_index': idx + 2,  # +2 for human-readable row number (header is row 1)
                    'emp': row.iloc[0],  # EMP
                    'mtg': row.iloc[1],  # MTG
                    'cod': row.iloc[2],  # COD
                    'qtd': row.iloc[3],  # QTD
                    'per': row.iloc[4]   # PER
                })
            
            return {
                'has_z': True,
                'count': z_count,
                'positions': z_positions,
                'details': f"Found {z_count} entries with 'Z' in column B (MTG) of generated CSV",
                'z_entries': z_details
            }
        else:
            return {
                'has_z': False,
                'count': 0,
                'positions': [],
                'details': "No 'Z' found in column B (MTG) of generated CSV"
            }
            
    except Exception as e:
        return {
            'has_z': False,
            'count': 0,
            'positions': [],
            'details': f"Error reading generated CSV file: {str(e)}"
        }


def xlsx_to_parent_child_csv(input_file: str, output_file: str, assembly_code: str = None) -> Tuple[bool, str]:
    """
    Converts the OLG hierarchical XLSX structure to parent-child CSV format.
    Uses breadth-first ordering to match manual creation logic.
    
    Args:
        input_file: Path to input XLSX file
        output_file: Path to output CSV file
        assembly_code: Main assembly code (required)
        
    Returns:
        Tuple of (success: bool, message: str)
        
    Raises:
        FileProcessingError: If file processing fails
        ValidationError: If validation fails
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Setup logging
        setup_logging()
        
        # Validate input parameters
        file_validation = validate_file_path(input_file)
        if not file_validation.is_valid:
            error_msg = "Erro de validação do arquivo:\n" + "\n".join(file_validation.errors)
            if file_validation.warnings:
                error_msg += "\nAvisos:\n" + "\n".join(file_validation.warnings)
            logger.error(error_msg)
            return False, error_msg
        
        # Validate assembly code
        if assembly_code:
            assembly_validation = validate_assembly_code(assembly_code)
            if not assembly_validation.is_valid:
                error_msg = "Erro de validação do código de montagem:\n" + "\n".join(assembly_validation.errors)
                logger.error(error_msg)
                return False, error_msg
            if assembly_validation.warnings:
                for warning in assembly_validation.warnings:
                    logger.warning(f"Código de montagem: {warning}")
        
        # Assembly code must be provided by user
        if not assembly_code:
            error_msg = "Código da montagem principal é obrigatório. Por favor, insira o código no campo correspondente."
            logger.error(error_msg)
            return False, error_msg
        
        root_assembly_code = assembly_code.strip()
        logger.info(f"Iniciando conversão com código de montagem: {root_assembly_code}")
        
        # Read the XLSX file with error handling
        try:
            logger.info(f"Lendo arquivo: {input_file}")
            df = pd.read_excel(input_file)
            logger.info(f"Arquivo lido com sucesso. Linhas: {len(df)}, Colunas: {len(df.columns)}")
        except Exception as e:
            error_msg = f"Erro ao ler arquivo Excel: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
        
        # Validate DataFrame structure
        df_validation = validate_dataframe_structure(df)
        if not df_validation.is_valid:
            error_msg = "Erro de validação da estrutura do arquivo:\n" + "\n".join(df_validation.errors)
            logger.error(error_msg)
            return False, error_msg
        
        # Log warnings if any
        if df_validation.warnings:
            for warning in df_validation.warnings:
                logger.warning(f"Estrutura do arquivo: {warning}")
        
        logger.info("Validações concluídas com sucesso")
        
        # Parse all items and organize by hierarchy level
        items_by_level = {}  # level -> [(item, quantity, child_code, original_index)]
        item_to_code = {}    # item -> child_code
        # Counters and logs for verification & comprehensive exclusion report
        ignored_caret_rows = 0
        skipped_no_code_rows = 0
        skipped_invalid_level_rows = 0
        considered_valid_rows = 0
        exclusion_records = []  # list of dicts: reason, row_idx, ITEM, QTD, N° DESENHO, CODIGO MP20
        duplicate_records = []  # track duplicate assemblies that were consolidated
        
        # Track all original rows for comprehensive reporting
        total_original_rows = len(df)
        header_info = "Cabeçalho do arquivo XLSX (linha 1)"
        
        # Track all processed lines to find the missing 26
        all_processed_lines = []  # track every line that was processed
        consolidated_relationships = []  # track relationships that were consolidated
        individual_line_tracking = []  # track each individual line and what happened to it
        consolidated_children = []  # track children of consolidated assemblies
        
        for index, row in df.iterrows():
            item = str(row['ITEM']).strip()
            quantity = row['QTD']
            drawing_number = row['N° DESENHO']
            material_code = row['CODIGO MP20']

            # Always ignore rows where drawing number contains '^'
            if pd.notna(drawing_number) and '^' in str(drawing_number):
                ignored_caret_rows += 1
                exclusion_records.append({
                    'MOTIVO': "'^' em N° DESENHO",
                    'LINHA_XLSX': index + 2,  # +2: header is line 1, df index starts at 0
                    'ITEM': item,
                    'QTD': quantity,
                    'N° DESENHO': drawing_number,
                    'CODIGO MP20': material_code
                })
                individual_line_tracking.append({
                    'MOTIVO': 'REMOVIDA - Contém "^" em N° DESENHO',
                    'LINHA_XLSX': index + 2,
                    'ITEM': item,
                    'QTD': quantity,
                    'N° DESENHO': drawing_number,
                    'CODIGO MP20': material_code
                })
                continue
            
            # Convert drawing number to code
            child_code = convert_olg_code(drawing_number)
            if not child_code:
                skipped_no_code_rows += 1
                exclusion_records.append({
                    'MOTIVO': 'N° DESENHO inválido ou ausente (sem código convertido)',
                    'LINHA_XLSX': index + 2,
                    'ITEM': item,
                    'QTD': quantity,
                    'N° DESENHO': drawing_number,
                    'CODIGO MP20': material_code
                })
                individual_line_tracking.append({
                    'MOTIVO': 'REMOVIDA - N° DESENHO inválido',
                    'LINHA_XLSX': index + 2,
                    'ITEM': item,
                    'QTD': quantity,
                    'N° DESENHO': drawing_number,
                    'CODIGO MP20': material_code
                })
                continue
            
            # Determine hierarchy level
            level = parse_hierarchy_level(item)
            if level < 0:
                skipped_invalid_level_rows += 1
                exclusion_records.append({
                    'MOTIVO': 'ITEM inválido (nível não identificável)',
                    'LINHA_XLSX': index + 2,
                    'ITEM': item,
                    'QTD': quantity,
                    'N° DESENHO': drawing_number,
                    'CODIGO MP20': material_code
                })
                individual_line_tracking.append({
                    'MOTIVO': 'REMOVIDA - ITEM inválido (nível não identificável)',
                    'LINHA_XLSX': index + 2,
                    'ITEM': item,
                    'QTD': quantity,
                    'N° DESENHO': drawing_number,
                    'CODIGO MP20': material_code
                })
                continue
                
            # Store item information
            if level not in items_by_level:
                items_by_level[level] = []
            items_by_level[level].append((item, quantity, child_code, index))
            item_to_code[item] = child_code
            considered_valid_rows += 1
            
            # Track this as a processed line
            all_processed_lines.append({
                'line_num': index + 2,  # +2 for header
                'item': item,
                'qty': quantity,
                'code': child_code,
                'level': level
            })
            
            # Mark this line as processed (will be updated later if consolidated)
            individual_line_tracking.append({
                'MOTIVO': 'PROCESSADA - Aguardando análise de consolidação',
                'LINHA_XLSX': index + 2,
                'ITEM': item,
                'QTD': quantity,
                'N° DESENHO': child_code,
                'CODIGO MP20': f'Nível {level}'
            })
        
        # Build parent-child relationships using breadth-first approach
        output_rows = []
        # Aggregate edges to merge duplicate subassemblies by code under the same parent
        edge_to_quantity = {}  # (parent_code, child_code) -> summed quantity
        # Track a single representative item path for each parent_code to traverse children only once
        processed_parent_code_to_item = {}

        # Level 0: aggregate direct children of main assembly
        if 0 in items_by_level:
            aggregate = {}
            representative_item_for_code = {}
            code_occurrences = {}  # track which rows had each code
            
            for item, quantity, child_code, original_index in items_by_level[0]:
                if child_code not in code_occurrences:
                    code_occurrences[child_code] = []
                code_occurrences[child_code].append((item, quantity, original_index))
                aggregate[child_code] = aggregate.get(child_code, 0) + (quantity if pd.notna(quantity) else 0)
                if child_code not in representative_item_for_code:
                    representative_item_for_code[child_code] = item
                    
            for child_code, total_qty in aggregate.items():
                # If this code appeared multiple times, record ALL occurrences (including first)
                if len(code_occurrences[child_code]) > 1:
                    for i, (item, qty, orig_idx) in enumerate(code_occurrences[child_code]):
                        duplicate_records.append({
                            'MOTIVO': f'Montagem duplicada {i+1}/{len(code_occurrences[child_code])} (consolidada para qty {total_qty})',
                            'LINHA_XLSX': orig_idx + 2,
                            'ITEM': item,
                            'QTD': qty,
                            'N° DESENHO': child_code,
                            'CODIGO MP20': f'Duplicata {i+1}'
                        })
                        
                        # Update individual line tracking for duplicates
                        for tracking_line in individual_line_tracking:
                            if (tracking_line['LINHA_XLSX'] == orig_idx + 2 and 
                                tracking_line['N° DESENHO'] == child_code):
                                tracking_line['MOTIVO'] = f'CONSOLIDADA - Duplicata {i+1}/{len(code_occurrences[child_code])} (qty final: {total_qty})'
                                tracking_line['CODIGO MP20'] = f'Duplicata {i+1}'
                                break
                
                # Check if this relationship was consolidated (multiple occurrences)
                if len(code_occurrences[child_code]) > 1:
                    consolidated_relationships.append({
                        'MOTIVO': f'Relacionamento consolidado (qty final: {total_qty})',
                        'LINHA_XLSX': 'N/A',
                        'ITEM': f'Parent: {root_assembly_code}',
                        'QTD': total_qty,
                        'N° DESENHO': f'Child: {child_code}',
                        'CODIGO MP20': f'Consolidado de {len(code_occurrences[child_code])} ocorrências'
                    })
                    
                    # Track this as a consolidated assembly that will have its children consolidated
                    consolidated_children.append({
                        'parent_code': child_code,
                        'parent_item': representative_item_for_code[child_code],
                        'total_qty': total_qty,
                        'occurrences': len(code_occurrences[child_code])
                    })
                
                edge_to_quantity[(root_assembly_code, child_code)] = edge_to_quantity.get((root_assembly_code, child_code), 0) + total_qty
                processed_parent_code_to_item[child_code] = (representative_item_for_code[child_code], 0)
                # Emit in BFS order for level 0
                output_rows.append({
                    'EMP': '001',
                    'MTG': root_assembly_code,
                    'COD': child_code,
                    'QTD': total_qty,
                    'PER': 0
                })

        # Process deeper levels in breadth-first manner with aggregation and deduplication
        current_level = 1
        while current_level in items_by_level and any(level == current_level - 1 for (_, level) in processed_parent_code_to_item.values()):
            # Select parents from previous level (unique by code)
            previous_level_parents = {code: (item, level) for code, (item, level) in processed_parent_code_to_item.items() if level == current_level - 1}
            # Prepare next level parents to add (avoid reprocessing same code)
            next_level_additions = {}

            for parent_code, (parent_item, _) in previous_level_parents.items():
                # Aggregate this parent's children on this level
                child_aggregate = {}
                child_representative_item = {}
                code_occurrences = {}  # track which rows had each code for this parent
                
                for item, quantity, child_code, original_index in items_by_level[current_level]:
                    # Extract parent prefix: "1.0" -> "1", "2.0" -> "2", "1.1" -> "1.1"
                    parent_prefix = parent_item.split('.')[0] if '.' in parent_item else parent_item
                    if parent_item.endswith('.0'):
                        # For main assemblies (1.0, 2.0), children are 1.1, 1.2, 2.1, 2.2, etc.
                        parent_prefix = parent_item.split('.')[0]
                        if item.startswith(parent_prefix + '.') and not item.endswith('.0'):
                            if child_code not in code_occurrences:
                                code_occurrences[child_code] = []
                            code_occurrences[child_code].append((item, quantity, original_index))
                            child_aggregate[child_code] = child_aggregate.get(child_code, 0) + (quantity if pd.notna(quantity) else 0)
                            if child_code not in child_representative_item:
                                child_representative_item[child_code] = item
                    else:
                        # For sub-assemblies, use normal prefix matching
                        if item.startswith(parent_item + '.'):
                            if child_code not in code_occurrences:
                                code_occurrences[child_code] = []
                            code_occurrences[child_code].append((item, quantity, original_index))
                            child_aggregate[child_code] = child_aggregate.get(child_code, 0) + (quantity if pd.notna(quantity) else 0)
                            if child_code not in child_representative_item:
                                child_representative_item[child_code] = item

                # Check for duplicates and record them
                for child_code, occurrences in code_occurrences.items():
                    if len(occurrences) > 1:
                        for i, (item, qty, orig_idx) in enumerate(occurrences):
                            duplicate_records.append({
                                'MOTIVO': f'Montagem duplicada {i+1}/{len(occurrences)} (consolidada para qty {child_aggregate[child_code]})',
                                'LINHA_XLSX': orig_idx + 2,
                                'ITEM': item,
                                'QTD': qty,
                                'N° DESENHO': child_code,
                                'CODIGO MP20': f'Duplicata {i+1}'
                            })
                            
                            # Update individual line tracking for duplicates
                            for tracking_line in individual_line_tracking:
                                if (tracking_line['LINHA_XLSX'] == orig_idx + 2 and 
                                    tracking_line['N° DESENHO'] == child_code):
                                    tracking_line['MOTIVO'] = f'CONSOLIDADA - Duplicata {i+1}/{len(occurrences)} (qty final: {child_aggregate[child_code]})'
                                    tracking_line['CODIGO MP20'] = f'Duplicata {i+1}'
                                    break

                # Emit unique edges for this parent and register children as potential parents
                for child_code, total_qty in child_aggregate.items():
                    # Check if this relationship was consolidated (multiple occurrences)
                    if len(code_occurrences[child_code]) > 1:
                        consolidated_relationships.append({
                            'MOTIVO': f'Relacionamento consolidado (qty final: {total_qty})',
                            'LINHA_XLSX': 'N/A',
                            'ITEM': f'Parent: {parent_code}',
                            'QTD': total_qty,
                            'N° DESENHO': f'Child: {child_code}',
                            'CODIGO MP20': f'Consolidado de {len(code_occurrences[child_code])} ocorrências'
                        })
                        
                        # Track this as a consolidated assembly that will have its children consolidated
                        consolidated_children.append({
                            'parent_code': child_code,
                            'parent_item': child_representative_item[child_code],
                            'total_qty': total_qty,
                            'occurrences': len(code_occurrences[child_code])
                        })
                    
                    edge_to_quantity[(parent_code, child_code)] = edge_to_quantity.get((parent_code, child_code), 0) + total_qty
                    output_rows.append({
                        'EMP': '001',
                        'MTG': parent_code,
                        'COD': child_code,
                        'QTD': total_qty,
                        'PER': 0
                    })
                    if child_code not in processed_parent_code_to_item and child_code not in next_level_additions:
                        next_level_additions[child_code] = (child_representative_item[child_code], current_level)

            # Add next level unique parents
            processed_parent_code_to_item.update(next_level_additions)
            current_level += 1
        
        # Create output DataFrame
        output_df = pd.DataFrame(output_rows)
        
        # Ensure destination folder structure and move original file as requested
        try:
            input_dir = os.path.dirname(input_file)
            main_code = assembly_code or os.path.splitext(os.path.basename(output_file))[0].replace('ESTRUTURA_', '')
            folder_name = f"ESTRUTURA {main_code}"
            target_dir = os.path.join(input_dir, folder_name)
            if not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)

            # Move the original selected file into the new folder if not already inside
            input_basename = os.path.basename(input_file)
            moved_input_path = os.path.join(target_dir, input_basename)
            if os.path.abspath(os.path.dirname(input_file)) != os.path.abspath(target_dir):
                try:
                    if os.path.exists(moved_input_path):
                        os.remove(moved_input_path)
                    shutil.move(input_file, moved_input_path)
                    input_file = moved_input_path
                except Exception:
                    pass  # Do not block conversion if move fails

            # Redirect output_file to inside the target_dir
            output_file = os.path.join(target_dir, os.path.basename(output_file))
        except Exception:
            pass  # Non-fatal, continue with original paths

        # Save to CSV with semicolon separator and header row
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            # Write header row first
            f.write('EMP;MTG;COD;QTD;PER\n')
            # Write data rows without header
            output_df.to_csv(f, sep=';', index=False, header=False)
        
        # Check for "Z" in column B of the generated CSV file
        z_detection_result = detect_z_in_generated_csv(output_file)

        # Write comprehensive exclusions report CSV inside the target directory
        try:
            report_directory = os.path.dirname(output_file)
            code_for_report = os.path.splitext(os.path.basename(output_file))[0].replace('ESTRUTURA_', '')
            exclusions_report_path = os.path.join(report_directory, f"RELATORIO_REMOVIDOS_{code_for_report}.csv")
            
            # Create clean report with only what you need
            comprehensive_records = []
            
            # Add header
            comprehensive_records.append({
                'MOTIVO': 'Cabeçalho do arquivo XLSX',
                'LINHA_XLSX': 1,
                'ITEM': 'Cabeçalho',
                'QTD': 'N/A',
                'N° DESENHO': 'ITEM;QTD;N° DESENHO;CODIGO MP20',
                'CODIGO MP20': 'N/A'
            })
            
            # Add only the actual removed lines (caret)
            comprehensive_records.extend(exclusion_records)
            
            # Add the duplicate lines that were consolidated
            comprehensive_records.extend(duplicate_records)
            
            # Add consolidated relationships
            comprehensive_records.extend(consolidated_relationships)
            
            # Add consolidated children - find children of consolidated assemblies
            for consolidated in consolidated_children:
                parent_code = consolidated['parent_code']
                parent_item = consolidated['parent_item']
                total_qty = consolidated['total_qty']
                occurrences = consolidated['occurrences']
                
                # Find all children of this consolidated parent
                for level, items in items_by_level.items():
                    for item, qty, child_code, orig_idx in items:
                        if item.startswith(parent_item + '.'):
                            comprehensive_records.append({
                                'MOTIVO': f'Filho de montagem consolidada (parent qty: {total_qty})',
                                'LINHA_XLSX': orig_idx + 2,
                                'ITEM': item,
                                'QTD': qty,
                                'N° DESENHO': child_code,
                                'CODIGO MP20': f'Parent: {parent_code} ({occurrences}x)'
                            })
            
            # Add summary statistics
            actual_exclusions = len(exclusion_records) + 1  # +1 for header
            duplicate_count = len(duplicate_records)
            consolidated_count = len(consolidated_relationships)
            comprehensive_records.append({
                'MOTIVO': '=== RESUMO ESTATÍSTICO ===',
                'LINHA_XLSX': 'N/A',
                'ITEM': f'Total linhas XLSX (com cabeçalho): {total_original_rows + 1}',
                'QTD': f'Linhas de dados: {total_original_rows}',
                'N° DESENHO': f'Linhas CSV geradas: {len(output_rows)}',
                'CODIGO MP20': f'Removidas: {actual_exclusions} | Duplicatas: {duplicate_count} | Consolidadas: {consolidated_count}'
            })
            
            comprehensive_records.append({
                'MOTIVO': '=== DETALHAMENTO REMOÇÕES ===',
                'LINHA_XLSX': 'N/A',
                'ITEM': f'Ignoradas por "^": {ignored_caret_rows}',
                'QTD': f'Sem código válido: {skipped_no_code_rows}',
                'N° DESENHO': f'Nível inválido: {skipped_invalid_level_rows}',
                'CODIGO MP20': f'Válidas processadas: {considered_valid_rows}'
            })
            
            # Add detailed math breakdown
            total_input = total_original_rows + 1  # +1 for header
            total_excluded = actual_exclusions + duplicate_count
            total_output = len(output_rows)
            math_diff = total_input - total_excluded - total_output
            
            comprehensive_records.append({
                'MOTIVO': '=== ANÁLISE MATEMÁTICA ===',
                'LINHA_XLSX': 'N/A',
                'ITEM': f'Total entrada: {total_input}',
                'QTD': f'Total excluídas: {total_excluded}',
                'N° DESENHO': f'Total saída: {total_output}',
                'CODIGO MP20': f'Diferença: {math_diff}'
            })
            
            exclusions_df = pd.DataFrame(comprehensive_records, columns=['MOTIVO', 'LINHA_XLSX', 'ITEM', 'QTD', 'N° DESENHO', 'CODIGO MP20'])
            exclusions_df.to_csv(exclusions_report_path, sep=';', index=False, encoding='utf-8-sig')
        except Exception as e:
            # Non-fatal: proceed without blocking export
            pass
        
        # Verification: rows generated should equal number of unique (parent_code, child_code) edges after aggregation
        expected_csv_rows = len(edge_to_quantity)
        generated_csv_rows = len(output_rows)

        if generated_csv_rows != expected_csv_rows:
            details = (
                f"Verificação de contagem falhou. Esperado: {expected_csv_rows} linhas no CSV, "
                f"Gerado: {generated_csv_rows}.\n"
                f"Resumo: Linhas XLSX (com cabeçalho): {len(df) + 1}; "
                f"Linhas de dados XLSX: {len(df)}; Ignoradas por '^': {ignored_caret_rows}; "
                f"Sem código válido: {skipped_no_code_rows}; Nível inválido: {skipped_invalid_level_rows}."
            )
            return False, details

        # Get counts for success message
        exclusion_count = len(exclusion_records) + 1  # +1 for header
        duplicate_count = len(duplicate_records)
        consolidated_count = len(consolidated_relationships)
        
        # Add Z detection results to success message
        z_detection_info = ""
        if z_detection_result['has_z']:
            z_detection_info = f"\n\n⚠️ AVISO - DETECÇÃO DE 'Z' NO ARQUIVO CSV GERADO:\n"
            z_detection_info += f"• {z_detection_result['details']}\n"
            z_detection_info += f"• Entradas com 'Z' na coluna B (MTG): {z_detection_result['count']}\n"
            if z_detection_result['z_entries']:
                z_detection_info += f"• Detalhes das entradas:\n"
                for entry in z_detection_result['z_entries']:
                    z_detection_info += f"  - Linha {entry['row_index']}: {entry['mtg']} → {entry['cod']} (Qtd: {entry['qtd']})\n"
        else:
            z_detection_info = f"\n\n✅ VERIFICAÇÃO DE 'Z' NO ARQUIVO CSV GERADO:\n• {z_detection_result['details']}"
        
        return True, (
            f"Estrutura exportada com sucesso! {generated_csv_rows} relacionamentos processados.\n"
            f"Arquivo CSV gerado: {output_file}\n\n"
            f"Verificação OK. Linhas XLSX (com cabeçalho): {len(df) + 1}; Linhas de dados: {len(df)}; "
            f"Ignoradas por '^': {ignored_caret_rows}; Válidas esperadas: {expected_csv_rows}; "
            f"CSV geradas: {generated_csv_rows}.\n\n"
            f"📊 Resumo de Processamento:\n"
            f"• Linhas removidas: {exclusion_count} (cabeçalho + caret)\n"
            f"• Duplicatas consolidadas: {duplicate_count}\n"
            f"• Relacionamentos consolidados: {consolidated_count}\n"
            f"• Total de linhas processadas: {len(df)}\n\n"
            f"Relatório completo salvo como RELATORIO_REMOVIDOS_{code_for_report}.csv.\n"
            f"Pronto para importação no sistema NEO.{z_detection_info}"
        )
        
    except FileNotFoundError as e:
        error_msg = f"Arquivo de estrutura não encontrado: {input_file}"
        logger.error(error_msg)
        return False, error_msg
    except ValidationError as e:
        error_msg = f"Erro de validação: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
    except FileProcessingError as e:
        error_msg = f"Erro de processamento de arquivo: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
    except pd.errors.EmptyDataError:
        error_msg = "Arquivo Excel está vazio ou não contém dados válidos"
        logger.error(error_msg)
        return False, error_msg
    except pd.errors.ParserError as e:
        error_msg = f"Erro ao processar arquivo Excel: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
    except PermissionError as e:
        error_msg = f"Erro de permissão ao acessar arquivo: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
    except MemoryError:
        error_msg = "Arquivo muito grande para processar. Tente com um arquivo menor."
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Erro inesperado durante a exportação da estrutura: {str(e)}"
        logger.error(f"Erro inesperado: {traceback.format_exc()}")
        return False, error_msg


# --- GUI Application ---
class OLGConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SOLID_STRUCTURE")
        self.root.geometry("600x670")
        self.root.resizable(False, False)
        # Dark theme color scheme
        self.colors = {
            'primary': '#C40024',      # Darker red from the cube
            'secondary': '#3498DB',    # Bright blue from neo CORP sticker
            'accent': '#FF4500',       # Orange-red highlight from cube
            'success': '#E4002B',      # Red for success (brand consistency)
            'warning': '#FF4500',      # Orange-red for warnings
            'danger': '#FF6B6B',       # Lighter red for errors in dark theme
            'light': '#1A1A1A',        # Dark background
            'dark': '#E8EAED',         # Light text for dark theme
            'white': '#2D2D2D',        # Dark card background
            'gray_100': '#3A3A3A',     # Dark gray for cards
            'gray_200': '#4A4A4A',     # Dark gray borders
            'gray_300': '#5A5A5A',     # Medium dark gray
            'gray_400': '#7A7A7A',     # Medium gray
            'gray_500': '#9A9A9A',     # Light gray
            'gray_600': '#BABABA',     # Lighter gray
            'gray_700': '#DADADA',     # Very light gray
            'gray_800': '#E8EAED',     # Almost white
            'gray_900': '#FFFFFF'      # White
        }
        
        self.root.configure(bg=self.colors['light'])
        
        # Configure dark theme for ttk widgets
        self.style = ttk.Style()
        self.style.configure("DarkEntry.TEntry",
                            fieldbackground=self.colors['gray_200'],  # Dark background
                            foreground="black",                      # Black text
                            insertcolor="black",                     # Black cursor
                            borderwidth=1,
                            relief="solid")
        
        # Configure progress bar style
        self.style.configure("Dark.Horizontal.TProgressbar",
                            background=self.colors['primary'],       # Red progress bar
                            troughcolor=self.colors['gray_300'],     # Lighter background for better contrast
                            borderwidth=1,
                            lightcolor=self.colors['primary'],
                            darkcolor=self.colors['primary'])
        
        # Set window icon
        try:
            icon_path = "SOLID_STRUCTURE.ico"
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
            else:
                # Try alternative path for when running from different directory
                alt_icon_path = os.path.join(os.path.dirname(__file__), "SOLID_STRUCTURE.ico")
                if os.path.exists(alt_icon_path):
                    self.root.iconbitmap(alt_icon_path)
        except Exception as e:
            # If icon loading fails, continue without it
            print(f"Warning: Could not load icon: {e}")
        
        # Store the path of the last generated file
        self.last_generated_file = None
        # Store the selected input file
        self.selected_input_file = None
        
        # State management variables
        self.last_input_file_hash = None
        self.last_assembly_code = None
        self.conversion_completed = False
        self.current_output_file = None
        
        # Load brand logo
        self.logo_image = None
        self.load_brand_logo()
        
        # Main container with dark theme padding - centered
        main_container = tk.Frame(root, bg=self.colors['light'], padx=30, pady=20)
        main_container.pack(expand=True, fill='both')
        
        # Center the main content
        center_frame = tk.Frame(main_container, bg=self.colors['light'])
        center_frame.pack(expand=True, fill='both')
        
        # Main content frame with dark theme border - centered
        main_frame = tk.Frame(center_frame, bg=self.colors['gray_100'], relief="raised", bd=2, padx=25, pady=20)
        main_frame.pack(expand=False, fill='both', anchor='center')
        
        # Header section - dark theme - centered
        header_frame = tk.Frame(main_frame, bg=self.colors['gray_100'])
        header_frame.pack(fill='x', pady=(0, 15))
        
        # Center all header content
        header_center = tk.Frame(header_frame, bg=self.colors['gray_100'])
        header_center.pack(expand=True, fill='x')
        
        # Logo above title - dark theme - centered
        if self.logo_image:
            logo_label = tk.Label(header_center, image=self.logo_image, bg=self.colors['gray_100'])
            logo_label.pack(pady=(0, 10))
        
        # Title - dark theme - centered
        title_label = tk.Label(header_center, 
                              text="SOLID_STRUCTURE", 
                              font=("Arial", 18, "bold"),
                              fg=self.colors['primary'],
                              bg=self.colors['gray_100'])
        title_label.pack(pady=(0, 5))
        
        # File selection section - dark theme - centered
        file_section_frame = tk.Frame(main_frame, bg=self.colors['gray_100'])
        file_section_frame.pack(fill='x', pady=(10, 15))
        
        # Center the file section
        file_center = tk.Frame(file_section_frame, bg=self.colors['gray_100'])
        file_center.pack(expand=True, fill='x')
        
        # File section with dark theme border - centered
        file_container = tk.Frame(file_center, bg=self.colors['gray_100'], relief="groove", bd=1, padx=15, pady=10)
        file_container.pack(fill='x')
        
        tk.Label(file_container, 
                text="📁 Arquivo de Estrutura de Montagem (XLSX)", 
                font=("Arial", 11, "bold"),
                fg=self.colors['primary'],
                bg=self.colors['gray_100']).pack(anchor="center", pady=(0, 10))
        
        # Center both file field and button
        file_center = tk.Frame(file_container, bg=self.colors['gray_100'])
        file_center.pack(expand=True, fill='x')
        
        # File input frame - centered
        file_input_frame = tk.Frame(file_center, bg=self.colors['gray_100'])
        file_input_frame.pack(anchor='center', pady=(0, 10))
        
        self.file_path_entry = ttk.Entry(file_input_frame, 
                                        font=("Arial", 11), 
                                        state="readonly", 
                                        style="DarkEntry.TEntry")
        self.file_path_entry.pack(ipady=4, ipadx=50)
        
        # Button frame - centered below field
        button_frame = tk.Frame(file_center, bg=self.colors['gray_100'])
        button_frame.pack(anchor='center')
        
        self.browse_button = tk.Button(button_frame, 
                                      text="📂 Procurar...", 
                                      command=self.browse_file,
                                      font=("Arial", 11),
                                      bg=self.colors['secondary'], 
                                      fg=self.colors['gray_900'],
                                      relief="solid",
                                      bd=1,
                                      padx=15, 
                                      pady=4,
                                      cursor="hand2")
        self.browse_button.pack()
        
        # Add hover effects to browse button - dark theme
        def on_browse_enter(e):
            self.browse_button.config(bg=self.colors['primary'])
        def on_browse_leave(e):
            self.browse_button.config(bg=self.colors['secondary'])
        
        self.browse_button.bind("<Enter>", on_browse_enter)
        self.browse_button.bind("<Leave>", on_browse_leave)
        
        # Configuration section - dark theme - centered
        config_section_frame = tk.Frame(main_frame, bg=self.colors['gray_100'])
        config_section_frame.pack(fill='x', pady=(0, 15))
        
        # Center the configuration section
        config_center = tk.Frame(config_section_frame, bg=self.colors['gray_100'])
        config_center.pack(expand=True, fill='x')
        
        # Configuration container with dark theme border - centered
        config_container = tk.Frame(config_center, bg=self.colors['gray_100'], relief="groove", bd=1, padx=15, pady=10)
        config_container.pack(fill='x')
        
        tk.Label(config_container, 
                text="⚙️ Código da montagem principal", 
                font=("Arial", 11, "bold"),
                fg=self.colors['primary'],
                bg=self.colors['gray_100']).pack(anchor="center", pady=(0, 15))
        
        # Assembly code section - dark theme - centered
        assembly_frame = tk.Frame(config_container, bg=self.colors['gray_100'])
        assembly_frame.pack(fill='x', pady=(0, 12))
        
        # Center the assembly code section
        assembly_center = tk.Frame(assembly_frame, bg=self.colors['gray_100'])
        assembly_center.pack(expand=True, fill='x')

        assembly_input_frame = tk.Frame(assembly_center, bg=self.colors['gray_100'])
        assembly_input_frame.pack(anchor="center")
        
        self.assembly_code_entry = ttk.Entry(assembly_input_frame, 
                                            font=("Arial", 11),
                                            style="DarkEntry.TEntry")
        self.assembly_code_entry.pack(ipady=4, ipadx=5)
        
        # Add real-time validation for assembly code
        self.assembly_code_entry.bind('<KeyRelease>', self.on_assembly_code_change)
        self.assembly_code_entry.bind('<FocusOut>', self.on_assembly_code_focus_out)
        
        # Store validation state
        self.assembly_code_valid = False
        # Buttons section - dark theme - centered
        buttons_section_frame = tk.Frame(main_frame, bg=self.colors['gray_100'])
        buttons_section_frame.pack(fill='x', pady=(10, 10))
        
        # Center the buttons container - dark theme
        buttons_center = tk.Frame(buttons_section_frame, bg=self.colors['gray_100'])
        buttons_center.pack(expand=True, fill='x')
        
        buttons_frame = tk.Frame(buttons_center, bg=self.colors['gray_100'])
        buttons_frame.pack(anchor='center')
        
        # Convert button - dark theme
        self.convert_button = tk.Button(buttons_frame, 
                                       text="🚀 Exportar Estrutura", 
                                       command=self.run_conversion,
                                       font=("Arial", 12, "bold"),
                                       bg=self.colors['primary'], 
                                       fg=self.colors['gray_900'],
                                       relief="flat",
                                       padx=25, 
                                       pady=12,
                                       state=tk.DISABLED,
                                       cursor="hand2")
        self.convert_button.pack(side=tk.LEFT, padx=(0, 15))
        
        # Open file button - dark theme
        self.open_file_button = tk.Button(buttons_frame, 
                                         text="📄 Abrir CSV Gerado", 
                                         command=self.open_generated_file,
                                         font=("Arial", 12, "bold"),
                                         bg=self.colors['secondary'], 
                                         fg=self.colors['gray_900'],
                                         relief="flat",
                                         padx=25, 
                                         pady=12,
                                         state=tk.DISABLED,
                                         cursor="hand2")
        self.open_file_button.pack(side=tk.LEFT)
        
        # Add hover effects to buttons - dark theme
        def on_convert_enter(e):
            if self.convert_button['state'] == 'normal':
                self.convert_button.config(bg=self.colors['secondary'])
        def on_convert_leave(e):
            if self.convert_button['state'] == 'normal':
                self.convert_button.config(bg=self.colors['primary'])
        
        def on_open_enter(e):
            if self.open_file_button['state'] == 'normal':
                self.open_file_button.config(bg=self.colors['primary'])
        def on_open_leave(e):
            if self.open_file_button['state'] == 'normal':
                self.open_file_button.config(bg=self.colors['secondary'])
        
        self.convert_button.bind("<Enter>", on_convert_enter)
        self.convert_button.bind("<Leave>", on_convert_leave)
        self.open_file_button.bind("<Enter>", on_open_enter)
        self.open_file_button.bind("<Leave>", on_open_leave)
        
        # Progress bar section - dark theme - centered
        progress_section_frame = tk.Frame(main_frame, bg=self.colors['gray_100'])
        progress_section_frame.pack(fill='x', pady=(5, 5))
        
        # Center the progress section
        progress_center = tk.Frame(progress_section_frame, bg=self.colors['gray_100'])
        progress_center.pack(expand=True, fill='x')
        
        # Progress container - dark theme - centered
        progress_container = tk.Frame(progress_center, bg=self.colors['gray_100'], relief="groove", bd=1, padx=15, pady=8)
        progress_container.pack(fill='x')
        
        # Progress bar label
        self.progress_label = tk.Label(progress_container, 
                                     text="📊 Progresso", 
                                     font=("Arial", 10, "bold"),
                                     fg=self.colors['primary'],
                                     bg=self.colors['gray_100'])
        self.progress_label.pack(anchor="center", pady=(0, 5))
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(progress_container, 
                                          mode='determinate',
                                          length=400,
                                          style="Dark.Horizontal.TProgressbar")
        self.progress_bar.pack(anchor="center", pady=(0, 5))
        
        # Set initial value to make progress bar visible
        self.progress_bar['value'] = 0
        self.progress_bar['maximum'] = 100
        
        # Add status indicator
        self.add_status_indicator()
        
        # Start periodic file checking
        self.root.after(2000, self.schedule_file_check)
    
    def load_brand_logo(self):
        """Load the brand logo from PNG file."""
        try:
            logo_path = "SOLID_STRUCTURE.png"
            if not os.path.exists(logo_path):
                logo_path = os.path.join(os.path.dirname(__file__), "SOLID_STRUCTURE.png")
            
            if os.path.exists(logo_path):
                # Load and resize the logo
                image = Image.open(logo_path)
                # Resize to appropriate size for the header
                image = image.resize((80, 80), Image.Resampling.LANCZOS)
                self.logo_image = ImageTk.PhotoImage(image)
            else:
                print("Warning: SOLID_STRUCTURE.png not found")
        except Exception as e:
            print(f"Warning: Could not load logo: {e}")
    
    def calculate_file_hash(self, file_path: str) -> Optional[str]:
        """
        Calculate hash of a file to detect changes.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Hash string or None if file doesn't exist
        """
        try:
            import hashlib
            
            if not os.path.exists(file_path):
                return None
            
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            print(f"Error calculating file hash: {e}")
            return None
    
    def check_for_changes(self) -> bool:
        """
        Check if input file or assembly code has changed since last conversion.
        
        Returns:
            True if changes detected, False otherwise
        """
        try:
            # Check if input file changed
            if self.selected_input_file:
                current_file_hash = self.calculate_file_hash(self.selected_input_file)
                if current_file_hash != self.last_input_file_hash:
                    return True
            
            # Check if assembly code changed
            current_assembly_code = self.assembly_code_entry.get().strip()
            if current_assembly_code != self.last_assembly_code:
                return True
            
            return False
            
        except Exception as e:
            print(f"Error checking for changes: {e}")
            return True  # Assume changes if error
    
    def reset_conversion_state(self):
        """Reset the conversion state when changes are detected."""
        try:
            # Reset state variables
            self.conversion_completed = False
            self.current_output_file = None
            
            # Disable buttons
            self.open_file_button.config(state=tk.DISABLED)
            self.convert_button.config(state=tk.DISABLED)
            
            # Update progress bar
            self.progress_bar['value'] = 0
            self.progress_label.config(text="📊 Progresso")
            
            # Preserve last generated file reference so the Open button keeps working
            # Update status indicator
            if self.selected_input_file:
                self.update_status_indicator("⚠️ Mudanças detectadas - estado resetado", self.colors['warning'])
            else:
                self.update_status_indicator("📋 Aguardando seleção de arquivo")
            
            # Silenced status print to keep console clean
            
        except Exception as e:
            print(f"Error resetting conversion state: {e}")
    
    def update_state_tracking(self):
        """Update the state tracking variables."""
        try:
            # Update file hash if file is selected
            if self.selected_input_file:
                self.last_input_file_hash = self.calculate_file_hash(self.selected_input_file)
            
            # Update assembly code
            self.last_assembly_code = self.assembly_code_entry.get().strip()
            
        except Exception as e:
            print(f"Error updating state tracking: {e}")
    
    def on_assembly_code_change(self, event):
        """Handle real-time changes in assembly code field."""
        try:
            # Get current text
            current_text = self.assembly_code_entry.get()
            
            # Sanitize the input
            sanitized_text, is_valid = validate_assembly_code_input(current_text)
            
            # Update the field if text was changed
            if sanitized_text != current_text:
                # Store cursor position
                cursor_pos = self.assembly_code_entry.index(tk.INSERT)
                
                # Update the text
                self.assembly_code_entry.delete(0, tk.END)
                self.assembly_code_entry.insert(0, sanitized_text)
                
                # Restore cursor position (adjusted for length change)
                new_cursor_pos = min(cursor_pos, len(sanitized_text))
                self.assembly_code_entry.icursor(new_cursor_pos)
            
            # Update validation state (always true now)
            self.assembly_code_valid = True
            
            # Update field appearance based on validation
            self.update_assembly_code_appearance()
            
            # Update convert button state based on current inputs
            self.update_convert_button_state()
            
            # Do not reset conversion state while typing; just track changes
            self.update_state_tracking()
            
        except Exception as e:
            print(f"Error in assembly code validation: {e}")
    
    def on_assembly_code_focus_out(self, event):
        """Handle focus out event for assembly code field."""
        try:
            # Final validation and cleanup
            current_text = self.assembly_code_entry.get()
            sanitized_text, is_valid = validate_assembly_code_input(current_text)
            
            if sanitized_text != current_text:
                self.assembly_code_entry.delete(0, tk.END)
                self.assembly_code_entry.insert(0, sanitized_text)
            
            self.assembly_code_valid = True
            self.update_assembly_code_appearance()
            
            # Update convert button state
            self.update_convert_button_state()
            # Track new value
            self.update_state_tracking()
            
        except Exception as e:
            print(f"Error in assembly code focus out: {e}")
    
    def update_assembly_code_appearance(self):
        """Update the visual appearance of the assembly code field based on validation."""
        try:
            current_text = self.assembly_code_entry.get()
            
            if not current_text:
                # Empty field - normal appearance
                self.assembly_code_entry.configure(style="DarkEntry.TEntry")
            elif self.assembly_code_valid:
                # Valid field - green border
                self.style.configure("ValidEntry.TEntry",
                                   fieldbackground=self.colors['gray_200'],
                                   foreground="black",
                                   insertcolor="black",
                                   borderwidth=2,
                                   relief="solid",
                                   bordercolor="#28a745")  # Green border
                self.assembly_code_entry.configure(style="ValidEntry.TEntry")
            else:
                # Invalid field - red border
                self.style.configure("InvalidEntry.TEntry",
                                   fieldbackground=self.colors['gray_200'],
                                   foreground="black",
                                   insertcolor="black",
                                   borderwidth=2,
                                   relief="solid",
                                   bordercolor="#dc3545")  # Red border
                self.assembly_code_entry.configure(style="InvalidEntry.TEntry")
                
        except Exception as e:
            print(f"Error updating assembly code appearance: {e}")
    
    def update_convert_button_state(self):
        """Update the convert button state based on current conditions."""
        try:
            # Button should be enabled only if:
            # 1. A file is selected
            # 2. Assembly code field is not empty
            # 3. Conversion is not completed (or state was reset)
            
            file_selected = bool(self.selected_input_file and os.path.exists(self.selected_input_file))
            code_not_empty = bool(self.assembly_code_entry.get().strip())
            not_completed = not self.conversion_completed
            
            should_enable = file_selected and code_not_empty and not_completed
            
            if should_enable:
                self.convert_button.config(state=tk.NORMAL)
            else:
                self.convert_button.config(state=tk.DISABLED)
                
        except Exception as e:
            print(f"Error updating convert button state: {e}")
    
    def add_status_indicator(self):
        """Add a status indicator to show current state."""
        try:
            # Status indicator frame
            status_frame = tk.Frame(self.main_frame, bg=self.colors['gray_100'])
            status_frame.pack(fill='x', pady=(5, 0))
            
            # Status label
            self.status_label = tk.Label(status_frame, 
                                       text="📋 Aguardando seleção de arquivo",
                                       font=("Arial", 9),
                                       fg=self.colors['gray_600'],
                                       bg=self.colors['gray_100'])
            self.status_label.pack(anchor="center")
            
        except Exception:
            pass
    
    def update_status_indicator(self, message: str, color: str = None):
        """Update the status indicator message and color."""
        try:
            if hasattr(self, 'status_label'):
                self.status_label.config(text=message)
                if color:
                    self.status_label.config(fg=color)
                else:
                    self.status_label.config(fg=self.colors['gray_600'])
        except Exception as e:
            print(f"Error updating status indicator: {e}")
    
    def schedule_file_check(self):
        """Schedule periodic file change checks."""
        try:
            # Only update button state periodically; avoid auto-resetting while user is typing
            self.update_convert_button_state()
            # Schedule next check
            self.root.after(2000, self.schedule_file_check)
            
        except Exception:
            # Still schedule next check even if this one failed
            self.root.after(2000, self.schedule_file_check)
    
    def browse_file(self):
        """Abre o diálogo para selecionar o arquivo de estrutura de montagem."""
        try:
            input_file = filedialog.askopenfilename(
                title="Selecionar Arquivo de Estrutura de Montagem",
                filetypes=[
                    ("Arquivos Excel", "*.xlsx *.xls"),
                    ("Todos os arquivos", "*.*")
                ]
            )
            
            if input_file:
                # Validate the selected file
                validation_result = validate_file_path(input_file)
                
                if not validation_result.is_valid:
                    error_msg = "Arquivo inválido:\n" + "\n".join(validation_result.errors)
                    messagebox.showerror("Arquivo Inválido", error_msg)
                    return
                
                # Show warnings if any
                if validation_result.warnings:
                    warning_msg = "Avisos sobre o arquivo selecionado:\n" + "\n".join(validation_result.warnings)
                    messagebox.showwarning("Avisos", warning_msg)
                
                # Check if this is a different file than before
                if input_file != self.selected_input_file:
                    # Reset conversion state when file changes
                    self.reset_conversion_state()
                
                self.selected_input_file = input_file
                # Show only filename in the entry for better UX
                filename = os.path.basename(input_file)
                
                # Update the entry field
                self.file_path_entry.config(state="normal")
                self.file_path_entry.delete(0, tk.END)
                self.file_path_entry.insert(0, filename)
                self.file_path_entry.config(state="readonly")
                
                # Update convert button state based on current conditions
                self.update_convert_button_state()
                
                # Update state tracking
                self.update_state_tracking()
                
                # Update status indicator
                if self.assembly_code_entry.get().strip():
                    self.update_status_indicator("✅ Arquivo selecionado - pronto para conversão", self.colors['success'])
                else:
                    self.update_status_indicator("⚠️ Arquivo selecionado - insira código da montagem", self.colors['warning'])
                
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao selecionar arquivo: {str(e)}")
    
    def open_generated_file(self):
        """Abre o último arquivo CSV gerado com a aplicação padrão."""
        try:
            candidate = None
            # Prefer explicitly tracked last generated file
            if getattr(self, 'last_generated_file', None) and os.path.exists(self.last_generated_file):
                candidate = self.last_generated_file
            else:
                # Fallback: search for newest generated ESTRUTURA_*.csv near input file or working dir
                search_dirs = []
                if getattr(self, 'selected_input_file', None):
                    base_dir = os.path.dirname(self.selected_input_file)
                    # Include potential structured folder "ESTRUTURA <code>"
                    try:
                        for name in os.listdir(base_dir):
                            if name.upper().startswith("ESTRUTURA "):
                                path = os.path.join(base_dir, name)
                                if os.path.isdir(path):
                                    search_dirs.append(path)
                    except Exception:
                        pass
                    search_dirs.append(base_dir)
                # Also add current working directory as last resort
                search_dirs.append(os.getcwd())
                newest_time = -1
                for d in search_dirs:
                    try:
                        for fname in os.listdir(d):
                            if fname.upper().startswith("ESTRUTURA_") and fname.lower().endswith(".csv"):
                                fpath = os.path.join(d, fname)
                                mtime = os.path.getmtime(fpath)
                                if mtime > newest_time:
                                    newest_time = mtime
                                    candidate = fpath
                    except Exception:
                        continue
            if candidate and os.path.exists(candidate):
                os.startfile(candidate)
                # Update reference for future opens
                self.last_generated_file = candidate
                self.open_file_button.config(state=tk.NORMAL)
            else:
                messagebox.showwarning("Aviso", "Nenhum arquivo gerado encontrado.")
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível abrir o arquivo:\n{str(e)}")
    
    def run_conversion(self):
        """Start the conversion process with progress simulation"""
        try:
            # Check if file is selected
            if not self.selected_input_file:
                messagebox.showwarning("Arquivo Necessário", "Por favor, selecione uma estrutura de montagem primeiro usando 'Procurar...'.")
                return
            
            # Validate file still exists
            if not os.path.exists(self.selected_input_file):
                messagebox.showerror("Arquivo Não Encontrado", f"O arquivo selecionado não foi encontrado:\n{self.selected_input_file}\n\nPor favor, selecione um novo arquivo.")
                self.selected_input_file = None
                self.file_path_entry.config(state="normal")
                self.file_path_entry.delete(0, tk.END)
                self.file_path_entry.config(state="readonly")
                self.convert_button.config(state=tk.DISABLED)
                return
            
            input_file = self.selected_input_file
            
            # Get assembly code from user input (required)
            assembly_code = self.assembly_code_entry.get().strip()
            
            # Check if field is empty
            if not assembly_code:
                messagebox.showerror("Campo Obrigatório", "O código da montagem principal é obrigatório. Por favor, insira o código no campo correspondente.")
                self.assembly_code_entry.focus()
                return
            
            # Basic validation - just check if field is not empty
            if not assembly_code.strip():
                messagebox.showerror("Campo Obrigatório", "O código da montagem principal é obrigatório.")
                self.assembly_code_entry.focus()
                return
            
            # Skip validation - just proceed with whatever the user entered
            
            code_for_filename = assembly_code
            
            # Validate output directory is writable
            directory, _ = os.path.split(input_file)
            try:
                # Test if directory is writable
                test_file = os.path.join(directory, "test_write.tmp")
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
            except Exception as e:
                messagebox.showerror("Erro de Permissão", f"Não é possível escrever no diretório:\n{directory}\n\nErro: {str(e)}")
                return
            
            # Generate output filename with ESTRUTURA format (initial path; may be redirected into folder later)
            output_file = os.path.join(directory, f"ESTRUTURA_{code_for_filename}.csv")
            
            # Check if output file already exists
            if os.path.exists(output_file):
                response = messagebox.askyesno("Arquivo Existente", f"O arquivo de saída já existe:\n{os.path.basename(output_file)}\n\nDeseja sobrescrever?")
                if not response:
                    return
            
            # Check for changes before starting conversion
            if self.check_for_changes():
                self.reset_conversion_state()
            
            # Start progress simulation
            self.start_progress_simulation(input_file, output_file, assembly_code)
            
        except Exception as e:
            messagebox.showerror("Erro", f"Erro inesperado: {str(e)}")
    
    def start_progress_simulation(self, input_file, output_file, assembly_code):
        """Start realistic progress simulation based on file size"""
        import threading
        import time
        
        # Disable convert button during processing
        self.convert_button.config(state=tk.DISABLED)
        
        # Get file line count for realistic timing
        try:
            df = pd.read_excel(input_file)
            line_count = len(df)
            # Calculate time: lines/100 seconds, minimum 2 seconds, maximum 10 seconds
            processing_time = max(2, min(10, line_count / 100))
        except:
            line_count = 100
            processing_time = 3
        
        # Reset progress bar
        self.progress_bar['value'] = 0
        self.progress_bar['maximum'] = 100
        
        # Start progress simulation in separate thread
        progress_thread = threading.Thread(target=self.simulate_progress, 
                                         args=(processing_time, input_file, output_file, assembly_code))
        progress_thread.daemon = True
        progress_thread.start()
    
    def simulate_progress(self, processing_time, input_file, output_file, assembly_code):
        """Simulate realistic progress with status updates"""
        import time
        
        # Progress stages with realistic descriptions
        stages = [
            ("Lendo arquivo XLSX...", 10),
            ("Validando estrutura de dados...", 20),
            ("Processando hierarquia...", 40),
            ("Convertendo códigos...", 60),
            ("Gerando relacionamentos...", 80),
            ("Salvando arquivo CSV...", 95),
            ("Finalizando...", 100)
        ]
        
        current_stage = 0
        start_time = time.time()
        
        while current_stage < len(stages):
            stage_text, target_progress = stages[current_stage]
            
            # Update status
            self.progress_label.config(text=stage_text)
            self.root.update()
            
            # Calculate time for this stage
            stage_duration = processing_time * (target_progress - (stages[current_stage-1][1] if current_stage > 0 else 0)) / 100
            
            # Animate progress for this stage
            start_progress = stages[current_stage-1][1] if current_stage > 0 else 0
            steps = 10
            step_duration = stage_duration / steps
            step_size = (target_progress - start_progress) / steps
            
            for i in range(steps):
                if time.time() - start_time >= processing_time:
                    break
                    
                self.progress_bar['value'] = start_progress + (i + 1) * step_size
                self.root.update()
                time.sleep(step_duration)
            
            current_stage += 1
        
        # Perform actual conversion
        self.progress_label.config(text="Processando conversão...")
        self.root.update()
        
        success, message = xlsx_to_parent_child_csv(input_file, output_file, assembly_code)
        
        # Complete progress bar
        self.progress_bar['value'] = 100
        self.progress_label.config(text="Processamento concluído!")
        self.root.update()
        
        # Re-enable convert button
        self.convert_button.config(state=tk.NORMAL)
        
        # Show result
        self.show_conversion_result(success, message, output_file, assembly_code)
    
    def show_conversion_result(self, success, message, output_file, assembly_code):
        """Show the conversion result after progress is complete"""
        if success:
            # Store the generated file path and enable the open button
            self.last_generated_file = output_file
            self.open_file_button.config(state=tk.NORMAL)
            
            # Update conversion state
            self.conversion_completed = True
            self.current_output_file = output_file
            
            # Disable convert button after successful conversion
            self.convert_button.config(state=tk.DISABLED)
            
            # Update state tracking after successful conversion
            self.update_state_tracking()
            
            # Update status indicator
            self.update_status_indicator("✅ Conversão concluída com sucesso!", self.colors['success'])
            
            # Check if Z was detected and show warning
            has_z_warning = "⚠️ AVISO - DETECÇÃO DE 'Z'" in message
            
            # Create a more comprehensive success message
            # Extract Z detection info from the message if present
            z_info_section = ""
            if "⚠️ AVISO - DETECÇÃO DE 'Z'" in message:
                z_start = message.find("⚠️ AVISO - DETECÇÃO DE 'Z'")
                z_info_section = f"\n\n{message[z_start:]}"
            elif "✅ VERIFICAÇÃO DE 'Z'" in message:
                z_start = message.find("✅ VERIFICAÇÃO DE 'Z'")
                z_info_section = f"\n\n{message[z_start:]}"
            
            # Get filename for display
            filename = os.path.basename(output_file)
            code_for_filename = assembly_code
            
            detailed_message = f"""✅ EXPORTAÇÃO CONCLUÍDA COM SUCESSO!

📁 Arquivo CSV gerado:
{filename}

📊 Estatísticas da Conversão:
{message.split('Verificação OK.')[1].split('Pronto para importação')[0].strip()}

📋 Arquivos Criados:
• ESTRUTURA_{code_for_filename}.csv (estrutura principal)
• RELATORIO_REMOVIDOS_{code_for_filename}.csv (relatório de exclusões)

🚀 Próximos Passos:
1. Use 'Abrir CSV Gerado' para visualizar a estrutura
2. Verifique o relatório de removidos se necessário
3. Importe o CSV no sistema NEO

✨ A estrutura está pronta para importação no sistema NEO!{z_info_section}"""
            
            # Show success message
            messagebox.showinfo("Exportação Concluída", detailed_message)
            
            # Show separate warning if Z was detected
            if has_z_warning:
                z_warning_message = f"""⚠️ AVISO - DETECÇÃO DE 'Z' NO ARQUIVO CSV GERADO!

{z_info_section.split('⚠️ AVISO - DETECÇÃO DE \'Z\' NO ARQUIVO CSV GERADO:')[1].strip()}

🔍 AÇÃO RECOMENDADA:
• Verifique as entradas listadas acima
• Confirme se os códigos com 'Z' estão corretos
• Revise a estrutura antes da importação no NEO

⚠️ Este aviso não impede a exportação, mas requer atenção!"""
                
                messagebox.showwarning("⚠️ AVISO - Detecção de 'Z'", z_warning_message)
            
            pass  # Success handled by messagebox
        else:
            messagebox.showerror("Erro na Exportação", message)


if __name__ == "__main__":
    try:
        # Setup logging first
        logger = setup_logging()
        logger.info("Iniciando aplicação SOLID_STRUCTURE")
        
        # Initialize GUI
        root = tk.Tk()
        app = OLGConverterApp(root)
        
        logger.info("Interface gráfica inicializada com sucesso")
        root.mainloop()
        
    except Exception as e:
        print(f"Erro crítico ao iniciar aplicação: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)
