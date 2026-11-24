"""Painel, vendas, PDV, compras, transferências, estoque e consumo interno (multiunidade)."""
import math
from datetime import date, datetime, timedelta

import numpy as np
from flask import Blueprint, abort, flash, g, jsonify, redirect, render_template, request, url_for

from . import exportar_excel
from . import relatorios as R
from .db import df, exec_, get_db, param, q, val

bp = Blueprint("com", __name__)


# ---------------------------------------------------------------------------
def periodo(meses_padrao=1):
    comps = R.competencias()
    ult = R.ultima_competencia_fechada()
    cf = request.args.get("fim") or ult
    ci = request.args.get("ini") or R.comp_soma(cf, -(meses_padrao - 1))
    ci, cf = max(ci, comps[0]), min(cf, comps[-1])
    if ci > cf:
        ci = cf
    d_ini, d_fim = R.limites(ci, cf)
    return ci, cf, d_ini, d_fim


def recs(d):
    return d.replace({np.nan: None}).to_dict("records")


def quer_excel():
    return request.args.get("formato") == "xlsx"


def unidade_escolhida(tipos=("LOJA",)):
    """Unidade para formulários de lançamento: a do formulário, a seleção única, ou None."""
    uid = request.values.get("unidade_id", type=int)
    if uid and g.por_id.get(uid, {}).get("tipo") in tipos:
        return uid
    if g.un_unica and g.por_id[g.un_unica]["tipo"] in tipos:
        return g.un_unica
    return None


def opcoes_unidades(tipos=("LOJA",)):
    return [u for u in g.unidades if u["tipo"] in tipos]


# ---------------------------------------------------------------------------
# Painel
# ---------------------------------------------------------------------------
@bp.route("/")
def painel():
    c = request.args.get("mes") or R.ultima_competencia_fechada()
    d_ini, d_fim = R.limites(c, c)
    k = R.kpis_mes(c)
    vm = R.vendas_mensais()
    if vm.empty or k is None:
        return render_template("vazio.html", msg="A seleção atual não tem vendas (escolha uma loja ou a rede).")
    cps = list(vm["competencia"])
    dre = R.dre(cps)
    proj = R.projetar_receita(3)["projecao"]
    cat = R.vendas_por_categoria(d_ini, d_fim)
    fp = R.formas_pagamento(d_ini, d_fim)
    hc = R.headcount_mensal().set_index("competencia")
    ref = R.data_referencia()
    pos = R.posicao_estoque(ids=R.un())
    P = R.ph(R.un())
    dm = dre[c] if c in dre.columns else None
    base = (dm["receita_bruta"] + dm["receitas_franquia"] + dm["margem_distribuicao"]) if dm is not None else 0
    lojas_ativas = val(f"""SELECT COUNT(DISTINCT unidade_id) FROM resumo_cupons_diario
                           WHERE unidade_id IN ({R.ph(R.un(True))}) AND data BETWEEN ? AND ?""", (*R.un(True), d_ini, d_fim))
    extras = dict(
        lucro=float(dm["lucro_liquido"]) if dm is not None else None,
        margem_liq=float(dm["lucro_liquido"] / base) if base else None,
        ebitda=float(dm["ebitda"]) if dm is not None else None,
        headcount=int(hc.loc[c, "headcount"]) if c in hc.index else None,
        turnover=float(hc.loc[c, "turnover"]) if c in hc.index else None,
        valor_estoque=float(pos["valor"].sum()) if len(pos) else 0,
        abaixo_min=int((pos["status"].isin(["Abaixo do mínimo", "Sem estoque"]) & (pos["revenda"] == 1)).sum()) if len(pos) else 0,
        perdas=float(-dm["perdas"]) if dm is not None else None,
        rupturas=val(f"SELECT SUM(venda_perdida_estimada) FROM rupturas WHERE unidade_id IN ({P}) AND data BETWEEN ? AND ?",
                     (*R.un(), d_ini, d_fim)),
        pagar_7d=val(f"""SELECT SUM(valor) FROM contas_pagar WHERE status='ABERTO' AND data_vencimento <= ?
                         AND unidade_id IN ({P})""", ((ref + timedelta(days=7)).isoformat(), *R.un())),
        folha=float(-dm["pessoal_folha"]) if dm is not None else None,
        lojas=lojas_ativas,
    )
    graf = dict(
        meses=[R.rotulo_mes(x) for x in cps] + [R.rotulo_mes(x) for x in proj["competencia"]],
        receita=[round(x, 2) for x in vm["receita"]] + [None] * len(proj),
        projecao=[None] * len(cps) + [round(x, 2) for x in proj["receita"]],
        lucro=[round(float(dre.loc["lucro_liquido", x]), 2) for x in cps],
        meses_hist=[R.rotulo_mes(x) for x in cps],
        cat_nomes=list(cat["categoria"]), cat_receita=[round(x, 2) for x in cat["receita"]],
        cat_margem=[round(x * 100, 1) for x in cat["margem"]],
        fp_nomes=list(fp["forma_pagamento"]), fp_receita=[round(x, 2) for x in fp["receita"]],
    )
    return render_template("painel.html", c=c, k=k, x=extras, g=graf)


