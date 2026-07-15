"""Configuração de logging do bot de vendas.

Expõe uma função utilitária que cria um logger com saída simultânea para
arquivo (com rotação) e para o console. É seguro chamar múltiplas vezes: os
handlers só são adicionados uma vez por nome de logger.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logger(
    name: str = "bot_vendas",
    log_file: str = "bot_vendas.log",
    level: str | int = "INFO",
) -> logging.Logger:
    """Cria (ou recupera) um logger configurado.

    Args:
        name: nome do logger.
        log_file: caminho do arquivo de log rotacionado.
        level: nível de log (nome ou constante do módulo ``logging``).
    """
    logger = logging.getLogger(name)

    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(level)

    # Evita adicionar handlers duplicados em recarregamentos.
    if logger.handlers:
        return logger

    formatter = logging.Formatter(_FORMAT)

    file_handler = RotatingFileHandler(
        log_file, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.propagate = False
    return logger
