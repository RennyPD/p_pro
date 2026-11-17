def paginate_and_filter(items, skip: int, limit: int, query: str | None, fields: tuple[str, ...]):
    if query:
        needle = query.casefold()
        items = [
            item
            for item in items
            if any(needle in str(getattr(item, field, "")).casefold() for field in fields)
        ]
    return items[skip : skip + limit]


def page_query(query, response, skip: int, limit: int | None):
    total = query.order_by(None).count()
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Has-More"] = str(limit is not None and skip + limit < total).lower()
    return query.offset(skip).limit(limit).all()