# ---------------------------------------------------------------------------
# Vendas
# ---------------------------------------------------------------------------
@bp.route("/vendas")
def vendas():
    ci, cf, d_ini, d_fim = periodo(1)
    ids = R.un(True)
    P = R.ph(ids)
    diario = df(f"""SELECT data, SUM(cupons) cupons, SUM(valor_total) receita, SUM(valor_total)/SUM(cupons) ticket
                    FROM resumo_cupons_diario WHERE unidade_id IN ({P}) AND data BETWEEN ? AND ? GROUP BY data ORDER BY data""",
                (*ids, d_ini, d_fim))
    cat = R.vendas_por_categoria(d_ini, d_fim)
    top = R.top_produtos(d_ini, d_fim, 20)
    fp = R.formas_pagamento(d_ini, d_fim)
    # mapa de calor e operadores usam os cupons individuais (últimos meses gravados)
    min_cupom = val("SELECT MIN(data) FROM vendas") or d_ini
    hh_ini = max(d_ini, min_cupom)
    hh = R.vendas_dia_hora(hh_ini, d_fim)
    ops = R.operadores(hh_ini, d_fim)
    por_loja = df(f"""SELECT u.codigo, u.nome, SUM(r.valor_total) receita, SUM(r.cupons) cupons,
                             SUM(r.valor_total)/SUM(r.cupons) ticket, 1 - SUM(r.custo_total)/SUM(r.valor_total) margem
                      FROM resumo_cupons_diario r JOIN unidades u ON u.id=r.unidade_id
                      WHERE r.unidade_id IN ({P}) AND r.data BETWEEN ? AND ? GROUP BY u.id ORDER BY receita DESC""",
                  (*ids, d_ini, d_fim))
    if quer_excel():
        return exportar_excel({"diario": diario, "por_loja": por_loja, "categorias": cat, "top_produtos": top,
                               "pagamento": fp, "operadores": ops}, f"vendas_{ci}_{cf}")
    tot = dict(receita=diario["receita"].sum(), cupons=diario["cupons"].sum())
    tot["ticket"] = tot["receita"] / tot["cupons"] if tot["cupons"] else 0
    tot["cmv"] = cat["cmv"].sum()
    tot["margem"] = 1 - tot["cmv"] / tot["receita"] if tot["receita"] else 0
    tot["clientes_fid"] = val(f"""SELECT SUM(cupons_fidelidade)*1.0/SUM(cupons) FROM resumo_cupons_diario
                                 WHERE unidade_id IN ({P}) AND data BETWEEN ? AND ?""", (*ids, d_ini, d_fim))
    dows = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
    horas = list(range(7, 22))
    mapa, vmax = [], 0
    for dw in [1, 2, 3, 4, 5, 6, 0]:
        linha = []
        for h in horas:
            r = hh[(hh["dow"] == dw) & (hh["hora"] == h)]
            v = float(r["receita"].sum() / r["dias"].max()) if len(r) else 0
            vmax = max(vmax, v)
            linha.append(v)
        mapa.append((dows[dw], linha))
    gr = dict(dias=[x[8:10] + "/" + x[5:7] for x in diario["data"]], receita=[round(x, 2) for x in diario["receita"]])
    return render_template("vendas.html", ci=ci, cf=cf, tot=tot, cat=recs(cat), top=recs(top), fp=recs(fp),
                           ops=recs(ops.head(60)), mapa=mapa, horas=horas, vmax=vmax, g=gr, por_loja=recs(por_loja),
                           hh_ini=hh_ini)


@bp.route("/vendas/abc")
def curva_abc():
    ci, cf, d_ini, d_fim = periodo(3)
    t = R.curva_abc(d_ini, d_fim)
    if t.empty:
        return render_template("vazio.html", msg="A curva ABC usa vendas: escolha uma loja ou um agrupamento de lojas.")
    if quer_excel():
        return exportar_excel(t, f"curva_abc_{ci}_{cf}")
    resumo = t.groupby("classe").agg(produtos=("id", "count"), receita=("receita", "sum"),
                                     lucro=("lucro_bruto", "sum")).reset_index()
    resumo["pct_produtos"] = resumo["produtos"] / resumo["produtos"].sum()
    resumo["pct_receita"] = resumo["receita"] / resumo["receita"].sum()
    gr = dict(x=list(range(1, len(t) + 1)), y=[round(v * 100, 2) for v in t["pct_acum"]])
    return render_template("abc.html", ci=ci, cf=cf, t=recs(t), resumo=recs(resumo), g=gr)


@bp.route("/vendas/promocoes")
def promocoes():
    ci, cf, d_ini, d_fim = periodo(6)
    ef = R.efeito_promocoes(d_ini, d_fim)
    if len(ef):
        ef["lift"] = ef["qtd_dia_promo"] / ef["qtd_dia_normal"] - 1
    camp = df("""SELECT campanha, data_inicio, data_fim, COUNT(*) itens FROM promocoes
                 WHERE data_fim >= ? AND data_inicio <= ? GROUP BY 1,2,3 ORDER BY 2 DESC""", (d_ini, d_fim))
    atuais = df("""SELECT p.descricao, pr.preco_normal, pr.preco_promocional, pr.data_inicio, pr.data_fim
                   FROM promocoes pr JOIN produtos p ON p.id=pr.produto_id
                   WHERE pr.data_inicio = (SELECT MAX(data_inicio) FROM promocoes) ORDER BY p.descricao""")
    if quer_excel():
        return exportar_excel({"efeito": ef, "campanhas": camp}, f"promocoes_{ci}_{cf}")
    return render_template("promocoes.html", ci=ci, cf=cf, ef=recs(ef), camp=recs(camp), atuais=recs(atuais))


@bp.route("/vendas/cupons")
def cupons():
    dia = request.args.get("dia") or R.data_referencia().isoformat()
    pag = int(request.args.get("pag", 1))
    ids = R.un(True)
    P = R.ph(ids)
    total = val(f"SELECT COUNT(*) FROM vendas WHERE data=? AND unidade_id IN ({P})", (dia, *ids))
    linhas = q(f"""SELECT v.*, f.nome operador, c.nome cliente, u.codigo unidade FROM vendas v
                   LEFT JOIN funcionarios f ON f.id=v.operador_id LEFT JOIN clientes c ON c.id=v.cliente_id
                   JOIN unidades u ON u.id=v.unidade_id
                   WHERE v.data=? AND v.unidade_id IN ({P}) ORDER BY v.id DESC LIMIT 100 OFFSET ?""",
               (dia, *ids, (pag - 1) * 100))
    resumo = q(f"""SELECT COUNT(*) n, SUM(valor_total) receita, AVG(valor_total) ticket FROM vendas
                   WHERE data=? AND status='CONCLUIDA' AND unidade_id IN ({P})""", (dia, *ids), one=True)
    periodo_cupons = q("SELECT MIN(data) ini, MAX(data) fim FROM vendas", one=True)
    return render_template("cupons.html", dia=dia, linhas=linhas, pag=pag, paginas=max(1, math.ceil(total / 100)),
                           resumo=resumo, periodo_cupons=periodo_cupons)


