# Roteiro do Power BI — Rede Vale Verde

Este roteiro leva os dados exportados até três dashboards prontos para o portfólio, publicados com o
**Publicar na Web** (gratuito) e incorporados no site do GitHub Pages.

---

## 1. Exportar os dados

Na pasta `mercado_vale_verde`, com o banco já gerado:

```
python powerbi/exportar_powerbi.py
```

Isso cria `powerbi/dados/` com 16 arquivos CSV (cerca de 80 MB). O separador é `;`, o decimal é `,`
e a codificação é UTF-8.

## 2. Importar no Power BI Desktop

1. **Arquivo > Opções > Configurações regionais**: deixe "Português (Brasil)" para este arquivo.
2. **Obter dados > Texto/CSV**: importe cada arquivo. Ou use **Pasta** e combine, se já estiver habituada.
3. No Power Query, confira os tipos:
   - `Data`, `DataRecebimento`, `Inauguracao` e `Cadastro` como **Data**;
   - IDs como **Número inteiro**;
   - valores como **Número decimal fixo** (ou decimal).
4. **Fechar e aplicar.**

## 3. Modelo (estrela)

Na Exibição de modelo, crie estas relações (todas de muitos para um, com filtro em direção única):

| De (fato) | Para (dimensão) | Observação |
|---|---|---|
| fVendas[Data] | dCalendario[Data] | |
| fVendas[UnidadeID] | dUnidade[UnidadeID] | |
| fVendas[ProdutoID] | dProduto[ProdutoID] | |
| fCupons[Data] · fCupons[UnidadeID] | dCalendario · dUnidade | |
| fTransferencias[Data] · fTransferencias[UnidadeID] | dCalendario · dUnidade | UnidadeID = loja que recebe |
| fTransferencias[CDID] | dUnidade[UnidadeID] | **inativa** (ativada via USERELATIONSHIP nas medidas "visão CD") |
| fCompras[Data] · [UnidadeID] · [FornecedorID] | dCalendario · dUnidade · dFornecedor | |
| fPerdas, fRupturas: [Data] · [UnidadeID] · [ProdutoID] | dCalendario · dUnidade · dProduto | |
| fFolha, fDespesas, fReceitasFranquia, fDRE: [Data] · [UnidadeID] | dCalendario · dUnidade | Data = 1º dia do mês |
| dCliente[UnidadeID] | dUnidade[UnidadeID] | |

Depois:
- Clique com o botão direito em **dCalendario > Marcar como tabela de datas** (coluna Data).
- Ordene `dCalendario[Mes]` por `MesNum`, `dCalendario[MesAno]` por `IndiceMes` e `fDRE[Linha]` por `Ordem`.
- Oculte as colunas de ID nas fatos (o recrutador repara na lista de campos limpa).
- Crie a tabela `_Medidas` e cole as medidas de **`medidas.dax`**, organizando-as em pastas de exibição.

Ao final, tire um print da Exibição de modelo, porque ele entra no case como "o modelo de dados".

---

## 4. Os três dashboards

Use uma página por tema, em 16:9 (1280 × 720). Mantenha a mesma identidade visual nos três:
fundo `#F9F9F7`, cartões brancos com borda clara, azul `#2A78D6` para lojas próprias, laranja `#EB6834`
para franquias e verde `#1F6B45` como cor da marca. Coloque segmentações (Período, Região, Modelo e Loja) numa
faixa no topo.

### Dashboard 1 — Desempenho da rede
**Pergunta:** a rede está crescendo de forma saudável, ou só porque abriu lojas?

| Página | Visuais |
|---|---|
| Visão geral | Cards HTML (`HTML Card Faturamento`), Ticket Médio, Margem Bruta %, Crescimento Mesmas Lojas %; colunas de Faturamento por MesAno com linha de Faturamento Ano Anterior; `HTML Ranking Lojas` |
| Mapa | Azure Maps (ou mapa de bolhas) com dUnidade[Latitude/Longitude], tamanho = Faturamento, cor = Margem LAIR %; mapa coroplético por UF |
| Próprias × franquias | Matriz Modelo × (Faturamento por m² Ano, Margem Bruta %, Perdas %, Pessoal %, Margem LAIR %); dispersão Faturamento por m² × Margem LAIR % por loja |

