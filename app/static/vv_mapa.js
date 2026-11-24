/* Helpers de mapa (Leaflet + fundos Esri/OpenStreetMap, sem chave de API). Requer internet para os mapas de fundo. */
const VVMapa = (() => {
  const SEQ = ['#e9f2fd', '#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#1c5cab', '#123e75'];
  const cores = { loja: '#2a78d6', franquia: '#eb6834', cd: '#1baf7a', sede: '#6250d6', concorrente: '#898781',
                  ruim: '#d03b3b', neutro: '#c3c2b7', bom: '#2a78d6' };

  function criar(id, centro = [-15.8, -50], zoom = 4) {
    const el = document.getElementById(id);
    if (!window.L) {
      el.innerHTML = '<div class="muted" style="padding:20px">Mapa indisponível: a biblioteca Leaflet não carregou (sem internet).</div>';
      return null;
    }
    const m = L.map(id, { scrollWheelZoom: true, preferCanvas: true }).setView(centro, zoom);
    // Fundos sem chave de API. O primeiro é o padrão; o controle no canto permite trocar.
    const fundos = {
      'Cinza claro (Esri)': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors', maxZoom: 16 }),
      'OpenStreetMap': L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors', maxZoom: 19 }),
      'Ruas (Esri)': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Tiles &copy; Esri', maxZoom: 19 }),
    };
    const padrao = fundos['Cinza claro (Esri)'].addTo(m);
    // se o fundo padrão falhar várias vezes, troca automaticamente para o OpenStreetMap
    let falhas = 0;
    padrao.on('tileerror', () => { if (++falhas === 6 && m.hasLayer(padrao)) { m.removeLayer(padrao); fundos['OpenStreetMap'].addTo(m); } });
    L.control.layers(fundos, null, { position: 'topleft', collapsed: true }).addTo(m);
    return m;
  }

  /* escala sequencial: valor -> cor (quantis do vetor de referência) */
  function escalaSeq(valores, paleta = SEQ) {
    const v = valores.filter(x => x != null && isFinite(x)).sort((a, b) => a - b);
    const qs = paleta.map((_, i) => v[Math.min(v.length - 1, Math.floor(i / paleta.length * v.length))]);
    const f = x => { if (x == null || !isFinite(x)) return '#e1e0d9'; let k = 0; for (let i = 0; i < qs.length; i++) if (x >= qs[i]) k = i; return paleta[k]; };
    f.limites = qs;
    return f;
  }
  /* divergente em torno de um ponto médio: abaixo = vermelho, acima = azul */
  function escalaDiv(min, meio, max) {
    const neg = ['#a82a2a', '#d03b3b', '#e98c8c', '#f3c6c6'];
    const pos = ['#cde2fb', '#86b6ef', '#3987e5', '#1c5cab'];
    return x => {
      if (x == null || !isFinite(x)) return '#e1e0d9';
      if (x < meio) { const t = Math.min(1, (meio - x) / Math.max(meio - min, 1e-9)); return neg[Math.max(0, 3 - Math.floor(t * 3.999))]; }
      const t = Math.min(1, (x - meio) / Math.max(max - meio, 1e-9)); return pos[Math.min(3, Math.floor(t * 3.999))];
    };
  }
  function legenda(mapa, html, pos = 'bottomright') {
    if (!mapa) return null;
    const c = L.control({ position: pos });
    c.onAdd = () => { const d = L.DomUtil.create('div', 'legenda-mapa'); d.innerHTML = html; return d; };
    c.addTo(mapa);
    return c;
  }
  /* GeoJSON dos estados (API de malhas do IBGE). Chama cb(geojson) ou cb(null) se não houver internet. */
  let _uf = null;
  async function estados(cb) {
    if (_uf) return cb(_uf);
    const urls = ['https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=UF'];
    for (const u of urls) {
      try { const r = await fetch(u); if (r.ok) { _uf = await r.json(); return cb(_uf); } } catch (e) { /* tenta a próxima */ }
    }
    cb(null);
  }
  function raioBolha(v, vmax, rmin = 6, rmax = 30) { return v > 0 ? rmin + (rmax - rmin) * Math.sqrt(v / vmax) : rmin; }
  return { criar, escalaSeq, escalaDiv, legenda, estados, raioBolha, cores, SEQ };
})();
