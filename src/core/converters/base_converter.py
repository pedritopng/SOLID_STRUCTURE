"""
Classe base para todos os conversores.
Implementa o princípio Dependency Inversion Principle (DIP).
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import pandas as pd

from ..models import ConversionRequest, ConversionResult, ProcessingStats
from ..data_processor import DataProcessor


class BaseConverter(ABC):
    """
    Classe base abstrata para todos os conversores.
    Define a interface comum que todos os conversores devem implementar.
    """
    
    def __init__(self):
        self.data_processor = DataProcessor()
    
    @abstractmethod
    def convert(self, request: ConversionRequest) -> ConversionResult:
        """
        Converte o arquivo XLSX para o formato específico.
        
        Args:
            request: Requisição de conversão
            
        Returns:
            ConversionResult com o resultado da conversão
        """
        pass
    
    @abstractmethod
    def get_output_filename(self, request: ConversionRequest) -> str:
        """
        Gera o nome do arquivo de saída baseado na requisição.
        
        Args:
            request: Requisição de conversão
            
        Returns:
            Nome do arquivo de saída
        """
        pass
    
    def process_excel_data(self, df: pd.DataFrame) -> tuple:
        """
        Processa os dados do Excel e retorna informações organizadas.
        
        Args:
            df: DataFrame com dados do Excel
            
        Returns:
            Tuple com (items_by_level, item_to_code, exclusion_records, stats)
        """
        return self.data_processor.process_excel_data(df)
    
    def create_stats(self, total_rows: int, valid_rows: int, excluded_rows: int) -> ProcessingStats:
        """
        Cria estatísticas de processamento.
        
        Args:
            total_rows: Total de linhas
            valid_rows: Linhas válidas
            excluded_rows: Linhas excluídas
            
        Returns:
            ProcessingStats com as estatísticas
        """
        return ProcessingStats(
            total_rows=total_rows,
            valid_rows=valid_rows,
            excluded_rows=excluded_rows,
            duplicate_rows=0,
            consolidated_rows=0,
            generated_relationships=valid_rows
        )

