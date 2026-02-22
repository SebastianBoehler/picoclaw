# Browser-Use API Reference

## Agent Parameters

```python
Agent(
    task="...",                    # Natural language task (required)
    llm=llm,                       # LLM instance (required)
    browser=browser,               # Browser instance
    max_steps=30,                  # Max browser actions
    use_vision="auto",             # "auto" | True | False
    max_failures=3,                # Retries on step errors
    max_actions_per_step=4,        # Actions per LLM call
    extend_system_message="...",   # Append to system prompt
    save_conversation_path="...",  # Save full conversation
    generate_gif=False,            # Generate GIF of session
    calculate_cost=False,          # Track API costs
)
```

## Browser Parameters

```python
Browser(
    headless=True,                 # No UI (default in Docker)
    cdp_url="http://...:9222",     # Connect to existing browser
    allowed_domains=["*.site.com"],# Domain whitelist
    prohibited_domains=["..."],    # Domain blacklist
    keep_alive=False,              # Keep browser after agent done
    window_size={"width": 1280, "height": 720},
    proxy=ProxySettings(server="http://host:8080"),
    storage_state="cookies.json",  # Load saved cookies/localStorage
    args=["--no-sandbox", "--disable-dev-shm-usage"],  # Required in Docker
)
```

## AgentHistoryList (return value of agent.run())

```python
history = await agent.run()

history.final_result()            # Final extracted content (string)
history.is_done()                 # True if completed successfully
history.is_successful()           # True if no errors
history.has_errors()              # True if any errors occurred
history.urls()                    # List of visited URLs
history.extracted_content()       # All extracted content
history.errors()                  # List of errors (None for clean steps)
history.number_of_steps()         # Total steps taken
history.total_duration_seconds()  # Total run time
history.screenshots()             # Base64 screenshots
history.screenshot_paths()        # Screenshot file paths
history.action_names()            # Names of executed actions
```

## Built-in Browser Actions

### Navigation
- `navigate(url)` — go to URL
- `go_back()` — browser back
- `search(query)` — DuckDuckGo/Google search
- `wait(seconds)` — pause

### Page Interaction
- `click(index)` — click element by index
- `input(index, text)` — type into field
- `scroll(direction, amount)` — scroll page
- `send_keys(keys)` — keyboard shortcuts (Enter, Escape, Tab)
- `find_text(text)` — scroll to text on page
- `upload_file(index, path)` — file upload

### Extraction
- `extract(goal)` — LLM-powered data extraction
- `screenshot()` — capture current state

### Forms
- `dropdown_options(index)` — list dropdown values
- `select_dropdown(index, value)` — select option

### JavaScript
- `evaluate(code)` — run JS on page (shadow DOM, custom selectors)

### Tabs
- `switch(tab_id)` — switch tab
- `close(tab_id)` — close tab

### Files
- `write_file(path, content)` — write file
- `read_file(path)` — read file

### Completion
- `done(text)` — complete task with final result

## Structured Output

```python
from pydantic import BaseModel

class ProductList(BaseModel):
    products: list[dict]
    total_count: int

agent = Agent(
    task="Extract all products",
    llm=llm,
    output_model_schema=ProductList,
)
history = await agent.run()
result = history.structured_output  # ProductList instance
```

## LLM Setup (OpenRouter)

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="x-ai/grok-4-fast",
    openai_api_key=os.environ["OPENROUTER_API_KEY"],
    openai_api_base="https://openrouter.ai/api/v1",
)
```

## Docker / Headless Notes

In Docker containers, always pass these browser args:
```python
Browser(
    headless=True,
    args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
)
```

Chromium must be installed: `playwright install chromium`
