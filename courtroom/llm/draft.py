"""Plain English in, a ``CaseFile`` out, for a person to check and edit.

The model proposes; the contracts decide what is valid. The reply is parsed as JSON and validated by the same pydantic
``CaseFile`` every other case goes through. If validation fails, the exact errors are sent back and the model is asked again, at
most ``MAX_REPAIRS`` times. A case that validates must still pass a few sanity checks (both sides have evidence, every point
the Accuser must prove has something bearing on it, the numbers are in range) before it is returned. It lands in the what-if
editor where every number is visible and editable; nothing here makes it a "real" case or touches a verdict.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

from pydantic import ValidationError

from courtroom.contracts import CaseFile, Side
from courtroom.llm.client import LLMClient

MAX_REPAIRS = 2
MAX_TEXT = 1500

SYSTEM = """You turn a short plain-English description of a dispute into a case file for a courtroom game. Reply with ONE JSON \
object and nothing else (no markdown fences, no commentary).

Everything must be fictional: invent names, never use real people, companies or brands.

The JSON object has these fields:
  "id": a short lowercase slug, letters digits and hyphens only
  "title": "Party v. Party — The Short Name"
  "synopsis": two plain sentences
  "case_type": "criminal" or "civil"
  "standard": criminal cases use "beyond_reasonable_doubt" or "clear_and_convincing"; civil cases use "preponderance"
  "charge": one sentence saying what the Accuser claims
  "elements": 1 to 3 things the Accuser must prove: {"id": "lowercase_with_underscores", "name": "short name", "description": "one sentence"}
  "witnesses": people who testify: {"id": "W-NAME", "name": "Full Name", "role": "their role", "credibility": 0.0 to 1.0, "bias_note": "or null"}
  "evidence": 4 to 8 exhibits, some owned by each side:
     {"id": "P-SOMETHING" (Accuser) or "D-SOMETHING" (Defender), "title": "...", "description": "one or two sentences",
      "kind": one of "document", "digital_log", "physical", "financial_record", "testimony", "expert",
      "owner": "prosecution" or "defense", "fact_id": "a short id for the underlying fact; two exhibits proving the same fact share it",
      "support": {"<element id>": a number from -1.0 (clearly helps the defense) to 1.0 (clearly helps the Accuser)},
      "reliability": 0.0 to 1.0 (how trustworthy the exhibit is), "witness_id": "a witness id, REQUIRED for testimony, else null",
      "hearsay": true/false, "authenticated": true/false, "lawfully_obtained": true/false, "disclosed": true/false,
      "personal_knowledge": true/false, "contradicts": ["ids of exhibits it contradicts"], "impeaches": ["witness ids it undermines"]}
Use at most two decimals for every number. Every key in "support" must be an element id. Give each side real evidence."""

REPAIR = "Your JSON was not accepted:\n{problems}\nReply again with the complete corrected JSON object only."


@dataclass
class Draft:
    case: CaseFile | None
    repairs: int = 0
    notes: list[str] = field(default_factory=list)
    error: str | None = None
    problems: list[str] = field(default_factory=list)  # what the last attempt got wrong, when it failed


def _strip(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if start >= 0 and end > start else text


def _round(x: object) -> object:
    return round(x, 2) if isinstance(x, float) else x


def _normalise(data: dict) -> dict:
    """Round every number the judge reads to two decimals before validation; models love 0.8500000001."""
    for e in data.get("evidence", []) or []:
        if isinstance(e, dict):
            e["reliability"] = _round(e.get("reliability"))
            if isinstance(e.get("support"), dict):
                e["support"] = {k: _round(v) for k, v in e["support"].items()}
    for w in data.get("witnesses", []) or []:
        if isinstance(w, dict):
            w["credibility"] = _round(w.get("credibility"))
    return data


def sanity(case: CaseFile) -> list[str]:
    """Things that make a valid case useless to play. Empty means fine."""
    problems: list[str] = []
    for side in Side:
        if not any(i.owner is side for i in case.evidence):
            problems.append(f"the {side.value} has no evidence")
    supported = {e.id: False for e in case.elements}
    for i in case.evidence:
        if i.owner is Side.PROSECUTION:
            for el, v in i.support.items():
                if v > 0:
                    supported[el] = True
    problems += [f"nothing the Accuser owns supports the element {el!r}" for el, ok in supported.items() if not ok]
    if len(case.evidence) < 3:
        problems.append("fewer than 3 exhibits")
    for i in case.evidence:
        if i.kind.value == "testimony" and i.witness_id is None:
            problems.append(f"{i.id} is testimony but names no witness")
        if not i.support:
            problems.append(f"{i.id} bears on no element")
    return problems


def _problems_text(exc: ValidationError) -> str:
    lines = []
    for err in exc.errors()[:8]:
        where = ".".join(str(p) for p in err["loc"])
        lines.append(f"- {where}: {err['msg']}")
    return "\n".join(lines)


def draft_case(description: str, client: LLMClient) -> Draft:
    description = " ".join(description.split())[:MAX_TEXT]
    prompt = f"Description of the dispute:\n{description}\n\nWrite the case file JSON."
    notes: list[str] = []
    raw = client.complete(SYSTEM, prompt)
    if raw is None:
        return Draft(None, 0, notes, error=client.last_error or "no language model answered")
    repairs = 0
    last_problems: list[str] = []
    while True:
        problems: list[str] = []
        case: CaseFile | None = None
        try:
            data = _normalise(json.loads(_strip(raw)))
            slug = hashlib.sha256(description.encode()).hexdigest()[:8]
            data["id"] = f"draft-{slug}"
            data["tags"] = ["custom"]
            case = CaseFile.model_validate(data)
            problems = sanity(case)
            if not problems:
                notes.append("The model proposed every number in this case. Check them before you trust a verdict.")
                if repairs:
                    notes.append(f"It needed {repairs} correction{'s' if repairs > 1 else ''} before the case passed the rule checks.")
                return Draft(case, repairs, notes)
        except json.JSONDecodeError as exc:
            problems = [f"not valid JSON ({exc.msg})"]
        except ValidationError as exc:
            problems = [_problems_text(exc)]
        except (TypeError, AttributeError) as exc:
            problems = [f"the JSON had the wrong shape ({type(exc).__name__})"]
        last_problems = problems
        if repairs >= MAX_REPAIRS:
            return Draft(None, repairs, notes, error="the model could not produce a valid case after repairs", problems=last_problems)
        repairs += 1
        raw = client.complete(SYSTEM, prompt + "\n\n" + REPAIR.format(problems="\n".join(problems)))
        if raw is None:
            return Draft(None, repairs, notes, error=client.last_error or "the model stopped answering", problems=last_problems)
