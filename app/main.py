#!/usr/bin/env python3
"""Kurage 陳情ナビ — 困りごとを、出せる形にする。

「市に言いたいことがあるが、どこに何をどう出せばいいか分からない」を、
**陳情書の体裁・所管の委員会・提出先・次の会期**まで繋ぐ。

**推測しない。** 締切日は市会が公表していないので書かない。
**転載しない。** 市のサイトの文章は載せず、事実と出典URLだけを持つ。
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .logic import build_document, load, next_session, pick_committee

HERE = Path(__file__).resolve().parent
app = FastAPI(title="Kurage 陳情ナビ")
PORT = int(os.environ.get("KCHINJO_PORT", "18377"))


class Ask(BaseModel):
    topic: str = ""
    reason: str = ""
    name: str = ""
    address: str = ""


# **Jinja を使わない。** 画面のデータは全部 API から取るので変数を差し込む必要が無く、
# テンプレートにすると JS の `${...}` や CSS の `{` が Jinja の構文と衝突する。
@app.get("/")
def index():
    return FileResponse(HERE / "templates" / "index.html")


@app.post("/api/build")
def api_build(a: Ask):
    cfg = load()
    topic = (a.topic or "").strip()
    if not topic:
        return JSONResponse({"error": "困りごとを書いてください"}, status_code=400)
    com, _ = pick_committee(topic, cfg, a.reason or "")
    doc = build_document(topic, a.reason, a.name, a.address, cfg)
    return {
        "document": doc,
        "committee": com,          # 当たらなければ None。当てずっぽうで1つ選ばない
        "session": next_session(cfg),
        "clerk": cfg["clerk"],
        "deadline_note": cfg["deadline_note"],
    }


@app.get("/healthz")
def healthz():
    return {"ok": True}
