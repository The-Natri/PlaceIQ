import { formatLpa } from "../../utils/format";

// Single-hue blue sequential ramp (light = few offers, dark = many).
// Magnitude uses one hue only, never a rainbow.
const RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"];
// White text only from #256abf onward (about 5.2:1). On #3987e5, white is
// only about 3.6:1, so that step keeps dark text (about 5.3:1) for the
// small-text 4.5:1 minimum.
const DARK_FROM = 4;

function step(value, max) {
  if (!value) return -1;
  return Math.min(RAMP.length - 1, Math.ceil((value / max) * RAMP.length) - 1);
}

/**
 * Company x department matrix of offers. It is a real <table> with the count
 * printed in each cell, so it is its own accessible table view; colour only
 * adds the at-a-glance pattern.
 */
export function Heatmap({ cells }) {
  const depts = [...new Set(cells.map((c) => c.dept_name))].sort();
  const byCompany = new Map();
  for (const c of cells) {
    if (!byCompany.has(c.company_name)) byCompany.set(c.company_name, {});
    byCompany.get(c.company_name)[c.dept_name] = c;
  }
  const companies = [...byCompany.keys()].sort((a, b) => {
    const total = (name) => Object.values(byCompany.get(name)).reduce((s, c) => s + c.offers_count, 0);
    return total(b) - total(a) || a.localeCompare(b);
  });
  const max = Math.max(1, ...cells.map((c) => c.offers_count));
  const short = (name) => name.replace(" Engineering", "").replace("Artificial Intelligence & ML", "AI & ML");

  return (
    <>
      <div className="table-wrap">
        <table className="heatmap">
          <caption className="sr-only">Offers by company and department</caption>
          <thead>
            <tr>
              <th scope="col">Company</th>
              {depts.map((d) => <th key={d} scope="col" title={d}>{short(d)}</th>)}
            </tr>
          </thead>
          <tbody>
            {companies.map((company) => (
              <tr key={company}>
                <th scope="row">{company}</th>
                {depts.map((dept) => {
                  const cell = byCompany.get(company)[dept];
                  const s = step(cell?.offers_count, max);
                  if (s < 0) return <td key={dept} className="empty" aria-label={`${company}, ${dept}: no offers`}>·</td>;
                  const label = `${company}, ${dept}: ${cell.offers_count} offer${cell.offers_count === 1 ? "" : "s"}, average ${formatLpa(cell.avg_package_lpa)}`;
                  return (
                    <td
                      key={dept}
                      title={label}
                      aria-label={label}
                      style={{ background: RAMP[s], color: s >= DARK_FROM ? "#fff" : "var(--c-text)" }}
                    >
                      {cell.offers_count}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="heat-scale" style={{ marginTop: 10 }} aria-hidden="true">
        <span>Fewer offers</span>
        {RAMP.map((c) => <span key={c} className="step" style={{ background: c }} />)}
        <span>More (max {max})</span>
      </div>
    </>
  );
}
