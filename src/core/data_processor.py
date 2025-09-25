"""
Módulo de processamento de dados para o sistema SOLID_STRUCTURE.
Implementa o princípio Single Responsibility Principle (SRP).
"""

import re
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
import logging

from .models import ProcessingStats, ValidationError


class OLGCodeConverter:
    """Classe responsável por converter códigos OL*."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def convert_olg_code(self, olg_code: Any) -> Optional[str]:
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
                self.logger.warning(f"Código muito curto para conversão: '{code_str}'")
                return code_str
            
            # Check if code starts with "OL" followed by any letter
            if code_str.startswith('OL') and len(code_str) >= 3 and code_str[2].isalpha():
                # Remove "OL" prefix, keeping the third character and rest
                converted_code = code_str[2:]  # Keep letter + numbers (e.g., "G12-06-1001")
                self.logger.debug(f"Convertido código OL: '{code_str}' -> '{converted_code}'")
            else:
                # If it doesn't match OL* pattern, use as is
                converted_code = code_str
                self.logger.debug(f"Código não-OL mantido como está: '{code_str}'")
            
            # Remove all dashes and spaces for consistency
            converted_code = converted_code.replace('-', '').replace(' ', '')
            
            # Validate result
            if not converted_code or len(converted_code) < 1:
                self.logger.warning(f"Código convertido vazio resultante de: '{code_str}'")
                return None
            
            # Check for reasonable length
            if len(converted_code) > 50:
                self.logger.warning(f"Código convertido muito longo: '{converted_code}' (original: '{code_str}')")
            
            return converted_code
            
        except Exception as e:
            self.logger.error(f"Erro ao converter código '{olg_code}': {str(e)}")
            raise ValidationError(f"Erro na conversão do código '{olg_code}': {str(e)}")


class HierarchyLevelParser:
    """Classe responsável por analisar níveis de hierarquia."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def parse_hierarchy_level(self, item_str: Any) -> int:
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
                self.logger.warning(f"Formato de item inválido: '{item_str}' (contém caracteres não numéricos)")
                return -1
            
            # Split by dots to analyze structure
            parts = item_str.split('.')
            
            # Validate that all parts are numeric
            for part in parts:
                part_clean = part.strip()
                if part_clean and not part_clean.isdigit():
                    self.logger.warning(f"Parte não numérica em item: '{item_str}' (parte: '{part_clean}')")
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
                self.logger.warning(f"Nível de hierarquia muito profundo: {level} para item '{item_str}'")
            
            self.logger.debug(f"Item '{item_str}' -> Nível {level}")
            return level
            
        except Exception as e:
            self.logger.error(f"Erro ao analisar nível de hierarquia para '{item_str}': {str(e)}")
            raise ValidationError(f"Erro na análise do nível de hierarquia: {str(e)}")


class DataProcessor:
    """Classe principal de processamento de dados."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.code_converter = OLGCodeConverter()
        self.hierarchy_parser = HierarchyLevelParser()
    
    def process_excel_data(self, df: pd.DataFrame) -> Tuple[Dict, Dict, List, ProcessingStats]:
        """
        Process Excel data and organize by hierarchy levels.
        
        Args:
            df: DataFrame with Excel data
            
        Returns:
            Tuple of (items_by_level, item_to_code, exclusion_records, stats)
        """
        items_by_level = {}  # level -> [(item, quantity, child_code, original_index)]
        item_to_code = {}    # item -> child_code
        
        # Counters for statistics
        ignored_caret_rows = 0
        skipped_no_code_rows = 0
        skipped_invalid_level_rows = 0
        considered_valid_rows = 0
        exclusion_records = []
        
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
                continue
            
            # Convert drawing number to code
            child_code = self.code_converter.convert_olg_code(drawing_number)
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
                continue
            
            # Determine hierarchy level
            level = self.hierarchy_parser.parse_hierarchy_level(item)
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
                continue
                
            # Store item information
            if level not in items_by_level:
                items_by_level[level] = []
            items_by_level[level].append((item, quantity, child_code, index))
            item_to_code[item] = child_code
            considered_valid_rows += 1
        
        # Create processing statistics
        stats = ProcessingStats(
            total_rows=len(df),
            valid_rows=considered_valid_rows,
            excluded_rows=ignored_caret_rows + skipped_no_code_rows + skipped_invalid_level_rows,
            duplicate_rows=0,  # Will be calculated later
            consolidated_rows=0,  # Will be calculated later
            generated_relationships=0  # Will be calculated later
        )
        
        return items_by_level, item_to_code, exclusion_records, stats


class CSVGenerator:
    """Classe responsável por gerar o arquivo CSV."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def build_parent_child_relationships(self, items_by_level: Dict, root_assembly_code: str) -> Tuple[List, Dict, List, List]:
        """
        Build parent-child relationships using breadth-first approach.
        
        Args:
            items_by_level: Dictionary with items organized by hierarchy level
            root_assembly_code: Main assembly code
            
        Returns:
            Tuple of (output_rows, edge_to_quantity, duplicate_records, consolidated_relationships)
        """
        output_rows = []
        edge_to_quantity = {}  # (parent_code, child_code) -> summed quantity
        processed_parent_code_to_item = {}
        duplicate_records = []
        consolidated_relationships = []

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
        
        return output_rows, edge_to_quantity, duplicate_records, consolidated_relationships
    
    def save_csv_file(self, output_rows: List, output_file: str) -> None:
        """
        Save the processed data to CSV file.
        
        Args:
            output_rows: List of output rows
            output_file: Path to output CSV file
        """
        import pandas as pd
        
        # Create output DataFrame
        output_df = pd.DataFrame(output_rows)
        
        # Save to CSV with semicolon separator and header row (UTF-8 with BOM for Excel)
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            # Write header row first
            f.write('EMP;MTG;COD;QTD;PER\n')
            # Write data rows without header
            output_df.to_csv(f, sep=';', index=False, header=False)
