import { Sparkles } from "lucide-react";
import { Card } from "../../components/ui/Layout";
import { Loading } from "../../components/ui/Feedback";
import { Alert } from "../../components/ui/Alert";
import { formatCgpa } from "../../utils/format";

// Plain-language bands for the probability. Shown as text, so the meaning
// never depends on colour.
function band(p) {
  if (p >= 0.7) return { label: "Strong chance", tone: "Your profile looks like students who were placed." };
  if (p >= 0.4) return { label: "Moderate chance", tone: "Your profile is in between — skills and clearing backlogs can tip it." };
  return { label: "Lower chance for now", tone: "Raising your CGPA, clearing backlogs and adding skills helps most." };
}

export function ProbabilityCard({ probability, loading, error, profile }) {
  return (
    <Card title="Placement probability" subtitle="An estimate from the PlaceIQ prediction model">
      {loading && <Loading label="Asking the model…" />}
      {error && <Alert variant="info">The prediction service isn't available right now. Try again later.</Alert>}
      {probability !== null && probability !== undefined && (() => {
        const pct = Math.round(probability * 100);
        const b = band(probability);
        return (
          <div style={{ display: "grid", gap: 14 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
              <span style={{ fontSize: "2.4rem", fontWeight: 800, lineHeight: 1 }}>{pct}%</span>
              <span style={{ fontWeight: 650 }}>{b.label}</span>
            </div>
            <div
              role="meter"
              aria-label="Placement probability"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={pct}
              style={{ height: 8, borderRadius: 4, background: "var(--c-neutral-soft)" }}
            >
              <div style={{ width: `${pct}%`, height: "100%", borderRadius: 4, background: "var(--viz-series-1)" }} />
            </div>
            <p className="muted">{b.tone}</p>

            <div className="divider" />
            <div>
              <div className="section-title"><Sparkles size={13} aria-hidden="true" /> How this is worked out</div>
              <p className="muted" style={{ fontSize: "0.85rem" }}>
                A logistic-regression model looks at four things — your CGPA ({formatCgpa(profile?.cgpa)}),
                backlogs ({profile?.backlogs ?? "—"}), department ({profile?.dept_code ?? "—"}) and number of
                skills ({profile?.skills?.length ?? "—"}) — and compares them with past placement outcomes.
                CGPA has the biggest effect, each backlog pulls the estimate down, and more skills push it up.
              </p>
              <p className="muted" style={{ fontSize: "0.8rem", marginTop: 6 }}>
                Treat it as a rough guide, not a promise: the model was trained on synthetic data and
                checked on only 36 students.
              </p>
            </div>
          </div>
        );
      })()}
    </Card>
  );
}
