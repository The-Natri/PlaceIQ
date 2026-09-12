import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";

const STATUS_OPTIONS = ["Applied", "Shortlisted", "Interview_Scheduled", "Rejected", "Selected"];
const ROUND_TYPES = ["Aptitude", "Technical", "HR", "Group_Discussion", "Coding_Test"];

export function AdminDriveDetail() {
  const { driveId } = useParams();
  const [drive, setDrive] = useState(null);
  const [applicants, setApplicants] = useState([]);
  const [message, setMessage] = useState("");

  function refresh() {
    api.get(`/drives/${driveId}`).then(setDrive);
    api.get(`/drives/${driveId}/applicants`).then(setApplicants);
  }

  useEffect(refresh, [driveId]);

  async function setStatus(applicationId, status) {
    setMessage("");
    try {
      await api.put(`/applications/${applicationId}/status`, { status });
      refresh();
    } catch (err) {
      setMessage(err.message);
    }
  }

  async function recordRound(applicationId, roundNumber, roundType, result) {
    setMessage("");
    try {
      await api.post(`/applications/${applicationId}/interview-rounds`, {
        round_number: Number(roundNumber), round_type: roundType, result,
      });
      setMessage("Round recorded.");
    } catch (err) {
      setMessage(err.message);
    }
  }

  async function recordOffer(applicationId, packageLpa) {
    setMessage("");
    try {
      await api.post(`/applications/${applicationId}/offer`, {
        offered_package_lpa: Number(packageLpa),
      });
      setMessage("Offer recorded — student placement_status updated automatically by the DB trigger.");
      refresh();
    } catch (err) {
      setMessage(err.message);
    }
  }

  if (!drive) return <p>Loading...</p>;

  return (
    <div className="page">
      <h1>{drive.company_name} — {drive.job_role}</h1>
      <p className="muted">
        Min CGPA: {drive.min_cgpa} | Max Backlogs: {drive.max_backlogs} | Status: {drive.status}
      </p>

      {message && <p className="notice">{message}</p>}

      <table>
        <thead>
          <tr>
            <th>Student</th><th>Dept</th><th>CGPA</th><th>Status</th>
            <th>Change Status</th><th>Record Round</th><th>Record Offer</th>
          </tr>
        </thead>
        <tbody>
          {applicants.map((a) => (
            <ApplicantRow
              key={a.application_id}
              applicant={a}
              onSetStatus={setStatus}
              onRecordRound={recordRound}
              onRecordOffer={recordOffer}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ApplicantRow({ applicant, onSetStatus, onRecordRound, onRecordOffer }) {
  const [roundNumber, setRoundNumber] = useState("1");
  const [roundType, setRoundType] = useState(ROUND_TYPES[0]);
  const [roundResult, setRoundResult] = useState("Pass");
  const [packageLpa, setPackageLpa] = useState("");

  return (
    <tr>
      <td>{applicant.name} ({applicant.reg_no})</td>
      <td>{applicant.dept_name}</td>
      <td>{applicant.cgpa}</td>
      <td>{applicant.status}</td>
      <td>
        {/* Offer_Made isn't in STATUS_OPTIONS — it's only ever set by
            recording an actual Offer (see applications.py), never picked
            from this dropdown. Rendering the select anyway would silently
            fall back to showing "Applied" as selected, which misrepresents
            the real status, so show plain text once an offer exists. */}
        {STATUS_OPTIONS.includes(applicant.status) ? (
          <select
            value={applicant.status}
            onChange={(e) => onSetStatus(applicant.application_id, e.target.value)}
          >
            {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        ) : (
          <span className="muted">managed via Offer</span>
        )}
      </td>
      <td className="inline-form">
        <input
          type="number" min="1" value={roundNumber}
          onChange={(e) => setRoundNumber(e.target.value)}
          style={{ width: "3em" }}
        />
        <select value={roundType} onChange={(e) => setRoundType(e.target.value)}>
          {ROUND_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <select value={roundResult} onChange={(e) => setRoundResult(e.target.value)}>
          <option value="Pass">Pass</option>
          <option value="Fail">Fail</option>
          <option value="Pending">Pending</option>
        </select>
        <button onClick={() => onRecordRound(applicant.application_id, roundNumber, roundType, roundResult)}>
          Save
        </button>
      </td>
      <td className="inline-form">
        <input
          type="number" step="0.01" placeholder="LPA" value={packageLpa}
          onChange={(e) => setPackageLpa(e.target.value)}
          style={{ width: "5em" }}
        />
        <button onClick={() => onRecordOffer(applicant.application_id, packageLpa)}>
          Record Offer
        </button>
      </td>
    </tr>
  );
}
