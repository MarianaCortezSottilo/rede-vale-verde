"""Projeções, consulta SQL, cadastros e dicionário de dados."""
import json

import pandas as pd
from flask import Blueprint, render_template, request

from . import exportar_excel
from . import relatorios as R
from .db import consulta_somente_leitura, df, get_db, q, val
from .rotas_comercial import quer_excel, recs

bp = Blueprint("ext", __name__)


@bp.route("/projecoes")
def projecoes():
    n = int(request.args.get("meses", 12))
    if not R.vendas_mensais().shape[0]:
        return render_template("vazio.html", msg="Projeções precisam de lojas na seleção.")
    p = R.projetar_receita(n)
    bt = R.backtest(6)
    base = R.bases_projecao()
    proj = p["projecao"]
    if quer_excel():
        return exportar_excel({"projecao": proj, "ajuste_historico": p["ajuste"], "backtest": bt,
                               "premissas": pd.DataFrame([{k: v for k, v in (base or {}).items() if k != "competencias"}])},
                              "projecoes")
    hist = p["historico"]
    gr = dict(meses=[R.rotulo_mes(c) for c in hist["competencia"]] + [R.rotulo_mes(c) for c in proj["competencia"]],
              real=[round(v, 2) for v in hist["receita"]] + [None] * len(proj),
              proj=[None] * (len(hist) - 1) + [round(float(hist["receita"].iloc[-1]), 2)] + [round(v, 2) for v in proj["receita"]],
              inf=[None] * len(hist) + [round(v, 2) for v in proj["inferior"]],
              sup=[None] * len(hist) + [round(v, 2) for v in proj["superior"]],
              saz=list(p["sazonalidade"].keys()), saz_v=[round(v * 100, 1) for v in p["sazonalidade"].values()])
    hc = R.headcount_mensal()
    hc_medio = float(hc[hc["competencia"].isin(base["competencias"])]["headcount"].mean()) if base else 1
    sim = dict(comps=list(proj["competencia"]), rotulos=[R.rotulo_mes(c) for c in proj["competencia"]],
               receita=[round(v, 2) for v in proj["receita"]], base=base, hc=round(hc_medio, 1))
    erro_bt = float(bt["erro_pct"].abs().mean()) if len(bt) else None
    return render_template("projecoes.html", p=p, proj=recs(proj), bt=recs(bt), base=base, g=gr, sim=json.dumps(sim), n=n,
                           erro_bt=erro_bt)


