# HealthFlow Phase 6D: React Frontend — Design Spec

## Overview

Build the React frontend for the HealthFlow Broker Dashboard. Three pages matching Stitch designs: Login, Client Portfolio (list), and Client Profile & Analysis (detail). Uses the Phase 6A auth backend for JWT authentication and the Phase 1-5 API endpoints for running analyses.

## Tech Stack

- React 18 with Vite
- Tailwind CSS with Stitch M3 color system
- React Router v6 for client-side routing
- Manrope (headlines) + Inter (body/labels) fonts
- Material Symbols Outlined icons
- Fetch API for backend calls (no axios dependency)

## Pages

| Route | Page | Source Design | Data Source |
|-------|------|---------------|-------------|
| `/login` | Login | `docs/designs/login-screen-stitch.html` | `POST /auth/login`, `POST /auth/register` |
| `/` | Client Portfolio | `docs/designs/client-management-stitch.html` | `GET /clients`, `POST /clients`, `DELETE /clients/{id}` |
| `/clients/:id` | Client Profile & Analysis | `docs/designs/client-profile-stitch.html` | `GET /clients/{id}`, `PUT /clients/{id}`, Phase 1-5 endpoints |

## Project Structure

```
frontend/
├── index.html
├── package.json
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
├── src/
│   ├── main.jsx                   # React DOM entry point
│   ├── App.jsx                    # Router setup with auth guard
│   ├── index.css                  # Tailwind directives + custom styles
│   ├── api/
│   │   └── client.js              # API wrapper with JWT auth
│   ├── contexts/
│   │   └── AuthContext.jsx        # JWT state, login/logout/refresh
│   ├── components/
│   │   ├── Layout.jsx             # Side nav + top bar shell
│   │   ├── Sidebar.jsx            # Left sidebar navigation
│   │   ├── TopBar.jsx             # Top app bar with search + profile
│   │   └── ProtectedRoute.jsx     # Auth guard redirect
│   ├── pages/
│   │   ├── LoginPage.jsx          # Split-panel login form
│   │   ├── ClientListPage.jsx     # Client portfolio table + filters
│   │   └── ClientProfilePage.jsx  # Client detail + analysis workflow
```

## Auth Flow

1. User visits any route → `ProtectedRoute` checks `AuthContext.isAuthenticated`
2. If not authenticated → redirect to `/login`
3. Login form calls `POST /auth/login` with email/password
4. On success: store access token + refresh token in AuthContext state (memory, not localStorage)
5. API client attaches `Authorization: Bearer <token>` to all requests
6. On 401 response: try `POST /auth/refresh`, if fails → clear auth state → redirect to `/login`
7. Logout: clear tokens from state, redirect to `/login`

## API Client (`src/api/client.js`)

```javascript
// Thin wrapper around fetch
// - Prepends API_BASE_URL (default http://localhost:8000)
// - Attaches JWT from auth context
// - Handles 401 → refresh → retry
// - Returns parsed JSON
// - Throws on non-2xx responses
```

Methods:
- `api.get(path)` → GET with auth header
- `api.post(path, body)` → POST with JSON body + auth header
- `api.put(path, body)` → PUT with JSON body + auth header
- `api.del(path)` → DELETE with auth header

## Tailwind Config

Extract the M3 color system from Stitch designs:

```javascript
colors: {
  primary: "#006194",
  "primary-container": "#007bb9",
  "on-primary": "#ffffff",
  "on-primary-container": "#fdfcff",
  secondary: "#006a61",
  "secondary-container": "#86f2e4",
  "on-secondary": "#ffffff",
  "on-secondary-container": "#006f66",
  tertiary: "#006195",
  "tertiary-container": "#287ab3",
  error: "#ba1a1a",
  "error-container": "#ffdad6",
  "on-error": "#ffffff",
  "on-error-container": "#93000a",
  surface: "#f7f9fb",
  "surface-container": "#eceef0",
  "surface-container-low": "#f2f4f6",
  "surface-container-high": "#e6e8ea",
  "surface-container-highest": "#e0e3e5",
  "surface-container-lowest": "#ffffff",
  "on-surface": "#191c1e",
  "on-surface-variant": "#3f4850",
  outline: "#707881",
  "outline-variant": "#bfc7d2",
  "inverse-surface": "#2d3133",
  "inverse-primary": "#93ccff",
},
fontFamily: {
  headline: ["Manrope", "sans-serif"],
  body: ["Inter", "sans-serif"],
  label: ["Inter", "sans-serif"],
},
borderRadius: {
  DEFAULT: "0.125rem",
  lg: "0.25rem",
  xl: "0.5rem",
  full: "0.75rem",
},
```

