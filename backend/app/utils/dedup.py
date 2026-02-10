from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


_WS_RE = re.compile(r"\s+")
_TRACKING_KEYS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "mkt_tok",
    "msclkid",
    "ref",
    "ref_src",
}


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

    query_pairs = parse_qsl(p.query or "", keep_blank_values=True)
    filtered: list[tuple[str, str]] = []
    for k, v in query_pairs:
        key = (k or "").strip()
        if not key:
            continue
        key_l = key.lower()
        if key_l.startswith("utm_"):
            continue
        if key_l in _TRACKING_KEYS:
            continue
        filtered.append((key, v))

    # Stable canonical form: sort by key then value
    filtered.sort(key=lambda kv: (kv[0].lower(), kv[1]))
    query = urlencode(filtered, doseq=True) if filtered else ""

    # Drop fragments; keep meaningful query params for dedup stability.
    return urlunparse((scheme, netloc, path, "", query, ""))


def domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""