EXEMPLOS = [
    ("Faturamento por loja e mês",
     """SELECT u.codigo, u.nome, substr(r.data,1,7) AS mes, ROUND(SUM(r.valor_total),2) AS faturamento,
       SUM(r.cupons) AS cupons, ROUND(SUM(r.valor_total)/SUM(r.cupons),2) AS ticket
FROM resumo_cupons_diario r JOIN unidades u ON u.id = r.unidade_id
GROUP BY u.id, mes ORDER BY mes, faturamento DESC;"""),
    ("Faturamento por estado e região (para mapas)",
     """SELECT c.regiao, c.uf, COUNT(DISTINCT u.id) AS lojas, ROUND(SUM(r.valor_total),2) AS faturamento_12m,
       ROUND(SUM(r.valor_total) / c.populacao, 2) AS faturamento_per_capita
FROM resumo_cupons_diario r JOIN unidades u ON u.id = r.unidade_id JOIN cidades c ON c.id = u.cidade_id
WHERE r.data >= date((SELECT MAX(data) FROM resumo_cupons_diario), '-365 days')
GROUP BY c.uf ORDER BY faturamento_12m DESC;"""),
    ("Same-store sales: crescimento das lojas com mais de 13 meses",
     """WITH m AS (SELECT unidade_id, substr(data,1,7) mes, SUM(valor_total) fat FROM resumo_cupons_diario GROUP BY 1,2)
SELECT u.codigo, a.mes, ROUND(a.fat,2) faturamento, ROUND(b.fat,2) ano_anterior, ROUND(a.fat/b.fat - 1, 4) crescimento
FROM m a JOIN m b ON b.unidade_id = a.unidade_id
 AND b.mes = printf('%04d-%s', CAST(substr(a.mes,1,4) AS INT) - 1, substr(a.mes,6,2))
JOIN unidades u ON u.id = a.unidade_id ORDER BY a.mes, u.codigo;"""),
    ("Royalties e fundo de marketing por franqueado",
     """SELECT f.nome_fantasia AS franqueado, u.codigo AS loja, rf.tipo,
       ROUND(SUM(rf.valor),2) AS valor, SUM(rf.status = 'ABERTO') AS titulos_em_aberto
FROM receitas_franquia rf JOIN unidades u ON u.id = rf.loja_id LEFT JOIN franqueados f ON f.id = rf.franqueado_id
GROUP BY 1, 2, 3 ORDER BY 1, 3;"""),
    ("Custo de frete por loja (transferências do CD)",
     """SELECT cd.codigo AS cd, lj.codigo AS loja, lj.distancia_cd_km AS km, COUNT(*) AS envios,
       ROUND(SUM(t.valor_transferencia),2) AS valor_transferido, ROUND(SUM(t.custo_frete),2) AS frete,
       ROUND(SUM(t.custo_frete) / SUM(t.valor_transferencia), 4) AS frete_sobre_valor
FROM transferencias t JOIN unidades cd ON cd.id = t.cd_id JOIN unidades lj ON lj.id = t.loja_id
GROUP BY t.loja_id ORDER BY frete_sobre_valor DESC;"""),
    ("Área de influência: faturamento por faixa de distância do cliente",
     """SELECT u.codigo,
       CASE WHEN c.distancia_km < 1 THEN '0-1 km' WHEN c.distancia_km < 3 THEN '1-3 km'
            WHEN c.distancia_km < 5 THEN '3-5 km' ELSE '5+ km' END AS faixa,
       COUNT(DISTINCT c.id) AS clientes, COUNT(v.id) AS cupons, ROUND(SUM(v.valor_total),2) AS valor
FROM clientes c JOIN unidades u ON u.id = c.unidade_id LEFT JOIN vendas v ON v.cliente_id = c.id
GROUP BY u.codigo, faixa ORDER BY u.codigo, faixa;"""),
    ("Concorrentes a menos de 2 km de cada loja",
     """SELECT u.codigo, u.nome, COUNT(*) AS concorrentes_2km, SUM(c.area_m2) AS area_concorrente
FROM concorrentes c JOIN unidades u ON u.id = c.loja_referencia_id
WHERE c.distancia_km <= 2 GROUP BY u.id ORDER BY 3 DESC;"""),
    ("Cidades candidatas sem loja (base para expansão)",
     """SELECT c.nome, c.uf, c.regiao, c.populacao, c.renda_per_capita, c.supermercados_concorrentes,
       ROUND(c.populacao * 1.0 / c.supermercados_concorrentes) AS habitantes_por_supermercado
FROM cidades c WHERE c.id NOT IN (SELECT cidade_id FROM unidades)
ORDER BY c.populacao * c.renda_per_capita DESC;"""),
    ("Produtividade: faturamento por m² e por checkout (12 meses)",
     """SELECT u.codigo, u.area_m2, u.checkouts, ROUND(SUM(r.valor_total)/u.area_m2, 2) AS faturamento_m2,
       ROUND(SUM(r.valor_total)/u.checkouts, 2) AS faturamento_checkout
FROM resumo_cupons_diario r JOIN unidades u ON u.id = r.unidade_id
WHERE r.data >= date((SELECT MAX(data) FROM resumo_cupons_diario), '-365 days')
GROUP BY u.id ORDER BY faturamento_m2 DESC;"""),
]


@bp.route("/sql", methods=["GET", "POST"])
def sql():
    texto = request.values.get("sql") or ""
    cols, linhas, erro = [], [], None
    if texto.strip():
        s = texto.strip().rstrip(";").lstrip("(").lower()
        if not (s.startswith("select") or s.startswith("with")):
            erro = "Somente consultas SELECT/WITH são permitidas nesta tela (o banco é aberto em modo leitura)."
        else:
            try:
                cols, linhas = consulta_somente_leitura(texto)
            except Exception as e:  # noqa
                erro = str(e)
        if not erro and request.values.get("formato") == "xlsx":
            return exportar_excel(pd.DataFrame(linhas, columns=cols), "consulta")
    return render_template("sql.html", texto=texto, cols=cols, linhas=linhas, erro=erro, exemplos=EXEMPLOS)


@bp.route("/dicionario")
def dicionario():
    tabelas = []
    for (nome,) in get_db().execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall():
        cols = q(f"PRAGMA table_info({nome})")
        fks = {r["from"]: f"{r['table']}.{r['to']}" for r in q(f"PRAGMA foreign_key_list({nome})")}
        tabelas.append(dict(nome=nome, cols=cols, fks=fks, n=val(f"SELECT COUNT(*) FROM {nome}")))
    return render_template("dicionario.html", tabelas=tabelas)


