"""
Estrutura da rede Vale Verde (franquia fictícia).

Coordenadas: centros aproximados das cidades reais (as lojas ficam a poucos km do centro, em endereços fictícios).
População: aproximada (Censo IBGE 2022, arredondada). Renda per capita e nº de concorrentes: ESTIMATIVAS
ilustrativas para fins didáticos — substitua por dados oficiais do IBGE para análises reais.
"""

# nome, UF, região, lat, lon, população, renda per capita (R$/mês), supermercados concorrentes (fictício)
CIDADES = [
    # cidades com unidades da rede
    ("Campinas", "SP", "Sudeste", -22.9099, -47.0626, 1139000, 2300, 140),
    ("São Paulo", "SP", "Sudeste", -23.5505, -46.6333, 11450000, 2400, 1250),
    ("Rio de Janeiro", "RJ", "Sudeste", -22.9068, -43.1729, 6211000, 2300, 720),
    ("Belo Horizonte", "MG", "Sudeste", -19.9167, -43.9345, 2316000, 2200, 260),
    ("Curitiba", "PR", "Sul", -25.4284, -49.2733, 1773000, 2300, 210),
    ("Porto Alegre", "RS", "Sul", -30.0346, -51.2177, 1332000, 2500, 170),
    ("Goiânia", "GO", "Centro-Oeste", -16.6869, -49.2648, 1437000, 1900, 180),
    ("Salvador", "BA", "Nordeste", -12.9777, -38.5016, 2418000, 1500, 230),
    ("Recife", "PE", "Nordeste", -8.0476, -34.8770, 1488000, 1600, 160),
    ("Belém", "PA", "Norte", -1.4558, -48.4902, 1303000, 1400, 120),
    ("Hortolândia", "SP", "Sudeste", -22.8583, -47.2200, 237000, 1700, 25),
    ("Araucária", "PR", "Sul", -25.5859, -49.4047, 151000, 1800, 18),
    ("Cabo de Santo Agostinho", "PE", "Nordeste", -8.2822, -35.0253, 203000, 1000, 20),
    # candidatas à expansão
    ("Fortaleza", "CE", "Nordeste", -3.7319, -38.5267, 2428000, 1400, 240),
    ("Manaus", "AM", "Norte", -3.1190, -60.0217, 2063000, 1200, 190),
    ("Brasília", "DF", "Centro-Oeste", -15.7939, -47.8828, 2817000, 3200, 330),
    ("São Luís", "MA", "Nordeste", -2.5307, -44.3068, 1037000, 1300, 95),
    ("Maceió", "AL", "Nordeste", -9.6658, -35.7350, 957000, 1300, 90),
    ("Natal", "RN", "Nordeste", -5.7945, -35.2110, 751000, 1500, 80),
    ("Teresina", "PI", "Nordeste", -5.0920, -42.8038, 866000, 1300, 85),
    ("João Pessoa", "PB", "Nordeste", -7.1195, -34.8450, 833000, 1500, 85),
    ("Aracaju", "SE", "Nordeste", -10.9472, -37.0731, 602000, 1500, 60),
    ("Feira de Santana", "BA", "Nordeste", -12.2664, -38.9663, 616000, 1100, 55),
    ("Campo Grande", "MS", "Centro-Oeste", -20.4697, -54.6201, 898000, 1900, 95),
    ("Cuiabá", "MT", "Centro-Oeste", -15.6014, -56.0979, 650000, 1900, 70),
    ("Uberlândia", "MG", "Sudeste", -18.9186, -48.2772, 713000, 1900, 75),
    ("Juiz de Fora", "MG", "Sudeste", -21.7642, -43.3496, 540000, 1800, 60),
    ("Ribeirão Preto", "SP", "Sudeste", -21.1704, -47.8103, 698000, 2100, 80),
    ("Sorocaba", "SP", "Sudeste", -23.5015, -47.4526, 723000, 1900, 80),
    ("São José dos Campos", "SP", "Sudeste", -23.1896, -45.8841, 697000, 2200, 75),
    ("Santos", "SP", "Sudeste", -23.9608, -46.3336, 418000, 2700, 55),
    ("Niterói", "RJ", "Sudeste", -22.8832, -43.1034, 482000, 3000, 60),
    ("Vitória", "ES", "Sudeste", -20.3155, -40.3128, 323000, 3000, 45),
    ("Vila Velha", "ES", "Sudeste", -20.3297, -40.2925, 467000, 2100, 50),
    ("Florianópolis", "SC", "Sul", -27.5954, -48.5480, 537000, 2900, 70),
    ("Joinville", "SC", "Sul", -26.3045, -48.8487, 616000, 2100, 65),
    ("Londrina", "PR", "Sul", -23.3045, -51.1696, 556000, 1900, 60),
    ("Maringá", "PR", "Sul", -23.4205, -51.9333, 409000, 2200, 50),
    ("Caxias do Sul", "RS", "Sul", -29.1678, -51.1794, 463000, 2200, 55),
    ("Porto Velho", "RO", "Norte", -8.7612, -63.9004, 460000, 1400, 45),
    ("Palmas", "TO", "Norte", -10.1840, -48.3336, 302000, 1700, 35),
]

