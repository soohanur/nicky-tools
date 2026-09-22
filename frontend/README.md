# Scraply - Frontend

Next.js 16 (App Router) dashboard, exported as static HTML (`output: "export"`).
JSX, Tailwind (utilities) on top of the design tokens in `src/app/globals.css`.
Talks to the FastAPI backend with a JWT kept in localStorage; there is no Node
server at runtime, nginx serves `out/`.

## Structure
```
src/
  app/
    layout.jsx            # root: <html>, Inter font, metadata, theme bootstrap, toast provider
    globals.css           # design system: tokens, cards, buttons, rail, tables, modal, auth
    (auth)/               # public pages (redirect to / when already signed in)
      layout.jsx
      login/page.jsx  register/page.jsx
    (dashboard)/          # signed-in pages, wrapped in <Shell> (rail + app bar + job state)
      layout.jsx
      page.jsx            #   Controls: upload, column mapping, lifecycle, progress, stats
      files/  logs/  settings/
    not-found.jsx
  components/
    layout/               # Shell (auth gate + JobProvider), Rail, AppBar
    dashboard/            # InputFileCard, ProgressCard, StatsCard, ColumnMapperModal,
                          # UploadedFilesTable, ExtractionLogsTable, NotificationPanel,
                          # WorkerConfigCard, NotificationsCard
    forms/                # LoginForm, RegisterForm, AuthAside, AuthBrand, PasswordInput
    ui/                   # Icon (SVG set), Alert, Switch, Logo
  data/                   # site.js (copy + mapping steps), nav.js (rail items)
  hooks/                  # useAuth, useJob (job state machine), useTheme, usePrefs,
                          # useNotifications, useToast, useFetch
  lib/                    # api-client.js (the ONLY fetch caller), api.js, auth.js,
                          # ws.js, notifications.js, prefs.js, theme.js, store.js, format.js, env.js
```

## Conventions
- `@/*` -> `src/*` (see jsconfig).
- Only `src/lib/api-client.js` calls `fetch`. Pages and components go through `src/lib/api.js`.
- Every page is a client component; nothing touches `window` during render
  (persisted values come in through `useSyncExternalStore`).
- Copy lives in `src/data/site.js`. Use "-" in text, never an em dash.

## Env
Copy `.env.example` -> `.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000   # backend origin, no /api/v1 suffix; empty in prod
```

## Scripts
```bash
npm run dev      # local dev on :3000
npm run build    # static export -> out/
npm run lint
```
