"""Acesso ao banco SQLite."""
import os
import sqlite3

import pandas as pd
from flask import current_app, g


def caminho_db():
    return current_app.config["DATABASE"]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(caminho_db(), detect_types=0)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def fechar_db(_=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def q(sql, params=(), one=False):
    """Consulta -> lista de dicts (ou um dict)."""
    cur = get_db().execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    return (rows[0] if rows else None) if one else rows


def val(sql, params=()):
    r = get_db().execute(sql, params).fetchone()
    return r[0] if r else None


def df(sql, params=()):
    return pd.read_sql_query(sql, get_db(), params=params)


def exec_(sql, params=()):
    cur = get_db().execute(sql, params)
    return cur.lastrowid


def consulta_somente_leitura(sql, limite=5000):
    """Executa SQL do usuário numa conexão read-only."""
    uri = "file:" + os.path.abspath(caminho_db()) + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        cur = con.execute(sql)
        cols = [c[0] for c in cur.description] if cur.description else []
        linhas = cur.fetchmany(limite)
        return cols, linhas
    finally:
        con.close()


def param(chave):
    return val("SELECT valor FROM parametros WHERE chave = ?", (chave,))
