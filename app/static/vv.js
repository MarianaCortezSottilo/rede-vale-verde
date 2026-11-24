/* Helpers de formatação e gráficos (Chart.js). Paleta categórica validada (ordem fixa). */
const VV = (() => {
  const cores = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948'];
  const status = { bom: '#0ca30c', critico: '#d03b3b' };
  const fmtBRL = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
  const fmtNum = (c = 0) => new Intl.NumberFormat('pt-BR', { minimumFractionDigits: c, maximumFractionDigits: c });

  function brl(v) { return v == null ? '–' : fmtBRL.format(v); }
  function compacto(v) {
    if (v == null) return '–';
    const a = Math.abs(v);
    if (a >= 1e6) return 'R$ ' + fmtNum(2).format(v / 1e6) + ' mi';
    if (a >= 1e3) return 'R$ ' + fmtNum(0).format(v / 1e3) + ' mil';
    return 'R$ ' + fmtNum(0).format(v);
  }
  function fmt(v, tipo) {
    if (v == null) return '–';
    if (tipo === 'brl') return brl(v);
    if (tipo === 'pct') return fmtNum(1).format(v) + '%';
    if (tipo === 'num') return fmtNum(0).format(v);
    if (tipo === 'dec') return fmtNum(2).format(v);
    return v;
  }
  function eixo(tipo) {
    if (tipo === 'brl') return v => compacto(v);
    if (tipo === 'pct') return v => fmtNum(0).format(v) + '%';
    return v => fmtNum(0).format(v);
  }

  if (window.Chart) {
    Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", sans-serif';
    Chart.defaults.font.size = 12;
    Chart.defaults.color = '#52514e';
    Chart.defaults.borderColor = '#e1e0d9';
    Chart.defaults.plugins.legend.labels.boxWidth = 10;
    Chart.defaults.plugins.legend.labels.boxHeight = 10;
    Chart.defaults.plugins.tooltip.backgroundColor = '#fcfcfb';
    Chart.defaults.plugins.tooltip.titleColor = '#0b0b0b';
    Chart.defaults.plugins.tooltip.bodyColor = '#52514e';
    Chart.defaults.plugins.tooltip.borderColor = 'rgba(11,11,11,.12)';
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.maintainAspectRatio = false;
  }

  /* opts: {tipo:'bar'|'line', fmt:'brl'|'pct'|'num', horizontal, empilhado, legenda, min} */
  function grafico(id, labels, series, opts = {}) {
    const el = document.getElementById(id);
    if (!el) return null;
    if (!window.Chart) {   // sem Chart.js (offline): mostra aviso no lugar do gráfico
      el.parentElement.innerHTML = '<div class="muted" style="padding:20px">Gráfico indisponível: Chart.js não carregou (sem internet). Veja o README para usar a cópia local.</div>';
      return null;
    }
    const tipo = opts.tipo || 'bar';
    const ds = series.map((s, i) => {
      const cor = s.cor || cores[s.slot != null ? s.slot : i];
      const base = { label: s.nome, data: s.dados, borderColor: cor, backgroundColor: s.fundo || cor };
      if ((s.tipo || tipo) === 'bar') {
        Object.assign(base, { type: 'bar', borderRadius: 4, borderSkipped: 'start', maxBarThickness: 30,
                              borderWidth: 0, categoryPercentage: .8, barPercentage: .9 });
      } else {
        Object.assign(base, { type: 'line', borderWidth: 2, pointRadius: s.pontos ?? 0, pointHoverRadius: 5,
                              tension: .25, fill: s.preencher ?? false, spanGaps: false, borderDash: s.tracejado ? [5, 4] : [] });
      }
      if (s.cores) base.backgroundColor = s.cores;
      if (s.stack) base.stack = s.stack;
      if (s.ordem != null) base.order = s.ordem;
      return Object.assign(base, s.extra || {});
    });
    const iy = opts.horizontal ? 'x' : 'y';
    const ix = opts.horizontal ? 'y' : 'x';
    const escalas = {};
    escalas[iy] = { beginAtZero: opts.min == null, min: opts.min, stacked: !!opts.empilhado,
                    grid: { color: '#e1e0d9' }, border: { display: false }, ticks: { callback: eixo(opts.fmt) } };
    escalas[ix] = { stacked: !!opts.empilhado, grid: { display: false }, border: { color: '#c3c2b7' },
                    ticks: { autoSkip: true, maxRotation: 0 } };
    return new Chart(el, {
      type: tipo, data: { labels, datasets: ds },
      options: {
        indexAxis: opts.horizontal ? 'y' : 'x',
        interaction: { mode: opts.horizontal ? 'nearest' : 'index', intersect: false },
        scales: escalas,
        plugins: {
          legend: { display: opts.legenda ?? series.length > 1, position: 'top', align: 'start',
                    labels: { filter: it => !it.text.startsWith('_') } },
          tooltip: { filter: it => it.raw != null && !it.dataset.label?.startsWith('_'),
                     callbacks: { label: c => ` ${c.dataset.label || ''}: ${fmt(c.raw, opts.fmt)}` } },
        },
      },
    });
  }
  return { cores, status, brl, compacto, fmt, grafico, fmtNum };
})();
