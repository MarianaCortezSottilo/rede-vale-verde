"""Recursos humanos: quadro, escalas, folha e indicadores (multiunidade)."""
from datetime import date, timedelta

import pandas as pd
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from . import exportar_excel
from . import relatorios as R
from .db import df, exec_, get_db, q, val
from .folha import calcular_linha, limites_mes
from .rotas_comercial import opcoes_unidades, quer_excel, recs

bp = Blueprint("rh", __name__, url_prefix="/rh")
FERIADOS_FECHADO = {"12-25", "01-01"}


def salario_vigente(fid, dia):
    s = val("""SELECT salario FROM historico_salarial WHERE funcionario_id=? AND data_inicio<=?
               ORDER BY data_inicio DESC, id DESC LIMIT 1""", (fid, dia))
    return s if s is not None else val("SELECT salario_admissao FROM funcionarios WHERE id=?", (fid,))


@bp.route("/")
def funcionarios():
    sit = request.args.get("situacao", "ativos")
    dep = request.args.get("departamento", "")
    ids = R.un()
    sql = f"""SELECT f.*, c.nome cargo, d.nome departamento, u.codigo unidade,
                     (SELECT salario FROM historico_salarial h WHERE h.funcionario_id=f.id
                      ORDER BY data_inicio DESC, id DESC LIMIT 1) salario_atual
              FROM funcionarios f JOIN cargos c ON c.id=f.cargo_id JOIN departamentos d ON d.id=c.departamento_id
              JOIN unidades u ON u.id=f.unidade_id WHERE f.unidade_id IN ({R.ph(ids)})"""
    pr = list(ids)
    if sit == "ativos":
        sql += " AND f.data_demissao IS NULL"
    elif sit == "desligados":
        sql += " AND f.data_demissao IS NOT NULL"
    if dep:
        sql += " AND d.nome=?"
        pr.append(dep)
    t = df(sql + " ORDER BY u.codigo, d.nome, c.nome, f.nome", pr)
    if quer_excel():
        return exportar_excel(t, f"funcionarios_{sit}")
    quadro = df(f"""SELECT u.codigo unidade, d.nome departamento, c.nome cargo,
                           SUM(f.data_demissao IS NULL AND f.tipo_contrato <> 'TEMPORARIO') ocupadas
                    FROM funcionarios f JOIN cargos c ON c.id=f.cargo_id JOIN departamentos d ON d.id=c.departamento_id
                    JOIN unidades u ON u.id=f.unidade_id WHERE f.unidade_id IN ({R.ph(ids)})
                    GROUP BY u.id, c.id ORDER BY u.codigo, d.nome, c.nome""", tuple(ids))
    resumo = t[t["data_demissao"].isna()].groupby("unidade").agg(ativos=("id", "count"),
                                                                  folha_mensal=("salario_atual", "sum")).reset_index() \
        if len(t) else pd.DataFrame()
    deps = [r["nome"] for r in q("SELECT nome FROM departamentos ORDER BY nome")]
    return render_template("rh_funcionarios.html", t=recs(t.head(1000)), n=len(t), quadro=recs(quadro), sit=sit, dep=dep,
                           deps=deps, resumo=recs(resumo))


@bp.route("/funcionario/<int:fid>")
def funcionario(fid):
    f = q("""SELECT f.*, c.nome cargo, d.nome departamento, u.codigo || ' · ' || u.nome unidade FROM funcionarios f
             JOIN cargos c ON c.id=f.cargo_id JOIN departamentos d ON d.id=c.departamento_id JOIN unidades u ON u.id=f.unidade_id
             WHERE f.id=?""", (fid,), one=True)
    if not f:
        abort(404)
    hist = q("SELECT * FROM historico_salarial WHERE funcionario_id=? ORDER BY data_inicio, id", (fid,))
    folha = q("SELECT * FROM folha_pagamento WHERE funcionario_id=? ORDER BY competencia DESC", (fid,))
    esc = q("SELECT tipo, COUNT(*) n FROM escalas WHERE funcionario_id=? AND data <= ? GROUP BY tipo",
            (fid, R.data_referencia().isoformat()))
    vendas = q("""SELECT substr(data,1,7) c, COUNT(*) cupons, SUM(valor_total) receita FROM vendas
                  WHERE operador_id=? GROUP BY 1 ORDER BY 1 DESC LIMIT 12""", (fid,)) if f["cargo"] == "Operador de Caixa" else None
    return render_template("rh_funcionario.html", f=f, hist=hist, folha=folha, esc=esc, vendas=vendas,
                           salario=salario_vigente(fid, date.today().isoformat()), hoje_iso=date.today().isoformat())


