# Dicionário de dados: modelo Power BI da Rede Vale Verde

Modelo em estrela com **6 dimensões** e **10 fatos**, exportado do sistema por `powerbi/exportar_powerbi.py`. Todos os dados são fictícios.

Convenções:

- Tabelas começadas por `d` são dimensões (o "quem/onde/o quê") e por `f` são fatos (os eventos e valores).
- Valores monetários em reais (R$). Colunas `Data` de tabelas mensais trazem o 1º dia do mês de competência.
- **PK** = chave da dimensão; **FK** = coluna que liga a fato à dimensão (relação muitos-para-um, filtro em direção única).
- IDs, latitudes e longitudes devem ficar com *Resumir por = Nenhum*.

## Índice

- [`dCalendario`](#dcalendario): dimensão, 1 linha por dia (nov/2024 a dez/2026)
- [`dUnidade`](#dunidade): dimensão, 1 linha por unidade (sede, 3 CDs e 10 lojas)
- [`dProduto`](#dproduto): dimensão, 1 linha por produto (SKU)
- [`dCidade`](#dcidade): dimensão, 1 linha por município (com loja ou candidato)
- [`dFornecedor`](#dfornecedor): dimensão, 1 linha por fornecedor
- [`dCliente`](#dcliente): dimensão, 1 linha por cliente do programa de fidelidade
- [`fVendas`](#fvendas): fato, 1 linha por loja × dia × produto
- [`fCupons`](#fcupons): fato, 1 linha por loja × dia × forma de pagamento
- [`fTransferencias`](#ftransferencias): fato, 1 linha por transferência (CD → loja)
- [`fCompras`](#fcompras): fato, 1 linha por pedido de compra
- [`fPerdas`](#fperdas): fato, 1 linha por movimento de saída sem venda
- [`fRupturas`](#frupturas): fato, 1 linha por loja × dia × produto em falta
- [`fFolha`](#ffolha): fato, 1 linha por unidade × mês × cargo
- [`fDespesas`](#fdespesas): fato, 1 linha por unidade × mês × categoria de despesa
- [`fReceitasFranquia`](#freceitasfranquia): fato, 1 linha por loja franqueada × mês × tipo
- [`fDRE`](#fdre): fato, 1 linha por unidade × mês × linha da DRE

## Relacionamentos

| Tabela | Coluna | Dimensão | Observação |
|---|---|---|---|
| `dUnidade` | `Cidade` | `dCidade[Cidade]` | opcional |
| `dCliente` | `UnidadeID` | `dUnidade[UnidadeID]` |  |
| `fVendas` | `UnidadeID` | `dUnidade[UnidadeID]` |  |
| `fVendas` | `Data` | `dCalendario[Data]` |  |
| `fVendas` | `ProdutoID` | `dProduto[ProdutoID]` |  |
| `fCupons` | `UnidadeID` | `dUnidade[UnidadeID]` |  |
| `fCupons` | `Data` | `dCalendario[Data]` |  |
| `fTransferencias` | `CDID` | `dUnidade[UnidadeID]` | inativa (USERELATIONSHIP) |
| `fTransferencias` | `UnidadeID` | `dUnidade[UnidadeID]` |  |
| `fTransferencias` | `Data` | `dCalendario[Data]` |  |
| `fCompras` | `UnidadeID` | `dUnidade[UnidadeID]` |  |
| `fCompras` | `FornecedorID` | `dFornecedor[FornecedorID]` |  |
| `fCompras` | `Data` | `dCalendario[Data]` |  |
| `fPerdas` | `UnidadeID` | `dUnidade[UnidadeID]` |  |
| `fPerdas` | `Data` | `dCalendario[Data]` |  |
| `fPerdas` | `ProdutoID` | `dProduto[ProdutoID]` |  |
| `fRupturas` | `UnidadeID` | `dUnidade[UnidadeID]` |  |
| `fRupturas` | `Data` | `dCalendario[Data]` |  |
| `fRupturas` | `ProdutoID` | `dProduto[ProdutoID]` |  |
| `fFolha` | `Data` | `dCalendario[Data]` |  |
| `fFolha` | `UnidadeID` | `dUnidade[UnidadeID]` |  |
| `fDespesas` | `Data` | `dCalendario[Data]` |  |
| `fDespesas` | `UnidadeID` | `dUnidade[UnidadeID]` |  |
| `fReceitasFranquia` | `Data` | `dCalendario[Data]` |  |
| `fReceitasFranquia` | `UnidadeID` | `dUnidade[UnidadeID]` |  |
| `fDRE` | `Data` | `dCalendario[Data]` |  |
| `fDRE` | `UnidadeID` | `dUnidade[UnidadeID]` |  |

## dCalendario

**Dimensão** · 1 linha por dia (nov/2024 a dez/2026) · 791 linhas

Calendário contínuo. Deve ser marcada como tabela de datas. Filtra todas as tabelas fato pela coluna Data.

| Coluna | Tipo | Chave | Descrição | Exemplo |
|---|---|---|---|---|
| `Data` | Data | PK | Dia do calendário. | 2025-12-01 |
| `Ano` | Inteiro |  | Ano civil (2024 a 2026). | 2025 |
| `MesNum` | Inteiro |  | Número do mês (1 a 12). Use para ordenar a coluna Mes. | 12 |
| `Mes` | Texto |  | Mês abreviado (jan, fev...). Ordenar por MesNum. | dez |
| `AnoMes` | Texto |  | Ano e mês no formato aaaa-mm; ordena corretamente em ordem alfabética. | 2025-12 |
| `MesAno` | Texto |  | Rótulo curto para gráficos (nov/24). Ordenar por IndiceMes. | dez/25 |
| `Trimestre` | Texto |  | Ano e trimestre (2025 T1). | 2025 T4 |
| `DiaSemanaNum` | Inteiro |  | Dia da semana, 1 = segunda ... 7 = domingo. Use para ordenar DiaSemana. | 1 |
| `DiaSemana` | Texto |  | Dia da semana abreviado (seg, ter...). Ordenar por DiaSemanaNum. | seg |
| `Dia` | Inteiro |  | Dia do mês (1 a 31). | 1 |
| `FimDeSemana` | Inteiro 0/1 |  | 1 se sábado ou domingo. | 0 |
| `LojaFechada` | Inteiro 0/1 |  | 1 em 25/12 e 01/01, dias em que as lojas não abrem. | 0 |
| `IndiceMes` | Inteiro |  | Sequência dos meses desde nov/2024 (0, 1, 2...). Útil para ordenar e para tendência. | 13 |

## dUnidade

**Dimensão** · 1 linha por unidade (sede, 3 CDs e 10 lojas) · 14 linhas

Cadastro das unidades da rede. É a dimensão central do modelo: filtra todas as fatos por UnidadeID.

| Coluna | Tipo | Chave | Descrição | Exemplo |
|---|---|---|---|---|
| `UnidadeID` | Inteiro | PK | Identificador da unidade. | 8 |
| `Codigo` | Texto |  | Código curto: SEDE, CD01 a CD03, VV01 a VV10. | VV04 |
| `Unidade` | Texto |  | Nome da unidade. | Vale Verde BH Savassi |
| `Tipo` | Texto |  | SEDE, CD (centro de distribuição) ou LOJA. | LOJA |
| `Modelo` | Texto |  | PROPRIA (loja da rede), FRANQUIA (loja de franqueado) ou FRANQUEADORA (sede e CDs). | FRANQUIA |
| `Cidade` | Texto | FK → dCidade | Município da unidade. Pode ligar em dCidade[Cidade] (opcional). | Belo Horizonte |
| `UF` | Texto |  | Sigla do estado. | MG |
| `Regiao` | Texto |  | Região do Brasil (Sudeste, Sul, Nordeste, Centro-Oeste, Norte). | Sudeste |
| `Latitude` | Decimal |  | Latitude da unidade, para mapas. Não resumir. | -19,93 |
| `Longitude` | Decimal |  | Longitude da unidade, para mapas. Não resumir. | -43,93 |
| `AreaM2` | Inteiro |  | Área de vendas (lojas) ou área construída (CDs e sede), em m². | 1300 |
| `Checkouts` | Inteiro |  | Quantidade de caixas (PDVs) da loja. Vazio para sede e CDs. | 7 |
| `Inauguracao` | Data |  | Data de abertura. Lojas inauguradas no período: VV09 (mar/25), VV06 (set/25), VV10 (abr/26). | 2021-11-01 |
| `CD` | Texto |  | Código do CD que abastece a loja. Vazio para sede e CDs. | CD02 |
| `DistanciaCDkm` | Decimal |  | Distância rodoviária estimada entre a loja e o seu CD, em km. | 660,40 |
| `LeadTimeCD` | Inteiro |  | Dias entre o envio pelo CD e a chegada na loja. | 1 |
| `Franqueado` | Texto |  | Nome do grupo franqueado. Vazio para lojas próprias. | Guaíba Supermercados |
| `FatorPreco` | Decimal |  | Multiplicador de preço da praça em relação à tabela da rede (1,03 = 3% acima). | 0,99 |

## dProduto

**Dimensão** · 1 linha por produto (SKU) · 237 linhas

Catálogo de produtos de revenda e de uso interno.

| Coluna | Tipo | Chave | Descrição | Exemplo |
|---|---|---|---|---|
| `ProdutoID` | Inteiro | PK | Identificador do produto. | 119 |
| `SKU` | Texto |  | Código interno do produto (6 dígitos, os 2 primeiros indicam a categoria). | 30010 |
| `Produto` | Texto |  | Descrição completa do produto. | Bebida Láctea Morango 900g Campo Bom |
| `Marca` | Texto |  | Marca do fabricante. "Vale Verde" é a marca própria. | Campo Bom |
| `Categoria` | Texto |  | Departamento do produto (Mercearia, Bebidas, Açougue...). | Laticínios e Frios |
| `Canal` | Texto |  | Como chega à loja: CD (via centro de distribuição) ou DIRETO (fornecedor regional entrega na loja). | DIRETO |
| `Perecivel` | Inteiro 0/1 |  | 1 para açougue, hortifrúti, padaria e frios. | 1 |
| `Revenda` | Inteiro 0/1 |  | 1 se o item é vendido ao cliente; 0 para itens de uso interno (sacolas, bobinas, limpeza). | 1 |
| `Medida` | Texto |  | Unidade de venda: UN, KG, PCT ou CX. | UN |
| `ValidadeDias` | Inteiro |  | Prazo de validade típico, em dias. | 120 |
| `Sazonalidade` | Texto |  | Época de pico de venda: NATAL, PASCOA, QUARESMA, INVERNO, VERAO, PANETONE, FDS. Vazio se não tem. | VERAO |
| `MarcaPropria` | Inteiro 0/1 |  | 1 se for produto da marca própria Vale Verde. | 0 |

## dCidade

**Dimensão** · 1 linha por município (com loja ou candidato) · 41 linhas

Municípios com unidades e cidades candidatas à expansão. Base dos mapas de mercado e do modelo de expansão.

| Coluna | Tipo | Chave | Descrição | Exemplo |
|---|---|---|---|---|
| `CidadeID` | Inteiro | PK | Identificador do município. | 21 |
| `Cidade` | Texto |  | Nome do município. | João Pessoa |
| `UF` | Texto |  | Sigla do estado. | PB |
| `Regiao` | Texto |  | Região do Brasil. | Nordeste |
| `Latitude` | Decimal |  | Latitude do centro da cidade. Não resumir. | -7,12 |
| `Longitude` | Decimal |  | Longitude do centro da cidade. Não resumir. | -34,84 |
| `Populacao` | Inteiro |  | População aproximada (habitantes). | 833000 |
| `RendaPerCapita` | Decimal |  | Renda mensal per capita ilustrativa, em R$. | 1.500 |
| `Concorrentes` | Inteiro |  | Quantidade estimada de supermercados concorrentes no município. | 85 |
| `Situacao` | Texto |  | Com loja, CD/Sede (só unidade de apoio) ou Candidata (alvo de expansão). | Candidata |

## dFornecedor

**Dimensão** · 1 linha por fornecedor · 37 linhas

Fornecedores nacionais (abastecem os CDs) e regionais (entregam perecíveis direto nas lojas).

| Coluna | Tipo | Chave | Descrição | Exemplo |
|---|---|---|---|---|
| `FornecedorID` | Inteiro | PK | Identificador do fornecedor. | 19 |
| `Fornecedor` | Texto |  | Nome fantasia. | Frios Campos Gerais |
| `Abrangencia` | Texto |  | NACIONAL (vende para os CDs) ou REGIONAL (vende para as lojas de uma região). | REGIONAL |
| `RegiaoAtendida` | Texto |  | Região que o fornecedor atende; Nacional para os de abrangência nacional. | Sul |
| `Tipo` | Texto |  | Linha de produtos: MERC (mercearia), BEB, FRIOS, LAT, LIMP, BAZAR, EMB, HORTI, PAD, BOV, AVES. | FRIOS |
| `Cidade` | Texto |  | Cidade de origem do fornecedor. | Ponta Grossa |
| `UF` | Texto |  | Estado de origem. | PR |
| `Latitude` | Decimal |  | Latitude do fornecedor. Não resumir. | -24,97 |
| `Longitude` | Decimal |  | Longitude do fornecedor. Não resumir. | -50,06 |
| `PrazoPagamento` | Inteiro |  | Prazo médio de pagamento negociado, em dias. | 21 |

## dCliente

**Dimensão** · 1 linha por cliente do programa de fidelidade · 33.480 linhas

Clientes cadastrados, com localização aproximada de residência. Usada nos mapas de área de influência.

| Coluna | Tipo | Chave | Descrição | Exemplo |
|---|---|---|---|---|
| `ClienteID` | Inteiro | PK | Identificador do cliente. Não resumir. | 16741 |
| `UnidadeID` | Inteiro | FK → dUnidade | Loja de referência do cliente (onde se cadastrou). | 9 |
| `Sexo` | Texto |  | M ou F. | F |
| `Bairro` | Texto |  | Bairro de residência (fictício), com a zona da cidade entre parênteses. | Jardim São Bento (Sudeste) |
| `Latitude` | Decimal |  | Latitude aproximada da residência. Não resumir. | -25,43 |
| `Longitude` | Decimal |  | Longitude aproximada da residência. Não resumir. | -49,32 |
| `DistanciaKm` | Decimal |  | Distância em linha reta entre a residência e a loja, em km. | 3,65 |
| `FaixaDistancia` | Texto |  | Faixa da distância: 0-1 km, 1-3 km, 3-5 km, 5+ km. | 3-5 km |
| `Cadastro` | Data |  | Data de adesão ao programa de fidelidade. | 2022-02-15 |
| `Compras6m` | Inteiro |  | Compras identificadas nos últimos 6 meses (período com cupons detalhados). | 1 |
| `Valor6m` | Decimal |  | Valor gasto nos últimos 6 meses, em R$. Vazio se não comprou. | 2.637,79 |

## fVendas

**Fato** · 1 linha por loja × dia × produto · 1.409.868 linhas

Vendas diárias por produto (24 meses). Use para mix, curva ABC, margem por categoria. Para faturamento total prefira fCupons, que inclui descontos.

| Coluna | Tipo | Chave | Descrição | Exemplo |
|---|---|---|---|---|
| `UnidadeID` | Inteiro | FK → dUnidade | Loja que vendeu. | 9 |
| `Data` | Data | FK → dCalendario | Dia da venda. | 2025-07-02 |
| `ProdutoID` | Inteiro | FK → dProduto | Produto vendido. | 55 |
| `Quantidade` | Decimal |  | Quantidade vendida na unidade de medida do produto (UN, KG...). | 51 |
| `Receita` | Decimal |  | Valor vendido, em R$ (preço praticado × quantidade). | 218,79 |
| `CMV` | Decimal |  | Custo da mercadoria vendida, em R$, pelo custo médio ponderado do estoque. | 152,47 |

## fCupons

**Fato** · 1 linha por loja × dia × forma de pagamento · 31.570 linhas

Resumo diário dos cupons fiscais. Fonte oficial do faturamento, ticket médio e fluxo de clientes.

| Coluna | Tipo | Chave | Descrição | Exemplo |
|---|---|---|---|---|
| `UnidadeID` | Inteiro | FK → dUnidade | Loja. | 9 |
| `Data` | Data | FK → dCalendario | Dia das vendas. | 2025-07-14 |
| `FormaPagamento` | Texto |  | CREDITO, DEBITO, PIX, DINHEIRO ou VOUCHER (vale-alimentação). | CREDITO |
| `Cupons` | Inteiro |  | Quantidade de cupons (compras). Base do ticket médio e do fluxo. | 142 |
| `Itens` | Inteiro |  | Itens registrados nos cupons. | 875 |
| `ValorBruto` | Decimal |  | Valor antes dos descontos, em R$. | 13.929,43 |
| `Desconto` | Decimal |  | Descontos concedidos no caixa, em R$. | 0 |
| `Receita` | Decimal |  | Valor pago pelo cliente (ValorBruto − Desconto), em R$. | 13.929,43 |
| `CMV` | Decimal |  | Custo das mercadorias desses cupons, em R$. | 9.355,38 |
| `CuponsFidelidade` | Inteiro |  | Cupons em que o cliente se identificou no programa de fidelidade. | 52 |

## fTransferencias

**Fato** · 1 linha por transferência (CD → loja) · 2.182 linhas

Abastecimento das lojas pelos CDs. A relação por CDID fica inativa e é ligada nas medidas de visão do CD (USERELATIONSHIP).

| Coluna | Tipo | Chave | Descrição | Exemplo |
|---|---|---|---|---|
| `TransferenciaID` | Inteiro | PK | Número da transferência. Não resumir. | 1092 |
| `CDID` | Inteiro | FK → dUnidade (inativa) | CD que enviou a mercadoria. | 2 |
| `UnidadeID` | Inteiro | FK → dUnidade | Loja que recebeu. | 11 |
| `Data` | Data | FK → dCalendario | Data de envio pelo CD. | 2025-11-28 |
| `DataRecebimento` | Data |  | Data em que a loja recebeu. Vazio se ainda em trânsito. | 2025-11-29 |
| `Status` | Texto |  | RECEBIDA, RECEBIDA_PARCIAL ou EM_TRANSITO. | RECEBIDA |
| `CustoCD` | Decimal |  | Custo da mercadoria para o CD, em R$. | 108.226,02 |
| `ValorTransferencia` | Decimal |  | Valor cobrado da loja (custo de referência + 1%), em R$. A diferença para CustoCD é a margem do CD. | 116.285,40 |
| `DistanciaKm` | Decimal |  | Distância rodoviária CD → loja, em km. | 899,80 |
| `Viagens` | Inteiro |  | Caminhões necessários (até R$ 150 mil de carga por viagem). | 1 |
| `Frete` | Decimal |  | Custo do frete, em R$ (R$ 400 por viagem + R$ 3,80 por km). | 3.819,24 |
| `LeadTimeDias` | Decimal |  | Dias entre envio e recebimento. | 1 |

## fCompras

**Fato** · 1 linha por pedido de compra · 23.876 linhas

Pedidos a fornecedores: dos CDs (itens de mercearia, com 6% de desconto por volume) e das lojas (perecíveis direto do fornecedor regional).

| Coluna | Tipo | Chave | Descrição | Exemplo |
|---|---|---|---|---|
| `PedidoID` | Inteiro | PK | Número do pedido. Não resumir. | 11939 |
| `UnidadeID` | Inteiro | FK → dUnidade | Unidade compradora (CD ou loja). | 13 |
| `FornecedorID` | Inteiro | FK → dFornecedor | Fornecedor. | 29 |
| `Data` | Data | FK → dCalendario | Data do pedido. | 2025-12-02 |
| `DataRecebimento` | Data |  | Data de entrega. Vazio se o pedido está aberto. | 2025-12-04 |
| `Status` | Texto |  | RECEBIDO, RECEBIDO_PARCIAL ou ABERTO. | RECEBIDO |
| `Valor` | Decimal |  | Valor total do pedido, em R$. | 4.145,65 |
| `DistanciaKm` | Decimal |  | Distância fornecedor → unidade, em km. | 178,70 |
| `LeadTimeDias` | Decimal |  | Dias entre pedido e entrega. | 2 |

## fPerdas

**Fato** · 1 linha por movimento de saída sem venda · 217.955 linhas

Quebras, consumo interno e ajustes de inventário (valorizados a custo).

| Coluna | Tipo | Chave | Descrição | Exemplo |
|---|---|---|---|---|
| `UnidadeID` | Inteiro | FK → dUnidade | Unidade onde ocorreu. | 6 |
| `Data` | Data | FK → dCalendario | Dia do registro. | 2025-12-06 |
| `ProdutoID` | Inteiro | FK → dProduto | Produto. | 90 |
| `Tipo` | Texto |  | PERDA (quebra), CONSUMO_INTERNO (uso pela própria loja) ou AJUSTE_INVENTARIO (diferença de contagem). | PERDA |
| `Motivo` | Texto |  | Motivo detalhado (Vencimento, Avaria, Furto/desvio, Copa/refeitório...). | Vencimento |
| `Quantidade` | Decimal |  | Quantidade baixada (positiva). Em ajuste de inventário pode ser negativa, quando sobrou produto. | 1 |
| `Valor` | Decimal |  | Valor a custo, em R$. | 1,54 |

## fRupturas

**Fato** · 1 linha por loja × dia × produto em falta · 388 linhas

Dias em que faltou produto na gôndola e a demanda não foi atendida.

| Coluna | Tipo | Chave | Descrição | Exemplo |
|---|---|---|---|---|
| `UnidadeID` | Inteiro | FK → dUnidade | Loja. | 9 |
| `Data` | Data | FK → dCalendario | Dia da falta. | 2025-12-07 |
| `ProdutoID` | Inteiro | FK → dProduto | Produto em falta. | 139 |
| `QtdNaoAtendida` | Decimal |  | Quantidade que os clientes teriam comprado. | 8,08 |
| `VendaPerdida` | Decimal |  | Venda perdida estimada, em R$ (quantidade × preço). | 540,34 |

## fFolha

**Fato** · 1 linha por unidade × mês × cargo · 5.028 linhas

Folha de pagamento mensal agregada por cargo. Data é sempre o 1º dia do mês de competência.

| Coluna | Tipo | Chave | Descrição | Exemplo |
|---|---|---|---|---|
| `Data` | Data | FK → dCalendario | Competência (1º dia do mês). | 2025-11-01 |
| `UnidadeID` | Inteiro | FK → dUnidade | Unidade onde o funcionário trabalha. | 13 |
| `Cargo` | Texto |  | Cargo. | Padeiro |
| `Departamento` | Texto |  | Setor (Frente de Caixa, Açougue, Logística (CD), Franqueadora (Sede)...). | Padaria |
| `Funcionarios` | Inteiro |  | Funcionários pagos no mês nesse cargo (headcount). | 2 |
| `SalarioBruto` | Decimal |  | Salários brutos, em R$. | 5.212,43 |
| `HorasExtras` | Decimal |  | Horas extras com reflexo no DSR, em R$. | 141,19 |
| `Encargos` | Decimal |  | INSS patronal e FGTS, em R$. | 1.866,06 |
| `Beneficios` | Decimal |  | Vale-alimentação e vale-transporte (líquido do desconto do funcionário), em R$. | 835,72 |
| `Provisoes` | Decimal |  | Provisões de 13º e férias com encargos, em R$. | 1.376,38 |
| `CustoTotal` | Decimal |  | Custo total para a empresa, em R$ (soma das colunas de custo). | 9.290,59 |

## fDespesas

**Fato** · 1 linha por unidade × mês × categoria de despesa · 5.812 linhas

Despesas operacionais lançadas por competência. Data é o 1º dia do mês.

| Coluna | Tipo | Chave | Descrição | Exemplo |
|---|---|---|---|---|
| `Data` | Data | FK → dCalendario | Competência (1º dia do mês). | 2025-12-01 |
| `UnidadeID` | Inteiro | FK → dUnidade | Unidade que teve a despesa. | 1 |
| `Categoria` | Texto |  | Categoria da despesa (Aluguel, Energia elétrica, Taxas de cartão...). | Internet e telefonia |
| `Tipo` | Texto |  | FIXA (não varia com as vendas) ou VARIAVEL. Base do ponto de equilíbrio. | FIXA |
| `GrupoDRE` | Texto |  | Linha da DRE onde a despesa entra: OCUPACAO, UTILIDADES, ADMINISTRATIVA, COMERCIAL, PESSOAL, LOGISTICA, FRANQUIA, DEPRECIACAO, FINANCEIRA. | ADMINISTRATIVA |
| `Valor` | Decimal |  | Valor da despesa, em R$. | 3.200 |

## fReceitasFranquia

**Fato** · 1 linha por loja franqueada × mês × tipo · 236 linhas

O que as franquias pagam à franqueadora.

| Coluna | Tipo | Chave | Descrição | Exemplo |
|---|---|---|---|---|
| `Data` | Data | FK → dCalendario | Competência (1º dia do mês). | 2025-12-01 |
| `UnidadeID` | Inteiro | FK → dUnidade | Loja franqueada que paga. | 12 |
| `Tipo` | Texto |  | ROYALTIES (1,5% do faturamento), FUNDO_MARKETING (0,5%) ou TAXA_FRANQUIA (R$ 180 mil na abertura). | ROYALTIES |
| `Base` | Decimal |  | Faturamento da loja usado no cálculo, em R$. Vazio na taxa de franquia. | 1.662.583,30 |
| `Valor` | Decimal |  | Valor devido, em R$. | 34.285,13 |
| `Status` | Texto |  | RECEBIDO ou ABERTO. | RECEBIDO |

## fDRE

**Fato** · 1 linha por unidade × mês × linha da DRE · 5.910 linhas

DRE gerencial já calculada, em formato longo. Deduções vêm negativas. Atenção: a tabela tem linhas de detalhe e de subtotal; nunca some a coluna Valor sem filtrar a linha (use a medida DRE Valor ou filtre Chave/Nivel).

| Coluna | Tipo | Chave | Descrição | Exemplo |
|---|---|---|---|---|
| `Data` | Data | FK → dCalendario | Competência (1º dia do mês). | 2024-12-01 |
| `UnidadeID` | Inteiro | FK → dUnidade | Unidade. Royalties e margem dos CDs aparecem como receita da franqueadora e custo das lojas. | 8 |
| `Ordem` | Inteiro |  | Posição da linha na DRE (1 a 25). Use para ordenar Linha. | 2 |
| `Chave` | Texto |  | Código fixo da linha (receita_bruta, cmv, ebitda, lucro_liquido...). Use nas medidas DAX. | descontos |
| `Linha` | Texto |  | Descrição da linha como aparece no relatório. Ordenar por Ordem. | (-) Descontos concedidos |
| `Nivel` | Inteiro |  | 0 = receita bruta, 1 = linha de detalhe (+/−), 2 = subtotal (=), 3 = lucro líquido. Use para formatação condicional. | 1 |
| `Valor` | Decimal |  | Valor da linha, em R$. Receitas e subtotais positivos, deduções negativas. | -218,85 |

---

Gerado por `powerbi/dicionario.py md`. Para atualizar, edite as descrições no script e rode de novo.
