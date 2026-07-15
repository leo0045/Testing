"""Testes automatizados do bot de vendas."""
from __future__ import annotations

import logging

from config import Config
from database import Database
from parser import SalesParser
from watcher import SalesProcessor, Stats, format_message
from whatsapp import WhatsAppClient


def _write_csv(path, rows):
    header = "id,produto,quantidade,valor,cliente\n"
    path.write_text(header + "".join(rows), encoding="utf-8")


class FakeWhatsApp:
    """Cliente falso que captura as mensagens em vez de enviá-las."""

    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    def send(self, text, recipient=None):
        if self.fail:
            return False
        self.sent.append(text)
        return True


def build_processor(tmp_path, whatsapp, csv_name="vendas.csv"):
    config = Config(str(tmp_path / "config.json"))
    config._data["csv_file"] = str(tmp_path / csv_name)  # noqa: SLF001
    config._data["database"] = str(tmp_path / "bot.db")  # noqa: SLF001
    database = Database(config.get("database"))
    parser = SalesParser(config.get("csv_file"))
    logger = logging.getLogger("test")
    return config, database, SalesProcessor(
        config, parser, database, whatsapp, logger, Stats()
    )


def test_parser_reads_and_normalizes_ids(tmp_path):
    csv_file = tmp_path / "vendas.csv"
    _write_csv(csv_file, ["1,Notebook,1,3500,Joao\n", "2,Mouse,2,150,Maria\n"])
    records = SalesParser(str(csv_file)).read()
    assert [r["id"] for r in records] == [1, 2]
    assert records[0]["produto"] == "Notebook"
    assert isinstance(records[0]["id"], int)


def test_parser_skips_rows_without_id(tmp_path):
    csv_file = tmp_path / "vendas.csv"
    _write_csv(csv_file, ["1,Notebook,1,3500,Joao\n", ",SemID,1,10,Ninguem\n"])
    records = SalesParser(str(csv_file)).read()
    assert len(records) == 1


def test_parser_missing_file_returns_empty(tmp_path):
    assert SalesParser(str(tmp_path / "nao_existe.csv")).read() == []


def test_config_persists_last_id(tmp_path):
    path = tmp_path / "config.json"
    config = Config(str(path))
    config.last_id = 42
    assert Config(str(path)).last_id == 42


def test_database_dedup(tmp_path):
    db = Database(str(tmp_path / "bot.db"))
    assert db.is_processed(1) is False
    db.mark_processed(1, {"id": 1, "produto": "X"})
    assert db.is_processed(1) is True
    assert db.count() == 1
    db.mark_processed(1, {"id": 1, "produto": "X"})  # idempotente
    assert db.count() == 1


def test_format_message_handles_missing_fields():
    msg = format_message({"id": 5, "produto": "Café"}, "Venda {id}: {produto} / {cliente}")
    assert "Venda 5" in msg
    assert "Café" in msg
    assert "-" in msg  # {cliente} ausente vira '-'


def test_processor_notifies_new_sales_only_once(tmp_path):
    whatsapp = FakeWhatsApp()
    config, database, processor = build_processor(tmp_path, whatsapp)
    csv_file = tmp_path / "vendas.csv"

    _write_csv(csv_file, ["1,Notebook,1,3500,Joao\n", "2,Mouse,2,150,Maria\n"])
    assert processor.process() == 2
    assert len(whatsapp.sent) == 2
    assert config.last_id == 2

    # Reprocessar sem novas linhas não deve reenviar.
    assert processor.process() == 0
    assert len(whatsapp.sent) == 2

    # Nova linha adicionada -> apenas ela é notificada.
    with open(csv_file, "a", encoding="utf-8") as handle:
        handle.write("3,Teclado,1,420,Carlos\n")
    assert processor.process() == 1
    assert len(whatsapp.sent) == 3
    assert config.last_id == 3


def test_processor_retries_on_failure(tmp_path):
    whatsapp = FakeWhatsApp(fail=True)
    config, database, processor = build_processor(tmp_path, whatsapp)
    csv_file = tmp_path / "vendas.csv"
    _write_csv(csv_file, ["1,Notebook,1,3500,Joao\n"])

    assert processor.process() == 0
    assert config.last_id == 0
    assert database.is_processed(1) is False

    # Quando o envio passa a funcionar, a venda é notificada.
    whatsapp.fail = False
    assert processor.process() == 1
    assert database.is_processed(1) is True


def test_whatsapp_dry_run_does_not_call_network():
    client = WhatsAppClient(
        base_url="http://invalid.local",
        instance="x",
        api_key="k",
        recipient="5511999999999",
        dry_run=True,
    )
    assert client.send("mensagem de teste") is True


def test_whatsapp_http_send(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 201
        text = "ok"

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return FakeResponse()

    monkeypatch.setattr("whatsapp.requests.post", fake_post)
    client = WhatsAppClient(
        base_url="http://localhost:8080",
        instance="vendas",
        api_key="secret",
        recipient="5511999999999",
        dry_run=False,
    )
    assert client.send("oi") is True
    assert captured["url"] == "http://localhost:8080/message/sendText/vendas"
    assert captured["json"] == {"number": "5511999999999", "text": "oi"}
    assert captured["headers"]["apikey"] == "secret"
