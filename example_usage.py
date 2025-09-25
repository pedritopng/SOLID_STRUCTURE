"""
Exemplo de uso da nova arquitetura SOLID_STRUCTURE.
Demonstra como usar os módulos separados programaticamente.
"""

import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from src.core.models import ConversionRequest, ConversionConfig
from src.core.converter import XLSXToCSVConverter
from src.core.validators import ValidationService


def exemplo_validacao():
    """Exemplo de como usar os validadores independentemente."""
    print("=== EXEMPLO DE VALIDAÇÃO ===")
    
    # Criar configuração personalizada
    config = ConversionConfig(
        max_file_size_mb=50,
        encoding='utf-8-sig'
    )
    
    # Criar serviço de validação
    validator = ValidationService(config)
    
    # Exemplo de validação de arquivo (arquivo inexistente)
    print("1. Validando arquivo inexistente:")
    result = validator.file_validator.validate_file_path("arquivo_inexistente.xlsx")
    print(f"   Válido: {result.is_valid}")
    print(f"   Erros: {result.errors}")
    
    # Exemplo de validação de código de montagem
    print("\n2. Validando código de montagem:")
    code_result = validator.assembly_validator.validate_assembly_code("ABC123")
    print(f"   Código 'ABC123' é válido: {code_result.is_valid}")
    
    code_result_invalid = validator.assembly_validator.validate_assembly_code("ABC@123")
    print(f"   Código 'ABC@123' é válido: {code_result_invalid.is_valid}")
    print(f"   Erros: {code_result_invalid.errors}")
    
    # Exemplo de sanitização de código
    print("\n3. Sanitizando códigos:")
    sanitized = validator.assembly_validator.sanitize_assembly_code("abc@123#")
    print(f"   'abc@123#' sanitizado: '{sanitized}'")


def exemplo_conversao():
    """Exemplo de como usar o conversor programaticamente."""
    print("\n=== EXEMPLO DE CONVERSÃO ===")
    
    # Criar requisição de conversão
    request = ConversionRequest(
        input_file="exemplo.xlsx",  # Arquivo que não existe, apenas para exemplo
        output_file="exemplo_saida.csv",
        assembly_code="TESTE123"
    )
    
    # Criar conversor
    converter = XLSXToCSVConverter()
    
    # Executar conversão
    print("1. Tentando converter arquivo inexistente:")
    result = converter.convert(request)
    
    print(f"   Sucesso: {result.success}")
    print(f"   Mensagem: {result.message}")
    
    if result.warnings:
        print(f"   Avisos: {result.warnings}")


def exemplo_configuracao_personalizada():
    """Exemplo de como personalizar a configuração."""
    print("\n=== EXEMPLO DE CONFIGURAÇÃO PERSONALIZADA ===")
    
    # Configuração personalizada
    config = ConversionConfig(
        required_columns=['ITEM', 'QTD', 'N° DESENHO', 'CODIGO MP20', 'COLUNA_EXTRA'],
        max_file_size_mb=200,
        supported_extensions=['.xlsx', '.xls', '.csv'],
        encoding='utf-8',
        separator=','
    )
    
    print("1. Configuração personalizada criada:")
    print(f"   Colunas obrigatórias: {config.required_columns}")
    print(f"   Tamanho máximo: {config.max_file_size_mb}MB")
    print(f"   Extensões suportadas: {config.supported_extensions}")
    print(f"   Codificação: {config.encoding}")
    print(f"   Separador: '{config.separator}'")


def exemplo_uso_com_funcao_compatibilidade():
    """Exemplo usando a função de compatibilidade."""
    print("\n=== EXEMPLO COM FUNÇÃO DE COMPATIBILIDADE ===")
    
    from src.core.converter import xlsx_to_parent_child_csv
    
    print("1. Usando função de compatibilidade:")
    success, message = xlsx_to_parent_child_csv(
        input_file="arquivo_inexistente.xlsx",
        output_file="saida.csv",
        assembly_code="COMPAT123"
    )
    
    print(f"   Sucesso: {success}")
    print(f"   Mensagem: {message}")


def main():
    """Função principal que executa todos os exemplos."""
    print("🚀 SOLID_STRUCTURE - Exemplos de Uso da Nova Arquitetura")
    print("=" * 60)
    
    try:
        exemplo_validacao()
        exemplo_conversao()
        exemplo_configuracao_personalizada()
        exemplo_uso_com_funcao_compatibilidade()
        
        print("\n" + "=" * 60)
        print("✅ Todos os exemplos executados com sucesso!")
        print("\n💡 Próximos passos:")
        print("   1. Execute 'python main.py' para usar a interface gráfica")
        print("   2. Consulte README_REFACTORING.md para mais detalhes")
        print("   3. Use os módulos individualmente conforme necessário")
        
    except Exception as e:
        print(f"\n❌ Erro ao executar exemplos: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
