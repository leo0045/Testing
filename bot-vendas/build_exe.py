"""Gera o executável do Bot de Vendas com o PyInstaller.

Atalho multiplataforma para ``pyinstaller bot_vendas.spec``. Também permite
gerar o executável do serviço do Windows (console) com ``--service``.

Exemplos:
    python build_exe.py            # gera a GUI (dist/BotVendas[.exe])
    python build_exe.py --service  # gera o serviço (dist/BotVendasService[.exe])

Observação: o PyInstaller NÃO faz compilação cruzada. Para gerar um ``.exe`` do
Windows, execute este script no Windows (ou sob Wine). Em Linux o resultado é
um binário ELF equivalente, útil para validar o empacotamento.
"""
from __future__ import annotations

import argparse
import os
import sys

import PyInstaller.__main__

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build do executável (PyInstaller)")
    parser.add_argument(
        "--service",
        action="store_true",
        help="Gera o executável do serviço do Windows em vez da GUI",
    )
    args = parser.parse_args()

    os.chdir(HERE)

    if args.service:
        pyinstaller_args = [
            "windows_service.py",
            "--name=BotVendasService",
            "--onefile",
            "--console",
            "--add-data=config.example.json{sep}.".format(sep=os.pathsep),
            "--add-data=vendas.example.csv{sep}.".format(sep=os.pathsep),
            "--collect-submodules=watchdog",
            "--noconfirm",
        ]
    else:
        pyinstaller_args = ["bot_vendas.spec", "--noconfirm"]

    print("Executando: pyinstaller", " ".join(pyinstaller_args))
    PyInstaller.__main__.run(pyinstaller_args)

    dist = os.path.join(HERE, "dist")
    print(f"\nConcluído. Executável(is) em: {dist}")
    if sys.platform != "win32":
        print(
            "Aviso: em sistemas não-Windows o binário gerado NÃO é um .exe do "
            "Windows. Rode este script no Windows para produzir o .exe."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
