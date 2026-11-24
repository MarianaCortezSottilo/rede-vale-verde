-- =====================================================================
-- Rede Vale Verde — consultas de exemplo (rode na tela Consulta SQL ou em qualquer cliente SQLite)
-- =====================================================================

-- Faturamento por loja e mês
SELECT u.codigo, u.nome, substr(r.data,1,7) AS mes, ROUND(SUM(r.valor_total),2) AS faturamento,
       SUM(r.cupons) AS cupons, ROUND(SUM(r.valor_total)/SUM(r.cupons),2) AS ticket
FROM resumo_cupons_diario r JOIN unidades u ON u.id = r.unidade_id
GROUP BY u.id, mes ORDER BY mes, faturamento DESC;

-- Faturamento por estado e região (para mapas)
SELECT c.regiao, c.uf, COUNT(DISTINCT u.id) AS lojas, ROUND(SUM(r.valor_total),2) AS faturamento_12m,
       ROUND(SUM(r.valor_total) / c.populacao, 2) AS faturamento_per_capita
FROM resumo_cupons_diario r JOIN unidades u ON u.id = r.unidade_id JOIN cidades c ON c.id = u.cidade_id
WHERE r.data >= date((SELECT MAX(data) FROM resumo_cupons_diario), '-365 days')
GROUP BY c.uf ORDER BY faturamento_12m DESC;

-- Same-store sales: crescimento das lojas com mais de 13 meses
WITH m AS (SELECT unidade_id, substr(data,1,7) mes, SUM(valor_total) fat FROM resumo_cupons_diario GROUP BY 1,2)
SELECT u.codigo, a.mes, ROUND(a.fat,2) faturamento, ROUND(b.fat,2) ano_anterior, ROUND(a.fat/b.fat - 1, 4) crescimento
FROM m a JOIN m b ON b.unidade_id = a.unidade_id
 AND b.mes = printf('%04d-%s', CAST(substr(a.mes,1,4) AS INT) - 1, substr(a.mes,6,2))
JOIN unidades u ON u.id = a.unidade_id ORDER BY a.mes, u.codigo;

-- Royalties e fundo de marketing por franqueado
SELECT f.nome_fantasia AS franqueado, u.codigo AS loja, rf.tipo,
       ROUND(SUM(rf.valor),2) AS valor, SUM(rf.status = 'ABERTO') AS titulos_em_aberto
FROM receitas_franquia rf JOIN unidades u ON u.id = rf.loja_id LEFT JOIN franqueados f ON f.id = rf.franqueado_id
GROUP BY 1, 2, 3 ORDER BY 1, 3;

-- Custo de frete por loja (transferências do CD)
SELECT cd.codigo AS cd, lj.codigo AS loja, lj.distancia_cd_km AS km, COUNT(*) AS envios,
       ROUND(SUM(t.valor_transferencia),2) AS valor_transferido, ROUND(SUM(t.custo_frete),2) AS frete,
       ROUND(SUM(t.custo_frete) / SUM(t.valor_transferencia), 4) AS frete_sobre_valor
FROM transferencias t JOIN unidades cd ON cd.id = t.cd_id JOIN unidades lj ON lj.id = t.loja_id
GROUP BY t.loja_id ORDER BY frete_sobre_valor DESC;

-- Área de influência: faturamento por faixa de distância do cliente
SELECT u.codigo,
       CASE WHEN c.distancia_km < 1 THEN '0-1 km' WHEN c.distancia_km < 3 THEN '1-3 km'
            WHEN c.distancia_km < 5 THEN '3-5 km' ELSE '5+ km' END AS faixa,
       COUNT(DISTINCT c.id) AS clientes, COUNT(v.id) AS cupons, ROUND(SUM(v.valor_total),2) AS valor
FROM clientes c JOIN unidades u ON u.id = c.unidade_id LEFT JOIN vendas v ON v.cliente_id = c.id
GROUP BY u.codigo, faixa ORDER BY u.codigo, faixa;

-- Concorrentes a menos de 2 km de cada loja
SELECT u.codigo, u.nome, COUNT(*) AS concorrentes_2km, SUM(c.area_m2) AS area_concorrente
FROM concorrentes c JOIN unidades u ON u.id = c.loja_referencia_id
WHERE c.distancia_km <= 2 GROUP BY u.id ORDER BY 3 DESC;

-- Cidades candidatas sem loja (base para expansão)
SELECT c.nome, c.uf, c.regiao, c.populacao, c.renda_per_capita, c.supermercados_concorrentes,
       ROUND(c.populacao * 1.0 / c.supermercados_concorrentes) AS habitantes_por_supermercado
FROM cidades c WHERE c.id NOT IN (SELECT cidade_id FROM unidades)
ORDER BY c.populacao * c.renda_per_capita DESC;

-- Produtividade: faturamento por m² e por checkout (12 meses)
SELECT u.codigo, u.area_m2, u.checkouts, ROUND(SUM(r.valor_total)/u.area_m2, 2) AS faturamento_m2,
       ROUND(SUM(r.valor_total)/u.checkouts, 2) AS faturamento_checkout
FROM resumo_cupons_diario r JOIN unidades u ON u.id = r.unidade_id
WHERE r.data >= date((SELECT MAX(data) FROM resumo_cupons_diario), '-365 days')
GROUP BY u.id ORDER BY faturamento_m2 DESC;

-- Cesta: itens mais comprados junto com Pão Francês (últimos meses com itens)
WITH pao AS (SELECT DISTINCT i.venda_id FROM itens_venda i JOIN produtos p ON p.id = i.produto_id WHERE p.descricao = 'Pão Francês')
SELECT p.descricao, COUNT(*) AS cupons_juntos
FROM itens_venda i JOIN pao ON pao.venda_id = i.venda_id JOIN produtos p ON p.id = i.produto_id
WHERE p.descricao <> 'Pão Francês' GROUP BY 1 ORDER BY 2 DESC LIMIT 15;

-- Custo de pessoal sobre faturamento por loja (12 meses)
SELECT u.codigo, u.modelo,
       ROUND((SELECT SUM(custo_total) FROM folha_pagamento f WHERE f.unidade_id = u.id AND f.competencia >= '2025-11'), 2) AS pessoal,
       ROUND((SELECT SUM(valor_total) FROM resumo_cupons_diario r WHERE r.unidade_id = u.id AND r.data >= '2025-11-01'), 2) AS faturamento
FROM unidades u WHERE u.tipo = 'LOJA' ORDER BY 1;

