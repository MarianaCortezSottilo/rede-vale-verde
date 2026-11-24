"""Regras de negócio e relatórios gerenciais da rede (todas as funções respeitam a seleção de unidades)."""
import math
from datetime import date, timedelta

import numpy as np
import pandas as pd
from flask import g

from .db import df, param, q, val

MESES_PT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


# ---------------------------------------------------------------------------
# Seleção de unidades
# ---------------------------------------------------------------------------
def un(lojas=False, ids=None):
    """Lista de ids da seleção atual (ou só lojas)."""
    if ids is not None:
        return list(ids)
    try:
        return list(g.un_lojas if lojas else g.un)
    except Exception:
        return [r["id"] for r in q("SELECT id FROM unidades WHERE tipo='LOJA'")]


def ph(ids):
    return ",".join("?" * len(ids))


def unidades_info(ids=None):
    sql = """SELECT u.*, c.nome cidade, c.uf, c.regiao, c.populacao, c.renda_per_capita, f.nome_fantasia franqueado,
                    cd.codigo cd_codigo, cd.nome cd_nome
             FROM unidades u JOIN cidades c ON c.id=u.cidade_id LEFT JOIN franqueados f ON f.id=u.franqueado_id
             LEFT JOIN unidades cd ON cd.id=u.cd_id"""
    if ids:
        return df(sql + f" WHERE u.id IN ({ph(ids)}) ORDER BY u.codigo", tuple(ids))
    return df(sql + " ORDER BY u.tipo DESC, u.codigo")


# ---------------------------------------------------------------------------
# Datas e competências
# ---------------------------------------------------------------------------
def data_referencia():
    d = val("SELECT MAX(data) FROM resumo_cupons_diario")
    return date.fromisoformat(d) if d else date.today()


def competencias():
    return [r["c"] for r in q("SELECT DISTINCT substr(data,1,7) c FROM resumo_cupons_diario ORDER BY 1")]


def fim_mes(c):
    a, m = int(c[:4]), int(c[5:])
    return date(a + (m == 12), m % 12 + 1, 1) - timedelta(days=1)


def ultima_competencia_fechada():
    for c in reversed(competencias()):
        if val("SELECT MAX(data) FROM resumo_cupons_diario WHERE data BETWEEN ? AND ?",
               (f"{c}-01", fim_mes(c).isoformat())) == fim_mes(c).isoformat():
            return c
    return competencias()[-1]


def rotulo_mes(c):
    return f"{MESES_PT[int(c[5:]) - 1]}/{c[2:4]}"


def comp_soma(c, n):
    a, m = int(c[:4]), int(c[5:]) - 1 + n
    return f"{a + m // 12:04d}-{m % 12 + 1:02d}"


def intervalo(c_ini, c_fim):
    out, c = [], c_ini
    while c <= c_fim:
        out.append(c)
        c = comp_soma(c, 1)
    return out


def limites(c_ini, c_fim):
    return f"{c_ini}-01", fim_mes(c_fim).isoformat()


# ---------------------------------------------------------------------------
# Vendas
# ---------------------------------------------------------------------------
def vendas_mensais(ids=None, por_unidade=False):
    ids = un(True, ids)
    grp = "unidade_id, " if por_unidade else ""
    v = df(f"""SELECT {grp}substr(data,1,7) competencia, SUM(cupons) cupons, SUM(valor_total) receita,
                      SUM(valor_bruto) bruto, SUM(custo_total) cmv, SUM(itens) itens, COUNT(DISTINCT data) dias,
                      SUM(cupons_fidelidade) fidelidade
               FROM resumo_cupons_diario WHERE unidade_id IN ({ph(ids)})
               GROUP BY {grp}competencia ORDER BY {grp}competencia""", tuple(ids))
    if v.empty:
        return v
    v["ticket_medio"] = v["receita"] / v["cupons"]
    v["margem_bruta"] = 1 - v["cmv"] / v["receita"]
    v["itens_por_cupom"] = v["itens"] / v["cupons"]
    v["receita_por_dia"] = v["receita"] / v["dias"]
    return v


def kpis_mes(c, ids=None):
    v = vendas_mensais(ids).set_index("competencia")
    if c not in v.index:
        return None
    atual = v.loc[c]
    ant = v.loc[comp_soma(c, -1)] if comp_soma(c, -1) in v.index else None
    aa = v.loc[comp_soma(c, -12)] if comp_soma(c, -12) in v.index else None

    def var(campo, base):
        return None if base is None or not base[campo] else atual[campo] / base[campo] - 1

    out = {}
    for campo in ("receita", "cupons", "ticket_medio", "margem_bruta", "itens_por_cupom"):
        out[campo] = dict(valor=float(atual[campo]), vs_mes=var(campo, ant), vs_ano=var(campo, aa))
    out["margem_bruta"]["vs_mes"] = None if ant is None else atual["margem_bruta"] - ant["margem_bruta"]
    out["margem_bruta"]["vs_ano"] = None if aa is None else atual["margem_bruta"] - aa["margem_bruta"]
    return out


def vendas_por_categoria(d_ini, d_fim, ids=None):
    ids = un(True, ids)
    return df(f"""SELECT c.nome categoria, SUM(r.receita) receita, SUM(r.custo) cmv, 1 - SUM(r.custo)/SUM(r.receita) margem
                  FROM resumo_vendas_diario r JOIN produtos p ON p.id=r.produto_id
                  JOIN categorias c ON c.id=p.categoria_id
                  WHERE r.unidade_id IN ({ph(ids)}) AND r.data BETWEEN ? AND ? GROUP BY 1 ORDER BY 2 DESC""",
              (*ids, d_ini, d_fim))