@bp.route("/vendas/cupom/<int:vid>")
def cupom(vid):
    v = q("""SELECT v.*, f.nome operador, c.nome cliente, u.codigo || ' · ' || u.nome unidade FROM vendas v
             LEFT JOIN funcionarios f ON f.id=v.operador_id LEFT JOIN clientes c ON c.id=v.cliente_id
             JOIN unidades u ON u.id=v.unidade_id WHERE v.id=?""", (vid,), one=True)
    if not v:
        abort(404)
    itens = q("""SELECT i.*, p.descricao, p.sku, p.unidade FROM itens_venda i JOIN produtos p ON p.id=i.produto_id
                 WHERE i.venda_id=? ORDER BY i.id""", (vid,))
    return render_template("cupom.html", v=v, itens=itens)


# ---------------------------------------------------------------------------
# PDV
# ---------------------------------------------------------------------------
def preco_vigente(uid, pid, dia):
    fator = val("SELECT fator_preco FROM unidades WHERE id=?", (uid,)) or 1.0
    pr = val("""SELECT preco_promocional FROM promocoes WHERE produto_id=? AND ? BETWEEN data_inicio AND data_fim
                ORDER BY id DESC LIMIT 1""", (pid, dia))
    base = float(pr) if pr else float(val("SELECT preco_atual FROM produtos WHERE id=?", (pid,)))
    return round(max(math.ceil(base * fator * 10 - 1e-9) / 10 - 0.01, 0.49), 2), 1 if pr else 0


@bp.route("/pdv", methods=["GET", "POST"])
def pdv():
    if request.method == "POST":
        dados = request.get_json()
        uid = int(dados.get("unidade_id") or 0)
        if g.por_id.get(uid, {}).get("tipo") != "LOJA":
            return jsonify(erro="Escolha a loja."), 400
        dia = dados.get("data") or date.today().isoformat()
        hora = dados.get("hora") or datetime.now().strftime("%H:%M:%S")
        itens = [i for i in dados.get("itens", []) if float(i.get("quantidade", 0)) > 0]
        if not itens:
            return jsonify(erro="Inclua ao menos um item."), 400
        linhas, bruto, custo = [], 0.0, 0.0
        for it in itens:
            pid, qtd = int(it["produto_id"]), float(it["quantidade"])
            est = q("SELECT quantidade, custo_medio FROM estoque WHERE unidade_id=? AND produto_id=?", (uid, pid), one=True)
            if est is None or est["quantidade"] < qtd - 1e-9:
                desc = val("SELECT descricao FROM produtos WHERE id=?", (pid,))
                return jsonify(erro=f"Estoque insuficiente de {desc} nesta loja (disponível: {est['quantidade'] if est else 0:g})."), 400
            preco, promo = preco_vigente(uid, pid, dia)
            v = round(qtd * preco, 2)
            linhas.append((pid, qtd, preco, est["custo_medio"], promo, v))
            bruto += v
            custo += qtd * est["custo_medio"]
        forma = dados.get("forma_pagamento", "DINHEIRO")
        desconto = round(float(dados.get("desconto") or 0), 2)
        cliente = val("SELECT id FROM clientes WHERE cpf=?", (dados["cpf"],)) if dados.get("cpf") else None
        vid = exec_("""INSERT INTO vendas (unidade_id,data,hora,pdv,operador_id,cliente_id,forma_pagamento,qtd_itens,
                       valor_bruto,desconto,valor_total,custo_total,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'CONCLUIDA')""",
                    (uid, dia, hora, int(dados.get("pdv") or 1), dados.get("operador_id") or None, cliente, forma,
                     len(linhas), round(bruto, 2), desconto, round(bruto - desconto, 2), round(custo, 2)))
        for pid, qtd, preco, cu, promo, v in linhas:
            exec_("""INSERT INTO itens_venda (venda_id,produto_id,quantidade,preco_unitario,custo_unitario,em_promocao,
                     valor_total) VALUES (?,?,?,?,?,?,?)""", (vid, pid, qtd, preco, cu, promo, v))
            exec_("UPDATE estoque SET quantidade=quantidade-?, atualizado_em=? WHERE unidade_id=? AND produto_id=?",
                  (qtd, f"{dia} {hora}", uid, pid))
            exec_("""INSERT INTO resumo_vendas_diario (unidade_id,data,produto_id,quantidade,receita,custo) VALUES (?,?,?,?,?,?)
                     ON CONFLICT(unidade_id,data,produto_id) DO UPDATE SET quantidade=quantidade+excluded.quantidade,
                     receita=receita+excluded.receita, custo=custo+excluded.custo""", (uid, dia, pid, qtd, v, qtd * cu))
        exec_("""INSERT INTO resumo_cupons_diario VALUES (?,?,?,1,?,?,?,?,?,?)
                 ON CONFLICT(unidade_id,data,forma_pagamento) DO UPDATE SET cupons=cupons+1, itens=itens+excluded.itens,
                 valor_bruto=valor_bruto+excluded.valor_bruto, desconto=desconto+excluded.desconto,
                 valor_total=valor_total+excluded.valor_total, custo_total=custo_total+excluded.custo_total,
                 cupons_fidelidade=cupons_fidelidade+excluded.cupons_fidelidade""",
              (uid, dia, forma, len(linhas), round(bruto, 2), desconto, round(bruto - desconto, 2), round(custo, 2),
               1 if cliente else 0))
        get_db().commit()
        return jsonify(ok=True, venda_id=vid, total=round(bruto - desconto, 2))
    uid = unidade_escolhida()
    produtos, operadores = [], []
    if uid:
        fator = val("SELECT fator_preco FROM unidades WHERE id=?", (uid,)) or 1
        produtos = q("""SELECT p.id, p.sku, p.ean, p.descricao, p.unidade, p.preco_atual * ? preco, e.quantidade estoque
                        FROM produtos p JOIN estoque e ON e.produto_id=p.id AND e.unidade_id=?
                        JOIN categorias c ON c.id=p.categoria_id WHERE c.revenda=1 AND p.ativo=1 ORDER BY p.descricao""",
                     (fator, uid))
        operadores = q("""SELECT f.id, f.nome FROM funcionarios f JOIN cargos c ON c.id=f.cargo_id
                          WHERE f.unidade_id=? AND f.data_demissao IS NULL AND c.nome IN ('Operador de Caixa','Fiscal de Caixa')
                          ORDER BY f.nome""", (uid,))
    return render_template("pdv.html", uid=uid, lojas=opcoes_unidades(), produtos=produtos, operadores=operadores)


