"""Monitoramento contínuo do arquivo de vendas.

Combina duas estratégias:
- ``watchdog`` para reagir imediatamente a alterações no arquivo;
- um loop de *polling* de segurança (intervalo configurável) que garante o
  processamento mesmo em sistemas de arquivos onde eventos não são entregues
  de forma confiável (ex.: alguns volumes de rede/containers).

O processamento em si é idempotente: vendas já registradas no banco são
ignoradas, evitando notificações duplicadas.
"""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Any

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from config import Config
from database import Database
from parser import SalesParser
from whatsapp import WhatsAppClient


@dataclass
class Stats:
    """Estatísticas em memória compartilhadas com o dashboard."""

    started_at: str = ""
    messages_sent: int = 0
    errors: int = 0
    last_sale_id: int = 0
    last_event_at: str = ""
    running: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


def format_message(record: dict[str, Any], template: str) -> str:
    """Formata a mensagem substituindo {campo} pelas colunas da venda."""

    class _SafeDict(dict):
        def __missing__(self, key: str) -> str:  # noqa: D401
            return "-"

    safe = _SafeDict({k: ("" if v is None else v) for k, v in record.items()})
    try:
        return template.format_map(safe)
    except (ValueError, IndexError):
        # Template malformado: cai para uma representação simples.
        return "Nova venda: " + ", ".join(f"{k}={v}" for k, v in record.items())


class SalesProcessor:
    """Encapsula a lógica de detectar e notificar vendas novas."""

    def __init__(
        self,
        config: Config,
        parser: SalesParser,
        database: Database,
        whatsapp: WhatsAppClient,
        logger: logging.Logger,
        stats: Stats | None = None,
    ):
        self.config = config
        self.parser = parser
        self.database = database
        self.whatsapp = whatsapp
        self.logger = logger
        self.stats = stats or Stats()
        self._lock = threading.Lock()

    def process(self) -> int:
        """Processa vendas novas. Retorna quantas foram notificadas agora."""
        # Garante que apenas uma execução ocorra por vez (watchdog + polling).
        with self._lock:
            return self._process_locked()

    def _process_locked(self) -> int:
        id_field = self.config.get("id_field", "id")
        template = self.config.get("message_template", "Nova venda: {id}")

        try:
            records = self.parser.read()
        except Exception:  # noqa: BLE001 - leitura não pode derrubar o monitor
            self.logger.exception("Erro ao ler o arquivo de vendas")
            self.stats.errors += 1
            return 0

        records.sort(key=lambda item: item.get(id_field, 0))
        notified = 0

        for record in records:
            sale_id = record.get(id_field)
            if sale_id is None:
                continue
            if self.database.is_processed(sale_id):
                continue

            message = format_message(record, template)
            if self.whatsapp.send(message):
                self.database.mark_processed(sale_id, record)
                if sale_id > self.config.last_id:
                    self.config.last_id = sale_id
                self.stats.messages_sent += 1
                self.stats.last_sale_id = sale_id
                notified += 1
                self.logger.info("Venda %s notificada com sucesso.", sale_id)
            else:
                # Não marca como processada: será tentada novamente no próximo ciclo.
                self.stats.errors += 1
                self.logger.warning(
                    "Venda %s não pôde ser notificada; tentará novamente.", sale_id
                )
                # Interrompe para preservar a ordem e evitar avançar o last_id.
                break

        return notified


class _FileEventHandler(FileSystemEventHandler):
    def __init__(self, target_path: str, callback, logger: logging.Logger):
        self._target = os.path.abspath(target_path)
        self._callback = callback
        self._logger = logger

    def _handle(self, event) -> None:
        try:
            src = os.path.abspath(event.src_path)
        except (AttributeError, TypeError):
            return
        if src == self._target:
            self._callback()

    def on_modified(self, event) -> None:  # noqa: D401
        self._handle(event)

    def on_created(self, event) -> None:  # noqa: D401
        self._handle(event)

    def on_moved(self, event) -> None:  # noqa: D401
        # Editores costumam salvar via arquivo temporário + rename.
        dest = getattr(event, "dest_path", None)
        if dest and os.path.abspath(dest) == self._target:
            self._callback()


class SalesWatcher:
    """Monitora o arquivo de vendas e dispara o processamento."""

    def __init__(
        self,
        processor: SalesProcessor,
        csv_file: str,
        interval: float,
        logger: logging.Logger,
    ):
        self.processor = processor
        self.csv_file = csv_file
        self.interval = max(float(interval), 0.5)
        self.logger = logger
        self._stop = threading.Event()
        self._observer: Observer | None = None
        self._poll_thread: threading.Thread | None = None

    def _safe_process(self) -> None:
        try:
            self.processor.process()
        except Exception:  # noqa: BLE001
            self.logger.exception("Erro inesperado no processamento de vendas")

    def start(self) -> None:
        self.logger.info("Iniciando monitoramento de '%s'", self.csv_file)
        self.processor.stats.running = True

        # Processa o que já existe no arquivo antes de observar mudanças.
        self._safe_process()

        directory = os.path.dirname(os.path.abspath(self.csv_file)) or "."
        os.makedirs(directory, exist_ok=True)

        handler = _FileEventHandler(self.csv_file, self._safe_process, self.logger)
        self._observer = Observer()
        self._observer.schedule(handler, directory, recursive=False)
        self._observer.start()

        self._poll_thread = threading.Thread(
            target=self._poll_loop, name="sales-poll", daemon=True
        )
        self._poll_thread.start()

    def _poll_loop(self) -> None:
        while not self._stop.wait(self.interval):
            self._safe_process()

    def stop(self) -> None:
        self.logger.info("Encerrando monitoramento.")
        self._stop.set()
        self.processor.stats.running = False
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
        if self._poll_thread is not None:
            self._poll_thread.join(timeout=5)