def vendas_dia_hora(d_ini, d_fim, ids=None):
    ids = un(True, ids)
    return df(f"""SELECT CAST(strftime('%w', data) AS INT) dow, CAST(substr(hora,1,2) AS INT) hora,
                         COUNT(*) cupons, SUM(valor_total) receita, COUNT(DISTINCT data || unidade_id) dias
                  FROM vendas WHERE unidade_id IN ({ph(ids)}) AND data BETWEEN ? AND ? AND status='CONCLUIDA'
                  GROUP BY 1,2""", (*ids, d_ini, d_fim))


def formas_pagamento(d_ini, d_fim, ids=None):
    ids = un(True, ids)
    return df(f"""SELECT forma_pagamento, SUM(cupons) cupons, SUM(valor_total) receita FROM resumo_cupons_diario
                  WHERE unidade_id IN ({ph(ids)}) AND data BETWEEN ? AND ? GROUP BY 1 ORDER BY 3 DESC""",
              (*ids, d_ini, d_fim))


def curva_abc(d_ini, d_fim, ids=None):
    ids = un(True, ids)
    t = df(f"""SELECT p.id, p.sku, p.descricao, c.nome categoria, SUM(r.quantidade) quantidade,
                      SUM(r.receita) receita, SUM(r.receita - r.custo) lucro_bruto
               FROM resumo_vendas_diario r JOIN produtos p ON p.id=r.produto_id
               JOIN categorias c ON c.id=p.categoria_id
               WHERE r.unidade_id IN ({ph(ids)}) AND r.data BETWEEN ? AND ? GROUP BY p.id ORDER BY receita DESC""",
           (*ids, d_ini, d_fim))
    if t.empty:
        return t
    t["pct"] = t["receita"] / t["receita"].sum()
    t["pct_acum"] = t["pct"].cumsum()
    t["classe"] = np.where(t["pct_acum"] - t["pct"] < 0.80, "A", np.where(t["pct_acum"] - t["pct"] < 0.95, "B", "C"))
    t["margem"] = t["lucro_bruto"] / t["receita"]
    return t


def top_produtos(d_ini, d_fim, n=15, ids=None):
    return curva_abc(d_ini, d_fim, ids).head(n)


def operadores(d_ini, d_fim, ids=None):
    ids = un(True, ids)
    return df(f"""SELECT f.nome, u.codigo unidade, COUNT(*) cupons, SUM(v.valor_total) receita, AVG(v.valor_total) ticket,
                         COUNT(DISTINCT v.data) dias
                  FROM vendas v JOIN funcionarios f ON f.id=v.operador_id JOIN unidades u ON u.id=v.unidade_id
                  WHERE v.unidade_id IN ({ph(ids)}) AND v.data BETWEEN ? AND ? GROUP BY f.id ORDER BY cupons DESC""",
              (*ids, d_ini, d_fim))


def efeito_promocoes(d_ini, d_fim, ids=None):
    ids = un(True, ids)
    pr = df("SELECT produto_id, data_inicio, data_fim FROM promocoes WHERE data_inicio <= ? AND data_fim >= ?",
            (d_fim, d_ini))
    vazio = pd.DataFrame(columns=["descricao", "qtd_dia_promo", "qtd_dia_normal", "margem_promo", "margem_normal",
                                  "dias_promo"])
    if pr.empty:
        return vazio
    dias_promo = set()
    for r in pr.itertuples():
        for d in pd.date_range(r.data_inicio, r.data_fim):
            dias_promo.add((r.produto_id, d.strftime("%Y-%m-%d")))
    pids = tuple(int(x) for x in pr["produto_id"].unique())
    v = df(f"""SELECT produto_id, data, SUM(quantidade) quantidade, SUM(receita) receita, SUM(custo) custo
               FROM resumo_vendas_diario WHERE unidade_id IN ({ph(ids)}) AND data BETWEEN ? AND ?
               AND produto_id IN ({ph(pids)}) GROUP BY 1,2""", (*ids, d_ini, d_fim, *pids))
    if v.empty:
        return vazio
    v["promo"] = [(p, d) in dias_promo for p, d in zip(v["produto_id"], v["data"])]
    gg = v.groupby(["produto_id", "promo"]).agg(qtd=("quantidade", "mean"), receita=("receita", "sum"),
                                                 custo=("custo", "sum"), dias=("data", "count")).reset_index()
    gg["margem"] = 1 - gg["custo"] / gg["receita"]
    a = gg[gg["promo"]].set_index("produto_id")
    b = gg[~gg["promo"]].set_index("produto_id")
    t = pd.DataFrame({"qtd_dia_promo": a["qtd"], "qtd_dia_normal": b["qtd"], "margem_promo": a["margem"],
                      "margem_normal": b["margem"], "dias_promo": a["dias"]}).dropna()
    nomes = df("SELECT id produto_id, descricao FROM produtos").set_index("produto_id")["descricao"]
    t.insert(0, "descricao", nomes.reindex(t.index).values)
    t = t.reset_index(drop=True)
    return t.sort_values(by="qtd_dia_promo", key=lambda s: s / t["qtd_dia_normal"], ascending=False)


