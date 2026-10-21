import { useMemo, useState } from "react";
import { ChartTooltip, TipRow, useChartTooltip } from "./ChartTooltip";
import { formatCgpa, toNumber } from "../../utils/format";

const W = 520;
const H = 290;
const M = { top: 14, right: 16, bottom: 42, left: 44 };
const SERIES = [
  { key: "Placed", label: "Placed", color: "var(--viz-series-1)" },
  { key: "Not Placed", label: "Not placed", color: "var(--viz-series-2)" },
];

// Small, stable vertical offset per student so dots that share the same
// whole-number backlog count don't sit exactly on top of each other.
function jitter(id) {
  const x = Math.sin(id * 12.9898) * 43758.5453;
  return (x - Math.floor(x) - 0.5) * 0.5;
}

/**
 * Scatter of every student: CGPA across, backlogs up, coloured by whether
 * they were placed. Hover finds the nearest dot (no pixel-hunting).
 */
export function CgpaScatter({ students }) {
  const { wrapRef, tip, show, hide } = useChartTooltip(W, H);
  const [activeId, setActiveId] = useState(null);

  const points = useMemo(() => {
    const maxBacklogs = Math.max(2, ...students.map((s) => s.backlogs)) + 0.5;
    const x = (cgpa) => M.left + ((cgpa - 4) / 6) * (W - M.left - M.right);
    const y = (b) => H - M.bottom - (b / maxBacklogs) * (H - M.top - M.bottom);
    return {
      maxBacklogs,
      x,
      y,
      dots: students.map((s) => {
        const cgpa = toNumber(s.cgpa);
        return {
          ...s,
          cgpa,
          cx: x(Math.max(4, cgpa)),
          cy: y(Math.max(0, s.backlogs + jitter(s.student_id))),
        };
      }),
    };
  }, [students]);

  function onMove(event) {
    const svg = event.currentTarget;
    const box = svg.getBoundingClientRect();
    const px = ((event.clientX - box.left) / box.width) * W;
    const py = ((event.clientY - box.top) / box.height) * H;
    let best = null;
    let bestDist = Infinity;
    for (const d of points.dots) {
      const dist = (d.cx - px) ** 2 + (d.cy - py) ** 2;
      if (dist < bestDist) { bestDist = dist; best = d; }
    }
    if (best && bestDist <= 22 ** 2) {
      setActiveId(best.student_id);
      const series = SERIES.find((s) => s.key === best.placement_status);
      show(best.cx, best.cy, (
        <>
          <TipRow color={series.color} value={series.label} label="" />
          <div>CGPA <strong>{formatCgpa(best.cgpa)}</strong> · {best.backlogs} backlog{best.backlogs === 1 ? "" : "s"}</div>
          <div className="muted" style={{ color: "#cbd5e1" }}>Student #{best.student_id}</div>
        </>
      ));
    } else {
      setActiveId(null);
      hide();
    }
  }

  const counts = SERIES.map((s) => ({ ...s, n: students.filter((d) => d.placement_status === s.key).length }));
  const yTicks = Array.from({ length: Math.floor(points.maxBacklogs) + 1 }, (_, i) => i);
  const xTicks = [4, 5, 6, 7, 8, 9, 10];

  return (
    <div className="chart" ref={wrapRef}>
      <div className="chart-legend" aria-hidden="true">
        {counts.map((s) => (
          <span key={s.key} className="legend-item">
            <span className="legend-swatch" style={{ background: s.color }} /> {s.label} ({s.n})
          </span>
        ))}
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Scatter plot of ${students.length} students: CGPA against backlogs, coloured by placement outcome. A table of the same data by CGPA band follows.`}
        onPointerMove={onMove}
        onPointerLeave={() => { setActiveId(null); hide(); }}
      >
        {yTicks.map((t) => (
          <g key={`y${t}`}>
            <line className="gridline" x1={M.left} x2={W - M.right} y1={points.y(t)} y2={points.y(t)} />
            <text x={M.left - 8} y={points.y(t)} textAnchor="end" dominantBaseline="middle">{t}</text>
          </g>
        ))}
        {xTicks.map((t) => (
          <text key={`x${t}`} x={points.x(t)} y={H - M.bottom + 16} textAnchor="middle">{t}</text>
        ))}
        <line className="baseline" x1={M.left} x2={W - M.right} y1={H - M.bottom} y2={H - M.bottom} />
        <text className="axis-label" x={(M.left + W - M.right) / 2} y={H - 6} textAnchor="middle">CGPA</text>
        <text className="axis-label" transform={`translate(12 ${(M.top + H - M.bottom) / 2}) rotate(-90)`} textAnchor="middle">Backlogs</text>

        {points.dots.map((d) => {
          const series = SERIES.find((s) => s.key === d.placement_status) || SERIES[1];
          return (
            <circle
              key={d.student_id}
              className={`mark ${activeId === d.student_id ? "is-active" : ""}`}
              cx={d.cx}
              cy={d.cy}
              r={4.5}
              fill={series.color}
              fillOpacity={0.85}
              stroke="var(--viz-surface)"
              strokeWidth={1.5}
            />
          );
        })}
      </svg>
      <ChartTooltip tip={tip} />
    </div>
  );
}
