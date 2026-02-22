# Browser-Use Task Examples

## Web Scraping

### Extract product listings
```
task = "Go to https://books.toscrape.com and extract the title, price, and rating of the first 10 books. Return as a JSON list."
```

### Monitor a page for changes
```
task = "Go to https://example.com/status, take a screenshot, and extract the current status text."
```

### Aggregate search results
```
task = "Search DuckDuckGo for 'browser-use python library', visit the top 3 results, and summarize what each page says about it."
```

## Form Automation

### Contact form submission
```
task = "Go to https://example.com/contact. Fill in: Name='John Doe', Email='john@example.com', Subject='Inquiry', Message='Hello, I have a question about your services.' Then click Submit and confirm the success message."
```

### Multi-step registration
```
task = "Go to https://example.com/register. Step 1: fill email and password. Step 2: fill profile details (name, company). Step 3: confirm email verification page appears."
```

## Data Research

### Company research
```
task = "Go to https://www.linkedin.com/company/openai and extract: company size, industry, headquarters, and the About section text."
```

### Price comparison
```
task = "Search for 'iPhone 16 Pro price' on Google. Visit the top 3 shopping results and extract the current price from each. Return a comparison table."
```

### News monitoring
```
task = "Go to https://techcrunch.com, find the 5 most recent articles about AI, and return their titles, publication dates, and URLs."
```

## Authentication Flows

### Login and extract
```
task = "Go to https://app.example.com/login. Enter username 'user@example.com' and password 'mypassword'. After login, navigate to /dashboard and extract the account balance shown."
```

### Cookie-based session
```
# Use storage_state to persist cookies between runs
Browser(storage_state="/workspace/cookies.json")
```

## JavaScript-Heavy Sites

### SPA data extraction
```
task = "Go to https://spa-example.com/data. Wait 3 seconds for the page to load, then extract all table rows from the data grid."
```

### Trigger dynamic content
```
task = "Go to https://example.com/infinite-scroll. Scroll down 5 times, waiting 2 seconds between each scroll, then extract all loaded items."
```

## Screenshots & Visual Verification

### Capture page state
```bash
python /app/scripts/browser_use_tool.py \
  --task "Navigate to https://example.com and take a screenshot" \
  --save-screenshot /workspace/screenshots/example.png \
  --max-steps 3
```

### Visual QA check
```
task = "Go to https://my-app.com, log in, navigate to the dashboard, and take a screenshot to verify the layout looks correct."
```

## Structured Output Examples

### Extract with schema
```python
structured_output = json.dumps({
    "type": "object",
    "properties": {
        "company_name": {"type": "string"},
        "employees": {"type": "integer"},
        "revenue": {"type": "string"},
        "founded": {"type": "integer"}
    }
})
```

```bash
python /app/scripts/browser_use_tool.py \
  --task "Go to https://company.com/about and extract company details" \
  --structured-output '{"type":"object","properties":{"name":{"type":"string"},"founded":{"type":"integer"}}}' \
  --output /workspace/company.json
```

## CLI Usage Patterns

### Simple navigation + extract
```bash
python /app/scripts/browser_use_tool.py \
  --task "Go to https://github.com/browser-use/browser-use and get the star count" \
  --max-steps 5
```

### Domain-restricted scraping
```bash
python /app/scripts/browser_use_tool.py \
  --task "Search for Python tutorials and summarize the top 3 results" \
  --allowed-domains "docs.python.org,realpython.com,python.org" \
  --max-steps 20
```

### Save full conversation for debugging
```bash
python /app/scripts/browser_use_tool.py \
  --task "..." \
  --output /workspace/result.json \
  --save-conversation /workspace/conversation.json
```
