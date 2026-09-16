def paginate_and_filter(items, skip: int, limit: int, query: str | None, fields: tuple[str, ...]):
    if query:
        needle = query.casefold()
        items = [
            item
            for item in items
            if any(needle in str(getattr(item, field, "")).casefold() for field in fields)
        ]
    return items[skip : skip + limit]
