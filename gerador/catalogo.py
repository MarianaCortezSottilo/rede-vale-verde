"""
Cadastros-base da empresa fictícia (todas as marcas, pessoas e empresas são inventadas).
Custos de referência: novembro/2024, em R$.
"""

EMPRESA = dict(
    razao_social="Vale Verde Franquias e Participações S.A.",
    nome_fantasia="Rede Vale Verde Supermercados",
    cnpj="00.000.000/0001-91 (fictício)",
    cidade="Campinas",
    uf="SP",
    regime_tributario="Lucro Real (simplificado)",
    fundacao="2019-03-10",
)

PARAMETROS = [
    ("aliq_icms_efetiva", 0.045, "ICMS efetivo líquido sobre a receita bruta (média do mix)"),
    ("aliq_pis_cofins_efetiva", 0.015, "PIS/COFINS não cumulativo líquido de créditos"),
    ("aliq_ir_csll", 0.34, "IRPJ + CSLL sobre lucro tributável (Lucro Real)"),
    ("mdr_debito", 0.009, "Taxa da maquininha - débito"),
    ("mdr_credito", 0.024, "Taxa da maquininha - crédito à vista"),
    ("mdr_voucher", 0.055, "Taxa de vale-alimentação/refeição"),
    ("mdr_pix", 0.0, "PIX (sem taxa)"),
    ("prazo_receb_debito", 1, "Dias para receber vendas no débito"),
    ("prazo_receb_credito", 30, "Dias para receber vendas no crédito"),
    ("prazo_receb_voucher", 30, "Dias para receber vendas em voucher"),
    ("encargo_inss_patronal", 0.278, "INSS patronal 20% + RAT 2% + terceiros 5,8%"),
    ("encargo_fgts", 0.08, "FGTS"),
    ("vale_alimentacao", 350.0, "Vale-alimentação mensal por funcionário (R$)"),
    ("vale_transporte_custo", 220.0, "Custo mensal bruto do VT por funcionário (R$)"),
    ("saldo_caixa_inicial", 450000.0, "Caixa + bancos por loja em 01/11/2024 (R$, referência)"),
    ("royalties_pct", 0.015, "Royalties mensais sobre a receita bruta das lojas franqueadas"),
    ("fundo_marketing_pct", 0.005, "Fundo de marketing da rede (lojas franqueadas)"),
    ("taxa_franquia", 180000.0, "Taxa inicial de franquia (R$)"),
    ("desconto_compra_cd", 0.06, "Desconto obtido pela compra centralizada nos CDs (sobre custo de referência)"),
    ("markup_transferencia", 0.01, "Preço de transferência CD->loja = custo de referência x (1 + markup)"),
    ("frete_fixo_viagem", 400.0, "Custo fixo por viagem de caminhão (R$)"),
    ("frete_por_km", 3.8, "Custo variável de frete por km rodado (R$)"),
    ("valor_por_viagem", 150000.0, "Valor máximo de mercadoria por viagem (capacidade da carreta, R$)"),
    ("prazo_transferencia_franquia", 21, "Prazo para o franqueado pagar as transferências do CD (dias)"),
    ("aliq_impostos_servicos", 0.1425, "ISS + PIS/COFINS sobre royalties e serviços da franqueadora"),
    ("fator_estrada", 1.25, "Distância rodoviária = distância em linha reta x fator"),
]

DEPARTAMENTOS = [
    ("Gerência", "ADMINISTRATIVO"),
    ("Administrativo/Financeiro", "ADMINISTRATIVO"),
    ("Frente de Caixa", "OPERACIONAL"),
    ("Mercearia/Reposição", "OPERACIONAL"),
    ("Açougue", "OPERACIONAL"),
    ("Padaria", "OPERACIONAL"),
    ("Hortifrúti", "OPERACIONAL"),
    ("Recebimento/Depósito", "OPERACIONAL"),
    ("Prevenção de Perdas", "OPERACIONAL"),
    ("Limpeza", "OPERACIONAL"),
    ("Logística (CD)", "OPERACIONAL"),
    ("Franqueadora (Sede)", "ADMINISTRATIVO"),
]

