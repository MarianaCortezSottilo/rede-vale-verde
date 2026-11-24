-- =====================================================================
--  Rede Vale Verde (franquia fictícia) — esquema do banco SQLite
--  Sede (franqueadora) + 3 centros de distribuição + 10 lojas
-- =====================================================================
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- Franqueadora, parâmetros e geografia
-- ---------------------------------------------------------------------
CREATE TABLE empresa (               -- a franqueadora
    id              INTEGER PRIMARY KEY,
    razao_social    TEXT NOT NULL,
    nome_fantasia   TEXT NOT NULL,
    cnpj            TEXT NOT NULL,
    cidade          TEXT NOT NULL,
    uf              TEXT NOT NULL,
    regime_tributario TEXT NOT NULL,
    fundacao        TEXT
);

CREATE TABLE parametros (
    chave       TEXT PRIMARY KEY,
    valor       REAL NOT NULL,
    descricao   TEXT
);

-- Cidades com loja e cidades candidatas à expansão (dados socioeconômicos aproximados)
CREATE TABLE cidades (
    id                  INTEGER PRIMARY KEY,
    nome                TEXT NOT NULL,
    uf                  TEXT NOT NULL,
    regiao              TEXT NOT NULL CHECK (regiao IN ('Norte','Nordeste','Centro-Oeste','Sudeste','Sul')),
    lat                 REAL NOT NULL,
    lon                 REAL NOT NULL,
    populacao           INTEGER NOT NULL,
    renda_per_capita    REAL NOT NULL,       -- R$/mês, estimativa
    supermercados_concorrentes INTEGER NOT NULL,  -- fictício
    UNIQUE (nome, uf)
);

CREATE TABLE franqueados (
    id              INTEGER PRIMARY KEY,
    razao_social    TEXT NOT NULL,
    nome_fantasia   TEXT NOT NULL,
    cnpj            TEXT NOT NULL,
    socio_responsavel TEXT NOT NULL,
    telefone        TEXT,
    data_contrato   TEXT NOT NULL,
    taxa_franquia   REAL NOT NULL
);

-- Unidades da rede: sede, centros de distribuição e lojas
CREATE TABLE unidades (
    id              INTEGER PRIMARY KEY,
    codigo          TEXT NOT NULL UNIQUE,           -- VV01, CD01, SEDE
    nome            TEXT NOT NULL,
    tipo            TEXT NOT NULL CHECK (tipo IN ('LOJA','CD','SEDE')),
    modelo          TEXT CHECK (modelo IN ('PROPRIA','FRANQUIA')),
    franqueado_id   INTEGER REFERENCES franqueados(id),
    cidade_id       INTEGER NOT NULL REFERENCES cidades(id),
    bairro          TEXT,
    endereco        TEXT,
    lat             REAL NOT NULL,
    lon             REAL NOT NULL,
    area_m2         INTEGER,
    checkouts       INTEGER,
    data_inauguracao TEXT NOT NULL,
    cd_id           INTEGER REFERENCES unidades(id), -- CD que abastece a loja
    distancia_cd_km REAL,                            -- rodoviária estimada
    lead_time_cd_dias INTEGER,
    dias_pedido_cd  TEXT,
    fator_preco     REAL DEFAULT 1.0,
    status          TEXT NOT NULL DEFAULT 'ATIVA'
);

-- Concorrentes mapeados ao redor das lojas (fictícios)
CREATE TABLE concorrentes (
    id          INTEGER PRIMARY KEY,
    nome        TEXT NOT NULL,
    formato     TEXT NOT NULL,      -- Atacarejo, Hipermercado, Supermercado, Mercado de bairro
    cidade_id   INTEGER NOT NULL REFERENCES cidades(id),
    loja_referencia_id INTEGER REFERENCES unidades(id),
    lat         REAL NOT NULL,
    lon         REAL NOT NULL,
    area_m2     INTEGER,
    distancia_km REAL
);

