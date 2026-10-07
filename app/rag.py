"""Tiny dependency-free RAG: chunk markdown playbooks by heading, rank with TF-IDF cosine."""
from __future__ import annotations

import math
import pathlib
import re
from collections import Counter

KB_DIR = pathlib.Path(__file__).resolve().parent.parent / "knowledge"
STOP = set("a an the and or of to in on is are for with this that it as by be at from if then".split())


def _tok(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9_]+", text.lower()) if w not in STOP and len(w) > 1]


class KnowledgeBase:
    def __init__(self, kb_dir: pathlib.Path = KB_DIR):
        self.chunks = []
        for f in sorted(kb_dir.glob("*.md")):
            title = f.stem
            for i, part in enumerate(re.split(r"\n(?=## )", f.read_text())):
                part = part.strip()
                if not part:
                    continue
                heading = part.splitlines()[0].lstrip("# ").strip()
                self.chunks.append({"id": f"{f.stem}#{i}", "source": f.name, "heading": heading,
                                    "text": part, "tf": Counter(_tok(f"{title} {part}"))})
        n = len(self.chunks)
        df = Counter(t for c in self.chunks for t in c["tf"])
        self.idf = {t: math.log((1 + n) / (1 + d)) + 1 for t, d in df.items()}
        for c in self.chunks:
            c["vec"] = {t: (1 + math.log(v)) * self.idf[t] for t, v in c["tf"].items()}
            c["norm"] = math.sqrt(sum(v * v for v in c["vec"].values())) or 1.0

    def search(self, query: str, k: int = 3) -> list[dict]:
        q = Counter(_tok(query))
        qvec = {t: (1 + math.log(v)) * self.idf[t] for t, v in q.items() if t in self.idf}
        qnorm = math.sqrt(sum(v * v for v in qvec.values())) or 1.0
        scored = []
        for c in self.chunks:
            dot = sum(w * c["vec"].get(t, 0) for t, w in qvec.items())
            if dot > 0:
                scored.append((dot / (qnorm * c["norm"]), c))
        scored.sort(key=lambda x: -x[0])
        return [{"id": c["id"], "heading": c["heading"], "text": c["text"], "score": round(s, 3)}
                for s, c in scored[:k]]


_kb = None


def get_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb
