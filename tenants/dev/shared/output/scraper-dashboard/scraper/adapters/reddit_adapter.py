"""Reddit adapter for subreddit posts."""
import hashlib
from typing import Dict, Any
from .base import SiteAdapter


class RedditAdapter(SiteAdapter):
    """Adapter for Reddit subreddit posts."""
    
    @property
    def name(self) -> str:
        return "reddit"
    
    async def scrape(self) -> Dict[str, Any]:
        """Fetch top posts from configured subreddits."""
        import aiohttp
        
        subreddits = self.config.get("subreddits", ["technology", "programming"])
        sort = self.config.get("sort", "hot")
        limit = self.config.get("limit", 10)
        
        results = []
        errors = []
        
        async with aiohttp.ClientSession() as session:
            for subreddit in subreddits:
                try:
                    url = f"https://www.reddit.com/r/{subreddit}/{sort}.json"
                    async with session.get(
                        url,
                        headers={"User-Agent": "ScraperBot/1.0"},
                        params={"limit": limit},
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as resp:
                        if resp.status != 200:
                            errors.append(f"Reddit r/{subreddit}: HTTP {resp.status}")
                            continue
                            
                        data = await resp.json()
                        
                        for post in data.get("data", {}).get("children", []):
                            post_data = post.get("data", {})
                            results.append({
                                "title": post_data.get("title", ""),
                                "content": post_data.get("selftext", "")[:500] if post_data.get("is_self") else f"🔗 {post_data.get('url', '')}",
                                "author": post_data.get("author", ""),
                                "url": f"https://reddit.com{post_data.get('permalink', '')}",
                                "subreddit": subreddit,
                                "metadata": {
                                    "score": post_data.get("score", 0),
                                    "comments": post_data.get("num_comments", 0),
                                    "upvote_ratio": post_data.get("upvote_ratio", 0)
                                }
                            })
                except Exception as e:
                    errors.append(f"Reddit r/{subreddit}: {e}")
        
        return {
            "success": len(results) > 0,
            "data": results,
            "errors": errors if errors else None
        }
