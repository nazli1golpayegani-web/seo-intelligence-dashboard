# SEO Intelligence

A local, single-user Python/Streamlit dashboard for Search Console and GA4. Twelve views cover search performance, organic acquisition, keyword opportunities, page outcomes, decline, overlap, technical API tools, optional AI and executive exports. **No Google Ads integration.**

## Start in demo mode

Python 3.11+ is required (tested on Python 3.12).

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-tested.txt
python -m streamlit run app.py
```

Open http://127.0.0.1:8501 on the same machine. Synthetic demo mode is on by default; no credentials are required. `requirements.txt` contains supported version ranges; `requirements-tested.txt` records the direct dependency versions used for validation, not a full transitive lock.

## Connect your real Google account

Do not send credentials in chat. Configure them on your own machine:

1. Visit https://console.cloud.google.com/ and create/select a project.
2. In **APIs & Services → Library**, enable **Google Search Console API**, **Google Analytics Data API**, and **Google Analytics Admin API** in that project.
3. Open **Google Auth Platform** (or OAuth consent screen), set your app name, support email and developer contact. Choose Internal only for an eligible Workspace organization; otherwise External.
4. For External testing, add your own Google email under Audience / Test users. Testing grants may expire and require reconnection; publishing an external app can require Google's verification.
5. Configure these two read-only data-access scopes:
   - `https://www.googleapis.com/auth/webmasters.readonly`
   - `https://www.googleapis.com/auth/analytics.readonly`
6. Under Clients / Create client, choose **Desktop app**. Download its JSON as `client_secret.json` beside `app.py`. The file must contain an `installed` client. Do not choose a Web application client. Desktop clients support the ephemeral loopback callback; no fixed redirect URI needs adding.
7. Copy `.env.example` to `.env`. Set `GOOGLE_CLIENT_SECRETS` if your JSON is elsewhere.
8. Credential storage prefers macOS Keychain, Windows Credential Locker, or a supported Linux Secret Service/KWallet keyring. If no supported secure backend exists, configure one. An explicit `ALLOW_FILE_TOKENS=true` permits a local permission-restricted plaintext file (`0600` inside `0700` directory). On Windows, additionally restrict the folder's ACL to your user. Tokens are never bundled in this project.
9. Run the application locally, turn demo mode off, choose **Connect Google Account**, then open **Continue to Google authorization**. Authorize on the **same computer** running the application. Select **Check connection** after returning. There is no manual token copying and no terminal action on reconnect.
10. Choose **Discover / refresh properties**. The account needs access to the actual GSC/GA4 properties; enabling APIs alone does not grant access. Domain properties and URL-prefix properties are supported. GA4 discovery uses account summaries from the Admin API.
11. Save a named mapping: select a GSC property, GA4 property, and canonical origin (e.g. `https://www.example.com`). Confirm they measure the same site. Either source may be absent; other-source views then show unavailable data. Never map unrelated websites.
12. Select your saved website in the sidebar. Configure brand expressions, URL normalization, business objective, minimum impressions and opportunity weights in Settings.

The server binds to `127.0.0.1`. This is **not** a hosted multi-user service. For remote hosting, replace desktop OAuth and local singleton storage with an appropriate per-user web authorization design. Do not expose this server on a public interface.

Disconnect deletes local credentials. To revoke the grant at Google as well, use https://myaccount.google.com/permissions. Caches remain under their old random connection identifier and are never reused by a new account connection. Delete `.data/` while the app is stopped to remove all cached analytics and settings.

## What is implemented

- Real Google REST requests via `google-auth` AuthorizedSession, OAuth PKCE and validated callback state, refresh and disconnect; no fake backend.
- GSC Sites, Search Analytics, search-appearance breakdown, Sitemaps, and on-demand URL Inspection.
- GA4 Admin discovery/key events, Metadata, compatibility checks, organic-filtered Data API reports and pagination.
- Retry/backoff for transient and quota errors, independent source failures, SQLite TTL caching and stale-cache fallback with timestamps. Cache keys include connection, property, dates, dimensions, metrics and filters.
- GSC totals fetched at their own grain; CTR = total clicks / total impressions; compatible-row positions are impression weighted. GA4 headline rates and user counts come from dedicated reports, not averaging grouped percentages or summing users.
- Twelve navigable views, six date presets/custom selection, previous-period and year-over-year comparison, device, country, search type, page, explicit brand pattern and organic-source controls. Country picker currently offers five named countries plus All.
- Keyword classifications, position distribution, query/page relationships, configurable transparent opportunity scoring and internal position-bucket CTR benchmarks (minimum five peers).
- Conservative hostname-aware page matching with unmatched/ambiguous retention and row-match coverage. Query parameter order, path case and trailing slashes are preserved by default except configured tracking parameters. No many-to-many metric inflation.
- Two-period decline; optional third-period persistence check; device/country and GA4 page comparisons. Query overlap and changed dominant URLs between periods are review signals.
- Page-level business opportunities plus query groups for manual content/internal-link review. These do not assert actual content gaps or missing links.
- Rule recommendations work without AI. Optional OpenAI call requires a visible consent checkbox and explicit action. Compact payload preview, structured validation, evidence-ID checks and canonical observed metrics are implemented.
- English/German Markdown/PDF reports, CSV tables, bundled Unicode fonts; synthetic demo contains growth, decline, low CTR, overlap, outcomes, unavailable revenue and unmatched pages.

