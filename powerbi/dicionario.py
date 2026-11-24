# -*- coding: utf-8 -*-
"""
Dicionário de dados do modelo Power BI da Rede Vale Verde.

Uma única fonte de verdade para:
  1. gerar o DICIONARIO.md (documentação para o GitHub);
  2. gravar as descrições dentro do modelo Power BI (projeto .pbip, formato TMDL);
  3. gerar um script C# para o Tabular Editor (alternativa).

Uso:
  python powerbi/dicionario.py md                      -> gera powerbi/DICIONARIO.md
  python powerbi/dicionario.py pbip "C:\\...\\Vale Verde.SemanticModel"
                                                       -> grava as descrições no projeto
  python powerbi/dicionario.py csx                     -> gera powerbi/descricoes_tabular_editor.csx
"""
import os
import re
import sys

# Descrição no nível da TABELA é copiada para a consulta do Power Query e, em algumas versões,
# provoca "referência cíclica" ao atualizar. Por isso fica desligada; ligue com --com-tabela.
COM_TABELA = "--com-tabela" in sys.argv

PASTA = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(PASTA, "dados")

U = "FK → dUnidade"
C = "FK → dCalendario"
P = "FK → dProduto"

# (coluna, tipo, chave, descrição)
TABELAS = [
    # ------------------------------------------------------------------ dimensões
    ("dCalendario", "Dimensão", "1 linha por dia (nov/2024 a dez/2026)",
     "Calendário contínuo. Deve ser marcada como tabela de datas. Filtra todas as tabelas fato pela coluna Data.", [
        ("Data", "Data", "PK", "Dia do calendário."),
        ("Ano", "Inteiro", "", "Ano civil (2024 a 2026)."),
        ("MesNum", "Inteiro", "", "Número do mês (1 a 12). Use para ordenar a coluna Mes."),
        ("Mes", "Texto", "", "Mês abreviado (jan, fev...). Ordenar por MesNum."),
        ("AnoMes", "Texto", "", "Ano e mês no formato aaaa-mm; ordena corretamente em ordem alfabética."),
        ("MesAno", "Texto", "", "Rótulo curto para gráficos (nov/24). Ordenar por IndiceMes."),
        ("Trimestre", "Texto", "", "Ano e trimestre (2025 T1)."),
        ("DiaSemanaNum", "Inteiro", "", "Dia da semana, 1 = segunda ... 7 = domingo. Use para ordenar DiaSemana."),
        ("DiaSemana", "Texto", "", "Dia da semana abreviado (seg, ter...). Ordenar por DiaSemanaNum."),
        ("Dia", "Inteiro", "", "Dia do mês (1 a 31)."),
        ("FimDeSemana", "Inteiro 0/1", "", "1 se sábado ou domingo."),
        ("LojaFechada", "Inteiro 0/1", "", "1 em 25/12 e 01/01, dias em que as lojas não abrem."),
        ("IndiceMes", "Inteiro", "", "Sequência dos meses desde nov/2024 (0, 1, 2...). Útil para ordenar e para tendência."),
    ]),
    ("dUnidade", "Dimensão", "1 linha por unidade (sede, 3 CDs e 10 lojas)",
     "Cadastro das unidades da rede. É a dimensão central do modelo: filtra todas as fatos por UnidadeID.", [
        ("UnidadeID", "Inteiro", "PK", "Identificador da unidade."),
        ("Codigo", "Texto", "", "Código curto: SEDE, CD01 a CD03, VV01 a VV10."),
        ("Unidade", "Texto", "", "Nome da unidade."),
        ("Tipo", "Texto", "", "SEDE, CD (centro de distribuição) ou LOJA."),
        ("Modelo", "Texto", "", "PROPRIA (loja da rede), FRANQUIA (loja de franqueado) ou FRANQUEADORA (sede e CDs)."),
        ("Cidade", "Texto", "FK → dCidade", "Município da unidade. Pode ligar em dCidade[Cidade] (opcional)."),
        ("UF", "Texto", "", "Sigla do estado."),
        ("Regiao", "Texto", "", "Região do Brasil (Sudeste, Sul, Nordeste, Centro-Oeste, Norte)."),
        ("Latitude", "Decimal", "", "Latitude da unidade, para mapas. Não resumir."),
        ("Longitude", "Decimal", "", "Longitude da unidade, para mapas. Não resumir."),
        ("AreaM2", "Inteiro", "", "Área de vendas (lojas) ou área construída (CDs e sede), em m²."),
        ("Checkouts", "Inteiro", "", "Quantidade de caixas (PDVs) da loja. Vazio para sede e CDs."),
        ("Inauguracao", "Data", "", "Data de abertura. Lojas inauguradas no período: VV09 (mar/25), VV06 (set/25), VV10 (abr/26)."),
        ("CD", "Texto", "", "Código do CD que abastece a loja. Vazio para sede e CDs."),
        ("DistanciaCDkm", "Decimal", "", "Distância rodoviária estimada entre a loja e o seu CD, em km."),
        ("LeadTimeCD", "Inteiro", "", "Dias entre o envio pelo CD e a chegada na loja."),
        ("Franqueado", "Texto", "", "Nome do grupo franqueado. Vazio para lojas próprias."),
        ("FatorPreco", "Decimal", "", "Multiplicador de preço da praça em relação à tabela da rede (1,03 = 3% acima)."),
    ]),
    ("dProduto", "Dimensão", "1 linha por produto (SKU)",
     "Catálogo de produtos de revenda e de uso interno.", [
        ("ProdutoID", "Inteiro", "PK", "Identificador do produto."),
        ("SKU", "Texto", "", "Código interno do produto (6 dígitos, os 2 primeiros indicam a categoria)."),
        ("Produto", "Texto", "", "Descrição completa do produto."),
        ("Marca", "Texto", "", "Marca do fabricante. \"Vale Verde\" é a marca própria."),
        ("Categoria", "Texto", "", "Departamento do produto (Mercearia, Bebidas, Açougue...)."),
        ("Canal", "Texto", "", "Como chega à loja: CD (via centro de distribuição) ou DIRETO (fornecedor regional entrega na loja)."),
        ("Perecivel", "Inteiro 0/1", "", "1 para açougue, hortifrúti, padaria e frios."),
        ("Revenda", "Inteiro 0/1", "", "1 se o item é vendido ao cliente; 0 para itens de uso interno (sacolas, bobinas, limpeza)."),
        ("Medida", "Texto", "", "Unidade de venda: UN, KG, PCT ou CX."),
        ("ValidadeDias", "Inteiro", "", "Prazo de validade típico, em dias."),
        ("Sazonalidade", "Texto", "", "Época de pico de venda: NATAL, PASCOA, QUARESMA, INVERNO, VERAO, PANETONE, FDS. Vazio se não tem."),
        ("MarcaPropria", "Inteiro 0/1", "", "1 se for produto da marca própria Vale Verde."),
    ]),
    ("dCidade", "Dimensão", "1 linha por município (com loja ou candidato)",
     "Municípios com unidades e cidades candidatas à expansão. Base dos mapas de mercado e do modelo de expansão.", [
        ("CidadeID", "Inteiro", "PK", "Identificador do município."),
        ("Cidade", "Texto", "", "Nome do município."),
        ("UF", "Texto", "", "Sigla do estado."),
        ("Regiao", "Texto", "", "Região do Brasil."),
        ("Latitude", "Decimal", "", "Latitude do centro da cidade. Não resumir."),
        ("Longitude", "Decimal", "", "Longitude do centro da cidade. Não resumir."),
        ("Populacao", "Inteiro", "", "População aproximada (habitantes)."),
        ("RendaPerCapita", "Decimal", "", "Renda mensal per capita ilustrativa, em R$."),
        ("Concorrentes", "Inteiro", "", "Quantidade estimada de supermercados concorrentes no município."),
        ("Situacao", "Texto", "", "Com loja, CD/Sede (só unidade de apoio) ou Candidata (alvo de expansão)."),
    ]),
    ("dFornecedor", "Dimensão", "1 linha por fornecedor",
     "Fornecedores nacionais (abastecem os CDs) e regionais (entregam perecíveis direto nas lojas).", [
        ("FornecedorID", "Inteiro", "PK", "Identificador do fornecedor."),
        ("Fornecedor", "Texto", "", "Nome fantasia."),
        ("Abrangencia", "Texto", "", "NACIONAL (vende para os CDs) ou REGIONAL (vende para as lojas de uma região)."),
        ("RegiaoAtendida", "Texto", "", "Região que o fornecedor atende; Nacional para os de abrangência nacional."),
        ("Tipo", "Texto", "", "Linha de produtos: MERC (mercearia), BEB, FRIOS, LAT, LIMP, BAZAR, EMB, HORTI, PAD, BOV, AVES."),
        ("Cidade", "Texto", "", "Cidade de origem do fornecedor."),
        ("UF", "Texto", "", "Estado de origem."),
        ("Latitude", "Decimal", "", "Latitude do fornecedor. Não resumir."),
        ("Longitude", "Decimal", "", "Longitude do fornecedor. Não resumir."),
        ("PrazoPagamento", "Inteiro", "", "Prazo médio de pagamento negociado, em dias."),
    ]),
    ("dCliente", "Dimensão", "1 linha por cliente do programa de fidelidade",
     "Clientes cadastrados, com localização aproximada de residência. Usada nos mapas de área de influência.", [
        ("ClienteID", "Inteiro", "PK", "Identificador do cliente. Não resumir."),
        ("UnidadeID", "Inteiro", U, "Loja de referência do cliente (onde se cadastrou)."),
        ("Sexo", "Texto", "", "M ou F."),
        ("Bairro", "Texto", "", "Bairro de residência (fictício), com a zona da cidade entre parênteses."),
        ("Latitude", "Decimal", "", "Latitude aproximada da residência. Não resumir."),
        ("Longitude", "Decimal", "", "Longitude aproximada da residência. Não resumir."),
        ("DistanciaKm", "Decimal", "", "Distância em linha reta entre a residência e a loja, em km."),
        ("FaixaDistancia", "Texto", "", "Faixa da distância: 0-1 km, 1-3 km, 3-5 km, 5+ km."),
        ("Cadastro", "Data", "", "Data de adesão ao programa de fidelidade."),
        ("Compras6m", "Inteiro", "", "Compras identificadas nos últimos 6 meses (período com cupons detalhados)."),
        ("Valor6m", "Decimal", "", "Valor gasto nos últimos 6 meses, em R$. Vazio se não comprou."),
    ]),
    # ------------------------------------------------------------------ fatos
    ("fVendas", "Fato", "1 linha por loja × dia × produto",
     "Vendas diárias por produto (24 meses). Use para mix, curva ABC, margem por categoria. Para faturamento total prefira fCupons, que inclui descontos.", [
        ("UnidadeID", "Inteiro", U, "Loja que vendeu."),
        ("Data", "Data", C, "Dia da venda."),
        ("ProdutoID", "Inteiro", P, "Produto vendido."),
        ("Quantidade", "Decimal", "", "Quantidade vendida na unidade de medida do produto (UN, KG...)."),
        ("Receita", "Decimal", "", "Valor vendido, em R$ (preço praticado × quantidade)."),
        ("CMV", "Decimal", "", "Custo da mercadoria vendida, em R$, pelo custo médio ponderado do estoque."),
    ]),
    ("fCupons", "Fato", "1 linha por loja × dia × forma de pagamento",
     "Resumo diário dos cupons fiscais. Fonte oficial do faturamento, ticket médio e fluxo de clientes.", [
        ("UnidadeID", "Inteiro", U, "Loja."),
        ("Data", "Data", C, "Dia das vendas."),
        ("FormaPagamento", "Texto", "", "CREDITO, DEBITO, PIX, DINHEIRO ou VOUCHER (vale-alimentação)."),
        ("Cupons", "Inteiro", "", "Quantidade de cupons (compras). Base do ticket médio e do fluxo."),
        ("Itens", "Inteiro", "", "Itens registrados nos cupons."),
        ("ValorBruto", "Decimal", "", "Valor antes dos descontos, em R$."),
        ("Desconto", "Decimal", "", "Descontos concedidos no caixa, em R$."),
        ("Receita", "Decimal", "", "Valor pago pelo cliente (ValorBruto − Desconto), em R$."),
        ("CMV", "Decimal", "", "Custo das mercadorias desses cupons, em R$."),
        ("CuponsFidelidade", "Inteiro", "", "Cupons em que o cliente se identificou no programa de fidelidade."),
    ]),
    ("fTransferencias", "Fato", "1 linha por transferência (CD → loja)",
     "Abastecimento das lojas pelos CDs. A relação por CDID fica inativa e é ligada nas medidas de visão do CD (USERELATIONSHIP).", [
        ("TransferenciaID", "Inteiro", "PK", "Número da transferência. Não resumir."),
        ("CDID", "Inteiro", U + " (inativa)", "CD que enviou a mercadoria."),
        ("UnidadeID", "Inteiro", U, "Loja que recebeu."),
        ("Data", "Data", C, "Data de envio pelo CD."),
        ("DataRecebimento", "Data", "", "Data em que a loja recebeu. Vazio se ainda em trânsito."),
        ("Status", "Texto", "", "RECEBIDA, RECEBIDA_PARCIAL ou EM_TRANSITO."),
        ("CustoCD", "Decimal", "", "Custo da mercadoria para o CD, em R$."),
        ("ValorTransferencia", "Decimal", "", "Valor cobrado da loja (custo de referência + 1%), em R$. A diferença para CustoCD é a margem do CD."),
        ("DistanciaKm", "Decimal", "", "Distância rodoviária CD → loja, em km."),
        ("Viagens", "Inteiro", "", "Caminhões necessários (até R$ 150 mil de carga por viagem)."),
        ("Frete", "Decimal", "", "Custo do frete, em R$ (R$ 400 por viagem + R$ 3,80 por km)."),
        ("LeadTimeDias", "Decimal", "", "Dias entre envio e recebimento."),
    ]),
    ("fCompras", "Fato", "1 linha por pedido de compra",
     "Pedidos a fornecedores: dos CDs (itens de mercearia, com 6% de desconto por volume) e das lojas (perecíveis direto do fornecedor regional).", [
        ("PedidoID", "Inteiro", "PK", "Número do pedido. Não resumir."),
        ("UnidadeID", "Inteiro", U, "Unidade compradora (CD ou loja)."),
        ("FornecedorID", "Inteiro", "FK → dFornecedor", "Fornecedor."),
        ("Data", "Data", C, "Data do pedido."),
        ("DataRecebimento", "Data", "", "Data de entrega. Vazio se o pedido está aberto."),
        ("Status", "Texto", "", "RECEBIDO, RECEBIDO_PARCIAL ou ABERTO."),
        ("Valor", "Decimal", "", "Valor total do pedido, em R$."),
        ("DistanciaKm", "Decimal", "", "Distância fornecedor → unidade, em km."),
        ("LeadTimeDias", "Decimal", "", "Dias entre pedido e entrega."),
    ]),
    ("fPerdas", "Fato", "1 linha por movimento de saída sem venda",
     "Quebras, consumo interno e ajustes de inventário (valorizados a custo).", [
        ("UnidadeID", "Inteiro", U, "Unidade onde ocorreu."),
        ("Data", "Data", C, "Dia do registro."),
        ("ProdutoID", "Inteiro", P, "Produto."),
        ("Tipo", "Texto", "", "PERDA (quebra), CONSUMO_INTERNO (uso pela própria loja) ou AJUSTE_INVENTARIO (diferença de contagem)."),
        ("Motivo", "Texto", "", "Motivo detalhado (Vencimento, Avaria, Furto/desvio, Copa/refeitório...)."),
        ("Quantidade", "Decimal", "", "Quantidade baixada (positiva). Em ajuste de inventário pode ser negativa, quando sobrou produto."),
        ("Valor", "Decimal", "", "Valor a custo, em R$."),
    ]),
    ("fRupturas", "Fato", "1 linha por loja × dia × produto em falta",
     "Dias em que faltou produto na gôndola e a demanda não foi atendida.", [
        ("UnidadeID", "Inteiro", U, "Loja."),
        ("Data", "Data", C, "Dia da falta."),
        ("ProdutoID", "Inteiro", P, "Produto em falta."),
        ("QtdNaoAtendida", "Decimal", "", "Quantidade que os clientes teriam comprado."),
        ("VendaPerdida", "Decimal", "", "Venda perdida estimada, em R$ (quantidade × preço)."),
    ]),
    ("fFolha", "Fato", "1 linha por unidade × mês × cargo",
     "Folha de pagamento mensal agregada por cargo. Data é sempre o 1º dia do mês de competência.", [
        ("Data", "Data", C, "Competência (1º dia do mês)."),
        ("UnidadeID", "Inteiro", U, "Unidade onde o funcionário trabalha."),
        ("Cargo", "Texto", "", "Cargo."),
        ("Departamento", "Texto", "", "Setor (Frente de Caixa, Açougue, Logística (CD), Franqueadora (Sede)...)."),
        ("Funcionarios", "Inteiro", "", "Funcionários pagos no mês nesse cargo (headcount)."),
        ("SalarioBruto", "Decimal", "", "Salários brutos, em R$."),
        ("HorasExtras", "Decimal", "", "Horas extras com reflexo no DSR, em R$."),
        ("Encargos", "Decimal", "", "INSS patronal e FGTS, em R$."),
        ("Beneficios", "Decimal", "", "Vale-alimentação e vale-transporte (líquido do desconto do funcionário), em R$."),
        ("Provisoes", "Decimal", "", "Provisões de 13º e férias com encargos, em R$."),
        ("CustoTotal", "Decimal", "", "Custo total para a empresa, em R$ (soma das colunas de custo)."),
    ]),
    ("fDespesas", "Fato", "1 linha por unidade × mês × categoria de despesa",
     "Despesas operacionais lançadas por competência. Data é o 1º dia do mês.", [
        ("Data", "Data", C, "Competência (1º dia do mês)."),
        ("UnidadeID", "Inteiro", U, "Unidade que teve a despesa."),
        ("Categoria", "Texto", "", "Categoria da despesa (Aluguel, Energia elétrica, Taxas de cartão...)."),
        ("Tipo", "Texto", "", "FIXA (não varia com as vendas) ou VARIAVEL. Base do ponto de equilíbrio."),
        ("GrupoDRE", "Texto", "", "Linha da DRE onde a despesa entra: OCUPACAO, UTILIDADES, ADMINISTRATIVA, COMERCIAL, PESSOAL, LOGISTICA, FRANQUIA, DEPRECIACAO, FINANCEIRA."),
        ("Valor", "Decimal", "", "Valor da despesa, em R$."),
    ]),
    ("fReceitasFranquia", "Fato", "1 linha por loja franqueada × mês × tipo",
     "O que as franquias pagam à franqueadora.", [
        ("Data", "Data", C, "Competência (1º dia do mês)."),
        ("UnidadeID", "Inteiro", U, "Loja franqueada que paga."),
        ("Tipo", "Texto", "", "ROYALTIES (1,5% do faturamento), FUNDO_MARKETING (0,5%) ou TAXA_FRANQUIA (R$ 180 mil na abertura)."),
        ("Base", "Decimal", "", "Faturamento da loja usado no cálculo, em R$. Vazio na taxa de franquia."),
        ("Valor", "Decimal", "", "Valor devido, em R$."),
        ("Status", "Texto", "", "RECEBIDO ou ABERTO."),
    ]),
    ("fDRE", "Fato", "1 linha por unidade × mês × linha da DRE",
     "DRE gerencial já calculada, em formato longo. Deduções vêm negativas. Atenção: a tabela tem linhas de detalhe e de subtotal; "
     "nunca some a coluna Valor sem filtrar a linha (use a medida DRE Valor ou filtre Chave/Nivel).", [
        ("Data", "Data", C, "Competência (1º dia do mês)."),
        ("UnidadeID", "Inteiro", U, "Unidade. Royalties e margem dos CDs aparecem como receita da franqueadora e custo das lojas."),
        ("Ordem", "Inteiro", "", "Posição da linha na DRE (1 a 25). Use para ordenar Linha."),
        ("Chave", "Texto", "", "Código fixo da linha (receita_bruta, cmv, ebitda, lucro_liquido...). Use nas medidas DAX."),
        ("Linha", "Texto", "", "Descrição da linha como aparece no relatório. Ordenar por Ordem."),
        ("Nivel", "Inteiro", "", "0 = receita bruta, 1 = linha de detalhe (+/−), 2 = subtotal (=), 3 = lucro líquido. Use para formatação condicional."),
        ("Valor", "Decimal", "", "Valor da linha, em R$. Receitas e subtotais positivos, deduções negativas."),
    ]),
]