# (cargo, departamento, salário nov/24, carga semanal, quadro, tipo_contrato, turnover mensal)
CARGOS = [
    ("Gerente Geral", "Gerência", 10500, 44, 1, "CLT", 0.004),
    ("Subgerente", "Gerência", 5800, 44, 1, "CLT", 0.008),
    ("Comprador", "Administrativo/Financeiro", 4600, 44, 1, "CLT", 0.010),
    ("Assistente Financeiro", "Administrativo/Financeiro", 2900, 44, 1, "CLT", 0.015),
    ("Assistente de DP/RH", "Administrativo/Financeiro", 3200, 44, 1, "CLT", 0.012),
    ("Jovem Aprendiz", "Administrativo/Financeiro", 760, 20, 1, "JOVEM_APRENDIZ", 0.020),
    ("Fiscal de Caixa", "Frente de Caixa", 2350, 44, 2, "CLT", 0.020),
    ("Operador de Caixa", "Frente de Caixa", 1980, 44, 10, "CLT", 0.045),
    ("Empacotador", "Frente de Caixa", 1530, 44, 3, "CLT", 0.060),
    ("Encarregado de Mercearia", "Mercearia/Reposição", 3300, 44, 1, "CLT", 0.010),
    ("Repositor", "Mercearia/Reposição", 1950, 44, 6, "CLT", 0.040),
    ("Açougueiro", "Açougue", 3100, 44, 2, "CLT", 0.015),
    ("Auxiliar de Açougue", "Açougue", 2050, 44, 2, "CLT", 0.030),
    ("Padeiro", "Padaria", 2800, 44, 2, "CLT", 0.015),
    ("Atendente de Padaria", "Padaria", 1950, 44, 2, "CLT", 0.035),
    ("Encarregado de Hortifrúti", "Hortifrúti", 3000, 44, 1, "CLT", 0.010),
    ("Auxiliar de Hortifrúti", "Hortifrúti", 1900, 44, 2, "CLT", 0.035),
    ("Conferente", "Recebimento/Depósito", 2450, 44, 1, "CLT", 0.015),
    ("Auxiliar de Depósito", "Recebimento/Depósito", 1900, 44, 1, "CLT", 0.030),
    ("Fiscal de Prevenção", "Prevenção de Perdas", 2250, 44, 2, "CLT", 0.025),
    ("Auxiliar de Limpeza", "Limpeza", 1780, 44, 2, "CLT", 0.030),
]

# Categoria: (nome, departamento responsável, margem alvo sobre preço, perecível, revenda, taxa de perda diária sobre estoque)
CATEGORIAS = [
    ("Mercearia", "Mercearia/Reposição", 0.28, 0, 1, 0.0006),
    ("Bebidas", "Mercearia/Reposição", 0.29, 0, 1, 0.0006),
    ("Laticínios e Frios", "Mercearia/Reposição", 0.28, 1, 1, 0.0050),
    ("Açougue", "Açougue", 0.32, 1, 1, 0.0110),
    ("Hortifrúti", "Hortifrúti", 0.42, 1, 1, 0.0300),
    ("Padaria", "Padaria", 0.55, 1, 1, 0.0550),
    ("Limpeza", "Mercearia/Reposição", 0.30, 0, 1, 0.0006),
    ("Higiene e Perfumaria", "Mercearia/Reposição", 0.34, 0, 1, 0.0010),
    ("Congelados", "Mercearia/Reposição", 0.30, 0, 1, 0.0008),
    ("Bazar e Pet", "Mercearia/Reposição", 0.36, 0, 1, 0.0006),
    ("Uso Interno", "Recebimento/Depósito", 0.0, 0, 0, 0.0),
]

