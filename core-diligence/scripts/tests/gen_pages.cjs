/* 测试专用：按编译出的 pages.json 生成正文页 HTML（每个 panel 一个区域，绑定节点用引擎的 content.html 生成）。
   用法：node gen_pages.cjs <report-forge 目录> <pages.json> <输出.html> */
const [RF, pagesFile, out] = process.argv.slice(2);
const fs = require('fs'), C = require(RF + '/scripts/content_contract.cjs');
const pages = JSON.parse(fs.readFileSync(pagesFile)).pages;
const b = (p, k, o) => C.html(p, k, o || {});
const html = pages.map(p => {
  const comp = p.composition || {panels: {}};
  const placed = new Set();
  const metrics = p.content.metrics || [];
  const panels = (p.regions || []).map(r => {
    const panel = comp.panels[r.panelRef] || {claimRefs: []};
    const parts = [];
    if (panel.form === 'svg.custom') {
      const nums = metrics.filter(m => typeof m.value === 'number' && m.unit === (metrics[0] || {}).unit);
      const max = Math.max(1, ...nums.map(m => m.value));
      const bars = nums.map((m, i) => `<rect x="${60 + i * 160}" y="${260 - m.value / max * 200}" width="110" height="${m.value / max * 200}" fill="#1f3a5f"/>` +
        `<text x="${115 + i * 160}" y="${250 - m.value / max * 200}" text-anchor="middle" font-size="18" data-content-key="metric:${m.id}">${m.text}</text>`).join('');
      nums.forEach(m => placed.add('metric:' + m.id));
      const svg = bars || '<line x1="40" x2="460" y1="150" y2="150" stroke="#1f3a5f" stroke-width="3"/><circle cx="120" cy="150" r="10" fill="#1f3a5f"/><circle cx="380" cy="150" r="10" fill="#1f3a5f"/><text x="120" y="190" text-anchor="middle" font-size="18">成立</text><text x="380" y="190" text-anchor="middle" font-size="18">首款产品</text>';
      parts.push(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 300" width="520" height="300" role="img" aria-label="${panel.visual || '图示'}">${bars ? '<line x1="40" x2="500" y1="260" y2="260" stroke="#9aa5b1"/>' : ''}${svg}</svg>`);
    }
    if (panel.form === 'html.kpi') {
      const ms = metrics.filter(m => !placed.has('metric:' + m.id));
      ms.forEach(m => placed.add('metric:' + m.id));
      parts.push(`<div class="kpi-card"><div class="kpi-label">${panel.visual || '关键指标'}</div><div class="kpi-value">${ms.map(m => b(p, 'metric:' + m.id, {tag: 'span'})).join(' ')}</div></div>`);
    }
    for (const cid of panel.claimRefs || []) {
      if (placed.has('claim:' + cid)) continue;
      placed.add('claim:' + cid); placed.add('limitation:' + cid);
      parts.push(b(p, 'claim:' + cid, {tag: 'p'}), b(p, 'limitation:' + cid, {tag: 'p', className: 'limit'}));
    }
    return `<div data-panel-id="${r.panelRef}" class="panel span-${r.span || 1}">${parts.join('')}</div>`;
  });
  const leftover = metrics.filter(m => !placed.has('metric:' + m.id)).map(m => b(p, 'metric:' + m.id, {tag: 'span'})).join('；');
  const claimsLeft = (p.content.claims || []).filter(c => !placed.has('claim:' + c.id)).map(c => b(p, 'claim:' + c.id, {tag: 'p'}) + b(p, 'limitation:' + c.id, {tag: 'p', className: 'limit'})).join('');
  const keys = (p.content.sources || []).map(s => 'source:' + s.key);
  return `<section class="slide reading" data-page-id="${p.id}" data-frame-boundary="line">
 <header class="slide__header">${b(p, 'title', {tag: 'h1', className: 'slide__title'})}<p class="slide__lead">合并口径｜基准日见封面</p></header>
 <div class="slide__body grid">${panels.join('')}</div>
 ${leftover || claimsLeft ? `<div class="extra">${leftover}${claimsLeft}</div>` : ''}
 <div class="takeaway" data-reading-role="takeaway">${p.proves}</div>
 <footer class="slide__source">来源：${keys.length ? b(p, keys.length === 1 ? keys[0] : keys, {tag: 'span'}) : ''}</footer>
</section>`;
}).join('\n');
fs.writeFileSync(out, html);
