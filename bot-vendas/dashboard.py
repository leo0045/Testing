"""Painel web (Flask) para acompanhar o bot de vendas.

Exibe o status do monitor, estatísticas de envio e a lista de vendas já
notificadas. Os dados são atualizados automaticamente via chamadas às rotas
``/api/status`` e ``/api/sales``.
"""
from __future__ import annotations

from flask import Flask, jsonify, render_template_string

from config import Config
from database import Database
from watcher import Stats

_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bot de Vendas · Painel</title>
  <style>
    :root { color-scheme: light dark; }
    * { box-sizing: border-box; }
    body {
      margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background: #0f172a; color: #e2e8f0;
    }
    header {
      padding: 24px 32px; background: linear-gradient(135deg,#1e293b,#0f172a);
      border-bottom: 1px solid #1e293b;
    }
    header h1 { margin: 0; font-size: 22px; }
    header p { margin: 4px 0 0; color: #94a3b8; font-size: 14px; }
    .wrap { padding: 24px 32px; max-width: 1100px; margin: 0 auto; }
    .cards { display: grid; grid-template-columns: repeat(auto-fit,minmax(180px,1fr)); gap: 16px; }
    .card {
      background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 18px;
    }
    .card .label { font-size: 13px; color: #94a3b8; text-transform: uppercase; letter-spacing: .04em; }
    .card .value { font-size: 28px; font-weight: 700; margin-top: 6px; }
    .status-dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:6px; }
    .on { background:#22c55e; } .off { background:#ef4444; }
    table { width: 100%; border-collapse: collapse; margin-top: 12px; }
    th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid #334155; font-size: 14px; }
    th { color: #94a3b8; font-weight: 600; }
    h2 { margin-top: 32px; font-size: 18px; }
    tr:hover td { background: #16213a; }
    .badge { background:#064e3b; color:#6ee7b7; padding:2px 8px; border-radius:999px; font-size:12px; }
    footer { text-align:center; color:#64748b; padding:24px; font-size:12px; }
    code { background:#0b1220; padding:2px 6px; border-radius:6px; }
  </style>
</head>
<body>
  <header>
    <h1>🤖 Bot de Vendas — Painel de Controle</h1>
    <p>Monitorando <code id="csv">...</code> e notificando novas vendas via WhatsApp (Evolution API).</p>
  </header>
  <div class="wrap">
    <div class="cards">
      <div class="card"><div class="label">Status</div><div class="value"><span id="dot" class="status-dot off"></span><span id="running">--</span></div></div>
      <div class="card"><div class="label">Mensagens enviadas</div><div class="value" id="sent">0</div></div>
      <div class="card"><div class="label">Último ID</div><div class="value" id="last_id">0</div></div>
      <div class="card"><div class="label">Erros</div><div class="value" id="errors">0</div></div>
    </div>

    <h2>Vendas notificadas</h2>
    <table>
      <thead><tr><th>ID</th><th>Detalhes</th><th>Status</th><th>Registrado em (UTC)</th></tr></thead>
      <tbody id="rows"><tr><td colspan="4">Carregando...</td></tr></tbody>
    </table>
  </div>
  <footer>Atualização automática a cada 3 segundos.</footer>

  <script>
    async function refresh() {
      try {
        const [s, v] = await Promise.all([
          fetch('/api/status').then(r => r.json()),
          fetch('/api/sales').then(r => r.json()),
        ]);
        document.getElementById('csv').textContent = s.csv_file;
        document.getElementById('running').textContent = s.running ? 'Ativo' : 'Parado';
        document.getElementById('dot').className = 'status-dot ' + (s.running ? 'on' : 'off');
        document.getElementById('sent').textContent = s.messages_sent;
        document.getElementById('last_id').textContent = s.last_id;
        document.getElementById('errors').textContent = s.errors;

        const rows = v.map(item => {
          const p = item.payload || {};
          const details = Object.entries(p)
            .filter(([k]) => k !== 'id')
            .map(([k, val]) => `${k}: ${val}`).join(' · ');
          const status = item.notified ? '<span class="badge">Notificada</span>' : 'Pendente';
          return `<tr><td>${item.sale_id}</td><td>${details || '-'}</td><td>${status}</td><td>${item.created_at || '-'}</td></tr>`;
        });
        document.getElementById('rows').innerHTML = rows.length ? rows.join('') :
          '<tr><td colspan="4">Nenhuma venda notificada ainda.</td></tr>';
      } catch (e) {
        console.error(e);
      }
    }
    refresh();
    setInterval(refresh, 3000);
  </script>
</body>
</html>
"""


def create_app(config: Config, database: Database, stats: Stats) -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index():  # noqa: D401
        return render_template_string(_TEMPLATE)

    @app.route("/api/status")
    def status():  # noqa: D401
        return jsonify(
            {
                "running": stats.running,
                "messages_sent": stats.messages_sent,
                "errors": stats.errors,
                "last_id": config.last_id,
                "last_sale_id": stats.last_sale_id,
                "started_at": stats.started_at,
                "csv_file": config.get("csv_file"),
            }
        )

    @app.route("/api/sales")
    def sales():  # noqa: D401
        return jsonify(database.all_sales())

    @app.route("/health")
    def health():  # noqa: D401
        return jsonify({"status": "ok"})

    return app