# Fornecedores: chave -> dados
FORNECEDORES = {
    "MERC1": ("Distribuidora Paulista de Alimentos Ltda.", "Dist. Paulista", "Campinas", "SP", 28, 3, "SEG,QUI", 1500),
    "MERC2": ("Atacado Real Distribuidora S.A.", "Atacado Real", "Jundiaí", "SP", 35, 4, "TER", 2500),
    "BEB": ("Serra Azul Distribuidora de Bebidas Ltda.", "Serra Azul Bebidas", "Limeira", "SP", 21, 2, "TER,SEX", 1200),
    "LAT": ("Laticínios Campo Bom Ltda.", "Campo Bom", "Poços de Caldas", "MG", 14, 2, "SEG,QUA,SEX", 600),
    "FRIOS": ("Polar Frios e Congelados Ltda.", "Polar Distribuidora", "Sumaré", "SP", 21, 2, "TER,SEX", 800),
    "BOV": ("Frigorífico Boi Forte Ltda.", "Boi Forte", "Araçatuba", "SP", 14, 1, "SEG,QUA,SEX", 1000),
    "AVES": ("Avícola Santa Clara Ltda.", "Avícola Santa Clara", "Amparo", "SP", 14, 1, "TER,QUI,SAB", 500),
    "HORTI": ("Hortifruti Irmãos Okada ME", "Irmãos Okada (CEASA)", "Campinas", "SP", 7, 1, "SEG,TER,QUA,QUI,SEX,SAB", 200),
    "PAD": ("Trigo de Ouro Massas Congeladas Ltda.", "Trigo de Ouro", "Valinhos", "SP", 14, 1, "SEG,TER,QUA,QUI,SEX,SAB", 150),
    "LIMP": ("Nova Era Higiene e Limpeza Ltda.", "Nova Era", "São Paulo", "SP", 28, 4, "QUA", 1000),
    "BAZAR": ("Comercial Andrade Bazar e Pet Ltda.", "Andrade Bazar & Pet", "Piracicaba", "SP", 30, 5, "SEG", 600),
    "EMB": ("Vale Pack Embalagens Ltda.", "Vale Pack", "Indaiatuba", "SP", 28, 5, "QUI", 300),
}

MARCAS = {
    "merc": ["Bom Grão", "Tio Nino", "Vale Verde"],
    "refri": ["Serra Azul", "Tropical", "Vale Verde"],
    "cerveja": ["Lúpulo Dourado", "Cevada Nobre", "Serra Fria"],
    "lat": ["Campo Bom", "Leiteria Mineira", "Vale Verde"],
    "limp": ["Brilhante", "Lar Limpo", "Vale Verde"],
    "hig": ["Suavità", "Bem-Estar", "Vale Verde"],
    "cong": ["Polar", "Sabor de Casa"],
    "pet": ["Amigo Fiel", "Casa & Cia"],
}
# multiplicador de custo e de popularidade por posição da marca
MARCA_CUSTO = [1.00, 1.15, 0.88]
MARCA_POP = [1.00, 0.60, 0.55]