@bp.route("/cadastros/produtos")
def produtos():
    t = df("""SELECT p.id, p.sku, p.ean, p.descricao, p.marca, c.nome categoria, c.canal, f.nome_fantasia fornecedor_referencia,
                     p.unidade, p.embalagem_compra, p.custo_atual, p.preco_atual,
                     CASE WHEN p.preco_atual > 0 THEN 1 - p.custo_atual/p.preco_atual END margem, p.validade_dias, p.sazonalidade
              FROM produtos p JOIN categorias c ON c.id=p.categoria_id JOIN fornecedores f ON f.id=p.fornecedor_id
              ORDER BY c.nome, p.descricao""")
    if quer_excel():
        return exportar_excel(t, "produtos")
    return render_template("produtos.html", t=recs(t))


@bp.route("/cadastros/fornecedores")
def fornecedores():
    t = df("""SELECT f.*, (SELECT SUM(valor_total) FROM pedidos_compra pc WHERE pc.fornecedor_id=f.id
                      AND pc.data_recebimento >= date((SELECT MAX(data) FROM resumo_cupons_diario), '-365 days')) compras_12m,
                     (SELECT COUNT(DISTINCT unidade_id) FROM pedidos_compra pc WHERE pc.fornecedor_id=f.id) unidades_atendidas,
                     (SELECT AVG(distancia_km) FROM pedidos_compra pc WHERE pc.fornecedor_id=f.id) km_medio
              FROM fornecedores f ORDER BY f.abrangencia, f.regiao_atendida, compras_12m DESC""")
    if quer_excel():
        return exportar_excel(t, "fornecedores")
    return render_template("fornecedores.html", t=recs(t))


@bp.route("/cadastros/clientes")
def clientes():
    ids = R.un(True)
    ref = R.data_referencia()
    t = df(f"""SELECT c.id, c.nome, u.codigo loja, c.bairro, c.sexo, c.distancia_km, c.data_cadastro,
                      COUNT(v.id) compras, SUM(v.valor_total) valor, MAX(v.data) ultima_compra
               FROM clientes c JOIN unidades u ON u.id=c.unidade_id LEFT JOIN vendas v ON v.cliente_id=c.id
               WHERE c.unidade_id IN ({R.ph(ids)}) GROUP BY c.id""", tuple(ids))
    if t.empty:
        return render_template("vazio.html", msg="Sem clientes para a seleção atual.")
    t["dias_sem_comprar"] = (pd.Timestamp(ref) - pd.to_datetime(t["ultima_compra"])).dt.days
    ativos = t[t["compras"] > 0].copy()
    ativos["R"] = pd.qcut(-ativos["dias_sem_comprar"].rank(method="first"), 5, labels=False) + 1
    ativos["F"] = pd.qcut(ativos["compras"].rank(method="first"), 5, labels=False) + 1
    ativos["M"] = pd.qcut(ativos["valor"].rank(method="first"), 5, labels=False) + 1

    def seg(r):
        if r.R >= 4 and r.F >= 4:
            return "Campeões"
        if r.R >= 3 and r.F >= 3:
            return "Leais"
        if r.R >= 4:
            return "Novos/recentes"
        if r.R <= 2 and r.F >= 3:
            return "Em risco"
        return "Hibernando"

    ativos["segmento"] = ativos.apply(seg, axis=1)
    t = t.merge(ativos[["id", "R", "F", "M", "segmento"]], on="id", how="left")
    t["segmento"] = t["segmento"].fillna("Sem compras no período")
    if quer_excel():
        return exportar_excel(t, "clientes_rfm")
    resumo = t.groupby("segmento").agg(clientes=("id", "count"), valor=("valor", "sum"), compras=("compras", "sum")).reset_index()
    resumo["ticket"] = resumo["valor"] / resumo["compras"].where(resumo["compras"] > 0)
    resumo = resumo.sort_values("valor", ascending=False)
    bairros = t.groupby(["loja", "bairro"]).agg(clientes=("id", "count"), valor=("valor", "sum"),
                                                distancia=("distancia_km", "mean")).reset_index().sort_values("valor", ascending=False)
    periodo = q("SELECT MIN(data) ini, MAX(data) fim FROM vendas", one=True)
    return render_template("clientes.html", t=recs(t.sort_values("valor", ascending=False).head(200)), resumo=recs(resumo),
                           bairros=recs(bairros.head(60)), n=len(t), periodo=periodo)
