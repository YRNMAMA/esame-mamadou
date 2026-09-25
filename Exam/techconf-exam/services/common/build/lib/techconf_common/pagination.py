"""Shared pagination helper."""

from typing import Any, Sequence


def paginate(items: Sequence[Any], page: int, page_size: int) -> dict:
    """Return a paginated response dict."""
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": list(items[start:end]),
        "page": page,
        "page_size": page_size,
        "total": total
    }


def parse_pagination_params(args: dict, max_page_size: int = 100) -> tuple[int, int]:
    """Parse and validate page/page_size from request args."""
    try:
        page = max(1, int(args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    try:
        page_size = max(1, min(max_page_size, int(args.get("page_size", 20))))
    except (ValueError, TypeError):
        page_size = 20
    return page, page_size