# Modo de quantidade por item vendido:
#   'u'  -> quase sempre 1 unidade      'm' -> 1 a 6 unidades
#   'c'  -> cerveja (1, 2, 6, 12...)    'l' -> leite (1, 2, 6, 12)
#   'k0.8' -> produto pesado, peso médio de 0,8 kg
# Tupla: (descrição, unidade, custo, giro relativo, modo qtd, validade dias, sazonalidade, marcas, fornecedor, embalagem de compra)
PRODUTOS = {
    "Mercearia": [
        ("Arroz Branco Tipo 1 5kg", "UN", 22.00, 10, "u", 365, None, "merc", "MERC1", 10),
        ("Feijão Carioca 1kg", "UN", 6.20, 9, "m", 270, None, "merc", "MERC1", 10),
        ("Feijão Preto 1kg", "UN", 6.80, 4, "u", 270, "INVERNO", "merc", "MERC1", 10),
        ("Açúcar Refinado 1kg", "UN", 3.90, 7, "m", 540, None, "merc", "MERC1", 10),
        ("Café Torrado e Moído 500g", "UN", 17.50, 8, "u", 180, None, "merc", "MERC1", 10),
        ("Óleo de Soja 900ml", "UN", 5.90, 8, "m", 365, None, "merc", "MERC2", 20),
        ("Macarrão Espaguete 500g", "UN", 3.40, 7, "m", 365, "INVERNO", "merc", "MERC2", 20),
        ("Macarrão Parafuso 500g", "UN", 3.60, 5, "m", 365, None, "merc", "MERC2", 20),
        ("Farinha de Trigo 1kg", "UN", 4.30, 4, "u", 180, None, "merc", "MERC1", 10),
        ("Molho de Tomate Sachê 300g", "UN", 1.90, 7, "m", 365, None, "merc", "MERC2", 24),
        ("Extrato de Tomate 340g", "UN", 3.60, 3, "u", 540, None, "merc", "MERC2", 24),
        ("Sal Refinado 1kg", "UN", 1.60, 3, "u", 900, None, "merc", "MERC1", 10),
        ("Milho Verde Lata 170g", "UN", 2.60, 3, "m", 720, None, "merc", "MERC2", 24),
        ("Sardinha em Lata 125g", "UN", 4.30, 3, "m", 720, None, "merc", "MERC2", 24),
        ("Biscoito Recheado 130g", "UN", 2.10, 7, "m", 240, None, "merc", "MERC2", 30),
        ("Biscoito Cream Cracker 350g", "UN", 4.20, 4, "u", 240, None, "merc", "MERC2", 20),
        ("Achocolatado em Pó 400g", "UN", 6.90, 4, "u", 365, "INVERNO", "merc", "MERC1", 12),
        ("Leite Condensado 395g", "UN", 5.30, 5, "m", 365, "NATAL", "merc", "MERC1", 24),
        ("Creme de Leite 200g", "UN", 2.90, 5, "m", 270, "NATAL", "merc", "MERC1", 24),
        ("Maionese 500g", "UN", 7.60, 3, "u", 240, "VERAO", "merc", "MERC2", 12),
        ("Cereal Matinal 300g", "UN", 9.80, 2, "u", 270, None, "merc", "MERC2", 12),
        ("Farofa Pronta 400g", "UN", 4.10, 2, "u", 240, "VERAO", "merc", "MERC2", 20),
        ("Tempero Completo 300g", "UN", 3.30, 2, "u", 365, None, "merc", "MERC2", 12),
        ("Azeite de Oliva Extra Virgem 500ml", "UN", 32.00, 2, "u", 540, "NATAL", "merc", "MERC1", 12),
        ("Fubá Mimoso 1kg", "UN", 3.00, 2, "u", 180, "INVERNO", "merc", "MERC1", 10),
        ("Aveia em Flocos 200g", "UN", 3.80, 2, "u", 270, None, "merc", "MERC1", 12),
        ("Chocolate em Barra 90g", "UN", 5.20, 4, "m", 270, "INVERNO", "merc", "MERC2", 20),
        ("Ovo de Páscoa ao Leite 200g", "UN", 32.00, 3, "u", 180, "PASCOA", None, "MERC2", 6),
        ("Panetone Frutas 500g", "UN", 14.00, 4, "u", 120, "PANETONE", None, "MERC2", 6),
    ],
    "Bebidas": [
        ("Refrigerante Cola 2L", "UN", 6.40, 10, "m", 180, "VERAO", "refri", "BEB", 6),
        ("Refrigerante Guaraná 2L", "UN", 5.20, 7, "m", 180, "VERAO", "refri", "BEB", 6),
        ("Água Mineral sem Gás 1,5L", "UN", 1.40, 6, "m", 365, "VERAO", "refri", "BEB", 6),
        ("Água Mineral sem Gás 500ml", "UN", 0.90, 4, "m", 365, "VERAO", None, "BEB", 12),
        ("Suco Integral Caixinha 1L", "UN", 4.60, 4, "m", 270, "VERAO", "refri", "BEB", 12),
        ("Refresco em Pó 25g", "UN", 0.70, 3, "m", 365, "VERAO", None, "BEB", 15),
        ("Cerveja Lata 350ml", "UN", 2.90, 12, "c", 180, "VERAO", "cerveja", "BEB", 12),
        ("Cerveja Long Neck 330ml", "UN", 3.90, 4, "c", 180, "VERAO", "cerveja", "BEB", 24),
        ("Cerveja Pack 12 Latas 350ml", "UN", 33.00, 4, "u", 180, "VERAO", "cerveja", "BEB", 2),
        ("Vinho Tinto Seco 750ml", "UN", 21.00, 2, "u", 1000, "INVERNO", None, "MERC2", 6),
        ("Energético Lata 250ml", "UN", 6.00, 2, "m", 365, None, None, "BEB", 6),
        ("Água de Coco 1L", "UN", 6.50, 2, "u", 180, "VERAO", None, "BEB", 12),
    ],
    "Laticínios e Frios": [
        ("Leite UHT Integral 1L", "UN", 4.30, 14, "l", 120, None, "lat", "LAT", 12),
        ("Leite UHT Desnatado 1L", "UN", 4.50, 4, "l", 120, None, "lat", "LAT", 12),
        ("Iogurte Natural 170g", "UN", 2.30, 4, "m", 30, None, "lat", "LAT", 12),
        ("Bebida Láctea Morango 900g", "UN", 5.40, 4, "u", 30, None, "lat", "LAT", 12),
        ("Queijo Mussarela Fatiado", "KG", 34.00, 5, "k0.35", 20, None, None, "FRIOS", 1),
        ("Presunto Cozido Fatiado", "KG", 24.00, 5, "k0.30", 15, None, None, "FRIOS", 1),
        ("Manteiga com Sal 200g", "UN", 11.00, 3, "u", 90, None, "lat", "LAT", 12),
        ("Margarina 500g", "UN", 6.20, 5, "u", 120, None, "lat", "LAT", 12),
        ("Requeijão Cremoso 200g", "UN", 5.80, 4, "u", 60, None, "lat", "LAT", 12),
        ("Queijo Minas Frescal", "KG", 32.00, 2, "k0.45", 15, None, None, "LAT", 1),
        ("Ovos Brancos Dúzia", "UN", 8.50, 8, "u", 25, "PASCOA", None, "AVES", 30),
        ("Salsicha Hot Dog", "KG", 12.50, 3, "k0.5", 30, None, None, "FRIOS", 1),
        ("Mortadela Fatiada", "KG", 16.00, 3, "k0.3", 15, None, None, "FRIOS", 1),
        ("Peito de Peru Defumado Fatiado", "KG", 52.00, 2, "k0.2", 15, "NATAL", None, "FRIOS", 1),
    ],
    "Açougue": [
        ("Carne Moída Patinho", "KG", 34.00, 6, "k0.8", 4, None, None, "BOV", 5),
        ("Alcatra Bovina", "KG", 42.00, 4, "k1.0", 5, "FDS", None, "BOV", 5),
        ("Picanha Bovina", "KG", 68.00, 1.5, "k1.2", 5, "FDS", None, "BOV", 5),
        ("Contrafilé Bovino", "KG", 45.00, 3, "k1.0", 5, "FDS", None, "BOV", 5),
        ("Acém Bovino", "KG", 30.00, 4, "k1.0", 5, "INVERNO", None, "BOV", 5),
        ("Costela Bovina", "KG", 24.00, 3, "k1.8", 5, "FDS", None, "BOV", 5),
        ("Peito de Frango", "KG", 15.00, 7, "k1.2", 5, None, None, "AVES", 5),
        ("Coxa e Sobrecoxa de Frango", "KG", 11.00, 6, "k1.3", 5, "FDS", None, "AVES", 5),
        ("Frango Inteiro Congelado", "KG", 10.00, 3, "k2.4", 180, None, None, "AVES", 10),
        ("Linguiça Toscana", "KG", 17.00, 5, "k1.0", 10, "FDS", None, "AVES", 5),
        ("Bisteca Suína", "KG", 19.00, 3, "k1.0", 5, None, None, "AVES", 5),
        ("Pernil Suíno", "KG", 18.00, 2, "k2.5", 5, "NATAL", None, "AVES", 5),
    ],
    "Hortifrúti": [
        ("Banana Prata", "KG", 3.60, 10, "k1.3", 6, None, None, "HORTI", 10),
        ("Tomate Italiano", "KG", 4.50, 9, "k1.0", 6, None, None, "HORTI", 10),
        ("Batata Lavada", "KG", 3.80, 8, "k1.5", 15, None, None, "HORTI", 10),
        ("Cebola", "KG", 3.40, 7, "k0.9", 20, None, None, "HORTI", 10),
        ("Alho Nacional", "KG", 18.00, 2, "k0.2", 30, None, None, "HORTI", 2),
        ("Cenoura", "KG", 3.20, 4, "k0.7", 12, None, None, "HORTI", 5),
        ("Maçã Gala", "KG", 7.50, 5, "k1.0", 20, None, None, "HORTI", 10),
        ("Laranja Pera", "KG", 2.90, 5, "k2.5", 15, "INVERNO", None, "HORTI", 20),
        ("Limão Tahiti", "KG", 3.00, 4, "k0.6", 15, "VERAO", None, "HORTI", 10),
        ("Mamão Formosa", "KG", 4.20, 3, "k1.8", 6, None, None, "HORTI", 10),
        ("Melancia", "KG", 1.60, 3, "k6.0", 10, "VERAO", None, "HORTI", 20),
        ("Uva Niágara", "KG", 9.00, 2, "k0.8", 6, "NATAL", None, "HORTI", 5),
        ("Alface Crespa", "UN", 1.60, 5, "u", 3, None, None, "HORTI", 12),
        ("Abobrinha", "KG", 3.50, 2, "k0.6", 8, None, None, "HORTI", 5),
        ("Pimentão Verde", "KG", 6.00, 2, "k0.3", 8, None, None, "HORTI", 5),
    ],
    "Padaria": [
        ("Pão Francês", "KG", 6.50, 16, "k0.45", 1, None, None, "PAD", 10),
        ("Pão de Queijo", "KG", 18.00, 3, "k0.3", 2, None, None, "PAD", 5),
        ("Bolo Caseiro Fubá", "UN", 7.50, 3, "u", 4, "INVERNO", None, "PAD", 6),
        ("Pão de Forma Tradicional 500g", "UN", 5.60, 5, "u", 10, None, None, "PAD", 10),
        ("Rosca Doce", "UN", 5.00, 2, "u", 3, None, None, "PAD", 6),
        ("Sonho de Creme", "UN", 1.80, 2, "m", 2, None, None, "PAD", 12),
    ],
    "Limpeza": [
        ("Detergente Líquido 500ml", "UN", 1.90, 7, "m", 720, None, "limp", "LIMP", 24),
        ("Sabão em Pó 1,6kg", "UN", 14.50, 4, "u", 720, None, "limp", "LIMP", 9),
        ("Lava-Roupas Líquido 3L", "UN", 26.00, 2, "u", 720, None, "limp", "LIMP", 6),
        ("Amaciante 2L", "UN", 9.80, 4, "u", 720, None, "limp", "LIMP", 6),
        ("Água Sanitária 2L", "UN", 4.20, 4, "u", 180, None, "limp", "LIMP", 6),
        ("Desinfetante 2L", "UN", 6.40, 3, "u", 720, None, "limp", "LIMP", 6),
        ("Esponja Multiuso 3un", "UN", 2.80, 3, "u", 1000, None, None, "LIMP", 20),
        ("Saco de Lixo 50L 10un", "UN", 5.40, 3, "u", 1000, None, None, "LIMP", 20),
    ],
    "Higiene e Perfumaria": [
        ("Papel Higiênico 12 Rolos", "UN", 15.50, 6, "u", 1000, None, "hig", "LIMP", 4),
        ("Sabonete em Barra 85g", "UN", 1.80, 6, "m", 1000, None, "hig", "LIMP", 12),
        ("Creme Dental 90g", "UN", 3.60, 5, "m", 720, None, "hig", "LIMP", 12),
        ("Shampoo 350ml", "UN", 10.50, 3, "u", 720, None, "hig", "LIMP", 12),
        ("Condicionador 350ml", "UN", 11.00, 2, "u", 720, None, "hig", "LIMP", 12),
        ("Desodorante Aerossol 150ml", "UN", 11.50, 3, "u", 720, "VERAO", "hig", "LIMP", 12),
        ("Fralda Descartável Pacote", "UN", 38.00, 2, "u", 1000, None, None, "LIMP", 4),
        ("Absorvente com Abas 8un", "UN", 4.60, 2, "u", 1000, None, None, "LIMP", 12),
    ],
    "Congelados": [
        ("Pizza Congelada Mussarela 460g", "UN", 12.50, 3, "u", 180, None, "cong", "FRIOS", 8),
        ("Lasanha Congelada Bolonhesa 600g", "UN", 13.00, 3, "u", 180, "INVERNO", "cong", "FRIOS", 8),
        ("Hambúrguer Bovino 672g", "UN", 14.00, 2, "u", 180, "VERAO", "cong", "FRIOS", 8),
        ("Batata Pré-Frita 1kg", "UN", 13.50, 2, "u", 365, None, None, "FRIOS", 8),
        ("Sorvete Napolitano 2L", "UN", 15.00, 3, "u", 365, "VERAO", None, "FRIOS", 6),
        ("Pão de Alho Congelado 400g", "UN", 9.00, 2, "u", 180, "FDS", None, "FRIOS", 10),
    ],
    "Bazar e Pet": [
        ("Ração para Cães Adultos 10kg", "UN", 72.00, 0.8, "u", 365, None, "pet", "BAZAR", 2),
        ("Ração para Gatos 1kg", "UN", 13.00, 1.2, "u", 365, None, "pet", "BAZAR", 10),
        ("Carvão Vegetal 3kg", "UN", 11.50, 3, "u", 1000, "FDS", None, "BAZAR", 10),
        ("Pilha Alcalina AA 2un", "UN", 7.50, 1, "u", 1000, "NATAL", None, "BAZAR", 12),
        ("Fósforo 10 Caixas", "UN", 3.60, 1, "u", 1000, None, None, "BAZAR", 10),
        ("Copo Descartável 200ml 100un", "UN", 4.60, 2, "u", 1000, "NATAL", None, "BAZAR", 20),
    ],
    # Materiais comprados para uso da própria loja (não vendidos)
    # (descrição, unidade, custo, -, -, validade, -, -, fornecedor, embalagem, consumo-base)
    "Uso Interno": [
        ("Sacola Plástica Reciclada (pct 1000un)", "PCT", 85.00, 0, None, None, None, None, "EMB", 5),
        ("Bobina Térmica PDV 80mm (cx 30 rolos)", "CX", 110.00, 0, None, None, None, None, "EMB", 1),
        ("Bandeja de Isopor (pct 400un)", "PCT", 72.00, 0, None, None, None, None, "EMB", 2),
        ("Filme PVC 28cm x 300m", "UN", 48.00, 0, None, None, None, None, "EMB", 4),
        ("Saco para Pão Kraft (pct 1000un)", "PCT", 42.00, 0, None, None, None, None, "EMB", 4),
        ("Etiqueta para Balança (cx 12 rolos)", "CX", 96.00, 0, None, None, None, None, "EMB", 1),
        ("Detergente Profissional 5L", "UN", 28.00, 0, None, None, None, None, "LIMP", 4),
        ("Desinfetante Profissional 5L", "UN", 26.00, 0, None, None, None, None, "LIMP", 4),
        ("Papel Toalha Interfolha (cx 1000 fls)", "CX", 18.00, 0, None, None, None, None, "LIMP", 4),
        ("Luva Descartável (cx 100un)", "CX", 24.00, 0, None, None, None, None, "EMB", 4),
    ],
}