# ---------------------------------------------------------------------------
# Compras
# ---------------------------------------------------------------------------
@bp.route("/compras")
def compras():
    ci, cf, d_ini, d_fim = periodo(1)
    status = request.args.get("status", "")
    forn = request.args.get("fornecedor", "")
    ids = R.un()
    P = R.ph(ids)
    sql = f"""SELECT p.*, f.nome_fantasia fornecedor, f.abrangencia, fu.nome comprador, u.codigo unidade,
                     (SELECT COUNT(*) FROM itens_compra i WHERE i.pedido_id=p.id) linhas
              FROM pedidos_compra p JOIN fornecedores f ON f.id=p.fornecedor_id JOIN unidades u ON u.id=p.unidade_id
              LEFT JOIN funcionarios fu ON fu.id=p.comprador_id
              WHERE p.unidade_id IN ({P}) AND (p.data_pedido BETWEEN ? AND ? OR p.status='ABERTO')"""
    pr = [*ids, d_ini, d_fim]
    if status:
        sql += " AND p.status=?"
        pr.append(status)
    if forn:
        sql += " AND p.fornecedor_id=?"
        pr.append(forn)
    pedidos = df(sql + " ORDER BY p.data_pedido DESC, p.id DESC", pr)
    por_forn = df(f"""SELECT f.nome_fantasia fornecedor, f.abrangencia, COUNT(*) pedidos, SUM(p.valor_total) valor,
                             AVG(p.distancia_km) km, AVG(julianday(p.data_recebimento)-julianday(p.data_pedido)) lead_real,
                             SUM(p.status='RECEBIDO_PARCIAL')*1.0/COUNT(*) pct_parcial
                      FROM pedidos_compra p JOIN fornecedores f ON f.id=p.fornecedor_id
                      WHERE p.unidade_id IN ({P}) AND p.data_pedido BETWEEN ? AND ? GROUP BY f.id ORDER BY valor DESC""",
                  (*ids, d_ini, d_fim))
    mensal = df(f"""SELECT substr(data_recebimento,1,7) c, SUM(valor_total) valor FROM pedidos_compra
                    WHERE data_recebimento IS NOT NULL AND unidade_id IN ({P}) GROUP BY 1 ORDER BY 1""", tuple(ids))
    if quer_excel():
        return exportar_excel({"pedidos": pedidos, "por_fornecedor": por_forn, "mensal": mensal}, f"compras_{ci}_{cf}")
    fornecedores = q("SELECT id, nome_fantasia FROM fornecedores ORDER BY 2")
    gr = dict(meses=[R.rotulo_mes(c) for c in mensal["c"]], valor=[round(v, 2) for v in mensal["valor"]])
    return render_template("compras.html", ci=ci, cf=cf, pedidos=recs(pedidos.head(300)), n=len(pedidos),
                           por_forn=recs(por_forn), fornecedores=fornecedores, status=status, forn=forn, g=gr)


@bp.route("/compras/<int:pid>")
def pedido(pid):
    p = q("""SELECT p.*, f.nome_fantasia fornecedor, f.razao_social, fu.nome comprador, u.codigo || ' · ' || u.nome unidade
             FROM pedidos_compra p JOIN fornecedores f ON f.id=p.fornecedor_id LEFT JOIN funcionarios fu ON fu.id=p.comprador_id
             JOIN unidades u ON u.id=p.unidade_id WHERE p.id=?""", (pid,), one=True)
    if not p:
        abort(404)
    itens = q("""SELECT i.*, pr.descricao, pr.sku, pr.unidade FROM itens_compra i JOIN produtos pr ON pr.id=i.produto_id
                 WHERE i.pedido_id=? ORDER BY pr.descricao""", (pid,))
    cp = q("SELECT * FROM contas_pagar WHERE origem='COMPRA' AND referencia=?", (f"PC-{pid:06d}",))
    return render_template("pedido.html", p=p, itens=itens, cp=cp, hoje_iso=date.today().isoformat())


def entrada_estoque(uid, pid, qtd, custo, dia):
    est = q("SELECT quantidade, custo_medio FROM estoque WHERE unidade_id=? AND produto_id=?", (uid, pid), one=True)
    if est is None:
        exec_("""INSERT INTO estoque (unidade_id,produto_id,quantidade,custo_medio,estoque_minimo,estoque_maximo,atualizado_em)
                 VALUES (?,?,?,?,0,0,?)""", (uid, pid, qtd, custo, dia))
        return
    q0 = max(est["quantidade"], 0)
    novo_cm = (q0 * est["custo_medio"] + qtd * custo) / (q0 + qtd) if q0 + qtd > 0 else custo
    exec_("UPDATE estoque SET quantidade=quantidade+?, custo_medio=?, atualizado_em=? WHERE unidade_id=? AND produto_id=?",
          (qtd, round(novo_cm, 4), dia, uid, pid))


