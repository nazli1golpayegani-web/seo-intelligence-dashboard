# CODEX BUILD TICKET: SEO Intelligence Dashboard

**Project:** SEO Intelligence Dashboard  
**Category:** SEO Analytics, Business Intelligence & AI-Powered Optimization  
**Priority:** High  
**Deliverable:** Fully functional application with live Google Search Console and GA4 API integrations.

## 1. Mission

You are acting as a Senior Full-Stack Engineer, Technical SEO Specialist, SEO Data Analyst, and AI Application Architect.

Build a professional, production-minded SEO analytics dashboard that connects directly to:

1. Google Search Console API
2. Google Analytics 4 Data API
3. Google Analytics Admin API for property discovery

The application must transform raw SEO and website analytics data into understandable performance insights and actionable SEO recommendations.

This must be a working application, not a design mockup, architecture proposal, or collection of sample components.

**Important: Google Ads integration is NOT required for this project.**

If an existing Google Ads Intelligence Dashboard exists in the repository, inspect it and reuse suitable components, styling, or utilities without breaking existing functionality. Keep SEO analysis and advertising analysis logically separate.

If no application exists, create a standalone SEO Intelligence Dashboard.

Do not ask unnecessary implementation questions. Make reasonable engineering decisions and document them.

---

## 2. Main Product Vision

The dashboard should answer seven business questions:

1. How is my website performing in organic Google Search?
2. Which keywords and landing pages drive meaningful organic traffic?
3. Which SEO rankings offer the greatest realistic growth opportunities?
4. Which pages or keywords are losing visibility?
5. Which organic landing pages generate business outcomes?
6. Which SEO problems deserve immediate attention?
7. What specific actions should I take next?

The product should function like an experienced SEO consultant, not simply a data visualization tool.

All recommendations must be supported by real data.

Never present assumptions, correlations, or hypotheses as proven causes.

---

## 3. Technology and Architecture

Use a Python-first architecture.

Preferred stack:

- Python 3.11+
- Streamlit
- Pandas
- NumPy
- Plotly
- Google API Python Client
- google-auth
- google-auth-oauthlib
- google-analytics-data
- Google Analytics Admin API client
- SQLite for local caching
- Pydantic for structured validation
- Pytest for automated testing
- Optional OpenAI API integration

Use supported, current library versions and official API documentation.

Build modular components and separate:

- Google authentication
- API integrations
- Data retrieval
- Data normalization
- Metric calculations
- SEO analysis logic
- AI recommendations
- Visualizations
- Export and reporting

Do not introduce unnecessary infrastructure such as Kubernetes, microservices, or a complex database deployment.

The initial version should run locally.

---

## 4. Google OAuth Integration

Implement real Google OAuth 2.0 authorization.

The user must be able to connect their own Google account without manually copying API tokens into the application.

Request only these read-only scopes:

Google Search Console:

`https://www.googleapis.com/auth/webmasters.readonly`

Google Analytics:

`https://www.googleapis.com/auth/analytics.readonly`

### Authentication requirements

- Provide a visible "Connect Google Account" action.
- Implement a working OAuth flow suitable for a localhost, single-user application.
- Support refresh tokens.
- Detect expired and revoked credentials.
- Provide clear authentication error messages.
- Store credentials securely and locally.
- Prefer OS-backed secure credential storage where feasible.
- Never log access or refresh tokens.
- Never commit tokens or client secrets to Git.
- Implement disconnect functionality.
- Show connection status separately for GSC and GA4.
- Handle cases where the user has permission for only one source.

The user should not need to interact with a terminal every time they reconnect.

If an OAuth callback service is technically needed, implement the smallest reliable solution.

Do not provide fake connection buttons or hardcoded API responses.

### Google Cloud setup

Document the exact steps required to:

1. Create or select a Google Cloud project.
2. Configure the Google OAuth consent screen.
3. Register the appropriate OAuth client.
4. Enable Search Console API.
5. Enable Google Analytics Data API.
6. Enable Google Analytics Admin API.
7. Configure the application's credentials.
8. Authorize access to real properties.

Provide an `.env.example`, but never include real secrets.

---

## 5. Property Selection

After authentication, discover available properties automatically.

### Search Console

Use the Sites API to list accessible properties.

Support:

- Domain properties
- URL-prefix properties
- Multiple websites

