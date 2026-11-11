# Data Handling and Publication Policy

Metrixa can collect company records, source URLs, page text, technology
signals, decision-maker names, and contact evidence from public web sources.
Some records can still be personal data even when the source page is public.

## What belongs in the public repository

Public Git history may contain source code, documentation, synthetic fixtures,
redacted screenshots, and reproducible configuration templates such as
`.env.example`. It must not contain:

- local SQLite databases or database backups;
- Excel, CSV, or Google Sheets exports containing live lead data;
- crawl pages, raw HTML, evidence text, or generated reports with live records;
- API keys, OAuth tokens, service-account files, cookies, or private URLs; or
- personal email addresses, direct phone numbers, or identifiable contact
  records copied from a live run.

The repository `.gitignore` is configured to block the common runtime paths,
but an ignore rule cannot remove a file that is already tracked. Check
`git ls-files` before publishing.

## Local operation

Keep live data in a local database or a protected customer environment. Use
synthetic or anonymized fixtures for tests and screenshots. Review source-site
terms, lawful basis, retention, access controls, and deletion requests before
using the crawler for a real customer workflow.

## Publication checklist

Before every public push:

1. Run `git status` and inspect every staged path.
2. Search for secrets and personal data in the diff.
3. Confirm that `.env`, databases, exports, `output/`, and `tmp/` are ignored
   and untracked.
4. Remove any previously committed sensitive file from Git history using an
   approved repository-history procedure; deleting it in a new commit alone
   does not erase old copies.
5. Re-run the application with an empty or synthetic database and check that
   the public documentation still works.

This policy is an engineering control, not legal advice. The operator or
customer remains responsible for applicable privacy and data-protection rules.