@bp.route("/compras/<int:pid>/receber", methods=["POST"])
def receber_pedido(pid):
    p = q("SELECT * FROM pedidos_compra WHERE id=?", (pid,), one=True)
    if not p or p["status"] != "ABERTO":
        flash("Pedido não está em aberto.", "erro")
        return redirect(url_for("com.pedido", pid=pid))
    dia = request.form.get("data") or date.today().isoformat()
    total, parcial = 0.0, False
    dep = val("SELECT id FROM departamentos WHERE nome=?",
              ("Logística (CD)" if g.por_id[p["unidade_id"]]["tipo"] == "CD" else "Recebimento/Depósito",))
    for it in q("SELECT * FROM itens_compra WHERE pedido_id=?", (pid,)):
        qrec = float(request.form.get(f"rec_{it['id']}", it["quantidade_pedida"]) or 0)
        parcial |= qrec < it["quantidade_pedida"] - 1e-9
        valor = round(qrec * it["custo_unitario"], 2)
        total += valor
        exec_("UPDATE itens_compra SET quantidade_recebida=?, valor_total=? WHERE id=?", (qrec, valor, it["id"]))
        if qrec > 0:
            entrada_estoque(p["unidade_id"], it["produto_id"], qrec, it["custo_unitario"], dia)
            exec_("""INSERT INTO movimentacoes_estoque (unidade_id,data,produto_id,tipo,quantidade,custo_unitario,motivo,
                     departamento_id,referencia) VALUES (?,?,?,'ENTRADA_COMPRA',?,?,'Recebimento de mercadoria',?,?)""",
                  (p["unidade_id"], dia, it["produto_id"], qrec, it["custo_unitario"], dep, f"PC-{pid:06d}"))
    exec_("UPDATE pedidos_compra SET status=?, data_recebimento=?, nota_fiscal=?, valor_total=? WHERE id=?",
          ("RECEBIDO_PARCIAL" if parcial else "RECEBIDO", dia, request.form.get("nota_fiscal") or "", round(total, 2), pid))
    venc = (date.fromisoformat(dia) + timedelta(days=p["prazo_pagamento_dias"])).isoformat()
    forn = val("SELECT nome_fantasia FROM fornecedores WHERE id=?", (p["fornecedor_id"],))
    exec_("""INSERT INTO contas_pagar (unidade_id,origem,referencia,favorecido,competencia,data_emissao,data_vencimento,valor,status)
             VALUES (?,'COMPRA',?,?,?,?,?,?,'ABERTO')""", (p["unidade_id"], f"PC-{pid:06d}", forn, dia[:7], dia, venc, round(total, 2)))
    get_db().commit()
    flash(f"Pedido recebido. Título de R$ {total:,.2f} gerado no contas a pagar (vencimento {venc}).", "ok")
    return redirect(url_for("com.pedido", pid=pid))


def fornecedores_da_unidade(uid):
    u = q("SELECT u.tipo, c.regiao FROM unidades u JOIN cidades c ON c.id=u.cidade_id WHERE u.id=?", (uid,), one=True)
    if u["tipo"] == "CD":
        return q("SELECT * FROM fornecedores WHERE abrangencia='NACIONAL' ORDER BY nome_fantasia")
    return q("SELECT * FROM fornecedores WHERE abrangencia='REGIONAL' AND regiao_atendida=? ORDER BY nome_fantasia",
             (u["regiao"],))


@bp.route("/compras/novo", methods=["GET", "POST"])
def novo_pedido():
    if request.method == "POST":
        dados = request.get_json()
        uid, fid = int(dados["unidade_id"]), int(dados["fornecedor_id"])
        itens = [i for i in dados.get("itens", []) if float(i.get("quantidade") or 0) > 0]
        if not itens:
            return jsonify(erro="Inclua ao menos um item."), 400
        f = q("SELECT * FROM fornecedores WHERE id=?", (fid,), one=True)
        dia = dados.get("data") or date.today().isoformat()
        prev = (date.fromisoformat(dia) + timedelta(days=2)).isoformat()
        pid = exec_("""INSERT INTO pedidos_compra (unidade_id,fornecedor_id,comprador_id,data_pedido,data_prevista,status,
                       valor_total,prazo_pagamento_dias) VALUES (?,?,?,?,?,'ABERTO',0,?)""",
                    (uid, fid, dados.get("comprador_id") or None, dia, prev, f["prazo_pagamento_dias"]))
        total = 0.0
        for it in itens:
            cu, qtd = float(it["custo"]), float(it["quantidade"])
            total += qtd * cu
            exec_("""INSERT INTO itens_compra (pedido_id,produto_id,quantidade_pedida,custo_unitario,valor_total)
                     VALUES (?,?,?,?,?)""", (pid, int(it["produto_id"]), qtd, cu, round(qtd * cu, 2)))
        exec_("UPDATE pedidos_compra SET valor_total=? WHERE id=?", (round(total, 2), pid))
        get_db().commit()
        return jsonify(ok=True, pedido_id=pid)
    uid = unidade_escolhida(("LOJA", "CD"))
    fornecedores, produtos, compradores = [], [], []
    if uid:
        fornecedores = fornecedores_da_unidade(uid)
        tipos = tuple({f["tipo"] for f in fornecedores})
        canal = "CD" if g.por_id[uid]["tipo"] == "CD" else "DIRETO"
        fat = {f["tipo"]: f["fator_custo"] for f in fornecedores}
        produtos = q(f"""SELECT p.id, p.descricao, p.tipo_fornecedor, p.custo_atual custo, p.embalagem_compra emb, p.unidade,
                                COALESCE(e.quantidade,0) estoque, COALESCE(e.estoque_minimo,0) minimo,
                                COALESCE(e.estoque_maximo,0) maximo
                         FROM produtos p JOIN categorias c ON c.id=p.categoria_id
                         LEFT JOIN estoque e ON e.produto_id=p.id AND e.unidade_id=?
                         WHERE p.ativo=1 AND c.canal=? AND p.tipo_fornecedor IN ({R.ph(tipos)}) ORDER BY p.descricao""",
                     (uid, canal, *tipos))
        for p in produtos:
            p["custo"] = round(p["custo"] * (1 - param("desconto_compra_cd")) if canal == "CD" else p["custo"] * fat.get(p["tipo_fornecedor"], 1), 2)
            p["forn_ids"] = [f["id"] for f in fornecedores if f["tipo"] == p["tipo_fornecedor"]]
        compradores = q("""SELECT f.id, f.nome FROM funcionarios f JOIN cargos c ON c.id=f.cargo_id
                           WHERE f.data_demissao IS NULL AND (f.unidade_id=? OR c.nome='Comprador Corporativo')
                           AND c.nome IN ('Comprador','Comprador Corporativo','Gerente Geral','Subgerente','Gerente de CD')""",
                        (uid,))
    return render_template("pedido_novo.html", uid=uid, unidades=opcoes_unidades(("LOJA", "CD")), fornecedores=fornecedores,
                           produtos=produtos, compradores=compradores)


