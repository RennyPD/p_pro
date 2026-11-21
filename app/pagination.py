"""Listing helpers that filter and paginate in the database (audit M3)."""

from sqlalchemy import or_


def search(query, text: str | None, *columns):
    """Case-insensitive ``contains`` over any of ``columns``; no-op without text."""
    if text and (term := text.strip()):
        query = query.filter(or_(*(column.icontains(term, autoescape=True) for column in columns)))
    return query


def page_query(query, response, skip: int, limit: int | None):
    total = query.order_by(None).count()
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Has-More"] = str(limit is not None and skip + limit < total).lower()
    return query.offset(skip).limit(limit).all()
