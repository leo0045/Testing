"""Persistência em SQLite usada para deduplicar notificações de vendas.

Cada venda notificada é registrada com sua ``sale_id`` como chave primária,
garantindo que nunca haja notificação duplicada, mesmo que o arquivo de vendas
seja reescrito ou reprocessado.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any


class Database:
    """Camada fina sobre o SQLite, segura para uso em múltiplas threads."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sales (
                    sale_id    INTEGER PRIMARY KEY,
                    payload    TEXT    NOT NULL,
                    notified   INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT    NOT NULL
                )
                """
            )
            self._conn.commit()

    def is_processed(self, sale_id: int) -> bool:
        """Indica se a venda já foi notificada com sucesso."""
        with self._lock:
            cursor = self._conn.execute(
                "SELECT notified FROM sales WHERE sale_id = ?", (sale_id,)
            )
            row = cursor.fetchone()
            return bool(row and row["notified"])

    def mark_processed(self, sale_id: int, payload: dict[str, Any]) -> None:
        """Registra (ou atualiza) a venda como notificada."""
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO sales (sale_id, payload, notified, created_at)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(sale_id) DO UPDATE SET notified = 1
                """,
                (
                    sale_id,
                    json.dumps(payload, ensure_ascii=False, default=str),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            self._conn.commit()

    def all_sales(self) -> list[dict[str, Any]]:
        """Retorna todas as vendas registradas, mais recentes primeiro."""
        with self._lock:
            cursor = self._conn.execute(
                """
                SELECT sale_id, payload, notified, created_at
                FROM sales ORDER BY sale_id DESC
                """
            )
            return [
                {
                    "sale_id": row["sale_id"],
                    "payload": json.loads(row["payload"]),
                    "notified": bool(row["notified"]),
                    "created_at": row["created_at"],
                }
                for row in cursor.fetchall()
            ]

    def count(self) -> int:
        """Quantidade de vendas notificadas com sucesso."""
        with self._lock:
            cursor = self._conn.execute(
                "SELECT COUNT(*) AS total FROM sales WHERE notified = 1"
            )
            return int(cursor.fetchone()["total"])

    def close(self) -> None:
        with self._lock:
            self._conn.close()
