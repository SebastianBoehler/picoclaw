"""
Base scraper engine with configurable adapters, rate limiting, and retry logic.
"""
import asyncio
import json
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional
import aiohttp
from aiohttp import ClientTimeout


@dataclass
class ScrapingConfig:
    """Configuration for a scraping job."""
    name: str
    base_url: str
    rate_limit_delay: tuple[float, float] = (1.0, 3.0)  # min, max seconds
    max_retries: int = 3
    retry_delay: float = 2.0
    timeout: int = 30
    headers: dict = field(default_factory=lambda: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0"
    })


@dataclass
class ScrapedItem:
    """A single scraped data item."""
    source: str
    url: str
    data: dict[str, Any]
    scraped_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseScraper(ABC):
    """Abstract base class for site-specific scrapers."""
    
    def __init__(self, config: ScrapingConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self._last_request_time: float = 0
        
    async def __aenter__(self):
        timeout = ClientTimeout(total=self.config.timeout)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers=self.config.headers
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _rate_limit(self):
        """Apply rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        min_delay, max_delay = self.config.rate_limit_delay
        target_delay = random.uniform(min_delay, max_delay)
        
        if elapsed < target_delay:
            await asyncio.sleep(target_delay - elapsed)
        
        self._last_request_time = time.time()
    
    async def _fetch(self, url: str, **kwargs) -> Optional[str]:
        """Fetch URL with retry logic."""
        for attempt in range(self.config.max_retries + 1):
            try:
                await self._rate_limit()
                
                async with self.session.get(url, **kwargs) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status in (429, 503, 502):
                        # Rate limited or service unavailable - retry
                        wait_time = self.config.retry_delay * (2 ** attempt)
                        await asyncio.sleep(wait_time)
                    else:
                        return None
                        
            except Exception as e:
                if attempt == self.config.max_retries:
                    return None
                await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
        
        return None
    
    @abstractmethod
    async def scrape(self) -> list[ScrapedItem]:
        """Main scraping method - must be implemented by subclasses."""
        pass


class StorageBackend(ABC):
    """Abstract storage backend for scraped data."""
    
    @abstractmethod
    async def save(self, items: list[ScrapedItem]) -> bool:
        pass
    
    @abstractmethod
    async def load(self, source: Optional[str] = None) -> list[ScrapedItem]:
        pass


class JSONStorage(StorageBackend):
    """JSON file storage backend."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    async def save(self, items: list[ScrapedItem]) -> bool:
        try:
            # Group by source
            by_source: dict[str, list] = {}
            for item in items:
                if item.source not in by_source:
                    by_source[item.source] = []
                by_source[item.source].append({
                    "url": item.url,
                    "data": item.data,
                    "scraped_at": item.scraped_at.isoformat(),
                    "metadata": item.metadata
                })
            
            # Save each source to its own file
            for source, data in by_source.items():
                filepath = self.data_dir / f"{source}.json"
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"Storage error: {e}")
            return False
    
    async def load(self, source: Optional[str] = None) -> list[ScrapedItem]:
        items = []
        try:
            if source:
                filepath = self.data_dir / f"{source}.json"
                if filepath.exists():
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for entry in data:
                            items.append(ScrapedItem(
                                source=source,
                                url=entry["url"],
                                data=entry["data"],
                                scraped_at=datetime.fromisoformat(entry["scraped_at"]),
                                metadata=entry.get("metadata", {})
                            ))
            else:
                # Load all sources
                for filepath in self.data_dir.glob("*.json"):
                    src = filepath.stem
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for entry in data:
                            items.append(ScrapedItem(
                                source=src,
                                url=entry["url"],
                                data=entry["data"],
                                scraped_at=datetime.fromisoformat(entry["scraped_at"]),
                                metadata=entry.get("metadata", {})
                            ))
        except Exception as e:
            print(f"Load error: {e}")
        
        return items


class ScraperEngine:
    """Main scraper engine that manages multiple scrapers."""
    
    def __init__(self, storage: Optional[StorageBackend] = None):
        self.scrapers: dict[str, type[BaseScraper]] = {}
        self.storage = storage or JSONStorage()
    
    def register(self, name: str, scraper_class: type[BaseScraper]):
        """Register a scraper class."""
        self.scrapers[name] = scraper_class
    
    async def run(self, scraper_name: str, config: ScrapingConfig) -> list[ScrapedItem]:
        """Run a specific scraper."""
        if scraper_name not in self.scrapers:
            raise ValueError(f"Unknown scraper: {scraper_name}")
        
        scraper_class = self.scrapers[scraper_name]
        
        async with scraper_class(config) as scraper:
            items = await scraper.scrape()
            await self.storage.save(items)
            return items
    
    async def run_all(self, configs: dict[str, ScrapingConfig]) -> dict[str, list[ScrapedItem]]:
        """Run all registered scrapers with their configs."""
        results = {}
        for name, config in configs.items():
            if name in self.scrapers:
                results[name] = await self.run(name, config)
        return results
