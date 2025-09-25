"""
Conversor para Verificação de Peças OLZ.
Baseado na macro "4 - VERIFICAÇÃO PEÇAS OLZ CADASTRADAS.bas"
"""

import pandas as pd
import logging
from typing import Dict, List, Any

from ..models import ConversionRequest, ConversionResult, ProcessingStats
from .base_converter import BaseConverter


class OLZVerificationConverter(BaseConverter):
    """
    Conversor para verificação de peças OLZ.
    
    Gera CSV com:
    - Coluna A: Código (sem "OL", "-" e " ")
    - Coluna B: Descrição
    - Coluna C: Status (CADASTRADA/NÃO CADASTRADA)
    - Coluna D: Observação
    """
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def convert(self, request: ConversionRequest) -> ConversionResult:
        """
        Converte para formato de verificação de peças OLZ.
        
        Args:
            request: Requisição de conversão
            
        Returns:
            ConversionResult com o resultado
        """
        try:
            # Ler arquivo Excel
            df = pd.read_excel(request.input_file)
            
            # Processar dados básicos (prepara utilitários e stats)
            _, item_to_code, _, stats = self.process_excel_data(df)

            # 1) Extrair todos os códigos OLZ únicos do arquivo de entrada
            input_olz_codes = self._extract_unique_olz_codes(df)

            # 2) Carregar planilha de referência (cadastrados)
            reference_codes = self._load_reference_olz_codes()

            # 3) Calcular faltantes (presentes no input e não encontrados na referência)
            missing_codes = sorted(list(input_olz_codes - reference_codes))

            output_file = None
            if missing_codes:
                # 4) Gerar arquivo completo com os faltantes (código + descrição + desenho original)
                missing_data = self._build_missing_olz_data(df, missing_codes)
                output_file = self._save_missing_olz_csv(missing_data, self.get_output_filename(request))
                stats.generated_relationships = len(missing_codes)
                success_message = (
                    f"Verificação OLZ concluída. Encontrados {len(input_olz_codes)} códigos OLZ no arquivo de entrada.\n"
                    f"Códigos NÃO localizados na planilha de referência: {len(missing_codes)}.\n"
                    f"Arquivo gerado com faltantes: {output_file}\n\n"
                    f"📋 Formato do arquivo:\n"
                    f"• Código OLZ\n"
                    f"• Descrição (CODIGO MP20)\n"
                    f"• N° Desenho original\n"
                    f"• Status: NÃO CADASTRADO"
                )
            else:
                stats.generated_relationships = 0
                success_message = (
                    f"Verificação OLZ concluída. {len(input_olz_codes)} códigos OLZ detectados no arquivo de entrada e todos constam na planilha de referência.\n"
                    f"Nenhum arquivo foi gerado."
                )

            return ConversionResult(True, success_message, output_file=output_file, stats=stats)
            
        except Exception as e:
            error_msg = f"Erro na conversão para verificação de peças OLZ: {str(e)}"
            self.logger.error(error_msg)
            return ConversionResult(False, error_msg)
    
    def _extract_unique_olz_codes(self, df: pd.DataFrame) -> set:
        """
        Extrai códigos OLZ únicos a partir do XLSX de entrada.
        """
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
            
            # Manter apenas códigos OLZ ('Z...')
            if code.startswith('Z'):
                processed_codes.add(code)
        return processed_codes

    def _load_reference_olz_codes(self) -> set:
        """Carrega a planilha de referência com os códigos OLZ cadastrados.
        Procura o arquivo através da variável de ambiente 'SOLID_OLZ_REFERENCE_FILE'.
        Se não definida, usa o caminho padrão: P:\GUINCHOS E GUINDASTES\OL1 - GERENCIAMENTO DE PROJETO\TODOS CADASTRADOS.csv
        Considera como coluna de código qualquer coluna cujo nome normalizado contenha 'codigo'/'código'/'cod'."""
        import os
        from pathlib import Path

        # 1) Fonte via variável de ambiente
        candidate = os.environ.get('SOLID_OLZ_REFERENCE_FILE')
        if not candidate:
            # 2) Caminho padrão da planilha de referência
            candidate = r"P:\GUINCHOS E GUINDASTES\OL1 - GERENCIAMENTO DE PROJETO\TODOS CADASTRADOS.csv"
        
        path: Path = None
        if candidate and Path(candidate).is_file():
            path = Path(candidate)

        codes = set()
        if not path:
            # Sem referência: retornar conjunto vazio (nenhum cadastrado) para que todos virem faltantes
            return codes

        try:
            # Tentar ler como CSV primeiro (caminho padrão é .csv)
            if str(path).lower().endswith('.csv'):
                ref_df = pd.read_csv(str(path), sep=';', encoding='utf-8-sig')
            else:
                ref_df = pd.read_excel(str(path))
            
            # Normalizar nomes de colunas
            norm = {self._normalize_header(c): c for c in ref_df.columns}
            code_col = None
            for key in ('codigo', 'código', 'cod'):
                if key in norm:
                    code_col = norm[key]
                    break
            if code_col is None:
                # fallback: primeira coluna
                code_col = ref_df.columns[0]
            for val in ref_df[code_col]:
                if pd.notna(val):
                    s = str(val).strip()
                    if s:
                        codes.add(s)
        except Exception:
            # Em caso de erro de leitura, retorna conjunto vazio
            return set()
        return codes
    
    def _build_missing_olz_data(self, df: pd.DataFrame, missing_codes: List[str]) -> List[Dict]:
        """
        Constrói dados completos para os códigos OLZ faltantes.
        
        Args:
            df: DataFrame original
            missing_codes: Lista de códigos OLZ que não foram encontrados na referência
            
        Returns:
            Lista de dicionários com dados completos dos faltantes
        """
        missing_data = []
        processed_codes = set()  # Para evitar duplicatas
        
        for index, row in df.iterrows():
            drawing_number = row['N° DESENHO']
            
            # Pular linhas com '^' (já processadas no data_processor)
            if pd.notna(drawing_number) and '^' in str(drawing_number):
                continue
            
            # Converter código
            code = self.data_processor.code_converter.convert_olg_code(drawing_number)
            if not code or not code.startswith('Z'):
                continue
            
            # Verificar se é um dos códigos faltantes
            if code not in missing_codes or code in processed_codes:
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
            
            # Criar registro completo
            missing_record = {
                'Codigo': code,
                'Descricao': description,
                'Desenho_Original': str(drawing_number) if pd.notna(drawing_number) else "",
                'Status': 'NÃO CADASTRADO'
            }
            
            missing_data.append(missing_record)
        
        return missing_data
    
    def _determine_registration_status(self, code: str, description: str) -> str:
        """
        Determina se a peça OLZ está cadastrada.
        
        Args:
            code: Código da peça
            description: Descrição da peça
            
        Returns:
            Status de cadastro
        """
        # Esta é uma implementação simulada
        # Em implementação real, compararia com arquivo de referência do sistema
        
        # Critérios simples para demonstração:
        if description and len(description) > 3:
            # Se tem descrição válida, assume que está cadastrada
            return 'CADASTRADA'
        else:
            return 'NÃO CADASTRADA'
    
    def _get_observation(self, status: str, code: str, description: str) -> str:
        """
        Gera observação baseada no status.
        
        Args:
            status: Status de cadastro
            code: Código da peça
            description: Descrição da peça
            
        Returns:
            Observação
        """
        if status == 'CADASTRADA':
            return 'Peça encontrada no sistema'
        else:
            if not description or description.strip() == "":
                return 'Descrição vazia - necessário cadastro'
            else:
                return 'Peça não encontrada no sistema'
    
    def _save_missing_olz_csv(self, missing_data: List[Dict], output_file: str) -> str:
        """
        Salva arquivo completo com os códigos OLZ não encontrados na referência.
        Retorna o caminho final gravado.
        """
        import os
        directory = os.path.dirname(output_file)
        # Extract assembly code from the output_file path (e.g., "VERIFICAÇÃO OLZ OLG08H2M2M.csv" -> "OLG08H2M2M")
        assembly_code = ""
        try:
            base_name = os.path.basename(output_file)
            if " " in base_name:
                # Extract the last part after the last space and before .csv
                parts = base_name.replace(".csv", "").split(" ")
                if len(parts) > 1:
                    assembly_code = parts[-1]
        except:
            pass
        
        if assembly_code:
            filename = f"OLZ FALTANTES {assembly_code}.csv"
        else:
            filename = "OLZ FALTANTES.csv"
        final_path = os.path.join(directory, filename)
        
        if not missing_data:
            # Criar arquivo vazio com cabeçalho
            df = pd.DataFrame(columns=['Codigo', 'Descricao', 'Desenho_Original', 'Status'])
        else:
            df = pd.DataFrame(missing_data)
        
        df.to_csv(final_path, sep=';', index=False, encoding='utf-8-sig', header=True)
        return final_path
    
    def get_output_filename(self, request: ConversionRequest) -> str:
        """
        Gera nome do arquivo de saída para verificação de peças OLZ.
        
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
            filename = f"VERIFICAÇÃO OLZ {assembly_code}.csv"
        else:
            filename = "VERIFICAÇÃO OLZ.csv"
        return os.path.join(directory, filename)

    @staticmethod
    def _sanitize_field(text: str) -> str:
        """Sanitiza campo de texto removendo quebras de linha e caracteres problemáticos."""
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

    @staticmethod
    def _normalize_header(name: str) -> str:
        s = str(name).strip().lower()
        # Remover acentos básicos
        import unicodedata
        s = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))
        s = s.replace(' ', '').replace('/', '')
        return s

