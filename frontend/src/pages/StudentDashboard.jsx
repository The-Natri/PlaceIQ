import { useEffect, useState } from "react";
import {
  GraduationCap,
  BriefcaseBusiness,
  FileText,
  CircleAlert,
  UserRound,
  CalendarDays,
  IndianRupee,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { api } from "../api";
import { useAuth } from "../auth/AuthContext";
import "./StudentDashboard.css";

export function StudentDashboard() {
  const { user } = useAuth();
  const studentId = user.profile.student_id;

  const [profile, setProfile] = useState(user.profile);
  const [eligibleDrives, setEligibleDrives] = useState([]);
  const [applications, setApplications] = useState([]);
  const [probability, setProbability] = useState(null);
  const [message, setMessage] = useState("");

  async function refreshAll() {
    const [prof, drives, apps] = await Promise.all([
      api.get(`/students/${studentId}`),
      api.get(`/students/${studentId}/eligible-drives`),
      api.get(`/students/${studentId}/applications`),
    ]);

    setProfile(prof);
    setEligibleDrives(drives);
    setApplications(apps);
  }

  useEffect(() => {
    refreshAll();

    api
      .get(`/students/${studentId}/placement-probability`)
      .then((r) => setProbability(r.placement_probability))
      .catch(() => setProbability(null));
  }, [studentId]);

  async function applyToDrive(driveId) {
    setMessage("");

    try {
      await api.post("/applications", { drive_id: driveId });
      setMessage("Applied successfully.");
      refreshAll();
    } catch (err) {
      setMessage(err.message);
    }
  }

  const placed =
    profile.placement_status?.toLowerCase() === "placed";

  return (
    <main className="student-dashboard">
      <section className="student-hero">
        <div>
          <p className="dashboard-eyebrow">STUDENT DASHBOARD</p>
          <h1>Welcome back, {profile.name}</h1>
          <p className="dashboard-subtitle">
            Track your placements, applications and upcoming opportunities.
          </p>
        </div>

        <div className="student-id-card">
          <span>Registration No.</span>
          <strong>{profile.reg_no}</strong>
        </div>
      </section>

      <section className="dashboard-stats">
        <StatCard
          icon={<GraduationCap size={20} />}
          label="CGPA"
          value={profile.cgpa}
          note="Current academic score"
        />

        <StatCard
          icon={<CircleAlert size={20} />}
          label="Backlogs"
          value={profile.backlogs}
          note="Current active backlogs"
        />

        <StatCard
          icon={<BriefcaseBusiness size={20} />}
          label="Eligible Drives"
          value={eligibleDrives.length}
          note="Available opportunities"
        />

        <StatCard
          icon={<FileText size={20} />}
          label="Applications"
          value={applications.length}
          note="Total applications"
        />
      </section>

      <section className="dashboard-main-grid">
        <div className="dashboard-card profile-card">
          <div className="card-heading-row">
            <div>
              <p className="section-label">PROFILE</p>
              <h2>Student Information</h2>
            </div>

            <span
              className={`placement-pill ${
                placed ? "placed" : "not-placed"
              }`}
            >
              {profile.placement_status}
            </span>
          </div>

          <div className="profile-grid">
            <ProfileItem
              icon={<UserRound size={18} />}
              label="Registration No."
              value={profile.reg_no}
            />

            <ProfileItem
              icon={<GraduationCap size={18} />}
              label="Department"
              value={profile.dept_name}
            />

            <ProfileItem
              icon={<GraduationCap size={18} />}
              label="CGPA"
              value={profile.cgpa}
            />

            <ProfileItem
              icon={<CircleAlert size={18} />}
              label="Backlogs"
              value={profile.backlogs}
            />
          </div>
        </div>

        {probability !== null && (
          <div className="dashboard-card probability-card">
            <p className="section-label">AI INSIGHT</p>
            <h2>Placement Probability</h2>

            <div className="probability-content">
              <div
                className="probability-ring"
                style={{
                  "--progress": `${probability * 360}deg`,
                }}
              >
                <div className="probability-ring-inner">
                  <strong>{(probability * 100).toFixed(1)}%</strong>
                </div>
              </div>

              <p>
                Estimated from your academic and profile information.
              </p>
            </div>

            <p className="probability-note">
              Logistic regression model using CGPA, backlogs, department
              and skill count.
            </p>
          </div>
        )}
      </section>

      {message && <div className="dashboard-notice">{message}</div>}

      <section className="dashboard-card drives-section">
        <div className="card-heading-row">
          <div>
            <p className="section-label">OPPORTUNITIES</p>
            <h2>Eligible Placement Drives</h2>
          </div>

          <span className="count-pill">
            {eligibleDrives.length} Available
          </span>
        </div>

        {eligibleDrives.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">
              <BriefcaseBusiness size={24} />
            </div>

            <h3>No eligible drives right now</h3>
            <p>New opportunities will appear here when available.</p>
          </div>
        ) : (
          <div className="drive-grid">
            {eligibleDrives.map((d) => (
              <div className="drive-card" key={d.drive_id}>
                <div className="drive-top">
                  <div className="company-avatar">
                    {d.company_name?.charAt(0)}
                  </div>

                  <div>
                    <h3>{d.company_name}</h3>
                    <p>{d.job_role}</p>
                  </div>
                </div>

                <div className="drive-info">
                  <div>
                    <CalendarDays size={16} />
                    <span>Date</span>
                    <strong>{d.drive_date?.slice(0, 10)}</strong>
                  </div>

                  <div>
                    <IndianRupee size={16} />
                    <span>Package</span>
                    <strong>{d.package_lpa} LPA</strong>
                  </div>
                </div>

                <button
                  className="apply-button"
                  onClick={() => applyToDrive(d.drive_id)}
                >
                  Apply Now
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="dashboard-card applications-section">
        <div className="card-heading-row">
          <div>
            <p className="section-label">APPLICATION TRACKER</p>
            <h2>My Applications</h2>
          </div>

          <span className="count-pill">
            {applications.length} Total
          </span>
        </div>

        {applications.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">
              <FileText size={24} />
            </div>

            <h3>No applications yet</h3>
            <p>Apply to an eligible drive to start tracking it here.</p>
          </div>
        ) : (
          <div className="applications-list">
            {applications.map((a) => (
              <ApplicationRow
                key={a.application_id}
                application={a}
                onChange={refreshAll}
              />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

function StatCard({ icon, label, value, note }) {
  return (
    <div className="stat-card">
      <div className="stat-card-top">
        <div className="stat-icon">{icon}</div>
        <p>{label}</p>
      </div>

      <h3>{value}</h3>
      <span>{note}</span>
    </div>
  );
}

function ProfileItem({ icon, label, value }) {
  return (
    <div className="profile-item">
      <div className="profile-icon">{icon}</div>

      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </div>
  );
}

function ApplicationRow({ application, onChange }) {
  const [expanded, setExpanded] = useState(false);
  const [detail, setDetail] = useState(null);
  const [message, setMessage] = useState("");

  async function toggle() {
    if (!expanded && !detail) {
      const d = await api.get(
        `/applications/${application.application_id}`
      );
      setDetail(d);
    }

    setExpanded(!expanded);
  }

  async function respondToOffer(offerId, action) {
    setMessage("");

    try {
      await api.post(`/offers/${offerId}/${action}`);
      setMessage(`Offer ${action}ed.`);

      const d = await api.get(
        `/applications/${application.application_id}`
      );

      setDetail(d);
      onChange();
    } catch (err) {
      setMessage(err.message);
    }
  }

  return (
    <div className="application-item">
      <button className="application-summary" onClick={toggle}>
        <div className="application-company">
          <div className="company-avatar small">
            {application.company_name?.charAt(0)}
          </div>

          <div>
            <strong>{application.company_name}</strong>
            <span>{application.job_role}</span>
          </div>
        </div>

        <div className="application-right">
          <span
            className={`status-badge status-${application.status}`}
          >
            {application.status?.replaceAll("_", " ")}
          </span>

          {expanded ? (
            <ChevronUp size={17} />
          ) : (
            <ChevronDown size={17} />
          )}
        </div>
      </button>

      {expanded && detail && (
        <div className="application-detail">
          <div className="detail-block">
            <h4>Interview Rounds</h4>

            {detail.interview_rounds.length === 0 ? (
              <p className="muted-text">
                No interview rounds recorded yet.
              </p>
            ) : (
              <div className="round-list">
                {detail.interview_rounds.map((r) => (
                  <div className="round-item" key={r.round_id}>
                    <div>
                      <strong>Round {r.round_number}</strong>
                      <span>{r.round_type}</span>
                    </div>

                    <span className="round-result">
                      {r.result}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {detail.offer && (
            <div className="offer-box">
              <div>
                <p>PLACEMENT OFFER</p>
                <h4>{detail.offer.offered_package_lpa} LPA</h4>
                <span>Status: {detail.offer.status}</span>
              </div>

              {detail.offer.status === "Pending" && (
                <div className="offer-buttons">
                  <button
                    className="accept-button"
                    onClick={() =>
                      respondToOffer(
                        detail.offer.offer_id,
                        "accept"
                      )
                    }
                  >
                    Accept Offer
                  </button>

                  <button
                    className="decline-button"
                    onClick={() =>
                      respondToOffer(
                        detail.offer.offer_id,
                        "decline"
                      )
                    }
                  >
                    Decline
                  </button>
                </div>
              )}
            </div>
          )}

          {message && (
            <div className="dashboard-notice small-notice">
              {message}
            </div>
          )}
        </div>
      )}
    </div>
  );
}