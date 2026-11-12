"""A model-worded version of the verdict explanation, accepted only if it stays inside the judge's own figures.

``courtroom.judge.explain`` builds the facts and a template sentence with no model at all. This module lets a model rephrase that
for a more natural read, then runs ``check_text`` on the answer: any number or exhibit id that is not in the facts refuses it, and
the template is used instead. So the model can change the wording and cannot introduce a figure.
"""

from __future__ import annotations

from courtroom.judge.explain import Facts, check_text, template_text
from courtroom.llm.client import LLMClient

SYSTEM = (
    "You explain a courtroom verdict to someone who is not a lawyer. The verdict was reached by a fixed rulebook, not by you. "
    "Use only the facts you are given. Do not add, change or estimate any number, name any exhibit that is not listed, or "
    "speculate about anything not listed. Write 3 to 5 plain sentences, at most 120 words. No preamble, no lists."
)


def explain_in_words(facts: Facts, client: LLMClient) -> dict[str, str | None]:
    fallback = template_text(facts)
    raw = client.complete(SYSTEM, "Facts of this verdict, already computed by the judge:\n" + fallback + "\n\nRewrite them as a short plain explanation.")
    if raw is None:
        return {"text": fallback, "source": "template", "note": client.last_error or "no language model answered"}
    problem = check_text(raw, facts)
    if problem is not None:
        return {"text": fallback, "source": "template", "note": f"the model's text was refused: {problem}"}
    return {"text": raw.strip(), "source": "model", "note": None}
