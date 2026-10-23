import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Award, Briefcase, Building, GraduationCap, RefreshCw, TrendingUp, Users } from "lucide-react";
import { api } from "../../api";
import { useApi } from "../../hooks/useApi";
import { BarList } from "../../components/charts/BarList";
import { CgpaScatter } from "../../components/charts/CgpaScatter";
import { Heatmap } from "../../components/charts/Heatmap";
import { CumulativeOffersChart, MonthlyOffersChart } from "../../components/charts/TimelineCharts";
import { Alert } from "../../components/ui/Alert";
import { DataTable } from "../../components/ui/DataTable";
import { Loading } from "../../components/ui/Feedback";
import { Card, PageHeader, StatCard } from "../../components/ui/Layout";
import { TabPanel, Tabs } from "../../components/ui/Tabs";
import { formatDateTime, formatLpa, formatMonth, formatPercent, toNumber } from "../../utils/format";

const TABS = ["overview", "recruiters", "rankings", "timeline", "matrix"];

// "View as table" for every chart: the accessible, colour-free twin.
function TableView({ children }) {
  return (
    <details style={{ marginTop: 14 }}>
      <summary className="section-title" style={{ cursor: "pointer" }}>View as table</summary>
      <div className="card" style={{ marginTop: 8 }}>{children}</div>
    </details>
  );
}

const CGPA_BANDS = [
  { label: "8.5 and above", min: 8.5, max: 11 },
  { label: "7.5 – 8.49", min: 7.5, max: 8.5 },
  { label: "6.5 – 7.49", min: 6.5, max: 7.5 },
  { label: "Below 6.5", min: 0, max: 6.5 },
];