### GA4

Use the Analytics Admin API to discover accessible GA4 properties.

### Mapping

Allow users to associate one Search Console property with the appropriate GA4 property.

Do not automatically assume that two properties with similar names represent the same website.

Allow manual correction and save the mapping.

Support switching between configured websites.

Prevent data from unrelated properties from being accidentally combined.

---

## 6. Data Retrieval Engine

### Google Search Console

Use the Search Analytics API.

Retrieve available data for:

- Date
- Query
- Page
- Country
- Device
- Search type
- Search appearance, where supported

Core metrics:

- Clicks
- Impressions
- CTR
- Average position

Support different reporting grains, including:

- Daily site performance
- Query performance
- Page performance
- Query-page combinations
- Device performance
- Country performance

Implement API pagination using `rowLimit` and `startRow`.

Respect Search Console's API row limits, top-row availability constraints, quotas, and data freshness.

Clearly indicate when retrieved query data may be incomplete.

Never describe a partial API result as the complete set of all search queries.

Use finalized data by default and label recent incomplete data when enabled.

### Google Analytics 4

Use the GA4 Data API.

Retrieve available, compatible combinations of:

Dimensions:

- date
- landingPage
- landingPagePlusQueryString
- sessionDefaultChannelGroup
- sessionSourceMedium
- deviceCategory
- country
- eventName, where appropriate

Metrics:

- sessions
- activeUsers
- newUsers
- engagedSessions
- engagementRate
- keyEvents
- sessionKeyEventRate
- totalRevenue, where available
- screenPageViews, where relevant

Use the GA4 Metadata API and compatibility checking when needed.

Support organic search filtering.

Distinguish all organic search traffic from specifically Google organic traffic.

Support key event analysis when configured.

Do not assume all websites have revenue or key event tracking.

### API reliability

Implement:

- Pagination
- Retry with exponential backoff
- Rate-limit handling
- Quota-aware requests
- Local caching
- Manual refresh
- Last successful synchronization timestamp
- Data freshness warnings
- Partial failure handling
- Error logging without credential exposure

A temporary API failure should not destroy previously cached reports.

---

## 7. SEO Data Model and Cross-Source Integration

Create normalized data models for both platforms.

Maintain the original source and metric definition for every field.

### URL normalization

Support:

- Domain and protocol normalization
- Path extraction
- Trailing slash handling
- Query parameter handling
- Configurable removal of tracking parameters
- Case-sensitive path preservation unless explicitly configured
- URL-prefix and Domain property differences

Avoid merging URLs that might represent different pages.

### Important analytical restrictions

Search Console Clicks and GA4 Sessions are not the same metric.

Do not add them together or imply they should match.

When comparing them, clearly label their definitions and explain discrepancies.

GSC uses different reporting conventions and attribution from GA4.

GA4 data may also differ because of consent configuration, tracking implementation, reporting identity, attribution, and time zones.

Query-level GSC data cannot automatically be linked to GA4 conversion outcomes.

Join page-level data only where URL mapping is reasonably reliable.

If a GSC URL cannot be matched to a GA4 landing page, preserve it as unmatched rather than silently discarding or inventing a match.

Display data-match coverage in the dashboard.

When presenting page-level SEO business performance, clearly distinguish measured page-level GA4 outcomes from search-query performance observed in GSC.

---

## 8. Dashboard Navigation

Create the following pages:

1. SEO Overview
2. Organic Traffic Analytics
3. Keyword Intelligence
4. Landing Page Performance
5. SEO Opportunity Finder
6. Content Decay & Traffic Loss
7. SEO Cannibalization Analysis
8. Technical SEO & Indexing
9. GA4 Business Performance
10. AI SEO Recommendations
11. Executive Reports
12. Connections & Settings

### Global filters

- Website
- Date range
- Previous period comparison
- Device
- Country
- Search type
- Page
- Brand / Non-brand
- Organic acquisition source

Available filters must update all relevant views.

Provide presets:

- Last 7 days
- Last 28 days
- Last 3 months
- Last 6 months
- Last 12 months
- Custom range

Support previous-period and year-over-year comparisons when historical data is available.

---

## 9. SEO Overview Dashboard

Create a professional executive overview.

### Search Console KPI cards

- Total Organic Clicks
- Total Impressions
- Organic CTR
- Average Position
- Click Growth %
- Impression Growth %

