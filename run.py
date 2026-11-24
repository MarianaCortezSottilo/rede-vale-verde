"""Inicia o sistema do Supermercado Vale Verde em http://127.0.0.1:5000"""
import os
import subprocess
import sys

from app import create_app

RAIZ = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("VV_DB", os.path.join(RAIZ, "dados", "vale_verde.db"))

if __name__ == "__main__":
    if not os.path.exists(DB):
        print("Banco não encontrado — gerando 24 meses da rede fictícia (leva 1 a 2 minutos)...")
        subprocess.check_call([sys.executable, os.path.join(RAIZ, "gerador", "gerar_dados.py"), "--db", DB])
    app = create_app(DB)
    app.run(debug=os.environ.get("VV_DEBUG") == "1", port=int(os.environ.get("PORT", 5000)))
