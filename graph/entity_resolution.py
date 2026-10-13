"""
Deterministic entity deduplication via canonical keys.
No fuzzy matching in v1 — use sha256(domain:identifier).
"""
import hashlib
import re
from urllib.parse import urlparse


def extract_domain(url: str) -> str:
    """Extract domain host from URL."""
    if not url:
        return "unknown"
    try:
        parsed = urlparse(url)
        return parsed.netloc or parsed.path.split('/')[0] or "unknown"
    except Exception:
        return "unknown"


def normalize_name(name: str) -> str:
    """Lowercase, strip, collapse whitespace, remove punctuation."""
    if not name:
        return ""
    name = name.lower().strip()
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name)
    return name


def canonical_key(domain: str, product_id: str | None = None,
                  name: str | None = None) -> str:
    """
    Generate a deterministic dedup key.
    Priority: product_id (e.g. ASIN) > normalized name.
    """
    domain_str = domain.lower() if domain else "unknown"
    identifier = product_id.strip() if (product_id and product_id.strip()) else normalize_name(name or "")
    raw = f"{domain_str}:{identifier}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()
