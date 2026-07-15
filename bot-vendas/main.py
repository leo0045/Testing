"""Ponto de entrada de linha de comando do bot de vendas.

Inicia o monitoramento e o painel web em segundo plano e aguarda até receber
um sinal de término (SIGINT/SIGTERM), encerrando de forma graciosa.
"""
from __future__ import annotations

import argparse
import signal
import sys
import threading

from app import BotApplication


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bot de notificação de vendas via WhatsApp (Evolution API)"
    )
    parser.add_argument(
        "-c", "--config", default="config.json", help="Caminho do arquivo de configuração"
    )
    parser.add_argument(
        "--no-dashboard", action="store_true", help="Executa sem o painel web"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    application = BotApplication(args.config)

    stop_event = threading.Event()

    def handle_signal(signum, _frame):
        application.logger.info("Sinal %s recebido, encerrando...", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    application.start(with_dashboard=not args.no_dashboard)
    try:
        stop_event.wait()
    finally:
        application.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
