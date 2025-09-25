"""
Módulo principal de conversão XLSX para CSV.
Implementa o princípio Single Responsibility Principle (SRP) e Dependency Inversion Principle (DIP).
"""

import os
import shutil
import pandas as pd
import logging
import traceback
from typing import Tuple, Optional

from .models import (
    ConversionRequest, ConversionResult, ProcessingStats, 
    ValidationError, FileProcessingError, ConversionConfig
)
from .validators import ValidationService
from .data_processor import DataProcessor, CSVGenerator
from .conversion_types import ConversionType
from .converters.parts_registration_converter import PartsRegistrationConverter
from .converters.description_update_converter import DescriptionUpdateConverter
from .converters.material_update_converter import MaterialUpdateConverter
from .converters.olz_verification_converter import OLZVerificationConverter


class ZDetector:
    """Classe responsável por detectar caracteres 'Z' no CSV gerado."""
    
    def detect_z_in_generated_csv(self, csv_file_path: str) -> dict:
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


class ReportGenerator:
    """Classe responsável por gerar relatórios de processamento."""
    
    def generate_exclusions_report(self, exclusion_records: list, duplicate_records: list, 
                                 consolidated_relationships: list, consolidated_children: list,
                                 items_by_level: dict, output_file: str, total_original_rows: int, 
                                 output_rows: list, assembly_code: str) -> None:
        """
        Generate comprehensive exclusions report CSV.
        
        Args:
            exclusion_records: List of excluded records
            duplicate_records: List of duplicate records
            consolidated_relationships: List of consolidated relationships
            consolidated_children: List of consolidated children
            items_by_level: Items organized by hierarchy level
            output_file: Path to output CSV file
            total_original_rows: Total number of original rows
            output_rows: List of output rows
            assembly_code: Assembly code for report naming
        """
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
                'ITEM': f'Ignoradas por "^": {len([r for r in exclusion_records if r["MOTIVO"] == "\'^\' em N° DESENHO"])}',
                'QTD': f'Sem código válido: {len([r for r in exclusion_records if "inválido ou ausente" in r["MOTIVO"]])}',
                'N° DESENHO': f'Nível inválido: {len([r for r in exclusion_records if "nível não identificável" in r["MOTIVO"]])}',
                'CODIGO MP20': f'Válidas processadas: {total_original_rows - len(exclusion_records)}'
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
            logging.getLogger(__name__).warning(f"Erro ao gerar relatório de exclusões: {str(e)}")


class MultiTypeConverter:
    """
    Conversor principal que suporta múltiplos tipos de conversão.
    Implementa o princípio Single Responsibility Principle (SRP) e Dependency Inversion Principle (DIP).
    """
    
    def __init__(self, config: ConversionConfig = None):
        self.config = config or ConversionConfig()
        self.logger = logging.getLogger(__name__)
        self.validator = ValidationService(self.config)
        self.data_processor = DataProcessor()
        self.csv_generator = CSVGenerator()
        self.z_detector = ZDetector()
        self.report_generator = ReportGenerator()
        
        # Inicializar conversores específicos
        self.converters = {
            ConversionType.PARTS_REGISTRATION: PartsRegistrationConverter(),
            ConversionType.DESCRIPTION_UPDATE: DescriptionUpdateConverter(),
            ConversionType.MATERIAL_UPDATE: MaterialUpdateConverter(),
            ConversionType.OLZ_VERIFICATION: OLZVerificationConverter()
        }
    
    def convert(self, request: ConversionRequest, conversion_type: ConversionType = ConversionType.HIERARCHICAL_STRUCTURE) -> ConversionResult:
        """
        Converte arquivo XLSX para CSV usando o tipo especificado.
        
        Args:
            request: Requisição de conversão
            conversion_type: Tipo de conversão a ser executada
            
        Returns:
            ConversionResult com o resultado da conversão
        """
        try:
            self.logger.info(f"Iniciando conversão tipo: {conversion_type.value}")
            
            # Validar request
            assembly_code_for_validation = request.assembly_code if conversion_type == ConversionType.HIERARCHICAL_STRUCTURE else ""
            validation_result = self.validator.validate_conversion_request(
                request.input_file, assembly_code_for_validation
            )
            
            if not validation_result.is_valid:
                error_msg = "Erro de validação:\n" + "\n".join(validation_result.errors)
                if validation_result.warnings:
                    error_msg += "\nAvisos:\n" + "\n".join(validation_result.warnings)
                self.logger.error(error_msg)
                return ConversionResult(False, error_msg, warnings=validation_result.warnings)
            
            # Executar conversão baseada no tipo
            if conversion_type == ConversionType.HIERARCHICAL_STRUCTURE:
                return self._convert_hierarchical_structure(request)
            else:
                # Usar conversor específico
                converter = self.converters.get(conversion_type)
                if not converter:
                    error_msg = f"Conversor não encontrado para tipo: {conversion_type}"
                    self.logger.error(error_msg)
                    return ConversionResult(False, error_msg)
                
                return converter.convert(request)
                
        except Exception as e:
            error_msg = f"Erro inesperado durante a conversão: {str(e)}"
            self.logger.error(f"Erro inesperado: {traceback.format_exc()}")
            return ConversionResult(False, error_msg)
    
    def _convert_hierarchical_structure(self, request: ConversionRequest) -> ConversionResult:
        """
        Converte para estrutura hierárquica (método original).
        
        Args:
            request: Requisição de conversão
            
        Returns:
            ConversionResult com o resultado
        """
        # Usar o conversor original para estrutura hierárquica
        original_converter = XLSXToCSVConverter(self.config)
        return original_converter.convert(request)