### GA4 KPI cards

- Organic Sessions
- Engaged Sessions
- Engagement Rate
- Key Events
- Session Key Event Rate
- Organic Revenue, when available

Maintain clear source labels.

### Core visualizations

- Clicks over time
- Impressions over time
- CTR over time
- Average Position over time
- Organic Sessions over time
- Key Events over time
- Device breakdown
- Country breakdown
- Top-performing pages
- Top-performing keywords

Include an SEO Insights panel that highlights important changes.

### Metric calculation requirements

Calculate aggregate CTR from total clicks divided by total impressions.

Use appropriate impression-weighting when aggregating Search Console positions across compatible rows.

Never simply average percentages or positions without respecting their aggregation semantics.

Display missing metrics as unavailable, not zero.

---

## 10. Keyword Intelligence

Create a dedicated keyword performance module using GSC queries.

Display:

- Search Query
- Clicks
- Impressions
- CTR
- Average Position
- Click Change
- Impression Change
- Position Change
- Number of Associated Pages, where available

### Keyword classifications

**High Performers**

Queries generating meaningful clicks and strong visibility.

**Quick Wins**

Queries ranking relatively well but having a plausible opportunity for improved CTR or ranking.

**Striking Distance**

Queries within a configurable ranking window, such as positions 4–20, with meaningful search impressions.

**Declining Keywords**

Queries showing a statistically or operationally meaningful reduction in performance.

**Rising Keywords**

Queries gaining visibility or clicks.

**High-Impression / Low-CTR Queries**

Queries requiring investigation into title relevance, search intent, SERP presentation, or snippet performance.

### Keyword analysis tools

- Searchable keyword table
- Position distribution
- Click vs impression scatter plot
- Ranking change analysis
- Brand vs non-brand analysis
- Device performance
- Country performance
- Query-to-page relationships
- CSV export

Allow users to configure branded keyword patterns.

Do not automatically classify brand terms solely through simple string matching without showing the configured logic.

### Opportunity scoring

Create a transparent keyword opportunity score using configurable factors:

- Impressions
- Average position
- CTR performance
- Recent trends
- Data quality
- Business relevance, when available

Do not convert impressions into guaranteed traffic forecasts.

---

## 11. Landing Page Intelligence

Combine GSC page performance and GA4 organic landing-page metrics when mappings are reliable.

Display:

- Landing Page URL
- GSC Clicks
- GSC Impressions
- Average Position
- CTR
- GA4 Organic Sessions
- Engagement Rate
- Key Events
- Organic Revenue, where available
- Traffic Change
- Business Performance Status

### Required analysis

Identify:

- High-traffic pages with weak business outcomes
- High-value pages with declining organic visibility
- Pages with many impressions but weak CTR
- Pages with strong engagement but limited search visibility
- Pages experiencing sustained organic traffic declines
- Pages with significant differences between GSC and GA4 measurements

Each finding must explain which data source supports it.

### Business opportunity analysis

Allow users to prioritize pages using:

- Organic traffic potential
- Actual GA4 key event performance
- Available revenue
- Search visibility
- Recent changes
- Confidence in the page matching

Do not claim that a particular query generated a conversion unless the available data genuinely supports that attribution.

---

## 12. SEO Opportunity Finder

This module is one of the product's most important differentiators.

Build a deterministic SEO opportunity detection engine.

### Opportunity types

**CTR Optimization**

Find pages and queries with significant impressions and CTR below comparable internal benchmarks.

Use position-aware benchmarking where enough data is available.

Do not assume that an arbitrary universal CTR curve applies to every website.

**Ranking Improvement**

Identify queries near important ranking thresholds with meaningful visibility.

**Content Expansion**

Identify existing queries related to pages that may indicate unaddressed subtopics.

Label proposed content expansions as hypotheses requiring content review.

**Content Refresh**

Identify pages showing persistent decline across comparable periods.

**Internal Linking Candidates**

Identify related query/page clusters that may benefit from internal linking.

Without crawl data, label these as candidates, not verified internal-link deficiencies.

**Business Value Opportunities**

Prioritize pages showing meaningful organic business performance with room for visibility growth.

### Opportunity output

Every opportunity must contain:

- Opportunity Title
- URL or Query
- Supporting Metrics
- Observation
- Possible Explanation
- Recommended Action
- Priority
- Confidence
- Evidence Limitations

