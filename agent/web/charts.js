// ---------- Графики в ответах чата ----------
// Модель присылает спецификацию в блоке ```chart {...}``` (формат описан в
// agent/backend/claude_agent.py), здесь она превращается в SVG.
// Типы: line (динамика + прогноз), bar (сравнение категорий), scatter (связь).

const SVG_NS = "http://www.w3.org/2000/svg";
const MAX_SERIES = 4; // цвета назначаются по порядку, пятого слота нет
const MAX_POINTS = 300;

function svgEl(tag, attrs, text) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
  if (text !== undefined) el.textContent = text;
  return el;
}

function htmlEl(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

function toNum(v) {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function toNumArray(arr, n) {
  const out = [];
  for (let i = 0; i < n; i++) out.push(Array.isArray(arr) ? toNum(arr[i]) : null);
  return out;
}

function fmtNum(v) {
  if (v === null) return "—";
  const a = Math.abs(v);
  return v.toLocaleString(LOCALES[currentLang], {
    maximumFractionDigits: a < 10 ? 2 : a < 1000 ? 1 : 0,
  });
}

function niceTicks(min, max, count) {
  if (min === max) {
    min -= 1;
    max += 1;
  }
  const raw = (max - min) / (count || 4);
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
  const ticks = [];
  for (let v = Math.floor(min / step) * step; v <= Math.ceil(max / step) * step + step / 2; v += step) {
    ticks.push(Number(v.toFixed(10)));
  }
  return ticks;
}

function seriesColor(i) {
  return `var(--series-${i + 1})`;
}

function truncate(s, max) {
  return s.length > max ? s.slice(0, max - 1) + "…" : s;
}

// ---------- Каркас: заголовок, легенда, область графика, таблица ----------

function mountChart(host, spec) {
  const type = spec && spec.type;
  const draw = { line: drawLine, bar: drawBar, scatter: drawScatter }[type];
  if (!draw) throw new Error("unknown chart type");

  const fig = htmlEl("figure", "chart");
  if (spec.title) fig.appendChild(htmlEl("figcaption", "chart-title", String(spec.title)));
  if (spec.subtitle) fig.appendChild(htmlEl("div", "chart-sub", String(spec.subtitle)));

  const legend = htmlEl("div", "chart-legend");
  const plot = htmlEl("div", "chart-plot");
  const tip = htmlEl("div", "chart-tip");
  fig.append(legend, plot);
  host.replaceChildren(fig);

  const width = Math.max(300, Math.min(plot.clientWidth || 600, 720));
  const table = draw(spec, { plot, legend, tip, width });
  plot.appendChild(tip);
  if (!legend.childElementCount) legend.remove();

  const details = htmlEl("details", "chart-data");
  const summary = htmlEl("summary");
  summary.dataset.i18n = "chart_data";
  summary.textContent = t("chart_data");
  details.append(summary, buildTable(table));
  fig.appendChild(details);
}

function buildTable({ head, rows }) {
  const table = htmlEl("table");
  const trh = htmlEl("tr");
  head.forEach((h) => trh.appendChild(htmlEl("th", null, h)));
  table.appendChild(trh);
  rows.forEach((r) => {
    const tr = htmlEl("tr");
    r.forEach((c) => tr.appendChild(htmlEl("td", null, c)));
    table.appendChild(tr);
  });
  return table;
}

function legendItem(legend, kind, color, text, i18nKey) {
  const item = htmlEl("span", "chart-legend-item");
  const key = htmlEl("i", `chart-key ${kind}`);
  if (color) key.style.setProperty("--key", color);
  const label = htmlEl("span", null, text);
  if (i18nKey) label.dataset.i18n = i18nKey;
  item.append(key, label);
  legend.appendChild(item);
}

function showTip(ctx, svg, xView, yView, rows, heading) {
  const { tip, plot, width } = ctx;
  tip.replaceChildren();
  if (heading) tip.appendChild(htmlEl("div", "chart-tip-head", heading));
  rows.forEach((r) => {
    const row = htmlEl("div", "chart-tip-row");
    if (r.color) {
      const sw = htmlEl("i", "chart-key dot");
      sw.style.setProperty("--key", r.color);
      row.appendChild(sw);
    }
    row.appendChild(htmlEl("span", null, r.name));
    row.appendChild(htmlEl("b", null, r.value));
    tip.appendChild(row);
  });
  tip.classList.add("visible");
  const scale = svg.getBoundingClientRect().width / width;
  const px = xView * scale;
  const flip = px > plot.clientWidth / 2;
  tip.style.left = flip ? "" : `${px + 12}px`;
  tip.style.right = flip ? `${plot.clientWidth - px + 12}px` : "";
  tip.style.top = `${Math.max(0, yView * scale - 10)}px`;
}

function hideTip(ctx) {
  ctx.tip.classList.remove("visible");
}

// координата указателя в единицах viewBox
function pointerX(svg, e, width) {
  const rect = svg.getBoundingClientRect();
  return { x: ((e.clientX - rect.left) / rect.width) * width, y: ((e.clientY - rect.top) / rect.width) * width };
}

function drawYAxis(svg, ticks, y, left, right) {
  ticks.forEach((v) => {
    svg.appendChild(svgEl("line", { x1: left, x2: right, y1: y(v), y2: y(v), class: "chart-grid" }));
    svg.appendChild(svgEl("text", { x: left - 8, y: y(v) + 4, class: "chart-tick", "text-anchor": "end" }, fmtNum(v)));
  });
}

// ---------- line: динамика, прогноз пунктиром с диапазоном ----------

function drawLine(spec, ctx) {
  const labels = (Array.isArray(spec.x) ? spec.x : []).slice(0, MAX_POINTS).map(String);
  const n = labels.length;
  const series = (Array.isArray(spec.series) ? spec.series : []).slice(0, MAX_SERIES).map((s, i) => ({
    name: String(s.name || ""),
    color: seriesColor(i),
    values: toNumArray(s.values, n),
    forecast: toNumArray(s.forecast, n),
    low: toNumArray(s.low, n),
    high: toNumArray(s.high, n),
  }));
  const all = series.flatMap((s) => [...s.values, ...s.forecast, ...s.low, ...s.high]).filter((v) => v !== null);
  if (!n || !all.length) throw new Error("empty chart");

  const W = ctx.width;
  const H = 260;
  const m = { t: spec.y_label ? 26 : 12, r: 16, b: 30, l: 56 };
  const ticks = niceTicks(Math.min(...all), Math.max(...all), 4);
  const y = (v) => m.t + (H - m.t - m.b) * (1 - (v - ticks[0]) / (ticks[ticks.length - 1] - ticks[0]));
  const x0 = m.l + 14;
  const x1 = W - m.r - 14;
  const x = (i) => (n === 1 ? (x0 + x1) / 2 : x0 + (i * (x1 - x0)) / (n - 1));

  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart-svg", role: "img" });
  if (spec.title) svg.setAttribute("aria-label", String(spec.title));

  // зона прогноза — до сетки, чтобы лежала под всем остальным
  const fi = labels.findIndex((_, i) => series.some((s) => s.forecast[i] !== null));
  if (fi >= 0) {
    const zx = fi > 0 ? (x(fi - 1) + x(fi)) / 2 : m.l;
    svg.appendChild(svgEl("rect", { x: zx, y: m.t, width: W - m.r - zx, height: H - m.t - m.b, class: "chart-zone" }));
    const zl = svgEl("text", { x: zx + 6, y: m.t + 13, class: "chart-tick" }, t("chart_forecast"));
    zl.dataset.i18n = "chart_forecast";
    svg.appendChild(zl);
  }

  drawYAxis(svg, ticks, y, m.l, W - m.r);
  if (spec.y_label) svg.appendChild(svgEl("text", { x: 0, y: 12, class: "chart-tick" }, String(spec.y_label)));
  const every = Math.ceil(n / Math.max(2, Math.floor((x1 - x0) / 56)));
  labels.forEach((lab, i) => {
    if (i % every === 0 || i === n - 1) {
      svg.appendChild(svgEl("text", { x: x(i), y: H - 10, class: "chart-tick", "text-anchor": "middle" }, lab));
    }
  });

  const pathOf = (pts) => pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join("");

  series.forEach((s) => {
    let lastActual = -1;
    s.values.forEach((v, i) => {
      if (v !== null) lastActual = i;
    });
    const fc = s.forecast.map((v, i) => (v !== null ? i : -1)).filter((i) => i >= 0);

    // диапазон прогноза — полупрозрачная заливка от последней фактической точки
    const band = fc.filter((i) => s.low[i] !== null && s.high[i] !== null);
    if (band.length) {
      const start = lastActual >= 0 && lastActual < band[0] ? [[x(lastActual), y(s.values[lastActual])]] : [];
      const upper = band.map((i) => [x(i), y(s.high[i])]);
      const lower = band.map((i) => [x(i), y(s.low[i])]).reverse();
      svg.appendChild(
        svgEl("path", { d: pathOf([...start, ...upper, ...lower]) + "Z", fill: s.color, class: "chart-band" })
      );
    }

    // факт — сплошная линия, разрывается на пропусках
    let run = [];
    const flush = () => {
      if (run.length > 1) svg.appendChild(svgEl("path", { d: pathOf(run), stroke: s.color, class: "chart-line" }));
      run = [];
    };
    s.values.forEach((v, i) => (v === null ? flush() : run.push([x(i), y(v)])));
    flush();

    // прогноз — пунктир, продолжает последнюю фактическую точку
    if (fc.length) {
      const pts = fc.map((i) => [x(i), y(s.forecast[i])]);
      if (lastActual >= 0 && lastActual < fc[0]) pts.unshift([x(lastActual), y(s.values[lastActual])]);
      if (pts.length > 1) {
        svg.appendChild(svgEl("path", { d: pathOf(pts), stroke: s.color, class: "chart-line forecast" }));
      }
    }

    s.values.forEach((v, i) => {
      if (v !== null) svg.appendChild(svgEl("circle", { cx: x(i), cy: y(v), r: 4, fill: s.color, class: "chart-dot" }));
    });
    fc.forEach((i) => {
      svg.appendChild(
        // цвет контура — через style: правило .chart-dot в CSS перекрыло бы атрибут stroke
        svgEl("circle", { cx: x(i), cy: y(s.forecast[i]), r: 4, style: `stroke:${s.color}`, class: "chart-dot hollow" })
      );
    });
  });

  // наведение: вертикаль + подсказка по ближайшему году
  const cross = svgEl("line", { y1: m.t, y2: H - m.b, class: "chart-cross" });
  svg.appendChild(cross);
  const cellText = (s, i) => {
    if (s.values[i] !== null) return fmtNum(s.values[i]);
    if (s.forecast[i] === null) return "—";
    const range = s.low[i] !== null && s.high[i] !== null ? ` (${fmtNum(s.low[i])} – ${fmtNum(s.high[i])})` : "";
    return `≈ ${fmtNum(s.forecast[i])}${range}`;
  };
  svg.addEventListener("pointermove", (e) => {
    const p = pointerX(svg, e, W);
    let i = n === 1 ? 0 : Math.round(((p.x - x0) / (x1 - x0)) * (n - 1));
    i = Math.max(0, Math.min(n - 1, i));
    cross.setAttribute("x1", x(i));
    cross.setAttribute("x2", x(i));
    cross.classList.add("visible");
    const isForecast = fi >= 0 && i >= fi;
    showTip(
      ctx,
      svg,
      x(i),
      m.t,
      series.map((s) => ({ color: s.color, name: s.name, value: cellText(s, i) })),
      isForecast ? `${labels[i]} · ${t("chart_forecast")}` : labels[i]
    );
  });
  svg.addEventListener("pointerleave", () => {
    cross.classList.remove("visible");
    hideTip(ctx);
  });

  if (series.length > 1) series.forEach((s) => legendItem(ctx.legend, "line", s.color, s.name));
  if (fi >= 0 && series.length > 1) legendItem(ctx.legend, "dash", null, t("chart_forecast"), "chart_forecast");

  ctx.plot.appendChild(svg);
  return {
    head: [String(spec.x_label || ""), ...series.map((s) => s.name || String(spec.y_label || ""))],
    rows: labels.map((lab, i) => [lab, ...series.map((s) => cellText(s, i))]),
  };
}

// ---------- bar: сравнение категорий, горизонтальные столбцы ----------

function drawBar(spec, ctx) {
  const labels = (Array.isArray(spec.x) ? spec.x : []).slice(0, 40).map(String);
  const n = labels.length;
  const first = (Array.isArray(spec.series) ? spec.series : [])[0] || {};
  const values = toNumArray(first.values, n);
  const present = values.filter((v) => v !== null);
  if (!n || !present.length) throw new Error("empty chart");

  const W = ctx.width;
  const rowH = 26;
  const barH = 14;
  const charW = 7.4; // с запасом под кириллицу и казахские буквы, чтобы подпись не обрезалась зря
  const labelW = Math.min(Math.round(W * 0.38), Math.max(...labels.map((l) => l.length)) * charW + 12);
  const m = { t: 6, r: 64, b: 6, l: labelW };
  const H = m.t + n * rowH + m.b;
  const lo = Math.min(0, ...present);
  const hi = Math.max(0, ...present);
  const x = (v) => m.l + ((W - m.l - m.r) * (v - lo)) / (hi - lo || 1);
  const maxChars = Math.max(4, Math.floor((labelW - 12) / charW));

  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart-svg", role: "img" });
  if (spec.title) svg.setAttribute("aria-label", String(spec.title));
  const name = String(first.name || spec.y_label || "");

  labels.forEach((lab, i) => {
    const top = m.t + i * rowH;
    const yb = top + (rowH - barH) / 2;
    const g = svgEl("g", { class: "chart-row" });
    g.appendChild(svgEl("rect", { x: 0, y: top, width: W, height: rowH, class: "chart-hit" }));
    const text = svgEl("text", { x: m.l - 8, y: top + rowH / 2 + 4, class: "chart-label", "text-anchor": "end" }, truncate(lab, maxChars));
    g.appendChild(text);

    const v = values[i];
    if (v !== null) {
      const a = x(0);
      const b = x(v);
      const w = Math.abs(b - a);
      const r = Math.min(4, w); // скругляется только конец с данными, у базовой линии — прямой
      const d =
        v >= 0
          ? `M${a},${yb}H${b - r}Q${b},${yb} ${b},${yb + r}V${yb + barH - r}Q${b},${yb + barH} ${b - r},${yb + barH}H${a}Z`
          : `M${a},${yb}H${b + r}Q${b},${yb} ${b},${yb + r}V${yb + barH - r}Q${b},${yb + barH} ${b + r},${yb + barH}H${a}Z`;
      g.appendChild(svgEl("path", { d, fill: seriesColor(0) }));
      g.appendChild(
        svgEl(
          "text",
          { x: v >= 0 ? b + 6 : b - 6, y: top + rowH / 2 + 4, class: "chart-value", "text-anchor": v >= 0 ? "start" : "end" },
          fmtNum(v)
        )
      );
    }
    g.addEventListener("pointermove", () => {
      showTip(ctx, svg, Math.max(x(v === null ? 0 : v), m.l), top, [{ color: seriesColor(0), name, value: fmtNum(v) }], lab);
    });
    g.addEventListener("pointerleave", () => hideTip(ctx));
    svg.appendChild(g);
  });
  svg.appendChild(svgEl("line", { x1: x(0), x2: x(0), y1: m.t, y2: H - m.b, class: "chart-axis" }));

  ctx.plot.appendChild(svg);
  return { head: [String(spec.x_label || ""), name], rows: labels.map((lab, i) => [lab, fmtNum(values[i])]) };
}

// ---------- scatter: связь двух показателей, опционально линия тренда ----------

function drawScatter(spec, ctx) {
  const points = (Array.isArray(spec.points) ? spec.points : [])
    .slice(0, MAX_POINTS)
    .map((p) => ({ x: toNum(p && p.x), y: toNum(p && p.y), label: p && p.label ? String(p.label) : "" }))
    .filter((p) => p.x !== null && p.y !== null);
  if (!points.length) throw new Error("empty chart");

  const W = ctx.width;
  const H = 300;
  const m = { t: spec.y_label ? 26 : 12, r: 16, b: spec.x_label ? 46 : 30, l: 56 };
  const xt = niceTicks(Math.min(...points.map((p) => p.x)), Math.max(...points.map((p) => p.x)), 5);
  const yt = niceTicks(Math.min(...points.map((p) => p.y)), Math.max(...points.map((p) => p.y)), 4);
  const x = (v) => m.l + ((W - m.l - m.r) * (v - xt[0])) / (xt[xt.length - 1] - xt[0]);
  const y = (v) => m.t + (H - m.t - m.b) * (1 - (v - yt[0]) / (yt[yt.length - 1] - yt[0]));

  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart-svg", role: "img" });
  if (spec.title) svg.setAttribute("aria-label", String(spec.title));

  drawYAxis(svg, yt, y, m.l, W - m.r);
  xt.forEach((v) => {
    svg.appendChild(svgEl("text", { x: x(v), y: H - m.b + 18, class: "chart-tick", "text-anchor": "middle" }, fmtNum(v)));
  });
  if (spec.y_label) svg.appendChild(svgEl("text", { x: 0, y: 12, class: "chart-tick" }, String(spec.y_label)));
  if (spec.x_label) {
    svg.appendChild(
      svgEl("text", { x: (m.l + W - m.r) / 2, y: H - 6, class: "chart-tick", "text-anchor": "middle" }, String(spec.x_label))
    );
  }

  const slope = toNum(spec.fit && spec.fit.slope);
  const intercept = toNum(spec.fit && spec.fit.intercept);
  if (slope !== null && intercept !== null) {
    const clipId = `clip-${Math.random().toString(36).slice(2)}`;
    const clip = svgEl("clipPath", { id: clipId });
    clip.appendChild(svgEl("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b }));
    svg.appendChild(clip);
    const a = xt[0];
    const b = xt[xt.length - 1];
    svg.appendChild(
      svgEl("line", {
        x1: x(a),
        y1: y(intercept + slope * a),
        x2: x(b),
        y2: y(intercept + slope * b),
        class: "chart-fit",
        "clip-path": `url(#${clipId})`,
      })
    );
    legendItem(ctx.legend, "fit", null, t("chart_trend"), "chart_trend");
  }

  const dots = points.map((p) => {
    const c = svgEl("circle", { cx: x(p.x), cy: y(p.y), r: 4, fill: seriesColor(0), class: "chart-dot" });
    svg.appendChild(c);
    return c;
  });

  const xName = String(spec.x_label || "x");
  const yName = String(spec.y_label || "y");
  let active = null;
  const clear = () => {
    if (active) active.classList.remove("active");
    active = null;
    hideTip(ctx);
  };
  svg.addEventListener("pointermove", (e) => {
    const ptr = pointerX(svg, e, W);
    let best = -1;
    let bestD = 28 * 28; // зона захвата больше самой точки
    points.forEach((p, i) => {
      const d = (x(p.x) - ptr.x) ** 2 + (y(p.y) - ptr.y) ** 2;
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    });
    if (best < 0) return clear();
    if (active !== dots[best]) {
      if (active) active.classList.remove("active");
      active = dots[best];
      active.classList.add("active");
    }
    const p = points[best];
    showTip(
      ctx,
      svg,
      x(p.x),
      y(p.y),
      [
        { name: xName, value: fmtNum(p.x) },
        { name: yName, value: fmtNum(p.y) },
      ],
      p.label
    );
  });
  svg.addEventListener("pointerleave", clear);

  ctx.plot.appendChild(svg);
  const hasLabels = points.some((p) => p.label);
  return {
    head: [...(hasLabels ? [""] : []), xName, yName],
    rows: points.map((p) => [...(hasLabels ? [p.label] : []), fmtNum(p.x), fmtNum(p.y)]),
  };
}