FRANQUEADOS = [
    # razão social, fantasia, sócio responsável, data contrato
    ("Tijuca Alimentos e Comércio Ltda.", "Grupo Tijuca", "Renato Albuquerque Siqueira", "2021-01-15"),
    ("Horizonte Varejo de Alimentos Ltda.", "Horizonte Varejo", "Cláudia Rezende Pacheco", "2021-06-10"),
    ("Pinhais Comércio de Alimentos Ltda.", "Pinhais Alimentos", "Marcos Wiedmann Kowalski", "2021-12-01"),
    ("Guaíba Supermercados Ltda.", "Guaíba Supermercados", "Eduardo Bertolini Fontana", "2025-04-20"),
    ("Itapuã Comércio Varejista Ltda.", "Itapuã Varejo", "Juliana Matos Conceição", "2022-05-05"),
    ("Marajó Alimentos Ltda.", "Marajó Alimentos", "Paulo Sérgio Barbalho Lobato", "2025-11-25"),
]

# Unidades: código, nome, tipo, modelo, franqueado (índice ou None), cidade, bairro (fictício), deslocamento
# do centro em km (leste, norte), área m², checkouts, inauguração, CD (código), dias de pedido ao CD,
# fator de demanda (porte), fator de preço, índice salarial, aluguel R$/m², índice de tarifa de energia
UNIDADES = [
    ("SEDE", "Sede Vale Verde Franquias", "SEDE", None, None, "Campinas", "Cambuí", (1.2, 0.8), 650, None,
     "2019-03-10", None, None, 0, 1.0, 1.0, 55.0, 1.0),
    ("CD01", "CD Sudeste/Centro-Oeste", "CD", None, None, "Hortolândia", "Distrito Industrial", (2.0, -1.5), 9000, None,
     "2019-03-01", None, None, 0, 1.0, 0.98, 16.0, 1.0),
    ("CD02", "CD Sul", "CD", None, None, "Araucária", "Polo Logístico", (-1.5, 1.0), 5000, None,
     "2022-03-01", None, None, 0, 1.0, 0.96, 14.0, 0.95),
    ("CD03", "CD Nordeste/Norte", "CD", None, None, "Cabo de Santo Agostinho", "Complexo de Suape", (3.0, -2.0), 6000, None,
     "2022-08-15", None, None, 0, 1.0, 0.86, 13.0, 1.05),
    ("VV01", "Vale Verde Campinas Taquaral", "LOJA", "PROPRIA", None, "Campinas", "Taquaral", (2.2, 2.6), 1400, 8,
     "2019-03-10", "CD01", "SEG,QUA,SEX", 1.00, 1.00, 0.98, 26.0, 1.00),
    ("VV02", "Vale Verde São Paulo Mooca", "LOJA", "PROPRIA", None, "São Paulo", "Mooca", (4.5, -1.2), 1800, 10,
     "2020-08-01", "CD01", "SEG,QUA,SEX", 1.25, 1.03, 1.05, 32.0, 1.02),
    ("VV03", "Vale Verde Rio Tijuca", "LOJA", "FRANQUIA", 0, "Rio de Janeiro", "Tijuca", (-4.8, -1.0), 1600, 9,
     "2021-05-01", "CD01", "TER,SEX", 1.15, 1.02, 1.00, 30.0, 1.12),
    ("VV04", "Vale Verde BH Savassi", "LOJA", "FRANQUIA", 1, "Belo Horizonte", "Savassi", (0.8, -1.4), 1300, 8,
     "2021-11-01", "CD01", "TER,SEX", 0.95, 0.99, 0.93, 25.0, 0.97),
    ("VV05", "Vale Verde Curitiba Água Verde", "LOJA", "FRANQUIA", 2, "Curitiba", "Água Verde", (-1.0, -2.0), 1300, 8,
     "2022-04-01", "CD02", "SEG,QUA,SEX", 0.90, 1.00, 0.97, 24.0, 0.95),
    ("VV06", "Vale Verde Porto Alegre Menino Deus", "LOJA", "FRANQUIA", 3, "Porto Alegre", "Menino Deus", (0.6, -2.4), 1200, 7,
     "2025-09-01", "CD02", "TER,SEX", 0.80, 1.01, 0.97, 24.0, 0.98),
    ("VV07", "Vale Verde Goiânia Setor Bueno", "LOJA", "PROPRIA", None, "Goiânia", "Setor Bueno", (-1.8, -1.6), 1200, 7,
     "2023-02-01", "CD01", "TER,SEX", 0.85, 0.97, 0.90, 20.0, 1.05),
    ("VV08", "Vale Verde Salvador Pituba", "LOJA", "FRANQUIA", 4, "Salvador", "Pituba", (4.0, 1.5), 1300, 8,
     "2022-10-01", "CD03", "TER,SEX", 0.90, 0.98, 0.86, 22.0, 1.04),
    ("VV09", "Vale Verde Recife Boa Viagem", "LOJA", "PROPRIA", None, "Recife", "Boa Viagem", (1.0, -5.5), 1200, 7,
     "2025-03-15", "CD03", "SEG,QUA,SEX", 0.80, 0.98, 0.86, 23.0, 1.06),
    ("VV10", "Vale Verde Belém Nazaré", "LOJA", "FRANQUIA", 5, "Belém", "Nazaré", (1.2, -0.6), 1100, 6,
     "2026-04-01", "CD03", "SEG", 0.70, 1.06, 0.85, 21.0, 1.10),
]

