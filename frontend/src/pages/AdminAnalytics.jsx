import { useEffect, useMemo, useState } from "react";
import {
  Users,
  UserCheck,
  Building2,
  BriefcaseBusiness,
  BadgeCheck,
  TrendingUp,
} from "lucide-react";
import { api } from "../api";
import "./AdminAnalytics.css";

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
    <main className="analytics-page">
      <section className="analytics-hero">
        <div>
          <p className="analytics-eyebrow">PLACEMENT INSIGHTS</p>
          <h1>Analytics</h1>
          <p className="analytics-subtitle">
            Monitor placement performance, recruiters and student outcomes.
          </p>
        </div>
      </section>

      {overview && (
        <section className="analytics-overview-grid">
          <AnalyticsStat
            icon={<Users size={20} />}
            label="Students"
            value={overview.total_students}
          />

          <AnalyticsStat
            icon={<UserCheck size={20} />}
            label="Placed"
            value={overview.placed_students}
          />

          <AnalyticsStat
            icon={<TrendingUp size={20} />}
            label="Placement Rate"
            value={`${overview.overall_placement_pct}%`}
          />

          <AnalyticsStat
            icon={<Building2 size={20} />}
            label="Companies"
            value={overview.total_companies}
          />

          <AnalyticsStat
            icon={<BriefcaseBusiness size={20} />}
            label="Drives"
            value={overview.total_drives}
          />

          <AnalyticsStat
            icon={<BadgeCheck size={20} />}
            label="Offers"
            value={overview.total_offers}
            note={`${overview.accepted_offers} accepted`}
          />
        </section>
      )}

      <section className="analytics-grid">
        <section className="analytics-card">
          <div className="analytics-card-header">
            <div>
              <p className="analytics-eyebrow">DEPARTMENT PERFORMANCE</p>
              <h2>Placement % by Department</h2>
            </div>
          </div>

          <div className="department-performance-list">
            {deptStats.map((d) => {
              const percentage = Number(d.placement_percentage || 0);

              return (
                <div className="department-performance-item" key={d.dept_id}>
                  <div className="department-performance-top">
                    <div>
                      <strong>{d.dept_name}</strong>
                      <span>
                        {d.placed_students} of {d.total_students} placed
                      </span>
                    </div>

                    <strong className="percentage-value">
                      {percentage}%
                    </strong>
                  </div>

                  <div className="analytics-progress">
                    <div
                      className="analytics-progress-fill"
                      style={{
                        width: `${Math.min(percentage, 100)}%`,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        <section className="analytics-card">
          <div className="analytics-card-header">
            <div>
              <p className="analytics-eyebrow">ACADEMIC CORRELATION</p>
              <h2>CGPA vs Placement Outcome</h2>
            </div>
          </div>

          <CgpaBuckets rows={scatter} />
        </section>
      </section>

      <section className="analytics-card analytics-wide-card">
        <div className="analytics-card-header">
          <div>
            <p className="analytics-eyebrow">RECRUITERS</p>
            <h2>Top Recruiters</h2>
            <p>Companies ranked by total number of offers.</p>
          </div>
        </div>

        <div className="analytics-table-wrapper">
          <table className="analytics-table">
            <thead>
              <tr>
                <th>Company</th>
                <th>Offers</th>
                <th>Avg LPA</th>
                <th>Max LPA</th>
                <th>Min LPA</th>
              </tr>
            </thead>

            <tbody>
              {companyStats.map((c) => (
                <tr key={c.company_id}>
                  <td>
                    <div className="analytics-company-cell">
                      <div className="analytics-company-avatar">
                        {c.company_name?.charAt(0)}
                      </div>

                      <strong>{c.company_name}</strong>
                    </div>
                  </td>

                  <td>
                    <span className="offer-count-pill">
                      {c.offers_count}
                    </span>
                  </td>

                  <td>{c.avg_package_lpa} LPA</td>
                  <td>{c.max_package_lpa} LPA</td>
                  <td>{c.min_package_lpa} LPA</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="analytics-card analytics-wide-card">
        <div className="analytics-card-header">
          <div>
            <p className="analytics-eyebrow">COMPENSATION</p>
            <h2>Package by Branch</h2>
            <p>
              Compare offer volume and salary packages across departments.
            </p>
          </div>
        </div>

        <div className="package-grid">
          {packageByBranch.map((p) => (
            <div className="package-card" key={p.dept_name}>
              <div className="package-card-header">
                <strong>{p.dept_name}</strong>

                <span>
                  {p.offers_count} offers
                </span>
              </div>

              <div className="package-average">
                <span>Average Package</span>
                <strong>{p.avg_package_lpa} LPA</strong>
              </div>

              <div className="package-range">
                <div>
                  <span>Minimum</span>
                  <strong>{p.min_package_lpa} LPA</strong>
                </div>

                <div>
                  <span>Maximum</span>
                  <strong>{p.max_package_lpa} LPA</strong>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

function AnalyticsStat({ icon, label, value, note }) {
  return (
    <div className="analytics-stat-card">
      <div className="analytics-stat-icon">
        {icon}
      </div>

      <div className="analytics-stat-content">
        <span>{label}</span>
        <strong>{value}</strong>

        {note && <small>{note}</small>}
      </div>
    </div>
  );
}

function CgpaBuckets({ rows }) {
  const summary = useMemo(() => {
    const buckets = [
      { label: "8.5+", min: 8.5, max: 10.01 },
      { label: "7.5 - 8.5", min: 7.5, max: 8.5 },
      { label: "6.5 - 7.5", min: 6.5, max: 7.5 },
      { label: "< 6.5", min: 0, max: 6.5 },
    ];

    return buckets.map((b) => {
      const inBucket = rows.filter(
        (r) => r.cgpa >= b.min && r.cgpa < b.max
      );

      const placed = inBucket.filter(
        (r) => r.placement_status === "Placed"
      );

      const percentage = inBucket.length
        ? ((100 * placed.length) / inBucket.length).toFixed(1)
        : "0";

      return {
        ...b,
        total: inBucket.length,
        placed: placed.length,
        pct: percentage,
      };
    });
  }, [rows]);

  return (
    <div className="cgpa-bucket-list">
      {summary.map((b) => (
        <div className="cgpa-bucket" key={b.label}>
          <div className="cgpa-bucket-header">
            <div>
              <strong>{b.label}</strong>
              <span>
                {b.placed} of {b.total} placed
              </span>
            </div>

            <strong>{b.pct}%</strong>
          </div>

          <div className="cgpa-bar">
            <div
              className="cgpa-bar-fill"
              style={{
                width: `${Math.min(Number(b.pct), 100)}%`,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}