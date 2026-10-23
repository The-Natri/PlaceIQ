import { useState } from "react";
import { ChartTooltip, TipRow, useChartTooltip } from "./ChartTooltip";
import { formatMonth, toNumber } from "../../utils/format";

const W = 560;
const H = 240;
const M = { top: 16, right: 18, bottom: 34, left: 40 };

// Round the axis top up to a tidy value (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10 x a power of ten).
function niceMax(v) {
  if (v <= 4) return 4;
  const pow = 10 ** Math.floor(Math.log10(v));
  const nice = [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].find((m) => m * pow >= v);
  return nice * pow;
}

function ticks(max) {
  const step = max / 4;
  return [0, 1, 2, 3, 4].map((i) => Math.round(i * step));
}

function Axes({ max, y, labels, x }) {
  return (
    <>
      {ticks(max).map((t) => (
        <g key={t}>
          <line className="gridline" x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} />
          <text x={M.left - 8} y={y(t)} textAnchor="end" dominantBaseline="middle">{t}</text>
        </g>
      ))}
      <line className="baseline" x1={M.left} x2={W - M.right} y1={y(0)} y2={y(0)} />
      {labels.map((l, i) =>
        l ? <text key={i} x={x(i)} y={H - M.bottom + 16} textAnchor="middle">{l}</text> : null
      )}
    </>
  );
}

// A bar whose top corners are rounded (4px) and whose base sits flat on the
// baseline.
function barPath(x, y, w, h) {
  const r = Math.min(4, w / 2, h);
  return `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h} Z`;
}

/** Offers per month: one series, one colour, each bar hoverable and focusable. */
export function MonthlyOffersChart({ rows }) {
  const { wrapRef, tip, show, hide } = useChartTooltip(W, H);
  const [active, setActive] = useState(null);
  const values = rows.map((r) => r.offers_in_month);
  const max = niceMax(Math.max(1, ...values));
  const band = (W - M.left - M.right) / rows.length;
  const x = (i) => M.left + band * i + band / 2;
  const y = (v) => H - M.bottom - (v / max) * (H - M.top - M.bottom);
  const barW = Math.max(6, band - 2); // 2px surface gap between neighbouring bars
  // With many months, label every other one so labels never collide.
  const labels = rows.map((r, i) => (rows.length > 8 && i % 2 ? "" : formatMonth(r.month)));

  function focusBar(i) {
    const r = rows[i];
    setActive(i);
    show(x(i), y(r.offers_in_month), <TipRow color="var(--viz-series-1)" value={r.offers_in_month} label={`offers · ${formatMonth(r.month)}`} />);
  }

  return (
    <div className="chart" ref={wrapRef}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Bar chart of offers made each month. The same numbers are in the table below.">
        <Axes max={max} y={y} x={x} labels={labels} />
        {rows.map((r, i) => {
          const h = Math.max(0, y(0) - y(r.offers_in_month));
          return (
            <g key={r.month}>
              <path
                className={`mark ${active === i ? "is-active" : ""}`}
                d={barPath(x(i) - barW / 2, y(r.offers_in_month), barW, h)}
                fill="var(--viz-series-1)"
              />
              {/* Hit area: the whole column, so short bars are easy to hover. */}
              <rect
                className="hit"
                x={x(i) - band / 2}
                y={M.top}
                width={band}
                height={H - M.top - M.bottom}
                tabIndex={0}
                aria-label={`${formatMonth(r.month)}: ${r.offers_in_month} offers`}
                onPointerEnter={() => focusBar(i)}
                onFocus={() => focusBar(i)}
                onPointerLeave={() => { setActive(null); hide(); }}
                onBlur={() => { setActive(null); hide(); }}
              />
            </g>
          );
        })}
      </svg>
      <ChartTooltip tip={tip} />
    </div>
  );
}

/** Running total of offers: a 2px line with a crosshair that snaps to the nearest month. */
export function CumulativeOffersChart({ rows }) {
  const { wrapRef, tip, show, hide } = useChartTooltip(W, H);
  const [active, setActive] = useState(null);
  const values = rows.map((r) => toNumber(r.cumulative_offers));
  const max = niceMax(Math.max(1, ...values));
  const step = rows.length > 1 ? (W - M.left - M.right - 20) / (rows.length - 1) : 0;
  const x = (i) => M.left + 10 + step * i;
  const y = (v) => H - M.bottom - (v / max) * (H - M.top - M.bottom);
  const labels = rows.map((r, i) => (rows.length > 8 && i % 2 ? "" : formatMonth(r.month)));
  const line = values.map((v, i) => `${i ? "L" : "M"}${x(i)},${y(v)}`).join(" ");
  const last = values.length - 1;

  function snap(event) {
    const box = event.currentTarget.getBoundingClientRect();
    const px = ((event.clientX - box.left) / box.width) * W;
    const i = Math.min(last, Math.max(0, Math.round((px - M.left - 10) / (step || 1))));
    setActive(i);
    show(x(i), y(values[i]), (
      <>
        <TipRow color="var(--viz-series-1)" value={values[i]} label="offers so far" />
        <div>by end of {formatMonth(rows[i].month)} (+{rows[i].offers_in_month} that month)</div>
      </>
    ));
  }

  return (
    <div className="chart" ref={wrapRef}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label="Line chart of the running total of offers by month. The same numbers are in the table below."
        onPointerMove={snap}
        onPointerLeave={() => { setActive(null); hide(); }}
      >
        <Axes max={max} y={y} x={x} labels={labels} />
        {active !== null && (
          <line x1={x(active)} x2={x(active)} y1={M.top} y2={y(0)} stroke="var(--viz-axis)" strokeWidth={1} />
        )}
        <path d={line} fill="none" stroke="var(--viz-series-1)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {values.map((v, i) => (
          <circle
            key={rows[i].month}
            className={`mark ${active === i ? "is-active" : ""}`}
            cx={x(i)}
            cy={y(v)}
            r={4}
            fill="var(--viz-series-1)"
            stroke="var(--viz-surface)"
            strokeWidth={2}
          />
        ))}
        {/* Direct label on the endpoint only — the total so far. */}
        {last >= 0 && (
          <text x={x(last) - 6} y={y(values[last]) - 10} textAnchor="end" style={{ fill: "var(--c-text)", fontWeight: 650 }}>
            {values[last]} offers
          </text>
        )}
      </svg>
      <ChartTooltip tip={tip} />
    </div>
  );
}
