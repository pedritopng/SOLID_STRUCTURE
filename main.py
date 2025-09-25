"""
Arquivo principal do sistema SOLID_STRUCTURE.
Orquestra a inicialização da aplicação seguindo os princípios SOLID.
"""

import tkinter as tk
import sys
import traceback
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from src.utils.logging_config import setup_logging
from src.gui.app import SOLIDStructureGUI


def main():
    """Função principal que inicializa a aplicação."""
    try:
        # Setup logging first
        logger = setup_logging()
        logger.info("Iniciando aplicação SOLID_STRUCTURE")
        
        # Initialize GUI
        root = tk.Tk()
        app = SOLIDStructureGUI(root)
        
        logger.info("Interface gráfica inicializada com sucesso")
        root.mainloop()
        
    except Exception as e:
        print(f"Erro crítico ao iniciar aplicação: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