**Números para contar a história** (12 meses, nov/25 a out/26):
- R$ 224 mi de faturamento, em 10 lojas de 9 estados;
- crescimento de 8,2% nas mesmas lojas, ou seja, a rede cresce mesmo sem contar as inaugurações;
- margem antes do IR de 7,9% nas próprias contra 4,2% nas franqueadas, diferença explicada por royalties, fundo,
  pró-labore do franqueado e juros da implantação;
- as três lojas novas seguem a curva de maturação: Porto Alegre foi de R$ 1,1 mi para R$ 1,75 mi/mês em um ano.

### Dashboard 2 — Logística e CDs
**Pergunta:** quanto custa abastecer cada loja, e onde a rede deveria ter o próximo CD?

| Página | Visuais |
|---|---|
| Rotas | Mapa com CDs e lojas; tabela loja × (DistanciaCDkm, Viagens, Frete, Frete % Transferido, Frete % Faturamento, Lead Time Médio); `HTML Semáforo Frete` |
| CDs | Colunas de Margem de Distribuição CD × Frete (visão CD) por CD; linha mensal do frete |
| Fornecedores | Barras de compras por fornecedor (nacional × regional); Lead Time Médio por fornecedor |

**Números:**
- o frete de Belém (VV10, 2.094 km do CD de Pernambuco) é 7,8% do valor transferido e 3,0% do faturamento da
  loja, contra 0,3% em Campinas;
- Goiânia (900 km) é a segunda rota mais cara: 1,9% do faturamento;
- a pergunta natural do case é se um CD no Norte ou no Centro-Oeste se pagaria.

### Dashboard 3 — Resultado e DRE
**Pergunta:** onde a rede ganha e onde perde dinheiro, e quanto precisa vender para empatar?

| Página | Visuais |
|---|---|
| DRE | Matriz fDRE[Linha] × MesAno com [DRE Valor] e [DRE % Vertical]; segmentação por Modelo/Unidade (incluindo "FRANQUEADORA") |
| Perdas e pessoal | Barras de Perdas por categoria e motivo; Perdas % e Pessoal % por loja |
| Equilíbrio | Cards Ponto de Equilíbrio Mensal e Margem de Contribuição %; colunas de LAIR por mês (destacando jan/fev) |

**Números:**
- as perdas se concentram em perecíveis: hortifrúti (R$ 982 mil), açougue (R$ 854 mil) e padaria (R$ 691 mil) em 12 meses;
- dezembro é o maior mês (R$ 21,6 mi) e janeiro/fevereiro têm o menor resultado;
- a franqueadora (próprias + CDs + sede) tem resultado positivo, sustentado por royalties e pela margem dos CDs.

---

## 5. Publicar na Web (gratuito)

1. **Publicar** (na faixa Página Inicial) > **Meu workspace**.
2. No navegador, em app.powerbi.com, abra o relatório > **Arquivo > Inserir relatório > Publicar na Web (público)**.
3. Copie o **link** (não o iframe). Ele vai no arquivo `casos.js` do site.

**Antes de começar, confira:**
- **O recurso precisa estar liberado no seu tenant.** Numa conta corporativa, o administrador pode ter desligado o
  "Publicar na Web". Se a opção não aparecer ou ficar cinza, peça ao TI, ou use uma conta de estudante.
- **Políticas da empresa.** Publicar um projeto pessoal no tenant do empregador pode esbarrar nas regras internas.
  Como os dados são 100% fictícios, o risco de exposição é zero, mas vale confirmar.
- **Tudo que vai para a web é público.** Por isso o projeto usa apenas dados fictícios.
- **Visuais personalizados** (como o HTML Content) e mapas podem depender de permissões do tenant. Abra o link
  público numa janela anônima para testar antes de divulgar.

---

## 6. O que capturar para o case (vai para o site)

Para cada dashboard, salve em `portfolio/img/`:
- `caseN-capa.png`: print da página principal (1280 × 720);
- `caseN-modelo.png`: print da Exibição de modelo (ou só das tabelas usadas no case);
- opcional, um GIF curto navegando pelo relatório (ScreenToGif é gratuito).

Depois escreva três parágrafos curtos em `portfolio/casos.js`: o problema, o modelo de dados e as decisões
de design. Os textos de exemplo já estão lá, com os números acima.
