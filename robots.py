import aiohttp
from urllib.robotparser import RobotFileParser
from urllib.parse import urljoin
from typing import Optional

class RobotsCache:
    """Cache robots.txt parsers per domain to avoid re-fetching"""

    def __init__(self):
        self._cache: dict[str, Optional[RobotFileParser]] = {}

    async def get_parser(self, base_url: str, session: aiohttp.ClientSession) -> Optional[RobotFileParser]:
        from urllib.parse import urlparse
        domain = urlparse(base_url).netloc

        if domain in self._cache:
            return self._cache[domain]

        robots_url = urljoin(base_url, "/robots.txt")
        try:
            async with session.get(robots_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    content = await response.text()
                    parser = RobotFileParser()
                    parser.parse(content.splitlines())
                    self._cache[domain] = parser
                    return parser
        except Exception:
            pass

        self._cache[domain] = None
        return None

    def is_allowed(self, parser: Optional[RobotFileParser], url: str) -> bool:
        if parser is None:
            return True  # no robots.txt = allowed
        return parser.can_fetch("*", url)