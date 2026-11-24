"""
Gera o banco da Rede Vale Verde (franquia fictícia): sede + 3 CDs + 10 lojas, nov/2024 a out/2026.

Uso:
    python gerador/gerar_dados.py                       # cria dados/vale_verde.db
    python gerador/gerar_dados.py --seed 7              # outra "realidade" com a mesma lógica
    python gerador/gerar_dados.py --meses-cupons 24     # guarda os cupons dos 24 meses (banco bem maior)

A operação é simulada dia a dia e de forma integrada:
  clientes -> vendas por loja -> estoque da loja -> pedido ao CD (transferência + frete) ou ao fornecedor
  regional (perecíveis) -> estoque do CD -> pedido aos fornecedores nacionais -> contas a pagar
  RH por unidade -> escalas -> folha;  franqueados -> royalties e fundo de marketing -> franqueadora
"""
import argparse
import math
import os
import sqlite3
import sys
import time
from datetime import date, timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalogo as C  # noqa: E402
import rede as RD  # noqa: E402

for _t in (np.int64, np.int32, np.int16, np.int8, np.uint64, np.uint32):
    sqlite3.register_adapter(_t, int)
sqlite3.register_adapter(np.float64, float)
sqlite3.register_adapter(np.float32, float)
sqlite3.register_adapter(np.str_, str)
sqlite3.register_adapter(np.bool_, int)

INICIO = date(2024, 11, 1)
FIM = date(2026, 10, 31)
FIM_ESCALA = date(2026, 11, 30)
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIAS_SEMANA = {"SEG": 0, "TER": 1, "QUA": 2, "QUI": 3, "SEX": 4, "SAB": 5, "DOM": 6}
SALARIO_MINIMO = {2024: 1412.0, 2025: 1518.0, 2026: 1621.0}
DISSIDIOS = [(date(2025, 5, 1), 0.053), (date(2026, 5, 1), 0.050)]
CANAL_DIRETO = {"Laticínios e Frios", "Açougue", "Hortifrúti", "Padaria"}
TIPOS_REGIONAIS = set(RD.REGIONAIS_TIPOS)
MARGEM_EXTRA = 0.03     # rede: preços ligeiramente acima da loja única (compensa custo logístico e royalties)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def comp(d):
    return f"{d.year:04d}-{d.month:02d}"


def idx_mes(d):
    return (d.year - INICIO.year) * 12 + d.month - INICIO.month


def arredonda_preco(v):
    v = math.ceil(v * 10) / 10 - 0.01
    return round(max(v, 0.49), 2)


def arredonda_vec(v):
    return np.round(np.maximum(np.ceil(v * 10 - 1e-9) / 10 - 0.01, 0.49), 2)


def haversine(a, b, c, d):
    r = 6371.0
    p1, p2 = math.radians(a), math.radians(c)
    dp, dl = math.radians(c - a), math.radians(d - b)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def ean13(rng):
    base = "200" + "".join(str(x) for x in rng.integers(0, 10, 9))
    s = sum(int(c) * (3 if i % 2 else 1) for i, c in enumerate(base))
    return base + str((10 - s % 10) % 10)