# Ajustes regionais de demanda: (mês -> multiplicador) por região/cidade
SAZONAL_REGIONAL = {
    "Nordeste": {6: 1.10},                      # festas juninas
    "Sul": {6: 1.03, 7: 1.04, 8: 1.02},         # inverno mais forte
    "Belém": {10: 1.15},                        # Círio de Nazaré
    "Centro-Oeste": {7: 1.03},
}
# Regiões onde produtos de inverno vendem ainda mais / menos
INVERNO_REGIONAL = {"Sul": 1.25, "Nordeste": 0.75, "Norte": 0.65, "Centro-Oeste": 0.9, "Sudeste": 1.0}
VERAO_REGIONAL = {"Sul": 0.95, "Nordeste": 1.1, "Norte": 1.15, "Centro-Oeste": 1.05, "Sudeste": 1.0}

# Fornecedores regionais de perecíveis: tipo -> (padrão de nome, prazo, dias de pedido, pedido mínimo)
REGIONAIS_TIPOS = {
    "HORTI": ("Hortifruti {n}", 7, "SEG,TER,QUA,QUI,SEX,SAB", 200),
    "PAD": ("Massas Congeladas {n}", 14, "SEG,TER,QUA,QUI,SEX,SAB", 150),
    "BOV": ("Frigorífico {n}", 14, "SEG,QUA,SEX", 1000),
    "AVES": ("Avícola {n}", 14, "TER,QUI,SAB", 500),
    "LAT": ("Laticínios {n}", 14, "SEG,QUA,SEX", 600),
    "FRIOS": ("Frios {n}", 21, "TER,SEX", 800),
}
# região -> (nomes por tipo, cidade-base, uf, lat, lon, fator de custo)
REGIONAIS = {
    "Sudeste": (dict(HORTI="Irmãos Okada (CEASA)", PAD="Trigo de Ouro", BOV="Boi Forte", AVES="Santa Clara",
                     LAT="Campo Bom", FRIOS="Serra da Mantiqueira"), "Campinas", "SP", -22.93, -47.13, 1.00),
    "Sul": (dict(HORTI="Serra Gaúcha", PAD="Pão do Sul", BOV="Pampa Carnes", AVES="Vale do Itajaí",
                 LAT="Colônia Holandesa", FRIOS="Campos Gerais"), "Ponta Grossa", "PR", -25.09, -50.16, 1.01),
    "Centro-Oeste": (dict(HORTI="Planalto Central", PAD="Cerrado Massas", BOV="Boi do Cerrado", AVES="Rio Verde",
                          LAT="Leite do Goiás", FRIOS="Planalto"), "Anápolis", "GO", -16.33, -48.95, 1.02),
    "Nordeste": (dict(HORTI="Vale do São Francisco", PAD="Massas Nordeste", BOV="Sertão Carnes", AVES="Agreste",
                      LAT="Bacia Leiteira", FRIOS="Atlântico"), "Caruaru", "PE", -8.28, -35.98, 1.03),
    "Norte": (dict(HORTI="Ver-o-Peso", PAD="Massas Amazônia", BOV="Marajó Carnes", AVES="Castanhal",
                   LAT="Laticínios do Pará", FRIOS="Amazônia Frios"), "Castanhal", "PA", -1.30, -47.93, 1.07),
}
# Fornecedores nacionais (abastecem os CDs): chave do catálogo -> (lat, lon)
NACIONAIS_COORD = {
    "MERC1": (-22.90, -47.06), "MERC2": (-23.19, -46.88), "BEB": (-22.56, -47.40), "FRIOS": (-22.82, -47.27),
    "LIMP": (-23.55, -46.63), "BAZAR": (-22.73, -47.65), "EMB": (-23.09, -47.22),
}

