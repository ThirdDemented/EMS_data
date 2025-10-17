"""gpt5_websearch_integration
================================

Integration utilities for the ESO Dashboard Builder platform to generate
live EMS data insights via OpenAI's GPT-5 web search capabilities.

The module exposes a single public function, ``generate_live_insight``, which
accepts a plain-language query and returns an object containing a textual
summary and the associated web citations sourced from authoritative EMS
websites. Requests are cached in-memory for six hours to avoid unnecessary
network calls and can be safely imported within FastAPI or Flask backends.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from openai import OpenAI


_CACHE: Dict[Tuple[str, str, str], Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 6 * 60 * 60  # Six hours.
_DEFAULT_ALLOWED_DOMAINS: List[str] = [
    "www.cdc.gov",
    "nemsis.org",
    "www.ems.gov",
    "www.naemt.org",
    "pubmed.ncbi.nlm.nih.gov",
    "www.fema.gov",
    "journals.lww.com",
]
_DEFAULT_LOCATION: Dict[str, str] = {
    "country": "US",
    "region": "Illinois",
    "city": "Havana",
}

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    """Return a singleton OpenAI client instance."""

    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def _cache_key(query: str, reasoning_effort: str, location: Optional[Mapping[str, str]]) -> Tuple[str, str, str]:
    """Generate a cache key for the current request."""

    location_key = "|".join(
        f"{key}:{value}" for key, value in sorted((location or {}).items())
    )
    return (query.strip(), reasoning_effort.strip().lower(), location_key)


def _is_cached(key: Tuple[str, str, str]) -> bool:
    """Determine whether a cache entry is still valid."""

    if key not in _CACHE:
        return False
    expires_at, _ = _CACHE[key]
    return time.time() < expires_at


def _get_cached(key: Tuple[str, str, str]) -> Optional[Dict[str, Any]]:
    """Retrieve a cached response if it remains valid."""

    if not _is_cached(key):
        _CACHE.pop(key, None)
        return None
    return _CACHE[key][1]


def _cache_response(key: Tuple[str, str, str], value: Dict[str, Any]) -> None:
    """Store a response in the cache with the configured TTL."""

    expires_at = time.time() + _CACHE_TTL_SECONDS
    _CACHE[key] = (expires_at, value)


def _merge_locations(location: Optional[Mapping[str, str]]) -> Dict[str, str]:
    """Combine the default location metadata with any user-supplied overrides."""

    merged = dict(_DEFAULT_LOCATION)
    if location:
        merged.update({k: v for k, v in location.items() if v})
    return merged


def _to_dict(obj: Any) -> Any:
    """Convert SDK response objects to primitive dictionaries for parsing."""

    if obj is None:
        return None

    if isinstance(obj, (dict, list, str, int, float, bool)):
        return obj

    for attr in ("model_dump", "dict", "to_dict"):
        if hasattr(obj, attr):
            method = getattr(obj, attr)
            try:
                return method()  # type: ignore[misc]
            except TypeError:
                try:
                    return method(exclude_none=True)  # type: ignore[misc]
                except TypeError:
                    continue

    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)

    return obj


def _extract_text(response: Any) -> str:
    """Extract textual content from the response object."""

    if hasattr(response, "output_text") and response.output_text:
        return str(response.output_text)

    response_dict = _to_dict(response)
    if isinstance(response_dict, dict):
        text = response_dict.get("output_text")
        if text:
            return str(text)
        if "output" in response_dict:
            text_fragments: List[str] = []
            for item in _iterate_items(response_dict["output"]):
                if isinstance(item, dict):
                    content = item.get("content")
                    if isinstance(content, str):
                        text_fragments.append(content)
                    elif isinstance(content, Iterable) and not isinstance(content, (str, bytes)):
                        for nested in content:
                            if isinstance(nested, dict) and nested.get("type") in {"output_text", "text"}:
                                value = nested.get("text") or nested.get("output_text")
                                if value:
                                    text_fragments.append(str(value))
            if text_fragments:
                return "\n".join(text_fragments)
    return ""


def _iterate_items(obj: Any) -> Iterable[Any]:
    """Yield elements from nested lists and dictionaries."""

    if isinstance(obj, dict):
        for value in obj.values():
            yield from _iterate_items(value)
    elif isinstance(obj, list):
        for item in obj:
            yield item
            yield from _iterate_items(item)
    else:
        yield obj


def _extract_citations(response: Any) -> List[Dict[str, str]]:
    """Extract citations from the response payload."""

    citations: List[Dict[str, str]] = []
    response_dict = _to_dict(response)
    seen_urls: set[str] = set()

    def _collect(data: Any) -> None:
        if isinstance(data, dict):
            possible = data.get("citations")
            if isinstance(possible, list):
                for entry in possible:
                    _collect(entry)
            url = data.get("url") or data.get("href")
            if url and isinstance(url, str) and url not in seen_urls:
                title = (
                    data.get("title")
                    or data.get("name")
                    or data.get("source")
                    or "Source"
                )
                citations.append({"title": str(title), "url": url})
                seen_urls.add(url)
            for value in data.values():
                _collect(value)
        elif isinstance(data, list):
            for item in data:
                _collect(item)

    _collect(response_dict)
    return citations


def generate_live_insight(
    query: str,
    reasoning_effort: str = "low",
    location: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Generate a live EMS insight using GPT-5 web search.

    Args:
        query: The natural-language question or request to answer.
        reasoning_effort: Hint to the model regarding effort ("low", "medium", "high").
        location: Optional mapping of user location metadata overrides.

    Returns:
        A dictionary containing the response text and associated citations.
    """

    cache_key = _cache_key(query, reasoning_effort, location)
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    client = _get_client()
    metadata_location = _merge_locations(location)

    try:
        response = client.responses.create(
            model="gpt-5",
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are an EMS analytics assistant for the ESO Dashboard Builder. "
                        "Use live web search to find current, authoritative data and include citations."
                    ),
                },
                {"role": "user", "content": query},
            ],
            reasoning={"effort": reasoning_effort},
            tools=[
                {
                    "type": "web_search",
                    "web_search": {
                        "allowed_domains": _DEFAULT_ALLOWED_DOMAINS,
                    },
                }
            ],
            metadata={"user_location": metadata_location},
        )

        result = {
            "text": _extract_text(response) or "",
            "citations": _extract_citations(response),
        }
        _cache_response(cache_key, result)
        return result
    except Exception as exc:  # pylint: disable=broad-except
        return {
            "text": f"⚠️ Error retrieving live insight: {exc}",
            "citations": [],
        }


if __name__ == "__main__":
    print(generate_live_insight("What are 2025 national EMS staffing trends?"))