# ---------------------------------------------------------------------------
# Estoque
# ---------------------------------------------------------------------------
def posicao_estoque(dias_media=28, ids=None):
    ids = un(False, ids)
    ref = data_referencia()
    ini = (ref - timedelta(days=dias_media - 1)).isoformat()
    fim = ref.isoformat()
    t = df(f"""SELECT e.unidade_id, u.codigo unidade, u.tipo tipo_unidade, p.id, p.sku, p.descricao, c.nome categoria,
                      c.canal, p.unidade medida, e.quantidade, e.custo_medio, e.quantidade*e.custo_medio valor,
                      e.estoque_minimo, e.estoque_maximo, c.revenda, p.embalagem_compra
               FROM estoque e JOIN produtos p ON p.id=e.produto_id JOIN categorias c ON c.id=p.categoria_id
               JOIN unidades u ON u.id=e.unidade_id
               WHERE e.unidade_id IN ({ph(ids)}) AND p.ativo=1 ORDER BY u.codigo, c.nome, p.descricao""", tuple(ids))
    if t.empty:
        return t
    vend = df(f"""SELECT unidade_id, produto_id id, SUM(quantidade) s FROM resumo_vendas_diario
                  WHERE unidade_id IN ({ph(ids)}) AND data BETWEEN ? AND ? GROUP BY 1,2""", (*ids, ini, fim))
    cons = df(f"""SELECT unidade_id, produto_id id, -SUM(quantidade) s FROM movimentacoes_estoque
                  WHERE unidade_id IN ({ph(ids)}) AND tipo='CONSUMO_INTERNO' AND data BETWEEN ? AND ? GROUP BY 1,2""",
              (*ids, ini, fim))
    env = df(f"""SELECT t.cd_id unidade_id, i.produto_id id, SUM(i.quantidade_enviada) s FROM itens_transferencia i
                 JOIN transferencias t ON t.id=i.transferencia_id
                 WHERE t.cd_id IN ({ph(ids)}) AND t.data_envio BETWEEN ? AND ? GROUP BY 1,2""", (*ids, ini, fim))
    saida = pd.concat([vend, cons, env]).groupby(["unidade_id", "id"])["s"].sum().rename("saida_periodo")
    t = t.merge(saida, left_on=["unidade_id", "id"], right_index=True, how="left")
    t["saida_periodo"] = pd.to_numeric(t["saida_periodo"], errors="coerce").fillna(0.0).astype(float)
    t["saida_dia"] = t["saida_periodo"] / dias_media
    t["cobertura_dias"] = t["quantidade"].astype(float) / t["saida_dia"].where(t["saida_dia"] > 0)
    t["status"] = np.select(
        [t["quantidade"] <= 0, t["quantidade"] < t["estoque_minimo"], t["quantidade"] > t["estoque_maximo"] * 1.5],
        ["Sem estoque", "Abaixo do mínimo", "Excesso"], "Normal")
    return t


def giro_por_categoria(ids=None):
    ids = un(False, ids)
    ref = data_referencia()
    ini = (ref - timedelta(days=89)).isoformat()
    cmv = df(f"""SELECT c.nome categoria, SUM(r.custo) cmv_90d FROM resumo_vendas_diario r
                 JOIN produtos p ON p.id=r.produto_id JOIN categorias c ON c.id=p.categoria_id
                 WHERE r.unidade_id IN ({ph(ids)}) AND r.data BETWEEN ? AND ? GROUP BY 1""", (*ids, ini, ref.isoformat()))
    trf = df(f"""SELECT c.nome categoria, SUM(i.quantidade_enviada*i.custo_cd) cmv_90d FROM itens_transferencia i
                 JOIN transferencias t ON t.id=i.transferencia_id JOIN produtos p ON p.id=i.produto_id
                 JOIN categorias c ON c.id=p.categoria_id
                 WHERE t.cd_id IN ({ph(ids)}) AND t.data_envio BETWEEN ? AND ? GROUP BY 1""", (*ids, ini, ref.isoformat()))
    cmv = pd.concat([cmv, trf]).groupby("categoria", as_index=False).sum()
    est = df(f"""SELECT c.nome categoria, SUM(e.quantidade*e.custo_medio) valor_estoque
                 FROM estoque e JOIN produtos p ON p.id=e.produto_id JOIN categorias c ON c.id=p.categoria_id
                 WHERE e.unidade_id IN ({ph(ids)}) GROUP BY 1""", tuple(ids))
    t = est.merge(cmv, on="categoria", how="left").fillna(0)
    t["valor_estoque"] = t["valor_estoque"].astype(float)
    t["cmv_90d"] = t["cmv_90d"].astype(float)
    t["cobertura_dias"] = t["valor_estoque"] / (t["cmv_90d"] / 90).where(t["cmv_90d"] > 0)
    t["giro_anual"] = (t["cmv_90d"] * 365 / 90) / t["valor_estoque"].where(t["valor_estoque"] > 0)
    return t.sort_values("valor_estoque", ascending=False)


