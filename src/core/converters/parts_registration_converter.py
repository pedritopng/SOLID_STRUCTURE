"""
Conversor para Cadastro de Peças e Montagens.
Baseado na macro "1 - CADASTRO DE PEÇAS E MONTAGENS FABRICADAS.bas"
"""

import pandas as pd
import logging
from typing import Dict, List, Any

from ..models import ConversionRequest, ConversionResult, ProcessingStats
from .base_converter import BaseConverter


class PartsRegistrationConverter(BaseConverter):
    """
    Conversor para cadastro de peças e montagens.
    
    Gera CSV com:
    - Coluna A: Código (sem "OL", "-" e " ")
    - Coluna B: Descrição
    - Colunas C-I: "3","4","107","108","16","3","S"
    - Coluna J: Peso do componente (separado por .)
    """
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.max_field_length = 100
    
    @staticmethod
    def _sanitize_field(text: str) -> str:
        """Remove quebras de linha e normaliza espaços para evitar quebra no CSV."""
        try:
            if text is None:
                return ""
            s = str(text).replace('\r', ' ').replace('\n', ' ').replace('\t', ' ')
            # Evitar delimitador dentro do campo: troca ';' por ','
            s = s.replace(';', ',')
            # Colapsar múltiplos espaços
            while '  ' in s:
                s = s.replace('  ', ' ')
            return s.strip()
        except Exception:
            return str(text) if text is not None else ""
    
    @staticmethod
    def _normalize_header(name: str) -> str:
        """Normaliza cabeçalho removendo acentos e espaços e colocando em minúsculas."""
        try:
            import unicodedata
            nkfd = unicodedata.normalize('NFKD', str(name))
            no_accents = "".join([c for c in nkfd if not unicodedata.combining(c)])
            return no_accents.lower().strip().replace(" ", "")
        except Exception:
            return str(name).lower().strip().replace(" ", "")
    
    def convert(self, request: ConversionRequest) -> ConversionResult:
        """
        Converte para formato de cadastro de peças e montagens.
        
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
            
            # Gerar dados de cadastro
            registration_data = self._generate_registration_data(df, item_to_code, exclusion_records)
            # Ordenar alfabeticamente pela coluna A (Codigo)
            registration_data.sort(key=lambda r: r.get('Codigo', ''))
            
            # Salvar arquivo CSV
            output_file = self.get_output_filename(request)
            self._save_registration_csv(registration_data, output_file)
            
            # Verificar comprimentos de campos
            warnings_list = self._check_field_lengths(registration_data, self.max_field_length)
            
            # Atualizar estatísticas
            stats.generated_relationships = len(registration_data)
            
            success_message = (
                f"Arquivo de cadastro gerado com sucesso!\n"
                f"Total de peças/montagens: {len(registration_data)}\n"
                f"Arquivo: {output_file}\n\n"
                f"📋 Formato do arquivo:\n"
                f"• Código (sem OL, -, espaço)\n"
                f"• Descrição\n"
                f"• Propriedades (3,4,107,108,16,3,S)\n"
                f"• Peso\n\n"
                f"🚀 Use o código de importação '1' no Importador"
            )
            # Se houver avisos, não poluir o popup principal; retornaremos os avisos em warnings
            if warnings_list:
                stats_msg = f"\n\n⚠️ {len(warnings_list)} aviso(s) de comprimento serão exibidos a seguir."
                success_message += stats_msg
                stats.warnings = (stats.warnings or []) + warnings_list
            
            return ConversionResult(
                success=True,
                message=success_message,
                output_file=output_file,
                stats=stats
            )
            
        except Exception as e:
            error_msg = f"Erro na conversão para cadastro de peças: {str(e)}"
            self.logger.error(error_msg)
            return ConversionResult(False, error_msg)
    
    def _generate_registration_data(self, df: pd.DataFrame, item_to_code: Dict, exclusion_records: List) -> List[Dict]:
        """
        Gera dados para cadastro de peças e montagens.
        
        Args:
            df: DataFrame original
            item_to_code: Mapeamento item -> código
            exclusion_records: Registros excluídos
            
        Returns:
            Lista de dicionários com dados de cadastro
        """
        registration_data = []
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
            
            # Coluna B deve trazer os dados da coluna C (DESCRIÇÃO) do arquivo de origem
            # Suporta variações de cabeçalho e fallback pela posição (3ª coluna - índice 2)
            description = ""
            # Tente encontrar uma coluna cujo nome normalizado seja 'descricao'
            try:
                normalized_map = {self._normalize_header(col): col for col in df.columns}
                target_key = 'descricao'
                if target_key in normalized_map:
                    value = row[normalized_map[target_key]]
                    description = str(value) if pd.notna(value) else ""
                else:
                    # Fallback por posição (coluna C = índice 2)
                    value = row.iloc[2]
                    description = str(value) if pd.notna(value) else ""
            except Exception:
                # Último recurso: string vazia
                description = ""
            # Sanitizar descrição para não quebrar linha
            description = self._sanitize_field(description)
            
            # Verificar se é peça OLZ (excluir)
            if code.startswith('Z'):
                continue
            
            # Obter peso a partir da coluna PESO (H) do arquivo de origem
            peso_value = "0.00"
            try:
                normalized_map = {self._normalize_header(col): col for col in df.columns}
                if 'peso' in normalized_map:
                    raw = row[normalized_map['peso']]
                    peso_value = str(raw) if pd.notna(raw) else "0.00"
                else:
                    raw = row.iloc[7]  # Coluna H por posição
                    peso_value = str(raw) if pd.notna(raw) else "0.00"
            except Exception:
                peso_value = "0.00"

            # Normalizar peso para ponto (.) e duas casas (formato como no CSV de exemplo)
            try:
                # Aceitar valores como '1,23' ou '1.23'
                txt = str(peso_value).strip()
                txt = txt.replace('\u00A0', ' ').replace(' ', '')
                txt = txt.replace(',', '.')
                num = float(txt)
                # Formatar com até 2 casas decimais, removendo zeros à direita
                formatted = f"{num:.2f}".rstrip('0').rstrip('.')
                peso_value = formatted if formatted != '' else '0'
            except Exception:
                # Se não for numérico, cai para '0'
                peso_value = '0'

            # Criar registro de cadastro
            registration_record = {
                'Codigo': code,
                'Descricao': description,
                'Prop3': '3',
                'Prop4': '4',
                'Prop107': '107',
                'Prop108': '108',
                'Prop16': '16',
                'Prop3_2': '3',
                'PropS': 'S',
                'Peso': peso_value
            }
            
            registration_data.append(registration_record)
        
        return registration_data
    
    def _save_registration_csv(self, data: List[Dict], output_file: str) -> None:
        """
        Salva dados de cadastro em arquivo CSV.
        
        Args:
            data: Lista de dados de cadastro
            output_file: Caminho do arquivo de saída
        """
        # Escrever em CP-1252 (Windows) sem cabeçalho, como o arquivo de referência
        import io
        df = pd.DataFrame(data, columns=['Codigo', 'Descricao', 'Prop3', 'Prop4', 'Prop107', 'Prop108', 'Prop16', 'Prop3_2', 'PropS', 'Peso']) if data else pd.DataFrame(columns=['Codigo', 'Descricao', 'Prop3', 'Prop4', 'Prop107', 'Prop108', 'Prop16', 'Prop3_2', 'PropS', 'Peso'])
        with open(output_file, 'w', encoding='cp1252', errors='replace', newline='') as f:
            df.to_csv(f, sep=';', index=False, header=False)

    def _check_field_lengths(self, data: List[Dict], limit: int) -> List[str]:
        warnings: List[str] = []
        try:
            # Cabeçalho humano: linha 1. Dados iniciam em 1 (sem cabeçalho no arquivo final),
            # mas para exibição ao usuário, consideramos a primeira linha de dados como 1.
            for idx, row in enumerate(data, start=1):
                for key in ['Codigo', 'Descricao']:
                    text = str(row.get(key, ''))
                    if len(text) > limit:
                        warnings.append(f"Linha {idx}: {key} muito longo para Código {row.get('Codigo','')} (len={len(text)})")
                        break
        except Exception:
            pass
        return warnings
    
    def get_output_filename(self, request: ConversionRequest) -> str:
        """
        Gera nome do arquivo de saída para cadastro de peças.
        
        Args:
            request: Requisição de conversão
            
        Returns:
            Nome do arquivo de saída
        """
        import os
        # Allow overriding output directory via env (DEV mode)
        out_dir = os.environ.get('SOLID_OUTPUT_DIR')
        if out_dir and os.path.isdir(out_dir):
            directory = out_dir
        else:
            directory = os.path.dirname(request.input_file)
        # Include assembly code in filename and replace underscores with spaces
        assembly_code = getattr(request, 'assembly_code', '')
        if assembly_code:
            filename = f"CADASTRO DE PEÇAS {assembly_code}.csv"
        else:
            filename = "CADASTRO DE PEÇAS.csv"
        return os.path.join(directory, filename)

