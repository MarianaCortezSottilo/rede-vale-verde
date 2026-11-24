"""Cálculo de folha (tabelas simplificadas para fins didáticos)."""
from datetime import date, timedelta

INSS_FAIXAS = {
    2024: [(1412.00, .075), (2666.68, .09), (4000.03, .12), (7786.02, .14)],
    2025: [(1518.00, .075), (2793.88, .09), (4190.83, .12), (8157.41, .14)],
    2026: [(1621.00, .075), (2902.84, .09), (4354.27, .12), (8475.55, .14)],
}


def calc_inss(bruto, ano):
    faixas = INSS_FAIXAS[min(max(ano, 2024), 2026)]
    total, anterior = 0.0, 0.0
    for teto, aliq in faixas:
        if bruto > anterior:
            total += (min(bruto, teto) - anterior) * aliq
        anterior = teto
    return round(total, 2)


def calc_irrf(bruto, inss, ano, mes):
    if ano == 2024 or (ano == 2025 and mes < 5):
        tab = [(2259.20, 0, 0), (2826.65, .075, 169.44), (3751.05, .15, 381.44), (4664.68, .225, 662.77), (1e12, .275, 896.00)]
        simpl = 564.80
    else:
        tab = [(2428.80, 0, 0), (2826.65, .075, 182.16), (3751.05, .15, 394.16), (4664.68, .225, 675.49), (1e12, .275, 908.73)]
        simpl = 607.20
    base = bruto - max(inss, simpl)
    ir = 0.0
    for teto, aliq, ded in tab:
        if base <= teto:
            ir = base * aliq - ded
            break
    ir = max(ir, 0.0)
    if ano >= 2026:
        if bruto <= 5000:
            ir = 0.0
        elif bruto <= 7350:
            ir = max(ir - (978.62 - 0.133145 * bruto), 0.0)
    return round(ir, 2)


def calcular_linha(sal, dias_t, ano, mes, tipo_contrato, usa_vt, he_horas, par, verbas=0.0, multa_fgts=0.0):
    base = round(sal * dias_t / 30, 2)
    he_v = round(he_horas * sal / 220 * 1.5, 2)
    dsr = round(he_v / 6, 2)
    bruto = round(base + he_v + dsr + verbas, 2)
    inss = calc_inss(bruto, ano)
    irrf = calc_irrf(bruto, inss, ano, mes)
    vt_desc = round(min(0.06 * base, par["vale_transporte_custo"] * dias_t / 30), 2) if usa_vt else 0.0
    liq = round(bruto - inss - irrf - vt_desc, 2)
    aliq_fgts = 0.02 if tipo_contrato == "JOVEM_APRENDIZ" else par["encargo_fgts"]
    fgts = round(bruto * aliq_fgts + multa_fgts, 2)
    inss_p = round(bruto * par["encargo_inss_patronal"], 2)
    va = round(par["vale_alimentacao"] * dias_t / 30, 2)
    vt_c = round(par["vale_transporte_custo"] * dias_t / 30, 2) if usa_vt else 0.0
    rem = base + he_v + dsr
    p13 = round(rem / 12, 2)
    pfer = round(rem / 12 * 4 / 3, 2)
    encp = round((p13 + pfer) * (par["encargo_inss_patronal"] + aliq_fgts), 2)
    custo = round(bruto + fgts + inss_p + va + vt_c - vt_desc + p13 + pfer + encp, 2)
    return dict(dias_trabalhados=dias_t, salario_base=base, horas_extras_qtd=he_horas, horas_extras_valor=he_v,
                dsr_horas_extras=dsr, verbas_rescisorias=verbas, salario_bruto=bruto, inss_funcionario=inss,
                irrf=irrf, desconto_vt=vt_desc, salario_liquido=liq, fgts=fgts, inss_patronal=inss_p,
                vale_alimentacao=va, vale_transporte_custo=vt_c, provisao_13=p13, provisao_ferias=pfer,
                encargos_provisoes=encp, custo_total=custo)


def limites_mes(competencia):
    ano, mes = int(competencia[:4]), int(competencia[5:])
    ini = date(ano, mes, 1)
    fim = date(ano + (mes == 12), mes % 12 + 1, 1) - timedelta(days=1)
    return ini, fim
