import { useEffect, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth/AuthContext";

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
      .catch(() => setProbability(null)); // ML service unavailable — widget just stays hidden
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

  return (
    <div className="page">
      <h1>Welcome, {profile.name}</h1>

      <section className="card">
        <h2>Profile</h2>
        <table className="kv-table">
          <tbody>
            <tr><th>Reg No</th><td>{profile.reg_no}</td></tr>
            <tr><th>Department</th><td>{profile.dept_name}</td></tr>
            <tr><th>CGPA</th><td>{profile.cgpa}</td></tr>
            <tr><th>Backlogs</th><td>{profile.backlogs}</td></tr>
            <tr><th>Placement Status</th><td>{profile.placement_status}</td></tr>
          </tbody>
        </table>
      </section>

      {probability !== null && (
        <section className="card">
          <h2>ML Placement Probability</h2>
          <p className="big-stat">{(probability * 100).toFixed(1)}%</p>
          <p className="muted">Predicted by a logistic regression model trained on CGPA, backlogs, department, and skill count.</p>
        </section>
      )}

      {message && <p className="notice">{message}</p>}

      <section className="card">
        <h2>Eligible Drives</h2>
        {eligibleDrives.length === 0 ? (
          <p className="muted">No eligible drives right now.</p>
        ) : (
          <table>
            <thead>
              <tr><th>Company</th><th>Role</th><th>Date</th><th>Package (LPA)</th><th></th></tr>
            </thead>
            <tbody>
              {eligibleDrives.map((d) => (
                <tr key={d.drive_id}>
                  <td>{d.company_name}</td>
                  <td>{d.job_role}</td>
                  <td>{d.drive_date?.slice(0, 10)}</td>
                  <td>{d.package_lpa}</td>
                  <td><button onClick={() => applyToDrive(d.drive_id)}>Apply</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="card">
        <h2>My Applications</h2>
        {applications.length === 0 ? (
          <p className="muted">No applications yet.</p>
        ) : (
          applications.map((a) => (
            <ApplicationRow key={a.application_id} application={a} onChange={refreshAll} />
          ))
        )}
      </section>
    </div>
  );
}

function ApplicationRow({ application, onChange }) {
  const [expanded, setExpanded] = useState(false);
  const [detail, setDetail] = useState(null);
  const [message, setMessage] = useState("");

  async function toggle() {
    if (!expanded && !detail) {
      const d = await api.get(`/applications/${application.application_id}`);
      setDetail(d);
    }
    setExpanded(!expanded);
  }

  async function respondToOffer(offerId, action) {
    setMessage("");
    try {
      await api.post(`/offers/${offerId}/${action}`);
      setMessage(`Offer ${action}ed.`);
      const d = await api.get(`/applications/${application.application_id}`);
      setDetail(d);
      onChange();
    } catch (err) {
      setMessage(err.message);
    }
  }

  return (
    <div className="application-row">
      <div className="application-summary" onClick={toggle}>
        <strong>{application.company_name}</strong> — {application.job_role}
        <span className={`status-badge status-${application.status}`}>{application.status}</span>
      </div>
      {expanded && detail && (
        <div className="application-detail">
          <h4>Interview Rounds</h4>
          {detail.interview_rounds.length === 0 ? (
            <p className="muted">No rounds recorded yet.</p>
          ) : (
            <ul>
              {detail.interview_rounds.map((r) => (
                <li key={r.round_id}>
                  Round {r.round_number} ({r.round_type}): {r.result}
                </li>
              ))}
            </ul>
          )}

          {detail.offer && (
            <>
              <h4>Offer</h4>
              <p>
                {detail.offer.offered_package_lpa} LPA — status: {detail.offer.status}
              </p>
              {detail.offer.status === "Pending" && (
                <div className="button-row">
                  <button onClick={() => respondToOffer(detail.offer.offer_id, "accept")}>Accept Offer</button>
                  <button onClick={() => respondToOffer(detail.offer.offer_id, "decline")}>Decline Offer</button>
                </div>
              )}
            </>
          )}
          {message && <p className="notice">{message}</p>}
        </div>
      )}
    </div>
  );
}
