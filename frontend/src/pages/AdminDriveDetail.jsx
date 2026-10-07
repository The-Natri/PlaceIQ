import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Building2,
  GraduationCap,
  Users,
  BriefcaseBusiness,
  CircleCheck,
  ClipboardList,
  IndianRupee,
} from "lucide-react";
import { api } from "../api";
import "./AdminDriveDetail.css";

const STATUS_OPTIONS = [
  "Applied",
  "Shortlisted",
  "Interview_Scheduled",
  "Rejected",
  "Selected",
];

const ROUND_TYPES = [
  "Aptitude",
  "Technical",
  "HR",
  "Group_Discussion",
  "Coding_Test",
];

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
      await api.put(`/applications/${applicationId}/status`, {
        status,
      });

      refresh();
    } catch (err) {
      setMessage(err.message);
    }
  }

  async function recordRound(
    applicationId,
    roundNumber,
    roundType,
    result
  ) {
    setMessage("");

    try {
      await api.post(
        `/applications/${applicationId}/interview-rounds`,
        {
          round_number: Number(roundNumber),
          round_type: roundType,
          result,
        }
      );

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

      setMessage(
        "Offer recorded — student placement_status updated automatically by the DB trigger."
      );

      refresh();
    } catch (err) {
      setMessage(err.message);
    }
  }

  if (!drive) {
    return (
      <div className="drive-detail-loading">
        <div className="loading-card">Loading drive details...</div>
      </div>
    );
  }

  return (
    <main className="drive-detail-page">
      <section className="drive-detail-hero">
        <div>
          <p className="drive-eyebrow">DRIVE MANAGEMENT</p>

          <h1>
            {drive.company_name}
            <span> — {drive.job_role}</span>
          </h1>

          <p className="drive-subtitle">
            Review applicants, update statuses, record interview rounds
            and manage offers.
          </p>
        </div>

        <span
          className={`drive-detail-status drive-detail-status-${drive.status}`}
        >
          {drive.status}
        </span>
      </section>

      <section className="drive-summary-grid">
        <SummaryCard
          icon={<Building2 size={19} />}
          label="Company"
          value={drive.company_name}
        />

        <SummaryCard
          icon={<GraduationCap size={19} />}
          label="Minimum CGPA"
          value={drive.min_cgpa}
        />

        <SummaryCard
          icon={<ClipboardList size={19} />}
          label="Max Backlogs"
          value={drive.max_backlogs}
        />

        <SummaryCard
          icon={<Users size={19} />}
          label="Applicants"
          value={applicants.length}
        />
      </section>

      {message && (
        <div className="drive-detail-notice">
          <CircleCheck size={17} />
          <span>{message}</span>
        </div>
      )}

      <section className="drive-detail-card">
        <div className="drive-detail-card-header">
          <div>
            <p className="drive-eyebrow">APPLICANTS</p>
            <h2>Applicant Management</h2>
            <p>
              Update each student's application progress and record
              interview activity.
            </p>
          </div>

          <span className="applicant-count-pill">
            {applicants.length} Applicants
          </span>
        </div>

        {applicants.length === 0 ? (
          <div className="drive-empty-state">
            <div className="drive-empty-icon">
              <Users size={24} />
            </div>

            <h3>No applicants yet</h3>
            <p>
              Applications for this drive will appear here.
            </p>
          </div>
        ) : (
          <div className="drive-table-wrapper">
            <table className="drive-applicant-table">
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Department</th>
                  <th>CGPA</th>
                  <th>Status</th>
                  <th>Change Status</th>
                  <th>Record Round</th>
                  <th>Record Offer</th>
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
        )}
      </section>
    </main>
  );
}

function SummaryCard({ icon, label, value }) {
  return (
    <div className="drive-summary-card">
      <div className="drive-summary-icon">
        {icon}
      </div>

      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </div>
  );
}

function ApplicantRow({
  applicant,
  onSetStatus,
  onRecordRound,
  onRecordOffer,
}) {
  const [roundNumber, setRoundNumber] = useState("1");
  const [roundType, setRoundType] = useState(ROUND_TYPES[0]);
  const [roundResult, setRoundResult] = useState("Pass");
  const [packageLpa, setPackageLpa] = useState("");

  return (
    <tr>
      <td>
        <div className="applicant-name-cell">
          <div className="applicant-avatar">
            {applicant.name?.charAt(0)}
          </div>

          <div>
            <strong>{applicant.name}</strong>
            <span>{applicant.reg_no}</span>
          </div>
        </div>
      </td>

      <td>{applicant.dept_name}</td>

      <td>
        <span className="cgpa-pill">
          {applicant.cgpa}
        </span>
      </td>

      <td>
        <span
          className={`app-status app-status-${applicant.status}`}
        >
          {applicant.status?.replaceAll("_", " ")}
        </span>
      </td>

      <td>
        {STATUS_OPTIONS.includes(applicant.status) ? (
          <select
            className="compact-select"
            value={applicant.status}
            onChange={(e) =>
              onSetStatus(
                applicant.application_id,
                e.target.value
              )
            }
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s.replaceAll("_", " ")}
              </option>
            ))}
          </select>
        ) : (
          <span className="offer-managed-text">
            Managed via Offer
          </span>
        )}
      </td>

      <td>
        <div className="round-controls">
          <input
            className="round-number-input"
            type="number"
            min="1"
            value={roundNumber}
            onChange={(e) =>
              setRoundNumber(e.target.value)
            }
          />

          <select
            className="compact-select"
            value={roundType}
            onChange={(e) =>
              setRoundType(e.target.value)
            }
          >
            {ROUND_TYPES.map((t) => (
              <option key={t} value={t}>
                {t.replaceAll("_", " ")}
              </option>
            ))}
          </select>

          <select
            className="compact-select"
            value={roundResult}
            onChange={(e) =>
              setRoundResult(e.target.value)
            }
          >
            <option value="Pass">Pass</option>
            <option value="Fail">Fail</option>
            <option value="Pending">Pending</option>
          </select>

          <button
            className="table-action-button"
            onClick={() =>
              onRecordRound(
                applicant.application_id,
                roundNumber,
                roundType,
                roundResult
              )
            }
          >
            Save
          </button>
        </div>
      </td>

      <td>
        <div className="offer-controls">
          <div className="offer-input-wrapper">
            <IndianRupee size={14} />

            <input
              type="number"
              step="0.01"
              placeholder="LPA"
              value={packageLpa}
              onChange={(e) =>
                setPackageLpa(e.target.value)
              }
            />
          </div>

          <button
            className="offer-record-button"
            onClick={() =>
              onRecordOffer(
                applicant.application_id,
                packageLpa
              )
            }
          >
            Record Offer
          </button>
        </div>
      </td>
    </tr>
  );
}