# Greenlight frontend

Next.js 16 (App Router) + React 19 + Tailwind CSS v4. The UI was designed in Lovable from
[docs/lovable/](../docs/lovable/) and ported here.

## Layout

| Path | Role |
|---|---|
| `app/*/page.tsx` | Route: page title/metadata only (server component) |
| `app/*/route-client.tsx` | Loads data for the route and renders its view |
| `views/` | Screens (queue, review, trace, evals, about, new application); data and callbacks via props |
| `components/` | Shell, badges/trust tags, small UI primitives, `AppLink` navigation adapter, async loading view |
| `lib/api.ts` | One typed function per backend endpoint, error normalisation, optional mocks |
| `lib/types.ts` | API contract types (nullable where the backend can return null) |
| `mocks/data.ts` | Fixtures captured from the real API, used only when mocks are enabled |
| `app/globals.css` | Design tokens (light/dark) and component styles |

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8010` | Greenlight API the browser calls |
| `NEXT_PUBLIC_USE_MOCKS` | `false` | `true` serves the fixtures in `mocks/` instead of the API |
| `NEXT_PUBLIC_MOCK_CLAUDE_DELAY_MS` | `8000` | Simulated Claude review time when mocks are on |

## Run

```bash
npm install
npm run dev -- --port 3100
```
