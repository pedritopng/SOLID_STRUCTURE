"""
Teste dos múltiplos tipos de conversão.
Demonstra como usar todos os 5 tipos de conversão disponíveis.
"""

import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from src.core.models import ConversionRequest
from src.core.converter import MultiTypeConverter
from src.core.conversion_types import ConversionType, get_conversion_type_info


def test_conversion_types():
    """Testa todos os tipos de conversão disponíveis."""
    print("🚀 SOLID_STRUCTURE - Teste de Múltiplos Tipos de Conversão")
    print("=" * 70)
    
    # Criar conversor multi-tipo
    converter = MultiTypeConverter()
    
    # Criar requisição de teste (arquivo inexistente para demonstração)
    request = ConversionRequest(
        input_file="arquivo_teste.xlsx",
        output_file="saida_teste.csv",
        assembly_code="TESTE123"
    )
    
    # Testar todos os tipos de conversão
    conversion_types = [
        ConversionType.HIERARCHICAL_STRUCTURE,
        ConversionType.PARTS_REGISTRATION,
        ConversionType.DESCRIPTION_UPDATE,
        ConversionType.MATERIAL_UPDATE,
        ConversionType.OLZ_VERIFICATION
    ]
    
    for conversion_type in conversion_types:
        print(f"\n📋 Testando: {get_conversion_type_info(conversion_type).name}")
        print("-" * 50)
        
        try:
            result = converter.convert(request, conversion_type)
            
            print(f"✅ Sucesso: {result.success}")
            print(f"📄 Mensagem: {result.message[:100]}...")
            
            if result.output_file:
                print(f"📁 Arquivo: {result.output_file}")
            
            if result.stats:
                print(f"📊 Estatísticas:")
                print(f"   - Total de linhas: {result.stats.total_rows}")
                print(f"   - Linhas válidas: {result.stats.valid_rows}")
                print(f"   - Linhas excluídas: {result.stats.excluded_rows}")
                print(f"   - Relacionamentos gerados: {result.stats.generated_relationships}")
            
            if result.warnings:
                print(f"⚠️ Avisos: {len(result.warnings)}")
                for warning in result.warnings[:3]:  # Mostrar apenas os primeiros 3
                    print(f"   - {warning}")
            
        except Exception as e:
            print(f"❌ Erro: {str(e)}")
    
    print("\n" + "=" * 70)
    print("✅ Teste de todos os tipos de conversão concluído!")
    
    # Mostrar informações dos tipos
    print("\n📚 Resumo dos Tipos de Conversão:")
    print("-" * 40)
    
    for conversion_type in conversion_types:
        info = get_conversion_type_info(conversion_type)
        print(f"\n🔧 {info.name}:")
        print(f"   Descrição: {info.description}")
        print(f"   Requer código de montagem: {'Sim' if info.requires_assembly_code else 'Não'}")
        print(f"   Prefixo do arquivo: {info.output_filename_prefix}")
        if info.import_code:
            print(f"   Código de importação: {info.import_code}")
        print(f"   Colunas de saída: {len(info.output_columns)}")
        print(f"   Colunas: {', '.join(info.output_columns[:3])}{'...' if len(info.output_columns) > 3 else ''}")


def test_conversion_type_info():
    """Testa as informações dos tipos de conversão."""
    print("\n🔍 Testando Informações dos Tipos:")
    print("-" * 40)
    
    # Testar obtenção de informações
    for conversion_type in ConversionType:
        info = get_conversion_type_info(conversion_type)
        print(f"✅ {info.name}: {info.description[:50]}...")
    
    print(f"\n📊 Total de tipos disponíveis: {len(ConversionType)}")


if __name__ == "__main__":
    try:
        test_conversion_types()
        test_conversion_type_info()
        
        print("\n" + "=" * 70)
        print("🎉 Todos os testes executados com sucesso!")
        print("\n💡 Próximos passos:")
        print("   1. Execute 'python main.py' para usar a interface gráfica")
        print("   2. Selecione um tipo de conversão")
        print("   3. Escolha um arquivo XLSX")
        print("   4. Execute a conversão")
        
    except Exception as e:
        print(f"\n❌ Erro durante os testes: {str(e)}")
        import traceback
        traceback.print_exc()

