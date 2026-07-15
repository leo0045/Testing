"""Interface gráfica (Tkinter) para configurar e operar o Bot de Vendas.

Permite configurar telefone de destino, pasta/arquivo monitorado e a Evolution
API, salvar tudo em ``config.json``, iniciar/parar o monitoramento, enviar uma
mensagem de teste, abrir o painel web e acompanhar os logs em tempo real.

Tkinter faz parte da biblioteca padrão do Python no Windows (usado para gerar o
.exe). Em Linux pode ser necessário instalar ``python3-tk``.
"""
from __future__ import annotations

import os
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

from app import BotApplication
from config import Config
from whatsapp import WhatsAppClient

APP_TITLE = "Bot de Vendas — Configuração"


class BotVendasGUI:
    def __init__(self, root: tk.Tk, config_path: str = "config.json"):
        self.root = root
        self.config_path = config_path
        self.config = Config(config_path)
        self.application: BotApplication | None = None
        self._log_pos = 0

        root.title(APP_TITLE)
        root.geometry("720x640")
        root.minsize(640, 560)

        self._build_widgets()
        self._load_into_fields()
        self._schedule_log_refresh()
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI
    def _build_widgets(self) -> None:
        pad = {"padx": 8, "pady": 4}
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        container = ttk.Frame(self.root, padding=12)
        container.pack(fill="both", expand=True)

        # --- Configurações gerais ---
        cfg = ttk.LabelFrame(container, text="Configuração", padding=10)
        cfg.pack(fill="x")
        cfg.columnconfigure(1, weight=1)

        self.var_phone = tk.StringVar()
        self.var_file = tk.StringVar()
        self.var_base_url = tk.StringVar()
        self.var_instance = tk.StringVar()
        self.var_api_key = tk.StringVar()
        self.var_port = tk.StringVar()
        self.var_interval = tk.StringVar()
        self.var_dry_run = tk.BooleanVar()

        ttk.Label(cfg, text="Telefone (destino):").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(cfg, textvariable=self.var_phone).grid(row=0, column=1, columnspan=2, sticky="ew", **pad)

        ttk.Label(cfg, text="Arquivo/pasta monitorada:").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(cfg, textvariable=self.var_file).grid(row=1, column=1, sticky="ew", **pad)
        ttk.Button(cfg, text="Procurar...", command=self._browse_file).grid(row=1, column=2, sticky="e", **pad)

        ttk.Label(cfg, text="Evolution API — URL:").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(cfg, textvariable=self.var_base_url).grid(row=2, column=1, columnspan=2, sticky="ew", **pad)

        ttk.Label(cfg, text="Evolution API — Instância:").grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(cfg, textvariable=self.var_instance).grid(row=3, column=1, columnspan=2, sticky="ew", **pad)

        ttk.Label(cfg, text="Evolution API — API Key:").grid(row=4, column=0, sticky="w", **pad)
        ttk.Entry(cfg, textvariable=self.var_api_key, show="*").grid(row=4, column=1, columnspan=2, sticky="ew", **pad)

        ttk.Label(cfg, text="Porta do painel:").grid(row=5, column=0, sticky="w", **pad)
        ttk.Entry(cfg, textvariable=self.var_port, width=10).grid(row=5, column=1, sticky="w", **pad)

        ttk.Label(cfg, text="Intervalo (s):").grid(row=6, column=0, sticky="w", **pad)
        ttk.Entry(cfg, textvariable=self.var_interval, width=10).grid(row=6, column=1, sticky="w", **pad)

        ttk.Checkbutton(
            cfg, text="Modo de teste (dry-run: não envia de verdade)",
            variable=self.var_dry_run,
        ).grid(row=7, column=0, columnspan=3, sticky="w", **pad)

        # --- Ações ---
        actions = ttk.Frame(container, padding=(0, 10))
        actions.pack(fill="x")
        ttk.Button(actions, text="Salvar configuração", command=self._save).pack(side="left", padx=4)
        self.btn_start = ttk.Button(actions, text="Iniciar", command=self._start)
        self.btn_start.pack(side="left", padx=4)
        self.btn_stop = ttk.Button(actions, text="Parar", command=self._stop, state="disabled")
        self.btn_stop.pack(side="left", padx=4)
        ttk.Button(actions, text="Enviar teste", command=self._send_test).pack(side="left", padx=4)
        ttk.Button(actions, text="Abrir painel", command=self._open_dashboard).pack(side="left", padx=4)

        # --- Status ---
        status = ttk.Frame(container)
        status.pack(fill="x")
        ttk.Label(status, text="Status:").pack(side="left")
        self.var_status = tk.StringVar(value="Parado")
        self.lbl_status = ttk.Label(status, textvariable=self.var_status, foreground="#b91c1c")
        self.lbl_status.pack(side="left", padx=6)

        # --- Logs ---
        logs = ttk.LabelFrame(container, text="Logs", padding=8)
        logs.pack(fill="both", expand=True, pady=(8, 0))
        self.txt_logs = tk.Text(logs, height=12, wrap="none", state="disabled",
                                background="#0b1220", foreground="#d1d5db")
        scroll = ttk.Scrollbar(logs, command=self.txt_logs.yview)
        self.txt_logs.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.txt_logs.pack(side="left", fill="both", expand=True)

    # -------------------------------------------------------------- helpers
    def _load_into_fields(self) -> None:
        data = self.config.data
        evo = data.get("evolution_api", {})
        dash = data.get("dashboard", {})
        self.var_phone.set(evo.get("recipient", ""))
        self.var_file.set(data.get("csv_file", "vendas.csv"))
        self.var_base_url.set(evo.get("base_url", ""))
        self.var_instance.set(evo.get("instance", ""))
        self.var_api_key.set(evo.get("api_key", ""))
        self.var_port.set(str(dash.get("port", 5000)))
        self.var_interval.set(str(data.get("check_interval", 2)))
        self.var_dry_run.set(bool(evo.get("dry_run", True)))

    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Selecione o arquivo de vendas",
            filetypes=[("Planilhas", "*.csv *.xlsx *.xls"), ("Todos", "*.*")],
        )
        if path:
            self.var_file.set(path)

    def _collect_config(self) -> dict:
        try:
            port = int(self.var_port.get())
        except ValueError:
            port = 5000
        try:
            interval = float(self.var_interval.get())
        except ValueError:
            interval = 2
        cfg = self.config.data
        cfg["csv_file"] = self.var_file.get().strip() or "vendas.csv"
        cfg["check_interval"] = interval
        cfg.setdefault("evolution_api", {})
        cfg["evolution_api"].update(
            {
                "recipient": self.var_phone.get().strip(),
                "base_url": self.var_base_url.get().strip(),
                "instance": self.var_instance.get().strip(),
                "api_key": self.var_api_key.get().strip(),
                "dry_run": bool(self.var_dry_run.get()),
            }
        )
        cfg.setdefault("dashboard", {})
        cfg["dashboard"]["port"] = port
        return cfg

    def _save(self) -> bool:
        cfg = self._collect_config()
        self.config._data = cfg  # noqa: SLF001
        self.config.save()
        messagebox.showinfo(APP_TITLE, "Configuração salva com sucesso.")
        return True

    def _start(self) -> None:
        if self.application and self.application.running:
            return
        self._save()
        try:
            self.application = BotApplication(self.config_path)
            self.application.start(with_dashboard=True)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(APP_TITLE, f"Falha ao iniciar: {exc}")
            return
        self.var_status.set("Rodando")
        self.lbl_status.configure(foreground="#15803d")
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")

    def _stop(self) -> None:
        if self.application:
            self.application.stop()
        self.var_status.set("Parado")
        self.lbl_status.configure(foreground="#b91c1c")
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")

    def _send_test(self) -> None:
        evo = self._collect_config()["evolution_api"]

        def worker():
            client = WhatsAppClient(
                base_url=evo.get("base_url", ""),
                instance=evo.get("instance", ""),
                api_key=evo.get("api_key", ""),
                recipient=evo.get("recipient", ""),
                dry_run=bool(evo.get("dry_run", True)),
            )
            ok = client.send("✅ Mensagem de teste do Bot de Vendas.")
            self.root.after(
                0,
                lambda: messagebox.showinfo(APP_TITLE, "Mensagem de teste enviada!")
                if ok
                else messagebox.showerror(APP_TITLE, "Falha ao enviar mensagem de teste."),
            )

        threading.Thread(target=worker, daemon=True).start()

    def _open_dashboard(self) -> None:
        try:
            port = int(self.var_port.get())
        except ValueError:
            port = 5000
        webbrowser.open(f"http://localhost:{port}")

    def _schedule_log_refresh(self) -> None:
        self._refresh_logs()
        self.root.after(1500, self._schedule_log_refresh)

    def _refresh_logs(self) -> None:
        log_file = self.config.get("log_file", "bot_vendas.log")
        if not os.path.exists(log_file):
            return
        try:
            with open(log_file, encoding="utf-8", errors="replace") as handle:
                handle.seek(self._log_pos)
                new_text = handle.read()
                self._log_pos = handle.tell()
        except OSError:
            return
        if new_text:
            self.txt_logs.configure(state="normal")
            self.txt_logs.insert("end", new_text)
            self.txt_logs.see("end")
            self.txt_logs.configure(state="disabled")

    def _on_close(self) -> None:
        try:
            if self.application:
                self.application.stop()
        finally:
            self.root.destroy()


def main() -> int:
    root = tk.Tk()
    BotVendasGUI(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
