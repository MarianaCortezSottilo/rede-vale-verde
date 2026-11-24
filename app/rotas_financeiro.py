"""DRE, fluxo de caixa, contas a pagar e despesas (multiunidade)."""
from datetime import date

import pandas as pd
from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from . import exportar_excel
from . import relatorios as R
from .db import df, exec_, get_db, q, val
from .rotas_comercial import opcoes_unidades, periodo, quer_excel, recs, unidade_escolhida

bp = Blueprint("fin", __name__, url_prefix="/financeiro")


@bp.route("/dre")
def dre():
    ci, cf, _, _ = periodo(12)
    comps = R.intervalo(ci, cf)
    t = R.dre(comps)
    cols, linhas = R.dre_tabela(comps)
    if quer_excel():
        t.insert(0, "linha", [r for _, r, _ in R.LINHAS_DRE])
        return exportar_excel(t, f"DRE_{g.sel}_{ci}_{cf}")
    gr = dict(meses=[R.rotulo_mes(c) for c in comps], lucro=[round(x, 2) for x in t.loc["lucro_liquido", comps]],
              ebitda=[round(x, 2) for x in t.loc["ebitda", comps]])
    return render_template("dre.html", ci=ci, cf=cf, cols=cols, linhas=linhas, g=gr, av=request.args.get("av") == "1")


@bp.route("/fluxo")
def fluxo():
    t = R.fluxo_caixa_mensal()
    saldo0, proj = R.fluxo_projetado(60)
    if quer_excel():
        return exportar_excel({"realizado_mensal": t, "projetado_60d": proj}, "fluxo_de_caixa")
    sai_cols = [c for c in t.columns if c.startswith("saida_")]
    gr = dict(meses=[R.rotulo_mes(c) for c in t["competencia"]], saldo=[round(v, 2) for v in t["saldo_acumulado"]],
              ent=[round(v, 2) for v in t["entradas_vendas"] + t["entradas_rede"]],
              sai=[round(-v, 2) for v in t[sai_cols].sum(axis=1)],
              dias=[d[8:10] + "/" + d[5:7] for d in proj["dia"]], psaldo=[round(v, 2) for v in proj["saldo"]])
    return render_template("fluxo.html", t=recs(t), proj=recs(proj), saldo0=saldo0, g=gr,
                           receber=float(proj["a_receber"].sum()), pagar=float(-proj["a_pagar"].sum()))


@bp.route("/contas")
def contas():
    ref = R.data_referencia().isoformat()
    st = request.args.get("status", "ABERTO")
    origem = request.args.get("origem", "")
    ids = R.un()
    P = R.ph(ids)
    sql = f"""SELECT cp.*, u.codigo unidade FROM contas_pagar cp JOIN unidades u ON u.id=cp.unidade_id
              WHERE cp.unidade_id IN ({P})"""
    pr = list(ids)
    if st:
        sql += " AND cp.status=?"
        pr.append(st)
    if origem:
        sql += " AND cp.origem=?"
        pr.append(origem)
    sql += " ORDER BY cp.data_vencimento" + (" DESC" if st == "PAGO" else "") + " LIMIT 500"
    linhas = q(sql, pr)
    aging = df(f"""SELECT CASE WHEN data_vencimento < ? THEN 'Vencido'
                               WHEN julianday(data_vencimento)-julianday(?) <= 7 THEN 'Até 7 dias'
                               WHEN julianday(data_vencimento)-julianday(?) <= 30 THEN '8 a 30 dias'
                               WHEN julianday(data_vencimento)-julianday(?) <= 60 THEN '31 a 60 dias'
                               ELSE 'Acima de 60 dias' END faixa, COUNT(*) titulos, SUM(valor) valor
                   FROM contas_pagar WHERE status='ABERTO' AND unidade_id IN ({P}) GROUP BY 1""", (ref, ref, ref, ref, *ids))
    ordem = ["Vencido", "Até 7 dias", "8 a 30 dias", "31 a 60 dias", "Acima de 60 dias"]
    aging["o"] = aging["faixa"].map({k: i for i, k in enumerate(ordem)})
    aging = aging.sort_values("o")
    if quer_excel():
        return exportar_excel({"titulos": pd.DataFrame(linhas), "aging": aging.drop(columns="o")}, "contas_a_pagar")
    return render_template("contas.html", linhas=linhas, aging=recs(aging), st=st, origem=origem, ref=ref)


