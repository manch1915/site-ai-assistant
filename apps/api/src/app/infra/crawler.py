import ipaddress
import socket
from collections.abc import AsyncIterator, Iterable
from typing import Any
from urllib.parse import urljoin, urlparse
from xml.etree.ElementTree import ParseError

import anyio
import httpcore
import httpx
from defusedxml import ElementTree

from app.infra.parsers import RawDocument, parse_html

_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
_USER_AGENT = "RelayIndexer/1.0 (+knowledge base crawler)"


class CrawlError(Exception):
    pass


def is_public_address(raw: str) -> bool:
    address = ipaddress.ip_address(raw)
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address.is_global and not address.is_multicast and not address.is_unspecified


class _PublicOnlyBackend(httpcore.AsyncNetworkBackend):
    """Resolves the host itself and connects to the checked IP.

    Checking the name before the request isn't enough: DNS can answer differently a moment
    later (rebinding). TLS still uses the original hostname for SNI and certificates.
    """

    def __init__(self) -> None:
        self._inner = httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,  # noqa: ASYNC109 (httpcore interface)
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        try:
            infos = await anyio.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise httpcore.ConnectError(f"Cannot resolve {host}") from exc
        addresses = [str(info[4][0]) for info in infos]
        if not addresses or not all(is_public_address(a) for a in addresses):
            raise httpcore.ConnectError(f"Refusing to fetch a private address: {host}")
        return await self._inner.connect_tcp(
            addresses[0], port, timeout, local_address, socket_options
        )

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


def _guarded_transport() -> httpx.AsyncHTTPTransport:
    transport = httpx.AsyncHTTPTransport()
    # httpx has no public hook for the network backend, so swap the pool it built.
    transport._pool = httpcore.AsyncConnectionPool(
        network_backend=_PublicOnlyBackend(), http1=True, http2=False
    )
    return transport


class Crawler:
    def __init__(self, *, max_pages: int, allow_private: bool = False, timeout: float = 15) -> None:
        self.max_pages = max_pages
        self.allow_private = allow_private
        self.timeout = timeout

    async def _on_request(self, request: httpx.Request) -> None:
        # Runs for redirects too.
        if request.url.scheme not in {"http", "https"} or not request.url.host:
            raise CrawlError(f"Not an http(s) URL: {request.url}")

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

        # Real sitemaps use absolute URLs, but relative ones are easy to support.
        locs = [urljoin(url, el.text.strip()) for el in root.iter(f"{_NS}loc") if el.text]
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
            transport=None if self.allow_private else _guarded_transport(),
        )
