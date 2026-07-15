"""Carregamento e persistência de configuração via ``config.json``.

A configuração é lida de um arquivo JSON. Caso o arquivo não exista, ele é
criado automaticamente a partir dos valores padrão. O último ID de venda
processado (``last_id``) também é persistido neste arquivo, conforme o
requisito do projeto.
"""
from __future__ import annotations

import copy
import json
import os
import threading
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    # Arquivo monitorado (CSV ou Excel).
    "csv_file": "vendas.csv",
    # Nome da coluna que identifica unicamente cada venda.
    "id_field": "id",
    # Intervalo (segundos) do polling de segurança do monitor.
    "check_interval": 2,
    # Último ID processado (atualizado automaticamente pelo sistema).
    "last_id": 0,
    # Nível de log: DEBUG, INFO, WARNING, ERROR.
    "log_level": "INFO",
    "log_file": "bot_vendas.log",
    "database": "bot_vendas.db",
    # Modelo da mensagem. Use {campo} para interpolar colunas da venda.
    "message_template": (
        "🛒 *Nova venda registrada!*\n"
        "ID: {id}\n"
        "Produto: {produto}\n"
        "Quantidade: {quantidade}\n"
        "Valor: R$ {valor}\n"
        "Cliente: {cliente}"
    ),
    "evolution_api": {
        "base_url": "http://localhost:8080",
        "instance": "vendas",
        "api_key": "CHANGE_ME",
        "recipient": "5511999999999",
        # Em dry_run as mensagens são apenas registradas em log (sem rede).
        # Deixe true até configurar credenciais reais da Evolution API.
        "dry_run": True,
        "timeout": 10,
    },
    "dashboard": {
        "enabled": True,
        "host": "0.0.0.0",
        "port": 5000,
    },
}


class Config:
    """Wrapper thread-safe em torno do ``config.json``."""

    def __init__(self, path: str = "config.json"):
        self.path = path
        self._lock = threading.RLock()
        self._data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Carrega a configuração, criando o arquivo padrão se necessário."""
        with self._lock:
            if os.path.exists(self.path):
                with open(self.path, encoding="utf-8") as handle:
                    data = json.load(handle)
                self._data = self._merge(copy.deepcopy(DEFAULT_CONFIG), data)
            else:
                self._data = copy.deepcopy(DEFAULT_CONFIG)
                self.save()

    @staticmethod
    def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Mescla recursivamente ``override`` sobre ``base``."""
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                base[key] = Config._merge(base[key], value)
            else:
                base[key] = value
        return base

    def save(self) -> None:
        """Persiste a configuração de forma atômica."""
        with self._lock:
            tmp_path = f"{self.path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(self._data, handle, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.path)

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return copy.deepcopy(self._data.get(key, default))

    def __getitem__(self, key: str) -> Any:
        with self._lock:
            return copy.deepcopy(self._data[key])

    @property
    def last_id(self) -> int:
        with self._lock:
            return int(self._data.get("last_id", 0))

    @last_id.setter
    def last_id(self, value: int) -> None:
        with self._lock:
            self._data["last_id"] = int(value)
            self.save()

    @property
    def data(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._data)