def kardex(unidade_id, produto_id):
    movs = df("""SELECT data, tipo, quantidade, custo_unitario, motivo, referencia FROM movimentacoes_estoque
                 WHERE unidade_id=? AND produto_id=?""", (unidade_id, produto_id))
    vend = df("""SELECT data, 'VENDA' tipo, -quantidade quantidade, custo/NULLIF(quantidade,0) custo_unitario,
                        'Vendas do dia' motivo, NULL referencia
                 FROM resumo_vendas_diario WHERE unidade_id=? AND produto_id=?""", (unidade_id, produto_id))
    ent = df("""SELECT t.data_recebimento data, 'ENTRADA_TRANSFERENCIA' tipo, i.quantidade_enviada quantidade,
                       i.preco_transferencia custo_unitario, 'Recebido do ' || cd.codigo motivo,
                       'TR-' || printf('%06d', t.id) referencia
                FROM itens_transferencia i JOIN transferencias t ON t.id=i.transferencia_id
                JOIN unidades cd ON cd.id=t.cd_id
                WHERE t.loja_id=? AND i.produto_id=? AND t.data_recebimento IS NOT NULL AND i.quantidade_enviada > 0""",
             (unidade_id, produto_id))
    sai = df("""SELECT t.data_envio data, 'SAIDA_TRANSFERENCIA' tipo, -i.quantidade_enviada quantidade, i.custo_cd custo_unitario,
                       'Enviado para ' || lj.codigo motivo, 'TR-' || printf('%06d', t.id) referencia
                FROM itens_transferencia i JOIN transferencias t ON t.id=i.transferencia_id
                JOIN unidades lj ON lj.id=t.loja_id
                WHERE t.cd_id=? AND i.produto_id=? AND i.quantidade_enviada > 0""", (unidade_id, produto_id))
    t = pd.concat([x for x in (movs, vend, ent, sai) if not x.empty], ignore_index=True)
    if t.empty:
        return pd.DataFrame(columns=["data", "tipo", "quantidade", "custo_unitario", "motivo", "referencia", "saldo"])
    ordem = {"SALDO_INICIAL": 0, "ENTRADA_COMPRA": 1, "ENTRADA_TRANSFERENCIA": 1, "VENDA": 2, "SAIDA_TRANSFERENCIA": 3,
             "CONSUMO_INTERNO": 4, "PERDA": 5, "AJUSTE_INVENTARIO": 6}
    t["o"] = t["tipo"].map(ordem)
    t = t.sort_values(["data", "o"]).drop(columns="o")
    t["saldo"] = t["quantidade"].cumsum().round(3)
    return t


def perdas_mensais(ids=None):
    ids = un(False, ids)
    return df(f"""SELECT substr(m.data,1,7) competencia, u.codigo unidade, c.nome categoria, m.motivo,
                         -SUM(m.quantidade*m.custo_unitario) valor
                  FROM movimentacoes_estoque m JOIN produtos p ON p.id=m.produto_id
                  JOIN categorias c ON c.id=p.categoria_id JOIN unidades u ON u.id=m.unidade_id
                  WHERE m.unidade_id IN ({ph(ids)}) AND m.tipo IN ('PERDA','AJUSTE_INVENTARIO') GROUP BY 1,2,3,4""",
              tuple(ids))


def consumo_interno(d_ini, d_fim, ids=None):
    ids = un(False, ids)
    return df(f"""SELECT substr(m.data,1,7) competencia, u.codigo unidade, d.nome departamento, m.motivo, p.descricao,
                         -SUM(m.quantidade) quantidade, -SUM(m.quantidade*m.custo_unitario) valor
                  FROM movimentacoes_estoque m JOIN produtos p ON p.id=m.produto_id
                  LEFT JOIN departamentos d ON d.id=m.departamento_id JOIN unidades u ON u.id=m.unidade_id
                  WHERE m.unidade_id IN ({ph(ids)}) AND m.tipo='CONSUMO_INTERNO' AND m.data BETWEEN ? AND ?
                  GROUP BY 1,2,3,4,5 ORDER BY 1, valor DESC""", (*ids, d_ini, d_fim))


def sugestao_compra(ids=None):
    t = posicao_estoque(ids=ids)
    if t.empty:
        return t
    t = t[(t["quantidade"] < t["estoque_minimo"]) & (t["saida_dia"] > 0)].copy()
    t["sugerido"] = np.ceil((t["estoque_maximo"] - t["quantidade"]) / t["embalagem_compra"]) * t["embalagem_compra"]
    t["valor_sugerido"] = t["sugerido"] * t["custo_medio"]
    # de quem comprar: loja -> CD (itens de CD) ou fornecedor regional; CD -> fornecedor nacional
    t["origem"] = np.where((t["tipo_unidade"] == "LOJA") & (t["canal"] == "CD"), "CD da rede", "Fornecedor")
    return t.sort_values(["unidade", "origem", "descricao"])


# ---------------------------------------------------------------------------
# DRE
# ---------------------------------------------------------------------------
LINHAS_DRE = [
    ("receita_bruta", "Receita bruta de vendas (lojas)", 0),
    ("descontos", "(-) Descontos concedidos", 1),
    ("receitas_franquia", "(+) Royalties, fundo de marketing e taxas de franquia", 1),
    ("margem_distribuicao", "(+) Margem de distribuição dos CDs (transferências − custo)", 1),
    ("impostos_vendas", "(-) Impostos sobre vendas e serviços", 1),
    ("receita_liquida", "= Receita líquida", 2),
    ("cmv", "(-) Custo das mercadorias vendidas (CMV)", 1),
    ("lucro_bruto", "= Lucro bruto", 2),
    ("perdas", "(-) Perdas e quebras", 1),
    ("consumo_interno", "(-) Consumo interno", 1),
    ("margem_operacional", "= Margem após perdas", 2),
    ("pessoal_folha", "(-) Folha, encargos e benefícios", 1),
    ("pessoal_outros", "(-) Pró-labore e outras despesas de pessoal", 1),
    ("ocupacao", "(-) Ocupação (aluguel, IPTU, manutenção)", 1),
    ("utilidades", "(-) Energia, água e resíduos", 1),
    ("administrativas", "(-) Despesas administrativas", 1),
    ("comerciais", "(-) Despesas comerciais (cartões, marketing, entregas)", 1),
    ("franquia", "(-) Royalties e fundo de marketing pagos", 1),
    ("logistica", "(-) Fretes e logística", 1),
    ("ebitda", "= EBITDA", 2),
    ("depreciacao", "(-) Depreciação", 1),
    ("financeiras", "(-) Despesas financeiras", 1),
    ("lair", "= Lucro antes do IR/CSLL", 2),
    ("ir_csll", "(-) IRPJ/CSLL (estimado)", 1),
    ("lucro_liquido", "= Lucro líquido", 3),
]