Allow users to sort opportunities by business relevance, priority, and estimated implementation effort.

---

## 13. Content Decay & SEO Traffic Loss

Implement a dedicated SEO decline investigation module.

Compare appropriate date ranges and detect:

- Falling clicks
- Falling impressions
- Declining average positions
- Reduced CTR
- Loss of organic landing-page sessions
- Declines in key event performance
- Sustained vs short-lived changes

### Diagnostic approach

Distinguish among:

- Demand changes
- Ranking changes
- CTR changes
- Device-specific changes
- Geographic changes
- Potential tracking changes
- Seasonal effects
- Possible content deterioration

Do not claim that a Google algorithm update caused a decline without independent evidence.

Do not claim that cannibalization or poor content caused the decline solely from correlation.

### Visualizations

- Before/after performance
- Historical trend
- Device comparison
- Country comparison
- Query movement
- Landing-page movement
- Decline severity ranking

Support configurable minimum data thresholds and periods.

---

## 14. SEO Cannibalization Analysis

Create a query-to-URL relationship analysis.

Find search queries where multiple URLs receive impressions or clicks.

### Required features

- Group URLs by query
- Display impressions and clicks per URL
- Compare average positions
- Compare time periods
- Identify possible URL switching
- Identify potentially competing pages
- Surface pages requiring manual inspection

### Important limitation

Multiple URLs appearing for one query does not automatically prove keyword cannibalization.

The tool must distinguish:

- Query overlap
- Potential ranking competition
- Different search intents
- Possible content differentiation
- Insufficient evidence

Use labels such as "Potential Cannibalization" and "Requires Review."

Do not automatically recommend redirects, canonical changes, or content deletion.

---

## 15. Technical SEO & Indexing

Use the supported Search Console API functionality.

### Sitemap monitoring

Retrieve available submitted sitemap information.

Display:

- Sitemap URL
- Last submission or retrieval information, where available
- Sitemap status
- Available submitted/discovered URL counts
- Available errors or warnings

### URL Inspection

Build a manual URL inspection feature using Google's URL Inspection API.

Display available information about:

- Index coverage status
- Google-selected canonical
- User-declared canonical
- Crawling information
- Indexing-related findings

Respect URL Inspection API quotas.

Make inspection on-demand, not an uncontrolled bulk process.

Clearly state that the API reports Google's indexed version and does not perform a live-site indexability test.

### Scope limitations

Do not pretend that GSC and GA4 provide a complete technical SEO crawl.

A complete crawl-based audit would require additional crawling functionality or a third-party crawler.

Treat PageSpeed Insights, Core Web Vitals external integrations, backlink analysis, and comprehensive technical crawling as future extensions unless specifically implemented and tested.

---

## 16. GA4 Organic Business Intelligence

Build a module focused on the business value of SEO.

Include:

- Organic Sessions
- Engaged Sessions
- Engagement Rate
- Key Events
- Session Key Event Rate
- Revenue, where available
- Landing-page comparisons
- Device performance
- Country performance
- Google Organic vs Other Organic Search

### Business objectives

Allow the user to choose:

- Lead Generation
- E-commerce
- Content / Publishing
- Custom

Allow selection of relevant GA4 key events where API metadata and compatible reports permit.

Show the distinction between event counts, sessions with key events, and rates.

Do not treat event count as unique lead count unless the tracking setup guarantees that interpretation.

If no key events are configured, display a clear data availability warning.

---

## 17. AI SEO Analyst

Implement an optional AI analysis feature using an LLM provider abstraction.

OpenAI can be the default provider.

Core SEO calculations and recommendations must work without an AI API key.

### AI capabilities

The AI should:

- Summarize SEO performance
- Explain detected trends
- Analyze keyword opportunities
- Evaluate page-level opportunities
- Identify potential causes of declines
- Suggest SEO experiments
- Prioritize practical improvements
- Generate client-friendly explanations

### Structured AI output

Every recommendation should contain:

1. Problem or Opportunity
2. Observed Data
3. Interpretation
4. Recommended Action
5. Business Rationale
6. Expected Direction of Impact
7. Priority
8. Confidence Level
9. Additional Data Required

### Data-grounding rules