# ---------------------------------------------------------------------------
# Transferências CD -> loja
# ---------------------------------------------------------------------------
@bp.route("/transferencias")
def transferencias():
    ci, cf, d_ini, d_fim = periodo(1)
    ids = R.un()
    P = R.ph(ids)
    t = df(f"""SELECT t.*, cd.codigo cd, lj.codigo loja, lj.nome loja_nome FROM transferencias t
               JOIN unidades cd ON cd.id=t.cd_id JOIN unidades lj ON lj.id=t.loja_id
               WHERE (t.cd_id IN ({P}) OR t.loja_id IN ({P})) AND (t.data_envio BETWEEN ? AND ? OR t.status='EM_TRANSITO')
               ORDER BY t.data_envio DESC, t.id DESC""", (*ids, *ids, d_ini, d_fim))
    if quer_excel():
        return exportar_excel(t, f"transferencias_{ci}_{cf}")
    resumo = t.groupby(["cd", "loja"]).agg(envios=("id", "count"), valor=("valor_transferencia", "sum"),
                                           frete=("custo_frete", "sum"), km=("distancia_km", "first"),
                                           viagens=("viagens", "sum")).reset_index() if len(t) else t
    if len(resumo):
        resumo["frete_pct"] = resumo["frete"] / resumo["valor"]
    return render_template("transferencias.html", ci=ci, cf=cf, t=recs(t.head(300)), n=len(t), resumo=recs(resumo))


@bp.route("/transferencias/<int:tid>", methods=["GET", "POST"])
def transferencia(tid):
    t = q("""SELECT t.*, cd.codigo cd, cd.nome cd_nome, lj.codigo loja, lj.nome loja_nome, lj.modelo FROM transferencias t
             JOIN unidades cd ON cd.id=t.cd_id JOIN unidades lj ON lj.id=t.loja_id WHERE t.id=?""", (tid,), one=True)
    if not t:
        abort(404)
    if request.method == "POST" and t["status"] == "EM_TRANSITO":
        dia = request.form.get("data") or date.today().isoformat()
        for it in q("SELECT * FROM itens_transferencia WHERE transferencia_id=?", (tid,)):
            if it["quantidade_enviada"] > 0:
                entrada_estoque(t["loja_id"], it["produto_id"], it["quantidade_enviada"], it["preco_transferencia"], dia)
        parcial = val("SELECT COUNT(*) FROM itens_transferencia WHERE transferencia_id=? AND quantidade_enviada < quantidade_solicitada", (tid,))
        exec_("UPDATE transferencias SET status=?, data_recebimento=? WHERE id=?",
              ("RECEBIDA_PARCIAL" if parcial else "RECEBIDA", dia, tid))
        if t["modelo"] == "FRANQUIA":
            venc = (date.fromisoformat(dia) + timedelta(days=int(param("prazo_transferencia_franquia")))).isoformat()
            exec_("""INSERT INTO contas_pagar (unidade_id,origem,referencia,favorecido,favorecido_unidade_id,competencia,
                     data_emissao,data_vencimento,valor,status) VALUES (?,'TRANSFERENCIA',?,?,?,?,?,?,?,'ABERTO')""",
                  (t["loja_id"], f"TR-{tid:06d}", t["cd_nome"], t["cd_id"], dia[:7], dia, venc, t["valor_transferencia"]))
        get_db().commit()
        flash("Transferência recebida na loja.", "ok")
        return redirect(url_for("com.transferencia", tid=tid))
    itens = q("""SELECT i.*, p.descricao, p.sku FROM itens_transferencia i JOIN produtos p ON p.id=i.produto_id
                 WHERE i.transferencia_id=? ORDER BY p.descricao""", (tid,))
    return render_template("transferencia.html", t=t, itens=itens, hoje_iso=date.today().isoformat())


@bp.route("/compras/sugestao", methods=["GET", "POST"])
def sugestao():
    t = R.sugestao_compra(ids=R.un(False))
    if request.method == "POST":
        dia = date.today().isoformat()
        npc = ntr = 0
        for uid, gu in t.groupby("unidade_id"):
            uid = int(uid)
            u = q("SELECT u.*, c.regiao FROM unidades u JOIN cidades c ON c.id=u.cidade_id WHERE u.id=?", (uid,), one=True)
            forn = {f["tipo"]: f for f in fornecedores_da_unidade(uid)}
            # itens do CD -> transferência
            gcd = gu[gu["origem"] == "CD da rede"]
            if len(gcd) and u["cd_id"]:
                tid = exec_("""INSERT INTO transferencias (cd_id,loja_id,data_pedido,data_envio,status,valor_custo_cd,
                               valor_transferencia,distancia_km,viagens,custo_frete) VALUES (?,?,?,?,'EM_TRANSITO',0,0,?,1,0)""",
                            (u["cd_id"], uid, dia, dia, u["distancia_cd_km"]))
                vcd = vtr = 0.0
                for _, r in gcd.iterrows():
                    pid = int(r["id"])
                    e_cd = q("SELECT quantidade, custo_medio FROM estoque WHERE unidade_id=? AND produto_id=?", (u["cd_id"], pid), one=True)
                    env = float(min(r["sugerido"], max(e_cd["quantidade"], 0))) if e_cd else 0.0
                    ref = val("SELECT custo_atual FROM produtos WHERE id=?", (pid,))
                    pt = round(ref * (1 + param("markup_transferencia")), 4)
                    cu = e_cd["custo_medio"] if e_cd else ref
                    exec_("""INSERT INTO itens_transferencia (transferencia_id,produto_id,quantidade_solicitada,quantidade_enviada,
                             custo_cd,preco_transferencia) VALUES (?,?,?,?,?,?)""", (tid, pid, float(r["sugerido"]), env, cu, pt))
                    if env > 0:
                        exec_("UPDATE estoque SET quantidade=quantidade-? WHERE unidade_id=? AND produto_id=?", (env, u["cd_id"], pid))
                    vcd += env * cu
                    vtr += env * pt
                viagens = max(1, math.ceil(vtr / param("valor_por_viagem")))
                frete = viagens * (param("frete_fixo_viagem") + param("frete_por_km") * (u["distancia_cd_km"] or 0))
                exec_("UPDATE transferencias SET valor_custo_cd=?, valor_transferencia=?, viagens=?, custo_frete=? WHERE id=?",
                      (round(vcd, 2), round(vtr, 2), viagens, round(frete, 2), tid))
                ntr += 1
            # demais itens -> pedido ao fornecedor (regional para loja, nacional para CD)
            gf = gu[gu["origem"] == "Fornecedor"].merge(df("SELECT id, tipo_fornecedor FROM produtos"), on="id")
            for tipo, gt in gf.groupby("tipo_fornecedor"):
                f = forn.get(tipo)
                if not f:
                    continue
                pid = exec_("""INSERT INTO pedidos_compra (unidade_id,fornecedor_id,data_pedido,data_prevista,status,valor_total,
                               prazo_pagamento_dias) VALUES (?,?,?,?,'ABERTO',?,?)""",
                            (uid, f["id"], dia, (date.today() + timedelta(days=2)).isoformat(),
                             round(float(gt["valor_sugerido"].sum()), 2), f["prazo_pagamento_dias"]))
                for _, r in gt.iterrows():
                    exec_("""INSERT INTO itens_compra (pedido_id,produto_id,quantidade_pedida,custo_unitario,valor_total)
                             VALUES (?,?,?,?,?)""", (pid, int(r["id"]), float(r["sugerido"]), float(r["custo_medio"]),
                                                     round(float(r["valor_sugerido"]), 2)))
                npc += 1
        get_db().commit()
        flash(f"{npc} pedido(s) a fornecedores e {ntr} transferência(s) do CD criados a partir da sugestão.", "ok")
        return redirect(url_for("com.compras", status="ABERTO"))
    if quer_excel():
        return exportar_excel(t, "sugestao_compra")
    return render_template("sugestao.html", t=recs(t), total=float(t["valor_sugerido"].sum()) if len(t) else 0)


