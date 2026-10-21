// The API sends Postgres NUMERIC values as strings ("8.50") to keep them
// exact (see docs/API.md); convert before doing maths or comparing.
export function toNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

export function formatLpa(value) {
  const n = toNumber(value);
  return n === null ? "—" : `₹${n.toFixed(2)} LPA`;
}

export function formatCgpa(value) {
  const n = toNumber(value);
  return n === null ? "—" : n.toFixed(2);
}

export function formatPercent(value, digits = 1) {
  const n = toNumber(value);
  return n === null ? "—" : `${n.toFixed(digits)}%`;
}

const DATE_FMT = new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" });
const DATETIME_FMT = new Intl.DateTimeFormat("en-IN", {
  day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
});
const MONTH_FMT = new Intl.DateTimeFormat("en-IN", { month: "short", year: "numeric" });

// Date-only values ("2026-02-13") are parsed as local dates, not UTC
// midnight, so they never show up as the previous day.
function parse(value) {
  if (!value) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [y, m, d] = value.split("-").map(Number);
    return new Date(y, m - 1, d);
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDate(value) {
  const d = parse(value);
  return d ? DATE_FMT.format(d) : "—";
}

export function formatDateTime(value) {
  const d = parse(value);
  return d ? DATETIME_FMT.format(d) : "—";
}

export function formatMonth(value) {
  const d = parse(value);
  return d ? MONTH_FMT.format(d) : "—";
}

export function initials(name = "") {
  return name.trim().charAt(0).toUpperCase() || "?";
}
