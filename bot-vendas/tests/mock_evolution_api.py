"""Servidor simulado da Evolution API para testes ponta-a-ponta.

Expõe ``POST /message/sendText/<instance>`` e registra cada mensagem recebida
em um arquivo JSON-lines (padrão: ``received_messages.jsonl``). Também oferece
``GET /messages`` para inspecionar o que foi recebido.

Uso:
    python tests/mock_evolution_api.py --port 8080 --out received_messages.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

from flask import Flask, jsonify, request


def create_mock_app(out_path: str) -> Flask:
    app = Flask("mock_evolution_api")

    @app.route("/message/sendText/<instance>", methods=["POST"])
    def send_text(instance: str):
        body = request.get_json(silent=True) or {}
        record = {
            "instance": instance,
            "apikey": request.headers.get("apikey"),
            "number": body.get("number"),
            "text": body.get("text"),
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(out_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return jsonify({"status": "ok", "message": "queued"}), 201

    @app.route("/messages", methods=["GET"])
    def messages():
        if not os.path.exists(out_path):
            return jsonify([])
        with open(out_path, encoding="utf-8") as handle:
            return jsonify([json.loads(line) for line in handle if line.strip()])

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Mock da Evolution API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--out", default="received_messages.jsonl")
    args = parser.parse_args()

    # Começa limpo a cada execução.
    if os.path.exists(args.out):
        os.remove(args.out)

    app = create_mock_app(args.out)
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
