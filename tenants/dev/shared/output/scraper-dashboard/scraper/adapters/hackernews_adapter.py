"""Hacker News adapter for top posts."""
import hashlib
from typing import Dict, Any
from .base import SiteAdapter


class HackerNewsAdapter(SiteAdapter):
    """Adapter for Hacker News top stories."""
    
    @property
    def name(self) -> str:
        return "hackernews"
    
    async def scrape(self) -> Dict[str, Any]:
        """Fetch top HN stories."""
        import aiohttp
        
        limit = self.config.get("limit", 30)
        
        async with aiohttp.ClientSession() as session:
            # Get top story IDs
            async with session.get(
                "https://hacker-news.firebaseio.com/v0/topstories.json",
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                story_ids = await resp.json()
                story_ids = story_ids[:limit]
            
            # Fetch each story
            results = []
            for story_id in story_ids:
                try:
                    async with session.get(
                        f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as resp:
                        story = await resp.json()
                        if story:
                            results.append({
                                "title": story.get("title", ""),
                                "content": f"🔗 {story.get('url', '')}" if story.get('url') else "💬 Discussion",
                                "author": story.get("by", ""),
                                "url": f"https://news.ycombinator.com/item?id={story_id}",
                                "metadata": {
                                    "score": story.get("score", 0),
                                    "comments": story.get("descendants", 0),
                                    "type": story.get("type", "")
                                }
                            })
                except Exception as e:
                    continue
        
        return {
            "success": len(results) > 0,
            "data": results
        }