# Inflação mensal média de custo por categoria (aprox. 2025-26) e volatilidade
INFLACAO_CATEGORIA = {
    "Mercearia": (0.0035, 0.008),
    "Bebidas": (0.0040, 0.006),
    "Laticínios e Frios": (0.0040, 0.012),
    "Açougue": (0.0055, 0.020),
    "Hortifrúti": (0.0040, 0.060),
    "Padaria": (0.0040, 0.008),
    "Limpeza": (0.0030, 0.006),
    "Higiene e Perfumaria": (0.0035, 0.006),
    "Congelados": (0.0035, 0.008),
    "Bazar e Pet": (0.0030, 0.006),
    "Uso Interno": (0.0035, 0.006),
}

NOMES_M = ["José", "João", "Antônio", "Francisco", "Carlos", "Paulo", "Pedro", "Lucas", "Luiz", "Marcos",
           "Luis", "Gabriel", "Rafael", "Daniel", "Marcelo", "Bruno", "Eduardo", "Felipe", "Raimundo", "Rodrigo",
           "Matheus", "André", "Fernando", "Fábio", "Leonardo", "Gustavo", "Guilherme", "Leandro", "Tiago", "Diego",
           "Vinícius", "Renato", "Ricardo", "Juliano", "Henrique", "Caio", "Igor", "Otávio", "Murilo", "Samuel"]