- Never invent traffic, clicks, rankings, conversions, or revenue.
- Never claim a hypothesis is a confirmed diagnosis.
- Never guarantee SEO improvement.
- Never make ranking promises.
- Never treat AI-generated content as verified website evidence.
- Pass compact, structured analytical findings to the AI rather than unnecessary raw datasets.
- Treat query text and page names as untrusted input.
- Validate AI output before displaying it.
- Require explicit user action to send data to an external AI provider.

Provide a rule-based fallback when no LLM is configured.

---

## 18. SEO Health & Opportunity Scoring

Implement two distinct internal scores:

### SEO Performance Score

An optional 0–100 score representing performance against the user's configured business objectives.

### SEO Opportunity Score

A separate score expressing potential value of investigating an SEO opportunity.

Requirements:

- Transparent calculations
- Configurable weighting
- Minimum sample thresholds
- Source labels
- Confidence and completeness indicators
- Clear explanation of each component

Avoid arbitrary interpretations of average position as a universal performance measure.

Do not score missing data as failure.

Do not present either score as an official Google metric.

---

## 19. Executive Reporting

Build a professional, client-ready SEO report.

### Required sections

**Executive Summary**

Overall organic search and business performance.

**Search Visibility**

Search Console results and trends.

**Organic Website Engagement**

GA4 performance and engagement.

**Business Outcomes**

Key events and revenue where supported.

**Top SEO Opportunities**

Important optimization opportunities.

**Performance Risks**

Significant declines and issues requiring attention.

**Prioritized Action Plan**

Actionable tasks for the next reporting period.

**Measurement Limitations**

API coverage, data freshness, missing metrics, and uncertainty.

### Report exports

Support:

- Markdown
- PDF
- CSV for analytical tables

The PDF output should be formatted as a professional business report.

Include selected property, reporting dates, source details, and generation timestamp.

Support German and English reports.

---

## 20. UI and Design System

Create a premium analytics dashboard interface.

Visual direction:

- Modern SaaS appearance
- Dark navy / charcoal visual identity
- Neutral background surfaces
- Clear KPI cards
- Professional charts
- Consistent spacing
- Responsive layout
- Accessible contrast
- Clean sidebar navigation
- Helpful empty states
- Clear explanations of metrics

Avoid an unstructured Streamlit interface.

The dashboard should feel suitable for presenting SEO performance to clients, management, or marketing teams.

### Key UI components

- Google connection status
- Site selector
- Date selector
- KPI cards
- Trend charts
- Performance tables
- Opportunity cards
- Data quality indicators
- AI analysis panels
- Export actions

Every important chart should support hover details.

Every opportunity must be traceable to its supporting data.

---

## 21. Caching and Performance

Implement local caching with SQLite or an equivalently simple solution.

Cache keys must include relevant inputs such as:

- Property ID
- Date range
- Dimensions
- Metrics
- Filters
- Search type

Do not allow data from different user accounts or properties to mix.

Provide configurable cache expiration and manual refresh.

Handle partial API responses.

Ensure dashboard navigation does not re-fetch all data unnecessarily.

Show retrieval and processing errors clearly.

---

## 22. Demo Mode

Build a complete demo mode using synthetic SEO and GA4 data.

It should demonstrate:

- Growing traffic
- Declining traffic
- Strong-performing queries
- Weak-CTR opportunities
- Ranking opportunities
- Multiple-page query overlap
- Organic conversion performance
- Missing data scenarios

Clearly label all demo data as synthetic.

The dashboard must be usable without connecting a real Google account.

Demo mode must never be confused with live production data.

---

## 23. Testing

Use Pytest.

Test at least:

- OAuth flow integration using mocked Google responses
- Credential refresh handling
- Property listing
- GSC pagination
- GA4 pagination
- API quota and error handling
- Date-range filtering
- CTR calculations
- Position aggregation
- Missing metric handling
- GA4 channel filtering
- URL normalization
- Page matching
- Cross-source metric separation
- Keyword opportunity calculations
- Traffic decline detection
- Potential cannibalization detection
- Technical SEO API parsing
- Report generation
- AI output validation
- Demo mode

Create deterministic test fixtures.

Do not require live credentials for the automated test suite.

---

## 24. Acceptance Criteria

The application is acceptable only when:

- [ ] It launches locally.
- [ ] Google OAuth is implemented and functional.
- [ ] Search Console properties can be listed.
- [ ] GA4 properties can be listed.
- [ ] The user can select and map properties.
- [ ] Live GSC performance data can be retrieved.
- [ ] Live GA4 reporting data can be retrieved.
- [ ] Data retrieval uses caching and pagination.
- [ ] The overview dashboard displays accurate KPIs.
- [ ] Keyword Intelligence works.
- [ ] Landing Page analysis works.
- [ ] SEO Opportunity Finder works.
- [ ] Traffic decline detection works.
- [ ] Potential cannibalization analysis works.
- [ ] Available sitemap data can be retrieved.
- [ ] Manual URL inspection works.
- [ ] SEO business outcomes can be analyzed.
- [ ] Actionable rule-based recommendations work.
- [ ] AI recommendations work when configured.
- [ ] Executive reports can be exported.
- [ ] Demo mode works without Google credentials.
- [ ] Automated tests pass.
- [ ] Setup instructions are complete.

Any acceptance item that cannot be verified in the development environment must be explicitly marked as unverified, not completed.

Do not claim successful live Google API integration unless it was actually tested with authorized credentials.

---

## 25. Suggested Project Structure

```text
seo-intelligence/
├── app.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── src/
│   ├── auth/
│   │   ├── google_oauth.py
│   │   └── token_store.py
│   ├── connectors/
│   │   ├── search_console.py
│   │   ├── ga4_data.py
│   │   ├── ga4_admin.py
│   │   └── url_inspection.py
│   ├── data/
│   │   ├── normalization.py
│   │   ├── url_mapping.py
│   │   ├── storage.py
│   │   └── validation.py
│   ├── analytics/
│   │   ├── seo_metrics.py
│   │   ├── keyword_analysis.py
│   │   ├── page_analysis.py
│   │   ├── opportunities.py
│   │   ├── content_decay.py
│   │   ├── cannibalization.py
│   │   └── business_performance.py
│   ├── ai/
│   │   ├── client.py
│   │   ├── prompts.py
│   │   └── recommendations.py
│   ├── reports/
│   │   ├── builder.py
│   │   └── export.py
│   ├── ui/
│   │   ├── components.py
│   │   ├── charts.py
│   │   └── pages/
│   └── utils/
│       ├── config.py
│       └── formatting.py
├── sample_data/
└── tests/
```

Adapt this structure where necessary to avoid unnecessary complexity.

---

## 26. Implementation Strategy

Work in the following sequence.

### Phase 1 — Foundation

Inspect the repository.

Implement the application skeleton, configuration, Google OAuth, property discovery, and data fetching.

Verify all integration code using mocks.

### Phase 2 — Core Analytics

Implement normalization, caching, SEO metrics, and the Overview, Keyword, and Landing Page dashboards.

### Phase 3 — SEO Intelligence

Implement the Opportunity Finder, Content Decay, Cannibalization, and GA4 Business Intelligence modules.

### Phase 4 — Technical SEO and AI

Implement supported sitemap and URL Inspection functions, optional AI insights, and the report generator.

### Phase 5 — Quality Assurance

Run automated tests.

Fix discovered problems.

Verify demo mode and application startup.

Document any live authentication steps that cannot be executed without the user's credentials.

---

## 27. Mandatory Codex Execution Instructions

**DO NOT STOP AFTER WRITING A PLAN.**

You must implement the application in the current workspace.

Follow these instructions:

1. Inspect the repository before modifying existing files.
2. Preserve unrelated code and features.
3. Write actual working code.
4. Implement the required UI components and analytics engines.
5. Add synthetic demo data.
6. Install dependencies when permitted.
7. Run automated tests.
8. Fix errors discovered during testing.
9. Run an application startup smoke test.
10. Document all configuration requirements.
11. Summarize implemented features and remaining limitations.

Do not generate only pseudocode or static screenshots.

Do not add fake backend integrations.

Do not hardcode analytics results.

Do not claim live integration is verified without testing it.

Do not request production credentials in chat.

Use reasonable defaults, prioritize core functionality, and make incremental improvements.

### Final deliverable

A professional, functional SEO Intelligence Dashboard that connects to Google Search Console and Google Analytics 4, analyzes organic search and website performance, identifies SEO growth opportunities, supports business outcome analysis, and produces evidence-based optimization recommendations.

**Start implementation now.**