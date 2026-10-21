import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Award, Briefcase, ClipboardList, GraduationCap, Search, Send, TrendingUp } from "lucide-react";
import { api } from "../../api";
import { useAuth } from "../../auth/AuthContext";
import { useApi } from "../../hooks/useApi";
import { ApplicationDetailModal } from "../../components/ApplicationDetailModal";
import { Alert } from "../../components/ui/Alert";
import { DataTable } from "../../components/ui/DataTable";
import { Card, CompanyCell, PageHeader, StatCard } from "../../components/ui/Layout";
import { Loading } from "../../components/ui/Feedback";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { TabPanel, Tabs } from "../../components/ui/Tabs";
import { formatCgpa, formatDate, formatLpa, formatPercent, toNumber } from "../../utils/format";
import { ProbabilityCard } from "./ProbabilityCard";

const TABS = ["overview", "drives", "applications"];

export function StudentDashboard() {
  const { user } = useAuth();
  const id = user.profile.student_id;
  const [params, setParams] = useSearchParams();
  const tab = TABS.includes(params.get("tab")) ? params.get("tab") : "overview";

  const profile = useApi(`/students/${id}`);
  const drives = useApi(`/students/${id}/eligible-drives`);
  const applications = useApi(`/students/${id}/applications`);
  const prediction = useApi(`/students/${id}/placement-probability`);

  const [openApp, setOpenApp] = useState(null);
  const [message, setMessage] = useState({ variant: "", text: "" });
  const [applying, setApplying] = useState(null);
  const [search, setSearch] = useState("");

  const appliedDriveIds = useMemo(
    () => new Set((applications.data || []).map((a) => a.drive_id)),
    [applications.data]
  );
  const visibleDrives = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (drives.data || []).filter(
      (d) => !term || d.company_name.toLowerCase().includes(term) || d.job_role.toLowerCase().includes(term)
    );
  }, [drives.data, search]);

  const p = profile.data;
  const offersMade = (applications.data || []).filter((a) => a.status === "Offer_Made").length;

  async function apply(drive) {
    setApplying(drive.drive_id);
    setMessage({ variant: "", text: "" });
    try {
      await api.post("/applications", { drive_id: drive.drive_id });
      setMessage({ variant: "success", text: `Applied to ${drive.company_name} — ${drive.job_role}. Track it under My Applications.` });
      applications.reload();
    } catch (err) {
      setMessage({ variant: "error", text: err.message });
    } finally {
      setApplying(null);
    }
  }

  function refreshAfterOfferChange() {
    applications.reload();
    profile.reload();
    prediction.reload();
  }

  return (
    <>
      <PageHeader
        eyebrow="Student dashboard"
        title={p ? `Welcome, ${p.name.split(" ")[0]}` : "Welcome"}
        subtitle="Your profile, the drives you can apply to, and where each application stands."
      />

      <Tabs
        label="Student dashboard sections"
        active={tab}
        onChange={(t) => setParams({ tab: t })}
        tabs={[
          { id: "overview", label: "Overview" },
          { id: "drives", label: "Eligible Drives", count: drives.data?.length },
          { id: "applications", label: "My Applications", count: applications.data?.length },
        ]}
      />

      <Alert variant={message.variant || "info"} onClose={() => setMessage({ variant: "", text: "" })}>
        {message.text}
      </Alert>

      <TabPanel id="overview" active={tab}>
        <div style={{ display: "grid", gap: "var(--gap)" }}>
          <div className="stat-grid">
            <StatCard icon={GraduationCap} label="CGPA" value={p ? formatCgpa(p.cgpa) : "—"} hint={p ? `${p.backlogs} active backlog${p.backlogs === 1 ? "" : "s"}` : ""} />
            <StatCard icon={Briefcase} label="Eligible drives" value={drives.data?.length ?? "—"} hint="Open drives you qualify for" />
            <StatCard icon={ClipboardList} label="Applications" value={applications.data?.length ?? "—"} hint={`${offersMade} with an offer`} />
            <StatCard icon={Award} label="Placement status" value={p ? <StatusBadge status={p.placement_status} /> : "—"} />
          </div>

          <div className="grid-2">
            <Card title="Profile" subtitle="As registered with the placement cell">
              {profile.error && <Alert variant="error">{profile.error}</Alert>}
              {!p && !profile.error && <Loading />}
              {p && (
                <>
                  <dl className="kv">
                    <div><dt>Registration No.</dt><dd>{p.reg_no}</dd></div>
                    <div><dt>Department</dt><dd>{p.dept_name}</dd></div>
                    <div><dt>Batch</dt><dd>{p.batch_year}</dd></div>
                    <div><dt>Email</dt><dd style={{ wordBreak: "break-all" }}>{p.email}</dd></div>
                    <div><dt>Phone</dt><dd>{p.phone || "—"}</dd></div>
                    <div><dt>Skills</dt><dd>{p.skills.map((s) => s.skill_name).join(", ") || "—"}</dd></div>
                  </dl>
                  {p.cgpa_standing && (
                    <>
                      <div className="divider" style={{ margin: "16px 0" }} />
                      <div className="section-title"><TrendingUp size={13} aria-hidden="true" /> CGPA standing in your department</div>
                      <p>
                        Rank <strong>{p.cgpa_standing.cgpa_rank_in_dept}</strong> of {p.cgpa_standing.dept_size} ·{" "}
                        <strong>{formatPercent(p.cgpa_standing.cgpa_percentile_in_dept)}</strong> percentile
                      </p>
                      <p className="field-hint">
                        {Math.round(toNumber(p.cgpa_standing.cgpa_percentile_in_dept))}% of your classmates
                        (not counting you) have a lower CGPA.
                      </p>
                    </>
                  )}
                </>
              )}
            </Card>

            <ProbabilityCard
              probability={prediction.data?.placement_probability}
              loading={prediction.loading}
              error={prediction.error}
              profile={p}
            />
          </div>
        </div>
      </TabPanel>

      <TabPanel id="drives" active={tab}>
        <Card title="Eligible drives" subtitle="Open drives whose CGPA, backlog and branch rules you meet" flush>
          <div className="toolbar">
            <label className="search-box">
              <span className="sr-only">Search drives</span>
              <Search size={16} aria-hidden="true" />
              <input className="input" placeholder="Search company or role" value={search} onChange={(e) => setSearch(e.target.value)} />
            </label>
          </div>
          <DataTable
            caption="Eligible drives"
            loading={drives.loading}
            error={drives.error}
            rows={drives.data ? visibleDrives : null}
            rowKey={(d) => d.drive_id}
            emptyTitle={search ? "No drives match your search" : "No eligible drives right now"}
            emptyMessage={search ? "Try a different company or role." : "New drives appear here when you meet their criteria."}
            columns={[
              { key: "company", header: "Company", render: (d) => <CompanyCell name={d.company_name} sub={d.job_role} /> },
              { key: "date", header: "Drive date", render: (d) => <span className="nowrap">{formatDate(d.drive_date)}</span> },
              { key: "package", header: "Package", className: "num", render: (d) => formatLpa(d.package_lpa) },
              { key: "criteria", header: "Criteria", render: (d) => <span className="cell-sub">CGPA ≥ {formatCgpa(d.min_cgpa)} · ≤ {d.max_backlogs} backlogs</span> },
              { key: "status", header: "Drive", render: (d) => <StatusBadge status={d.status} /> },
              {
                key: "action",
                header: <span className="sr-only">Action</span>,
                render: (d) =>
                  appliedDriveIds.has(d.drive_id) ? (
                    <span className="badge badge-primary">Applied</span>
                  ) : (
                    <button type="button" className="btn btn-primary btn-sm" disabled={applying === d.drive_id} onClick={() => apply(d)}>
                      <Send size={14} aria-hidden="true" /> {applying === d.drive_id ? "Applying…" : "Apply"}
                    </button>
                  ),
              },
            ]}
          />
        </Card>
      </TabPanel>

      <TabPanel id="applications" active={tab}>
        <Card title="My applications" subtitle="Click an application to see its rounds, offer and full history" flush>
          <DataTable
            caption="My applications"
            loading={applications.loading}
            error={applications.error}
            rows={applications.data}
            rowKey={(a) => a.application_id}
            onRowClick={(a) => setOpenApp(a.application_id)}
            emptyTitle="No applications yet"
            emptyMessage="Apply to a drive from the Eligible Drives tab."
            columns={[
              { key: "company", header: "Company", render: (a) => <CompanyCell name={a.company_name} sub={a.job_role} /> },
              { key: "applied", header: "Applied on", render: (a) => <span className="nowrap">{formatDate(a.applied_at)}</span> },
              { key: "package", header: "Package", className: "num", render: (a) => formatLpa(a.package_lpa) },
              { key: "status", header: "Status", render: (a) => <StatusBadge status={a.status} /> },
              {
                key: "view",
                header: <span className="sr-only">Details</span>,
                render: (a) => (
                  <button type="button" className="btn btn-secondary btn-sm" onClick={(e) => { e.stopPropagation(); setOpenApp(a.application_id); }}>
                    {a.status === "Offer_Made" ? "View offer" : "Details"}
                  </button>
                ),
              },
            ]}
          />
        </Card>
      </TabPanel>

      <ApplicationDetailModal
        open={openApp !== null}
        applicationId={openApp}
        onClose={() => setOpenApp(null)}
        canRespond
        onChanged={refreshAfterOfferChange}
      />
    </>
  );
}
