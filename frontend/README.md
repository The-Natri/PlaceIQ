# PlaceIQ frontend

React 19 + Vite + React Router. No UI kit and no chart library: plain CSS
with design tokens, and charts as small SVG components.

## Run it

```bash
npm install          # again after every pull: teammates may add packages
npm run build        # production build into dist/; must pass before committing
npx oxlint src       # lint
```

The backend serves the built app and the API from **one origin**:
`http://localhost:8080` (see the main README for `docker compose up` or
`start.ps1`). The app calls the API at the relative path `/api`, so no URL
has to be configured and no CORS is needed.

For live editing, run the backend on port 8080, then `npm run dev`
(http://localhost:5173). Vite forwards `/api` to the backend
(`vite.config.js`), so the browser still sees a single origin.

## Where things live

```
src/
  styles/
    tokens.css      colours, radii, sizes   <- change these to restyle the whole app
    base.css        element defaults, focus ring, utility classes
    layout.css      app shell: sidebar, top bar, content column, mobile drawer
    components.css  cards, buttons, badges, tables, tabs, forms, alerts, modals
    charts.css      chart marks, legends, tooltips, heatmap
  components/
    layout/AppLayout.jsx   sidebar + top bar wrapper for every logged-in page
    ui/                    reusable pieces: Tabs, DataTable, Modal, Field,
                           Alert, StatusBadge, Loading/EmptyState, PageHeader, Card, StatCard
    charts/                CgpaScatter, BarList, MonthlyOffers/CumulativeOffers, Heatmap
    ApplicationDetailModal.jsx   rounds + offer + status history (student and admin)
  pages/
    auth/      Login, Signup
    student/   StudentDashboard (Overview / Eligible Drives / My Applications tabs), ProbabilityCard
    admin/     AdminDrives, AdminDriveDetail, DriveFormModal, AdminStudents, AdminAnalytics
  hooks/useApi.js   load a GET endpoint: { data, loading, error, reload }
  utils/format.js   numbers, dates, LPA (the API sends NUMERIC values as strings)
  utils/status.js   status labels, badge colours, allowed status transitions
  api.js            fetch wrapper that adds the login token
  auth/             AuthContext (who is logged in), ProtectedRoute, homeRoute
```

## Conventions

- **Every API call and response is documented in `../docs/API.md`.**
- **Colours** go in `styles/tokens.css`; components use the `var(--…)` names only.
- **Forms** use `<Field id label error>` around the input. It wires the label
  to the input (`htmlFor`/`id`) and links the error message for screen readers.
- **Tables** use `<DataTable>`, which handles loading, error and empty states.
- **Status** is always shown with `<StatusBadge>`: text plus colour, never colour alone.
- **Tabs** are synced to the URL (`?tab=`), so they survive a refresh and can be linked to.
- **Charts** use the validated colours `--viz-series-1/2`. Each chart has a
  table view, so no value is only reachable by hovering. Two measures on
  different scales get two charts, never one chart with two y-axes.
- **Status changes** offered in the UI mirror the database's allowed
  transitions (`utils/status.js` → `NEXT_STATUSES`). The database is the
  final authority: if they ever disagree, the API returns 409 and the
  message is shown.
