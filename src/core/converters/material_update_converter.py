"""
Conversor para Atualização de Matéria Prima.
Baseado na macro "3 - ATUALIZAÇÃO MATÉRIA PRIMA DE PEÇAS FABRICADAS.bas"
"""

import pandas as pd
import logging
from typing import Dict, List, Any

from ..models import ConversionRequest, ConversionResult, ProcessingStats
from .base_converter import BaseConverter


class MaterialUpdateConverter(BaseConverter):
    """
    Conversor para atualização de matéria prima de peças fabricadas.
    
    Gera CSV com:
    - Coluna A: Empresa = "001"
    - Coluna B: Código (sem "OL", "-" e " ")
    - Coluna C: Código da Matéria Prima
    - Coluna D: Peso ou metragem (sempre exibido como ="x,yy")
    - Coluna E: Perda = "0"
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
    def _extract_meters_from_text(text: str) -> str:
        """Extrai o último valor em mm do texto e converte para metros com vírgula e 2 casas.
        Ex.: "... 5920mm" -> "5,92".
        Retorna "1,00" caso não consiga extrair.
        """
        try:
            import re
            if text is None:
                return "1,00"
            s = str(text)
            matches = re.findall(r"(\d+(?:[\.,]\d+)?)\s*mm", s, flags=re.IGNORECASE)
            if not matches:
                return "1,00"
            val_txt = matches[-1].replace(',', '.')
            mm = float(val_txt)
            meters = mm / 1000.0
            return f"{meters:.2f}".replace('.', ',')
        except Exception:
            return "1,00"

    def _count_valid_map_rows(self, df: pd.DataFrame) -> int:
        """Conta linhas do XLSX que têm código de matéria-prima válido (após formatação),
        considerando as mesmas regras de filtragem da conversão (ignora peças OLZ/Z*)."""
        count = 0
        processed_codes = set()  # Para evitar duplicatas (mesma lógica da geração)
        try:
            for _, row in df.iterrows():
                drawing_number = row['N° DESENHO']
                
                # Pular linhas com '^' (já processadas no data_processor)
                if pd.notna(drawing_number) and '^' in str(drawing_number):
                    continue
                    
                code = self.data_processor.code_converter.convert_olg_code(drawing_number)
                if not code or code.startswith('Z'):
                    continue
                
                # Evitar duplicatas (mesma lógica da geração)
                if code in processed_codes:
                    continue
                processed_codes.add(code)
                
                raw = str(row['CODIGO MP20']) if pd.notna(row['CODIGO MP20']) else ""
                formatted = self._format_material_code(raw)
                if formatted:
                    count += 1
        except Exception:
            pass
        return count
    
    @staticmethod
    def _format_material_code(raw: str) -> str:
        """Formata o código da matéria-prima para um dos 3 padrões aceitos:
        1) 6 dígitos numéricos (ex.: 123456)
        2) 'Z' + 5 dígitos (ex.: Z12345)
        3) 'Z' + 6 dígitos (ex.: Z123456)
        Caso não seja possível, retorna string vazia.
        """
        try:
            import re
            if raw is None:
                return ""
            s = str(raw).strip().upper()
            # Novo método: cortar a partir do primeiro " - " se existir
            if ' - ' in s:
                s = s.split(' - ', 1)[0].strip()
            if not s:
                return ""
            if s.startswith('Z'):
                digits = ''.join(re.findall(r'\d', s))
                if len(digits) >= 6:
                    return 'Z' + digits[-6:]
                if len(digits) >= 5:
                    return 'Z' + digits[-5:]
                return ''
            else:
                digits = ''.join(re.findall(r'\d', s))
                if len(digits) >= 6:
                    return digits[-6:]
                return ''
        except Exception:
            return ""
    
    def convert(self, request: ConversionRequest) -> ConversionResult:
        """
        Converte para formato de atualização de matéria prima.
        
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
            
            # Gerar dados de atualização de matéria prima + avisos
            material_data, warnings_list = self._generate_material_data(df, item_to_code, exclusion_records)

            # Verificação: quantidade gerada deve igualar quantidade de linhas com MAP válido
            expected_count = self._count_valid_map_rows(df)
            generated_count = len(material_data)
            if expected_count != generated_count:
                warnings_list.append(
                    f"Verificação de contagem: esperado {expected_count} registros com MAP válido, gerado {generated_count}."
                )
            
            # Salvar arquivo CSV
            output_file = self.get_output_filename(request)
            # Ordenar alfabeticamente pela coluna B (COD)
            material_data.sort(key=lambda r: r.get('COD', ''))
            self._save_material_csv(material_data, output_file)
            
            # Atualizar estatísticas
            stats.generated_relationships = len(material_data)
            if warnings_list:
                stats.warnings = (stats.warnings or []) + warnings_list
            
            success_message = (
                f"Arquivo de atualização de matéria prima gerado com sucesso!\n"
                f"Total de componentes: {len(material_data)}\n"
                f"Arquivo: {output_file}\n\n"
                f"📋 Formato do arquivo:\n"
                f"• Empresa: 001\n"
                f"• Código (sem OL, -, espaço)\n"
                f"• Código da Matéria Prima\n"
                f"• Peso/Metragem\n"
                f"• Perda: 0\n\n"
                f"⚠️ Regras aplicadas:\n"
                f"• Z20 => metragem em metros\n"
                f"• Demais => peso em kg"
            )
            
            return ConversionResult(
                success=True,
                message=success_message,
                output_file=output_file,
                stats=stats
            )
            
        except Exception as e:
            error_msg = f"Erro na conversão para atualização de matéria prima: {str(e)}"
            self.logger.error(error_msg)
            return ConversionResult(False, error_msg)
    
    def _generate_material_data(self, df: pd.DataFrame, item_to_code: Dict, exclusion_records: List) -> List[Dict]:
        """
        Gera dados para atualização de matéria prima.
        
        Args:
            df: DataFrame original
            item_to_code: Mapeamento item -> código
            exclusion_records: Registros excluídos
            
        Returns:
            Lista de dicionários com dados de matéria prima
        """
        material_data = []
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
            # Ignorar todos os códigos OLZ (iniciados por 'Z')
            if code.startswith('Z'):
                continue
            
            # Evitar duplicatas
            if code in processed_codes:
                continue
            processed_codes.add(code)
            
            # Obter código de matéria prima (usar CODIGO MP20) e aplicar formatação exigida
            material_code_raw = str(row['CODIGO MP20']) if pd.notna(row['CODIGO MP20']) else ""
            material_code = self._format_material_code(material_code_raw)
            
            if not material_code:
                # Sem código de matéria-prima: não é relevante para este conversor
                # (ex.: itens que não são peças com MAP). Ignorar silenciosamente.
                continue
            
            # Calcular PES: se MAP começa com Z20 (mangueira), usar metragem extraída do texto.
            # Caso contrário, tentar coluna PESO; se não houver, usar regra antiga.
            try:
                if material_code.startswith('Z20'):
                    # Para mangueiras: extrair SEMPRE a metragem a partir da coluna C (Descrição)
                    try:
                        normalized_map_desc = {self._normalize_header(col): col for col in df.columns}
                        if 'descricao' in normalized_map_desc:
                            desc_text = row[normalized_map_desc['descricao']]
                        elif 'descrição' in normalized_map_desc:
                            desc_text = row[normalized_map_desc['descrição']]
                        elif 'desc' in normalized_map_desc:
                            desc_text = row[normalized_map_desc['desc']]
                        else:
                            # Fallback por posição (coluna C = índice 2)
                            desc_text = row.iloc[2]
                    except Exception:
                        desc_text = material_code_raw
                    weight_or_length = self._extract_meters_from_text(desc_text)
                    if weight_or_length == "1,00":
                        warnings.append(f"Linha {index+2}: Metragem não encontrada para mangueira (Z20) código {code}")
                else:
                    normalized_map = {self._normalize_header(col): col for col in df.columns}
                    weight_or_length = "0,00"
                    if 'peso' in normalized_map:
                        raw_weight = row[normalized_map['peso']]
                        if pd.notna(raw_weight):
                            txt = str(raw_weight).strip().replace('\u00A0', ' ').replace(' ', '')
                            txt = txt.replace(',', '.')
                            val = float(txt)
                            weight_or_length = f"{val:.2f}".replace('.', ',')
                    else:
                        weight_or_length = self._calculate_weight_or_length(code, material_code)
                        warnings.append(f"Linha {index+2}: Coluna PESO ausente, usando valor padrão para código {code}")
            except Exception:
                weight_or_length = self._calculate_weight_or_length(code, material_code)
                warnings.append(f"Linha {index+2}: Erro ao calcular PES para código {code}, usando padrão")
            
            # Criar registro de matéria prima
            material_record = {
                'EMP': '001',
                'COD': code,
                'MAP': material_code,
                'PES': weight_or_length,
                'PER': '0'
            }
            
            material_data.append(material_record)
        
        return material_data, warnings
    
    def _calculate_weight_or_length(self, code: str, material_code: str) -> str:
        """
        Calcula peso ou metragem baseado no código.
        
        Args:
            code: Código da peça
            material_code: Código da matéria prima
            
        Returns:
            Peso ou metragem formatado
        """
        # Regra: Z20 => metragem em metros a partir da ÚLTIMA ocorrência "mm"
        if code.startswith('Z') and '20' in code:
            # Para peças Z20, calcular metragem
            # Extrair números após "mm" se existir
            if 'mm' in material_code:
                # Encontrar a última ocorrência de "mm"
                mm_pos = material_code.rfind('mm')
                if mm_pos != -1:
                    # Extrair números após "mm"
                    after_mm = material_code[mm_pos + 2:].strip()
                    # Converter para metros (assumindo que está em mm)
                    try:
                        mm_value = float(after_mm.replace(',', '.'))
                        meters = mm_value / 1000
                        return f"{meters:.2f}".replace('.', ',')
                    except ValueError:
                        pass
            
            # Se não conseguir calcular, usar valor padrão
            return "1,00"
        else:
            # Para demais peças, usar peso em kg
            # Tentar extrair peso do material_code se possível
            # Por enquanto, usar valor padrão
            return "0,50"
    
    def _save_material_csv(self, data: List[Dict], output_file: str) -> None:
        """
        Salva dados de matéria prima em arquivo CSV.
        
        Args:
            data: Lista de dados de matéria prima
            output_file: Caminho do arquivo de saída
        """
        if not data:
            # Criar arquivo com cabeçalho solicitado
            df = pd.DataFrame(columns=['EMP', 'COD', 'MAP', 'PES', 'PER'])
        else:
            df = pd.DataFrame(data, columns=['EMP', 'COD', 'MAP', 'PES', 'PER'])
        
        # Salvar com ponto e vírgula (UTF-8 com BOM) incluindo cabeçalho EMP;COD;MAP;PES;PER
        df.to_csv(output_file, sep=';', index=False, encoding='utf-8-sig')
    
    def get_output_filename(self, request: ConversionRequest) -> str:
        """
        Gera nome do arquivo de saída para atualização de matéria prima.
        
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
            filename = f"ATUALIZAÇÃO DE MATÉRIA PRIMA {assembly_code}.csv"
        else:
            filename = "ATUALIZAÇÃO DE MATÉRIA PRIMA.csv"
        return os.path.join(directory, filename)