NOMES_F = ["Maria", "Ana", "Francisca", "Antônia", "Adriana", "Juliana", "Márcia", "Fernanda", "Patrícia", "Aline",
           "Sandra", "Camila", "Amanda", "Bruna", "Jéssica", "Letícia", "Júlia", "Luciana", "Vanessa", "Mariana",
           "Gabriela", "Vera", "Vitória", "Larissa", "Cláudia", "Beatriz", "Rita", "Luana", "Débora", "Renata",
           "Simone", "Tatiane", "Priscila", "Carla", "Daniela", "Natália", "Raquel", "Isabela", "Elaine", "Roberta"]
SOBRENOMES = ["Silva", "Santos", "Oliveira", "Souza", "Rodrigues", "Ferreira", "Alves", "Pereira", "Lima", "Gomes",
              "Costa", "Ribeiro", "Martins", "Carvalho", "Almeida", "Lopes", "Soares", "Fernandes", "Vieira", "Barbosa",
              "Rocha", "Dias", "Nascimento", "Andrade", "Moreira", "Nunes", "Marques", "Machado", "Mendes", "Freitas",
              "Cardoso", "Ramos", "Gonçalves", "Santana", "Teixeira", "Moraes", "Pinto", "Cavalcanti", "Campos", "Prado"]
