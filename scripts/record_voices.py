"""Pre-record every courtroom line with fixed Kokoro voices, so speech sounds the same on every device.

The web app plays these MP3s when they exist and falls back to the browser's own speech otherwise
(only possible on a local server running trials outside the pre-run bundle).

Steps:
    node scripts/collect_lines.cjs > lines.json
    python scripts/record_voices.py lines.json --model model_quantized.onnx --voices voices.npz

Model: Kokoro-82M v1.0 (Apache-2.0), ONNX export from huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX.
voices.npz holds each voice's style table, shape (510, 1, 256), keyed by voice name.
Needs: kokoro-onnx (for phonemes), onnxruntime, soundfile, numpy, and ffmpeg on PATH.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import onnxruntime as ort
import soundfile as sf
from kokoro_onnx.tokenizer import Tokenizer

WEB = Path(__file__).resolve().parents[1] / "courtroom" / "viz" / "web"
OUT = WEB / "voices"
SR = 24000
MAX_TOKENS = 500

# The cast: (voice, accent, speed). British voices start with "b", American with "a".
MAIN = {
    "court": ("bm_george", 0.92),
    "prosecution": ("bf_emma", 1.0),
    "defense": ("am_michael", 1.0),
    "bailiff": ("am_adam", 0.95),
}
WITNESS = {
    "Maya": "af_sky", "Mrs. Bell": "bf_isabella", "Mr. Ortiz": "am_eric", "Kim": "af_nova", "Leo": "am_puck",
    "Mrs. Green": "bf_lily", "Dr. Fox": "af_sarah", "Dr. Lena Marsh": "af_nicole", "Priya Nandakumar": "af_jessica",
    "Det. Samuel Okafor": "am_onyx", "Mira Vance": "af_bella", "Prof. Ian Cho": "bm_lewis", "Tom Reyes": "am_liam",
    "Dana Whitfield": "af_river", "Rosa Ibarra": "af_nova", "Kofi Mensah": "am_echo", "Lin Zhao": "af_kore",
    "Dr. Sam Ortega": "am_fenrir", "Grace Obi": "af_heart", "Dr. Aiko Tan": "bf_alice", "Dr. Ben Hollis": "bm_daniel",
    "Dr. Ruth Adeyemi": "af_sarah", "Martin Lund": "bm_fable", "Operator A": "am_liam", "Operator B": "af_river",
    "Paid informant": "am_fenrir",
}


def cast(who: str) -> tuple[str, float]:
    if who.startswith("witness:"):
        name = who.split(":", 1)[1].split(",")[0].strip()
        return WITNESS.get(name, "af_heart" if name.startswith(("Mrs", "Ms")) else "am_eric"), 1.0
    return MAIN.get(who, ("am_eric", 1.0))


def key_of(who: str, text: str) -> str:
    """Stable file name for a line; app.js looks lines up by the same 'who|text' key in manifest.json."""
    return hashlib.sha1(f"{who}|{text}".encode()).hexdigest()[:16]


def speakable(text: str) -> str:
    # say "Mrs." as a word, read money and percentages naturally
    t = text.replace("“", "").replace("”", "").replace('"', "")
    t = re.sub(r"\$([\d,.]+)", r"\1 dollars", t)
    t = re.sub(r"(\d+)%", r"\1 percent", t)
    return t


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("lines")
    ap.add_argument("--model", required=True)
    ap.add_argument("--voices", required=True)
    ap.add_argument("--force", action="store_true", help="re-record lines that already have an MP3")
    ap.add_argument("--ffmpeg", default=shutil.which("ffmpeg") or "ffmpeg", help="path to ffmpeg if it isn't on PATH")
    a = ap.parse_args()

    lines = json.loads(Path(a.lines).read_text(encoding="utf8"))
    voices = np.load(a.voices)
    sess = ort.InferenceSession(a.model, providers=["CPUExecutionProvider"])
    tok = Tokenizer()
    OUT.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, str] = {}
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "line.wav"
        for i, line in enumerate(lines, 1):
            who, text = line["who"], line["text"]
            name = key_of(who, text)
            mp3 = OUT / f"{name}.mp3"
            manifest[f"{who}|{text}"] = f"{name}.mp3"
            if mp3.exists() and not a.force:
                continue
            voice, speed = cast(who)
            lang = "en-gb" if voice.startswith("b") else "en-us"
            phonemes = tok.phonemize(speakable(text), lang)
            # long lines are spoken sentence by sentence to stay inside the model's context
            chunks, cur = [], ""
            for part in re.split(r"(?<=[.!?,;:])\s+", phonemes):
                if cur and len(tok.tokenize(cur + " " + part)) > MAX_TOKENS:
                    chunks.append(cur)
                    cur = part
                else:
                    cur = f"{cur} {part}".strip()
            chunks.append(cur)
            audio = []
            for ch in chunks:
                ids = tok.tokenize(ch)
                style = voices[voice][len(ids)]
                out = sess.run(None, {
                    "input_ids": np.array([[0, *ids, 0]], dtype=np.int64),
                    "style": np.asarray(style, dtype=np.float32),
                    "speed": np.array([speed], dtype=np.float32),
                })[0]
                audio.append(np.squeeze(out))
                audio.append(np.zeros(int(SR * 0.12), dtype=np.float32))
            sf.write(wav, np.concatenate(audio), SR)
            subprocess.run(
                [a.ffmpeg, "-y", "-loglevel", "error", "-i", str(wav), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                 "-ac", "1", "-ar", "24000", "-b:a", "48k", str(mp3)],
                check=True,
            )
            if i % 25 == 0:
                print(f"{i}/{len(lines)}", flush=True)
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")), encoding="utf8")
    print(f"done: {len(manifest)} lines in {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
