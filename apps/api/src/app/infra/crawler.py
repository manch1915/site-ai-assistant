import asyncio
import ipaddress
import socket
from collections.abc import AsyncIterator
from urllib.parse import urljoin, urlparse
from xml.etree.ElementTree import ParseError

import httpx
from defusedxml import ElementTree

from app.infra.parsers import RawDocument, parse_html

_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
_USER_AGENT = "RelayIndexer/1.0 (+knowledge base crawler)"


class CrawlError(Exception):
    pass


def _is_public_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
        ):
            return False
    return True


class Crawler:
    def __init__(self, *, max_pages: int, allow_private: bool = False, timeout: float = 15) -> None:
        self.max_pages = max_pages
        self.allow_private = allow_private
        self.timeout = timeout

    async def _check_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise CrawlError(f"Not an http(s) URL: {url}")
        if not self.allow_private:
            public = await asyncio.to_thread(_is_public_host, parsed.hostname)
            if not public:
                raise CrawlError(f"Refusing to fetch a private address: {parsed.hostname}")

    async def _on_request(self, request: httpx.Request) -> None:
        # Runs for redirects too, so a public page can't bounce us into the internal network.
        await self._check_url(str(request.url))

    async def _get(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        response = await client.get(url)
        response.raise_for_status()
        return response

    async def sitemap_urls(self, client: httpx.AsyncClient, url: str, depth: int = 0) -> list[str]:
        response = await self._get(client, url)
        try:
            root = ElementTree.fromstring(response.content)
        except ParseError as exc:
            raise CrawlError(f"{url} is not a valid sitemap") from exc

        locs = [el.text.strip() for el in root.iter(f"{_NS}loc") if el.text]
        if root.tag == f"{_NS}sitemapindex" and depth < 2:
            nested: list[str] = []
            for child in locs:
                nested.extend(await self.sitemap_urls(client, child, depth + 1))
                if len(nested) >= self.max_pages:
                    break
            locs = nested

        host = urlparse(url).hostname
        same_host = [loc for loc in locs if urlparse(loc).hostname == host]
        return list(dict.fromkeys(same_host))[: self.max_pages]

    async def crawl_sitemap(self, sitemap_url: str) -> AsyncIterator[RawDocument]:
        async with self._client() as client:
            if not sitemap_url.endswith(".xml"):
                sitemap_url = urljoin(sitemap_url.rstrip("/") + "/", "sitemap.xml")
            for page_url in await self.sitemap_urls(client, sitemap_url):
                document = await self._fetch_page(client, page_url)
                if document is not None:
                    yield document

    async def fetch_page(self, url: str) -> RawDocument:
        async with self._client() as client:
            document = await self._fetch_page(client, url, strict=True)
        if document is None:
            raise CrawlError(f"No readable text on {url}")
        return document

    async def _fetch_page(
        self, client: httpx.AsyncClient, url: str, *, strict: bool = False
    ) -> RawDocument | None:
        try:
            response = await self._get(client, url)
        except (httpx.HTTPError, CrawlError):
            # One broken page shouldn't stop a sitemap crawl, but a single URL should say why.
            if strict:
                raise
            return None
        if "html" not in response.headers.get("content-type", "html"):
            return None
        document = parse_html(response.text, url=str(response.url))
        return document if document.text.strip() else None

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
            max_redirects=5,
            event_hooks={"request": [self._on_request]},
        )
