import { useEffect, useState } from "react";
import { CircleCheck, CircleX } from "lucide-react";
import { api } from "../api";
import { Alert } from "./ui/Alert";
import { EmptyState, Loading } from "./ui/Feedback";
import { Modal } from "./ui/Modal";
import { StatusBadge } from "./ui/StatusBadge";
import { formatDate, formatDateTime, formatLpa } from "../utils/format";
import { statusLabel } from "../utils/status";

/**
 * Everything about one application: interview rounds, the offer (full
 * detail from GET /offers/:id) and the status history that the database's
 * audit trigger records. Students also get Accept / Decline on a Pending
 * offer; admins see the same view read-only.
 */
export function ApplicationDetailModal({ applicationId, open, onClose, canRespond = false, onChanged }) {
  const [app, setApp] = useState(null);
  const [offer, setOffer] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    setError("");
    try {
      const detail = await api.get(`/applications/${applicationId}`);
      setApp(detail);
      setOffer(detail.offer ? await api.get(`/offers/${detail.offer.offer_id}`) : null);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    if (open && applicationId) {
      setApp(null);
      setOffer(null);
      setNotice("");
      load();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, applicationId]);

  async function respond(action) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.post(`/offers/${offer.offer_id}/${action}`);
      setNotice(action === "accept" ? "Offer accepted. Congratulations!" : "Offer declined.");
      await load();
      onChanged?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      wide
      title={app ? `${app.company_name} · ${app.job_role}` : "Application"}
      subtitle={app ? `Applied ${formatDateTime(app.applied_at)}` : undefined}
    >
      <Alert variant="error">{error}</Alert>
      <Alert variant="success">{notice}</Alert>
      {!app && !error && <Loading />}

      {app && (
        <>
          <dl className="kv">
            <div><dt>Current status</dt><dd><StatusBadge status={app.status} /></dd></div>
            <div><dt>Drive date</dt><dd>{formatDate(app.drive_date)}</dd></div>
            <div><dt>Advertised package</dt><dd>{formatLpa(app.package_lpa)}</dd></div>
          </dl>

          <section>
            <h3 className="section-title">Offer</h3>
            {offer ? (
              <div className="card">
                <div className="card-body">
                  <dl className="kv">
                    <div><dt>Status</dt><dd><StatusBadge status={offer.status} /></dd></div>
                    <div><dt>Package offered</dt><dd>{formatLpa(offer.offered_package_lpa)}</dd></div>
                    <div><dt>Offer date</dt><dd>{formatDate(offer.offer_date)}</dd></div>
                    <div><dt>Joining date</dt><dd>{formatDate(offer.joining_date)}</dd></div>
                  </dl>
                  {canRespond && offer.status === "Pending" && (
                    <div className="inline-actions" style={{ marginTop: 14 }}>
                      <button type="button" className="btn btn-success" disabled={busy} onClick={() => respond("accept")}>
                        <CircleCheck size={16} aria-hidden="true" /> Accept offer
                      </button>
                      <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => respond("decline")}>
                        <CircleX size={16} aria-hidden="true" /> Decline
                      </button>
                      <span className="muted">You can hold only one accepted offer.</span>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <p className="muted">No offer yet.</p>
            )}
          </section>

          <div className="grid-2">
            <section>
              <h3 className="section-title">Interview rounds</h3>
              {app.interview_rounds.length === 0 ? (
                <EmptyState title="No rounds recorded" />
              ) : (
                <div className="table-wrap">
                  <table className="table">
                    <thead><tr><th scope="col">#</th><th scope="col">Round</th><th scope="col">Date</th><th scope="col">Result</th></tr></thead>
                    <tbody>
                      {app.interview_rounds.map((r) => (
                        <tr key={r.round_id}>
                          <td className="num">{r.round_number}</td>
                          <td>{statusLabel(r.round_type)}</td>
                          <td className="nowrap">{formatDate(r.round_date)}</td>
                          <td><StatusBadge status={r.result} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section>
              <h3 className="section-title">Status history</h3>
              {app.status_history.length === 0 ? (
                <p className="muted">Still at its first status, Applied.</p>
              ) : (
                <ol className="timeline">
                  {app.status_history.map((h, i) => (
                    <li key={i}>
                      <div>
                        {statusLabel(h.old_status)} → <strong>{statusLabel(h.new_status)}</strong>
                      </div>
                      <div className="timeline-when">{formatDateTime(h.changed_at)}</div>
                    </li>
                  ))}
                </ol>
              )}
              <p className="field-hint" style={{ marginTop: 8 }}>
                Recorded automatically by the database (audit trigger).
              </p>
            </section>
          </div>
        </>
      )}
    </Modal>
  );
}