## Measurement and scope

GSC clicks and GA4 sessions measure different things; never sum them. GA4 outcomes are **page-level**, not attributed to GSC queries. All-organic GA4 includes search engines beyond Google unless Google organic is selected. Brand and GSC search-type filters cannot filter GA4 equivalently and are visibly disclosed.

GSC reports are top-row observations and may omit privacy-protected/anonymized queries. Pagination cannot recover everything Google omits. Missing rows do not establish zero traffic. Finalized data is default; the default end date is three days ago. Older comparisons can exceed GSC retention. GA4 metadata exposes timezone/currency, thresholding and sampling information when returned. Inspect Data quality notes. Event count is not unique leads; session key-event rate comes from the API.

Hostnames are required for cross-source joins. Protocol is inferred from the confirmed canonical origin because GA4 hostname does not include it. Set protocol equivalence only after checking your site. Normalization collisions remain ambiguous. Match coverage is a percentage of retrieved GSC page rows, not all website URLs.

Opportunity scores are internal investigation priorities, not Google scores or traffic forecasts. Current score components are impression scale, internal CTR gap and configurable ranking window; trend/business/context are separate tables, not undocumented score bonuses. Missing CTR peers give no CTR bonus. Optional business-goal performance scoring is intentionally not offered without explicit targets. Business objective is a planning label, not an automatic conversion interpretation.

Search-appearance and technical APIs can legitimately return no data. URL Inspection describes the indexed version and is manually triggered; it is not a live fetch. No crawler, backlinks, PageSpeed or external Core Web Vitals integration is included. Content expansion/internal linking use query groups and require manual content review. Dominant-URL changes between periods are not proof of daily URL alternation. No causal algorithm-update diagnosis or automated destructive SEO changes.

The AI output schema and evidence IDs are validated; model interpretation is still unverified and may be wrong. Review qualitative claims before using them. Only OpenAI is implemented behind a replaceable provider class. The default model is configurable with `OPENAI_MODEL`; set `OPENAI_API_KEY` in `.env` only if using AI.

## Test and verification

```bash
python -m pytest -q
```

31 tests passed in the build environment. Coverage includes every demo view with Streamlit AppTest, OAuth loopback callback/state with mocked Google, refresh/revocation handling, properties, GSC/GA4 pagination, quotas, failed-report caching, isolation, date/channel filters, weighted metrics, URL matching, opportunities, decline, overlap/switching, technical responses, AI validation, and report exports. A local server returned `200 ok` from `/_stcore/health`. German PDF pages were rendered and visually inspected.

See `ACCEPTANCE.md` for implemented vs independently verified vs unverified acceptance items. **Live Google authorization, live reports, OS-keychain integration on your computer, and live OpenAI calls have not been verified with real credentials.** Browser pixel-level UI review could not run because the Chromium download was unavailable; AppTest validated the page execution paths.

## Modules

- `app.py`: dashboard, settings, filters, exports.
- `src/auth.py`: desktop OAuth and credential storage.
- `src/connectors.py`: real Google REST adapters and reliability.
- `src/storage.py`: account-isolated SQLite cache and settings.
- `src/analytics.py`: normalization, metrics and deterministic investigation engines.
- `src/demo.py`: reproducible synthetic data.
- `src/ai.py`: optional structured AI provider.
- `src/reports.py`: bilingual Markdown and PDF export.

Architecture uses direct official REST endpoints instead of extra generated Google SDK dependencies, minimizing installation surface while retaining `google-auth` for authorization.

## Official references checked during implementation

- Desktop OAuth: https://developers.google.com/identity/protocols/oauth2/native-app
- GSC Search Analytics: https://developers.google.com/webmaster-tools/v1/searchanalytics/query
- GA4 reporting and pagination: https://developers.google.com/analytics/devguides/reporting/data/v1/basics
- GA4 Metadata/compatibility: https://developers.google.com/analytics/devguides/reporting/data/v1
- GSC URL Inspection: https://developers.google.com/webmaster-tools/v1/urlInspection.index/inspect
- GA4 Admin account summaries: https://developers.google.com/analytics/devguides/config/admin/v1/rest/v1beta/accountSummaries/list