class XLSXToCSVConverter:
    """
    Classe principal de conversão XLSX para CSV (versão original).
    Implementa o princípio Single Responsibility Principle (SRP) e Dependency Inversion Principle (DIP).
    """
    
    def __init__(self, config: ConversionConfig = None):
        self.config = config or ConversionConfig()
        self.logger = logging.getLogger(__name__)
        self.validator = ValidationService(self.config)
        self.data_processor = DataProcessor()
        self.csv_generator = CSVGenerator()
        self.z_detector = ZDetector()
        self.report_generator = ReportGenerator()
    
    def convert(self, request: ConversionRequest) -> ConversionResult:
        """
        Convert XLSX file to parent-child CSV format.
        
        Args:
            request: Conversion request with input file, output file, and assembly code
            
        Returns:
            ConversionResult with success status and details
        """
        try:
            self.logger.info(f"Iniciando conversão com código de montagem: {request.assembly_code}")
            
            # Validate request
            validation_result = self.validator.validate_conversion_request(
                request.input_file, request.assembly_code
            )
            
            if not validation_result.is_valid:
                error_msg = "Erro de validação:\n" + "\n".join(validation_result.errors)
                if validation_result.warnings:
                    error_msg += "\nAvisos:\n" + "\n".join(validation_result.warnings)
                self.logger.error(error_msg)
                return ConversionResult(False, error_msg, warnings=validation_result.warnings)
            
            # Log warnings if any
            if validation_result.warnings:
                for warning in validation_result.warnings:
                    self.logger.warning(f"Validação: {warning}")
            
            root_assembly_code = request.assembly_code.strip()
            
            # Read the XLSX file
            try:
                self.logger.info(f"Lendo arquivo: {request.input_file}")
                df = pd.read_excel(request.input_file)
                self.logger.info(f"Arquivo lido com sucesso. Linhas: {len(df)}, Colunas: {len(df.columns)}")
            except Exception as e:
                error_msg = f"Erro ao ler arquivo Excel: {str(e)}"
                self.logger.error(error_msg)
                return ConversionResult(False, error_msg)
            
            # Validate DataFrame structure
            df_validation = self.validator.dataframe_validator.validate_dataframe_structure(df)
            if not df_validation.is_valid:
                error_msg = "Erro de validação da estrutura do arquivo:\n" + "\n".join(df_validation.errors)
                self.logger.error(error_msg)
                return ConversionResult(False, error_msg)
            
            # Log warnings if any
            if df_validation.warnings:
                for warning in df_validation.warnings:
                    self.logger.warning(f"Estrutura do arquivo: {warning}")
            
            self.logger.info("Validações concluídas com sucesso")
            
            # Process Excel data
            items_by_level, item_to_code, exclusion_records, stats = self.data_processor.process_excel_data(df)
            
            # Build parent-child relationships
            output_rows, edge_to_quantity, duplicate_records, consolidated_relationships = self.csv_generator.build_parent_child_relationships(
                items_by_level, root_assembly_code
            )
            
            # Prepare output directory and file
            final_output_file = self._prepare_output_file(request.input_file, request.output_file, root_assembly_code)
            
            # Save CSV file
            self.csv_generator.save_csv_file(output_rows, final_output_file)
            
            # Check for "Z" in column B of the generated CSV file
            z_detection_result = self.z_detector.detect_z_in_generated_csv(final_output_file)
            
            # Generate comprehensive exclusions report
            self.report_generator.generate_exclusions_report(
                exclusion_records, duplicate_records, consolidated_relationships, [],
                items_by_level, final_output_file, len(df), output_rows, root_assembly_code
            )
            
            # Update statistics
            stats.duplicate_rows = len(duplicate_records)
            stats.consolidated_rows = len(consolidated_relationships)
            stats.generated_relationships = len(output_rows)
            
            # Verification
            expected_csv_rows = len(edge_to_quantity)
            generated_csv_rows = len(output_rows)
            
            if generated_csv_rows != expected_csv_rows:
                details = (
                    f"Verificação de contagem falhou. Esperado: {expected_csv_rows} linhas no CSV, "
                    f"Gerado: {generated_csv_rows}.\n"
                    f"Resumo: Linhas XLSX (com cabeçalho): {len(df) + 1}; "
                    f"Linhas de dados XLSX: {len(df)}; Ignoradas por '^': {stats.excluded_rows}; "
                    f"Válidas esperadas: {expected_csv_rows}."
                )
                return ConversionResult(False, details)
            
            # Create success message
            success_message = self._create_success_message(
                final_output_file, generated_csv_rows, stats, z_detection_result, 
                len(exclusion_records), len(duplicate_records), len(consolidated_relationships), root_assembly_code
            )
            
            return ConversionResult(
                success=True,
                message=success_message,
                output_file=final_output_file,
                stats=stats,
                warnings=validation_result.warnings
            )
            
        except FileNotFoundError as e:
            error_msg = f"Arquivo de estrutura não encontrado: {request.input_file}"
            self.logger.error(error_msg)
            return ConversionResult(False, error_msg)
        except ValidationError as e:
            error_msg = f"Erro de validação: {str(e)}"
            self.logger.error(error_msg)
            return ConversionResult(False, error_msg)
        except FileProcessingError as e:
            error_msg = f"Erro de processamento de arquivo: {str(e)}"
            self.logger.error(error_msg)
            return ConversionResult(False, error_msg)
        except pd.errors.EmptyDataError:
            error_msg = "Arquivo Excel está vazio ou não contém dados válidos"
            self.logger.error(error_msg)
            return ConversionResult(False, error_msg)
        except pd.errors.ParserError as e:
            error_msg = f"Erro ao processar arquivo Excel: {str(e)}"
            self.logger.error(error_msg)
            return ConversionResult(False, error_msg)
        except PermissionError as e:
            error_msg = f"Erro de permissão ao acessar arquivo: {str(e)}"
            self.logger.error(error_msg)
            return ConversionResult(False, error_msg)
        except MemoryError:
            error_msg = "Arquivo muito grande para processar. Tente com um arquivo menor."
            self.logger.error(error_msg)
            return ConversionResult(False, error_msg)
        except Exception as e:
            error_msg = f"Erro inesperado durante a exportação da estrutura: {str(e)}"
            self.logger.error(f"Erro inesperado: {traceback.format_exc()}")
            return ConversionResult(False, error_msg)
    
    def _prepare_output_file(self, input_file: str, output_file: str, assembly_code: str) -> str:
        """
        Prepare output file path and directory structure.
        
        Args:
            input_file: Path to input file
            output_file: Path to output file
            assembly_code: Assembly code
            
        Returns:
            Final output file path
        """
        try:
            # If an explicit output dir is set (DEV), honor it
            out_dir = os.environ.get('SOLID_OUTPUT_DIR')
            if out_dir and os.path.isdir(out_dir):
                target_dir = out_dir
            else:
                input_dir = os.path.dirname(input_file)
                main_code = assembly_code or os.path.splitext(os.path.basename(output_file))[0].replace('ESTRUTURA_', '')
                folder_name = f"ESTRUTURA {main_code}"
                target_dir = os.path.join(input_dir, folder_name)
            
            if not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)

            # Copy the original selected file into the new folder if not already inside
            # This preserves the original file for multiple conversions
            input_basename = os.path.basename(input_file)
            copied_input_path = os.path.join(target_dir, input_basename)
            if os.path.abspath(os.path.dirname(input_file)) != os.path.abspath(target_dir):
                try:
                    if os.path.exists(copied_input_path):
                        os.remove(copied_input_path)
                    shutil.copy2(input_file, copied_input_path)
                except Exception:
                    pass  # Do not block conversion if copy fails

            # Redirect output_file to inside the target_dir
            final_output_file = os.path.join(target_dir, os.path.basename(output_file))
            return final_output_file
            
        except Exception:
            return output_file  # Return original if folder creation fails
    
    def _create_success_message(self, output_file: str, generated_csv_rows: int, 
                              stats: ProcessingStats, z_detection_result: dict,
                              exclusion_count: int, duplicate_count: int, 
                              consolidated_count: int, assembly_code: str) -> str:
        """
        Create comprehensive success message.
        
        Args:
            output_file: Path to output file
            generated_csv_rows: Number of generated CSV rows
            stats: Processing statistics
            z_detection_result: Z detection results
            exclusion_count: Number of exclusions
            duplicate_count: Number of duplicates
            consolidated_count: Number of consolidated relationships
            assembly_code: Assembly code
            
        Returns:
            Success message string
        """
        # Add Z detection results to success message
        z_detection_info = ""
        if z_detection_result['has_z']:
            z_detection_info = f"\n\n⚠️ AVISO - DETECÇÃO DE 'Z' NO ARQUIVO CSV GERADO:\n"
            z_detection_info += f"• {z_detection_result['details']}\n"
            z_detection_info += f"• Entradas com 'Z' na coluna B (MTG): {z_detection_result['count']}\n"
            if z_detection_result.get('z_entries'):
                z_detection_info += f"• Detalhes das entradas:\n"
                for entry in z_detection_result['z_entries']:
                    z_detection_info += f"  - Linha {entry['row_index']}: {entry['mtg']} → {entry['cod']} (Qtd: {entry['qtd']})\n"
        else:
            z_detection_info = f"\n\n✅ VERIFICAÇÃO DE 'Z' NO ARQUIVO CSV GERADO:\n• {z_detection_result['details']}"
        
        code_for_report = assembly_code
        
        return (
            f"Estrutura exportada com sucesso! {generated_csv_rows} relacionamentos processados.\n"
            f"Arquivo CSV gerado: {output_file}\n\n"
            f"Verificação OK. Linhas XLSX (com cabeçalho): {stats.total_rows + 1}; Linhas de dados: {stats.total_rows}; "
            f"Ignoradas por '^': {stats.excluded_rows}; Válidas esperadas: {generated_csv_rows}; "
            f"CSV geradas: {generated_csv_rows}.\n\n"
            f"📊 Resumo de Processamento:\n"
            f"• Linhas removidas: {exclusion_count + 1} (cabeçalho + caret)\n"
            f"• Duplicatas consolidadas: {duplicate_count}\n"
            f"• Relacionamentos consolidados: {consolidated_count}\n"
            f"• Total de linhas processadas: {stats.total_rows}\n\n"
            f"Relatório completo salvo como RELATORIO_REMOVIDOS_{code_for_report}.csv.\n"
            f"Pronto para importação no sistema NEO.{z_detection_info}"
        )


# Função de conveniência para compatibilidade com código existente
def xlsx_to_parent_child_csv(input_file: str, output_file: str, assembly_code: str = None) -> Tuple[bool, str]:
    """
    Função de conveniência para conversão XLSX para CSV.
    Mantém compatibilidade com o código existente.
    
    Args:
        input_file: Path to input XLSX file
        output_file: Path to output CSV file
        assembly_code: Main assembly code (required)
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    if not assembly_code:
        return False, "Código da montagem principal é obrigatório. Por favor, insira o código no campo correspondente."
    
    request = ConversionRequest(
        input_file=input_file,
        output_file=output_file,
        assembly_code=assembly_code
    )
    
    converter = XLSXToCSVConverter()
    result = converter.convert(request)
    
    return result.success, result.message