def dre(comps, ids=None):
    """DRE por competência para a seleção de unidades. Na visão de rede, royalties e margem dos CDs
    aparecem como receita da franqueadora e como custo/despesa das lojas (o efeito líquido é zero)."""
    ids = un(False, ids)
    if not comps:
        return pd.DataFrame()
    d_ini, d_fim = limites(comps[0], comps[-1])
    P = ph(ids)
    icms, pis, ir = param("aliq_icms_efetiva"), param("aliq_pis_cofins_efetiva"), param("aliq_ir_csll")
    iss = param("aliq_impostos_servicos")
    v = df(f"""SELECT substr(data,1,7) c, SUM(valor_bruto) bruto, SUM(desconto) desconto, SUM(valor_total) receita,
                      SUM(custo_total) cmv FROM resumo_cupons_diario
               WHERE unidade_id IN ({P}) AND data BETWEEN ? AND ? GROUP BY 1""", (*ids, d_ini, d_fim)).set_index("c")
    m = df(f"""SELECT substr(data,1,7) c, tipo, -SUM(quantidade*custo_unitario) valor FROM movimentacoes_estoque
               WHERE unidade_id IN ({P}) AND tipo IN ('PERDA','AJUSTE_INVENTARIO','CONSUMO_INTERNO')
               AND data BETWEEN ? AND ? GROUP BY 1,2""", (*ids, d_ini, d_fim))
    f = df(f"""SELECT competencia c, SUM(custo_total) valor FROM folha_pagamento WHERE unidade_id IN ({P})
               AND competencia BETWEEN ? AND ? GROUP BY 1""", (*ids, comps[0], comps[-1])).set_index("c")["valor"]
    d = df(f"""SELECT d.competencia c, cd.grupo_dre g, SUM(d.valor) valor FROM despesas d
               JOIN categorias_despesa cd ON cd.id=d.categoria_id
               WHERE d.unidade_id IN ({P}) AND d.competencia BETWEEN ? AND ? GROUP BY 1,2""",
           (*ids, comps[0], comps[-1]))
    dg = d.pivot_table(index="c", columns="g", values="valor", aggfunc="sum").fillna(0) if not d.empty else pd.DataFrame()
    sede = val(f"SELECT id FROM unidades WHERE tipo='SEDE' AND id IN ({P})", tuple(ids))
    rf = df("SELECT competencia c, SUM(valor) valor FROM receitas_franquia WHERE competencia BETWEEN ? AND ? GROUP BY 1",
            (comps[0], comps[-1])).set_index("c")["valor"] if sede else pd.Series(dtype=float)
    md = df(f"""SELECT substr(data_envio,1,7) c, SUM(valor_transferencia - valor_custo_cd) valor FROM transferencias
                WHERE cd_id IN ({P}) AND data_envio BETWEEN ? AND ? GROUP BY 1""",
            (*ids, d_ini, d_fim)).set_index("c")["valor"]
    res = {}
    for c in comps:
        r = {}
        r["receita_bruta"] = float(v["bruto"].get(c, 0))
        r["descontos"] = -float(v["desconto"].get(c, 0))
        r["receitas_franquia"] = float(rf.get(c, 0))
        r["margem_distribuicao"] = float(md.get(c, 0))
        rec = float(v["receita"].get(c, 0))
        r["impostos_vendas"] = -rec * (icms + pis) - r["receitas_franquia"] * iss
        r["receita_liquida"] = sum(r[k] for k in ("receita_bruta", "descontos", "receitas_franquia",
                                                  "margem_distribuicao", "impostos_vendas"))
        r["cmv"] = -float(v["cmv"].get(c, 0))
        r["lucro_bruto"] = r["receita_liquida"] + r["cmv"]
        mm = m[m["c"] == c]
        r["perdas"] = -float(mm[mm["tipo"].isin(["PERDA", "AJUSTE_INVENTARIO"])]["valor"].sum())
        r["consumo_interno"] = -float(mm[mm["tipo"] == "CONSUMO_INTERNO"]["valor"].sum())
        r["margem_operacional"] = r["lucro_bruto"] + r["perdas"] + r["consumo_interno"]
        gr = dg.loc[c] if c in dg.index else pd.Series(dtype=float)
        r["pessoal_folha"] = -float(f.get(c, 0))
        for k, grupo in (("pessoal_outros", "PESSOAL"), ("ocupacao", "OCUPACAO"), ("utilidades", "UTILIDADES"),
                         ("administrativas", "ADMINISTRATIVA"), ("comerciais", "COMERCIAL"), ("franquia", "FRANQUIA"),
                         ("logistica", "LOGISTICA"), ("depreciacao", "DEPRECIACAO"), ("financeiras", "FINANCEIRA")):
            r[k] = -float(gr.get(grupo, 0))
        r["ebitda"] = r["margem_operacional"] + sum(r[k] for k in ("pessoal_folha", "pessoal_outros", "ocupacao",
                                                                       "utilidades", "administrativas", "comerciais",
                                                                       "franquia", "logistica"))
        r["lair"] = r["ebitda"] + r["depreciacao"] + r["financeiras"]
        r["ir_csll"] = -max(r["lair"], 0) * ir
        r["lucro_liquido"] = r["lair"] + r["ir_csll"]
        res[c] = r
    t = pd.DataFrame(res)
    t["Total"] = t.sum(axis=1)
    return t.loc[[k for k, _, _ in LINHAS_DRE]]