# ---------------------------------------------------------------------------
# Estoque
# ---------------------------------------------------------------------------
@bp.route("/estoque")
def estoque():
    t = R.posicao_estoque(ids=R.un())
    cat = request.args.get("categoria", "")
    st = request.args.get("status", "")
    busca = request.args.get("busca", "").lower()
    giro = R.giro_por_categoria()
    if quer_excel():
        return exportar_excel({"posicao": t, "giro_categoria": giro}, "posicao_estoque")
    por_un = t.groupby(["unidade", "tipo_unidade"]).agg(valor=("valor", "sum"), skus=("id", "count"),
                                                        abaixo=("status", lambda s: int((s == "Abaixo do mínimo").sum())),
                                                        sem=("status", lambda s: int((s == "Sem estoque").sum()))).reset_index() if len(t) else t
    rev = t[t["revenda"] == 1] if len(t) else t
    resumo = dict(valor=t["valor"].sum() if len(t) else 0, skus=len(t),
                  sem=int((rev["status"] == "Sem estoque").sum()) if len(t) else 0,
                  abaixo=int((rev["status"] == "Abaixo do mínimo").sum()) if len(t) else 0,
                  excesso=int((t["status"] == "Excesso").sum()) if len(t) else 0,
                  cobertura=float(giro["valor_estoque"].sum() / max(giro["cmv_90d"].sum() / 90, 1)))
    if cat:
        t = t[t["categoria"] == cat]
    if st:
        t = t[t["status"] == st]
    if busca:
        t = t[t["descricao"].str.lower().str.contains(busca) | t["sku"].str.contains(busca)]
    cats = [r["nome"] for r in q("SELECT nome FROM categorias ORDER BY nome")]
    return render_template("estoque.html", t=recs(t.head(1500)), n=len(t), resumo=resumo, giro=recs(giro), cats=cats,
                           cat=cat, st=st, busca=busca, por_un=recs(por_un))


@bp.route("/estoque/<int:uid>/<int:pid>")
def produto_estoque(uid, pid):
    p = q("""SELECT p.*, c.nome categoria, c.canal, f.nome_fantasia fornecedor, e.quantidade, e.custo_medio, e.estoque_minimo,
                    e.estoque_maximo, u.codigo unidade_cod, u.nome unidade_nome, u.fator_preco
             FROM produtos p JOIN categorias c ON c.id=p.categoria_id JOIN fornecedores f ON f.id=p.fornecedor_id
             JOIN estoque e ON e.produto_id=p.id AND e.unidade_id=? JOIN unidades u ON u.id=e.unidade_id WHERE p.id=?""",
          (uid, pid), one=True)
    if not p:
        abort(404)
    k = R.kardex(uid, pid)
    if quer_excel():
        return exportar_excel(k, f"kardex_{p['unidade_cod']}_{p['sku']}")
    diario = k.groupby("data")["saldo"].last() if len(k) else k
    vend = df("""SELECT substr(data,1,7) c, SUM(quantidade) qtd FROM resumo_vendas_diario
                 WHERE unidade_id=? AND produto_id=? GROUP BY 1 ORDER BY 1""", (uid, pid))
    precos = df("SELECT competencia, custo, preco FROM historico_precos WHERE produto_id=? ORDER BY 1", (pid,))
    outras = q("""SELECT u.id, u.codigo, e.quantidade FROM estoque e JOIN unidades u ON u.id=e.unidade_id
                  WHERE e.produto_id=? ORDER BY u.codigo""", (pid,))
    gr = dict(dias=[d[8:10] + "/" + d[5:7] + "/" + d[2:4] for d in diario.index] if len(k) else [],
              saldo=[round(x, 3) for x in diario.values] if len(k) else [],
              meses=[R.rotulo_mes(c) for c in vend["c"]], qtd=[round(x, 3) for x in vend["qtd"]],
              pmeses=[R.rotulo_mes(c) for c in precos["competencia"]], custo=list(precos["custo"]),
              preco=[None if v != v else round(v * (p["fator_preco"] or 1), 2) for v in precos["preco"]])
    return render_template("produto_estoque.html", p=p, uid=uid, mov=recs(k.iloc[::-1].head(150)), g=gr, n=len(k),
                           outras=outras)


