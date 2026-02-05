from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse


_WS_RE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    s = (name or "").strip().lower()
    s = _WS_RE.sub(" ", s)
    return s


def canonicalize_url(url: str) -> str:
    try:
        p = urlparse(url)
    except Exception:
        return url
    netloc = p.netloc.lower()
    scheme = p.scheme.lower() or "https"
    path = p.path or "/"
    # Drop common tracking query params by removing all query entirely for dedup
    return urlunparse((scheme, netloc, path, "", "", ""))


def domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""
