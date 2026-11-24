"""Visão de rede: comparativo de unidades, mapas (desempenho, clientes, logística, expansão) e franqueadora."""
import math
from datetime import date, timedelta

import numpy as np
import pandas as pd
from flask import Blueprint, abort, g, render_template, request

from . import exportar_excel
from . import relatorios as R
from .db import df, param, q, val
from .rotas_comercial import quer_excel, recs

bp = Blueprint("rede", __name__)

UF_IBGE = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO", "21": "MA", "22": "PI",
           "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
           "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF"}


def haversine(a, b, c, d):
    p1, p2 = math.radians(a), math.radians(c)
    h = math.sin(math.radians(c - a) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(d - b) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def ultimos12():
    cps = [c for c in R.competencias() if c <= R.ultima_competencia_fechada()]
    return cps[-12:], cps[-24:-12]


def indicadores_lojas():
    """Indicadores dos últimos 12 meses fechados para cada loja (base do comparativo e dos mapas)."""
    u12, a12 = ultimos12()
    d_ini, d_fim = R.limites(u12[0], u12[-1])
    a_ini, a_fim = (R.limites(a12[0], a12[-1]) if a12 else (None, None))
    info = R.unidades_info()
    lojas = info[info["tipo"] == "LOJA"].copy()
    ids = list(lojas["id"])
    P = R.ph(ids)
    v = df(f"""SELECT unidade_id id, SUM(valor_total) receita, SUM(cupons) cupons, SUM(custo_total) cmv,
                      SUM(cupons_fidelidade) fid, COUNT(DISTINCT data) dias
               FROM resumo_cupons_diario WHERE unidade_id IN ({P}) AND data BETWEEN ? AND ? GROUP BY 1""",
           (*ids, d_ini, d_fim))
    va = df(f"""SELECT unidade_id id, SUM(valor_total) receita_ant, COUNT(DISTINCT data) dias_ant
                FROM resumo_cupons_diario WHERE unidade_id IN ({P}) AND data BETWEEN ? AND ? GROUP BY 1""",
            (*ids, a_ini, a_fim)) if a_ini else pd.DataFrame(columns=["id", "receita_ant", "dias_ant"])
    res = R.resultado_por_unidade(u12, ids).rename(columns={"unidade_id": "id"})
    hc = df(f"""SELECT unidade_id id, COUNT(*) funcionarios FROM funcionarios WHERE data_demissao IS NULL
                AND unidade_id IN ({P}) GROUP BY 1""", tuple(ids))
    cli = df(f"""SELECT unidade_id id, COUNT(*) clientes, AVG(distancia_km) dist_media FROM clientes
                 WHERE unidade_id IN ({P}) GROUP BY 1""", tuple(ids))
    conc = df(f"""SELECT loja_referencia_id id, SUM(distancia_km <= 2) concorrentes_2km FROM concorrentes
                  WHERE loja_referencia_id IN ({P}) GROUP BY 1""", tuple(ids))
    t = lojas.merge(v, on="id", how="left").merge(va, on="id", how="left") \
        .merge(res[["id", "perdas", "folha", "ebitda", "lair", "lucro_liquido", "franquia", "margem_ebitda", "margem_lair"]],
               on="id", how="left").merge(hc, on="id", how="left").merge(cli, on="id", how="left").merge(conc, on="id", how="left")
    t["ticket"] = t["receita"] / t["cupons"]
    t["margem_bruta"] = 1 - t["cmv"] / t["receita"]
    t["perdas_pct"] = t["perdas"] / t["receita"]
    t["folha_pct"] = t["folha"] / t["receita"]
    t["receita_m2_ano"] = t["receita"] / t["area_m2"] * 365 / t["dias"]
    t["receita_checkout_mes"] = t["receita"] / t["checkouts"] / (t["dias"] / 30.4)
    t["receita_mensal"] = t["receita"] / (t["dias"] / 30.4)
    # crescimento same-store: só lojas com 12 meses completos nos dois períodos
    t["mesmas_lojas"] = (t["dias"] >= 350) & (t["dias_ant"].fillna(0) >= 350)
    t["crescimento"] = np.where(t["mesmas_lojas"], t["receita"] / t["receita_ant"] - 1, np.nan)
    t["fidelidade_pct"] = t["fid"] / t["cupons"]
    hoje = R.data_referencia()
    t["meses_operacao"] = [(hoje - date.fromisoformat(d)).days / 30.4 for d in t["data_inauguracao"]]
    return t, u12


@bp.route("/rede")
def rede():
    t, u12 = indicadores_lojas()
    info = R.unidades_info()
    cds = info[info["tipo"] == "CD"].copy()
    d_ini, d_fim = R.limites(u12[0], u12[-1])
    tr = df("""SELECT cd_id id, SUM(valor_transferencia) transferido, SUM(valor_transferencia - valor_custo_cd) margem,
                      SUM(custo_frete) frete, COUNT(DISTINCT loja_id) lojas, COUNT(*) envios
               FROM transferencias WHERE data_envio BETWEEN ? AND ? GROUP BY 1""", (d_ini, d_fim))
    cds = cds.merge(tr, on="id", how="left")
    uf = t.groupby(["uf", "regiao"]).agg(lojas=("id", "count"), receita=("receita", "sum"), populacao=("populacao", "sum"),
                                         lair=("lair", "sum")).reset_index()
    uf["receita_per_capita"] = uf["receita"] / uf["populacao"]
    reg = t.groupby("regiao").agg(lojas=("id", "count"), receita=("receita", "sum"), lair=("lair", "sum"),
                                  perdas=("perdas", "sum")).reset_index()
    reg["margem_lair"] = reg["lair"] / reg["receita"]
    reg["perdas_pct"] = reg["perdas"] / reg["receita"]
    modelo = t.groupby("modelo").agg(lojas=("id", "count"), receita=("receita", "sum"), lair=("lair", "sum"),
                                     area=("area_m2", "sum"), folha=("folha", "sum"), perdas=("perdas", "sum")).reset_index()
    if quer_excel():
        return exportar_excel({"lojas": t, "cds": cds, "estados": uf, "regioes": reg}, "comparativo_rede")
    cols = ["id", "codigo", "nome", "cidade", "uf", "regiao", "modelo", "lat", "lon", "receita", "receita_mensal", "crescimento",
            "ticket", "margem_bruta", "perdas_pct", "folha_pct", "margem_lair", "lair", "receita_m2_ano", "area_m2",
            "funcionarios", "clientes", "meses_operacao", "franqueado", "cd_codigo"]
    pontos = recs(t[cols])
    cd_pts = recs(cds[["id", "codigo", "nome", "cidade", "lat", "lon", "transferido", "margem", "frete", "lojas"]])
    sede = recs(info[info["tipo"] == "SEDE"][["codigo", "nome", "cidade", "lat", "lon"]])
    rede_tot = dict(receita=float(t["receita"].sum()), lojas=len(t), lair=float(t["lair"].sum()),
                    sss=float(t[t["mesmas_lojas"]]["receita"].sum() / t[t["mesmas_lojas"]]["receita_ant"].sum() - 1)
                    if t["mesmas_lojas"].any() else None, funcionarios=int(t["funcionarios"].sum()),
                    estados=int(t["uf"].nunique()))
    gr = dict(nomes=[f"{a} {b}" for a, b in zip(t["codigo"], t["cidade"])], receita=[round(x, 2) for x in t["receita"]],
              lair=[round(x * 100, 2) for x in t["margem_lair"]], modelo=list(t["modelo"]))
    return render_template("rede.html", t=recs(t.sort_values("receita", ascending=False)), cds=recs(cds), uf=recs(uf),
                           reg=recs(reg.sort_values("receita", ascending=False)), modelo=recs(modelo), pontos=pontos,
                           cd_pts=cd_pts, sede=sede, uf_dados={r["uf"]: r for r in recs(uf)}, UF_IBGE=UF_IBGE, tot=rede_tot,
                           u12=u12, g=gr)


# ---------------------------------------------------------------------------
@bp.route("/mapas/clientes")
def mapa_clientes():
    lojas = [u for u in g.unidades if u["tipo"] == "LOJA"]
    uid = request.args.get("loja", type=int) or (g.un_unica if g.un_unica in [l["id"] for l in lojas] else lojas[0]["id"])
    loja = R.unidades_info([uid]).iloc[0].to_dict()
    cl = df("""SELECT c.id, c.nome, c.bairro, c.lat, c.lon, c.distancia_km, c.data_cadastro, COUNT(v.id) compras,
                      COALESCE(SUM(v.valor_total),0) valor, MAX(v.data) ultima
               FROM clientes c LEFT JOIN vendas v ON v.cliente_id=c.id WHERE c.unidade_id=? GROUP BY c.id""", (uid,))
    faixas = [(0, 1, "até 1 km"), (1, 3, "1 a 3 km"), (3, 5, "3 a 5 km"), (5, 99, "mais de 5 km")]
    an = []
    tot_v, tot_c = cl["valor"].sum() or 1, len(cl) or 1
    ativos = cl[cl["compras"] > 0]
    for a, b, rot in faixas:
        s = cl[(cl["distancia_km"] >= a) & (cl["distancia_km"] < b)]
        sa = s[s["compras"] > 0]
        an.append(dict(faixa=rot, clientes=len(s), pct_clientes=len(s) / tot_c, valor=float(s["valor"].sum()),
                       pct_valor=float(s["valor"].sum() / tot_v), ticket=float(sa["valor"].sum() / max(sa["compras"].sum(), 1)),
                       freq=float(sa["compras"].mean()) if len(sa) else 0))
    raio80 = float(cl.sort_values("distancia_km").assign(acum=lambda x: x["valor"].cumsum() / tot_v)
                   .query("acum >= 0.8")["distancia_km"].min()) if len(cl) else None
    conc = df("SELECT nome, formato, lat, lon, area_m2, distancia_km FROM concorrentes WHERE loja_referencia_id=? ORDER BY distancia_km",
              (uid,))
    bairros = cl.groupby("bairro").agg(clientes=("id", "count"), valor=("valor", "sum"), dist=("distancia_km", "mean"),
                                       lat=("lat", "mean"), lon=("lon", "mean")).reset_index().sort_values("valor", ascending=False)
    bairros["pct_valor"] = bairros["valor"] / tot_v
    if quer_excel():
        return exportar_excel({"clientes": cl, "faixas": pd.DataFrame(an), "bairros": bairros, "concorrentes": conc},
                              f"area_influencia_{loja['codigo']}")
    periodo = q("SELECT MIN(data) ini, MAX(data) fim FROM vendas WHERE unidade_id=?", (uid,), one=True)
    pts = cl[["lat", "lon", "valor", "compras", "distancia_km"]].round(5).values.tolist()
    return render_template("mapa_clientes.html", loja=loja, lojas=lojas, uid=uid, pts=pts, conc=recs(conc), an=an,
                           bairros=recs(bairros), raio80=raio80, n=len(cl), ativos=len(ativos), periodo=periodo)


# ---------------------------------------------------------------------------
@bp.route("/mapas/logistica")
def mapa_logistica():
    u12, _ = ultimos12()
    d_ini, d_fim = R.limites(u12[0], u12[-1])
    info = R.unidades_info()
    rotas = df("""SELECT t.cd_id, t.loja_id, cd.codigo cd, lj.codigo loja, lj.nome loja_nome, cd.lat cd_lat, cd.lon cd_lon,
                         lj.lat loja_lat, lj.lon loja_lon, lj.distancia_cd_km km, lj.lead_time_cd_dias lead, lj.dias_pedido_cd,
                         COUNT(*) envios, SUM(t.viagens) viagens, SUM(t.valor_transferencia) valor, SUM(t.custo_frete) frete,
                         AVG(julianday(t.data_recebimento) - julianday(t.data_envio)) lead_real,
                         SUM(t.status='RECEBIDA_PARCIAL')*1.0/COUNT(*) pct_parcial
                  FROM transferencias t JOIN unidades cd ON cd.id=t.cd_id JOIN unidades lj ON lj.id=t.loja_id
                  WHERE t.data_envio BETWEEN ? AND ? GROUP BY t.loja_id ORDER BY cd.codigo, lj.codigo""", (d_ini, d_fim))
    rec = df("""SELECT unidade_id loja_id, SUM(valor_total) receita FROM resumo_cupons_diario
                WHERE data BETWEEN ? AND ? GROUP BY 1""", (d_ini, d_fim))
    rotas = rotas.merge(rec, on="loja_id", how="left")
    rotas["frete_pct_valor"] = rotas["frete"] / rotas["valor"]
    rotas["frete_pct_receita"] = rotas["frete"] / rotas["receita"]
    rotas["custo_por_viagem"] = rotas["frete"] / rotas["viagens"]
    cds = rotas.groupby(["cd_id", "cd"]).agg(lojas=("loja", "count"), valor=("valor", "sum"), frete=("frete", "sum"),
                                             viagens=("viagens", "sum")).reset_index()
    marg = df("""SELECT cd_id, SUM(valor_transferencia - valor_custo_cd) margem FROM transferencias
                 WHERE data_envio BETWEEN ? AND ? GROUP BY 1""", (d_ini, d_fim))
    cds = cds.merge(marg, on="cd_id", how="left")
    res_cd = R.resultado_por_unidade(u12, list(cds["cd_id"])).rename(columns={"unidade_id": "cd_id"})
    cds = cds.merge(res_cd[["cd_id", "ebitda", "lair"]], on="cd_id", how="left")
    forn = df("""SELECT f.id, f.nome_fantasia, f.abrangencia, f.regiao_atendida, f.cidade, f.uf, f.lat, f.lon, f.tipo,
                        SUM(p.valor_total) compras, COUNT(DISTINCT p.unidade_id) unidades, AVG(p.distancia_km) km,
                        GROUP_CONCAT(DISTINCT p.unidade_id) destinos
                 FROM fornecedores f LEFT JOIN pedidos_compra p ON p.fornecedor_id=f.id AND p.data_pedido BETWEEN ? AND ?
                 GROUP BY f.id""", (d_ini, d_fim))
    if quer_excel():
        return exportar_excel({"rotas_cd_loja": rotas, "cds": cds, "fornecedores": forn}, "logistica")
    unid = recs(info[["id", "codigo", "nome", "tipo", "modelo", "cidade", "lat", "lon"]])
    return render_template("mapa_logistica.html", rotas=recs(rotas), cds=recs(cds), forn=recs(forn), unid=unid, u12=u12,
                           frete_tot=float(rotas["frete"].sum()), valor_tot=float(rotas["valor"].sum()),
                           par=dict(fixo=param("frete_fixo_viagem"), km=param("frete_por_km"), cap=param("valor_por_viagem"),
                                    estrada=param("fator_estrada")))


# ---------------------------------------------------------------------------
@bp.route("/mapas/expansao")
def expansao():
    t, u12 = indicadores_lojas()
    maduras = t[t["meses_operacao"] >= 18].copy()
    # receita/m² ~ renda per capita (log-log) nas lojas maduras
    x, y = np.log(maduras["renda_per_capita"].values), np.log(maduras["receita_m2_ano"].values)
    b, a = np.polyfit(x, y, 1) if len(maduras) >= 3 else (0.4, float(np.log(t["receita_m2_ano"].median())))
    b = float(np.clip(b, 0.1, 1.2))
    a = float(np.mean(y - b * x)) if len(maduras) >= 3 else a
    hab_sup_rede = float((maduras["populacao"] / val("SELECT AVG(supermercados_concorrentes) FROM cidades")).median())
    cid = df("""SELECT c.* FROM cidades c WHERE c.id NOT IN (SELECT cidade_id FROM unidades)""")
    cds = R.unidades_info()
    cds = cds[cds["tipo"] == "CD"]
    linhas = []
    margem_ref = float(maduras["margem_lair"].median()) if len(maduras) else 0.03
    for r in cid.itertuples():
        dists = [(haversine(r.lat, r.lon, c.lat, c.lon) * param("fator_estrada"), c.codigo, c.nome) for c in cds.itertuples()]
        km, cdc, cdn = min(dists)
        hab_sup = r.populacao / max(r.supermercados_concorrentes, 1)
        f_conc = float(np.clip((hab_sup / 9000) ** 0.25, 0.8, 1.2))
        rec_m2 = math.exp(a + b * math.log(r.renda_per_capita)) * f_conc
        receita = rec_m2 * 1300
        frete = 104 * (param("frete_fixo_viagem") + param("frete_por_km") * km) * max(1, receita * 0.42 / 52 / param("valor_por_viagem"))
        frete_base = 104 * (param("frete_fixo_viagem") + param("frete_por_km") * 300)
        lucro = receita * margem_ref - (frete - frete_base)
        linhas.append(dict(id=r.id, nome=r.nome, uf=r.uf, regiao=r.regiao, lat=r.lat, lon=r.lon, populacao=r.populacao,
                           renda=r.renda_per_capita, concorrentes=r.supermercados_concorrentes, hab_por_super=hab_sup,
                           km_cd=km, cd=cdc, cd_nome=cdn, receita_est=receita, frete_est=frete, frete_pct=frete / receita,
                           lucro_est=lucro, payback_anos=4_500_000 / lucro if lucro > 0 else None))
    cand = pd.DataFrame(linhas)
    if quer_excel():
        return exportar_excel({"candidatas": cand, "lojas_atuais": t}, "expansao")
    lojas = recs(t[["codigo", "nome", "cidade", "lat", "lon", "modelo", "receita", "receita_m2_ano", "renda_per_capita"]])
    cd_pts = recs(cds[["codigo", "nome", "cidade", "lat", "lon"]])
    calib = dict(a=a, b=b, n=len(maduras), margem=margem_ref,
                 pontos=[dict(nome=f"{r.codigo} {r.cidade}", x=float(r.renda_per_capita), y=float(r.receita_m2_ano))
                         for r in maduras.itertuples()])
    return render_template("expansao.html", cand=recs(cand), lojas=lojas, cd_pts=cd_pts, calib=calib, u12=u12)


# ---------------------------------------------------------------------------
@bp.route("/franquia")
def franquia():
    u12, _ = ultimos12()
    rf = df("""SELECT competencia, tipo, SUM(valor) valor FROM receitas_franquia GROUP BY 1,2 ORDER BY 1""")
    piv = rf.pivot_table(index="competencia", columns="tipo", values="valor", aggfunc="sum").fillna(0)
    t, _ = indicadores_lojas()
    fr = df("""SELECT f.id franqueado_id, f.nome_fantasia franqueado, f.socio_responsavel, f.data_contrato, u.id, u.codigo,
                      u.cidade_id, u.data_inauguracao,
                      SUM(CASE WHEN rf.tipo='ROYALTIES' AND rf.competencia >= ? THEN rf.valor END) royalties_12m,
                      SUM(CASE WHEN rf.tipo='FUNDO_MARKETING' AND rf.competencia >= ? THEN rf.valor END) fundo_12m,
                      SUM(CASE WHEN rf.status='ABERTO' THEN rf.valor END) em_aberto
               FROM franqueados f JOIN unidades u ON u.franqueado_id=f.id LEFT JOIN receitas_franquia rf ON rf.loja_id=u.id
               GROUP BY f.id ORDER BY u.codigo""", (u12[0], u12[0]))
    fr = fr.merge(t[["id", "cidade", "receita", "margem_lair", "lair", "perdas_pct", "folha_pct", "crescimento"]], on="id", how="left")
    transf = df("""SELECT t.loja_id id, SUM(t.valor_transferencia) compras_cd FROM transferencias t
                   WHERE t.data_envio >= ? GROUP BY 1""", (u12[0] + "-01",))
    fr = fr.merge(transf, on="id", how="left")
    fr["pct_compras_cd"] = fr["compras_cd"] / (fr["receita"] * 0.7)
    # comparativo próprias x franqueadas
    comp = t.groupby("modelo").agg(lojas=("id", "count"), receita=("receita", "sum"), area=("area_m2", "sum"),
                                   lair=("lair", "sum"), perdas=("perdas", "sum"), folha=("folha", "sum"),
                                   cmv=("cmv", "sum"), cupons=("cupons", "sum")).reset_index()
    comp["receita_m2"] = comp["receita"] / comp["area"]
    comp["margem_bruta"] = 1 - comp["cmv"] / comp["receita"]
    comp["perdas_pct"] = comp["perdas"] / comp["receita"]
    comp["folha_pct"] = comp["folha"] / comp["receita"]
    comp["margem_lair"] = comp["lair"] / comp["receita"]
    comp["ticket"] = comp["receita"] / comp["cupons"]
    # resultado da franqueadora
    ids_fq = [u["id"] for u in g.unidades if u["tipo"] != "LOJA" or u["modelo"] == "PROPRIA"]
    dre_fq = R.dre(u12, ids_fq)["Total"]
    sede = [u["id"] for u in g.unidades if u["tipo"] == "SEDE"]
    cds = [u["id"] for u in g.unidades if u["tipo"] == "CD"]
    prop = [u["id"] for u in g.unidades if u["modelo"] == "PROPRIA"]
    blocos = []
    for nome, ids in (("Lojas próprias", prop), ("Centros de distribuição", cds), ("Sede (royalties e fundo)", sede)):
        d = R.dre(u12, ids)["Total"]
        blocos.append(dict(nome=nome, receita=float(d["receita_bruta"] + d["receitas_franquia"] + d["margem_distribuicao"]),
                           ebitda=float(d["ebitda"]), lair=float(d["lair"])))
    taxas = df("""SELECT rf.competencia, f.nome_fantasia, rf.valor FROM receitas_franquia rf JOIN franqueados f ON f.id=rf.franqueado_id
                  WHERE rf.tipo='TAXA_FRANQUIA' ORDER BY 1""")
    if quer_excel():
        return exportar_excel({"receitas_mensais": piv.reset_index(), "franqueados": fr, "proprias_x_franquias": comp}, "franquia")
    gr = dict(meses=[R.rotulo_mes(c) for c in piv.index], roy=[round(v, 2) for v in piv.get("ROYALTIES", [])],
              fundo=[round(v, 2) for v in piv.get("FUNDO_MARKETING", [])],
              taxa=[round(v, 2) for v in piv.get("TAXA_FRANQUIA", pd.Series(0, index=piv.index))])
    return render_template("franquia.html", fr=recs(fr), comp=recs(comp), blocos=blocos, dre_fq=dre_fq.to_dict(), g=gr,
                           taxas=recs(taxas), u12=u12, par=dict(roy=param("royalties_pct"), fundo=param("fundo_marketing_pct"),
                                                                 taxa=param("taxa_franquia"), markup=param("markup_transferencia")))


# ---------------------------------------------------------------------------
@bp.route("/unidades/<int:uid>")
def unidade(uid):
    info = R.unidades_info([uid])
    if info.empty:
        abort(404)
    u = info.iloc[0].to_dict()
    u12, _ = ultimos12()
    d = R.dre(u12, [uid])["Total"].to_dict()
    vm = R.vendas_mensais([uid]) if u["tipo"] == "LOJA" else pd.DataFrame()
    hc = val("SELECT COUNT(*) FROM funcionarios WHERE unidade_id=? AND data_demissao IS NULL", (uid,))
    est = val("SELECT SUM(quantidade*custo_medio) FROM estoque WHERE unidade_id=?", (uid,))
    conc = q("SELECT nome, formato, lat, lon, distancia_km FROM concorrentes WHERE loja_referencia_id=?", (uid,))
    atendidas = q("SELECT id, codigo, nome, lat, lon, distancia_cd_km FROM unidades WHERE cd_id=?", (uid,))
    cd = q("SELECT codigo, nome, lat, lon FROM unidades WHERE id=?", (u["cd_id"],), one=True) if u.get("cd_id") == u.get("cd_id") and u.get("cd_id") else None
    gr = dict(meses=[R.rotulo_mes(c) for c in vm["competencia"]] if len(vm) else [],
              receita=[round(x, 2) for x in vm["receita"]] if len(vm) else [])
    return render_template("unidade.html", u=u, d=d, hc=hc, est=est, conc=conc, atendidas=atendidas, cd=cd, g=gr, u12=u12)
