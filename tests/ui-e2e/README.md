# ReplayGate UI E2E (Playwright)

## Prerequisites
- Node.js 18+
- Services running via Docker Compose

## Install
```powershell
cd tests\ui-e2e
npm ci
npx playwright install --with-deps
```

## Run
```powershell
$env:RG_WEB_BASE = "http://localhost:5173"
$env:RG_API_BASE = "http://localhost:8080"

npx playwright test
```

## Notes
- Tests use the Platform API to seed runs when needed.
- Base URLs can be overridden via RG_WEB_BASE and RG_API_BASE.
