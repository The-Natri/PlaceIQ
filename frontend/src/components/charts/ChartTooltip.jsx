import { useCallback, useRef, useState } from "react";

/**
 * Shared hover/focus tooltip for the SVG charts. Charts call show() with a
 * point in SVG viewBox units; it is converted to pixels inside the chart's
 * wrapper so the tooltip lines up at any screen width.
 * Tooltips only *enhance*: every value is also in the chart's table view.
 */
export function useChartTooltip(viewBoxWidth, viewBoxHeight) {
  const wrapRef = useRef(null);
  const [tip, setTip] = useState(null);

  const show = useCallback(
    (x, y, content) => {
      const box = wrapRef.current?.querySelector("svg")?.getBoundingClientRect();
      if (!box) return;
      setTip({
        left: (x / viewBoxWidth) * box.width,
        top: (y / viewBoxHeight) * box.height,
        content,
      });
    },
    [viewBoxWidth, viewBoxHeight]
  );
  const hide = useCallback(() => setTip(null), []);

  return { wrapRef, tip, show, hide };
}

export function ChartTooltip({ tip }) {
  if (!tip) return null;
  return (
    <div className="chart-tooltip" style={{ left: tip.left, top: tip.top }} role="status">
      {tip.content}
    </div>
  );
}

// Tooltip row: a short line in the series colour (not a filled box), then
// the value (strong) and its label.
export function TipRow({ color, value, label }) {
  return (
    <div>
      {color && <span className="tooltip-key" style={{ background: color }} />}
      <strong>{value}</strong> {label}
    </div>
  );
}