def dre_tabela(comps, ids=None):
    t = dre(comps, ids)
    linhas = []
    base = t.loc["receita_bruta"] + t.loc["receitas_franquia"] + t.loc["margem_distribuicao"]
    for k, rot, nivel in LINHAS_DRE:
        vals = t.loc[k].to_dict()
        if nivel == 1 and all(abs(x) < 0.005 for x in vals.values()):
            continue                      # esconde linhas zeradas para a seleção
        av = {c: (vals[c] / base[c] if base[c] else None) for c in t.columns}
        linhas.append(dict(chave=k, rotulo=rot, nivel=nivel, valores=vals, av=av))
    return list(t.columns), linhas


def resultado_por_unidade(comps, ids=None):
    """Indicadores de DRE de cada unidade (para comparativos e mapas)."""
    ids = un(False, ids)
    linhas = []
    for uid in ids:
        t = dre(comps, [uid])["Total"]
        base = t["receita_bruta"] + t["receitas_franquia"] + t["margem_distribuicao"]
        linhas.append(dict(unidade_id=uid, receita=t["receita_bruta"] + t["descontos"], base=base,
                           lucro_bruto=t["lucro_bruto"], perdas=-t["perdas"], folha=-t["pessoal_folha"],
                           ebitda=t["ebitda"], lair=t["lair"], lucro_liquido=t["lucro_liquido"],
                           franquia=-t["franquia"], logistica=-t["logistica"],
                           margem_ebitda=t["ebitda"] / base if base else None,
                           margem_lair=t["lair"] / base if base else None))
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------------------
# Fluxo de caixa (intercompany eliminado dentro da seleção)
# ---------------------------------------------------------------------------
def recebimentos(ids=None):
    ids = un(True, ids)
    return df(f"""SELECT date(data, '+' || CASE forma_pagamento WHEN 'DEBITO' THEN CAST(? AS INT)
                         WHEN 'CREDITO' THEN CAST(? AS INT) WHEN 'VOUCHER' THEN CAST(? AS INT) ELSE 0 END || ' days') dia,
                         SUM(valor_total) valor
                  FROM resumo_cupons_diario WHERE unidade_id IN ({ph(ids)}) GROUP BY 1""",
              (param("prazo_receb_debito"), param("prazo_receb_credito"), param("prazo_receb_voucher"), *ids))


def recebimentos_rede(ids=None):
    """Entradas vindas de outras unidades da rede (franqueado pagando CD/franqueadora) + taxas de franquia."""
    ids = un(False, ids)
    P = ph(ids)
    t = df(f"""SELECT COALESCE(data_pagamento, data_vencimento) dia, status, SUM(valor) valor FROM contas_pagar
               WHERE favorecido_unidade_id IN ({P}) AND unidade_id NOT IN ({P}) GROUP BY 1,2""", (*ids, *ids))
    if val(f"SELECT COUNT(*) FROM unidades WHERE tipo='SEDE' AND id IN ({P})", tuple(ids)):
        tx = df("SELECT data_recebimento dia, 'PAGO' status, valor FROM receitas_franquia WHERE tipo='TAXA_FRANQUIA'")
        t = pd.concat([t, tx], ignore_index=True)
    return t


def fluxo_caixa_mensal(ids=None):
    ids = un(False, ids)
    P = ph(ids)
    ref = data_referencia().isoformat()
    rec = recebimentos(ids)
    rec = rec[rec["dia"] <= ref].copy()
    rec["c"] = rec["dia"].str[:7]
    ent = rec.groupby("c")["valor"].sum()
    rr = recebimentos_rede(ids)
    rr = rr[(rr["status"] == "PAGO") & (rr["dia"] <= ref)].copy()
    rr["c"] = rr["dia"].str[:7]
    ent_rede = rr.groupby("c")["valor"].sum()
    pg = df(f"""SELECT substr(data_pagamento,1,7) c, origem, SUM(valor) valor FROM contas_pagar
                WHERE status='PAGO' AND data_pagamento <= ? AND unidade_id IN ({P})
                AND (favorecido_unidade_id IS NULL OR favorecido_unidade_id NOT IN ({P})) GROUP BY 1,2""",
            (ref, *ids, *ids))
    sai = pg.pivot_table(index="c", columns="origem", values="valor", aggfunc="sum").fillna(0) if not pg.empty else pd.DataFrame()
    cps = sorted(set(ent.index) | set(sai.index) | set(ent_rede.index))
    t = pd.DataFrame(index=cps)
    t["entradas_vendas"] = ent
    t["entradas_rede"] = ent_rede
    for o in ("COMPRA", "TRANSFERENCIA", "FOLHA", "ENCARGOS", "IMPOSTOS", "FRANQUIA", "DESPESA"):
        t["saida_" + o.lower()] = -(sai[o] if o in sai.columns else 0)
    t = t.fillna(0)
    t["saldo_mes"] = t.sum(axis=1)
    t["saldo_acumulado"] = param("saldo_caixa_inicial") * len(ids) + t["saldo_mes"].cumsum()
    return t.reset_index().rename(columns={"index": "competencia"})


