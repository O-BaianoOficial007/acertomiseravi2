from __future__ import annotations

import logging
import sys
import tkinter as tk
from tkinter import messagebox

import dados
from interface import Aplicativo 

def configurar_log() -> None:
    try:
        dados.garantir_pastas()
        logging.basicConfig(
            filename=dados.ARQUIVO_LOG,
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            encoding="utf-8",
        )
    except Exception:
        logging.basicConfig(level=logging.INFO)


def main() -> int:
    configurar_log()
    raiz = tk.Tk()
    try:
        app = Aplicativo(raiz)
        if not app.iniciar():
            raiz.destroy()
            return 1
    except Exception:
        logging.getLogger(__name__).exception("Erro fatal ao iniciar")
        messagebox.showerror("Erro fatal", "Ocorreu um erro inesperado ao iniciar. Veja o arquivo de log.")
        raiz.destroy()
        return 1
    raiz.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