# --------------------------------------------------------------------------- utilidades
def _amostra(tabela):
    """Lê o CSV (se existir) para contar linhas e pegar exemplos."""
    caminho = os.path.join(DADOS, tabela + ".csv")
    if not os.path.exists(caminho):
        return None, {}
    try:
        import pandas as pd
        d = pd.read_csv(caminho, sep=";", decimal=",", encoding="utf-8-sig", low_memory=False)
    except Exception:
        return None, {}
    ex = {}
    for c in d.columns:
        s = d[c].dropna()
        s = s[s.astype(str).str.strip() != ""]
        if s.empty:
            ex[c] = ""
            continue
        if d[c].dtype == object and s.nunique() <= 6:
            ex[c] = ", ".join(map(str, sorted(s.unique())))
        else:
            v = s.iloc[len(s) // 2]
            if isinstance(v, float):
                v = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                v = v[:-3] if v.endswith(",00") else v
            ex[c] = str(v)
    return len(d), ex


def _fmt_int(n):
    return f"{n:,}".replace(",", ".")


# --------------------------------------------------------------------------- 1. Markdown
def gerar_md():
    out = ["# Dicionário de dados: modelo Power BI da Rede Vale Verde", "",
           "Modelo em estrela com **6 dimensões** e **10 fatos**, exportado do sistema por "
           "`powerbi/exportar_powerbi.py`. Todos os dados são fictícios.", "",
           "Convenções:", "",
           "- Tabelas começadas por `d` são dimensões (o \"quem/onde/o quê\") e por `f` são fatos (os eventos e valores).",
           "- Valores monetários em reais (R$). Colunas `Data` de tabelas mensais trazem o 1º dia do mês de competência.",
           "- **PK** = chave da dimensão; **FK** = coluna que liga a fato à dimensão (relação muitos-para-um, filtro em direção única).",
           "- IDs, latitudes e longitudes devem ficar com *Resumir por = Nenhum*.", "",
           "## Índice", ""]
    for nome, tipo, grao, desc, cols in TABELAS:
        out.append(f"- [`{nome}`](#{nome.lower()}): {tipo.lower()}, {grao}")
    out += ["", "## Relacionamentos", "", "| Tabela | Coluna | Dimensão | Observação |", "|---|---|---|---|"]
    for nome, tipo, grao, desc, cols in TABELAS:
        for col, t, chave, d in cols:
            if chave.startswith("FK"):
                dim = chave.replace("FK → ", "").replace(" (inativa)", "")
                obs = "inativa (USERELATIONSHIP)" if "inativa" in chave else ("opcional" if dim == "dCidade" else "")
                ligacao = "Data" if dim == "dCalendario" else ("Cidade" if dim == "dCidade" else dim.replace("d", "", 1) + "ID")
                out.append(f"| `{nome}` | `{col}` | `{dim}[{ligacao}]` | {obs} |")
    for nome, tipo, grao, desc, cols in TABELAS:
        n, ex = _amostra(nome)
        out += ["", f"## {nome}", "", f"**{tipo}** · {grao}" + (f" · {_fmt_int(n)} linhas" if n else ""), "", desc, "",
                "| Coluna | Tipo | Chave | Descrição | Exemplo |", "|---|---|---|---|---|"]
        for col, t, chave, d in cols:
            e = ex.get(col, "").replace("|", "/")
            out.append(f"| `{col}` | {t} | {chave} | {d} | {e} |")
    out += ["", "---", "", "Gerado por `powerbi/dicionario.py md`. Para atualizar, edite as descrições no script e rode de novo.", ""]
    destino = os.path.join(PASTA, "DICIONARIO.md")
    with open(destino, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("Gerado:", destino)


# --------------------------------------------------------------------------- 2. Projeto .pbip (TMDL)
def _nome_tmdl(nome):
    return nome if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", nome) else "'" + nome.replace("'", "''") + "'"


def _aplicar_em_arquivo(caminho, tabela, desc_tabela, desc_colunas):
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        texto = f.read()
    nl = "\r\n" if "\r\n" in texto else "\n"
    linhas = texto.replace("\r\n", "\n").split("\n")
    novas, i, feitas = [], 0, 0
    alvo_tab = re.compile(r"^table\s+(.+?)\s*$")
    alvo_col = re.compile(r"^(\t+|\s+)column\s+('(?:[^']|'')+'|[^\s=]+)")
    while i < len(linhas):
        ln = linhas[i]
        m_t = alvo_tab.match(ln)
        m_c = alvo_col.match(ln)
        if m_t or m_c:
            # remove descrições antigas (linhas /// imediatamente acima)
            while novas and novas[-1].lstrip().startswith("///"):
                novas.pop()
            if m_t:
                if desc_tabela:
                    novas.append(f"/// {desc_tabela}")
                    feitas += 1
            else:
                indent = m_c.group(1)
                col = m_c.group(2).strip("'").replace("''", "'")
                if col in desc_colunas:
                    novas.append(f"{indent}/// {desc_colunas[col]}")
                    feitas += 1
        novas.append(ln)
        i += 1
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        f.write(nl.join(novas))
    return feitas


def aplicar_pbip(pasta_modelo):
    pasta_modelo = pasta_modelo.strip('"')
    tabelas_dir = os.path.join(pasta_modelo, "definition", "tables")
    if not os.path.isdir(tabelas_dir):
        print("Não encontrei", tabelas_dir)
        print("Informe a pasta que termina em .SemanticModel (ela tem definition\\tables dentro).")
        print("Se não houver a pasta definition, ative o formato TMDL: Opções > Recursos de visualização >")
        print("'Armazenar o modelo semântico usando o formato TMDL' e salve o projeto de novo.")
        sys.exit(1)
    total = 0
    for nome, tipo, grao, desc, cols in TABELAS:
        arq = os.path.join(tabelas_dir, nome + ".tmdl")
        if not os.path.exists(arq):
            print(f"  {nome:20s} não encontrada no projeto (ignorada)")
            continue
        desc_tab = f"{tipo} · {grao}. {desc}" if COM_TABELA else None
        n = _aplicar_em_arquivo(arq, nome, desc_tab, {c[0]: c[3] for c in cols})
        total += n
        print(f"  {nome:20s} {n} descrições")
    print(f"Pronto: {total} descrições gravadas. Abra o .pbip no Power BI Desktop.")


# --------------------------------------------------------------------------- 3. Tabular Editor
def gerar_csx():
    def s(t):
        return '"' + t.replace("\\", "\\\\").replace('"', '\\"') + '"'
    out = ["// Script C# para o Tabular Editor 2 (gratuito): Advanced Scripting > colar > Run (F5) > Ctrl+S.",
           "// Gerado por powerbi/dicionario.py csx",
           "Action<string, string, string> D = (t, c, d) => {",
           "    if (!Model.Tables.Contains(t)) return;",
           "    if (c == null) { Model.Tables[t].Description = d; return; }",
           "    if (Model.Tables[t].Columns.Contains(c)) Model.Tables[t].Columns[c].Description = d;",
           "};", ""]
    for nome, tipo, grao, desc, cols in TABELAS:
        out.append(f"D({s(nome)}, null, {s(f'{tipo} · {grao}. {desc}')});")
        for col, t, chave, d in cols:
            out.append(f"D({s(nome)}, {s(col)}, {s(d)});")
    destino = os.path.join(PASTA, "descricoes_tabular_editor.csx")
    with open(destino, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("Gerado:", destino)


if __name__ == "__main__":
    acao = sys.argv[1] if len(sys.argv) > 1 else "md"
    if acao == "md":
        gerar_md()
    elif acao == "pbip" and len(sys.argv) > 2:
        aplicar_pbip(sys.argv[2])
    elif acao == "csx":
        gerar_csx()
    else:
        print(__doc__)