def fluxo_projetado(dias=60, ids=None):
    ids = un(False, ids)
    P = ph(ids)
    ref = data_referencia()
    fim = (ref + timedelta(days=dias)).isoformat()
    rec = recebimentos(ids)
    rec = rec[(rec["dia"] > ref.isoformat()) & (rec["dia"] <= fim)].groupby("dia")["valor"].sum()
    rr = recebimentos_rede(ids)
    rr = rr[(rr["status"] == "ABERTO") & (rr["dia"] <= fim)].groupby("dia")["valor"].sum()
    cp = df(f"""SELECT data_vencimento dia, SUM(valor) valor FROM contas_pagar
                WHERE status='ABERTO' AND data_vencimento <= ? AND unidade_id IN ({P})
                AND (favorecido_unidade_id IS NULL OR favorecido_unidade_id NOT IN ({P})) GROUP BY 1""",
            (fim, *ids, *ids)).set_index("dia")["valor"]
    vencidas = float(cp[cp.index <= ref.isoformat()].sum())
    rr_venc = float(rr[rr.index <= ref.isoformat()].sum())
    idx = [(ref + timedelta(days=k)).isoformat() for k in range(1, dias + 1)]
    t = pd.DataFrame(index=idx)
    t["a_receber"] = rec.reindex(idx).fillna(0) + rr.reindex(idx).fillna(0)
    t["a_pagar"] = -cp.reindex(idx).fillna(0)
    t.loc[idx[0], "a_pagar"] -= vencidas
    t.loc[idx[0], "a_receber"] += rr_venc
    fm = fluxo_caixa_mensal(ids)
    saldo0 = float(fm["saldo_acumulado"].iloc[-1]) if len(fm) else 0.0
    t["saldo"] = saldo0 + (t["a_receber"] + t["a_pagar"]).cumsum()
    return saldo0, t.reset_index().rename(columns={"index": "dia"})


# ---------------------------------------------------------------------------
# RH
# ---------------------------------------------------------------------------
def headcount_mensal(ids=None):
    ids = un(False, ids)
    cps = competencias()
    funcs = df(f"""SELECT f.id, f.data_admissao, f.data_demissao, f.tipo_contrato FROM funcionarios f
                   WHERE f.unidade_id IN ({ph(ids)})""", tuple(ids))
    rows = []
    for c in cps:
        ini, fim = limites(c, c)
        ativos = funcs[(funcs["data_admissao"] <= fim) & (funcs["data_demissao"].isna() | (funcs["data_demissao"] > fim))]
        adm = funcs[(funcs["data_admissao"] >= ini) & (funcs["data_admissao"] <= fim)]
        dem = funcs[funcs["data_demissao"].notna() & (funcs["data_demissao"] >= ini) & (funcs["data_demissao"] <= fim)]
        ini_at = funcs[(funcs["data_admissao"] < ini) & (funcs["data_demissao"].isna() | (funcs["data_demissao"] >= ini))]
        media = (len(ini_at) + len(ativos)) / 2 or 1
        rows.append(dict(competencia=c, headcount=len(ativos), admissoes=len(adm), desligamentos=len(dem),
                         temporarios=int((ativos["tipo_contrato"] == "TEMPORARIO").sum()),
                         turnover=((len(adm) + len(dem)) / 2) / media))
    return pd.DataFrame(rows)


def folha_resumo(ids=None):
    ids = un(False, ids)
    return df(f"""SELECT competencia, COUNT(*) funcionarios, SUM(salario_bruto) bruto,
                         SUM(horas_extras_valor + dsr_horas_extras) horas_extras, SUM(fgts + inss_patronal) encargos,
                         SUM(vale_alimentacao + vale_transporte_custo - desconto_vt) beneficios,
                         SUM(provisao_13 + provisao_ferias + encargos_provisoes) provisoes, SUM(salario_liquido) liquido,
                         SUM(custo_total) custo_total
                  FROM folha_pagamento WHERE unidade_id IN ({ph(ids)}) GROUP BY 1 ORDER BY 1""", tuple(ids))


def folha_por_departamento(c, ids=None):
    ids = un(False, ids)
    return df(f"""SELECT d.nome departamento, COUNT(*) funcionarios, SUM(fp.salario_bruto) bruto,
                         SUM(fp.horas_extras_qtd) horas_extras, SUM(fp.custo_total) custo_total
                  FROM folha_pagamento fp JOIN funcionarios f ON f.id=fp.funcionario_id
                  JOIN cargos c ON c.id=f.cargo_id JOIN departamentos d ON d.id=c.departamento_id
                  WHERE fp.competencia=? AND fp.unidade_id IN ({ph(ids)}) GROUP BY 1 ORDER BY custo_total DESC""",
              (c, *ids))


# ---------------------------------------------------------------------------
# Projeções: modelo em painel (lojas maduras) + curva de maturação (lojas novas)
# ---------------------------------------------------------------------------
def maturacao(dias_abertos):
    return 0.55 + 0.45 * (1 - np.exp(-np.asarray(dias_abertos, dtype=float) / 120))


def _modelo_painel(ate=None):
    """log(receita/dia) = efeito da loja + tendência + sazonalidade mensal + log(maturação)."""
    v = vendas_mensais(ids=[r["id"] for r in q("SELECT id FROM unidades WHERE tipo='LOJA'")], por_unidade=True)
    inaug = {r["id"]: date.fromisoformat(r["data_inauguracao"]) for r in q("SELECT id, data_inauguracao FROM unidades")}
    if ate:
        v = v[v["competencia"] <= ate]
    # meses completos (≥ 25 dias de venda), exceto o mês de inauguração
    v = v[v["dias"] >= 25].copy()
    cps = sorted(v["competencia"].unique())
    v["t"] = v["competencia"].map({c: i for i, c in enumerate(cps)})
    v["mes"] = v["competencia"].str[5:].astype(int)
    v["dias_abertos"] = [(date.fromisoformat(c + "-15") - inaug[u]).days for u, c in zip(v["unidade_id"], v["competencia"])]
    v["mat"] = np.log(maturacao(v["dias_abertos"]))
    lojas = sorted(v["unidade_id"].unique())
    y = np.log(v["receita_por_dia"].values) - v["mat"].values
    X = [v["t"].values.astype(float)]
    for k in range(2, 13):
        X.append((v["mes"].values == k).astype(float))
    for u in lojas:
        X.append((v["unidade_id"].values == u).astype(float))
    X = np.vstack(X).T
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    sigma = float(np.sqrt((resid ** 2).sum() / max(1, len(y) - X.shape[1])))
    return dict(coef=coef, sigma=sigma, cps=cps, lojas=lojas, inaug=inaug, v=v, ultimo_t=len(cps) - 1)


