---
name: rss-client
description: Fetch and parse any RSS or Atom feed from a URL. Use when asked to monitor news sources, auction feeds, job boards, blogs, press releases, or any other RSS/Atom feed. Can discover feed URLs from websites and filter/summarize feed content.
---

# RSS Client

Fetch any RSS or Atom feed using `http_fetch GET <url>`. The response is XML — parse it to extract items.

## Reading a Feed

```
http_fetch GET <feed-url>
```

Parse the XML response. Both RSS 2.0 and Atom formats are common:

| Data       | RSS 2.0            | Atom                         |
| ---------- | ------------------ | ---------------------------- |
| Feed title | `<channel><title>` | `<feed><title>`              |
| Item list  | `<item>`           | `<entry>`                    |
| Item title | `<title>`          | `<title>`                    |
| Item link  | `<link>`           | `<link href="...">`          |
| Summary    | `<description>`    | `<summary>` or `<content>`   |
| Date       | `<pubDate>`        | `<updated>` or `<published>` |
| Category   | `<category>`       | `<category term="...">`      |
| Author     | `<author>`         | `<author><name>`             |

## Discovering Feed URLs

If you only have a website URL (not a direct feed URL), try these common paths:

- `<site>/feed`
- `<site>/rss`
- `<site>/feed.xml`
- `<site>/atom.xml`
- `<site>/rss.xml`
- `<site>/index.xml`

Or fetch the homepage and look for `<link rel="alternate" type="application/rss+xml" href="...">` in the HTML `<head>`.

## Example Feed URLs

### Industrial Auctions

- **Rockmann Industrieauktionen** (machinery, equipment): `https://auktionen.rockmann-industrieauktionen.de/de/Services/AuctionsRss`

### News & Press

- **Hacker News** (tech): `https://news.ycombinator.com/rss`
- **TechCrunch**: `https://techcrunch.com/feed/`
- **Heise Online** (German tech): `https://www.heise.de/rss/heise-atom.xml`
- **Spiegel Online** (German news): `https://www.spiegel.de/schlagzeilen/index.rss`
- **Reuters** (top news): `https://feeds.reuters.com/reuters/topNews`

### Business & Finance

- **Bundesanzeiger** (German official notices): check site for feed URL
- **PR Newswire**: `https://www.prnewswire.com/rss/news-releases-list.rss`

### Jobs

- **LinkedIn Jobs** (search-specific): `https://www.linkedin.com/jobs/search/?keywords=<term>&location=<loc>&format=rss`
- **Indeed**: `https://www.indeed.com/rss?q=<term>&l=<location>`

## Workflows

### Monitor a feed for new items

1. `http_fetch GET <feed-url>` → parse XML
2. Extract all `<item>` / `<entry>` elements with title, link, date, description
3. Filter by keyword or date if needed
4. Save to `workspace/research/MM_DD_YYYY/<feed-name>.md`

### Find and read a site's feed

1. `http_fetch GET <website-homepage>` → scan HTML for `<link rel="alternate" type="application/rss+xml">`
2. If not found, try `<site>/feed`, `<site>/rss`, `<site>/feed.xml`
3. Once feed URL found, fetch and parse as above

### Research a specific item

1. Fetch feed → find matching item by keyword in title/description
2. Extract `<link>` → `http_fetch GET <item-link>` for full article/page
3. Summarize findings

### Cross-reference with lead research

Industrial auction feeds (e.g. Rockmann) signal company liquidations or asset sales — a company selling off machinery may be restructuring or in financial distress. Cross-reference with `/handelsregister/search` and `/northdata/kpis` to qualify as a lead.

## Notes

- Always respect `<ttl>` (time-to-live) in RSS if present — it indicates how often the feed updates
- Dates in RSS are RFC 822 format (`Wed, 19 Feb 2026 10:00:00 +0100`); Atom uses ISO 8601
- If a feed requires authentication, check if a public URL variant exists first
