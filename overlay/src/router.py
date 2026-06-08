"""Deterministic BioClaw router.

Known biocuration workflows should not depend on an LLM emitting exact tool
syntax. This module turns common user messages into grounded BioKG/PLN calls
and returns OmegaClaw command text such as `send ...`.
"""
import os
import re


def route_direct(msgnew, msg, lastresults="") -> str:
    """Return an OmegaClaw command string, or "" to let the LLM handle it."""
    if os.environ.get("BIOCLAW_PROMPT", "").strip().lower() != "conductor":
        return ""
    if _truthy(msgnew):
        return route_human_message(msg)
    return route_last_results(lastresults)


def route_human_message(msg: str) -> str:
    text = _clean_message(msg)
    if not text:
        return ""
    lower = text.lower().strip().rstrip(".")

    m = re.match(r"^approve\s+([0-9a-f]{8})$", lower)
    if m:
        import biokg
        return _send(biokg.promote(m.group(1)))

    m = re.match(r"^reject\s+([0-9a-f]{8})$", lower)
    if m:
        import biokg
        return _send(biokg.reject(m.group(1)))

    if lower in {"show staging", "list staging", "what's pending", "whats pending", "pending proposals"}:
        import biokg
        return _send(biog_single_line(biokg.list_staging()))

    entity = _lookup_entity(text)
    if entity:
        import biokg
        return _send(biokg.lookup(entity))

    edge = _edge_question(text, prefixes=("who said ", "source of ", "evidence for "))
    if edge:
        import biokg
        return _send(biokg.provenance("|".join(edge)))

    edge = _edge_question(text, prefixes=("reconcile ", "merge evidence for "))
    if edge:
        import biokg
        return _send(biokg.pln_evidence_merge_pipe("|".join(edge)))

    target = _enhancer_target(text)
    if target:
        import biokg
        return _send(biokg.pln_source_aggregate_pipe(f"{target}|associated_with|enhancer"))

    staged = _stage_request(text)
    if staged:
        import biokg
        result = biokg.stage_pipe("|".join(staged))
        sid = _staging_id(result)
        if sid:
            result += f" To approve, reply: approve {sid}. To reject, reply: reject {sid}."
        return _send(result)

    return ""


def route_last_results(lastresults: str) -> str:
    text = _decode(lastresults)
    marker = " replied — relay this verbatim to the user with the send command]: "
    idx = text.find(marker)
    if idx < 0:
        return ""
    reply = text[idx + len(marker):]
    reply = _strip_result_tail(reply)
    if not reply:
        return ""
    return _send(reply)


def _lookup_entity(text: str) -> str:
    q = re.sub(r"\s+", " ", text).strip().rstrip("?.!")
    patterns = (
        (r"^what\s+does\s+(.+?)\s+do$", 1),
        (r"^tell\s+me\s+about\s+(.+)$", 1),
        (r"^what\s+is\s+(.+)$", 1),
        (r"^show\s+me\s+(.+)$", 1),
    )
    for pattern, group in patterns:
        m = re.match(pattern, q, flags=re.IGNORECASE)
        if m:
            return m.group(group).strip()
    return ""


def _edge_question(text: str, prefixes: tuple):
    q = re.sub(r"\s+", " ", text).strip().rstrip("?.!")
    lower = q.lower()
    for prefix in prefixes:
        if not lower.startswith(prefix):
            continue
        body = q[len(prefix):].strip()
        parts = body.split(maxsplit=2)
        if len(parts) == 3:
            return parts[0], parts[1], parts[2]
    return None


def _enhancer_target(text: str) -> str:
    q = re.sub(r"\s+", " ", text).strip().rstrip("?.!")
    m = re.match(r"^(?:is|are)\s+(.+?)\s+enhancer[-\s]?regulated$", q, flags=re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _stage_request(text: str):
    q = re.sub(r"\s+", " ", text).strip().rstrip(".")
    m = re.match(
        r"^(?:propose adding edge|stage)\s*:?\s+(.+?)\s+([A-Za-z_][A-Za-z0-9_]*)\s+(.+?)(?:,\s*evidence\s*:\s*(.+))?$",
        q,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    source, edge, target, evidence = m.groups()
    return source.strip(), edge.strip(), target.strip(), (evidence or "proposed by biocurator").strip()


def _clean_message(msg: str) -> str:
    text = _decode(msg).strip().strip('"').strip("'").strip()
    if ":" in text:
        speaker, rest = text.split(":", 1)
        if speaker and " " not in speaker and len(speaker) <= 64:
            text = rest.strip()
    return text


def _decode(text: str) -> str:
    return (str(text)
            .replace("_quote_", '"')
            .replace("_apostrophe_", "'")
            .replace("_newline_", "\n"))


def _send(text: str) -> str:
    return "send " + biog_single_line(text)


def biog_single_line(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).replace("\r", " ").replace("\n", " ")).strip()


def _staging_id(text: str) -> str:
    m = re.search(r"\[STAGED edge ([0-9a-f]{8})\]", str(text), flags=re.IGNORECASE)
    return m.group(1) if m else ""


def _strip_result_tail(text: str) -> str:
    text = text.strip()
    for marker in ('_quote_', '"))', '")', '))'):
        idx = text.find(marker)
        if idx >= 0:
            text = text[:idx]
    return text.strip().strip('"').strip("'").strip()


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "t", "yes"}
