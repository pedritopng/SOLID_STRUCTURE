"""
Configuração de logging para o sistema SOLID_STRUCTURE.
Implementa o princípio Single Responsibility Principle (SRP).
"""

import logging
import sys


def setup_logging():
    """
    Setup logging configuration.

    In frozen (packaged) builds, disable file logging and suppress output by
    elevating the level to CRITICAL so no log file is created.
    In development, log to stdout only.
    """
    root_logger = logging.getLogger()
    if root_logger.handlers:
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

    if getattr(sys, 'frozen', False):  # running as packaged EXE
        logging.basicConfig(level=logging.CRITICAL)
    else:  # development/run from source
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
    return logging.getLogger(__name__)