# Quadro de pessoal dos CDs e da sede: (cargo, departamento, salário, carga, quadro, contrato, turnover/mês)
CARGOS_CD = [
    ("Gerente de CD", "Logística (CD)", 9800, 44, 1, "CLT", 0.006),
    ("Analista de Logística", "Logística (CD)", 4300, 44, 1, "CLT", 0.012),
    ("Conferente de CD", "Logística (CD)", 2600, 44, 2, "CLT", 0.020),
    ("Operador de Empilhadeira", "Logística (CD)", 2800, 44, 2, "CLT", 0.020),
    ("Separador de Pedidos", "Logística (CD)", 2050, 44, 4, "CLT", 0.040),
]
CARGOS_SEDE = [
    ("Diretor Geral", "Franqueadora (Sede)", 32000, 44, 1, "CLT", 0.002),
    ("Gerente de Expansão", "Franqueadora (Sede)", 16000, 44, 1, "CLT", 0.006),
    ("Gerente Comercial e de Compras", "Franqueadora (Sede)", 15000, 44, 1, "CLT", 0.006),
    ("Comprador Corporativo", "Franqueadora (Sede)", 7200, 44, 2, "CLT", 0.010),
    ("Consultor de Campo", "Franqueadora (Sede)", 7800, 44, 2, "CLT", 0.012),
    ("Analista de Marketing", "Franqueadora (Sede)", 6200, 44, 1, "CLT", 0.012),
    ("Analista Financeiro", "Franqueadora (Sede)", 6500, 44, 1, "CLT", 0.010),
    ("Analista de BI", "Franqueadora (Sede)", 7500, 44, 1, "CLT", 0.012),
    ("Assistente de DP", "Franqueadora (Sede)", 3600, 44, 1, "CLT", 0.012),
]

CONCORRENTES_NOMES = [
    ("Atacarejo Max", "Atacarejo", 6000), ("Super Bom Preço", "Supermercado", 1800),
    ("Hiper Central", "Hipermercado", 9000), ("Mercado Econômico", "Supermercado", 1200),
    ("Rede Sol Supermercados", "Supermercado", 2200), ("Mercadinho do Bairro", "Mercado de bairro", 350),
    ("Empório Fresco", "Mercado de bairro", 500), ("Atacado Popular", "Atacarejo", 5500),
    ("SuperVizinho", "Supermercado", 1500), ("Mercado Família", "Mercado de bairro", 400),
]

# Rótulos fictícios de bairros ao redor de cada loja (setor angular)
SETORES = ["Norte", "Nordeste", "Leste", "Sudeste", "Sul", "Sudoeste", "Oeste", "Noroeste"]