-- ---------------------------------------------------------------------
-- RH
-- ---------------------------------------------------------------------
CREATE TABLE departamentos (
    id      INTEGER PRIMARY KEY,
    nome    TEXT NOT NULL UNIQUE,
    tipo    TEXT NOT NULL CHECK (tipo IN ('OPERACIONAL','ADMINISTRATIVO'))
);

CREATE TABLE cargos (
    id                  INTEGER PRIMARY KEY,
    nome                TEXT NOT NULL UNIQUE,
    departamento_id     INTEGER NOT NULL REFERENCES departamentos(id),
    salario_base        REAL NOT NULL,          -- referência Campinas, nov/2024
    carga_horaria_sem   INTEGER NOT NULL,
    quadro_ideal        INTEGER NOT NULL,       -- loja-padrão (ou unidade-padrão)
    tipo_unidade        TEXT NOT NULL CHECK (tipo_unidade IN ('LOJA','CD','SEDE'))
);

CREATE TABLE funcionarios (
    id              INTEGER PRIMARY KEY,
    matricula       TEXT NOT NULL UNIQUE,
    nome            TEXT NOT NULL,
    cpf             TEXT NOT NULL,
    data_nascimento TEXT,
    sexo            TEXT,
    unidade_id      INTEGER NOT NULL REFERENCES unidades(id),
    cargo_id        INTEGER NOT NULL REFERENCES cargos(id),
    tipo_contrato   TEXT NOT NULL CHECK (tipo_contrato IN ('CLT','JOVEM_APRENDIZ','ESTAGIO','TEMPORARIO')),
    turno           TEXT NOT NULL CHECK (turno IN ('MANHA','TARDE','COMERCIAL')),
    salario_admissao REAL NOT NULL,
    data_admissao   TEXT NOT NULL,
    data_demissao   TEXT,
    motivo_desligamento TEXT,
    usa_vale_transporte INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE historico_salarial (
    id              INTEGER PRIMARY KEY,
    funcionario_id  INTEGER NOT NULL REFERENCES funcionarios(id),
    data_inicio     TEXT NOT NULL,
    salario         REAL NOT NULL,
    motivo          TEXT NOT NULL
);

CREATE TABLE escalas (
    id              INTEGER PRIMARY KEY,
    funcionario_id  INTEGER NOT NULL REFERENCES funcionarios(id),
    data            TEXT NOT NULL,
    tipo            TEXT NOT NULL CHECK (tipo IN ('TRABALHO','FOLGA','FERIAS','ATESTADO','FALTA')),
    hora_inicio     TEXT,
    hora_fim        TEXT,
    UNIQUE (funcionario_id, data)
);

CREATE TABLE folha_pagamento (
    id                  INTEGER PRIMARY KEY,
    competencia         TEXT NOT NULL,
    unidade_id          INTEGER NOT NULL REFERENCES unidades(id),
    funcionario_id      INTEGER NOT NULL REFERENCES funcionarios(id),
    dias_trabalhados    INTEGER NOT NULL,
    salario_base        REAL NOT NULL,
    horas_extras_qtd    REAL NOT NULL DEFAULT 0,
    horas_extras_valor  REAL NOT NULL DEFAULT 0,
    dsr_horas_extras    REAL NOT NULL DEFAULT 0,
    verbas_rescisorias  REAL NOT NULL DEFAULT 0,
    salario_bruto       REAL NOT NULL,
    inss_funcionario    REAL NOT NULL,
    irrf                REAL NOT NULL,
    desconto_vt         REAL NOT NULL,
    salario_liquido     REAL NOT NULL,
    fgts                REAL NOT NULL,
    inss_patronal       REAL NOT NULL,
    vale_alimentacao    REAL NOT NULL,
    vale_transporte_custo REAL NOT NULL,
    provisao_13         REAL NOT NULL,
    provisao_ferias     REAL NOT NULL,
    encargos_provisoes  REAL NOT NULL,
    custo_total         REAL NOT NULL,
    UNIQUE (competencia, funcionario_id)
);

-- ---------------------------------------------------------------------
-- Cadastros comerciais
-- ---------------------------------------------------------------------
CREATE TABLE categorias (
    id              INTEGER PRIMARY KEY,
    nome            TEXT NOT NULL UNIQUE,
    departamento_id INTEGER REFERENCES departamentos(id),
    margem_alvo     REAL NOT NULL,
    perecivel       INTEGER NOT NULL DEFAULT 0,
    revenda         INTEGER NOT NULL DEFAULT 1,
    canal           TEXT NOT NULL CHECK (canal IN ('CD','DIRETO'))   -- como chega à loja
);

CREATE TABLE fornecedores (
    id                  INTEGER PRIMARY KEY,
    razao_social        TEXT NOT NULL,
    nome_fantasia       TEXT NOT NULL,
    cnpj                TEXT NOT NULL,
    abrangencia         TEXT NOT NULL CHECK (abrangencia IN ('NACIONAL','REGIONAL')),
    regiao_atendida     TEXT,                       -- para regionais
    cidade              TEXT,
    uf                  TEXT,
    lat                 REAL,
    lon                 REAL,
    telefone            TEXT,
    prazo_pagamento_dias INTEGER NOT NULL,
    dias_pedido         TEXT NOT NULL,
    pedido_minimo       REAL NOT NULL DEFAULT 0,
    fator_custo         REAL NOT NULL DEFAULT 1.0,  -- custo relativo ao preço de referência nacional
    tipo                TEXT NOT NULL               -- chave do tipo de fornecimento (MERC1, HORTI, BOV...)
);

CREATE TABLE produtos (
    id              INTEGER PRIMARY KEY,
    sku             TEXT NOT NULL UNIQUE,
    ean             TEXT,
    descricao       TEXT NOT NULL,
    marca           TEXT,
    categoria_id    INTEGER NOT NULL REFERENCES categorias(id),
    fornecedor_id   INTEGER NOT NULL REFERENCES fornecedores(id),  -- nacional (CD) ou regional Sudeste (direto)
    tipo_fornecedor TEXT NOT NULL,      -- chave do tipo (HORTI, BOV...) para achar o regional de cada loja
    unidade         TEXT NOT NULL CHECK (unidade IN ('UN','KG','PCT','CX')),
    embalagem_compra REAL NOT NULL DEFAULT 1,
    custo_atual     REAL NOT NULL,      -- custo de referência nacional
    preco_atual     REAL,               -- preço de referência (cada loja aplica seu fator)
    validade_dias   INTEGER,
    sazonalidade    TEXT,
    ativo           INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE historico_precos (
    id          INTEGER PRIMARY KEY,
    produto_id  INTEGER NOT NULL REFERENCES produtos(id),
    competencia TEXT NOT NULL,
    custo       REAL NOT NULL,
    preco       REAL,
    UNIQUE (produto_id, competencia)
);

CREATE TABLE promocoes (               -- encarte nacional da rede
    id                  INTEGER PRIMARY KEY,
    produto_id          INTEGER NOT NULL REFERENCES produtos(id),
    data_inicio         TEXT NOT NULL,
    data_fim            TEXT NOT NULL,
    preco_normal        REAL NOT NULL,
    preco_promocional   REAL NOT NULL,
    campanha            TEXT
);

CREATE TABLE clientes (
    id              INTEGER PRIMARY KEY,
    unidade_id      INTEGER NOT NULL REFERENCES unidades(id),   -- loja de referência
    nome            TEXT NOT NULL,
    cpf             TEXT NOT NULL,
    data_nascimento TEXT,
    sexo            TEXT,
    bairro          TEXT,
    lat             REAL,
    lon             REAL,
    distancia_km    REAL,
    data_cadastro   TEXT NOT NULL
);

-- ---------------------------------------------------------------------
-- Vendas
-- ---------------------------------------------------------------------
CREATE TABLE vendas (                  -- cupons (histórico recente; ver resumo para os 24 meses)
    id              INTEGER PRIMARY KEY,
    unidade_id      INTEGER NOT NULL REFERENCES unidades(id),
    data            TEXT NOT NULL,
    hora            TEXT NOT NULL,
    pdv             INTEGER NOT NULL,
    operador_id     INTEGER REFERENCES funcionarios(id),
    cliente_id      INTEGER REFERENCES clientes(id),
    forma_pagamento TEXT NOT NULL CHECK (forma_pagamento IN ('DINHEIRO','DEBITO','CREDITO','PIX','VOUCHER')),
    qtd_itens       INTEGER NOT NULL,
    valor_bruto     REAL NOT NULL,
    desconto        REAL NOT NULL DEFAULT 0,
    valor_total     REAL NOT NULL,
    custo_total     REAL NOT NULL,
    status          TEXT NOT NULL DEFAULT 'CONCLUIDA' CHECK (status IN ('CONCLUIDA','CANCELADA'))
);

CREATE TABLE itens_venda (
    id              INTEGER PRIMARY KEY,
    venda_id        INTEGER NOT NULL REFERENCES vendas(id),
    produto_id      INTEGER NOT NULL REFERENCES produtos(id),
    quantidade      REAL NOT NULL,
    preco_unitario  REAL NOT NULL,
    custo_unitario  REAL NOT NULL,
    em_promocao     INTEGER NOT NULL DEFAULT 0,
    valor_total     REAL NOT NULL
);

-- Resumos diários (24 meses completos; base de DRE, projeções e mapas)
CREATE TABLE resumo_vendas_diario (
    unidade_id  INTEGER NOT NULL REFERENCES unidades(id),
    data        TEXT NOT NULL,
    produto_id  INTEGER NOT NULL REFERENCES produtos(id),
    quantidade  REAL NOT NULL,
    receita     REAL NOT NULL,
    custo       REAL NOT NULL,
    PRIMARY KEY (unidade_id, data, produto_id)
) WITHOUT ROWID;

CREATE TABLE resumo_cupons_diario (
    unidade_id      INTEGER NOT NULL REFERENCES unidades(id),
    data            TEXT NOT NULL,
    forma_pagamento TEXT NOT NULL,
    cupons          INTEGER NOT NULL,
    itens           INTEGER NOT NULL,
    valor_bruto     REAL NOT NULL,
    desconto        REAL NOT NULL,
    valor_total     REAL NOT NULL,
    custo_total     REAL NOT NULL,
    cupons_fidelidade INTEGER NOT NULL,
    PRIMARY KEY (unidade_id, data, forma_pagamento)
) WITHOUT ROWID;

-- ---------------------------------------------------------------------
-- Suprimentos
-- ---------------------------------------------------------------------
CREATE TABLE pedidos_compra (
    id                  INTEGER PRIMARY KEY,
    unidade_id          INTEGER NOT NULL REFERENCES unidades(id),   -- CD ou loja (perecíveis)
    fornecedor_id       INTEGER NOT NULL REFERENCES fornecedores(id),
    comprador_id        INTEGER REFERENCES funcionarios(id),
    data_pedido         TEXT NOT NULL,
    data_prevista       TEXT NOT NULL,
    data_recebimento    TEXT,
    status              TEXT NOT NULL CHECK (status IN ('ABERTO','RECEBIDO','RECEBIDO_PARCIAL','CANCELADO')),
    nota_fiscal         TEXT,
    valor_total         REAL NOT NULL,
    prazo_pagamento_dias INTEGER NOT NULL,
    distancia_km        REAL
);

CREATE TABLE itens_compra (
    id                  INTEGER PRIMARY KEY,
    pedido_id           INTEGER NOT NULL REFERENCES pedidos_compra(id),
    produto_id          INTEGER NOT NULL REFERENCES produtos(id),
    quantidade_pedida   REAL NOT NULL,
    quantidade_recebida REAL,
    custo_unitario      REAL NOT NULL,
    valor_total         REAL NOT NULL
);

-- Transferências CD -> loja (preço de transferência = custo de referência x fator)
CREATE TABLE transferencias (
    id                  INTEGER PRIMARY KEY,
    cd_id               INTEGER NOT NULL REFERENCES unidades(id),
    loja_id             INTEGER NOT NULL REFERENCES unidades(id),
    data_pedido         TEXT NOT NULL,
    data_envio          TEXT NOT NULL,
    data_recebimento    TEXT,
    status              TEXT NOT NULL CHECK (status IN ('EM_TRANSITO','RECEBIDA','RECEBIDA_PARCIAL')),
    valor_custo_cd      REAL NOT NULL,      -- quanto a mercadoria custou ao CD
    valor_transferencia REAL NOT NULL,      -- quanto a loja paga
    distancia_km        REAL NOT NULL,
    viagens             INTEGER NOT NULL,
    custo_frete         REAL NOT NULL
);

CREATE TABLE itens_transferencia (
    id                      INTEGER PRIMARY KEY,
    transferencia_id        INTEGER NOT NULL REFERENCES transferencias(id),
    produto_id              INTEGER NOT NULL REFERENCES produtos(id),
    quantidade_solicitada   REAL NOT NULL,
    quantidade_enviada      REAL NOT NULL,
    custo_cd                REAL NOT NULL,
    preco_transferencia     REAL NOT NULL
);

CREATE TABLE estoque (
    unidade_id      INTEGER NOT NULL REFERENCES unidades(id),
    produto_id      INTEGER NOT NULL REFERENCES produtos(id),
    quantidade      REAL NOT NULL,
    custo_medio     REAL NOT NULL,
    estoque_minimo  REAL NOT NULL,
    estoque_maximo  REAL NOT NULL,
    atualizado_em   TEXT NOT NULL,
    PRIMARY KEY (unidade_id, produto_id)
);

CREATE TABLE movimentacoes_estoque (       -- tudo que não é venda (perdas e consumo consolidados por semana)
    id              INTEGER PRIMARY KEY,
    unidade_id      INTEGER NOT NULL REFERENCES unidades(id),
    data            TEXT NOT NULL,
    produto_id      INTEGER NOT NULL REFERENCES produtos(id),
    tipo            TEXT NOT NULL CHECK (tipo IN ('SALDO_INICIAL','ENTRADA_COMPRA','ENTRADA_TRANSFERENCIA',
                                                  'SAIDA_TRANSFERENCIA','CONSUMO_INTERNO','PERDA','AJUSTE_INVENTARIO')),
    quantidade      REAL NOT NULL,
    custo_unitario  REAL NOT NULL,
    motivo          TEXT,
    departamento_id INTEGER REFERENCES departamentos(id),
    referencia      TEXT
);

CREATE TABLE rupturas (
    id              INTEGER PRIMARY KEY,
    unidade_id      INTEGER NOT NULL REFERENCES unidades(id),
    data            TEXT NOT NULL,
    produto_id      INTEGER NOT NULL REFERENCES produtos(id),
    qtd_nao_atendida REAL NOT NULL,
    venda_perdida_estimada REAL NOT NULL
);

-- ---------------------------------------------------------------------
-- Financeiro
-- ---------------------------------------------------------------------
CREATE TABLE categorias_despesa (
    id          INTEGER PRIMARY KEY,
    nome        TEXT NOT NULL UNIQUE,
    tipo        TEXT NOT NULL CHECK (tipo IN ('FIXA','VARIAVEL')),
    grupo_dre   TEXT NOT NULL CHECK (grupo_dre IN ('OCUPACAO','UTILIDADES','ADMINISTRATIVA','COMERCIAL','PESSOAL',
                                                   'FINANCEIRA','DEPRECIACAO','FRANQUIA','LOGISTICA'))
);

CREATE TABLE despesas (
    id                  INTEGER PRIMARY KEY,
    unidade_id          INTEGER NOT NULL REFERENCES unidades(id),
    competencia         TEXT NOT NULL,
    categoria_id        INTEGER NOT NULL REFERENCES categorias_despesa(id),
    descricao           TEXT NOT NULL,
    favorecido          TEXT,
    departamento_id     INTEGER REFERENCES departamentos(id),
    valor               REAL NOT NULL,
    data_vencimento     TEXT NOT NULL,
    data_pagamento      TEXT,
    status              TEXT NOT NULL CHECK (status IN ('ABERTO','PAGO'))
);

-- Receitas da franqueadora (royalties, fundo de marketing, taxa inicial)
CREATE TABLE receitas_franquia (
    id              INTEGER PRIMARY KEY,
    competencia     TEXT NOT NULL,
    loja_id         INTEGER NOT NULL REFERENCES unidades(id),   -- quem paga
    franqueado_id   INTEGER REFERENCES franqueados(id),
    tipo            TEXT NOT NULL CHECK (tipo IN ('ROYALTIES','FUNDO_MARKETING','TAXA_FRANQUIA')),
    base_calculo    REAL,
    percentual      REAL,
    valor           REAL NOT NULL,
    data_vencimento TEXT NOT NULL,
    data_recebimento TEXT,
    status          TEXT NOT NULL CHECK (status IN ('ABERTO','RECEBIDO'))
);

-- Obrigações a pagar de cada unidade. Se o favorecido for outra unidade da rede (ex.: franqueado
-- pagando transferências/royalties à franqueadora), favorecido_unidade_id é preenchido.
CREATE TABLE contas_pagar (
    id              INTEGER PRIMARY KEY,
    unidade_id      INTEGER NOT NULL REFERENCES unidades(id),
    origem          TEXT NOT NULL CHECK (origem IN ('COMPRA','TRANSFERENCIA','DESPESA','FOLHA','ENCARGOS','IMPOSTOS','FRANQUIA')),
    referencia      TEXT,
    favorecido      TEXT NOT NULL,
    favorecido_unidade_id INTEGER REFERENCES unidades(id),
    competencia     TEXT,
    data_emissao    TEXT NOT NULL,
    data_vencimento TEXT NOT NULL,
    valor           REAL NOT NULL,
    data_pagamento  TEXT,
    status          TEXT NOT NULL CHECK (status IN ('ABERTO','PAGO'))
);

-- ---------------------------------------------------------------------
-- Índices
-- ---------------------------------------------------------------------
CREATE INDEX ix_vendas_un_data      ON vendas(unidade_id, data);
CREATE INDEX ix_vendas_cliente      ON vendas(cliente_id);
CREATE INDEX ix_itens_venda_venda   ON itens_venda(venda_id);
CREATE INDEX ix_resumo_prod         ON resumo_vendas_diario(produto_id, unidade_id);
CREATE INDEX ix_mov_un_prod_data    ON movimentacoes_estoque(unidade_id, produto_id, data);
CREATE INDEX ix_mov_tipo_data       ON movimentacoes_estoque(tipo, data);
CREATE INDEX ix_itens_compra_ped    ON itens_compra(pedido_id);
CREATE INDEX ix_pedidos_un_data     ON pedidos_compra(unidade_id, data_pedido);
CREATE INDEX ix_transf_loja         ON transferencias(loja_id, data_envio);
CREATE INDEX ix_transf_cd           ON transferencias(cd_id, data_envio);
CREATE INDEX ix_itens_transf        ON itens_transferencia(transferencia_id);
CREATE INDEX ix_escalas_data        ON escalas(data);
CREATE INDEX ix_folha_comp          ON folha_pagamento(competencia, unidade_id);
CREATE INDEX ix_despesas_comp       ON despesas(competencia, unidade_id);
CREATE INDEX ix_cp_venc             ON contas_pagar(data_vencimento);
CREATE INDEX ix_cp_un               ON contas_pagar(unidade_id, status);
CREATE INDEX ix_rupturas_data       ON rupturas(unidade_id, data);
CREATE INDEX ix_clientes_un         ON clientes(unidade_id);
CREATE INDEX ix_func_un             ON funcionarios(unidade_id);
