"""
Conversor para Atualização de Descrições.
Baseado na macro "2 - ATUALIZAÇÃO DA DESCRIÇÃO DE TODOS OS COMPONENTES.bas"
"""

import pandas as pd
import logging
from typing import Dict, List, Any

from ..models import ConversionRequest, ConversionResult, ProcessingStats
from .base_converter import BaseConverter


class DescriptionUpdateConverter(BaseConverter):
    """
    Conversor para atualização de descrições.
    
    Gera CSV com:
    - Coluna A: Código (sem "OL", "-" e " ")
    - Coluna B: Descrição da peça
    """
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
    @staticmethod
    def _normalize_header(name: str) -> str:
        try:
            import unicodedata
            nkfd = unicodedata.normalize('NFKD', str(name))
            no_accents = "".join([c for c in nkfd if not unicodedata.combining(c)])
            return no_accents.lower().strip().replace(" ", "")
        except Exception:
            return str(name).lower().strip().replace(" ", "")
    
    @staticmethod
    def _sanitize_field(text: str) -> str:
        try:
            if text is None:
                return ""
            s = str(text).replace('\r', ' ').replace('\n', ' ').replace('\t', ' ')
            s = s.replace(';', ',')
            while '  ' in s:
                s = s.replace('  ', ' ')
            return s.strip()
        except Exception:
            return str(text) if text is not None else ""
    
    def convert(self, request: ConversionRequest) -> ConversionResult:
        """
        Converte para formato de atualização de descrições.
        
        Args:
            request: Requisição de conversão
            
        Returns:
            ConversionResult com o resultado
        """
        try:
            # Ler arquivo Excel
            df = pd.read_excel(request.input_file)
            
            # Processar dados
            items_by_level, item_to_code, exclusion_records, stats = self.process_excel_data(df)
            
            # Gerar dados de atualização de descrições + avisos
            description_data, warnings_list = self._generate_description_data(df, item_to_code, exclusion_records)
            
            # Salvar arquivo CSV
            output_file = self.get_output_filename(request)
            # Ordenar alfabeticamente pela coluna A (Codigo)
            description_data.sort(key=lambda r: r.get('Codigo', ''))
            self._save_description_csv(description_data, output_file)
            
            # Atualizar estatísticas
            stats.generated_relationships = len(description_data)
            if warnings_list:
                stats.warnings = (stats.warnings or []) + warnings_list
            
            success_message = (
                f"Arquivo de atualização de descrições gerado com sucesso!\n"
                f"Total de componentes: {len(description_data)}\n"
                f"Arquivo: {output_file}\n\n"
                f"📋 Formato do arquivo:\n"
                f"• Código (sem OL, -, espaço)\n"
                f"• Descrição\n\n"
                f"🚀 Use o código de importação '7' no Importador"
            )
            
            return ConversionResult(
                success=True,
                message=success_message,
                output_file=output_file,
                stats=stats
            )
            
        except Exception as e:
            error_msg = f"Erro na conversão para atualização de descrições: {str(e)}"
            self.logger.error(error_msg)
            return ConversionResult(False, error_msg)
    
    def _generate_description_data(self, df: pd.DataFrame, item_to_code: Dict, exclusion_records: List) -> List[Dict]:
        """
        Gera dados para atualização de descrições.
        
        Args:
            df: DataFrame original
            item_to_code: Mapeamento item -> código
            exclusion_records: Registros excluídos
            
        Returns:
            Lista de dicionários com dados de descrição
        """
        description_data = []
        warnings: List[str] = []
        processed_codes = set()  # Para evitar duplicatas
        
        for index, row in df.iterrows():
            drawing_number = row['N° DESENHO']
            
            # Pular linhas com '^' (já processadas no data_processor)
            if pd.notna(drawing_number) and '^' in str(drawing_number):
                continue
            
            # Converter código
            code = self.data_processor.code_converter.convert_olg_code(drawing_number)
            if not code:
                continue
            
            # Evitar duplicatas
            if code in processed_codes:
                continue
            processed_codes.add(code)
            
            # Obter descrição da coluna C (Descrição) com fallback por posição
            description = ""
            try:
                normalized_map = {self._normalize_header(col): col for col in df.columns}
                target_key = 'descricao'
                if target_key in normalized_map:
                    value = row[normalized_map[target_key]]
                    description = str(value) if pd.notna(value) else ""
                else:
                    value = row.iloc[2]  # coluna C
                    description = str(value) if pd.notna(value) else ""
            except Exception:
                description = ""
            description = self._sanitize_field(description)
            
            # Incluir códigos Z (OLZ) neste conversor – não filtrar
            
            # Validar e registrar avisos (não escrever colunas de status/observação)
            validation_result = self._validate_description(description, code)
            if not validation_result['is_valid']:
                # Linha humana = índice do DF + 2 (1 = cabeçalho do Excel)
                human_line = index + 2
                warnings.append(f"Linha {human_line}: {validation_result['message']} para Código {code}")

            # Registro com apenas Código e Descrição
            description_record = {
                'Codigo': code,
                'Descricao': description
            }
            description_data.append(description_record)
        
        return description_data, warnings
    
    def _validate_description(self, description: str, code: str) -> Dict[str, Any]:
        """
        Valida uma descrição.
        
        Args:
            description: Descrição a ser validada
            code: Código da peça
            
        Returns:
            Dicionário com resultado da validação
        """
        if not description or description.strip() == "":
            return {
                'is_valid': False,
                'message': 'Descrição vazia'
            }
        
        # Verificar limite de caracteres (aproximadamente 80 caracteres)
        if len(description) > 80:
            return {
                'is_valid': False,
                'message': f'Descrição muito longa ({len(description)} caracteres)'
            }
        
        return {
            'is_valid': True,
            'message': 'OK'
        }
    
    def _save_description_csv(self, data: List[Dict], output_file: str) -> None:
        """
        Salva dados de descrição em arquivo CSV.
        
        Args:
            data: Lista de dados de descrição
            output_file: Caminho do arquivo de saída
        """
        if not data:
            df = pd.DataFrame(columns=['Codigo', 'Descricao'])
        else:
            df = pd.DataFrame(data, columns=['Codigo', 'Descricao'])
        
        # Salvar com ponto e vírgula, sem cabeçalho (UTF-8 com BOM)
        df.to_csv(output_file, sep=';', index=False, header=False, encoding='utf-8-sig')
    
    def get_output_filename(self, request: ConversionRequest) -> str:
        """
        Gera nome do arquivo de saída para atualização de descrições.
        
        Args:
            request: Requisição de conversão
            
        Returns:
            Nome do arquivo de saída
        """
        import os
        out_dir = os.environ.get('SOLID_OUTPUT_DIR')
        if out_dir and os.path.isdir(out_dir):
            directory = out_dir
        else:
            directory = os.path.dirname(request.input_file)
        # Include assembly code in filename and replace underscores with spaces
        assembly_code = getattr(request, 'assembly_code', '')
        if assembly_code:
            filename = f"ATUALIZAÇÃO DE DESCRIÇÕES {assembly_code}.csv"
        else:
            filename = "ATUALIZAÇÃO DE DESCRIÇÕES.csv"
        return os.path.join(directory, filename)