@bp.route("/contas/<int:cid>/pagar", methods=["POST"])
def pagar(cid):
    dia = request.form.get("data") or date.today().isoformat()
    exec_("UPDATE contas_pagar SET status='PAGO', data_pagamento=? WHERE id=? AND status='ABERTO'", (dia, cid))
    c = q("SELECT * FROM contas_pagar WHERE id=?", (cid,), one=True)
    if c and c["origem"] in ("DESPESA", "FRANQUIA"):
        exec_("""UPDATE despesas SET status='PAGO', data_pagamento=? WHERE status='ABERTO' AND unidade_id=? AND descricao=?
                 AND valor=? AND data_vencimento=?""", (dia, c["unidade_id"], c["referencia"], c["valor"], c["data_vencimento"]))
    get_db().commit()
    flash("Título baixado como pago.", "ok")
    return redirect(request.referrer or url_for("fin.contas"))


@bp.route("/despesas", methods=["GET", "POST"])
def despesas():
    if request.method == "POST":
        f = request.form
        uid = int(f["unidade_id"])
        comp = f["competencia"]
        valor = float(f["valor"].replace(".", "").replace(",", ".")) if "," in f["valor"] else float(f["valor"])
        exec_("""INSERT INTO despesas (unidade_id,competencia,categoria_id,descricao,favorecido,departamento_id,valor,
                 data_vencimento,status) VALUES (?,?,?,?,?,?,?,?,'ABERTO')""",
              (uid, comp, int(f["categoria_id"]), f["descricao"], f.get("favorecido"), f.get("departamento_id") or None,
               valor, f["vencimento"]))
        cat = val("SELECT nome FROM categorias_despesa WHERE id=?", (int(f["categoria_id"]),))
        if cat != "Depreciação":
            exec_("""INSERT INTO contas_pagar (unidade_id,origem,referencia,favorecido,competencia,data_emissao,data_vencimento,
                     valor,status) VALUES (?,'DESPESA',?,?,?,?,?,?,'ABERTO')""",
                  (uid, f["descricao"], f.get("favorecido") or cat, comp, date.today().isoformat(), f["vencimento"], valor))
        get_db().commit()
        flash("Despesa lançada (e enviada ao contas a pagar).", "ok")
        return redirect(url_for("fin.despesas", ini=comp, fim=comp))
    ci, cf, _, _ = periodo(1)
    ids = R.un()
    P = R.ph(ids)
    t = df(f"""SELECT d.*, cd.nome categoria, cd.tipo, cd.grupo_dre, dp.nome departamento, u.codigo unidade FROM despesas d
               JOIN categorias_despesa cd ON cd.id=d.categoria_id LEFT JOIN departamentos dp ON dp.id=d.departamento_id
               JOIN unidades u ON u.id=d.unidade_id
               WHERE d.unidade_id IN ({P}) AND d.competencia BETWEEN ? AND ? ORDER BY d.competencia, d.valor DESC""",
           (*ids, ci, cf))
    hist = df(f"""SELECT d.competencia, cd.tipo, SUM(d.valor) valor FROM despesas d
                  JOIN categorias_despesa cd ON cd.id=d.categoria_id
                  WHERE cd.grupo_dre <> 'DEPRECIACAO' AND d.unidade_id IN ({P}) GROUP BY 1,2 ORDER BY 1""", tuple(ids))
    if quer_excel():
        return exportar_excel({"despesas": t, "fixas_variaveis_mensal": hist}, f"despesas_{ci}_{cf}")
    por_cat = t.groupby(["categoria", "tipo"])["valor"].sum().reset_index().sort_values("valor", ascending=False)
    hp = hist.pivot_table(index="competencia", columns="tipo", values="valor", aggfunc="sum").fillna(0)
    gr = dict(meses=[R.rotulo_mes(c) for c in hp.index], fixa=[round(v, 2) for v in hp.get("FIXA", [])],
              variavel=[round(v, 2) for v in hp.get("VARIAVEL", [])])
    total = float(t["valor"].sum()) or 1.0
    return render_template("despesas.html", ci=ci, cf=cf, t=recs(t.head(800)), n=len(t), por_cat=recs(por_cat), g=gr,
                           cats=q("SELECT * FROM categorias_despesa ORDER BY nome"),
                           deps=q("SELECT id, nome FROM departamentos ORDER BY nome"), total=total,
                           fixas=float(t[t["tipo"] == "FIXA"]["valor"].sum()), comp_padrao=date.today().strftime("%Y-%m"),
                           unidades_form=opcoes_unidades(("LOJA", "CD", "SEDE")), uid=unidade_escolhida(("LOJA", "CD", "SEDE")))
