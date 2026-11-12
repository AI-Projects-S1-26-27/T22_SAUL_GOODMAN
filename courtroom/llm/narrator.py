"""Spoken lines for a case that has no script, worded by the model from the exhibit's own text and nothing else.

``courtroom/viz/web/story.js`` holds the hand-written lines for the library cases. For any other case (a generated one, an edited
one, one drafted from English) the page builds plain lines from the exhibit's title and description, and this module can do
better: it asks the model to word each line, tells it to add no facts, and then *checks* the reply. A line is accepted only if
every number in it appears in the source text and every capitalised word is either in the source or an ordinary courtroom word.
A line that fails is dropped and the page keeps its generic one. The narration is returned beside the trial and never written into
a trial event, so it cannot move a digest or a verdict.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel

from courtroom.contracts import CaseFile, EvidenceItem, Side
from courtroom.llm.client import LLMClient

SYSTEM = (
    "You write one spoken line for a lawyer in a courtroom game, in plain everyday English, at most 40 words. Use ONLY the "
    "facts in the exhibit text you are given. Do not add any name, number, place, time or detail that is not in it. Speak as the "
    "lawyer addressing the judge (\"Your Honour, ...\"). For a witness, also write what the witness says on the stand, in the "
    "first person, using only the exhibit text. Reply with JSON {\"say\": \"...\", \"wit\": \"...\"}; leave \"wit\" empty if "
    "the exhibit is not a witness."
)

ORDINARY = {
    "Your", "Honour", "Honor", "I", "I'd", "I'm", "The", "This", "That", "These", "Here", "We", "He", "She", "They", "It", "Please", "Thank",
    "Accuser", "Defender", "Judge", "Court", "Mr", "Mrs", "Ms", "Dr", "Prof", "My", "Our", "In", "On", "At", "As", "A", "An", "And", "But",
    "Yes", "No", "Not", "When", "What", "Who", "Why", "How", "If", "So", "Then", "There", "Now", "Today", "Evidence", "Exhibit", "Witness",
}


class Line(BaseModel):
    say: str = ""
    wit: str = ""


def _source(case: CaseFile, item: EvidenceItem) -> str:
    witness = case.witness(item.witness_id) if item.witness_id else None
    parts = [case.title, case.synopsis, case.charge, item.title, item.description]
    if witness:
        parts += [witness.name, witness.role]
    return " ".join(parts)


def check_line(text: str, source: str) -> str | None:
    """None if the line adds nothing new, else why it is refused."""
    src_low = source.lower()
    for num in re.findall(r"\d+(?:[.,]\d+)?", text):
        if num not in source:
            return f"it used the number {num}, which is not in the exhibit text"
    src_words = set(re.findall(r"[A-Za-z']+", source))
    for word in re.findall(r"\b[A-Z][a-z']+", text):
        if word not in ORDINARY and word not in src_words and word.lower() not in src_low:
            return f"it used the name or word {word!r}, which is not in the exhibit text"
    return None


def narrate_case(case: CaseFile, client: LLMClient) -> dict[str, Any]:
    """Model-worded lines for every exhibit, with the refused ones listed. Offline this returns an empty ``ev``."""
    client.start_trial()
    ev: dict[str, dict[str, str]] = {}
    refused: dict[str, str] = {}
    for item in case.evidence:
        witness = case.witness(item.witness_id) if item.witness_id else None
        who = "the Accuser" if item.owner is Side.PROSECUTION else "the Defender"
        prompt = (
            f"You speak for {who}.\nExhibit title: {item.title}\nExhibit text: {item.description}\n"
            + (f"Witness: {witness.name}, {witness.role}\n" if witness else "")
            + "Write the JSON."
        )
        raw = client.complete(SYSTEM, prompt, schema=Line)
        if raw is None:
            refused[item.id] = "the model did not answer"
            continue
        try:
            line = Line.model_validate(json.loads(raw))
        except (ValueError, TypeError):
            refused[item.id] = "the reply was not the expected JSON"
            continue
        source = _source(case, item)
        why = check_line(line.say, source) or (check_line(line.wit, source) if line.wit else None)
        if not line.say.strip() or why:
            refused[item.id] = why or "empty line"
            continue
        entry = {"say": line.say.strip()}
        if witness:
            if not line.wit.strip():
                refused[item.id] = "no testimony given for a witness"
                continue
            entry |= {"witness": f"{witness.name}, {witness.role}", "wit": line.wit.strip()}
            # the page splits a witness's line at "calls <Name>, <role>.", so keep that shape
            entry["say"] = f"{who.capitalize()} calls {witness.name}, {witness.role}. {entry['say']}"
        ev[item.id] = entry
    client.save()
    return {"ev": ev, "refused": refused, "source": client.last_source, "model": client.last_model}
