# Public Release Checklist

Use this checklist before making a branch or repository public.

## Repository and license

- [ ] `LICENSE` is Apache License 2.0.
- [ ] `NOTICE` names the copyright holder and public-repository boundary.
- [ ] `README.md` links to the license, security policy, and data policy.
- [ ] Third-party package and asset notices have been reviewed.

## Data and secrets

- [ ] `.env`, tokens, cookies, service-account files, and private URLs are absent.
- [ ] Live SQLite databases, exports, crawl evidence, reports, and temp files
      are absent from the commit.
- [ ] `git ls-files` contains only public-safe files.
- [ ] A secret scan and a personal-data review were completed on the diff.

## Verification

- [ ] The app starts from a clean environment with synthetic or empty data.
- [ ] `npm run build` passes in `web/`.
- [ ] Python checks pass or their limitations are documented.
- [ ] Public documentation does not promise unmeasured accuracy, mailbox
      verification, or production security.
- [ ] The release notes explain known limitations and data-source terms.
