"""CoinGecko adapter for crypto price data."""
import hashlib
from typing import Dict, Any
from .base import SiteAdapter


class CoinGeckoAdapter(SiteAdapter):
    """Adapter for CoinGecko API."""
    
    @property
    def name(self) -> str:
        return "coingecko"
    
    async def scrape(self) -> Dict[str, Any]:
        """Fetch top crypto prices."""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": 10,
                    "page": 1,
                    "sparkline": "false"
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                data = await resp.json()
                
                results = []
                for coin in data:
                    results.append({
                        "title": coin.get("name", ""),
                        "content": f"${coin.get('current_price', 0):,.2f}",
                        "author": coin.get("symbol", "").upper(),
                        "url": f"https://coingecko.com/en/coins/{coin.get('id', '')}",
                        "metadata": {
                            "change_24h": coin.get("price_change_percentage_24h", 0),
                            "market_cap": coin.get("market_cap", 0),
                            "volume_24h": coin.get("total_volume", 0)
                        }
                    })
                
                return {
                    "success": True,
                    "data": results,
                    "raw_response": data
                }
