"""Call an OpenAI-compatible LLM to normalize STL file part names and categories.

The service sends a structured list of filenames to the configured endpoint and
expects back a JSON object mapping file IDs to suggested part_type, part_name,
and sup_base_filename values.  It works with Ollama (no key required), OpenAI,
or any other server that implements the /v1/chat/completions endpoint.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

_log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are an assistant that normalizes 3D-printing STL file names for a miniature figure library.

Given a JSON list of STL files (id, filename, current part_type, current part_name), return a JSON object with a single key "files" containing an array of suggestions.

Rules:
1. part_type: assign ONE short category that best describes the piece. Use Title Case.
   Common values: Body, Head, Arm, Leg, Weapon, Shield, Base, Cape, Accessory, Torso, Hand, Foot.
   If the type cannot be inferred, leave null.
2. part_name: a short human-readable label (e.g. "Right Arm", "Helmeted Head 2").
   Strip leading category tokens, underscores, and numeric suffixes where they add no meaning.
   If the existing part_name is already clean, repeat it unchanged.
3. sup_base_filename: if this file is a presupported variant of another file in the list,
   return the EXACT filename of its base (non-supported) counterpart. Otherwise null.
   Presupported files typically start with "Sup_", "(S)", or contain "supported"/"presupported".
4. Only include files where you are making at least one change. Omit unchanged files.
5. Return ONLY the JSON object — no markdown, no explanation.

Example output:
{"files": [
  {"id": 1, "part_type": "Head", "part_name": "Helmeted Head", "sup_base_filename": null},
  {"id": 2, "part_type": "Head", "part_name": "Helmeted Head", "sup_base_filename": "Head_01.stl"}
]}"""


def run(
    files: list[dict[str, Any]],
    base_url: str,
    model: str,
    api_key: str = "",
) -> list[dict[str, Any]]:
    """Call the LLM and return a list of suggestion dicts.

    Each dict has keys: id (int), part_type (str|None), part_name (str|None),
    sup_base_filename (str|None).  Raises ValueError on unrecoverable errors so
    the caller can surface a clean 400/500 to the user.
    """
    base_url = base_url.rstrip("/")
    if not base_url:
        raise ValueError("AI organizer URL is not configured")
    if not model:
        raise ValueError("AI organizer model is not configured")

    user_content = json.dumps(
        [{"id": f["id"], "filename": f["filename"],
          "part_type": f.get("part_type"), "part_name": f.get("part_name")}
         for f in files],
        ensure_ascii=False,
    )

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
    }
    # Attempt JSON mode — not all models/servers support it, so we don't hard-fail
    # if the server returns a 400 for this field; we retry without it.
    payload["response_format"] = {"type": "json_object"}

    endpoint = f"{base_url}/v1/chat/completions"
    try:
        resp = httpx.post(endpoint, json=payload, headers=headers, timeout=120)
    except httpx.RequestError as exc:
        raise ValueError(f"Could not reach AI organizer at {base_url}: {exc}") from exc

    if resp.status_code == 400 and "response_format" in resp.text:
        # Model doesn't support JSON mode — retry without it
        payload.pop("response_format", None)
        try:
            resp = httpx.post(endpoint, json=payload, headers=headers, timeout=120)
        except httpx.RequestError as exc:
            raise ValueError(f"Could not reach AI organizer at {base_url}: {exc}") from exc

    if not resp.is_success:
        raise ValueError(f"AI organizer returned {resp.status_code}: {resp.text[:300]}")

    try:
        body = resp.json()
        raw_text: str = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unexpected response shape from AI organizer: {exc}") from exc

    # Strip markdown code fences if the model wrapped the JSON
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```", 2)[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.rsplit("```", 1)[0].strip()

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        _log.warning("AI organizer returned non-JSON: %s", raw_text[:200])
        raise ValueError(f"AI organizer did not return valid JSON: {exc}") from exc

    suggestions = data.get("files", [])
    if not isinstance(suggestions, list):
        raise ValueError("AI organizer response missing 'files' array")

    return suggestions
