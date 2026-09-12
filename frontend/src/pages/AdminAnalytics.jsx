import { useEffect, useState } from "react";
import { api } from "../api";

export function AdminAnalytics() {
  const [overview, setOverview] = useState(null);
  const [deptStats, setDeptStats] = useState([]);
  const [companyStats, setCompanyStats] = useState([]);
  const [packageByBranch, setPackageByBranch] = useState([]);
  const [scatter, setScatter] = useState([]);

  useEffect(() => {
    api.get("/analytics/overview").then(setOverview);
    api.get("/analytics/department-stats").then(setDeptStats);
    api.get("/analytics/company-stats?top=8").then(setCompanyStats);
    api.get("/analytics/package-by-branch").then(setPackageByBranch);
    api.get("/analytics/cgpa-vs-outcome").then(setScatter);
  }, []);

  return (
    <div className="page">
      <h1>Analytics</h1>

      {overview && (
        <section className="card">
          <h2>Overview</h2>
          <div className="stat-row">
            <Stat label="Students" value={overview.total_students} />
            <Stat label="Placed" value={overview.placed_students} />
            <Stat label="Placement %" value={`${overview.overall_placement_pct}%`} />
            <Stat label="Companies" value={overview.total_companies} />
            <Stat label="Drives" value={overview.total_drives} />
            <Stat label="Offers (Accepted)" value={`${overview.total_offers} (${overview.accepted_offers})`} />
          </div>
        </section>
      )}

      <section className="card">
        <h2>Placement % by Department</h2>
        <table>
          <thead><tr><th>Department</th><th>Total</th><th>Placed</th><th>%</th></tr></thead>
          <tbody>
            {deptStats.map((d) => (
              <tr key={d.dept_id}>
                <td>{d.dept_name}</td>
                <td>{d.total_students}</td>
                <td>{d.placed_students}</td>
                <td>{d.placement_percentage}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2>Top Recruiters (by offer count)</h2>
        <table>
          <thead><tr><th>Company</th><th>Offers</th><th>Avg LPA</th><th>Max LPA</th><th>Min LPA</th></tr></thead>
          <tbody>
            {companyStats.map((c) => (
              <tr key={c.company_id}>
                <td>{c.company_name}</td>
                <td>{c.offers_count}</td>
                <td>{c.avg_package_lpa}</td>
                <td>{c.max_package_lpa}</td>
                <td>{c.min_package_lpa}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2>Package by Branch</h2>
        <table>
          <thead><tr><th>Department</th><th>Offers</th><th>Avg LPA</th><th>Max LPA</th><th>Min LPA</th></tr></thead>
          <tbody>
            {packageByBranch.map((p) => (
              <tr key={p.dept_name}>
                <td>{p.dept_name}</td>
                <td>{p.offers_count}</td>
                <td>{p.avg_package_lpa}</td>
                <td>{p.max_package_lpa}</td>
                <td>{p.min_package_lpa}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2>CGPA vs Outcome</h2>
        <p className="muted">
          Raw per-student data points ({scatter.length} students) — a scatter/bar chart belongs
          here once the frontend is restyled; showing a compact table for now.
        </p>
        <CgpaBuckets rows={scatter} />
      </section>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="stat-tile">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

// Cheap bucketed summary so the CGPA-vs-outcome correlation is visible
// without pulling in a charting library — a placeholder for the scatter
// chart the teammate will likely add during the visual redesign.
function CgpaBuckets({ rows }) {
  const buckets = [
    { label: "8.5+", min: 8.5, max: 10.01 },
    { label: "7.5 - 8.5", min: 7.5, max: 8.5 },
    { label: "6.5 - 7.5", min: 6.5, max: 7.5 },
    { label: "< 6.5", min: 0, max: 6.5 },
  ];
  const summary = buckets.map((b) => {
    const inBucket = rows.filter((r) => r.cgpa >= b.min && r.cgpa < b.max);
    const placed = inBucket.filter((r) => r.placement_status === "Placed");
    return {
      ...b,
      total: inBucket.length,
      placed: placed.length,
      pct: inBucket.length ? ((100 * placed.length) / inBucket.length).toFixed(1) : "0",
    };
  });

  return (
    <table>
      <thead><tr><th>CGPA Band</th><th>Total</th><th>Placed</th><th>%</th></tr></thead>
      <tbody>
        {summary.map((b) => (
          <tr key={b.label}>
            <td>{b.label}</td>
            <td>{b.total}</td>
            <td>{b.placed}</td>
            <td>{b.pct}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
