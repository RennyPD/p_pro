"""Error tracking without personal data (Fase 4 C).

Sentry (or GlitchTip, which speaks the same protocol) is enabled only when
``SENTRY_DSN`` is set. Nexo keeps data of minors (Ley 172-13), so events carry
only what is needed to fix a bug: the error and its stack trace, the route,
the request id and the institution. Never request bodies, headers, cookies,
query strings, local variables, breadcrumbs or the account's identity; emails
and long numbers (cédulas, phones, cards) in messages are masked.
"""

import logging
import re

from app.db.database import settings

logger = logging.getLogger("nexo.observability")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
LONG_NUMBER = re.compile(r"\d[\d -]{6,}\d")
TOKEN = re.compile(r"(?i)\b(bearer|token|password|secret)\b[=: ]+\S+")


def mask(text: str) -> str:
    text = EMAIL.sub("[correo]", text)
    text = TOKEN.sub(lambda match: f"{match.group(1)} [oculto]", text)
    return LONG_NUMBER.sub("[número]", text)


def scrub(event: dict, _hint: dict | None = None) -> dict:
    """``before_send``: keep the error, drop everything personal."""
    request = event.get("request") or {}
    event["request"] = {key: request[key] for key in ("method", "url") if key in request}
    if "url" in event["request"]:
        event["request"]["url"] = event["request"]["url"].split("?", 1)[0]
    event.pop("user", None)
    event.pop("breadcrumbs", None)
    event.pop("extra", None)
    contexts = event.get("contexts") or {}
    event["contexts"] = {
        key: contexts[key] for key in ("runtime", "os", "trace") if key in contexts
    }
    if "message" in event and isinstance(event["message"], str):
        event["message"] = mask(event["message"])
    logentry = event.get("logentry")
    if isinstance(logentry, dict):
        event["logentry"] = {"message": mask(str(logentry.get("message", "")))}
    for exception in (event.get("exception") or {}).get("values", []):
        if isinstance(exception.get("value"), str):
            exception["value"] = mask(exception["value"])
        for frame in (exception.get("stacktrace") or {}).get("frames", []):
            frame.pop("vars", None)
    tags = event.get("tags") or {}
    allowed = {"institution_id", "request_id", "route"}
    if isinstance(tags, dict):
        event["tags"] = {key: value for key, value in tags.items() if key in allowed}
    else:  # list of pairs
        event["tags"] = [pair for pair in tags if pair[0] in allowed]
    return event


def init_sentry() -> bool:
    if not settings.sentry_dsn:
        return False
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment or settings.app_environment,
        release=settings.sentry_release,
        # send_default_pii stays off (its default); scrub() enforces it anyway.
        include_local_variables=False,
        max_request_body_size="never",
        max_breadcrumbs=0,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        before_send=scrub,
        before_send_transaction=scrub,
    )
    logger.info("sentry_enabled")
    return True


def tag(name: str, value) -> None:
    """Tag the current scope (request id, institution); harmless when disabled."""
    if not settings.sentry_dsn:
        return
    import sentry_sdk

    sentry_sdk.get_isolation_scope().set_tag(name, str(value))