## Page Details

### LoginPage (`/login`)

Pixel-match the Stitch login design:
- Split panel: left = brand hero (primary blue bg, logo, headline, testimonial), right = login form
- Mobile: form only (hero hidden)
- Form fields: email, password with Material icons
- "Remember me" checkbox, "Forgot password?" link
- "Sign In" button → calls `POST /auth/login`
- "Create a Broker Account" link → calls `POST /auth/register` (simple inline form or expand)
- SSL Secure + HIPAA Compliant badges
- On success: redirect to `/`

### ClientListPage (`/`)

Pixel-match the Stitch client management design:
- Page header: "Client Portfolio" + "Add Client" button
- Filter bar: 4-column grid (Zip Code input, Age Range select, Income select, Apply Filters button)
- Client table with columns: Name (with avatar initials), Zip Code, Age, Primary Plan (badge), Last Analysis Date, Actions
- Row hover reveals action buttons: Run Analysis, Edit, View Profile
- Pagination footer
- Summary stats: 3-column grid (New Leads, Analysis Score Avg, Urgent Renewals)
- "Add Client" opens a modal with ClientCreate form fields
- "View Profile" navigates to `/clients/:id`
- Data from `GET /clients`

### ClientProfilePage (`/clients/:id`)

Pixel-match the Stitch client profile design:
- Client header: avatar, name, age, income, location, "Active Policy" badge
- Action buttons: "Edit Profile", "Generate Appeal Draft"
- Tabs: Plan Analysis (default), Profile Details, Prescriptions, Preferred Doctors
- **Plan Analysis tab:**
  - Analysis Workflow stepper (5 phases mapping to Phase 1-5 features)
  - Each step has: status (Complete/In Progress/Pending), description, action button
  - Step 1 "Extract Data" → calls `POST /translate` with client's SoB if available
  - Step 2 "Scrape Networks" → calls `POST /verify` with client's doctors/prescriptions
  - Step 3 "Categorize Risks" → calls `POST /calculate` with client's usage data
  - Step 4 "Compare Marketplace" → calls `POST /compare` with client's profile
  - Step 5 "Final Recommendation" → calls `POST /estimate` for cost breakdown
  - Summary cards: Annual Out-of-Pocket, Projected Savings
  - Risk categorization panel with utilization progress bars
  - Locked comparison section (gated by workflow progress)
- **Profile Details tab:** editable form with client fields, save via `PUT /clients/{id}`
- **Prescriptions tab:** list of client's prescriptions, add/remove
- **Preferred Doctors tab:** list of client's doctors with NPIs, add/remove
- Data from `GET /clients/{id}`

## Vite Dev Server Proxy

Configure Vite to proxy `/api` requests to FastAPI backend at `http://localhost:8000` to avoid CORS issues during development:

```javascript
// vite.config.js
export default defineConfig({
  server: {
    proxy: {
      '/auth': 'http://localhost:8000',
      '/clients': 'http://localhost:8000',
      '/compare': 'http://localhost:8000',
      '/calculate': 'http://localhost:8000',
      '/translate': 'http://localhost:8000',
      '/appeal': 'http://localhost:8000',
      '/verify': 'http://localhost:8000',
      '/estimate': 'http://localhost:8000',
      '/plans': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    }
  }
})
```

## What This Does NOT Do

- No frontend unit tests (visual verification only)
- No SSR/SSG (pure SPA)
- No state management library (React Context is sufficient)
- No dark mode (light only, matching Stitch designs)
- No mobile-native responsive (responsive web only)
- No Docker setup (Phase 6E)
