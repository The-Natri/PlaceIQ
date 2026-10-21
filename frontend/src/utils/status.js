// Display labels and badge colours for every status value the API returns.

const VARIANTS = {
  // application
  Applied: "info",
  Shortlisted: "primary",
  Interview_Scheduled: "warning",
  Selected: "success",
  Offer_Made: "success",
  Rejected: "danger",
  // interview round result
  Pass: "success",
  Fail: "danger",
  // offer (and a round still Pending)
  Pending: "warning",
  Accepted: "success",
  Declined: "danger",
  // student
  Placed: "success",
  "Not Placed": "neutral",
  // drive
  Upcoming: "info",
  Ongoing: "warning",
  Completed: "neutral",
  Cancelled: "danger",
};

export function statusVariant(status) {
  return VARIANTS[status] || "neutral";
}

export function statusLabel(status) {
  return (status || "").replaceAll("_", " ");
}

// Mirror of the allowed-transitions table enforced by the database trigger
// trg_application_status_transition (db/schema.sql, Section 6). The UI only
// uses it to offer valid choices; the database still makes the final call,
// so if this ever drifts the API answers 409 and the error is shown.
export const NEXT_STATUSES = {
  Applied: ["Shortlisted", "Interview_Scheduled", "Rejected"],
  Shortlisted: ["Interview_Scheduled", "Selected", "Rejected"],
  Interview_Scheduled: ["Selected", "Rejected"],
  Selected: ["Rejected"], // Offer_Made is set by recording an offer, not by hand
  Offer_Made: [],
  Rejected: [],
};

export const ROUND_TYPES = ["Aptitude", "Technical", "HR", "Group_Discussion", "Coding_Test"];
export const DRIVE_STATUSES = ["Upcoming", "Ongoing", "Completed", "Cancelled"];
export const DRIVE_TYPES = ["Full-Time", "Internship"];
