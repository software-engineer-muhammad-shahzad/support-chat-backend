"""External web content for the agent's fetch_webpage tool — reads a
public URL's page text so the assistant can answer questions grounded in
content outside the user's own uploaded documents.
"""

import ipaddress
import logging
import socket
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2MB — a page's HTML, not its images/video
MAX_TEXT_CHARS = 8000  # keeps the tool result small enough for the model's context


class FetchError(Exception):
    """The URL couldn't be fetched or isn't allowed. Always caught at the
    tool boundary (tools.py) and turned into a message handed back to the
    model as the tool's result, never raised past it."""


def _guard_against_ssrf(hostname: str) -> None:
    """Refuses to fetch a hostname that resolves to a private, loopback,
    link-local, or otherwise non-public address. Without this, a URL
    supplied through a user's prompt could make this server fetch its own
    internal network on the model's behalf — a cloud metadata endpoint, an
    internal admin panel, another container on the same host — using this
    tool as an SSRF proxy. "Read a public webpage" never needs an internal
    address, so every one of them is refused outright.
    """
    try:
        addresses = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise FetchError(f"Could not resolve host: {hostname}") from exc

    for family, _type, _proto, _canonname, sockaddr in addresses:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise FetchError(f"Refusing to fetch a non-public address: {hostname}")


def fetch_webpage_text(url: str) -> str:
    """Fetches `url` and returns its visible text, stripped of HTML markup
    (script/style included) and truncated to a size sensible for an LLM
    prompt. Streams the response with a hard byte cap rather than trusting
    Content-Length, so a malicious or misbehaving server can't force an
    unbounded download by lying about (or omitting) its size.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise FetchError("Only http:// and https:// URLs are supported.")
    if not parsed.hostname:
        raise FetchError("That doesn't look like a valid URL.")

    _guard_against_ssrf(parsed.hostname)

    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={"User-Agent": "Mozilla/5.0 (compatible; SupportChatAssistant/1.0)"},
        stream=True,
    )
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type and "text/plain" not in content_type:
        raise FetchError(f"Unsupported content type: {content_type or 'unknown'}")

    chunks = []
    total = 0
    for chunk in response.iter_content(chunk_size=8192):
        total += len(chunk)
        if total > MAX_RESPONSE_BYTES:
            logger.info("Truncating oversized response from %s", url)
            break
        chunks.append(chunk)
    raw = b"".join(chunks)

    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = " ".join(soup.get_text(separator=" ").split())
    return text[:MAX_TEXT_CHARS]
