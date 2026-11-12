"""A stand-in for an Ollama server, for trying the AI features with no model and no key.

    python scripts/stub_ollama.py                       # listens on 127.0.0.1:11435
    OLLAMA_LOCAL_URL=http://127.0.0.1:11435 python -m courtroom serve

It answers ``/api/tags`` and ``/api/chat`` with canned replies shaped like a real model's: the lawyer picks the first legal
move and gives a reason, a drafted case is a fixed small case, and a spoken line repeats the exhibit title. The model it
reports is called ``stub-model`` so nothing it produces can be mistaken for a real model's output.
"""

from __future__ import annotations

import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

CASE = {
    "id": "x", "title": "Lee v. Park — The Borrowed Drone", "synopsis": "Lee lent Park a drone. It came back with a cracked frame. Park says it was already cracked.",
    "case_type": "civil", "standard": "preponderance", "charge": "Park broke the drone.",
    "elements": [{"id": "damage", "name": "Damage", "description": "Park damaged the drone."}],
    "witnesses": [{"id": "W-SAM", "name": "Sam Ortiz", "role": "neighbour", "credibility": 0.8, "bias_note": None}],
    "evidence": [
        {"id": "P-PHOTO", "title": "Photo of the cracked drone", "description": "A photo showing a cracked frame.", "kind": "physical", "owner": "prosecution", "fact_id": "f1", "support": {"damage": 0.8}, "reliability": 0.9},
        {"id": "P-SAM", "title": "Sam saw Park crash it", "description": "Sam says he watched Park crash the drone into a fence.", "kind": "testimony", "owner": "prosecution", "fact_id": "f2", "support": {"damage": 0.7}, "reliability": 0.7, "witness_id": "W-SAM"},
        {"id": "D-NOTE", "title": "Repair shop note", "description": "A shop note says the frame was already cracked.", "kind": "document", "owner": "defense", "fact_id": "f3", "support": {"damage": -0.6}, "reliability": 0.8},
        {"id": "D-MSG", "title": "Park's message to Lee", "description": "Park wrote that the frame looked cracked when he picked it up.", "kind": "document", "owner": "defense", "fact_id": "f4", "support": {"damage": -0.4}, "reliability": 0.6},
    ],
}


def reply(body: dict) -> str:
    system = body["messages"][0]["content"]
    user = body["messages"][-1]["content"]
    if "attorney in a stylised courtroom" in system:
        return json.dumps({"choice": 0, "reason": "This move helps my side the most right now."})
    if "plain-English description of a dispute" in system:
        return json.dumps(CASE)
    if "one spoken line for a lawyer" in system:
        title = re.search(r"Exhibit title: (.*)", user)
        text = re.search(r"Exhibit text: (.*)", user)
        wit = "witness" if "Witness:" in user else ""
        line = {"say": f"Your Honour, here is {title.group(1) if title else 'the exhibit'}.", "wit": f"I can tell you what I know. {text.group(1) if text else ''}" if wit else ""}
        return json.dumps(line)
    return "This is a stub reply."


class Handler(BaseHTTPRequestHandler):
    def _send(self, obj: dict) -> None:
        data = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        self._send({"models": [{"name": "stub-model"}]} if self.path.startswith("/api/tags") else {})

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        self._send({"message": {"role": "assistant", "content": reply(body)}})

    def log_message(self, *args: object) -> None:
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 11435
    print(f"stub Ollama on http://127.0.0.1:{port} (model: stub-model)")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