# INSS/IRRF aproximados (mesmas regras do app)
sys.path.insert(0, RAIZ)
from app.folha import calc_inss, calc_irrf  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=2024)
    ap.add_argument("--db", default=os.path.join(RAIZ, "dados", "vale_verde.db"))
    ap.add_argument("--meses-cupons", type=int, default=6, help="meses finais com cupons individuais gravados")
    ap.add_argument("--meses-itens", type=int, default=2, help="meses finais com itens de cupom gravados")
    args = ap.parse_args()
    args.meses_itens = min(args.meses_itens, args.meses_cupons)
    SEED = args.seed
    rng = np.random.default_rng(SEED)
    t0 = time.time()

    os.makedirs(os.path.dirname(args.db), exist_ok=True)
    if os.path.exists(args.db):
        os.remove(args.db)
    con = sqlite3.connect(args.db)
    con.execute("PRAGMA journal_mode = OFF")
    con.execute("PRAGMA synchronous = OFF")
    with open(os.path.join(RAIZ, "db", "schema.sql"), encoding="utf-8") as f:
        con.executescript(f.read())
    con.execute("PRAGMA foreign_keys = OFF")

    dias = [INICIO + timedelta(days=i) for i in range((FIM - INICIO).days + 1)]
    ND = len(dias)
    dia_idx = {d: i for i, d in enumerate(dias)}
    NM = idx_mes(FIM) + 1
    comps = [comp(date(2024 + (10 + m) // 12, (10 + m) % 12 + 1, 1)) for m in range(NM)]
    mes_do_dia = np.array([idx_mes(d) for d in dias])
    fechado = np.array([d.isoformat() in C.FERIADOS_FECHADO for d in dias])
    feriado_dom = np.array([d.isoformat() in C.FERIADOS_DOMINGO for d in dias])
    domingo = np.array([d.weekday() == 6 for d in dias])
    regime_domingo = (domingo | feriado_dom) & ~fechado
    meses = np.array([d.month for d in dias])
    dds = np.array([d.weekday() for d in dias])
    diam = np.array([d.day for d in dias])
    corte_cupons = comps[max(0, NM - args.meses_cupons)] + "-01"
    corte_itens = comps[max(0, NM - args.meses_itens)] + "-01"

    # =========================================================================
    # 1. Cadastros
    # =========================================================================
    log("Cadastros: franqueadora, cidades, unidades, fornecedores, produtos")
    e = C.EMPRESA
    con.execute("INSERT INTO empresa VALUES (1,?,?,?,?,?,?,?)",
                (e["razao_social"], e["nome_fantasia"], e["cnpj"], e["cidade"], e["uf"], e["regime_tributario"],
                 e["fundacao"]))
    con.executemany("INSERT INTO parametros VALUES (?,?,?)", C.PARAMETROS)
    par = {k: v for k, v, _ in C.PARAMETROS}

    dep_id = {}
    for i, (nome, tipo) in enumerate(C.DEPARTAMENTOS, 1):
        dep_id[nome] = i
        con.execute("INSERT INTO departamentos VALUES (?,?,?)", (i, nome, tipo))
    dep_tipo = dict(C.DEPARTAMENTOS)

    cargo_id, cargo_info = {}, {}
    for tipo_un, lista in (("LOJA", C.CARGOS), ("CD", RD.CARGOS_CD), ("SEDE", RD.CARGOS_SEDE)):
        for (nome, dep, sal, ch, qd, tipo, turn) in lista:
            k = len(cargo_id) + 1
            cargo_id[nome] = k
            cargo_info[k] = dict(nome=nome, dep=dep, sal=sal, ch=ch, q=qd, tipo=tipo, turnover=turn, un=tipo_un,
                                 admin=dep_tipo[dep] == "ADMINISTRATIVO")
            con.execute("INSERT INTO cargos VALUES (?,?,?,?,?,?,?)", (k, nome, dep_id[dep], sal, ch, qd, tipo_un))

    cat_id, cat_info = {}, {}
    for i, (nome, dep, marg, per, rev, perda) in enumerate(C.CATEGORIAS, 1):
        canal = "DIRETO" if nome in CANAL_DIRETO else "CD"
        marg = marg + MARGEM_EXTRA if rev else marg
        cat_id[nome] = i
        cat_info[nome] = dict(dep=dep, margem=marg, perecivel=per, revenda=rev, perda=perda, canal=canal)
        con.execute("INSERT INTO categorias VALUES (?,?,?,?,?,?,?)", (i, nome, dep_id[dep], marg, per, rev, canal))

    cid_id, cid_info = {}, {}
    for i, (nome, uf, reg, lat, lon, popl, renda, conc) in enumerate(RD.CIDADES, 1):
        cid_id[nome] = i
        cid_info[nome] = dict(uf=uf, regiao=reg, lat=lat, lon=lon, pop=popl, renda=renda)
        con.execute("INSERT INTO cidades VALUES (?,?,?,?,?,?,?,?,?)", (i, nome, uf, reg, lat, lon, popl, renda, conc))

    for i, (rs, nf, socio, dc) in enumerate(RD.FRANQUEADOS, 1):
        con.execute("INSERT INTO franqueados VALUES (?,?,?,?,?,?,?,?)",
                    (i, rs, nf, f"{rng.integers(10, 99)}.{rng.integers(100, 999)}.{rng.integers(100, 999)}/0001-"
                                f"{rng.integers(10, 99)} (fictício)", socio,
                     f"({rng.choice([11, 21, 31, 41, 51, 71, 81, 91])}) 9{rng.integers(1000, 9999)}-{rng.integers(1000, 9999)}",
                     dc, par["taxa_franquia"]))

    # --- unidades ------------------------------------------------------------
    unid = []         # dicts
    cod_uid = {}
    for k, (cod, nome, tipo, modelo, fq, cidade, bairro, (dx, dy), area, ck, inaug, cdcod, diasp, fdem, fpre,
            fsal, alu, ener) in enumerate(RD.UNIDADES, 1):
        ci = cid_info[cidade]
        lat = ci["lat"] + dy / 111.0
        lon = ci["lon"] + dx / (111.0 * math.cos(math.radians(ci["lat"])))
        u = dict(id=k, cod=cod, nome=nome, tipo=tipo, modelo=modelo, franq=(fq + 1) if fq is not None else None,
                 cidade=cidade, regiao=ci["regiao"], bairro=bairro, lat=lat, lon=lon, area=area, ck=ck,
                 inaug=date.fromisoformat(inaug), cdcod=cdcod, diasp=diasp, fdem=fdem, fpre=fpre, fsal=fsal,
                 alu=alu, ener=ener)
        unid.append(u)
        cod_uid[cod] = k
    U = {u["id"]: u for u in unid}
    for u in unid:
        if u["tipo"] == "LOJA":
            cd = U[cod_uid[u["cdcod"]]]
            u["cd"] = cd["id"]
            u["km_cd"] = round(haversine(u["lat"], u["lon"], cd["lat"], cd["lon"]) * par["fator_estrada"], 1)
            u["lead_cd"] = 1 + int(u["km_cd"] // 700)
            u["dias_cd"] = {DIAS_SEMANA[x] for x in u["diasp"].split(",")}
        u["i0"] = max(0, (u["inaug"] - INICIO).days)
        con.execute("INSERT INTO unidades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (u["id"], u["cod"], u["nome"], u["tipo"], u["modelo"], u["franq"], cid_id[u["cidade"]],
                     u["bairro"], f"Av. Fictícia, {rng.integers(100, 3000)} — {u['bairro']}", round(u["lat"], 6),
                     round(u["lon"], 6), u["area"], u["ck"], u["inaug"].isoformat(), u.get("cd"), u.get("km_cd"),
                     u.get("lead_cd"), u["diasp"], u["fpre"], "ATIVA"))
    lojas = [u for u in unid if u["tipo"] == "LOJA"]
    cds = [u for u in unid if u["tipo"] == "CD"]
    sede = [u for u in unid if u["tipo"] == "SEDE"][0]
    for n, l in enumerate(lojas):
        l["n"] = n
    NL = len(lojas)

    # --- concorrentes --------------------------------------------------------
    conc = []
    for l in lojas:
        for k in range(int(rng.integers(6, 10))):
            nome, fmt, area = RD.CONCORRENTES_NOMES[int(rng.integers(0, len(RD.CONCORRENTES_NOMES)))]
            dist = float(rng.uniform(0.4, 6.0))
            ang = rng.uniform(0, 2 * math.pi)
            la = l["lat"] + dist * math.sin(ang) / 111.0
            lo = l["lon"] + dist * math.cos(ang) / (111.0 * math.cos(math.radians(l["lat"])))
            conc.append((f"{nome} {l['cidade'].split()[0]} {k + 1}", fmt, cid_id[l["cidade"]], l["id"], round(la, 6),
                         round(lo, 6), int(area * rng.uniform(0.7, 1.3)), round(dist, 2)))
    con.executemany("INSERT INTO concorrentes (nome,formato,cidade_id,loja_referencia_id,lat,lon,area_m2,distancia_km) "
                    "VALUES (?,?,?,?,?,?,?,?)", conc)

    # --- fornecedores --------------------------------------------------------
    forn_id, forn_info = {}, {}

    def novo_forn(chave, rs, nf, abr, reg, cidade, uf, lat, lon, prazo, diasp, minimo, fcusto):
        k = len(forn_id) + 1
        forn_id[chave] = k
        forn_info[k] = dict(nome=nf, prazo=prazo, dias={DIAS_SEMANA[x] for x in diasp.split(",")}, minimo=minimo,
                            lat=lat, lon=lon, fcusto=fcusto, abr=abr)
        cnpj = f"{rng.integers(10, 99)}.{rng.integers(100, 999)}.{rng.integers(100, 999)}/0001-{rng.integers(10, 99)} (fictício)"
        tel = f"({rng.choice([11, 19, 41, 51, 62, 71, 81, 91])}) 3{rng.integers(100, 999)}-{rng.integers(1000, 9999)}"
        con.execute("INSERT INTO fornecedores VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (k, rs, nf, cnpj, abr, reg, cidade, uf, lat, lon, tel, prazo, diasp, minimo, fcusto, chave.split("|")[0]))

    for chave, (rs, nf, cid, uf, prazo, lead, diasp, minimo) in C.FORNECEDORES.items():
        if chave in TIPOS_REGIONAIS - {"FRIOS"}:
            continue
        lat, lon = RD.NACIONAIS_COORD[chave]
        if chave == "FRIOS":
            rs, nf = "Polar Congelados Ltda.", "Polar Congelados"
        novo_forn(chave, rs, nf, "NACIONAL", None, cid, uf, lat, lon, prazo, diasp, minimo * 4, 1.0)
    for reg, (nomes, cid, uf, lat, lon, fc) in RD.REGIONAIS.items():
        for tipo, (padrao, prazo, diasp, minimo) in RD.REGIONAIS_TIPOS.items():
            nf = padrao.format(n=nomes[tipo])
            la, lo = lat + rng.uniform(-0.25, 0.25), lon + rng.uniform(-0.25, 0.25)
            novo_forn(f"{tipo}|{reg}", f"{nf} Ltda.", nf, "REGIONAL", reg, cid, uf, round(la, 4), round(lo, 4), prazo,
                      diasp, minimo, fc)

    # --- produtos ------------------------------------------------------------
    prods = []
    for ci, (cat, itens) in enumerate(C.PRODUTOS.items(), 1):
        seq = 0
        for it in itens:
            if cat == "Uso Interno":
                desc, un, custo, _, _, val, saz, marcas, fk, emb = it
                variantes = [(None, 1.0, 0.0)]
                qm = None
            else:
                desc, un, custo, giro, qm, val, saz, marcas, fk, emb = it
                variantes = [(m, C.MARCA_CUSTO[j], giro * C.MARCA_POP[j]) for j, m in enumerate(C.MARCAS[marcas])] \
                    if marcas else [(None, 1.0, giro)]
            for marca, mc, pop in variantes:
                seq += 1
                c0 = round(custo * mc * rng.uniform(0.97, 1.03), 2)
                marg = cat_info[cat]["margem"] + (0.03 if marca == "Vale Verde" else 0)
                marg = float(np.clip(marg + rng.normal(0, 0.02), 0.12, 0.68)) if cat != "Uso Interno" else 0.0
                canal = cat_info[cat]["canal"]
                if canal == "DIRETO":
                    fid = forn_id[f"{fk}|Sudeste"]
                else:
                    fid = forn_id[fk]
                prods.append(dict(id=len(prods) + 1, sku=f"{ci:02d}{seq:04d}", ean=ean13(rng) if cat != "Uso Interno" else None,
                                  desc=f"{desc} {marca}" if marca else desc, marca=marca, cat=cat, forn=fid, tipo_f=fk,
                                  un=un, emb=float(emb), custo0=c0, margem=marg, validade=val, saz=saz, pop=pop,
                                  qmode=qm, revenda=cat != "Uso Interno", canal=canal))
    for p in prods:
        p["pop"] *= {"Hortifrúti": 2.3, "Padaria": 2.6, "Açougue": 1.1}.get(p["cat"], 1.0)
        if p["desc"].startswith("Ovos Brancos") or p["desc"].startswith("Sardinha"):
            p["saz"] = "QUARESMA"
    NP = len(prods)
    P = pd.DataFrame(prods)
    revenda = P["revenda"].values.astype(bool)
    is_kg = (P["un"] == "KG").values
    canal_cd = (P["canal"] == "CD").values
    cat_arr = P["cat"].values
    emb = P["emb"].values.astype(float)
    pop = P["pop"].values.astype(float)
    log(f"  {NP} produtos, {len(forn_id)} fornecedores, {NL} lojas, {len(cds)} CDs")

    # --- custos e preços de referência ----------------------------------------
    custo_m = np.zeros((NM, NP))
    preco_m = np.full((NM, NP), np.nan)
    for cat in cat_info:
        mu, sig = C.INFLACAO_CATEGORIA[cat]
        dev = 0.0
        idx_cat = np.zeros(NM)
        for m in range(NM):
            dev = 0.65 * dev + rng.normal(0, sig)
            idx_cat[m] = (1 + mu) ** m * math.exp(dev)
        for j in np.where(cat_arr == cat)[0]:
            pdev = 0.0
            for m in range(NM):
                pdev = 0.6 * pdev + rng.normal(0, 0.01 if cat != "Hortifrúti" else 0.05)
                custo_m[m, j] = round(prods[j]["custo0"] * idx_cat[m] * math.exp(pdev), 2)
    for j, p in enumerate(prods):
        if not p["revenda"]:
            continue
        atual = arredonda_preco(custo_m[0, j] / (1 - p["margem"]))
        for m in range(NM):
            alvo = custo_m[m, j] / (1 - p["margem"])
            if abs(alvo - atual) / atual > 0.03 or m % 3 == 0:
                atual = arredonda_preco(alvo)
            preco_m[m, j] = atual
    con.executemany("INSERT INTO historico_precos (produto_id, competencia, custo, preco) VALUES (?,?,?,?)",
                    [(j + 1, comps[m], float(custo_m[m, j]), None if np.isnan(preco_m[m, j]) else float(preco_m[m, j]))
                     for j in range(NP) for m in range(NM)])

    # --- sazonalidade nacional + encarte --------------------------------------
    def fator_tag(tag):
        f = np.ones(ND)
        if tag == "VERAO":
            f = np.select([np.isin(meses, [12, 1, 2, 3]), np.isin(meses, [10, 11]), np.isin(meses, [6, 7, 8])],
                          [1.45, 1.15, 0.70], 0.95)
        elif tag == "INVERNO":
            f = np.select([np.isin(meses, [6, 7, 8]), np.isin(meses, [5, 9]), np.isin(meses, [12, 1, 2])],
                          [1.45, 1.15, 0.75], 0.95)
        elif tag == "NATAL":
            f = np.select([(meses == 12) & (diam <= 24), meses == 12, meses == 11], [2.2, 1.3, 1.15], 1.0)
        elif tag == "FDS":
            f = np.select([dds == 4, dds == 5, dds == 6], [1.3, 1.7, 1.9], 0.8) * np.where(np.isin(meses, [12, 1, 2]), 1.1, 1.0)
        elif tag == "PANETONE":
            f = np.select([(meses == 10) & (diam >= 20), meses == 11, (meses == 12) & (diam <= 24), meses == 12],
                          [0.5, 1.0, 3.0, 0.6], 0.0)
        elif tag in ("PASCOA", "QUARESMA"):
            f = np.zeros(ND) if tag == "PASCOA" else np.ones(ND)
            for _, ds in C.PASCOA.items():
                dp = date.fromisoformat(ds)
                for k in range(1, 40):
                    d = dp - timedelta(days=k)
                    if d in dia_idx:
                        if tag == "PASCOA":
                            f[dia_idx[d]] = 3.5 if k <= 7 else max(0.3, 3.0 * (1 - k / 40))
                        elif k <= 7:
                            f[dia_idx[d]] = 1.5
        return f

    SAZ = np.ones((ND, NP), dtype=np.float32)
    for tag in P["saz"].dropna().unique():
        SAZ[:, P["saz"].values == tag] = fator_tag(tag)[:, None]
    horti = np.where(cat_arr == "Hortifrúti")[0]
    SAZ[np.ix_(dds == 2, horti)] *= 1.5
    col_verao = P["saz"].values == "VERAO"
    col_inverno = P["saz"].values == "INVERNO"

    PROMO = np.zeros((ND, NP), dtype=bool)
    PRECO_PROMO = np.zeros((ND, NP), dtype=np.float32)
    promos = []
    ini = INICIO - timedelta(days=(INICIO.weekday() - 3) % 7)
    while ini <= FIM:
        fim_s = ini + timedelta(days=6)
        i0, i1 = max(0, (ini - INICIO).days), min(ND - 1, (fim_s - INICIO).days)
        w = pop * SAZ[i0:i1 + 1].mean(axis=0) * revenda
        escolhidos = rng.choice(NP, size=18, replace=False, p=w / w.sum())
        m = mes_do_dia[i0]
        for j in escolhidos:
            pn = preco_m[m, j]
            pp = arredonda_preco(max(pn * (1 - rng.uniform(0.08, 0.20)), custo_m[m, j] * 1.03))
            if pp >= pn:
                continue
            PROMO[i0:i1 + 1, j] = True
            PRECO_PROMO[i0:i1 + 1, j] = pp
            promos.append((j + 1, max(ini, INICIO).isoformat(), min(fim_s, FIM).isoformat(), float(pn), float(pp),
                           f"Encarte nacional {ini.strftime('%d/%m/%Y')}"))
        ini += timedelta(days=7)
    con.executemany("INSERT INTO promocoes (produto_id,data_inicio,data_fim,preco_normal,preco_promocional,campanha) "
                    "VALUES (?,?,?,?,?,?)", promos)

    # --- fornecedor regional e custos por loja ---------------------------------
    tipo_f = P["tipo_f"].values
    for l in lojas:
        reg = l["regiao"]
        l["fornec"] = {}            # tipo -> (fid, lead, km)
        for tipo in TIPOS_REGIONAIS:
            fid = forn_id[f"{tipo}|{reg}"]
            fi = forn_info[fid]
            km = haversine(l["lat"], l["lon"], fi["lat"], fi["lon"]) * par["fator_estrada"]
            l["fornec"][tipo] = (fid, 1 + int(km // 450), round(km, 1))
        fc = RD.REGIONAIS[reg][5]
        l["fator_custo_dir"] = fc
        # custo de entrada na loja: CD = referência x (1+markup); direto = referência x fator regional
        l["custo_m"] = np.where(canal_cd[None, :], custo_m * (1 + par["markup_transferencia"]), custo_m * fc)
        l["preco_m"] = np.where(revenda[None, :], arredonda_vec(preco_m * l["fpre"]), np.nan)
        l["promo_preco"] = arredonda_vec(PRECO_PROMO * l["fpre"]).astype(np.float32)
        l["saz_reg"] = {m: v for m, v in RD.SAZONAL_REGIONAL.get(reg, {}).items()}
        l["saz_reg"].update(RD.SAZONAL_REGIONAL.get(l["cidade"], {}))
        l["mult_verao"] = RD.VERAO_REGIONAL[reg]
        l["mult_inverno"] = RD.INVERNO_REGIONAL[reg]
    for c in cds:
        c["fornec"] = {}
        for chave in set(P.loc[canal_cd, "tipo_f"]):
            fid = forn_id[chave]
            fi = forn_info[fid]
            km = haversine(c["lat"], c["lon"], fi["lat"], fi["lon"]) * par["fator_estrada"]
            c["fornec"][chave] = (fid, 1 + int(km // 600), round(km, 1))
        c["lojas"] = [l for l in lojas if l["cd"] == c["id"]]

    # =========================================================================
    # 2. RH: quadro por unidade, rotatividade, salários
    # =========================================================================
    log("RH: quadro de pessoal das 14 unidades")
    funcs, hist_sal = [], []
    usados = set()
    sal_atual = {}
    sal_ref = {}                     # (uid, cargo) -> salário de admissão vigente
    turno_toggle = {}

    def novo_nome(sexo):
        while True:
            pn = rng.choice(C.NOMES_M if sexo == "M" else C.NOMES_F)
            s1, s2 = rng.choice(C.SOBRENOMES, 2, replace=False)
            n = f"{pn} {s1} {s2}"
            if n not in usados:
                usados.add(n)
                return n

    def admitir(u, cid, data_adm, tipo=None, salario=None, fim_contrato=None):
        info = cargo_info[cid]
        sexo = rng.choice(["M", "F"], p=[0.25, 0.75] if "Caixa" in info["nome"] else [0.5, 0.5])
        idade = int(rng.integers(16, 20)) if info["tipo"] == "JOVEM_APRENDIZ" else int(np.clip(rng.normal(33, 9), 18, 62))
        nasc = data_adm - timedelta(days=int(idade * 365.25 + rng.integers(0, 365)))
        if info["admin"]:
            turno = "COMERCIAL"
        else:
            k = turno_toggle.get((u["id"], cid), 0)
            turno = "MANHA" if k % 2 == 0 else "TARDE"
            turno_toggle[(u["id"], cid)] = k + 1
        sal = salario if salario is not None else sal_ref[(u["id"], cid)]
        f = dict(idx=len(funcs), uid=u["id"], nome=novo_nome(sexo),
                 cpf=f"999.{rng.integers(100, 999)}.{rng.integers(100, 999)}-{rng.integers(10, 99)}", nasc=nasc,
                 sexo=sexo, cargo=cid, tipo=tipo or info["tipo"], turno=turno, sal_adm=round(sal, 2), adm=data_adm,
                 dem=None, motivo=None, vt=int(rng.random() < 0.7), fim_contrato=fim_contrato,
                 grupo_dom=int(rng.integers(0, 2)), folga_dia=int(rng.integers(0, 4)))
        funcs.append(f)
        hist_sal.append((f["idx"], data_adm, round(sal, 2), "Admissão"))
        sal_atual[f["idx"]] = round(sal, 2)
        return f

    quadro = {}          # uid -> {cargo: n}
    for u in unid:
        q = {}
        if u["tipo"] == "LOJA":
            for (nome, *_r) in C.CARGOS:
                cid = cargo_id[nome]
                base = cargo_info[cid]["q"]
                q[cid] = base if base == 1 else max(1, int(round(base * u["fdem"])))
        elif u["tipo"] == "CD":
            esc = {"CD01": 1.0, "CD02": 0.6, "CD03": 0.8}[u["cod"]]
            for (nome, *_r) in RD.CARGOS_CD:
                cid = cargo_id[nome]
                base = cargo_info[cid]["q"]
                q[cid] = base if base == 1 else max(1, int(round(base * esc)))
        else:
            for (nome, *_r) in RD.CARGOS_SEDE:
                q[cargo_id[nome]] = cargo_info[cargo_id[nome]]["q"]
        quadro[u["id"]] = q
        for cid in q:
            sal_ref[(u["id"], cid)] = round(cargo_info[cid]["sal"] * u["fsal"], 2)

    for u in unid:
        for cid, n in quadro[u["id"]].items():
            info = cargo_info[cid]
            for _ in range(n):
                if u["inaug"] <= INICIO:
                    max_anos = (INICIO - u["inaug"]).days / 365
                    anos = min(rng.exponential(5 if "Gerente" in info["nome"] or "Diretor" in info["nome"] else 2.3), max_anos)
                    if info["tipo"] == "JOVEM_APRENDIZ":
                        anos = min(rng.uniform(0, 1), max_anos)
                    adm = INICIO - timedelta(days=int(anos * 365) + 15)
                    adm = max(adm, u["inaug"] - timedelta(days=20))
                    s_at = sal_ref[(u["id"], cid)] * (1 + min(anos, 8) * 0.012) * rng.uniform(0.98, 1.04)
                    f = admitir(u, cid, adm, salario=s_at / (1.05 ** min(anos, 10)))
                    hist_sal.append((f["idx"], INICIO, round(s_at, 2), "Saldo em 01/11/2024"))
                    sal_atual[f["idx"]] = round(s_at, 2)
                else:
                    u.setdefault("admissoes_futuras", []).append(cid)

    abertura = {}        # data -> lista de (u, cargo)
    for u in unid:
        for cid in u.get("admissoes_futuras", []):
            d = u["inaug"] - timedelta(days=int(rng.integers(15, 25)))
            abertura.setdefault(d, []).append((u, cid))

    vagas = []
    dt_ = INICIO
    while dt_ <= FIM:
        for u, cid in abertura.get(dt_, []):
            admitir(u, cid, dt_)
        for dd, pct in DISSIDIOS:
            if dt_ == dd:
                for k in sal_ref:
                    sal_ref[k] = round(sal_ref[k] * (1 + pct), 2)
                for f in funcs:
                    if f["dem"] is None and f["adm"] <= dt_:
                        sal_atual[f["idx"]] = round(sal_atual[f["idx"]] * (1 + pct), 2)
                        hist_sal.append((f["idx"], dt_, sal_atual[f["idx"]], f"Dissídio {dt_.year} (+{pct * 100:.1f}%)"))
        if dt_.month == 1 and dt_.day == 2:
            sm = SALARIO_MINIMO[dt_.year]
            for k in sal_ref:
                piso = sm * (0.54 if cargo_info[k[1]]["tipo"] == "JOVEM_APRENDIZ" else 1.0)
                sal_ref[k] = max(sal_ref[k], piso)
            for f in funcs:
                if f["dem"] is None and f["adm"] <= dt_:
                    piso = sm * (0.54 if cargo_info[f["cargo"]]["tipo"] == "JOVEM_APRENDIZ" else 1.0)
                    if sal_atual[f["idx"]] < piso:
                        sal_atual[f["idx"]] = round(piso, 2)
                        hist_sal.append((f["idx"], dt_, round(piso, 2), "Ajuste ao salário mínimo"))
                    elif rng.random() < 0.15 and f["tipo"] == "CLT":
                        sal_atual[f["idx"]] = round(sal_atual[f["idx"]] * 1.04, 2)
                        hist_sal.append((f["idx"], dt_, sal_atual[f["idx"]], "Mérito (+4%)"))
        if dt_.month == 12 and dt_.day == 1:
            for l in lojas:
                if l["inaug"] <= dt_:
                    for cnome, n in (("Operador de Caixa", 2), ("Repositor", 1), ("Empacotador", 1)):
                        for _ in range(n):
                            admitir(l, cargo_id[cnome], dt_, tipo="TEMPORARIO", fim_contrato=date(dt_.year + 1, 1, 10))
        for f in funcs:
            if f["dem"] is not None or f["adm"] > dt_:
                continue
            if f["fim_contrato"] and dt_ >= f["fim_contrato"]:
                f["dem"], f["motivo"] = dt_, "Término de contrato temporário"
                continue
            info = cargo_info[f["cargo"]]
            haz = info["turnover"] / 30
            dias_casa = (dt_ - f["adm"]).days
            if dias_casa < 90:
                haz *= 1.8
            if f["tipo"] == "TEMPORARIO":
                haz = 0.0005
            if U[f["uid"]]["modelo"] == "FRANQUIA":
                haz *= 1.15
            if rng.random() < haz:
                if 44 <= dias_casa <= 45 or 89 <= dias_casa <= 90:
                    mot = "Término de contrato de experiência"
                else:
                    mot = rng.choice(["Pedido de demissão", "Dispensa sem justa causa", "Justa causa"], p=[0.58, 0.38, 0.04])
                f["dem"], f["motivo"] = dt_, mot
                if f["tipo"] != "TEMPORARIO":
                    vagas.append([dt_ + timedelta(days=int(rng.integers(6, 26))), f["uid"], f["cargo"]])
        for v in [v for v in vagas if v[0] == dt_]:
            admitir(U[v[1]], v[2], dt_)
            vagas.remove(v)
        dt_ += timedelta(days=1)

    hist_by_f = {}
    for h in sorted(hist_sal, key=lambda x: (x[0], x[1])):
        hist_by_f.setdefault(h[0], []).append(h)

    def salario_em(fidx, d):
        s = hist_by_f[fidx][0][2]
        for h in hist_by_f[fidx]:
            if h[1] <= d:
                s = h[2]
        return s

    con.executemany("INSERT INTO funcionarios VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [(f["idx"] + 1, f"VV{f['idx'] + 1:05d}", f["nome"], f["cpf"], f["nasc"].isoformat(), f["sexo"],
                      f["uid"], f["cargo"], f["tipo"], f["turno"], f["sal_adm"], f["adm"].isoformat(),
                      f["dem"].isoformat() if f["dem"] else None, f["motivo"], f["vt"]) for f in funcs])
    con.executemany("INSERT INTO historico_salarial (funcionario_id,data_inicio,salario,motivo) VALUES (?,?,?,?)",
                    [(h[0] + 1, h[1].isoformat(), h[2], h[3]) for h in sorted(hist_sal, key=lambda x: (x[0], x[1]))])
    log(f"  {len(funcs)} funcionários no período ({sum(1 for f in funcs if f['dem'] is None)} ativos em {FIM})")

    # --- escalas -------------------------------------------------------------
    log("Escalas de trabalho")
    escalas = []
    ops_dia = {}     # (uid, data) -> {"M": [...], "T": [...]}
    cx_cid = cargo_id["Operador de Caixa"]
    for f in funcs:
        ini_f = max(f["adm"], INICIO)
        fim_f = (f["dem"] - timedelta(days=1)) if f["dem"] else FIM_ESCALA
        if fim_f < ini_f:
            continue
        ferias = set()
        k = 1
        while True:
            aquis = f["adm"] + timedelta(days=365 * k)
            if aquis > fim_f:
                break
            for _ in range(10):
                ini_fer = aquis + timedelta(days=int(rng.integers(0, 300)))
                ini_fer -= timedelta(days=ini_fer.weekday())
                if ini_fer.month != 12 and not (ini_fer.month == 11 and ini_fer.day > 20):
                    break
            for x in range(30):
                ferias.add(ini_fer + timedelta(days=x))
            k += 1
        unid_tipo = U[f["uid"]]["tipo"]
        d = ini_f
        while d <= fim_f:
            ds = d.isoformat()
            wd = d.weekday()
            semana = (d - date(2024, 10, 28)).days // 7
            closed = ds in C.FERIADOS_FECHADO
            reg_dom = (wd == 6 or ds in C.FERIADOS_DOMINGO) and not closed
            if d in ferias:
                tipo, hi, hf = "FERIAS", None, None
            elif closed:
                tipo, hi, hf = "FOLGA", None, None
            elif f["turno"] == "COMERCIAL" or unid_tipo != "LOJA":
                if wd >= 5 or reg_dom:
                    tipo, hi, hf = "FOLGA", None, None
                elif f["tipo"] == "JOVEM_APRENDIZ":
                    tipo, hi, hf = "TRABALHO", "08:00", "12:00"
                elif unid_tipo == "CD" and f["turno"] == "TARDE":
                    tipo, hi, hf = "TRABALHO", "14:00", "22:48"
                elif unid_tipo == "CD":
                    tipo, hi, hf = "TRABALHO", "05:00", "13:48"
                else:
                    tipo, hi, hf = "TRABALHO", "08:00", "17:48"
            else:
                trabalha_dom = (semana + f["grupo_dom"]) % 2 == 0
                if reg_dom:
                    ok = trabalha_dom if wd == 6 else (d.toordinal() + f["grupo_dom"]) % 2 == 0
                    tipo, hi, hf = ("TRABALHO", "08:00", "13:00") if ok else ("FOLGA", None, None)
                elif trabalha_dom and wd == f["folga_dia"]:
                    tipo, hi, hf = "FOLGA", None, None
                else:
                    tipo = "TRABALHO"
                    hi, hf = ("07:00", "15:20") if f["turno"] == "MANHA" else ("13:40", "22:00")
            if tipo == "TRABALHO" and d <= FIM:
                r = rng.random()
                if r < 0.008:
                    tipo, hi, hf = "ATESTADO", None, None
                elif r < 0.011:
                    tipo, hi, hf = "FALTA", None, None
            escalas.append((f["idx"] + 1, ds, tipo, hi, hf))
            if tipo == "TRABALHO" and f["cargo"] == cx_cid and d <= FIM:
                ops_dia.setdefault((f["uid"], d), {"M": [], "T": []})["M" if hi in ("07:00", "08:00") else "T"].append(f["idx"] + 1)
            d += timedelta(days=1)
    con.executemany("INSERT INTO escalas (funcionario_id,data,tipo,hora_inicio,hora_fim) VALUES (?,?,?,?,?)", escalas)
    log(f"  {len(escalas):,} linhas de escala")
    del escalas

    # =========================================================================
    # 3. Demanda das lojas (reprodutível por loja)
    # =========================================================================
    fator_mes = {1: .94, 2: .92, 3: .98, 4: .99, 5: 1.0, 6: .98, 7: 1.0, 8: .99, 9: .97, 10: 1.0, 11: 1.02, 12: 1.17}
    fator_dds = {0: .86, 1: .88, 2: .97, 3: .93, 4: 1.12, 5: 1.38, 6: .60}
    horas_sem = np.arange(7, 22)
    p_h_sem = np.array([.03, .05, .07, .09, .10, .08, .06, .05, .05, .06, .09, .11, .09, .05, .02])
    p_h_sem /= p_h_sem.sum()
    horas_dom = np.arange(8, 13)
    p_h_dom = np.array([.15, .25, .25, .22, .13])
    qmode = [p["qmode"] for p in prods]
    modos = {}
    for j, q in enumerate(qmode):
        if q is not None:
            modos.setdefault(q, []).append(j)
    modo_mask = {q: np.isin(np.arange(NP), js) for q, js in modos.items()}
    kg_media = np.array([float(q[1:]) if q and q.startswith("k") else 0.0 for q in qmode])
    B0 = 600.0

    for l in lojas:      # elasticidade das ofertas por loja
        r_e = np.random.default_rng(SEED * 7919 + l["n"])
        l["elast"] = np.where(PROMO, r_e.uniform(1.6, 2.3, size=(ND, NP)), 1.0).astype(np.float32)

    def gerar_demanda(l):
        """Mesma semente => mesmos cupons. Retorna arrays de cupons e itens."""
        r = np.random.default_rng(SEED * 1000 + l["n"] + 1)
        cup_dia, cup_seg, cup_ni, it_prod, it_qtd = [], [], [], [], []
        mult = np.ones(NP, dtype=np.float32)
        for i, d in enumerate(dias):
            if i < l["i0"] or fechado[i]:
                continue
            mu = B0 * l["fdem"] * (1.035 ** (i / 365)) * fator_mes[d.month] * l["saz_reg"].get(d.month, 1.0) \
                * fator_dds[d.weekday()]
            if feriado_dom[i]:
                mu = B0 * l["fdem"] * 0.62
            if d.day <= 10:
                mu *= 1.10 if not 5 <= d.day <= 8 else 1.16
            elif d.day >= 24:
                mu *= 0.93
            mu *= C.DATAS_PICO.get(d.isoformat(), 1.0)
            if l["i0"] > 0:                         # loja nova: curva de maturação
                t = i - l["i0"]
                mu *= (0.55 + 0.45 * (1 - math.exp(-t / 120))) * (1.8 if t == 0 else 1.3 if t < 7 else 1.0)
            mu *= r.lognormal(0, 0.06)
            n = r.poisson(mu)
            lam = r.gamma(1.25, 5.2 / 1.25, size=n) * (1.12 if d.weekday() == 5 else 1.0)
            ni = 1 + r.poisson(lam)
            hrs = r.choice(horas_dom, size=n, p=p_h_dom) if regime_domingo[i] else r.choice(horas_sem, size=n, p=p_h_sem)
            segs = hrs * 3600 + r.integers(0, 3600, size=n)
            mult[:] = 1.0
            mult[col_verao] = l["mult_verao"] if meses[i] in (12, 1, 2, 3) else 1.0
            mult[col_inverno] = l["mult_inverno"] if meses[i] in (5, 6, 7, 8, 9) else 1.0
            w = pop * SAZ[i] * l["elast"][i] * mult
            w[~revenda] = 0
            tot = int(ni.sum())
            prod = r.choice(NP, size=tot, p=w / w.sum())
            qtd = np.ones(tot, dtype=np.float32)
            for q, msk_all in modo_mask.items():
                msk = msk_all[prod]
                k = int(msk.sum())
                if not k or q.startswith("k"):
                    continue
                if q == "u":
                    qtd[msk] = r.choice([1, 2, 3], size=k, p=[.85, .12, .03])
                elif q == "m":
                    qtd[msk] = r.choice([1, 2, 3, 4, 6], size=k, p=[.5, .25, .1, .08, .07])
                elif q == "c":
                    qtd[msk] = r.choice([1, 2, 3, 4, 6, 12], size=k, p=[.15, .15, .08, .12, .25, .25])
                elif q == "l":
                    qtd[msk] = r.choice([1, 2, 3, 6, 12], size=k, p=[.25, .3, .1, .2, .15])
            km = is_kg[prod]
            if km.any():
                qtd[km] = np.maximum(np.round(kg_media[prod[km]] * r.lognormal(-0.1, 0.45, size=int(km.sum())), 3), 0.05)
            cup_dia.append(np.full(n, i, dtype=np.int16))
            cup_seg.append(segs.astype(np.int32))
            cup_ni.append(ni.astype(np.int32))
            it_prod.append(prod.astype(np.int16))
            it_qtd.append(qtd)
        cup_dia = np.concatenate(cup_dia)
        cup_ni = np.concatenate(cup_ni)
        it_cup = np.repeat(np.arange(len(cup_dia), dtype=np.int32), cup_ni)
        it_prod = np.concatenate(it_prod)
        it_qtd = np.concatenate(it_qtd)
        cup_seg = np.concatenate(cup_seg)
        it_dia = cup_dia[it_cup]
        ordem = np.lexsort((cup_seg[it_cup], it_prod, it_dia))
        return dict(cup_dia=cup_dia, cup_seg=cup_seg, it_cup=it_cup, it_prod=it_prod, it_qtd=it_qtd, it_dia=it_dia,
                    ordem=ordem)

    log("Demanda dos clientes por loja (fase 1)")
    for l in lojas:
        dmd = gerar_demanda(l)
        it_dia, it_prod, it_qtd = dmd["it_dia"], dmd["it_prod"], dmd["it_qtd"]
        DEM = np.zeros((ND, NP), dtype=np.float64)
        np.add.at(DEM, (it_dia.astype(np.int64), it_prod.astype(np.int64)), it_qtd)
        ordem = dmd["ordem"]
        chave = it_dia[ordem].astype(np.int64) * NP + it_prod[ordem]
        l["qtd_ord"] = it_qtd[ordem]
        l["starts"] = np.searchsorted(chave, np.arange(ND * NP + 1, dtype=np.int64)).astype(np.int64)
        l["DEM"] = DEM
        l["ncup"] = np.bincount(dmd["cup_dia"].astype(np.int64), minlength=ND).astype(float)
        cat_it = cat_arr[it_prod]
        l["n_acoug"] = np.bincount(it_dia[cat_it == "Açougue"].astype(np.int64), minlength=ND).astype(float)
        l["n_horti"] = np.bincount(it_dia[cat_it == "Hortifrúti"].astype(np.int64), minlength=ND).astype(float)
        l["n_pao"] = np.bincount(it_dia[cat_it == "Padaria"].astype(np.int64), minlength=ND).astype(float)
        l["n_kg"] = np.bincount(it_dia[is_kg[it_prod]].astype(np.int64), minlength=ND).astype(float)
        l["trim"] = {}
        log(f"  {l['cod']} {l['cidade']}: {len(dmd['cup_dia']):,} cupons, {len(it_qtd):,} itens")
        del dmd

    # --- consumo interno por loja ---------------------------------------------
    pid_desc = {p["desc"]: j for j, p in enumerate(prods)}
    for l in lojas:
        CONS = np.zeros((ND, NP))
        info = {}
        aberto = ((~fechado) & (np.arange(ND) >= l["i0"])).astype(float)
        r = np.random.default_rng(SEED * 31 + l["n"])

        def regra(desc, serie, motivo, dep):
            j = pid_desc[desc]
            CONS[:, j] = serie
            info[j] = (motivo, dep)
        regra("Sacola Plástica Reciclada (pct 1000un)", l["ncup"] * 2.3 / 1000, "Sacolas para clientes", "Frente de Caixa")
        regra("Bobina Térmica PDV 80mm (cx 30 rolos)", l["ncup"] / (30 * 380), "Bobinas dos PDVs", "Frente de Caixa")
        regra("Bandeja de Isopor (pct 400un)", (l["n_acoug"] * 0.7 + l["n_horti"] * 0.15) / 400, "Embalagem de fracionados", "Açougue")
        regra("Filme PVC 28cm x 300m", (l["n_acoug"] * 0.7 + l["n_horti"] * 0.15) / 1100, "Embalagem de fracionados", "Açougue")
        regra("Saco para Pão Kraft (pct 1000un)", l["n_pao"] * 1.1 / 1000, "Embalagem da padaria", "Padaria")
        regra("Etiqueta para Balança (cx 12 rolos)", l["n_kg"] / 12000, "Etiquetas de balança", "Hortifrúti")
        regra("Detergente Profissional 5L", aberto * 0.13, "Limpeza da loja", "Limpeza")
        regra("Desinfetante Profissional 5L", aberto * 0.12, "Limpeza da loja", "Limpeza")
        regra("Papel Toalha Interfolha (cx 1000 fls)", aberto * 0.28, "Banheiros e copa", "Limpeza")
        regra("Luva Descartável (cx 100un)", aberto * 0.35, "EPI manipulação de alimentos", "Açougue")
        for desc, taxa, mot, dep in [
            ("Café Torrado e Moído 500g Bom Grão", 0.85, "Copa/refeitório", "Administrativo/Financeiro"),
            ("Açúcar Refinado 1kg Vale Verde", 0.55, "Copa/refeitório", "Administrativo/Financeiro"),
            ("Leite UHT Integral 1L Vale Verde", 1.4, "Copa/refeitório", "Administrativo/Financeiro"),
            ("Pão Francês", 1.1, "Lanche dos funcionários", "Administrativo/Financeiro"),
            ("Papel Higiênico 12 Rolos Vale Verde", 0.3, "Banheiros", "Limpeza"),
            ("Saco de Lixo 50L 10un", 0.7, "Limpeza da loja", "Limpeza"),
            ("Detergente Líquido 500ml Vale Verde", 0.35, "Copa/refeitório", "Limpeza"),
            ("Copo Descartável 200ml 100un", 0.45, "Copa/bebedouros", "Administrativo/Financeiro"),
        ]:
            regra(desc, aberto * taxa * l["fdem"] * r.uniform(0.7, 1.3, ND), mot, dep)
        for j in info:
            if not is_kg[j]:
                acum = np.floor(np.cumsum(CONS[:, j]) + 1e-9)
                CONS[:, j] = np.diff(np.concatenate([[0], acum]))
            else:
                CONS[:, j] = np.round(CONS[:, j], 3)
        for i in np.where((dds == 5) & ~fechado & (np.arange(ND) >= l["i0"]))[0]:
            cand = np.where(PROMO[i] & revenda & ~is_kg)[0]
            for j in r.choice(cand, size=min(2, len(cand)), replace=False):
                CONS[i, j] += float(r.integers(2, 5))
        l["CONS"] = CONS
        l["cons_info"] = info
        l["DTOT"] = l["DEM"] + CONS
        l["cum"] = np.vstack([np.zeros(NP), np.cumsum(l["DTOT"], axis=0)])

    # =========================================================================
    # 4. Simulação integrada: lojas + CDs
    # =========================================================================
    log("Simulando estoques, transferências, compras, perdas e rupturas (rede)")
    taxa_perda = np.array([cat_info[p["cat"]]["perda"] for p in prods])

    def _seg(v):
        v = v or 999
        return 0.6 if v <= 7 else 1.5 if v <= 30 else 6.0 if v <= 120 else 14.0
    seg_dias = np.array([_seg(p["validade"]) for p in prods])
    sazonal_plan = np.array([p["saz"] in ("PANETONE", "PASCOA") for p in prods])
    desc_cd = par["desconto_compra_cd"]
    markup = par["markup_transferencia"]

    movs, rupt = [], []
    pedidos, itens_c = [], []
    transfs, itens_t = [], []
    acum_sem = {}         # (uid, j, tipo, motivo, dep) -> [qtd, valor]

    def flush_semana(ds):
        for (uid, j, tipo, mot, dep), (q, v) in acum_sem.items():
            if q:
                movs.append((uid, ds, j + 1, tipo, -round(q, 3), round(v / q, 4), mot, dep, None))
        acum_sem.clear()

    def acumula(uid, j, tipo, mot, dep, q, cu):
        k = (uid, j, tipo, mot, dep)
        a = acum_sem.setdefault(k, [0.0, 0.0])
        a[0] += q
        a[1] += q * cu

    def prox_dia_util(k):
        while k < ND and (dias[k].weekday() == 6 or fechado[k]):
            k += 1
        return k

    def prox_pedido(dias_set, i):
        for k in range(1, 8):
            if i + k >= ND or dias[i + k].weekday() in dias_set:
                return k
        return 7

    # estado das lojas
    for l in lojas:
        l["est"] = np.zeros(NP)
        l["em_ped"] = np.zeros(NP)
        l["VEND"] = np.zeros((ND, NP))
        l["cheg"] = {}
        l["trans_req"] = []
        l["prods_tipo"] = {t: np.where((tipo_f == t) & ~canal_cd)[0] for t in TIPOS_REGIONAIS}
        l["prods_cd"] = np.where(canal_cd)[0]
    for c in cds:
        c["est"] = np.zeros(NP)
        c["em_ped"] = np.zeros(NP)
        c["ENV"] = np.zeros((ND, NP))
        c["cheg"] = {}
        c["prods_forn"] = {}
        for chave in c["fornec"]:
            c["prods_forn"][chave] = np.where(canal_cd & (tipo_f == chave))[0]
        # demanda esperada das lojas atendidas (para previsão e estoque inicial)
        c["DTOT"] = sum(l["DTOT"] for l in c["lojas"]) if c["lojas"] else np.zeros((ND, NP))
        c["cum"] = np.vstack([np.zeros(NP), np.cumsum(c["DTOT"], axis=0)])
        f0 = c["DTOT"][:60].mean(axis=0)
        alvo = f0 * (6 + 10) * canal_cd
        c["est"] = np.ceil(alvo * rng.uniform(0.8, 1.1, NP))
        for j in np.nonzero(c["est"])[0]:
            movs.append((c["id"], INICIO.isoformat(), j + 1, "SALDO_INICIAL", float(c["est"][j]),
                         round(float(custo_m[0, j] * (1 - desc_cd)), 4), "Saldo de abertura do sistema", None, None))

    def abrir_loja(l, i):
        a, b = i + 1, min(i + 29, ND)
        f0 = (l["cum"][b] - l["cum"][a]) / max(1, b - a)
        alvo = f0 * (3 + 3 + seg_dias)
        q = np.where(is_kg, np.round(alvo * rng.uniform(0.7, 1.0, NP), 3), np.ceil(alvo * rng.uniform(0.7, 1.0, NP)))
        l["est"] = q
        m = mes_do_dia[i]
        mot = "Saldo de abertura do sistema" if i == 0 else "Estoque de inauguração"
        for j in np.nonzero(q)[0]:
            movs.append((l["id"], dias[i].isoformat(), j + 1, "SALDO_INICIAL", float(q[j]), float(l["custo_m"][m, j]),
                         mot, None, None))

    comprador_loja = {}
    comprador_cd = None
    for f in funcs:
        nome_c = cargo_info[f["cargo"]]["nome"]
        if nome_c == "Comprador" and f["uid"] not in comprador_loja:
            comprador_loja[f["uid"]] = f["idx"] + 1
        if nome_c == "Comprador Corporativo" and comprador_cd is None:
            comprador_cd = f["idx"] + 1

    def criar_pedido(uid, fid, i, js, qtds, km, lead, custos, comprador):
        k = prox_dia_util(i + lead)
        pid = len(pedidos) + 1
        recebido = k < ND
        total, parcial = 0.0, False
        destino = U[uid]
        for j, q, cu in zip(js, qtds, custos):
            qrec = q
            if rng.random() < 0.015:
                qrec = math.floor(q * rng.uniform(0.0, 0.85) / emb[j]) * emb[j]
                parcial = True
            destino["em_ped"][j] += q
            itens_c.append((pid, j + 1, q, qrec if recebido else None, cu, round((qrec if recebido else q) * cu, 2)))
            total += (qrec if recebido else q) * cu
            if recebido:
                destino["cheg"].setdefault(k, []).append(("C", pid, j, q, qrec, cu))
        prev = dias[k] if k < ND else dias[i] + timedelta(days=lead)
        pedidos.append(dict(id=pid, uid=uid, forn=fid, data=dias[i], prev=prev, receb=dias[k] if recebido else None,
                            status=("RECEBIDO_PARCIAL" if parcial else "RECEBIDO") if recebido else "ABERTO",
                            total=round(total, 2), comprador=comprador, km=km))

    for i, d in enumerate(dias):
        m = mes_do_dia[i]
        ds = d.isoformat()
        # (a) recebimentos nos CDs
        for c in cds:
            for (kind, ref, j, q, qrec, cu) in c["cheg"].pop(i, []):
                c["em_ped"][j] -= q
                if qrec > 0:
                    c["est"][j] += qrec
                    movs.append((c["id"], ds, j + 1, "ENTRADA_COMPRA", float(qrec), float(cu), "Recebimento de mercadoria",
                                 dep_id["Logística (CD)"], f"PC-{ref:06d}"))
        for l in lojas:
            if i < l["i0"]:
                continue
            if i == l["i0"]:
                abrir_loja(l, i)
            for (kind, ref, j, q, qrec, cu) in l["cheg"].pop(i, []):
                l["em_ped"][j] -= q
                if qrec > 0:
                    l["est"][j] += qrec
                    if kind == "C":
                        movs.append((l["id"], ds, j + 1, "ENTRADA_COMPRA", float(qrec), float(cu),
                                     "Recebimento de mercadoria", dep_id["Recebimento/Depósito"], f"PC-{ref:06d}"))
            if fechado[i]:
                continue
            est = l["est"]
            # (b) vendas
            dem = l["DEM"][i]
            vend = dem.copy()
            for j in np.where(dem > est + 1e-9)[0]:
                s, e_ = l["starts"][i * NP + j], l["starts"][i * NP + j + 1]
                cs = np.cumsum(l["qtd_ord"][s:e_], dtype=np.float64)
                k = int(np.searchsorted(cs, est[j] + 1e-9, side="right"))
                l["trim"][(i, j)] = k
                vend[j] = float(cs[k - 1]) if k else 0.0
                perdido = dem[j] - vend[j]
                if perdido > 0:
                    pr = l["promo_preco"][i, j] if PROMO[i, j] else l["preco_m"][m, j]
                    rupt.append((l["id"], ds, j + 1, round(float(perdido), 3), round(float(perdido * pr), 2)))
            est -= vend
            l["VEND"][i] = vend
            # (c) consumo interno
            cons = np.minimum(l["CONS"][i], np.maximum(est, 0))
            for j in np.nonzero(cons > 0)[0]:
                mot, dep = l["cons_info"].get(j, ("Degustação/ação promocional", "Mercearia/Reposição"))
                acumula(l["id"], j, "CONSUMO_INTERNO", mot, dep_id[dep], float(cons[j]), float(l["custo_m"][m, j]))
            est -= cons
            # (d) perdas
            base = np.maximum(est, 0)
            perda = np.zeros(NP)
            un = ~is_kg & (taxa_perda > 0)
            perda[un] = rng.binomial(base[un].astype(np.int64), np.clip(taxa_perda[un] * rng.uniform(0.5, 1.5, un.sum()), 0, 1))
            kg = is_kg & (taxa_perda > 0)
            perda[kg] = np.round(base[kg] * taxa_perda[kg] * rng.uniform(0.5, 1.5, kg.sum()), 3)
            for j in np.nonzero(perda > 0)[0]:
                cat = cat_arr[j]
                if cat_info[cat]["perecivel"]:
                    mot = "Vencimento/deterioração"
                else:
                    mot = ("Avaria", "Furto/desvio", "Vencimento")[int(rng.choice(3, p=[.5, .3, .2]))]
                acumula(l["id"], j, "PERDA", mot, dep_id[cat_info[cat]["dep"]], float(perda[j]), float(l["custo_m"][m, j]))
            est -= perda
            # (e) inventário rotativo
            if i + 1 >= ND or dias[i + 1].month != d.month:
                for j in np.where(revenda)[0]:
                    if rng.random() < (0.05 if is_kg[j] else 0.12) and est[j] > 0:
                        if is_kg[j]:
                            delta = round(-est[j] * rng.uniform(0.01, 0.06), 3)
                        else:
                            delta = float(-rng.choice([1, 1, 1, 2, 2, 3]) if rng.random() < .75 else 1)
                            delta = max(delta, -est[j])
                        if delta:
                            est[j] += delta
                            movs.append((l["id"], ds, j + 1, "AJUSTE_INVENTARIO", float(delta), float(l["custo_m"][m, j]),
                                         "Inventário rotativo", None, None))
            # (f) pedidos aos fornecedores regionais (perecíveis)
            for tipo, js in l["prods_tipo"].items():
                if not len(js):
                    continue
                fid, L, km = l["fornec"][tipo]
                dset = forn_info[fid]["dias"]
                if d.weekday() not in dset and not (i > 0 and fechado[i - 1] and dias[i - 1].weekday() in dset):
                    continue
                R = prox_pedido(dset, i)
                t = i - l["i0"]
                hist = (l["VEND"][max(l["i0"], i - 27):i + 1, js].mean(axis=0) + l["CONS"][max(l["i0"], i - 27):i + 1, js].mean(axis=0)) \
                    if t >= 27 else l["DTOT"][i:i + 28, js].mean(axis=0)
                a_, b_ = i + 1, min(i + 15, ND)
                fut = (l["cum"][b_, js] - l["cum"][a_, js]) / max(1, b_ - a_) * rng.uniform(0.92, 1.08, len(js))
                f = np.where(sazonal_plan[js], fut, 0.5 * hist + 0.5 * fut)
                a_, b_ = i + 1, min(i + 1 + L + R, ND)
                soma_fut = (l["cum"][b_, js] - l["cum"][a_, js]) if b_ > a_ else f * (L + R)
                S = np.maximum(f * (L + R + seg_dias[js]), soma_fut * rng.uniform(0.95, 1.08, len(js)) + f * seg_dias[js])
                nec = S - (est[js] + l["em_ped"][js])
                ped = nec > 0.25 * emb[js]
                if not ped.any():
                    continue
                jj = js[ped]
                qs = [round(math.ceil(q / emb[j] - 1e-9) * emb[j], 3) for j, q in zip(jj, nec[ped])]
                cus = [round(float(custo_m[m, j] * l["fator_custo_dir"] * rng.normal(1, 0.01)), 2) for j in jj]
                criar_pedido(l["id"], fid, i, jj, qs, km, L, cus, comprador_loja.get(l["id"]))
            # (g) reposição pelo CD
            if d.weekday() in l["dias_cd"] or (i > 0 and fechado[i - 1] and dias[i - 1].weekday() in l["dias_cd"]):
                js = l["prods_cd"]
                L = l["lead_cd"]
                R = prox_pedido(l["dias_cd"], i)
                t = i - l["i0"]
                hist = (l["VEND"][max(l["i0"], i - 27):i + 1, js].mean(axis=0) + l["CONS"][max(l["i0"], i - 27):i + 1, js].mean(axis=0)) \
                    if t >= 27 else l["DTOT"][i:i + 28, js].mean(axis=0)
                a_, b_ = i + 1, min(i + 15, ND)
                fut = (l["cum"][b_, js] - l["cum"][a_, js]) / max(1, b_ - a_) * rng.uniform(0.92, 1.08, len(js))
                f = np.where(sazonal_plan[js], fut, 0.5 * hist + 0.5 * fut)
                a_, b_ = i + 1, min(i + 1 + L + R, ND)
                soma_fut = (l["cum"][b_, js] - l["cum"][a_, js]) if b_ > a_ else f * (L + R)
                S = np.maximum(f * (L + R + seg_dias[js]), soma_fut * rng.uniform(0.95, 1.08, len(js)) + f * seg_dias[js])
                nec = S - (est[js] + l["em_ped"][js])
                ped = nec > 0.25 * emb[js]
                if ped.any():
                    jj = js[ped]
                    qs = np.array([math.ceil(q / emb[j] - 1e-9) * emb[j] for j, q in zip(jj, nec[ped])])
                    U[l["cd"]].setdefault("req", []).append((l, jj, qs))
        # (h) CDs atendem as lojas
        for c in cds:
            reqs = c.pop("req", [])
            if not reqs:
                continue
            total_req = np.zeros(NP)
            for (_, jj, qs) in reqs:
                total_req[jj] += qs
            ratio = np.where(total_req > 0, np.minimum(1.0, c["est"] / np.maximum(total_req, 1e-9)), 1.0)
            for (l, jj, qs) in reqs:
                env = np.floor(qs * ratio[jj] + 1e-9)
                env = np.minimum(env, np.maximum(c["est"][jj], 0))
                c["est"][jj] -= env
                c["ENV"][i, jj] += env
                k = prox_dia_util(i + l["lead_cd"])
                tid = len(transfs) + 1
                v_cd = v_tr = 0.0
                for j, q, qe in zip(jj, qs, env):
                    cu_cd = round(float(custo_m[m, j] * (1 - desc_cd)), 4)
                    pt = round(float(custo_m[m, j] * (1 + markup)), 4)
                    itens_t.append((tid, j + 1, float(q), float(qe), cu_cd, pt))
                    v_cd += qe * cu_cd
                    v_tr += qe * pt
                    l["em_ped"][j] += q
                    if k < ND:
                        l["cheg"].setdefault(k, []).append(("T", tid, j, q, qe, pt))
                viagens = max(1, math.ceil(v_tr / par["valor_por_viagem"]))
                frete = viagens * (par["frete_fixo_viagem"] + par["frete_por_km"] * l["km_cd"])
                parcial = bool((env < qs - 1e-9).any())
                transfs.append(dict(id=tid, cd=c["id"], loja=l["id"], data=dias[i], receb=dias[k] if k < ND else None,
                                    status=("RECEBIDA_PARCIAL" if parcial else "RECEBIDA") if k < ND else "EM_TRANSITO",
                                    v_cd=round(v_cd, 2), v_tr=round(v_tr, 2), km=l["km_cd"], viagens=viagens,
                                    frete=round(frete, 2)))
        # (i) CDs compram dos fornecedores nacionais
        for c in cds:
            if fechado[i]:
                continue
            for chave, js in c["prods_forn"].items():
                if not len(js):
                    continue
                fid, L, km = c["fornec"][chave]
                dset = forn_info[fid]["dias"]
                if d.weekday() not in dset and not (i > 0 and fechado[i - 1] and dias[i - 1].weekday() in dset):
                    continue
                R = prox_pedido(dset, i)
                hist = c["ENV"][max(0, i - 27):i + 1, js].mean(axis=0) if i >= 27 else c["DTOT"][:28, js].mean(axis=0)
                a_, b_ = i + 1, min(i + 1 + L + R + 7, ND)
                fut = (c["cum"][b_, js] - c["cum"][a_, js]) / max(1, b_ - a_)
                f = np.where(sazonal_plan[js], fut, 0.4 * hist + 0.6 * fut)
                S = f * (L + R + 7 + 4)
                nec = S - (c["est"][js] + c["em_ped"][js])
                ped = nec > 2 * emb[js]
                if not ped.any():
                    continue
                jj = js[ped]
                qs = [math.ceil(q / (emb[j] * 2) - 1e-9) * emb[j] * 2 for j, q in zip(jj, nec[ped])]
                cus = [round(float(custo_m[m, j] * (1 - desc_cd) * rng.normal(1, 0.008)), 2) for j in jj]
                criar_pedido(c["id"], fid, i, jj, qs, km, L, cus, comprador_cd)
        if d.weekday() == 5 or i == ND - 1:
            flush_semana(ds)
    log(f"  {len(pedidos):,} pedidos a fornecedores, {len(transfs):,} transferências CD→loja, {len(rupt):,} rupturas")

    # =========================================================================
    # 5. Cupons, itens, clientes (fase 2: regenera a demanda e aplica os cortes)
    # =========================================================================
    log("Consolidando cupons, itens e clientes por loja")
    proximo_id = 1
    cli_id0 = 1
    rc_rows = []
    for l in lojas:
        r = np.random.default_rng(SEED * 97 + l["n"])
        dmd = gerar_demanda(l)
        NI = len(dmd["it_qtd"])
        manter = np.ones(NI, dtype=bool)
        ordem = dmd["ordem"]
        for (i, j), k in l["trim"].items():
            s, e_ = l["starts"][i * NP + j], l["starts"][i * NP + j + 1]
            manter[ordem[s + k:e_]] = False
        it_cup = dmd["it_cup"][manter]
        it_prod = dmd["it_prod"][manter].astype(np.int64)
        it_qtd = dmd["it_qtd"][manter].astype(np.float64)
        it_dia = dmd["it_dia"][manter].astype(np.int64)
        ncup_total = len(dmd["cup_dia"])
        nitens = np.bincount(it_cup, minlength=ncup_total)
        cup_ok = np.where(nitens > 0)[0]
        ordc = cup_ok[np.lexsort((dmd["cup_seg"][cup_ok], dmd["cup_dia"][cup_ok]))]
        pos = np.full(ncup_total, -1, dtype=np.int64)
        pos[ordc] = np.arange(len(ordc))
        mi = mes_do_dia[it_dia]
        em_promo = PROMO[it_dia, it_prod]
        preco_it = np.where(em_promo, l["promo_preco"][it_dia, it_prod], l["preco_m"][mi, it_prod])
        custo_it = l["custo_m"][mi, it_prod]
        val_it = np.round(it_qtd * preco_it, 2)
        cst_it = it_qtd * custo_it
        cpos = pos[it_cup]
        NC = len(ordc)
        bruto = np.bincount(cpos, weights=val_it, minlength=NC)
        custo_c = np.bincount(cpos, weights=cst_it, minlength=NC)
        qi = np.bincount(cpos, minlength=NC)
        cdia = dmd["cup_dia"][ordc].astype(np.int64)
        cseg = dmd["cup_seg"][ordc]
        cm = mes_do_dia[cdia] / max(1, NM - 1)
        norte_ne = l["regiao"] in ("Norte", "Nordeste")
        pr = np.vstack([0.20 - 0.08 * cm + (0.05 if norte_ne else 0), 0.30 - 0.04 * cm, 0.27 + 0 * cm,
                        0.17 + 0.12 * cm, np.full(NC, 0.06 if not norte_ne else 0.04)]).T
        pr[bruto > 150, 2] *= 1.7
        pr[bruto < 25, 0] *= 1.6
        pr[bruto < 25, 3] *= 1.3
        pr /= pr.sum(axis=1, keepdims=True)
        fp_idx = np.minimum((r.random(NC)[:, None] > np.cumsum(pr, axis=1)).sum(axis=1), 4)
        formas = np.array(["DINHEIRO", "DEBITO", "CREDITO", "PIX", "VOUCHER"])[fp_idx]
        desconto = np.where(formas == "DINHEIRO", np.round(bruto - np.floor(bruto * 10 + 1e-9) / 10, 2), 0.0)
        # clientes geolocalizados
        NCLI = int(3600 * l["fdem"])
        escala_km = 1.25 if cid_info[l["cidade"]]["pop"] > 3e6 else 1.6
        dist = np.minimum(r.gamma(1.8, escala_km, NCLI), 15.0)
        ang = r.uniform(0, 2 * np.pi, NCLI)
        clat = l["lat"] + dist * np.sin(ang) / 111.0
        clon = l["lon"] + dist * np.cos(ang) / (111.0 * math.cos(math.radians(l["lat"])))
        setor = ((ang + np.pi / 8) // (np.pi / 4)).astype(int) % 8
        anel = (dist > 2.5).astype(int)
        i_ini = l["i0"]
        cad = np.where((r.random(NCLI) < 0.65) & (i_ini == 0), r.integers(-1500, 0, NCLI),
                       i_ini + (r.beta(1.2, 3, NCLI) * (ND - i_ini)).astype(int))
        wcli = (r.pareto(1.3, NCLI) + 0.2) * np.exp(-dist / 3.5)
        wcli /= wcli.sum()
        cli = r.choice(NCLI, size=NC, p=wcli)
        cli_ok = (r.random(NC) < 0.38) & (cad[cli] <= cdia)
        cliente = np.where(cli_ok, cli + cli_id0, 0)
        clientes = []
        for k in range(NCLI):
            sx = "M" if r.random() < 0.42 else "F"
            nm = f"{C.NOMES_M[int(r.integers(0, len(C.NOMES_M)))] if sx == 'M' else C.NOMES_F[int(r.integers(0, len(C.NOMES_F)))]} " \
                 f"{C.SOBRENOMES[int(r.integers(0, 40))]} {C.SOBRENOMES[int(r.integers(0, 40))]}"
            idade = int(np.clip(r.normal(44, 14), 18, 88))
            dc = INICIO + timedelta(days=int(cad[k]))
            bairro = f"{C.BAIRROS[(setor[k] * 2 + anel[k]) % len(C.BAIRROS)]} ({RD.SETORES[setor[k]]})"
            clientes.append((k + cli_id0, l["id"], nm, f"999.{r.integers(100, 999)}.{r.integers(100, 999)}-{r.integers(10, 99)}",
                             (dc - timedelta(days=idade * 365)).isoformat(), sx, bairro, round(float(clat[k]), 6),
                             round(float(clon[k]), 6), round(float(dist[k]), 2), dc.isoformat()))
        con.executemany("INSERT INTO clientes VALUES (?,?,?,?,?,?,?,?,?,?,?)", clientes)
        cli_id0 += NCLI
        # operador e PDV
        operador = np.zeros(NC, dtype=np.int64)
        pdv = np.zeros(NC, dtype=np.int64)
        for i in np.unique(cdia):
            sel = np.where(cdia == i)[0]
            grupos = ops_dia.get((l["id"], dias[i]), {"M": [], "T": []})
            todos = grupos["M"] + grupos["T"] or [None]
            tarde = cseg[sel] >= 14 * 3600 + 1800
            for msk, g in ((~tarde, grupos["M"] or todos), (tarde, grupos["T"] or todos)):
                s2 = sel[msk]
                if len(s2):
                    k = r.integers(0, len(g), len(s2))
                    operador[s2] = [g[x] or 0 for x in k]
                    pdv[s2] = k % l["ck"] + 1
        datas = np.array([dias[i].isoformat() for i in range(ND)])
        cdata = datas[cdia]
        # resumo de cupons (todos)
        rc = pd.DataFrame({"data": cdata, "forma": formas, "itens": qi, "bruto": bruto, "desc": desconto,
                           "custo": custo_c, "fid": cliente > 0})
        rc = rc.groupby(["data", "forma"]).agg(cupons=("itens", "size"), itens=("itens", "sum"), bruto=("bruto", "sum"),
                                               desc=("desc", "sum"), custo=("custo", "sum"), fid=("fid", "sum")).reset_index()
        for t in rc.itertuples():
            rc_rows.append((l["id"], t.data, t.forma, int(t.cupons), int(t.itens), round(t.bruto, 2), round(t.desc, 2),
                            round(t.bruto - t.desc, 2), round(t.custo, 2), int(t.fid)))
        # resumo diário por produto (todos)
        rs = pd.DataFrame({"data": datas[it_dia], "p": it_prod + 1, "q": it_qtd, "v": val_it, "c": cst_it}) \
            .groupby(["data", "p"], as_index=False).sum()
        con.executemany("INSERT INTO resumo_vendas_diario VALUES (?,?,?,?,?,?)",
                        [(l["id"], t.data, int(t.p), round(t.q, 3), round(t.v, 2), round(t.c, 2)) for t in rs.itertuples()])
        l["receita_dia"] = np.bincount(cdia, weights=bruto - desconto, minlength=ND)
        l["fp_mes"] = pd.DataFrame({"comp": [x[:7] for x in cdata], "forma": formas, "v": bruto - desconto}) \
            .groupby(["comp", "forma"])["v"].sum()
        # cupons recentes (vendas + itens)
        sel_c = np.where(cdata >= corte_cupons)[0]
        ids = np.zeros(NC, dtype=np.int64)
        ids[sel_c] = np.arange(proximo_id, proximo_id + len(sel_c))
        proximo_id += len(sel_c)
        vdf = pd.DataFrame({
            "id": ids[sel_c], "unidade_id": l["id"], "data": cdata[sel_c],
            "hora": [f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}" for s in cseg[sel_c]],
            "pdv": pdv[sel_c], "operador_id": pd.array(np.where(operador[sel_c] > 0, operador[sel_c], None), dtype="Int64"),
            "cliente_id": pd.array(np.where(cliente[sel_c] > 0, cliente[sel_c], None), dtype="Int64"),
            "forma_pagamento": formas[sel_c], "qtd_itens": qi[sel_c], "valor_bruto": np.round(bruto[sel_c], 2),
            "desconto": desconto[sel_c], "valor_total": np.round(bruto[sel_c] - desconto[sel_c], 2),
            "custo_total": np.round(custo_c[sel_c], 2), "status": "CONCLUIDA"})
        vdf.to_sql("vendas", con, if_exists="append", index=False, chunksize=50000)
        sel_i = np.where(datas[it_dia] >= corte_itens)[0]
        o = sel_i[np.argsort(ids[cpos[sel_i]], kind="stable")]
        idf = pd.DataFrame({"venda_id": ids[cpos[o]], "produto_id": it_prod[o] + 1, "quantidade": np.round(it_qtd[o], 3),
                            "preco_unitario": preco_it[o], "custo_unitario": np.round(custo_it[o], 4),
                            "em_promocao": em_promo[o].astype(int), "valor_total": val_it[o]})
        idf.to_sql("itens_venda", con, if_exists="append", index=False, chunksize=100000)
        l["n_clientes"] = NCLI
        log(f"  {l['cod']}: receita R$ {l['receita_dia'].sum() / 1e6:,.1f} mi · {NC:,} cupons ({len(sel_c):,} gravados)")
        for k in ("DEM", "qtd_ord", "starts", "trim", "elast", "CONS", "DTOT", "cum"):
            l.pop(k, None)
        del dmd
    con.executemany("INSERT INTO resumo_cupons_diario VALUES (?,?,?,?,?,?,?,?,?,?)", rc_rows)

    # --- compras, transferências, movimentos, rupturas, estoque -----------------
    log("Gravando suprimentos")
    con.executemany("INSERT INTO pedidos_compra VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    [(p["id"], p["uid"], p["forn"], p["comprador"], p["data"].isoformat(), p["prev"].isoformat(),
                      p["receb"].isoformat() if p["receb"] else None, p["status"],
                      f"{rng.integers(100000, 999999)}" if p["receb"] else None, p["total"],
                      forn_info[p["forn"]]["prazo"], p["km"]) for p in pedidos])
    con.executemany("INSERT INTO itens_compra (pedido_id,produto_id,quantidade_pedida,quantidade_recebida,custo_unitario,"
                    "valor_total) VALUES (?,?,?,?,?,?)", itens_c)
    con.executemany("INSERT INTO transferencias VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    [(t["id"], t["cd"], t["loja"], t["data"].isoformat(), t["data"].isoformat(),
                      t["receb"].isoformat() if t["receb"] else None, t["status"], t["v_cd"], t["v_tr"], t["km"],
                      t["viagens"], t["frete"]) for t in transfs])
    con.executemany("INSERT INTO itens_transferencia (transferencia_id,produto_id,quantidade_solicitada,quantidade_enviada,"
                    "custo_cd,preco_transferencia) VALUES (?,?,?,?,?,?)", itens_t)
    con.executemany("INSERT INTO movimentacoes_estoque (unidade_id,data,produto_id,tipo,quantidade,custo_unitario,motivo,"
                    "departamento_id,referencia) VALUES (?,?,?,?,?,?,?,?,?)", movs)
    con.executemany("INSERT INTO rupturas (unidade_id,data,produto_id,qtd_nao_atendida,venda_perdida_estimada) "
                    "VALUES (?,?,?,?,?)", rupt)
    for j, p in enumerate(prods):
        con.execute("INSERT INTO produtos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (j + 1, p["sku"], p["ean"], p["desc"], p["marca"], cat_id[p["cat"]], p["forn"], p["tipo_f"], p["un"],
                     p["emb"], float(custo_m[-1, j]), None if np.isnan(preco_m[-1, j]) else float(preco_m[-1, j]),
                     p["validade"], p["saz"], 1))
    est_rows = []
    for l in lojas:
        f_fin = l["VEND"][-28:].mean(axis=0)
        L = np.where(canal_cd, l["lead_cd"], 1)
        R = np.where(canal_cd, 7 / len(l["dias_cd"]), 1.5)
        for j in range(NP):
            if l["est"][j] <= 0 and f_fin[j] == 0 and not canal_cd[j] and not revenda[j]:
                continue
            est_rows.append((l["id"], j + 1, round(float(l["est"][j]), 3), round(float(l["custo_m"][-1, j]), 4),
                             round(float(f_fin[j] * 0.88 * (L[j] + seg_dias[j])), 1),
                             round(float(f_fin[j] * (L[j] + R[j] + seg_dias[j]) * 1.3), 1), FIM.isoformat() + " 22:00:00"))
    for c in cds:
        f_fin = c["ENV"][-28:].mean(axis=0)
        for j in np.where(canal_cd)[0]:
            est_rows.append((c["id"], j + 1, round(float(c["est"][j]), 3), round(float(custo_m[-1, j] * (1 - desc_cd)), 4),
                             round(float(f_fin[j] * 8), 1), round(float(f_fin[j] * 20), 1), FIM.isoformat() + " 22:00:00"))
    con.executemany("INSERT INTO estoque VALUES (?,?,?,?,?,?,?)", est_rows)

    # =========================================================================
    # 6. Folha de pagamento
    # =========================================================================
    log("Folha de pagamento")
    folha = []
    for c_ in comps:
        ano, mes = int(c_[:4]), int(c_[5:])
        ini_m = date(ano, mes, 1)
        fim_m = date(ano + (mes == 12), mes % 12 + 1, 1) - timedelta(days=1)
        for f in funcs:
            a = max(f["adm"], ini_m)
            b = min((f["dem"] - timedelta(days=1)) if f["dem"] else fim_m, fim_m)
            if b < a:
                continue
            dias_t = 30 if (a == ini_m and b == fim_m) else min(30, (b - a).days + 1)
            sal = salario_em(f["idx"], b)
            info = cargo_info[f["cargo"]]
            he_h = 0.0
            if not info["admin"] and f["tipo"] in ("CLT", "TEMPORARIO"):
                he_h = float(rng.poisson(5 * (2.2 if mes == 12 else 1.0)) * dias_t / 30)
            base = round(sal * dias_t / 30, 2)
            he_v = round(he_h * sal / 220 * 1.5, 2)
            dsr = round(he_v / 6, 2)
            resc = multa = 0.0
            if f["dem"] and ini_m <= f["dem"] <= fim_m + timedelta(days=1) and f["motivo"] == "Dispensa sem justa causa":
                resc = round(sal, 2)
                multa = round(0.40 * 0.08 * sal * min(max(1, (f["dem"] - f["adm"]).days / 30), 120), 2)
            bruto_f = round(base + he_v + dsr + resc, 2)
            inss = calc_inss(bruto_f, ano)
            irrf = calc_irrf(bruto_f, inss, ano, mes)
            vt_desc = round(min(0.06 * base, par["vale_transporte_custo"] * dias_t / 30), 2) if f["vt"] else 0.0
            liq = round(bruto_f - inss - irrf - vt_desc, 2)
            aliq_fgts = 0.02 if f["tipo"] == "JOVEM_APRENDIZ" else par["encargo_fgts"]
            fgts = round(bruto_f * aliq_fgts + multa, 2)
            inss_p = round(bruto_f * par["encargo_inss_patronal"], 2)
            va = round(par["vale_alimentacao"] * dias_t / 30, 2)
            vt_c = round(par["vale_transporte_custo"] * dias_t / 30, 2) if f["vt"] else 0.0
            rem = base + he_v + dsr
            p13 = round(rem / 12, 2)
            pfer = round(rem / 12 * 4 / 3, 2)
            encp = round((p13 + pfer) * (par["encargo_inss_patronal"] + aliq_fgts), 2)
            custo = round(bruto_f + fgts + inss_p + va + vt_c - vt_desc + p13 + pfer + encp, 2)
            folha.append((c_, f["uid"], f["idx"] + 1, dias_t, base, he_h, he_v, dsr, resc, bruto_f, inss, irrf, vt_desc,
                          liq, fgts, inss_p, va, vt_c, p13, pfer, encp, custo))
    con.executemany("INSERT INTO folha_pagamento (competencia,unidade_id,funcionario_id,dias_trabalhados,salario_base,"
                    "horas_extras_qtd,horas_extras_valor,dsr_horas_extras,verbas_rescisorias,salario_bruto,"
                    "inss_funcionario,irrf,desconto_vt,salario_liquido,fgts,inss_patronal,vale_alimentacao,"
                    "vale_transporte_custo,provisao_13,provisao_ferias,encargos_provisoes,custo_total) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", folha)
    FOL = pd.DataFrame(folha, columns=["comp", "uid", "fid", "dias", "base", "heh", "hev", "dsr", "resc", "bruto", "inss",
                                       "irrf", "vtd", "liq", "fgts", "inssp", "va", "vtc", "p13", "pfer", "encp", "custo"])

    # =========================================================================
    # 7. Despesas por unidade, receitas da franqueadora
    # =========================================================================
    log("Despesas por unidade e receitas de franquia")
    cats_desp = [
        ("Aluguel", "FIXA", "OCUPACAO"), ("IPTU", "FIXA", "OCUPACAO"), ("Dedetização e higienização", "FIXA", "OCUPACAO"),
        ("Manutenção de equipamentos e refrigeração", "VARIAVEL", "OCUPACAO"),
        ("Energia elétrica", "VARIAVEL", "UTILIDADES"), ("Água e esgoto", "VARIAVEL", "UTILIDADES"),
        ("Coleta de resíduos", "FIXA", "UTILIDADES"),
        ("Internet e telefonia", "FIXA", "ADMINISTRATIVA"), ("Sistemas (ERP, PDV, WMS)", "FIXA", "ADMINISTRATIVA"),
        ("Contabilidade e auditoria", "FIXA", "ADMINISTRATIVA"), ("Segurança e monitoramento", "FIXA", "ADMINISTRATIVA"),
        ("Seguros", "FIXA", "ADMINISTRATIVA"), ("Material de escritório", "VARIAVEL", "ADMINISTRATIVA"),
        ("Jurídico", "FIXA", "ADMINISTRATIVA"), ("Viagens e visitas de campo", "VARIAVEL", "ADMINISTRATIVA"),
        ("Marketing local", "VARIAVEL", "COMERCIAL"), ("Marketing institucional da rede", "VARIAVEL", "COMERCIAL"),
        ("Taxas de cartão e voucher", "VARIAVEL", "COMERCIAL"), ("Entregas em domicílio", "VARIAVEL", "COMERCIAL"),
        ("Eventos e convenção de franqueados", "VARIAVEL", "COMERCIAL"),
        ("Pró-labore dos sócios", "FIXA", "PESSOAL"), ("INSS sobre pró-labore", "FIXA", "PESSOAL"),
        ("Uniformes e EPIs", "VARIAVEL", "PESSOAL"), ("Exames ocupacionais", "VARIAVEL", "PESSOAL"),
        ("Treinamentos", "VARIAVEL", "PESSOAL"),
        ("Royalties", "VARIAVEL", "FRANQUIA"), ("Fundo de marketing", "VARIAVEL", "FRANQUIA"),
        ("Fretes de transferência", "VARIAVEL", "LOGISTICA"), ("Manutenção de frota e empilhadeiras", "VARIAVEL", "LOGISTICA"),
        ("Tarifas bancárias", "FIXA", "FINANCEIRA"), ("Juros de financiamento", "FIXA", "FINANCEIRA"),
        ("Depreciação", "FIXA", "DEPRECIACAO"),
    ]
    cd_id = {}
    for k, (n, t, g) in enumerate(cats_desp, 1):
        cd_id[n] = k
        con.execute("INSERT INTO categorias_despesa VALUES (?,?,?,?)", (k, n, t, g))

    despesas = []

    def add(uid, c_, cat, desc, fav, valor, dia_venc, dep=None, mes_seguinte=True):
        if valor <= 0:
            return
        ano, mes = int(c_[:4]), int(c_[5:])
        if mes_seguinte:
            ano, mes = ano + (mes == 12), mes % 12 + 1
        venc = date(ano, mes, min(dia_venc, 28))
        if cat == "Depreciação":
            despesas.append((uid, c_, cd_id[cat], desc, fav, dep, round(valor, 2), venc.isoformat(), None, "PAGO"))
            return
        pg = venc + timedelta(days=int(rng.integers(0, 4)) if rng.random() < 0.06 else 0)
        pago = pg <= FIM
        despesas.append((uid, c_, cd_id[cat], desc, fav, dep, round(valor, 2), venc.isoformat(),
                         pg.isoformat() if pago else None, "PAGO" if pago else "ABERTO"))

    D = dep_id
    TR = pd.DataFrame(transfs)
    TR["comp"] = TR["data"].map(comp)
    frete_cd = TR.groupby(["cd", "comp"])["frete"].sum()
    transf_cd = TR.groupby(["cd", "comp"])["v_tr"].sum()
    adm_m = pd.Series([(f["uid"], comp(f["adm"])) for f in funcs if f["adm"] >= INICIO]).value_counts()
    receitas = []
    rec_loja_m = {}
    for l in lojas:
        s = pd.Series(l["receita_dia"], index=[comp(d) for d in dias]).groupby(level=0).sum()
        rec_loja_m[l["id"]] = s

    for c_ in comps:
        ano, mes = int(c_[:4]), int(c_[5:])
        anos = idx_mes(date(ano, mes, 1)) / 12
        fe = {1: 1.22, 2: 1.22, 3: 1.18, 4: 1.05, 5: .95, 6: .86, 7: .84, 8: .88, 9: .97, 10: 1.08, 11: 1.12, 12: 1.2}[mes]
        reaj_alug = (1.042 if (ano > 2025 or (ano == 2025 and mes >= 3)) else 1.0) * (1.031 if (ano == 2026 and mes >= 3) else 1.0)
        for u in unid:
            ini_u = u["inaug"] - timedelta(days=30)
            if date(ano, mes, 1) < date(ini_u.year, ini_u.month, 1):
                continue
            uid = u["id"]
            esc = u["area"] / 1400
            n_adm = int(adm_m.get((uid, c_), 0))
            if u["tipo"] == "LOJA":
                rec = float(rec_loja_m[uid].get(c_, 0))
                aberta = rec > 0
                add(uid, c_, "Aluguel", f"Aluguel {c_}", "Locador do imóvel (fictício)", u["area"] * u["alu"] * reaj_alug, 5, D["Gerência"])
                if 2 <= mes <= 11:
                    add(uid, c_, "IPTU", f"IPTU {ano} parcela {mes - 1}/10", "Prefeitura Municipal", 1.65 * u["area"] * (1.045 ** (ano - 2025)), 15, D["Gerência"], False)
                if not aberta:
                    add(uid, c_, "Treinamentos", "Treinamento de equipe para inauguração", "Universidade Vale Verde", 25000, 10, D["Gerência"])
                    add(uid, c_, "Marketing local", "Campanha de inauguração", "Agência regional", 60000, 10, D["Gerência"])
                    continue
                add(uid, c_, "Dedetização e higienização", "Controle de pragas mensal", "Higienize Serviços Ambientais", 650, 10, D["Limpeza"])
                manut = rng.uniform(3500, 9000) * esc * (1.4 if mes in (12, 1, 2) else 1.0)
                if rng.random() < 0.12:
                    manut += rng.uniform(8000, 22000)
                add(uid, c_, "Manutenção de equipamentos e refrigeração", "Manutenção preventiva e corretiva", "Frio Total Refrigeração", manut, 10, D["Recebimento/Depósito"])
                add(uid, c_, "Energia elétrica", f"Conta de energia {c_}", "Concessionária de Energia Elétrica",
                    30000 * esc * u["ener"] * fe * (1.045 ** anos) * rng.uniform(0.96, 1.08), 12, D["Gerência"])
                add(uid, c_, "Água e esgoto", f"Conta de água {c_}", "Companhia de Saneamento", 3300 * esc * (1.05 ** anos) * rng.uniform(0.9, 1.12), 12, D["Gerência"])
                add(uid, c_, "Coleta de resíduos", "Coleta de resíduos orgânicos e recicláveis", "Coleta Ambiental", 900 * esc, 10, D["Limpeza"])
                add(uid, c_, "Internet e telefonia", "Link dedicado + telefonia", "Conecta Telecom", 1150, 15, D["Administrativo/Financeiro"])
                add(uid, c_, "Sistemas (ERP, PDV, WMS)", "Licenças de PDV e retaguarda", "Sistemas Varejo Mais", 380 * u["ck"] * (1.05 ** int(anos)), 10, D["Administrativo/Financeiro"])
                if u["modelo"] == "FRANQUIA":
                    add(uid, c_, "Contabilidade e auditoria", "Honorários contábeis", "Escritório contábil local", 4800, 10, D["Administrativo/Financeiro"])
                    add(uid, c_, "Pró-labore dos sócios", "Pró-labore do franqueado", RD.FRANQUEADOS[u["franq"] - 1][2], 15000, 5, D["Gerência"])
                    add(uid, c_, "INSS sobre pró-labore", "INSS 20% sobre pró-labore", "Receita Federal", 3000, 20, D["Gerência"])
                    juros = 6500 * (0.985 ** max(0, (date(ano, mes, 1) - u["inaug"]).days / 30))
                    add(uid, c_, "Juros de financiamento", "Juros do financiamento da implantação", "Banco Comercial", juros, 15, D["Administrativo/Financeiro"], False)
                    roy = rec * par["royalties_pct"]
                    fun = rec * par["fundo_marketing_pct"]
                    add(uid, c_, "Royalties", f"Royalties {c_} ({par['royalties_pct'] * 100:.1f}%)", "Vale Verde Franquias", roy, 10, D["Gerência"])
                    add(uid, c_, "Fundo de marketing", f"Fundo de marketing {c_}", "Vale Verde Franquias", fun, 10, D["Gerência"])
                    vy, vm = ano + (mes == 12), mes % 12 + 1
                    venc = date(vy, vm, 10)
                    for tipo, v, pct in (("ROYALTIES", roy, par["royalties_pct"]), ("FUNDO_MARKETING", fun, par["fundo_marketing_pct"])):
                        receitas.append((c_, uid, u["franq"], tipo, round(rec, 2), pct, round(v, 2), venc.isoformat(),
                                         venc.isoformat() if venc <= FIM else None, "RECEBIDO" if venc <= FIM else "ABERTO"))
                add(uid, c_, "Segurança e monitoramento", "Monitoramento 24h e alarmes", "Guardião Segurança Eletrônica", 4100 * esc, 10, D["Prevenção de Perdas"])
                add(uid, c_, "Seguros", "Seguro do estabelecimento (parcela)", "Seguradora Horizonte", 1480 * esc, 20, D["Gerência"])
                add(uid, c_, "Material de escritório", "Papelaria e suprimentos", "Papelaria Central", rng.uniform(380, 950), 10, D["Administrativo/Financeiro"])
                add(uid, c_, "Marketing local", "Carro de som, panfletos e redes sociais locais", "Agência regional", rec * 0.002 * rng.uniform(0.8, 1.2), 15, D["Gerência"])
                fp = l_fp = next(x for x in lojas if x["id"] == uid)["fp_mes"]
                fpc = fp.loc[c_] if c_ in fp.index.get_level_values(0) else pd.Series(dtype=float)
                mdr = fpc.get("DEBITO", 0) * par["mdr_debito"] + fpc.get("CREDITO", 0) * par["mdr_credito"] + fpc.get("VOUCHER", 0) * par["mdr_voucher"]
                add(uid, c_, "Taxas de cartão e voucher", f"MDR adquirentes {c_}", "Adquirentes (cartões/vouchers)", mdr, 1, D["Frente de Caixa"])
                add(uid, c_, "Entregas em domicílio", "Entregas (terceirizado)", "Leva & Traz Entregas", rec * 0.0025 * rng.uniform(0.8, 1.2), 10, D["Frente de Caixa"])
                add(uid, c_, "Uniformes e EPIs", "Uniformes, botas e aventais", "Uniformes Ideal", 300 + n_adm * 180 + (1800 * esc if mes in (3, 9) else 0), 10, D["Administrativo/Financeiro"])
                add(uid, c_, "Exames ocupacionais", "ASO admissional/periódico/demissional", "Clínica Saúde do Trabalho", 250 + n_adm * 120 + rng.uniform(0, 200), 10, D["Administrativo/Financeiro"])
                if mes in (2, 6, 9):
                    add(uid, c_, "Treinamentos", "Treinamento de atendimento e segurança de alimentos", "Universidade Vale Verde", rng.uniform(1200, 2800), 10, D["Administrativo/Financeiro"])
                add(uid, c_, "Tarifas bancárias", "Tarifas e pacote de serviços", "Banco Comercial", 680, 1, D["Administrativo/Financeiro"], False)
                add(uid, c_, "Depreciação", "Depreciação de equipamentos e instalações", "Lançamento contábil (não-caixa)",
                    6800 * esc * (1.35 if u["i0"] > 0 else 1.0), 28, D["Gerência"], False)
            elif u["tipo"] == "CD":
                add(uid, c_, "Aluguel", f"Aluguel do galpão {c_}", "Condomínio Logístico (fictício)", u["area"] * u["alu"] * 0.6 * reaj_alug, 5, D["Logística (CD)"])
                add(uid, c_, "Energia elétrica", f"Conta de energia {c_}", "Concessionária de Energia Elétrica", 4.0 * u["area"] * u["ener"] * fe * rng.uniform(0.95, 1.08), 12, D["Logística (CD)"])
                add(uid, c_, "Água e esgoto", f"Conta de água {c_}", "Companhia de Saneamento", 900 * rng.uniform(0.9, 1.1), 12, D["Logística (CD)"])
                add(uid, c_, "Segurança e monitoramento", "Portaria e vigilância 24h", "Guardião Segurança", 0.9 * u["area"], 10, D["Logística (CD)"])
                add(uid, c_, "Sistemas (ERP, PDV, WMS)", "WMS e coletores", "Sistemas Varejo Mais", 3500, 10, D["Logística (CD)"])
                add(uid, c_, "Seguros", "Seguro de carga e patrimonial", "Seguradora Horizonte", float(transf_cd.get((uid, c_), 0)) * 0.0008 + 1500, 20, D["Logística (CD)"])
                add(uid, c_, "Fretes de transferência", f"Fretes CD→lojas {c_}", "Transportadora Rota Certa (terceirizada)", float(frete_cd.get((uid, c_), 0)), 15, D["Logística (CD)"])
                add(uid, c_, "Manutenção de frota e empilhadeiras", "Empilhadeiras e paleteiras", "Movimenta Equipamentos", rng.uniform(2500, 6000) * u["area"] / 9000 + 1500, 10, D["Logística (CD)"])
                add(uid, c_, "Uniformes e EPIs", "EPIs do CD", "Uniformes Ideal", 400 + n_adm * 220, 10, D["Logística (CD)"])
                add(uid, c_, "Exames ocupacionais", "ASO", "Clínica Saúde do Trabalho", 150 + n_adm * 120, 10, D["Logística (CD)"])
                add(uid, c_, "Depreciação", "Depreciação de racks, empilhadeiras e instalações", "Lançamento contábil (não-caixa)", 1.6 * u["area"], 28, D["Logística (CD)"], False)
            else:   # sede
                fundo = sum(rec_loja_m[l["id"]].get(c_, 0) for l in lojas if l["modelo"] == "FRANQUIA") * par["fundo_marketing_pct"]
                add(uid, c_, "Aluguel", f"Aluguel do escritório {c_}", "Edifício Corporativo (fictício)", u["area"] * u["alu"] * reaj_alug, 5, D["Franqueadora (Sede)"])
                add(uid, c_, "Energia elétrica", f"Conta de energia {c_}", "Concessionária de Energia Elétrica", 4200 * fe, 12, D["Franqueadora (Sede)"])
                add(uid, c_, "Internet e telefonia", "Links e telefonia corporativa", "Conecta Telecom", 3200, 15, D["Franqueadora (Sede)"])
                add(uid, c_, "Sistemas (ERP, PDV, WMS)", "ERP corporativo, BI e nuvem", "Sistemas Varejo Mais", 24000 * (1.05 ** int(anos)), 10, D["Franqueadora (Sede)"])
                add(uid, c_, "Contabilidade e auditoria", "Contabilidade centralizada (lojas próprias + CDs) e auditoria", "Exatidão Auditores", 26000, 10, D["Franqueadora (Sede)"])
                add(uid, c_, "Jurídico", "Assessoria jurídica e contratos de franquia", "Mendes & Rocha Advogados (fictício)", 9500, 10, D["Franqueadora (Sede)"])
                add(uid, c_, "Viagens e visitas de campo", "Visitas de consultores e expansão", "Agência de Viagens Rumo", rng.uniform(14000, 26000), 10, D["Franqueadora (Sede)"])
                add(uid, c_, "Marketing institucional da rede", "Campanhas nacionais (encarte, rádio, digital)", "Agência Ponto Criativo",
                    fundo * rng.uniform(0.9, 1.0) + sum(rec_loja_m[l["id"]].get(c_, 0) for l in lojas if l["modelo"] == "PROPRIA") * 0.004 + (40000 if mes == 12 else 0), 15, D["Franqueadora (Sede)"])
                if mes == 3:
                    add(uid, c_, "Eventos e convenção de franqueados", f"Convenção anual {ano}", "Eventos Prime", 85000, 15, D["Franqueadora (Sede)"])
                add(uid, c_, "Material de escritório", "Papelaria e suprimentos", "Papelaria Central", rng.uniform(600, 1400), 10, D["Franqueadora (Sede)"])
                add(uid, c_, "Pró-labore dos sócios", "Pró-labore dos fundadores", "Sócios fundadores", 36000, 5, D["Franqueadora (Sede)"])
                add(uid, c_, "INSS sobre pró-labore", "INSS 20% sobre pró-labore", "Receita Federal", 7200, 20, D["Franqueadora (Sede)"])
                add(uid, c_, "Tarifas bancárias", "Tarifas e cash management", "Banco Comercial", 1900, 1, D["Franqueadora (Sede)"], False)
                add(uid, c_, "Depreciação", "Depreciação de móveis e TI", "Lançamento contábil (não-caixa)", 5200, 28, D["Franqueadora (Sede)"], False)
    # taxas iniciais de franquia
    for k, (rs, nf, socio, dc) in enumerate(RD.FRANQUEADOS, 1):
        dcd = date.fromisoformat(dc)
        if INICIO <= dcd <= FIM:
            loja = next(l for l in lojas if l["franq"] == k)
            receitas.append((comp(dcd), loja["id"], k, "TAXA_FRANQUIA", None, None, par["taxa_franquia"], dc, dc, "RECEBIDO"))
    con.executemany("INSERT INTO despesas (unidade_id,competencia,categoria_id,descricao,favorecido,departamento_id,valor,"
                    "data_vencimento,data_pagamento,status) VALUES (?,?,?,?,?,?,?,?,?,?)", despesas)
    con.executemany("INSERT INTO receitas_franquia (competencia,loja_id,franqueado_id,tipo,base_calculo,percentual,valor,"
                    "data_vencimento,data_recebimento,status) VALUES (?,?,?,?,?,?,?,?,?,?)", receitas)

    # =========================================================================
    # 8. Contas a pagar
    # =========================================================================
    log("Contas a pagar e impostos")
    cp = []
    sede_id = sede["id"]

    def conta(uid, origem, ref, fav, c_, emissao, venc, valor, fav_uid=None, atraso=True):
        if valor <= 0:
            return
        pg = venc
        if atraso and rng.random() < 0.05:
            pg = venc + timedelta(days=int(rng.integers(1, 5)))
        pago = pg <= FIM
        cp.append((uid, origem, ref, fav, fav_uid, c_, emissao.isoformat(), venc.isoformat(), round(valor, 2),
                   pg.isoformat() if pago else None, "PAGO" if pago else "ABERTO"))

    for p in pedidos:
        if p["receb"] is None:
            continue
        conta(p["uid"], "COMPRA", f"PC-{p['id']:06d}", forn_info[p["forn"]]["nome"], comp(p["receb"]), p["receb"],
              p["receb"] + timedelta(days=forn_info[p["forn"]]["prazo"]), p["total"])
    for t in transfs:
        if t["receb"] is None or U[t["loja"]]["modelo"] != "FRANQUIA":
            continue      # lojas próprias: transferência intercompany sem título
        conta(t["loja"], "TRANSFERENCIA", f"TR-{t['id']:06d}", U[t["cd"]]["nome"], comp(t["receb"]), t["receb"],
              t["receb"] + timedelta(days=int(par["prazo_transferencia_franquia"])), t["v_tr"], fav_uid=t["cd"])
    for (uid, c_, cid_, desc, fav, dep, valor, venc, pg, st) in despesas:
        if cid_ == cd_id["Depreciação"]:
            continue
        franq = cid_ in (cd_id["Royalties"], cd_id["Fundo de marketing"])
        cp.append((uid, "FRANQUIA" if franq else "DESPESA", desc, fav, sede_id if franq else None, c_, f"{c_}-01", venc,
                   valor, pg, st))

    def dia_util(ano, mes, n):
        d = date(ano, mes, 1)
        k = 0
        while True:
            if d.weekday() < 5:
                k += 1
                if k == n:
                    return d
            d += timedelta(days=1)

    for (c_, uid), g in FOL.groupby(["comp", "uid"]):
        ano, mes = int(c_[:4]), int(c_[5:])
        a2, m2 = ano + (mes == 12), mes % 12 + 1
        em = date(ano, mes, 28)
        conta(uid, "FOLHA", f"Folha {c_}", "Funcionários (salário líquido)", c_, em, dia_util(a2, m2, 5), g["liq"].sum(), atraso=False)
        conta(uid, "FOLHA", f"Vale-alimentação {c_}", "Cartão Alimenta Mais", c_, em, date(ano, mes, 25), g["va"].sum(), atraso=False)
        conta(uid, "FOLHA", f"Vale-transporte {c_}", "Operadora de transporte", c_, em, date(ano, mes, 1), g["vtc"].sum(), atraso=False)
        conta(uid, "ENCARGOS", f"INSS {c_}", "Receita Federal (DCTFWeb)", c_, em, date(a2, m2, 20), g["inss"].sum() + g["inssp"].sum(), atraso=False)
        conta(uid, "ENCARGOS", f"FGTS {c_}", "FGTS Digital (Caixa)", c_, em, date(a2, m2, 20), g["fgts"].sum(), atraso=False)
        conta(uid, "ENCARGOS", f"IRRF folha {c_}", "Receita Federal", c_, em, date(a2, m2, 20), g["irrf"].sum(), atraso=False)
        conta(uid, "FOLHA", f"Férias pagas {c_}", "Funcionários (férias)", c_, em, date(ano, mes, 26), g["pfer"].sum(), atraso=False)
        if mes in (11, 12):
            ano13 = FOL[(FOL["comp"].str[:4] == str(ano)) & (FOL["uid"] == uid)]
            v13 = ano13["p13"].sum() * 12 / max(1, ano13["comp"].nunique()) * 0.5
            conta(uid, "FOLHA", f"13º salário {ano} - {'1ª' if mes == 11 else '2ª'} parcela", "Funcionários (13º)", c_, em,
                  date(ano, mes, 28 if mes == 11 else 19), v13, atraso=False)

    # Impostos: ICMS/PIS sobre vendas por loja; ISS/PIS/COFINS sobre receitas de franquia (sede);
    # IR/CSLL por entidade (cada franqueado é uma empresa; a franqueadora consolida lojas próprias, CDs e sede)
    RS = pd.read_sql_query("SELECT unidade_id u, substr(data,1,7) c, SUM(custo) cmv FROM resumo_vendas_diario GROUP BY 1,2", con)
    MV = pd.DataFrame(movs, columns=["u", "data", "pid", "tipo", "q", "cu", "mot", "dep", "ref"])
    MV["c"] = MV["data"].str[:7]
    MV["v"] = MV["q"] * MV["cu"]
    DS = pd.DataFrame(despesas, columns=["u", "c", "cid", "desc", "fav", "dep", "valor", "venc", "pg", "st"])
    RF = pd.DataFrame(receitas, columns=["c", "loja", "franq", "tipo", "base", "pct", "valor", "venc", "rec", "st"])
    lucro_ent = {}
    for c_ in comps:
        ano, mes = int(c_[:4]), int(c_[5:])
        a2, m2 = ano + (mes == 12), mes % 12 + 1
        em = date(ano, mes, 28)
        for u in unid:
            uid = u["id"]
            rec = float(rec_loja_m[uid].get(c_, 0)) if u["tipo"] == "LOJA" else 0.0
            ded = rec * (par["aliq_icms_efetiva"] + par["aliq_pis_cofins_efetiva"])
            if u["tipo"] == "LOJA" and rec > 0:
                conta(uid, "IMPOSTOS", f"ICMS {c_}", "Secretaria da Fazenda", c_, em, date(a2, m2, 20), rec * par["aliq_icms_efetiva"], atraso=False)
                conta(uid, "IMPOSTOS", f"PIS/COFINS {c_}", "Receita Federal", c_, em, date(a2, m2, 25), rec * par["aliq_pis_cofins_efetiva"], atraso=False)
            cmv = float(RS[(RS["u"] == uid) & (RS["c"] == c_)]["cmv"].sum())
            mv = MV[(MV["u"] == uid) & (MV["c"] == c_) & MV["tipo"].isin(["PERDA", "AJUSTE_INVENTARIO", "CONSUMO_INTERNO"])]["v"].sum()
            desp = float(DS[(DS["u"] == uid) & (DS["c"] == c_)]["valor"].sum())
            fol = float(FOL[(FOL["uid"] == uid) & (FOL["comp"] == c_)]["custo"].sum())
            outras = 0.0
            if u["tipo"] == "CD":
                outras = float(TR[(TR["cd"] == uid) & (TR["comp"] == c_)].eval("v_tr - v_cd").sum())
            if u["tipo"] == "SEDE":
                rf = float(RF[RF["c"] == c_]["valor"].sum())
                iss = rf * par["aliq_impostos_servicos"]
                outras = rf - iss
                if iss > 0:
                    conta(uid, "IMPOSTOS", f"ISS/PIS/COFINS serviços {c_}", "Prefeitura / Receita Federal", c_, em, date(a2, m2, 15), iss, atraso=False)
            lair = rec - ded - cmv + mv - fol - desp + outras
            ent = uid if u["modelo"] == "FRANQUIA" else sede_id
            lucro_ent[(ent, c_)] = lucro_ent.get((ent, c_), 0.0) + lair
    for (ent, c_), lair in lucro_ent.items():
        if lair > 0:
            ano, mes = int(c_[:4]), int(c_[5:])
            a2, m2 = ano + (mes == 12), mes % 12 + 1
            conta(ent, "IMPOSTOS", f"IRPJ/CSLL estimativa {c_}", "Receita Federal", c_, date(ano, mes, 28),
                  date(a2, m2, 28), lair * par["aliq_ir_csll"], atraso=False)
    con.executemany("INSERT INTO contas_pagar (unidade_id,origem,referencia,favorecido,favorecido_unidade_id,competencia,"
                    "data_emissao,data_vencimento,valor,data_pagamento,status) VALUES (?,?,?,?,?,?,?,?,?,?,?)", cp)

    con.commit()
    erros = con.execute("PRAGMA foreign_key_check").fetchall()
    if erros:
        log(f"ATENÇÃO: {len(erros)} violações de chave estrangeira, ex.: {erros[:3]}")
    log("Otimizando o banco (ANALYZE)")
    con.execute("ANALYZE")
    con.commit()
    con.close()

    # ---------------------------------------------------------------------------
    log("Resultado antes do IR por entidade nos últimos 12 meses:")
    ult12 = comps[-12:]
    for ent in sorted({e for e, _ in lucro_ent}):
        v = sum(lucro_ent.get((ent, c_), 0) for c_ in ult12)
        if U[ent]["tipo"] == "LOJA":
            rec = float(rec_loja_m[ent][rec_loja_m[ent].index.isin(ult12)].sum())
            print(f"    {U[ent]['cod']} {U[ent]['nome']:<40} receita R$ {rec / 1e6:6.2f} mi  LAIR R$ {v / 1e3:8.0f} mil ({v / max(rec, 1) * 100:5.2f}%)")
        else:
            print(f"    Franqueadora (lojas próprias + CDs + sede)            LAIR R$ {v / 1e3:8.0f} mil")
    for l in lojas:
        print(f"    {l['cod']} receita 12m R$ {rec_loja_m[l['id']][rec_loja_m[l['id']].index.isin(ult12)].sum() / 1e6:6.2f} mi")
    log(f"Banco gerado em {args.db} ({os.path.getsize(args.db) / 1e6:.0f} MB) em {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
