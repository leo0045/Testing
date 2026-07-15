"""Configuração compartilhada dos testes.

Adiciona a raiz do projeto ao ``sys.path`` para que os módulos (``config``,
``parser``, etc.) possam ser importados diretamente nos testes.
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
