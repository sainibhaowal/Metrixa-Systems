# Contributing

Thanks for helping improve Metrixa Engine.

## Development setup

The project has a Python/FastAPI engine and a Next.js cockpit.

```powershell
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Set-Location web
npm ci
```

Copy `.env.example` to `.env` only for local development. Never commit the
resulting file or any provider credential.

## Safe contribution rules

- Use synthetic, anonymized, or fixture data in code and tests.
- Do not add live lead databases, exports, crawl evidence, screenshots with
  contacts, or customer material.
- Keep changes focused and explain behavior changes in the pull request.
- Preserve source attribution and the license of third-party code or assets.
- Do not add a provider, scraper, or integration without documenting its
  terms, rate limits, failure behavior, and data handling.

## Checks before opening a pull request

```powershell
Set-Location web
npm run build
Set-Location ..
.\.venv\Scripts\python.exe -m pytest -q
```

If a check cannot run locally, say why in the pull request. Include a short
manual verification note for UI changes.

## Pull request checklist

- [ ] No secrets or live personal data are included.
- [ ] Documentation and `.env.example` are updated when configuration changes.
- [ ] Tests or build checks were run, or the reason is recorded.
- [ ] New dependencies and their licenses are documented.
- [ ] The change is compatible with Apache License 2.0 for original project
      code.
