"""
Exporta a Rede Vale Verde em modelo estrela (CSV) para o Power BI.

Uso (na pasta mercado_vale_verde):
    python powerbi/exportar_powerbi.py
Gera os arquivos em powerbi/dados/. No Power BI Desktop: Obter dados > Pasta > powerbi/dados
(ou Texto/CSV, um por um). Separador ";" e decimal "," (padrão brasileiro), codificação UTF-8.

Tabelas
  Dimensões: dCalendario, dUnidade, dProduto, dCidade, dFornecedor, dCliente
  Fatos:     fVendas (loja x dia x produto), fCupons (loja x dia x forma de pagamento),
             fTransferencias, fCompras, fPerdas, fRupturas, fFolha, fDespesas, fReceitasFranquia,
             fDRE (formato longo: unidade x mês x linha da DRE),
             fEstoque (posição atual), fCaixa (fluxo mensal), fCaixaProjetado (60 dias), fContasPagar
"""
import os
import sys
from datetime import date, timedelta

import pandas as pd

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
SAIDA = os.path.join(RAIZ, "powerbi", "dados")

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


ERROS = []


def salvar(df, nome):
    caminho = os.path.join(SAIDA, f"{nome}.csv")
    df.to_csv(caminho, sep=";", decimal=",", index=False, encoding="utf-8-sig", float_format="%.4f")
    print(f"  {nome:<20} {len(df):>10,} linhas  {os.path.getsize(caminho) / 1e6:7.1f} MB", flush=True)


