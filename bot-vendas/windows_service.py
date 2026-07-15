"""Instalação e execução do Bot de Vendas como serviço do Windows.

Requer Windows + ``pywin32`` (``pip install pywin32``). Os imports do pywin32
são protegidos para que o módulo possa ser importado (e testado) em outros
sistemas operacionais sem erro.

Uso no Windows (prompt como Administrador):

    python windows_service.py install     # registra o serviço
    python windows_service.py start        # inicia
    python windows_service.py stop         # para
    python windows_service.py remove       # remove o serviço

Após gerar o .exe do serviço com PyInstaller, use ``BotVendasService.exe`` no
lugar de ``python windows_service.py``.

O diretório de trabalho do serviço é ajustado para a pasta do executável; o
arquivo de configuração pode ser sobrescrito pela variável de ambiente
``BOT_VENDAS_CONFIG``.
"""
from __future__ import annotations

import os
import sys

try:  # pywin32 só existe no Windows
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil

    _HAS_PYWIN32 = True
except ImportError:
    _HAS_PYWIN32 = False


if _HAS_PYWIN32:
    from app import BotApplication

    class BotVendasService(win32serviceutil.ServiceFramework):
        _svc_name_ = "BotVendas"
        _svc_display_name_ = "Bot de Vendas (WhatsApp)"
        _svc_description_ = (
            "Monitora o arquivo de vendas e envia notificações no WhatsApp "
            "via Evolution API."
        )

        def __init__(self, args):
            super().__init__(args)
            self._stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.application: BotApplication | None = None

        def SvcStop(self):  # noqa: N802 (assinatura exigida pelo pywin32)
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            if self.application is not None:
                self.application.stop()
            win32event.SetEvent(self._stop_event)

        def SvcDoRun(self):  # noqa: N802
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, ""),
            )
            base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            try:
                os.chdir(base_dir)
            except OSError:
                pass
            config_path = os.environ.get("BOT_VENDAS_CONFIG", "config.json")
            self.application = BotApplication(config_path)
            self.application.start(with_dashboard=True)
            win32event.WaitForSingleObject(self._stop_event, win32event.INFINITE)


def main() -> int:
    if not _HAS_PYWIN32:
        print(
            "Instalação como serviço do Windows requer Windows + pywin32.\n"
            "No Windows: pip install pywin32 e então:\n"
            "  python windows_service.py install|start|stop|remove"
        )
        return 1

    if len(sys.argv) == 1:
        # Executado pelo Gerenciador de Controle de Serviços do Windows.
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(BotVendasService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(BotVendasService)
    return 0


if __name__ == "__main__":
    sys.exit(main())