def _dias_operacao(c):
    ini, fim = date.fromisoformat(c + "-01"), fim_mes(c)
    return (fim - ini).days + 1 - sum(1 for md in ("12-25", "01-01") if md[:2] == c[5:])


def projetar_receita(meses=12, ate=None, ids=None):
    ids = un(True, ids)
    M = _modelo_painel(ate)
    coef, cps = M["coef"], M["cps"]
    tend, saz = coef[0], np.concatenate([[0.0], coef[1:12]])
    efeito = {u: coef[12 + k] for k, u in enumerate(M["lojas"])}
    ult = cps[-1]
    futuros = [comp_soma(ult, k) for k in range(1, meses + 1)]
    proj = np.zeros(meses)
    for u in ids:
        if u not in efeito:
            continue
        for k, c in enumerate(futuros):
            dias_ab = (date.fromisoformat(c + "-15") - M["inaug"][u]).days
            if dias_ab < 0:
                continue
            ly = efeito[u] + tend * (M["ultimo_t"] + k + 1) + saz[int(c[5:]) - 1] + math.log(maturacao(dias_ab))
            proj[k] += math.exp(ly) * _dias_operacao(c)
    n_ef = max(1, len([u for u in ids if u in efeito]))
    sig = M["sigma"] / math.sqrt(n_ef) * 1.25
    z = 1.2816
    p = pd.DataFrame({"competencia": futuros, "receita": proj, "inferior": proj * math.exp(-z * sig),
                      "superior": proj * math.exp(z * sig)})
    hist = vendas_mensais(ids)
    if ate:
        hist = hist[hist["competencia"] <= ate]
    hist = hist[hist["competencia"].isin(cps) | (hist["competencia"] <= ult)]
    # ajuste in-sample agregado
    vv = M["v"][M["v"]["unidade_id"].isin(ids)].copy()
    if not vv.empty:
        vv["aj"] = [math.exp(efeito[u] + tend * t + saz[mm - 1] + mt) * dd for u, t, mm, mt, dd in
                    zip(vv["unidade_id"], vv["t"], vv["mes"], vv["mat"], vv["dias"])]
        aj = vv.groupby("competencia").agg(real=("receita", "sum"), ajustado=("aj", "sum")).reset_index()
        mape = float(np.mean(np.abs(aj["real"] / aj["ajustado"] - 1)))
    else:
        aj, mape = pd.DataFrame(columns=["competencia", "real", "ajustado"]), None
    return dict(historico=hist[["competencia", "receita"]], projecao=p, crescimento_anual=float(math.exp(tend * 12) - 1),
                sazonalidade={MESES_PT[k]: float(math.exp(saz[k])) for k in range(12)}, sigma=sig, mape=mape, ajuste=aj)


def backtest(meses_teste=6, ids=None):
    ids = un(True, ids)
    cps = [c for c in competencias() if c <= ultima_competencia_fechada()]
    corte = cps[-meses_teste - 1]
    p = projetar_receita(meses_teste, ate=corte, ids=ids)["projecao"]
    real = vendas_mensais(ids).set_index("competencia")["receita"]
    p["real"] = p["competencia"].map(real)
    p["erro_pct"] = p["receita"] / p["real"] - 1
    return p


def bases_projecao(ids=None):
    ids_all = un(False, ids)
    cps = [c for c in competencias() if c <= ultima_competencia_fechada()][-12:]
    t = dre(cps, ids_all)["Total"]
    rec = t["receita_bruta"]
    if rec <= 0:
        return None
    desp = df(f"""SELECT cd.tipo, cd.grupo_dre, SUM(d.valor) valor FROM despesas d
                  JOIN categorias_despesa cd ON cd.id=d.categoria_id
                  WHERE d.unidade_id IN ({ph(ids_all)}) AND d.competencia BETWEEN ? AND ? GROUP BY 1,2""",
              (*ids_all, cps[0], cps[-1]))
    fixas = float(desp[(desp["tipo"] == "FIXA") & (desp["grupo_dre"] != "DEPRECIACAO")]["valor"].sum()) / 12
    variaveis_pct = float(desp[desp["tipo"] == "VARIAVEL"]["valor"].sum()) / rec
    return dict(
        competencias=cps, receita_12m=float(rec), desconto_pct=float(-t["descontos"] / rec),
        impostos_pct=float(param("aliq_icms_efetiva") + param("aliq_pis_cofins_efetiva")),
        outras_receitas_pct=float((t["receitas_franquia"] * (1 - param("aliq_impostos_servicos")) + t["margem_distribuicao"]) / rec),
        cmv_pct=float(-t["cmv"] / rec), perdas_pct=float(-t["perdas"] / rec), consumo_pct=float(-t["consumo_interno"] / rec),
        folha_mes=float(-t["pessoal_folha"] / 12), fixas_mes=fixas, variaveis_pct=variaveis_pct,
        depreciacao_mes=float(-t["depreciacao"] / 12), ir_pct=float(param("aliq_ir_csll")),
        lucro_12m=float(t["lucro_liquido"]),
    )
