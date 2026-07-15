"""Núcleo da aplicação compartilhado por CLI, GUI e serviço do Windows.

``BotApplication`` encapsula a montagem de todos os componentes (configuração,
banco, cliente WhatsApp, monitor de arquivo e painel web) e expõe ``start()`` /
``stop()`` idempotentes. O painel web é servido por um servidor WSGI
controlável (``werkzeug.make_server``), permitindo iniciar/parar em tempo de
execução — essencial para a GUI e o serviço.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from werkzeug.serving import make_server

from config import Config
from dashboard import create_app
from database import Database
from logger import setup_logger
from parser import SalesParser
from watcher import SalesProcessor, SalesWatcher, Stats
from whatsapp import WhatsAppClient


class _DashboardServer:
    """Servidor WSGI em thread, com parada controlada."""

    def __init__(self, host: str, port: int, wsgi_app, logger: logging.Logger):
        self._logger = logger
        self._server = make_server(host, port, wsgi_app, threaded=True)
        self._thread = threading.Thread(
            target=self._server.serve_forever, name="dashboard", daemon=True
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        try:
            self._server.shutdown()
            self._thread.join(timeout=5)
        except Exception:  # noqa: BLE001
            self._logger.exception("Erro ao encerrar o painel web")


class BotApplication:
    """Orquestra o bot de vendas de ponta a ponta."""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = Config(config_path)
        self.logger = setup_logger(
            log_file=self.config.get("log_file", "bot_vendas.log"),
            level=self.config.get("log_level", "INFO"),
        )
        self.stats = Stats(started_at="")
        self.database: Database | None = None
        self.watcher: SalesWatcher | None = None
        self._dashboard: _DashboardServer | None = None
        self._running = False
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self._running

    def _build(self) -> None:
        self.config.load()
        self.database = Database(self.config.get("database", "bot_vendas.db"))

        evo = self.config.get("evolution_api", {})
        whatsapp = WhatsAppClient(
            base_url=evo.get("base_url", "http://localhost:8080"),
            instance=evo.get("instance", "vendas"),
            api_key=evo.get("api_key", ""),
            recipient=evo.get("recipient", ""),
            dry_run=bool(evo.get("dry_run", False)),
            timeout=int(evo.get("timeout", 10)),
            logger=self.logger,
        )

        self.stats = Stats(started_at=datetime.now(timezone.utc).isoformat())
        parser = SalesParser(
            self.config.get("csv_file", "vendas.csv"),
            id_field=self.config.get("id_field", "id"),
        )
        processor = SalesProcessor(
            self.config, parser, self.database, whatsapp, self.logger, self.stats
        )
        self.watcher = SalesWatcher(
            processor,
            self.config.get("csv_file", "vendas.csv"),
            self.config.get("check_interval", 2),
            self.logger,
        )

    def start(self, with_dashboard: bool = True) -> None:
        with self._lock:
            if self._running:
                return
            self._build()
            assert self.watcher is not None
            self.watcher.start()

            dashboard_cfg = self.config.get("dashboard", {})
            if with_dashboard and dashboard_cfg.get("enabled", True):
                host = dashboard_cfg.get("host", "0.0.0.0")
                port = int(dashboard_cfg.get("port", 5000))
                wsgi_app = create_app(self.config, self.database, self.stats)
                self._dashboard = _DashboardServer(host, port, wsgi_app, self.logger)
                self._dashboard.start()
                self.logger.info("Painel disponível em http://%s:%s", host, port)

            self._running = True
            self.logger.info("Bot de vendas iniciado.")

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            if self._dashboard is not None:
                self._dashboard.stop()
                self._dashboard = None
            if self.watcher is not None:
                self.watcher.stop()
            if self.database is not None:
                self.database.close()
            self._running = False
            self.logger.info("Bot de vendas encerrado.")
