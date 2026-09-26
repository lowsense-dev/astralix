"""Fetch untrusted web documents without reaching private networks."""

import ipaddress
from urllib.parse import urljoin, urlsplit

import aiohttp

from ._security import MAX_WEB_DOCUMENT_SIZE


def validate_url(url):
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Web documents require an HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Credentials in web document URLs are not allowed")
    if "%" in parsed.hostname:
        raise ValueError("Scoped IP addresses are not allowed")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return
    if not address.is_global:
        raise ValueError("Web documents cannot access private or reserved addresses")


class PublicResolver(aiohttp.resolver.DefaultResolver):
    async def resolve(self, host, port=0, family=0):
        results = await super().resolve(host, port, family)
        if not results or any(
            not ipaddress.ip_address(result["host"]).is_global for result in results
        ):
            raise ValueError("Web document DNS resolved to a non-public address")
        return results


async def download(url, stream):
    resolver = PublicResolver()
    connector = aiohttp.TCPConnector(resolver=resolver, use_dns_cache=False)
    try:
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=120, connect=15),
        ) as session:
            for _ in range(6):
                validate_url(url)
                async with session.get(url, allow_redirects=False) as response:
                    if response.status in (301, 302, 303, 307, 308):
                        location = response.headers.get("Location")
                        if not location:
                            raise ValueError("Web document redirect has no location")
                        url = urljoin(url, location)
                        continue
                    response.raise_for_status()
                    if (response.content_length or 0) > MAX_WEB_DOCUMENT_SIZE:
                        raise ValueError("Web document exceeds size limit")
                    size = 0
                    async for chunk in response.content.iter_chunked(128 * 1024):
                        size += len(chunk)
                        if size > MAX_WEB_DOCUMENT_SIZE:
                            raise ValueError("Web document exceeds size limit")
                        stream.write(chunk)
                    return
            raise ValueError("Too many web document redirects")
    finally:
        await resolver.close()