export function AdminAnalytics() {
  const [params, setParams] = useSearchParams();
  const tab = TABS.includes(params.get("tab")) ? params.get("tab") : "overview";
  const [topN, setTopN] = useState(3);

  const overview = useApi("/analytics/overview");
  const deptStats = useApi("/analytics/department-stats");
  const scatter = useApi("/analytics/cgpa-vs-outcome");
  const companies = useApi("/analytics/company-stats");
  const branch = useApi("/analytics/package-by-branch");
  const rankings = useApi(`/analytics/top-offers-per-dept?n=${topN}`);
  const timeline = useApi("/analytics/placement-timeline");
  const matrix = useApi("/analytics/company-dept-matrix");

  const [refreshing, setRefreshing] = useState(false);
  const [notice, setNotice] = useState({ variant: "", text: "" });

  const bands = useMemo(() => {
    const rows = scatter.data || [];
    return CGPA_BANDS.map((b) => {
      const inBand = rows.filter((r) => { const c = toNumber(r.cgpa); return c >= b.min && c < b.max; });
      const placed = inBand.filter((r) => r.placement_status === "Placed").length;
      return { ...b, total: inBand.length, placed, pct: inBand.length ? (100 * placed) / inBand.length : null };
    });
  }, [scatter.data]);

  async function refreshMatrix() {
    setRefreshing(true);
    setNotice({ variant: "", text: "" });
    try {
      const r = await api.post("/analytics/refresh-matrix");
      await matrix.reload();
      setNotice({ variant: "success", text: `Snapshot rebuilt at ${formatDateTime(r.refreshed_at)}.` });
    } catch (err) {
      setNotice({ variant: "error", text: err.message });
    } finally {
      setRefreshing(false);
    }
  }

  const o = overview.data;

  return (
    <>
      <PageHeader eyebrow="Placement cell" title="Placement analytics" subtitle="Season-wide outcomes by department, recruiter and month." />

      {o && (
        <div className="stat-grid">
          <StatCard icon={GraduationCap} label="Students" value={o.total_students} />
          <StatCard icon={Award} label="Placed" value={o.placed_students} hint={`${formatPercent(o.overall_placement_pct)} of students`} />
          <StatCard icon={Building} label="Companies" value={o.total_companies} />
          <StatCard icon={Briefcase} label="Drives" value={o.total_drives} />
          <StatCard icon={Users} label="Offers made" value={o.total_offers} hint={`${o.accepted_offers} accepted`} />
        </div>
      )}
      {overview.error && <Alert variant="error">{overview.error}</Alert>}

      <Tabs
        label="Analytics sections"
        active={tab}
        onChange={(t) => setParams({ tab: t })}
        tabs={[
          { id: "overview", label: "Overview" },
          { id: "recruiters", label: "Recruiters & packages" },
          { id: "rankings", label: "Top offers" },
          { id: "timeline", label: "Timeline" },
          { id: "matrix", label: "Company × department" },
        ]}
      />

      <TabPanel id="overview" active={tab}>
        <div className="grid-2">
          <Card title="Placement % by department" subtitle="Share of each department's students who are placed">
            {deptStats.error && <Alert variant="error">{deptStats.error}</Alert>}
            {!deptStats.data && !deptStats.error && <Loading />}
            {deptStats.data && (
              <>
                <BarList
                  label="Placement percentage by department"
                  max={100}
                  rows={deptStats.data.map((d) => ({
                    key: d.dept_id,
                    label: d.dept_name,
                    value: toNumber(d.placement_percentage) ?? 0,
                    display: formatPercent(d.placement_percentage),
                  }))}
                />
                <TableView>
                  <DataTable
                    caption="Placement by department"
                    rows={deptStats.data}
                    rowKey={(d) => d.dept_id}
                    columns={[
                      { key: "dept_name", header: "Department" },
                      { key: "total_students", header: "Students", className: "num" },
                      { key: "placed_students", header: "Placed", className: "num" },
                      { key: "pct", header: "Placed %", className: "num", render: (d) => formatPercent(d.placement_percentage) },
                    ]}
                  />
                </TableView>
              </>
            )}
          </Card>

          <Card title="CGPA vs placement outcome" subtitle="Each dot is one student; hover a dot for details">
            {scatter.error && <Alert variant="error">{scatter.error}</Alert>}
            {!scatter.data && !scatter.error && <Loading />}
            {scatter.data && (
              <>
                <CgpaScatter students={scatter.data} />
                <TableView>
                  <DataTable
                    caption="Placement rate by CGPA band"
                    rows={bands}
                    rowKey={(b) => b.label}
                    columns={[
                      { key: "label", header: "CGPA band" },
                      { key: "total", header: "Students", className: "num" },
                      { key: "placed", header: "Placed", className: "num" },
                      { key: "pct", header: "Placed %", className: "num", render: (b) => (b.pct === null ? "—" : formatPercent(b.pct)) },
                    ]}
                  />
                </TableView>
              </>
            )}
          </Card>
        </div>
      </TabPanel>

      <TabPanel id="recruiters" active={tab}>
        <div style={{ display: "grid", gap: "var(--gap)" }}>
          <Card title="Top recruiters" subtitle="Companies by number of offers made (from company_wise_stats_view)" flush>
            <DataTable
              caption="Top recruiters"
              loading={companies.loading}
              error={companies.error}
              rows={companies.data}
              rowKey={(c) => c.company_id}
              columns={[
                { key: "rank", header: "#", className: "num", render: (c) => companies.data.indexOf(c) + 1 },
                { key: "company_name", header: "Company" },
                { key: "offers_count", header: "Offers", className: "num" },
                { key: "avg", header: "Average", className: "num", render: (c) => formatLpa(c.avg_package_lpa) },
                { key: "max", header: "Highest", className: "num", render: (c) => formatLpa(c.max_package_lpa) },
                { key: "min", header: "Lowest", className: "num", render: (c) => formatLpa(c.min_package_lpa) },
              ]}
            />
          </Card>
          <Card title="Packages by branch" subtitle="Offers and package range per department" flush>
            <DataTable
              caption="Packages by branch"
              loading={branch.loading}
              error={branch.error}
              rows={branch.data}
              rowKey={(b) => b.dept_name}
              columns={[
                { key: "dept_name", header: "Department" },
                { key: "offers_count", header: "Offers", className: "num" },
                { key: "avg", header: "Average", className: "num", render: (b) => formatLpa(b.avg_package_lpa) },
                { key: "max", header: "Highest", className: "num", render: (b) => formatLpa(b.max_package_lpa) },
                { key: "min", header: "Lowest", className: "num", render: (b) => formatLpa(b.min_package_lpa) },
              ]}
            />
          </Card>
        </div>
      </TabPanel>

      <TabPanel id="rankings" active={tab}>
        <Card
          title="Top offers in each department"
          subtitle="Ranked with RANK() over each department (ties share a rank)"
          actions={
            <label className="inline-actions">
              <span className="muted">Show top</span>
              <select className="input" style={{ width: "auto" }} value={topN} onChange={(e) => setTopN(Number(e.target.value))}>
                {[1, 3, 5, 10].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </label>
          }
          flush
        >
          <DataTable
            caption="Top offers per department"
            loading={rankings.loading}
            error={rankings.error}
            rows={rankings.data}
            rowKey={(r) => `${r.dept_name}-${r.reg_no}-${r.company_name}-${r.rank_in_dept}`}
            columns={[
              { key: "dept_name", header: "Department" },
              { key: "rank_in_dept", header: "Rank", className: "num" },
              { key: "name", header: "Student", render: (r) => (<><div>{r.name}</div><div className="cell-sub">{r.reg_no}</div></>) },
              { key: "company_name", header: "Company" },
              { key: "pkg", header: "Package", className: "num", render: (r) => formatLpa(r.offered_package_lpa) },
            ]}
          />
        </Card>
      </TabPanel>

      <TabPanel id="timeline" active={tab}>
        {timeline.error && <Alert variant="error">{timeline.error}</Alert>}
        {!timeline.data && !timeline.error && <Loading />}
        {timeline.data && (
          <div style={{ display: "grid", gap: "var(--gap)" }}>
            <div className="grid-2">
              <Card title="Offers per month" subtitle="Hover or tab to a bar for its value">
                <MonthlyOffersChart rows={timeline.data} />
              </Card>
              <Card title="Total offers so far" subtitle="Running total (window function SUM … OVER)">
                <CumulativeOffersChart rows={timeline.data} />
              </Card>
            </div>
            <Card title="Month by month" flush>
              <DataTable
                caption="Offers by month"
                rows={timeline.data}
                rowKey={(r) => r.month}
                columns={[
                  { key: "month", header: "Month", render: (r) => formatMonth(r.month) },
                  { key: "offers_in_month", header: "Offers", className: "num" },
                  { key: "cumulative_offers", header: "Running total", className: "num", render: (r) => toNumber(r.cumulative_offers) },
                  {
                    key: "change",
                    header: "Change vs previous month",
                    className: "num",
                    render: (r) => (r.change_from_prev_month === null ? "—" : r.change_from_prev_month > 0 ? `+${r.change_from_prev_month}` : r.change_from_prev_month),
                  },
                ]}
              />
            </Card>
          </div>
        )}
      </TabPanel>

      <TabPanel id="matrix" active={tab}>
        <Card
          title="Offers by company and department"
          subtitle={
            matrix.data?.refreshed_at
              ? `Stored snapshot (materialized view), last rebuilt ${formatDateTime(matrix.data.refreshed_at)}`
              : "Stored snapshot (materialized view)"
          }
          actions={
            <button type="button" className="btn btn-secondary btn-sm" onClick={refreshMatrix} disabled={refreshing}>
              <RefreshCw size={14} className={refreshing ? "spin" : undefined} aria-hidden="true" /> {refreshing ? "Rebuilding…" : "Rebuild snapshot"}
            </button>
          }
        >
          <Alert variant={notice.variant || "info"} onClose={() => setNotice({ variant: "", text: "" })}>{notice.text}</Alert>
          <p className="muted" style={{ marginBottom: 12, marginTop: notice.text ? 12 : 0 }}>
            <TrendingUp size={13} aria-hidden="true" /> This view is computed once and stored, so it can lag behind
            new offers until it is rebuilt. Declined offers are not counted.
          </p>
          {matrix.error && <Alert variant="error">{matrix.error}</Alert>}
          {!matrix.data && !matrix.error && <Loading />}
          {matrix.data && <Heatmap cells={matrix.data.cells} />}
        </Card>
      </TabPanel>
    </>
  );
}
