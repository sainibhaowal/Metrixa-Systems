# Third-Party Notices

Metrixa is distributed under the Apache License 2.0 for its original code and
documentation. The Apache license does **not** relicense third-party packages,
vendor files, brand artwork, source data, or external services. Those materials
remain under the terms shown below.

This inventory was checked against the repository manifests and bundled files
on 2026-11-11. SPDX identifiers are used where a package publishes a standard
license identifier. The linked upstream license file is the authoritative text.

## Inventory basis

- Python direct dependencies and build requirements: `pyproject.toml`.
- JavaScript direct dependencies and exact resolved versions: `web/package.json`
  and `web/package-lock.json` (455 lockfile package entries, including
  transitive packages).
- Bundled vendor files: `docs/Case Study/vendor/` and `web/public/icons/`.
- Embedded provider artwork: `web/src/components/icons/ProviderLogos.tsx`.
- The lockfile is the source of truth for the complete transitive JavaScript
  graph. This document lists every direct package and every bundled asset family
  that this repository ships or references.

## Python runtime dependencies

| Package | Declared version | License | Upstream license |
| --- | --- | --- | --- |
| fastapi | `>=0.115.0` | MIT | [LICENSE](https://github.com/fastapi/fastapi/blob/master/LICENSE) |
| httpx | `httpx[http2]>=0.27.0` | BSD-3-Clause | [LICENSE.md](https://github.com/encode/httpx/blob/master/LICENSE.md) |
| sse-starlette | `>=2.1.0` | BSD-3-Clause | [LICENSE](https://github.com/sysid/sse-starlette/blob/main/LICENSE) |
| uvicorn | `>=0.30.0` | BSD-3-Clause | [LICENSE.md](https://github.com/encode/uvicorn/blob/master/LICENSE.md) |
| selectolax | `>=0.3.21` | MIT | [LICENSE](https://github.com/rushter/selectolax/blob/master/LICENSE) |
| beautifulsoup4 | `>=4.12.3` | MIT | [LICENSE](https://bazaar.launchpad.net/~leonardr/beautifulsoup/bs4/view/head:/LICENSE) |
| lxml | `>=5.2.0` | BSD-3-Clause | [LICENSE.txt](https://github.com/lxml/lxml/blob/master/LICENSE.txt) |
| trafilatura | `>=1.12.0` | Apache-2.0 | [LICENSE](https://github.com/adbar/trafilatura/blob/master/LICENSE) |
| rapidfuzz | `>=3.9.0` | MIT | [LICENSE](https://github.com/rapidfuzz/RapidFuzz/blob/main/LICENSE) |
| phonenumbers | `>=8.13.40` | Apache-2.0 | [LICENSE](https://github.com/daviddrysdale/python-phonenumbers/blob/dev/LICENSE) |
| tldextract | `>=5.1.2` | BSD-3-Clause | [LICENSE](https://github.com/john-kurkowski/tldextract/blob/master/LICENSE) |
| dnspython | `>=2.6.1` | ISC | [LICENSE](https://github.com/rthalley/dnspython/blob/master/LICENSE) |
| email-validator | `>=2.2.0` | Unlicense | [LICENSE](https://github.com/JoshData/python-email-validator/blob/main/LICENSE) |
| pydantic | `>=2.8.0` | MIT | [LICENSE](https://github.com/pydantic/pydantic/blob/main/LICENSE) |
| pydantic-settings | `>=2.4.0` | MIT | [LICENSE](https://github.com/pydantic/pydantic-settings/blob/main/LICENSE) |
| python-dotenv | `>=1.0.1` | BSD-3-Clause | [LICENSE](https://github.com/theskumar/python-dotenv/blob/main/LICENSE) |
| typer | `>=0.12.3` | MIT | [LICENSE](https://github.com/fastapi/typer/blob/master/LICENSE) |
| rich | `>=13.7.1` | MIT | [LICENSE](https://github.com/Textualize/rich/blob/master/LICENSE) |
| openpyxl | `>=3.1.5` | MIT | [LICENCE.RST](https://foss.heptapod.net/openpyxl/openpyxl/-/blob/branch/default/LICENCE.RST) |
| tenacity | `>=8.5.0` | Apache-2.0 | [LICENSE](https://github.com/jd/tenacity/blob/main/LICENSE) |
| gspread | `>=6.1.0` | MIT | [LICENSE.txt](https://github.com/burnash/gspread/blob/master/LICENSE.txt) |
| google-auth | `>=2.30.0` | Apache-2.0 | [LICENSE](https://github.com/googleapis/google-auth-library-python/blob/main/LICENSE) |

## Python build and development dependencies

These packages are used to build or test the Python project and are declared in
`pyproject.toml`.

| Package | Declared version | License | Upstream license |
| --- | --- | --- | --- |
| setuptools | `>=68.0` | MIT | [LICENSE](https://github.com/pypa/setuptools/blob/main/LICENSE) |
| wheel | unpinned | MIT | [LICENSE.txt](https://github.com/pypa/wheel/blob/main/LICENSE.txt) |
| pytest | `>=8.3.0` | MIT | [LICENSE](https://github.com/pytest-dev/pytest/blob/main/LICENSE) |
| pytest-asyncio | `>=0.23.8` | Apache-2.0 | [LICENSE](https://github.com/pytest-dev/pytest-asyncio/blob/master/LICENSE) |
| pytest-cov | `>=5.0.0` | MIT | [LICENSE](https://github.com/pytest-dev/pytest-cov/blob/master/LICENSE) |

## JavaScript runtime dependencies

The versions below are the currently resolved direct versions in
`web/package-lock.json`.

| Package | Resolved version | License | Upstream license |
| --- | --- | --- | --- |
| clsx | `2.1.1` | MIT | [license](https://github.com/lukeed/clsx/blob/master/license) |
| lucide-react | `1.70.0` | ISC | [LICENSE](https://github.com/lucide-icons/lucide/blob/main/LICENSE) |
| next | `14.2.35` | MIT | [license.md](https://github.com/vercel/next.js/blob/canary/license.md) |
| react | `18.3.1` | MIT | [LICENSE](https://github.com/facebook/react/blob/main/LICENSE) |
| react-dom | `18.3.1` | MIT | [LICENSE](https://github.com/facebook/react/blob/main/LICENSE) |
| recharts | `2.15.4` | MIT | [LICENSE](https://github.com/recharts/recharts/blob/main/LICENSE) |
| tailwind-merge | `2.6.1` | MIT | [LICENSE.md](https://github.com/dcastil/tailwind-merge/blob/main/LICENSE.md) |

## JavaScript build and development dependencies

| Package | Resolved version | License | Upstream license |
| --- | --- | --- | --- |
| @types/node | `20.19.43` | MIT | [DefinitelyTyped LICENSE](https://github.com/DefinitelyTyped/DefinitelyTyped/blob/master/LICENSE) |
| @types/react | `18.3.31` | MIT | [DefinitelyTyped LICENSE](https://github.com/DefinitelyTyped/DefinitelyTyped/blob/master/LICENSE) |
| @types/react-dom | `18.3.7` | MIT | [DefinitelyTyped LICENSE](https://github.com/DefinitelyTyped/DefinitelyTyped/blob/master/LICENSE) |
| autoprefixer | `10.6.2` | MIT | [LICENSE](https://github.com/postcss/autoprefixer/blob/main/LICENSE) |
| eslint | `8.57.1` | MIT | [LICENSE](https://github.com/eslint/eslint/blob/main/LICENSE) |
| eslint-config-next | `14.2.23` | MIT | [Next.js license](https://github.com/vercel/next.js/blob/canary/license.md) |
| postcss | `8.5.32` | MIT | [LICENSE](https://github.com/postcss/postcss/blob/main/LICENSE) |
| prettier | `3.9.10` | MIT | [LICENSE](https://github.com/prettier/prettier/blob/main/LICENSE) |
| tailwindcss | `3.4.19` | MIT | [LICENSE](https://github.com/tailwindlabs/tailwindcss/blob/main/LICENSE) |
| typescript | `5.9.3` | Apache-2.0 | [LICENSE.txt](https://github.com/microsoft/TypeScript/blob/main/LICENSE.txt) |

## Bundled vendor files

| Repository path | Upstream project | License / terms |
| --- | --- | --- |
| `docs/Case Study/vendor/katex.min.js` | KaTeX | [MIT license](https://github.com/KaTeX/KaTeX/blob/main/LICENSE) |
| `docs/Case Study/vendor/auto-render.min.js` | KaTeX auto-render extension | [MIT license](https://github.com/KaTeX/KaTeX/blob/main/LICENSE) |
| `docs/Case Study/vendor/katex.min.css` | KaTeX | [MIT license](https://github.com/KaTeX/KaTeX/blob/main/LICENSE) |
| `docs/Case Study/vendor/fonts/*.woff2` | KaTeX fonts | [MIT license](https://github.com/KaTeX/KaTeX/blob/main/LICENSE) |

The KaTeX vendor files and fonts are kept in the repository for the case-study
PDF/web rendering path. If they are replaced or regenerated, re-check the
upstream version and license before publishing a new release.

## Bundled logos and brand artwork

The SVG files in `web/public/icons/` and the matching inline paths in
`web/src/components/icons/ProviderLogos.tsx` include artwork identified in the
source comments as follows:

| Files / artwork family | Source and license | Additional restriction |
| --- | --- | --- |
| Gemini, OpenAI, DeepSeek, Ollama, LM Studio, llama.cpp/LlamaIndex, NVIDIA, Tavily and Google provider marks | [Lobe Icons](https://github.com/lobehub/lobe-icons), [MIT license](https://github.com/lobehub/lobe-icons/blob/master/LICENSE) | The underlying names and logos are trademarks of their respective owners. MIT does not grant trademark rights or imply endorsement. |
| Brave and SearXNG marks | [Simple Icons](https://github.com/simple-icons/simple-icons), [project license](https://github.com/simple-icons/simple-icons/blob/develop/LICENSE.md), [trademark disclaimer](https://github.com/simple-icons/simple-icons/blob/develop/DISCLAIMER.md) | Simple Icons states that individual icons can have separate trademark or license restrictions. Check the icon record and brand guidelines before redistributing or changing the marks. |
| `AutoFallbackLogo`, `DeterministicLogo`, and `NativeMetaSearchLogo` | Original Metrixa artwork in `ProviderLogos.tsx` | Covered by this repository's Apache License 2.0 unless a future revision identifies another source. |

Do not present any provider logo as an endorsement, partnership, or official
integration unless the provider has separately granted that permission.

## External services, data sources, and trademarks

The application can call services and publish links to sources at runtime. They
are not bundled software and their terms are separate from this notice. Current
examples include Google Sheets/Google APIs, OpenStreetMap, VDIV, Gelbe Seiten,
11880.com, SearXNG, Tavily, Brave Search, Google Custom Search, DNS resolvers,
LLM providers, LinkedIn and company websites. Review each provider's current
terms, robots/rate limits, API terms, privacy requirements, and trademark rules
before enabling it in a public deployment. Source records and company content
remain owned by their respective publishers.

## Transitive dependencies and release checks

The npm lockfile contains the complete resolved transitive graph. Before making a
redistributable release, regenerate and review a machine-readable license report
from the committed lockfile and the target Python environment, for example:

```text
npm --prefix web ls --all --json
python -m pip inspect
```

The report must be checked for packages added by an indirect dependency, native
libraries pulled by wheels, and any license that requires attribution or source
distribution. Keep the upstream license text and any required notices alongside
the release artifacts. If a dependency changes, update this file and the
manifest/lockfile together.
