# Bot de Vendas — Notificações no WhatsApp via Evolution API

Sistema em Python que **monitora continuamente** um arquivo `vendas.csv` (ou
`.xlsx`) e, a cada nova venda adicionada, envia uma mensagem no **WhatsApp**
usando a **Evolution API**.

## Recursos

- Monitoramento contínuo do arquivo de vendas (`watchdog` + *polling* de segurança).
- Envio de mensagens via Evolution API (com modo `dry_run` para testes sem rede).
- **Deduplicação**: cada venda é notificada uma única vez (garantido por SQLite).
- Persistência do **último ID processado** em `config.json`.
- Execução em **segundo plano** com **logs rotacionados** e **tratamento de erros**.
- Configuração totalmente via arquivo **JSON**.
- **Painel web** (Flask) com status, estatísticas e histórico de vendas.

## Estrutura do projeto

```
bot-vendas/
├── main.py              # ponto de entrada (wiring + execução)
├── watcher.py           # monitora o arquivo e processa vendas novas
├── parser.py            # lê CSV/Excel
├── whatsapp.py          # cliente da Evolution API
├── config.py            # carga/persistência do config.json
├── database.py          # SQLite (deduplicação)
├── logger.py            # configuração de logs
├── dashboard.py         # painel web (Flask)
├── requirements.txt     # dependências de execução
├── requirements-dev.txt # dependências de desenvolvimento (pytest)
├── config.example.json  # modelo de configuração
├── vendas.example.csv   # exemplo de arquivo de vendas
└── README.md
```

## Instalação

Requer **Python 3.10+**.

```bash
cd bot-vendas

# (recomendado) ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

## Configuração

Copie o modelo e ajuste os valores:

```bash
cp config.example.json config.json
```

Campos principais de `config.json`:

| Campo | Descrição |
|-------|-----------|
| `csv_file` | Arquivo monitorado (`.csv` ou `.xlsx`). |
| `id_field` | Nome da coluna que identifica cada venda. |
| `check_interval` | Intervalo (s) do *polling* de segurança. |
| `last_id` | Último ID processado (atualizado automaticamente). |
| `message_template` | Modelo da mensagem; use `{coluna}` para interpolar. |
| `evolution_api.base_url` | URL da sua Evolution API. |
| `evolution_api.instance` | Nome da instância. |
| `evolution_api.api_key` | Chave da API (`apikey`). |
| `evolution_api.recipient` | Número de destino (ex.: `5511999999999`). |
| `evolution_api.dry_run` | `true` = apenas registra em log (não envia). |
| `dashboard.enabled/host/port` | Configuração do painel web. |

> **Importante:** deixe `dry_run: true` enquanto testa. Ao configurar as
> credenciais reais da Evolution API, altere para `false`.

## Formato do arquivo de vendas

A primeira linha é o cabeçalho. É obrigatório existir uma coluna de ID
(padrão `id`). Exemplo (`vendas.example.csv`):

```csv
id,produto,quantidade,valor,cliente
1,Notebook Dell,1,3500.00,João Silva
2,Mouse Logitech,2,150.00,Maria Souza
```

## Uso

```bash
# cria vendas.csv a partir do exemplo, se ainda não existir
cp -n vendas.example.csv vendas.csv

python3 main.py                 # inicia monitor + painel web
python3 main.py --no-dashboard  # apenas o monitor
python3 main.py -c outro.json   # usa outro arquivo de config
```

Adicione uma nova linha ao `vendas.csv` e a notificação é disparada
automaticamente:

```bash
echo "4,Monitor LG,1,1200.00,Ana Lima" >> vendas.csv
```

O painel fica disponível em `http://localhost:5000`.

## Executando em segundo plano

Com `nohup`:

```bash
nohup python3 main.py > bot.out 2>&1 &
```

Como serviço `systemd` (`/etc/systemd/system/bot-vendas.service`):

```ini
[Unit]
Description=Bot de Vendas (WhatsApp)
After=network.target

[Service]
WorkingDirectory=/caminho/para/bot-vendas
ExecStart=/caminho/para/bot-vendas/.venv/bin/python main.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now bot-vendas
```

## Testes

```bash
pip install -r requirements-dev.txt
pytest -v
```

Para um teste manual ponta-a-ponta sem uma Evolution API real, use o servidor
simulado incluído em `tests/mock_evolution_api.py` (registra as mensagens
recebidas) e aponte `evolution_api.base_url` para ele com `dry_run: false`.

## Como funciona a deduplicação

1. O parser lê todas as vendas do arquivo.
2. Para cada venda cujo ID ainda **não** está no SQLite, uma mensagem é enviada.
3. Em caso de sucesso, o ID é gravado no banco e `last_id` é atualizado em
   `config.json`.
4. Se o envio falhar, a venda **não** é marcada e será tentada novamente no
   próximo ciclo (preservando a ordem).
