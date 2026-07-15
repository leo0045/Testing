#!/usr/bin/env python3
"""Testes rápidos de parsing CSV/Excel e detecção de linhas novas."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

import monitor_vendas as mv


class TestParsing(unittest.TestCase):
    def test_csv_comma(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "vendas.csv"
            path.write_text(
                "produto,valor,vendedor\nNotebook,3500,Ana\nMouse,89.90,Bruno\n",
                encoding="utf-8",
            )
            rows = mv.read_csv_rows(path)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["produto"], "Notebook")
            self.assertEqual(rows[0]["valor"], "3500")
            self.assertEqual(rows[0]["vendedor"], "Ana")

    def test_csv_semicolon(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "vendas.csv"
            path.write_text(
                "produto;valor;vendedor\nTeclado;199;Carla\n",
                encoding="utf-8",
            )
            rows = mv.read_csv_rows(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["produto"], "Teclado")

    def test_excel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "planilha.xlsx"
            wb = Workbook()
            ws = wb.active
            ws.append(["Produto", "Valor", "Vendedor"])
            ws.append(["Monitor", 1200, "Diego"])
            wb.save(path)
            wb.close()
            rows = mv.read_excel_rows(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["produto"], "Monitor")
            self.assertEqual(rows[0]["vendedor"], "Diego")

    def test_message_format(self) -> None:
        msg = mv.format_message(
            {"produto": "SSD", "valor": "450", "vendedor": "Eva"}
        )
        self.assertIn("SSD", msg)
        self.assertIn("450", msg)
        self.assertIn("Eva", msg)

    def test_new_lines_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            watch = Path(tmp)
            csv_path = watch / "vendas.csv"
            csv_path.write_text(
                "produto,valor,vendedor\nA,10,X\n",
                encoding="utf-8",
            )
            monitor = mv.SalesMonitor(watch)
            baseline = len(monitor._seen[str(csv_path)])
            self.assertEqual(baseline, 1)

            csv_path.write_text(
                "produto,valor,vendedor\nA,10,X\nB,20,Y\n",
                encoding="utf-8",
            )
            # força processamento sem debounce
            monitor._last_processed.clear()
            sent: list[dict] = []

            original = mv.send_whatsapp

            def fake_send(sale: dict) -> bool:
                sent.append(sale)
                return True

            mv.send_whatsapp = fake_send  # type: ignore[assignment]
            try:
                monitor._process_file(csv_path)
            finally:
                mv.send_whatsapp = original  # type: ignore[assignment]

            self.assertEqual(len(sent), 1)
            self.assertEqual(sent[0]["produto"], "B")


if __name__ == "__main__":
    unittest.main()