@bp.route("/estoque/perdas")
def perdas():
    ci, cf, d_ini, d_fim = periodo(12)
    t = R.perdas_mensais()
    t = t[(t["competencia"] >= ci) & (t["competencia"] <= cf)]
    rec = R.vendas_mensais().set_index("competencia")["receita"] if len(R.vendas_mensais()) else None
    P = R.ph(R.un())
    rup = df(f"""SELECT p.descricao, c.nome categoria, u.codigo unidade, COUNT(*) dias, SUM(r.qtd_nao_atendida) qtd,
                        SUM(r.venda_perdida_estimada) venda_perdida
                 FROM rupturas r JOIN produtos p ON p.id=r.produto_id JOIN categorias c ON c.id=p.categoria_id
                 JOIN unidades u ON u.id=r.unidade_id
                 WHERE r.unidade_id IN ({P}) AND r.data BETWEEN ? AND ? GROUP BY p.id, u.id ORDER BY venda_perdida DESC LIMIT 25""",
             (*R.un(), d_ini, d_fim))
    if quer_excel():
        return exportar_excel({"perdas": t, "rupturas": rup}, f"perdas_{ci}_{cf}")
    pc = t.pivot_table(index="competencia", columns="categoria", values="valor", aggfunc="sum").fillna(0)
    por_cat = t.groupby("categoria")["valor"].sum().sort_values(ascending=False)
    por_mot = t.groupby("motivo")["valor"].sum().sort_values(ascending=False)
    por_un = t.groupby("unidade")["valor"].sum().sort_values(ascending=False)
    mensal = pc.sum(axis=1)
    rec_tot = float(rec[(rec.index >= ci) & (rec.index <= cf)].sum()) if rec is not None else 0
    rec_un = df(f"""SELECT u.codigo unidade, SUM(r.valor_total) receita FROM resumo_cupons_diario r JOIN unidades u ON u.id=r.unidade_id
                    WHERE r.unidade_id IN ({P}) AND r.data BETWEEN ? AND ? GROUP BY 1""", (*R.un(), d_ini, d_fim)) \
        .set_index("unidade")["receita"]
    gr = dict(meses=[R.rotulo_mes(c) for c in mensal.index], valor=[round(v, 2) for v in mensal.values],
              pct=[round(mensal[c] / rec.get(c, np.nan) * 100, 2) if rec is not None else None for c in mensal.index])
    return render_template("perdas.html", ci=ci, cf=cf, g=gr, por_cat=list(por_cat.items()), por_mot=list(por_mot.items()),
                           por_un=[(k, v, (v / rec_un[k]) if rec_un.get(k) else None) for k, v in por_un.items()],
                           total=float(t["valor"].sum()), rec=rec_tot or None, rup=recs(rup))


@bp.route("/estoque/movimentar", methods=["GET", "POST"])
def movimentar():
    if request.method == "POST":
        uid = int(request.form["unidade_id"])
        pid = int(request.form["produto_id"])
        tipo = request.form["tipo"]
        qtd = abs(float(request.form["quantidade"].replace(",", ".")))
        dia = request.form.get("data") or date.today().isoformat()
        sinal = 1 if (tipo == "AJUSTE_INVENTARIO" and request.form.get("sentido") == "entrada") else -1
        est = q("SELECT quantidade, custo_medio FROM estoque WHERE unidade_id=? AND produto_id=?", (uid, pid), one=True)
        if est is None or (sinal < 0 and est["quantidade"] < qtd):
            flash("Quantidade maior que o estoque disponível nesta unidade.", "erro")
            return redirect(url_for("com.movimentar", unidade_id=uid))
        exec_("""INSERT INTO movimentacoes_estoque (unidade_id,data,produto_id,tipo,quantidade,custo_unitario,motivo,departamento_id)
                 VALUES (?,?,?,?,?,?,?,?)""", (uid, dia, pid, tipo, sinal * qtd, est["custo_medio"],
                                               request.form.get("motivo") or None, request.form.get("departamento_id") or None))
        exec_("UPDATE estoque SET quantidade=quantidade+?, atualizado_em=? WHERE unidade_id=? AND produto_id=?",
              (sinal * qtd, dia, uid, pid))
        get_db().commit()
        flash("Movimentação registrada.", "ok")
        return redirect(url_for("com.produto_estoque", uid=uid, pid=pid))
    uid = unidade_escolhida(("LOJA", "CD"))
    produtos = q("""SELECT p.id, p.descricao, p.unidade, e.quantidade FROM produtos p JOIN estoque e ON e.produto_id=p.id
                    WHERE e.unidade_id=? ORDER BY 2""", (uid,)) if uid else []
    deps = q("SELECT id, nome FROM departamentos ORDER BY nome")
    return render_template("movimentar.html", uid=uid, unidades=opcoes_unidades(("LOJA", "CD")), produtos=produtos, deps=deps,
                           tipo=request.args.get("tipo", "CONSUMO_INTERNO"), hoje_iso=date.today().isoformat())


@bp.route("/consumo")
def consumo():
    ci, cf, d_ini, d_fim = periodo(12)
    t = R.consumo_interno(d_ini, d_fim)
    if quer_excel():
        return exportar_excel(t, f"consumo_interno_{ci}_{cf}")
    mensal = t.groupby("competencia")["valor"].sum()
    por_dep = t.groupby("departamento")["valor"].sum().sort_values(ascending=False)
    por_mot = t.groupby("motivo")["valor"].sum().sort_values(ascending=False)
    por_un = t.groupby("unidade")["valor"].sum().sort_values(ascending=False)
    itens = t.groupby("descricao").agg(quantidade=("quantidade", "sum"), valor=("valor", "sum")) \
        .sort_values("valor", ascending=False).reset_index()
    gr = dict(meses=[R.rotulo_mes(c) for c in mensal.index], valor=[round(v, 2) for v in mensal.values])
    return render_template("consumo.html", ci=ci, cf=cf, g=gr, por_dep=list(por_dep.items()), por_mot=list(por_mot.items()),
                           por_un=list(por_un.items()), itens=recs(itens), total=float(t["valor"].sum()))