def exportar(nome, funcao):
    """Executa uma exportação; se der erro, mostra o motivo e segue para a próxima tabela."""
    import traceback
    try:
        salvar(funcao(), nome)
    except Exception as e:  # noqa
        ERROS.append(nome)
        print(f"  {nome:<20} ERRO: {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()


def main():
    from app import create_app
    from app import relatorios as R
    from app.db import df

    banco = os.environ.get("VV_DB", os.path.join(RAIZ, "dados", "vale_verde.db"))
    if not os.path.exists(banco) or os.path.getsize(banco) < 1_000_000:
        print(f"\nBanco não encontrado em:\n  {banco}\n")
        print("Rode este script de dentro da pasta mercado_vale_verde que tem o banco gerado")
        print("(a que você usa com 'python run.py'), copiando a pasta powerbi para dentro dela.")
        sys.exit(1)
    os.makedirs(SAIDA, exist_ok=True)
    app = create_app(banco)
    with app.app_context():
        print("Exportando para", SAIDA)
        # ---------------- dimensões ----------------
        ini, fim = date(2024, 11, 1), date(2026, 12, 31)
        fechados = {"12-25", "01-01"}
        cal = []
        d = ini
        while d <= fim:
            cal.append(dict(Data=d.isoformat(), Ano=d.year, MesNum=d.month, Mes=MESES[d.month - 1],
                            AnoMes=f"{d.year}-{d.month:02d}", MesAno=f"{MESES[d.month - 1]}/{str(d.year)[2:]}",
                            Trimestre=f"{d.year} T{(d.month - 1) // 3 + 1}", DiaSemanaNum=d.weekday() + 1,
                            DiaSemana=DIAS[d.weekday()], Dia=d.day, FimDeSemana=int(d.weekday() >= 5),
                            LojaFechada=int(d.strftime("%m-%d") in fechados),
                            IndiceMes=(d.year - 2024) * 12 + d.month - 11))
            d += timedelta(days=1)
        exportar("dCalendario", lambda: pd.DataFrame(cal))

        exportar("dUnidade", lambda: df("""SELECT u.id UnidadeID, u.codigo Codigo, u.nome Unidade, u.tipo Tipo,
                            COALESCE(u.modelo, 'FRANQUEADORA') Modelo, c.nome Cidade, c.uf UF, c.regiao Regiao,
                            u.lat Latitude, u.lon Longitude, u.area_m2 AreaM2, u.checkouts Checkouts,
                            u.data_inauguracao Inauguracao, cd.codigo CD, u.distancia_cd_km DistanciaCDkm,
                            u.lead_time_cd_dias LeadTimeCD, f.nome_fantasia Franqueado, u.fator_preco FatorPreco
                     FROM unidades u JOIN cidades c ON c.id=u.cidade_id LEFT JOIN unidades cd ON cd.id=u.cd_id
                     LEFT JOIN franqueados f ON f.id=u.franqueado_id ORDER BY u.id"""))
        exportar("dProduto", lambda: df("""SELECT p.id ProdutoID, p.sku SKU, p.descricao Produto, COALESCE(p.marca,'(sem marca)') Marca,
                            c.nome Categoria, c.canal Canal, c.perecivel Perecivel, c.revenda Revenda, p.unidade Medida,
                            p.validade_dias ValidadeDias, COALESCE(p.sazonalidade,'') Sazonalidade,
                            CASE WHEN p.marca='Vale Verde' THEN 1 ELSE 0 END MarcaPropria
                     FROM produtos p JOIN categorias c ON c.id=p.categoria_id ORDER BY p.id"""))
        exportar("dCidade", lambda: df("""SELECT c.id CidadeID, c.nome Cidade, c.uf UF, c.regiao Regiao, c.lat Latitude, c.lon Longitude,
                            c.populacao Populacao, c.renda_per_capita RendaPerCapita,
                            c.supermercados_concorrentes Concorrentes,
                            CASE WHEN EXISTS (SELECT 1 FROM unidades u WHERE u.cidade_id=c.id AND u.tipo='LOJA') THEN 'Com loja'
                                 WHEN EXISTS (SELECT 1 FROM unidades u WHERE u.cidade_id=c.id) THEN 'CD/Sede'
                                 ELSE 'Candidata' END Situacao
                     FROM cidades c"""))
        exportar("dFornecedor", lambda: df("""SELECT id FornecedorID, nome_fantasia Fornecedor, abrangencia Abrangencia,
                            COALESCE(regiao_atendida,'Nacional') RegiaoAtendida, tipo Tipo, cidade Cidade, uf UF,
                            lat Latitude, lon Longitude, prazo_pagamento_dias PrazoPagamento FROM fornecedores"""))
        exportar("dCliente", lambda: df("""SELECT id ClienteID, unidade_id UnidadeID, sexo Sexo, bairro Bairro, lat Latitude, lon Longitude,
                            distancia_km DistanciaKm,
                            CASE WHEN distancia_km < 1 THEN '0-1 km' WHEN distancia_km < 3 THEN '1-3 km'
                                 WHEN distancia_km < 5 THEN '3-5 km' ELSE '5+ km' END FaixaDistancia,
                            data_cadastro Cadastro,
                            (SELECT COUNT(*) FROM vendas v WHERE v.cliente_id=c.id) Compras6m,
                            (SELECT ROUND(SUM(valor_total),2) FROM vendas v WHERE v.cliente_id=c.id) Valor6m
                     FROM clientes c"""))

        # ---------------- fatos ----------------
        exportar("fVendas", lambda: df("""SELECT unidade_id UnidadeID, data Data, produto_id ProdutoID, quantidade Quantidade,
                            receita Receita, custo CMV FROM resumo_vendas_diario"""))
        exportar("fCupons", lambda: df("""SELECT unidade_id UnidadeID, data Data, forma_pagamento FormaPagamento, cupons Cupons, itens Itens,
                            valor_bruto ValorBruto, desconto Desconto, valor_total Receita, custo_total CMV,
                            cupons_fidelidade CuponsFidelidade FROM resumo_cupons_diario"""))
        exportar("fTransferencias", lambda: df("""SELECT id TransferenciaID, cd_id CDID, loja_id UnidadeID, data_envio Data, data_recebimento DataRecebimento,
                            status Status, valor_custo_cd CustoCD, valor_transferencia ValorTransferencia,
                            distancia_km DistanciaKm, viagens Viagens, custo_frete Frete,
                            julianday(data_recebimento) - julianday(data_envio) LeadTimeDias
                     FROM transferencias"""))
        exportar("fCompras", lambda: df("""SELECT p.id PedidoID, p.unidade_id UnidadeID, p.fornecedor_id FornecedorID, p.data_pedido Data,
                            p.data_recebimento DataRecebimento, p.status Status, p.valor_total Valor,
                            p.distancia_km DistanciaKm,
                            julianday(p.data_recebimento) - julianday(p.data_pedido) LeadTimeDias
                     FROM pedidos_compra p"""))
        exportar("fPerdas", lambda: df("""SELECT unidade_id UnidadeID, data Data, produto_id ProdutoID, tipo Tipo, COALESCE(motivo,'') Motivo,
                            -quantidade Quantidade, -quantidade*custo_unitario Valor
                     FROM movimentacoes_estoque WHERE tipo IN ('PERDA','AJUSTE_INVENTARIO','CONSUMO_INTERNO')"""))
        exportar("fRupturas", lambda: df("""SELECT unidade_id UnidadeID, data Data, produto_id ProdutoID, qtd_nao_atendida QtdNaoAtendida,
                            venda_perdida_estimada VendaPerdida FROM rupturas"""))
        exportar("fFolha", lambda: df("""SELECT fp.competencia || '-01' Data, fp.unidade_id UnidadeID, c.nome Cargo, d.nome Departamento,
                            COUNT(*) Funcionarios, SUM(fp.salario_bruto) SalarioBruto,
                            SUM(fp.horas_extras_valor + fp.dsr_horas_extras) HorasExtras,
                            SUM(fp.fgts + fp.inss_patronal) Encargos,
                            SUM(fp.vale_alimentacao + fp.vale_transporte_custo - fp.desconto_vt) Beneficios,
                            SUM(fp.provisao_13 + fp.provisao_ferias + fp.encargos_provisoes) Provisoes,
                            SUM(fp.custo_total) CustoTotal
                     FROM folha_pagamento fp JOIN funcionarios f ON f.id=fp.funcionario_id JOIN cargos c ON c.id=f.cargo_id
                     JOIN departamentos d ON d.id=c.departamento_id GROUP BY 1,2,3,4"""))
        exportar("fDespesas", lambda: df("""SELECT d.competencia || '-01' Data, d.unidade_id UnidadeID, cd.nome Categoria, cd.tipo Tipo,
                            cd.grupo_dre GrupoDRE, d.valor Valor FROM despesas d
                     JOIN categorias_despesa cd ON cd.id=d.categoria_id"""))
        exportar("fReceitasFranquia", lambda: df("""SELECT competencia || '-01' Data, loja_id UnidadeID, tipo Tipo, base_calculo Base, valor Valor,
                            status Status FROM receitas_franquia"""))

        # ---------------- estoque e caixa ----------------
        ids_todos = [r["id"] for r in R.q("SELECT id FROM unidades ORDER BY id")]
        ref = R.data_referencia()

        def estoque():
            t = R.posicao_estoque(ids=ids_todos)
            t = t[t["revenda"] == 1] if "revenda" in t else t
            return pd.DataFrame(dict(
                UnidadeID=t["unidade_id"], ProdutoID=t["id"], Quantidade=t["quantidade"].astype(float),
                CustoMedio=t["custo_medio"].astype(float), Valor=(t["quantidade"] * t["custo_medio"]).astype(float),
                EstoqueMinimo=t["estoque_minimo"], EstoqueMaximo=t["estoque_maximo"],
                SaidaDia=t["saida_dia"].round(4), CoberturaDias=t["cobertura_dias"].round(1),
                Status=t["status"], DataPosicao=ref.isoformat()))
        exportar("fEstoque", estoque)

        ROT = {"entradas_vendas": ("Entradas", "Vendas (cartão, PIX, dinheiro)"),
               "entradas_rede": ("Entradas", "Recebido da rede (royalties, transferências)"),
               "saida_compra": ("Saídas", "Fornecedores"), "saida_transferencia": ("Saídas", "Transferências do CD"),
               "saida_folha": ("Saídas", "Folha de pagamento"), "saida_encargos": ("Saídas", "Encargos (INSS, FGTS)"),
               "saida_impostos": ("Saídas", "Impostos"), "saida_franquia": ("Saídas", "Royalties e fundo pagos"),
               "saida_despesa": ("Saídas", "Despesas operacionais")}

        def caixa():
            linhas = []
            inicial = float(R.param("saldo_caixa_inicial"))
            for uid in ids_todos:
                t = R.fluxo_caixa_mensal(ids=[uid])
                if t.empty:
                    continue
                linhas.append(dict(Data=f"{t['competencia'].iloc[0]}-01", UnidadeID=uid, Grupo="Saldo inicial",
                                   Categoria="Saldo inicial", Ordem=0, Valor=inicial))
                for _, r in t.iterrows():
                    for i, (col, (grupo, cat)) in enumerate(ROT.items(), start=1):
                        v = float(r.get(col, 0) or 0)
                        if abs(v) > 0.005:
                            linhas.append(dict(Data=f"{r['competencia']}-01", UnidadeID=uid, Grupo=grupo,
                                               Categoria=cat, Ordem=i, Valor=round(v, 2)))
            return pd.DataFrame(linhas)
        exportar("fCaixa", caixa)

        def caixa_projetado():
            linhas = []
            for uid in ids_todos:
                saldo0, t = R.fluxo_projetado(60, ids=[uid])
                for _, r in t.iterrows():
                    linhas.append(dict(Data=r["dia"], UnidadeID=uid, AReceber=round(float(r["a_receber"]), 2),
                                       APagar=round(float(r["a_pagar"]), 2), Saldo=round(float(r["saldo"]), 2)))
            return pd.DataFrame(linhas)
        exportar("fCaixaProjetado", caixa_projetado)

        def contas_pagar():
            t = df("""SELECT unidade_id UnidadeID, origem Origem, favorecido Favorecido, data_emissao Emissao,
                             data_vencimento Vencimento, data_pagamento Pagamento, status Status, valor Valor
                      FROM contas_pagar WHERE status='ABERTO'
                         OR data_pagamento >= date(?, '-90 days')""", (ref.isoformat(),))
            venc = pd.to_datetime(t["Vencimento"])
            dias = (venc - pd.Timestamp(ref)).dt.days
            faixas = [(-10**6, -1, 1, "Vencido"), (0, 7, 2, "Até 7 dias"), (8, 30, 3, "8 a 30 dias"),
                      (31, 60, 4, "31 a 60 dias"), (61, 10**6, 5, "Mais de 60 dias")]
            t["DiasParaVencer"] = dias
            t["Faixa"] = ""; t["FaixaOrdem"] = 0
            for a, b, o, nome in faixas:
                m = (dias >= a) & (dias <= b)
                t.loc[m, "Faixa"] = nome; t.loc[m, "FaixaOrdem"] = o
            t.loc[t["Status"] == "PAGO", ["Faixa", "FaixaOrdem"]] = ["Pago", 9]
            t["Origem"] = t["Origem"].map({"COMPRA": "Fornecedores", "TRANSFERENCIA": "Transferências do CD",
                                           "DESPESA": "Despesas", "FOLHA": "Folha", "ENCARGOS": "Encargos",
                                           "IMPOSTOS": "Impostos", "FRANQUIA": "Royalties e fundo"}).fillna(t["Origem"])
            return t
        exportar("fContasPagar", contas_pagar)

        # DRE por unidade e mês (mesma regra do sistema), formato longo
        print("  fDRE                 calculando a DRE de 14 unidades...", flush=True)
        comps = [c for c in R.competencias() if c <= R.ultima_competencia_fechada()]
        linhas = []
        ordem = {k: (i + 1, rot, nivel) for i, (k, rot, nivel) in enumerate(R.LINHAS_DRE)}
        for (uid,) in [(r["id"],) for r in R.q("SELECT id FROM unidades")]:
            t = R.dre(comps, [uid]).drop(columns="Total")
            for k, serie in t.iterrows():
                o, rot, nivel = ordem[k]
                for c, v in serie.items():
                    linhas.append(dict(Data=f"{c}-01", UnidadeID=uid, Ordem=o, Chave=k, Linha=rot,
                                       Nivel=nivel, Valor=round(float(v), 2)))
        dre_df = pd.DataFrame(linhas)
        dre_df = dre_df[dre_df["Valor"] != 0]          # linhas zeradas (ex.: royalties numa loja própria) saem
        salvar(dre_df, "fDRE")
    if ERROS:
        print(f"\nTerminou com erro em: {', '.join(ERROS)}. Copie as mensagens acima e envie para análise.")
    else:
        print("\nPronto: 20 tabelas. No Power BI Desktop: Obter dados > Texto/CSV (ou Pasta) > powerbi/dados.")


if __name__ == "__main__":
    main()
