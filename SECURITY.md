# Security Policy

## Scope

This policy covers the source code and documentation in the public Metrixa
Engine repository. It does not make the local crawler, deployment environment,
third-party providers, or generated lead datasets production-secure by itself.

## Reporting a vulnerability

Please do not report security issues in a public GitHub issue, pull request, or
discussion. Use GitHub's **Private vulnerability reporting** for the repository
when it is enabled. If it is not enabled, contact the maintainer through the
private contact method shown in the repository profile and include:

- a short description and affected component;
- reproducible steps or a minimal proof of concept;
- impact, prerequisites, and any known workaround; and
- the commit, release, or environment where it was observed.

Do not include API keys, passwords, real lead exports, personal contact data,
or other secrets in the report. Redact them and describe how they were found.

## Response process

The maintainer will acknowledge a report when practical, reproduce and assess
the issue, coordinate a fix, and publish a release note when disclosure is
appropriate. Please allow time for remediation before public disclosure.

## Safe handling requirements

- Keep `.env` and provider credentials outside Git.
- Never commit `data/*.db`, exports, crawl evidence, generated reports, or
  real personal contact data.
- Rotate a credential immediately if it may have been exposed.
- Review dependency and framework updates before deploying to an internet-
  reachable environment.
- Treat DNS MX results as domain-level signals, not mailbox verification.

The project is a local pilot. Operators remain responsible for access control,
data protection, lawful processing, source-site terms, and deployment security.
