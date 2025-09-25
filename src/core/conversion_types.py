"""
Tipos de conversão disponíveis no sistema SOLID_STRUCTURE.
Implementa o princípio Single Responsibility Principle (SRP).
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Optional


class ConversionType(Enum):
    """Enumeração dos tipos de conversão disponíveis."""
    
    HIERARCHICAL_STRUCTURE = "hierarchical_structure"
    PARTS_REGISTRATION = "parts_registration"
    DESCRIPTION_UPDATE = "description_update"
    MATERIAL_UPDATE = "material_update"
    OLZ_VERIFICATION = "olz_verification"
    ALL_CONVERSIONS = "all_conversions"


@dataclass
class ConversionTypeInfo:
    """Informações sobre um tipo de conversão."""
    
    type: ConversionType
    name: str
    description: str
    output_columns: list
    requires_assembly_code: bool
    output_filename_prefix: str
    import_code: Optional[str] = None  # Código do importador no sistema NEO


# Configurações dos tipos de conversão
CONVERSION_TYPES: Dict[ConversionType, ConversionTypeInfo] = {
    ConversionType.HIERARCHICAL_STRUCTURE: ConversionTypeInfo(
        type=ConversionType.HIERARCHICAL_STRUCTURE,
        name="Estrutura Hierárquica",
        description="Gera CSV com relacionamentos pai-filho da estrutura de montagem",
        output_columns=["EMP", "MTG", "COD", "QTD", "PER"],
        requires_assembly_code=True,
        output_filename_prefix="ESTRUTURA",
        import_code=None
    ),
    
    ConversionType.PARTS_REGISTRATION: ConversionTypeInfo(
        type=ConversionType.PARTS_REGISTRATION,
        name="Cadastro de Peças e Montagens",
        description="Gera CSV para cadastrar peças e montagens no sistema",
        output_columns=["Codigo", "Descricao", "Prop3", "Prop4", "Prop107", "Prop108", "Prop16", "Prop3_2", "PropS", "Peso"],
        requires_assembly_code=False,
        output_filename_prefix="CADASTRO_PECAS",
        import_code="1"
    ),
    
    ConversionType.DESCRIPTION_UPDATE: ConversionTypeInfo(
        type=ConversionType.DESCRIPTION_UPDATE,
        name="Atualização de Descrições",
        description="Gera CSV para atualizar descrições dos componentes",
        output_columns=["Codigo", "Descricao"],
        requires_assembly_code=False,
        output_filename_prefix="ATUALIZACAO_DESCRICOES",
        import_code="7"
    ),
    
    ConversionType.MATERIAL_UPDATE: ConversionTypeInfo(
        type=ConversionType.MATERIAL_UPDATE,
        name="Atualização de Matéria Prima",
        description="Gera CSV para atualizar matéria prima de peças fabricadas",
        output_columns=["Empresa", "Codigo", "CodigoMP", "Peso", "Perda"],
        requires_assembly_code=False,
        output_filename_prefix="ATUALIZACAO_MATERIA_PRIMA",
        import_code=None
    ),
    
    ConversionType.OLZ_VERIFICATION: ConversionTypeInfo(
        type=ConversionType.OLZ_VERIFICATION,
        name="Verificação de Peças OLZ",
        description="Verifica se peças OLZ estão cadastradas no sistema",
        output_columns=["Codigo", "Descricao", "Status", "Observacao"],
        requires_assembly_code=False,
        output_filename_prefix="VERIFICACAO_OLZ",
        import_code=None
    ),
    
    ConversionType.ALL_CONVERSIONS: ConversionTypeInfo(
        type=ConversionType.ALL_CONVERSIONS,
        name="Todas as Conversões",
        description="Executa Cadastro, Descrições, Matéria Prima e depois Verificação OLZ",
        output_columns=[],
        requires_assembly_code=False,
        output_filename_prefix="TODAS",
        import_code=None
    )
}


def get_conversion_type_info(conversion_type: ConversionType) -> ConversionTypeInfo:
    """
    Obtém informações sobre um tipo de conversão.
    
    Args:
        conversion_type: Tipo de conversão
        
    Returns:
        ConversionTypeInfo com as informações do tipo
    """
    return CONVERSION_TYPES[conversion_type]


def get_all_conversion_types() -> Dict[ConversionType, ConversionTypeInfo]:
    """
    Obtém todos os tipos de conversão disponíveis.
    
    Returns:
        Dicionário com todos os tipos de conversão
    """
    return CONVERSION_TYPES.copy()


def get_conversion_types_for_gui() -> list:
    """
    Obtém lista formatada dos tipos de conversão para uso na interface gráfica.
    
    Returns:
        Lista de tuplas (nome, descrição, tipo)
    """
    # Ordem específica para layout 2 colunas (3 à esquerda, 3 à direita):
    # Esquerda: Hierárquica, Cadastro, OLZ | Direita: Descrições, Matéria Prima, Todas
    ordered_types = [
        ConversionType.HIERARCHICAL_STRUCTURE,
        ConversionType.PARTS_REGISTRATION,
        ConversionType.OLZ_VERIFICATION,
        ConversionType.DESCRIPTION_UPDATE,
        ConversionType.MATERIAL_UPDATE,
        ConversionType.ALL_CONVERSIONS,
    ]
    return [
        (
            CONVERSION_TYPES[t].name,
            CONVERSION_TYPES[t].description,
            t
        )
        for t in ordered_types
    ]

