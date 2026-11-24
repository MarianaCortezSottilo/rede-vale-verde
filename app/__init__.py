"""Rede Vale Verde — sistema de gestão integrado da franquia (empresa fictícia)."""
import io
import os
from datetime import date

from flask import Flask, g, request, send_file, session

from . import db

SELECOES = {
    "rede": "Rede (todas as lojas)",
    "proprias": "Lojas próprias",
    "franquias": "Lojas franqueadas",
    "franqueadora": "Franqueadora (próprias + CDs + sede)",
    "tudo": "Todas as unidades",
}


def create_app(caminho_db=None):
    app = Flask(__name__)
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app.config["DATABASE"] = caminho_db or os.environ.get("VV_DB", os.path.join(raiz, "dados", "vale_verde.db"))
    app.config["SECRET_KEY"] = "vale-verde-ficticio"
    app.config["JSON_AS_ASCII"] = False
    app.teardown_appcontext(db.fechar_db)
    registrar_filtros(app)

    from .rotas_comercial import bp as bp_com
    from .rotas_financeiro import bp as bp_fin
    from .rotas_rh import bp as bp_rh
    from .rotas_extra import bp as bp_ext
    from .rotas_rede import bp as bp_rede
    for bp in (bp_com, bp_fin, bp_rh, bp_ext, bp_rede):
        app.register_blueprint(bp)

    @app.before_request
    def resolver_unidades():
        """Seleção global de unidades (?u=rede|proprias|franquias|franqueadora|tudo|<id>), guardada na sessão."""
        if request.endpoint == "static":
            return
        if "u" in request.args:
            session["u"] = request.args["u"]
        sel = session.get("u", "rede")
        try:
            unidades = db.q("SELECT id, codigo, nome, tipo, modelo FROM unidades ORDER BY tipo DESC, codigo")
        except Exception:
            unidades = []
        g.unidades = unidades
        por_id = {u["id"]: u for u in unidades}
        if sel.isdigit() and int(sel) in por_id:
            ids = [int(sel)]
            rotulo = f"{por_id[int(sel)]['codigo']} · {por_id[int(sel)]['nome']}"
        else:
            if sel not in SELECOES:
                sel = "rede"
            filtro = {
                "rede": lambda u: u["tipo"] == "LOJA",
                "proprias": lambda u: u["tipo"] == "LOJA" and u["modelo"] == "PROPRIA",
                "franquias": lambda u: u["tipo"] == "LOJA" and u["modelo"] == "FRANQUIA",
                "franqueadora": lambda u: u["tipo"] != "LOJA" or u["modelo"] == "PROPRIA",
                "tudo": lambda u: True,
            }[sel]
            ids = [u["id"] for u in unidades if filtro(u)]
            rotulo = SELECOES[sel]
        g.sel = sel
        g.un = ids or [0]
        g.un_lojas = [i for i in ids if por_id[i]["tipo"] == "LOJA"] or [0]
        g.un_unica = ids[0] if len(ids) == 1 else None
        g.un_rotulo = rotulo
        g.por_id = por_id

    @app.context_processor
    def contexto():
        from .relatorios import competencias, rotulo_mes
        try:
            emp = db.q("SELECT nome_fantasia, cidade, uf FROM empresa", one=True)
            comps = competencias()
        except Exception:
            emp, comps = None, []
        chart_local = os.path.exists(os.path.join(app.static_folder, "chart.umd.min.js"))
        return dict(empresa=emp, todas_comps=comps, rotulo_mes=rotulo_mes, hoje=date.today(), args=request.args,
                    chart_local=chart_local, SELECOES=SELECOES, sel=getattr(g, "sel", "rede"),
                    unidades=getattr(g, "unidades", []), un_rotulo=getattr(g, "un_rotulo", ""),
                    un_unica=getattr(g, "un_unica", None))

    return app


# ---------------------------------------------------------------------------
def brl(v, casas=2):
    if v is None or v != v:
        return "–"
    s = f"{abs(v):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-R$ " if v < 0 else "R$ ") + s


def num(v, casas=0):
    if v is None or v != v:
        return "–"
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v, casas=1, sinal=False):
    if v is None or v != v:
        return "–"
    s = f"{v * 100:+.{casas}f}" if sinal else f"{v * 100:.{casas}f}"
    return s.replace(".", ",") + "%"


def data_br(s):
    if not s:
        return "–"
    s = str(s)
    return f"{s[8:10]}/{s[5:7]}/{s[0:4]}" + (s[10:16] if len(s) > 10 else "")


def mil(v):
    if v is None or v != v:
        return "–"
    a = abs(v)
    if a >= 1e6:
        return brl(v / 1e6, 2) + " mi"
    if a >= 1e3:
        return brl(v / 1e3, 0) + " mil"
    return brl(v, 0)


def registrar_filtros(app):
    app.jinja_env.filters.update(brl=brl, num=num, pct=pct, data_br=data_br, mil=mil)


def exportar_excel(frames, nome):
    import pandas as pd
    if not isinstance(frames, dict):
        frames = {"dados": frames}
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for aba, d in frames.items():
            d.to_excel(w, sheet_name=aba[:31], index=False)
            ws = w.sheets[aba[:31]]
            for col in ws.columns:
                largura = max(len(str(c.value or "")) for c in col[:200])
                ws.column_dimensions[col[0].column_letter].width = min(max(10, largura + 2), 60)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=f"{nome}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
