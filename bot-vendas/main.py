"""Ponto de entrada do bot de vendas.

Inicializa configuração, banco, cliente WhatsApp, monitor de arquivo e o
painel web. O monitoramento roda em threads em segundo plano; o processo
principal serve o dashboard (ou apenas aguarda, se o dashboard estiver
desativado). Encerramento gracioso via SIGINT/SIGTERM.
"""
from __future__ import annotations

import argparse
import signal
import sys
import threading
from datetime import datetime, timezone

from config import Config
from database import Database
from dashboard import create_app
from logger import setup_logger
from parser import SalesParser
from watcher import SalesProcessor, SalesWatcher, Stats
from whatsapp import WhatsAppClient


def build_components(config: Config):
    logger = setup_logger(
        log_file=config.get("log_file", "bot_vendas.log"),
        level=config.get("log_level", "INFO"),
    )

    database = Database(config.get("database", "bot_vendas.db"))

    evo = config.get("evolution_api", {})
    whatsapp = WhatsAppClient(
        base_url=evo.get("base_url", "http://localhost:8080"),
        instance=evo.get("instance", "vendas"),
        api_key=evo.get("api_key", ""),
        recipient=evo.get("recipient", ""),
        dry_run=bool(evo.get("dry_run", False)),
        timeout=int(evo.get("timeout", 10)),
        logger=logger,
    )

    stats = Stats(started_at=datetime.now(timezone.utc).isoformat())
    parser = SalesParser(
        config.get("csv_file", "vendas.csv"),
        id_field=config.get("id_field", "id"),
    )
    processor = SalesProcessor(config, parser, database, whatsapp, logger, stats)
    watcher = SalesWatcher(
        processor,
        config.get("csv_file", "vendas.csv"),
        config.get("check_interval", 2),
        logger,
    )
    return logger, database, watcher, stats


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bot de notificação de vendas via WhatsApp")
    parser.add_argument(
        "-c", "--config", default="config.json", help="Caminho do arquivo de configuração"
    )
    parser.add_argument(
        "--no-dashboard", action="store_true", help="Executa sem o painel web"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = Config(args.config)
    logger, database, watcher, stats = build_components(config)

    stop_event = threading.Event()

    def handle_signal(signum, _frame):
        logger.info("Sinal %s recebido, encerrando...", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    watcher.start()
    logger.info("Bot de vendas iniciado.")

    dashboard_cfg = config.get("dashboard", {})
    run_dashboard = dashboard_cfg.get("enabled", True) and not args.no_dashboard

    try:
        if run_dashboard:
            app = create_app(config, database, stats)
            host = dashboard_cfg.get("host", "0.0.0.0")
            port = int(dashboard_cfg.get("port", 5000))
            logger.info("Painel disponível em http://%s:%s", host, port)

            server_thread = threading.Thread(
                target=lambda: app.run(
                    host=host, port=port, debug=False, use_reloader=False, threaded=True
                ),
                name="dashboard",
                daemon=True,
            )
            server_thread.start()

        stop_event.wait()
    finally:
        watcher.stop()
        database.close()
        logger.info("Bot de vendas encerrado.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