BAIRROS = ["Centro", "Jardim das Flores", "Vila Nova", "Parque Industrial", "Jardim Primavera", "Vila Esperança",
           "Residencial Bela Vista", "Jardim São Bento", "Vila Operária", "Chácara Recreio", "Jardim Alvorada",
           "Parque dos Ipês", "Vila Santa Rita", "Loteamento Boa Vista"]

# Feriados (loja fechada em 25/12 e 01/01; demais funcionam em horário de domingo)
FERIADOS_FECHADO = ["2024-12-25", "2025-01-01", "2025-12-25", "2026-01-01"]
FERIADOS_DOMINGO = ["2024-11-15", "2024-11-20", "2025-03-04", "2025-04-18", "2025-04-21", "2025-05-01",
                    "2025-06-19", "2025-09-07", "2025-10-12", "2025-11-02", "2025-11-15", "2025-11-20",
                    "2026-02-17", "2026-04-03", "2026-04-21", "2026-05-01", "2026-06-04", "2026-09-07",
                    "2026-10-12"]
# Véspera de grandes datas (movimento muito acima do normal)
DATAS_PICO = {"2024-12-23": 1.6, "2024-12-24": 2.0, "2024-12-30": 1.5, "2024-12-31": 1.7,
              "2025-12-23": 1.6, "2025-12-24": 2.0, "2025-12-30": 1.5, "2025-12-31": 1.7,
              "2025-04-17": 1.35, "2025-04-19": 1.4, "2026-04-02": 1.35, "2026-04-04": 1.4,
              "2025-05-10": 1.2, "2026-05-09": 1.2, "2025-08-09": 1.15, "2026-08-08": 1.15}
PASCOA = {2025: "2025-04-20", 2026: "2026-04-05"}