@bp.route("/admitir", methods=["GET", "POST"])
def admitir():
    if request.method == "POST":
        fm = request.form
        n = val("SELECT MAX(id) FROM funcionarios") + 1
        sal = float(fm["salario"].replace(",", "."))
        fid = exec_("""INSERT INTO funcionarios (id,matricula,nome,cpf,data_nascimento,sexo,unidade_id,cargo_id,tipo_contrato,
                       turno,salario_admissao,data_admissao,usa_vale_transporte) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (n, f"VV{n:05d}", fm["nome"], fm.get("cpf") or "999.000.000-00", fm.get("data_nascimento") or None,
                     fm.get("sexo"), int(fm["unidade_id"]), int(fm["cargo_id"]), fm["tipo_contrato"], fm["turno"], sal,
                     fm["data_admissao"], 1 if fm.get("vt") else 0))
        exec_("INSERT INTO historico_salarial (funcionario_id,data_inicio,salario,motivo) VALUES (?,?,?,'Admissão')",
              (fid, fm["data_admissao"], sal))
        get_db().commit()
        flash(f"Funcionário admitido (matrícula VV{n:05d}). Gere a escala do mês para incluí-lo.", "ok")
        return redirect(url_for("rh.funcionario", fid=fid))
    cargos = q("""SELECT c.*, d.nome departamento FROM cargos c JOIN departamentos d ON d.id=c.departamento_id
                  ORDER BY c.tipo_unidade, d.nome, c.nome""")
    pisos = {}
    for r in q("""SELECT f.unidade_id, f.cargo_id, h.salario FROM historico_salarial h JOIN funcionarios f ON f.id=h.funcionario_id
                  WHERE h.motivo='Admissão' ORDER BY h.data_inicio"""):
        pisos[f"{r['unidade_id']}-{r['cargo_id']}"] = r["salario"]
    return render_template("rh_admitir.html", cargos=cargos, pisos=pisos, hoje_iso=date.today().isoformat(),
                           unidades_form=opcoes_unidades(("LOJA", "CD", "SEDE")), uid=g.un_unica)


@bp.route("/funcionario/<int:fid>/desligar", methods=["POST"])
def desligar(fid):
    dia = request.form["data"]
    exec_("UPDATE funcionarios SET data_demissao=?, motivo_desligamento=? WHERE id=? AND data_demissao IS NULL",
          (dia, request.form["motivo"], fid))
    exec_("DELETE FROM escalas WHERE funcionario_id=? AND data>=?", (fid, dia))
    get_db().commit()
    flash("Desligamento registrado e escalas futuras removidas.", "ok")
    return redirect(url_for("rh.funcionario", fid=fid))


@bp.route("/funcionario/<int:fid>/reajuste", methods=["POST"])
def reajuste(fid):
    exec_("INSERT INTO historico_salarial (funcionario_id,data_inicio,salario,motivo) VALUES (?,?,?,?)",
          (fid, request.form["data"], float(request.form["salario"].replace(",", ".")), request.form["motivo"]))
    get_db().commit()
    flash("Alteração salarial registrada.", "ok")
    return redirect(url_for("rh.funcionario", fid=fid))


# ---------------------------------------------------------------------------
# Escala
# ---------------------------------------------------------------------------
def gerar_escala(comp, uid):
    ini, fim = limites_mes(comp)
    funcs = q("""SELECT f.*, u.tipo tipo_un FROM funcionarios f JOIN unidades u ON u.id=f.unidade_id
                 WHERE f.unidade_id=? AND f.data_admissao <= ? AND (f.data_demissao IS NULL OR f.data_demissao > ?)""",
              (uid, fim.isoformat(), ini.isoformat()))
    criadas = 0
    for f in funcs:
        grupo, folga = f["id"] % 2, f["id"] % 4
        d = max(ini, date.fromisoformat(f["data_admissao"]))
        fim_f = min(fim, date.fromisoformat(f["data_demissao"]) - timedelta(days=1)) if f["data_demissao"] else fim
        while d <= fim_f:
            if val("SELECT 1 FROM escalas WHERE funcionario_id=? AND data=?", (f["id"], d.isoformat())):
                d += timedelta(days=1)
                continue
            wd = d.weekday()
            semana = (d - date(2024, 10, 28)).days // 7
            if d.strftime("%m-%d") in FERIADOS_FECHADO:
                reg = ("FOLGA", None, None)
            elif f["turno"] == "COMERCIAL" or f["tipo_un"] != "LOJA":
                if wd >= 5:
                    reg = ("FOLGA", None, None)
                elif f["tipo_un"] == "CD":
                    reg = ("TRABALHO", "05:00", "13:48") if f["turno"] == "MANHA" else ("TRABALHO", "14:00", "22:48")
                else:
                    reg = ("TRABALHO", "08:00", "17:48")
            else:
                trabalha_dom = (semana + grupo) % 2 == 0
                if wd == 6:
                    reg = ("TRABALHO", "08:00", "13:00") if trabalha_dom else ("FOLGA", None, None)
                elif trabalha_dom and wd == folga:
                    reg = ("FOLGA", None, None)
                else:
                    reg = ("TRABALHO",) + (("07:00", "15:20") if f["turno"] == "MANHA" else ("13:40", "22:00"))
            exec_("INSERT INTO escalas (funcionario_id,data,tipo,hora_inicio,hora_fim) VALUES (?,?,?,?,?)",
                  (f["id"], d.isoformat()) + reg)
            criadas += 1
            d += timedelta(days=1)
    get_db().commit()
    return criadas


@bp.route("/escala", methods=["GET", "POST"])
def escala():
    if request.method == "POST":
        comp, uid = request.form["mes"], int(request.form["unidade_id"])
        n = gerar_escala(comp, uid)
        flash(f"{n} dia(s) de escala gerados para {comp} (registros existentes foram mantidos).", "ok")
        return redirect(url_for("rh.escala", mes=comp, unidade_id=uid))
    comp = request.args.get("mes") or date.today().strftime("%Y-%m")
    uid = request.args.get("unidade_id", type=int) or g.un_unica or R.un()[0]
    ini, fim = limites_mes(comp)
    dep = request.args.get("departamento", "")
    t = df("""SELECT e.funcionario_id, f.nome, c.nome cargo, d.nome departamento, f.turno, e.data, e.tipo, e.hora_inicio,
                     e.hora_fim
              FROM escalas e JOIN funcionarios f ON f.id=e.funcionario_id JOIN cargos c ON c.id=f.cargo_id
              JOIN departamentos d ON d.id=c.departamento_id WHERE f.unidade_id=? AND e.data BETWEEN ? AND ?""",
           (uid, ini.isoformat(), fim.isoformat()))
    if dep:
        t = t[t["departamento"] == dep]
    if quer_excel():
        return exportar_excel(t, f"escala_{comp}")
    dias = [ini + timedelta(days=k) for k in range((fim - ini).days + 1)]
    grade = []
    for (fid, nome, cargo, depn, turno), gq in t.groupby(["funcionario_id", "nome", "cargo", "departamento", "turno"]):
        mapa = {r["data"]: (r["tipo"], r["hora_inicio"], r["hora_fim"]) for _, r in gq.iterrows()}
        cel = []
        for d in dias:
            tp, hi, hf = mapa.get(d.isoformat(), (None, None, None))
            if tp == "TRABALHO":
                cod = {"07:00": "M", "13:40": "T", "05:00": "M", "14:00": "T"}.get(hi) or ("D" if hf == "13:00" else "C")
            else:
                cod = {"FOLGA": "F", "FERIAS": "Fé", "ATESTADO": "At", "FALTA": "Fa"}.get(tp, "")
            cel.append((cod, tp))
        grade.append(dict(id=fid, nome=nome, cargo=cargo, dep=depn, turno=turno, cel=cel,
                          trab=sum(1 for c, _ in cel if c in ("M", "T", "D", "C"))))
    grade.sort(key=lambda x: (x["dep"], x["cargo"], x["nome"]))
    cx = t[(t["cargo"] == "Operador de Caixa") & (t["tipo"] == "TRABALHO")].groupby("data").size()
    cobertura = [int(cx.get(d.isoformat(), 0)) for d in dias]
    deps = [r["nome"] for r in q("SELECT nome FROM departamentos ORDER BY nome")]
    return render_template("rh_escala.html", comp=comp, dias=dias, grade=grade, cobertura=cobertura, dep=dep, deps=deps,
                           anterior=R.comp_soma(comp, -1), proximo=R.comp_soma(comp, 1), uid=uid,
                           unidades_form=opcoes_unidades(("LOJA", "CD", "SEDE")))


# ---------------------------------------------------------------------------
# Folha
# ---------------------------------------------------------------------------
@bp.route("/folha")
def folha():
    resumo = R.folha_resumo()
    if resumo.empty:
        return render_template("vazio.html", msg="Sem folha para a seleção atual.")
    comp = request.args.get("comp") or resumo["competencia"].iloc[-1]
    ids = R.un()
    linhas = df(f"""SELECT fp.*, f.nome, f.matricula, c.nome cargo, d.nome departamento, u.codigo unidade
                    FROM folha_pagamento fp JOIN funcionarios f ON f.id=fp.funcionario_id JOIN cargos c ON c.id=f.cargo_id
                    JOIN departamentos d ON d.id=c.departamento_id JOIN unidades u ON u.id=fp.unidade_id
                    WHERE fp.competencia=? AND fp.unidade_id IN ({R.ph(ids)}) ORDER BY u.codigo, d.nome, f.nome""",
                (comp, *ids))
    if quer_excel():
        return exportar_excel({"folha": linhas, "resumo_mensal": resumo}, f"folha_{comp}")
    dep = R.folha_por_departamento(comp)
    por_un = linhas.groupby("unidade").agg(pessoas=("id", "count"), bruto=("salario_bruto", "sum"),
                                           custo=("custo_total", "sum")).reset_index() if len(linhas) else pd.DataFrame()
    gr = dict(meses=[R.rotulo_mes(c) for c in resumo["competencia"]], bruto=[round(v, 2) for v in resumo["bruto"]],
              encargos=[round(v, 2) for v in resumo["encargos"]], beneficios=[round(v, 2) for v in resumo["beneficios"]],
              provisoes=[round(v, 2) for v in resumo["provisoes"]])
    tot = linhas.select_dtypes("number").sum().to_dict() if len(linhas) else {}
    return render_template("rh_folha.html", comp=comp, linhas=recs(linhas.head(600)), n=len(linhas), tot=tot, dep=recs(dep),
                           g=gr, comps=list(resumo["competencia"]), proxima=R.comp_soma(resumo["competencia"].iloc[-1], 1),
                           por_un=recs(por_un))


@bp.route("/folha/calcular", methods=["POST"])
def calcular_folha():
    comp = request.form["comp"]
    ids = R.un()
    par = {r["chave"]: r["valor"] for r in q("SELECT chave, valor FROM parametros")}
    ini, fim = limites_mes(comp)
    he_padrao = float(request.form.get("horas_extras") or 0)
    feitas = 0
    for uid in ids:
        if val("SELECT COUNT(*) FROM folha_pagamento WHERE competencia=? AND unidade_id=?", (comp, uid)):
            continue
        funcs = q("""SELECT f.*, d.tipo tipo_dep FROM funcionarios f JOIN cargos c ON c.id=f.cargo_id
                     JOIN departamentos d ON d.id=c.departamento_id
                     WHERE f.unidade_id=? AND f.data_admissao <= ? AND (f.data_demissao IS NULL OR f.data_demissao > ?)""",
                  (uid, fim.isoformat(), ini.isoformat()))
        tot = dict(liq=0, va=0, vt=0, inss=0, fgts=0, irrf=0)
        for f in funcs:
            a = max(date.fromisoformat(f["data_admissao"]), ini)
            b = min(date.fromisoformat(f["data_demissao"]) - timedelta(days=1), fim) if f["data_demissao"] else fim
            dias_t = 30 if (a == ini and b == fim) else min(30, (b - a).days + 1)
            sal = salario_vigente(f["id"], b.isoformat())
            he = he_padrao * dias_t / 30 if f["tipo_dep"] == "OPERACIONAL" and f["tipo_contrato"] in ("CLT", "TEMPORARIO") else 0
            verbas = multa = 0.0
            if f["data_demissao"] and f["motivo_desligamento"] == "Dispensa sem justa causa":
                verbas = sal
                meses = max(1, (date.fromisoformat(f["data_demissao"]) - date.fromisoformat(f["data_admissao"])).days / 30)
                multa = round(0.40 * 0.08 * sal * min(meses, 120), 2)
            r = calcular_linha(sal, dias_t, fim.year, fim.month, f["tipo_contrato"], f["usa_vale_transporte"], he, par,
                               verbas, multa)
            exec_(f"INSERT INTO folha_pagamento (competencia,unidade_id,funcionario_id,{','.join(r.keys())}) "
                  f"VALUES (?,?,?,{','.join('?' * len(r))})", (comp, uid, f["id"], *r.values()))
            tot["liq"] += r["salario_liquido"]
            tot["va"] += r["vale_alimentacao"]
            tot["vt"] += r["vale_transporte_custo"]
            tot["inss"] += r["inss_funcionario"] + r["inss_patronal"]
            tot["fgts"] += r["fgts"]
            tot["irrf"] += r["irrf"]
        a2, m2 = fim.year + (fim.month == 12), fim.month % 12 + 1
        d5, k = date(a2, m2, 1), 0
        while True:
            if d5.weekday() < 5:
                k += 1
                if k == 5:
                    break
            d5 += timedelta(days=1)
        for origem, ref, fav, venc, v in [
            ("FOLHA", f"Folha {comp}", "Funcionários (salário líquido)", d5, tot["liq"]),
            ("FOLHA", f"Vale-alimentação {comp}", "Cartão Alimenta Mais", date(fim.year, fim.month, 25), tot["va"]),
            ("FOLHA", f"Vale-transporte {comp}", "Operadora de transporte", ini, tot["vt"]),
            ("ENCARGOS", f"INSS {comp}", "Receita Federal (DCTFWeb)", date(a2, m2, 20), tot["inss"]),
            ("ENCARGOS", f"FGTS {comp}", "FGTS Digital (Caixa)", date(a2, m2, 20), tot["fgts"]),
            ("ENCARGOS", f"IRRF folha {comp}", "Receita Federal", date(a2, m2, 20), tot["irrf"]),
        ]:
            if v > 0:
                exec_("""INSERT INTO contas_pagar (unidade_id,origem,referencia,favorecido,competencia,data_emissao,data_vencimento,
                         valor,status) VALUES (?,?,?,?,?,?,?,?,'ABERTO')""",
                      (uid, origem, ref, fav, comp, fim.isoformat(), venc.isoformat(), round(v, 2)))
        feitas += 1
    get_db().commit()
    flash(f"Folha de {comp} calculada para {feitas} unidade(s) da seleção e lançada no contas a pagar.", "ok")
    return redirect(url_for("rh.folha", comp=comp))


# ---------------------------------------------------------------------------
# Indicadores
# ---------------------------------------------------------------------------
@bp.route("/indicadores")
def indicadores():
    ids = R.un()
    P = R.ph(ids)
    hc = R.headcount_mensal()
    fr = R.folha_resumo()
    vm = R.vendas_mensais()
    vm = vm[["competencia", "receita"]] if len(vm) else pd.DataFrame(columns=["competencia", "receita"])
    ab = df(f"""SELECT substr(e.data,1,7) competencia, SUM(e.tipo IN ('ATESTADO','FALTA'))*1.0 /
                       NULLIF(SUM(e.tipo IN ('TRABALHO','ATESTADO','FALTA')),0) absenteismo
                FROM escalas e JOIN funcionarios f ON f.id=e.funcionario_id
                WHERE e.data <= ? AND f.unidade_id IN ({P}) GROUP BY 1""", (R.data_referencia().isoformat(), *ids))
    t = hc.merge(fr[["competencia", "custo_total", "horas_extras"]], on="competencia", how="left") \
        .merge(vm, on="competencia", how="left").merge(ab, on="competencia", how="left")
    t["custo_por_func"] = t["custo_total"] / t["headcount"]
    t["folha_sobre_receita"] = t["custo_total"] / t["receita"]
    t["receita_por_func"] = t["receita"] / t["headcount"]
    deslig = df(f"""SELECT motivo_desligamento motivo, COUNT(*) n FROM funcionarios WHERE data_demissao IS NOT NULL
                    AND unidade_id IN ({P}) GROUP BY 1 ORDER BY 2 DESC""", tuple(ids))
    por_cargo = df(f"""SELECT c.nome cargo, COUNT(*) desligamentos,
                              AVG(julianday(f.data_demissao)-julianday(f.data_admissao)) dias_medios_casa
                       FROM funcionarios f JOIN cargos c ON c.id=f.cargo_id
                       WHERE f.data_demissao IS NOT NULL AND f.data_demissao >= '2024-11-01' AND f.unidade_id IN ({P})
                       GROUP BY 1 ORDER BY 2 DESC""", tuple(ids))
    ult12 = [c for c in R.competencias() if c <= R.ultima_competencia_fechada()][-12:]
    por_un = df(f"""SELECT u.codigo, u.nome, u.modelo, u.tipo,
                           (SELECT COUNT(*) FROM funcionarios f WHERE f.unidade_id=u.id AND f.data_demissao IS NULL) ativos,
                           (SELECT COUNT(*) FROM funcionarios f WHERE f.unidade_id=u.id AND f.data_demissao BETWEEN ? AND ?) deslig_12m,
                           (SELECT SUM(custo_total) FROM folha_pagamento fp WHERE fp.unidade_id=u.id AND fp.competencia BETWEEN ? AND ?) custo_12m,
                           (SELECT SUM(valor_total) FROM resumo_cupons_diario r WHERE r.unidade_id=u.id AND r.data BETWEEN ? AND ?) receita_12m
                    FROM unidades u WHERE u.id IN ({P}) ORDER BY u.codigo""",
                (ult12[0] + "-01", R.fim_mes(ult12[-1]).isoformat(), ult12[0], ult12[-1], ult12[0] + "-01",
                 R.fim_mes(ult12[-1]).isoformat(), *ids))
    por_un["turnover_anual"] = por_un["deslig_12m"] / por_un["ativos"].clip(lower=1)
    por_un["folha_pct"] = por_un["custo_12m"] / por_un["receita_12m"]
    if quer_excel():
        return exportar_excel({"indicadores_mensais": t, "por_unidade": por_un, "motivos_desligamento": deslig,
                               "por_cargo": por_cargo}, "indicadores_rh")
    t = t[t["custo_total"].notna()]
    gr = dict(meses=[R.rotulo_mes(c) for c in t["competencia"]], hc=list(t["headcount"]),
              turnover=[round(v * 100, 2) for v in t["turnover"]],
              folha_pct=[round(v * 100, 2) if v == v else None for v in t["folha_sobre_receita"]])
    return render_template("rh_indicadores.html", t=recs(t), deslig=recs(deslig), por_cargo=recs(por_cargo), g=gr,
                           por_un=recs(por_un))
