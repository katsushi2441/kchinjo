#!/usr/bin/env python3
"""Kurage 陳情ナビ — 困りごとを、出せる形にする。

「市に言いたいことがあるが、どこに何をどう出せばいいか分からない」を、
**陳情書の体裁・所管の委員会・提出先・次の会期**まで繋ぐ。

**推測しない。** 締切日は市会が公表していないので書かない。
**転載しない。** 市のサイトの文章は載せず、事実と出典URLだけを持つ。
"""
from __future__ import annotations

import datetime
import os
from html import escape as e
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse,
                               PlainTextResponse)
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


# --- 検索から直接来る入口 -------------------------------------------------
# 入口を1枚しか持っていなかった間、この製品は Search Console で90日間 表示0 だった。
# 一方で同じ作りの kflood は「区名＋ハザードマップ」で9位前後に入っている。
# 差は語の粒度で、抽象語1枚ではなく**語ごとにページを持つ**必要がある。
# 実測（キーワードプランナー 2026-09-19）: 「陳情」6,600/月・競合低、
# 「陳情 請願 違い」720/月・競合低、「市議会 陳情」20/月。
_STATIC_PAGES = {
    "chinjo-seigan": "seigan.html",   # 陳情と請願の違い
    "kakikata": "kakikata.html",      # 陳情書の書き方
}


@app.get("/style.css")
def style():
    return FileResponse(HERE / "templates" / "style.css", media_type="text/css")


@app.get("/{slug}/", response_class=HTMLResponse)
def static_page(slug: str):
    if slug == "nagoya":
        return HTMLResponse(_nagoya_page())
    name = _STATIC_PAGES.get(slug)
    if not name:
        raise HTTPException(404, "そのページはありません")
    return FileResponse(HERE / "templates" / name)


def _nagoya_page() -> str:
    """名古屋市会のページ。会期は日付で変わるので、データから組み立てる。

    **f-string を使わない。** テンプレートに CSS や JS の波括弧が混ざったときに
    壊れるため、印（<!--NAME-->）を置換する形にしている。
    """
    cfg = load()
    html = (HERE / "templates" / "nagoya.html").read_text(encoding="utf-8")
    com = "".join(
        f"<tr><th>{e(c['name'])}</th><td>{e(c.get('what', ''))}</td></tr>"
        for c in cfg["committees"])
    clerk = (f"<tr><th>あて先</th><td>{e(cfg['addressee'])} 様</td></tr>"
             f"<tr><th>提出先</th><td>{e(cfg['clerk']['name'])}<br>"
             f"<a href=\"tel:{e(cfg['clerk']['tel'])}\">{e(cfg['clerk']['tel'])}</a></td></tr>"
             "<tr><th>議員の紹介</th><td><b>要りません</b></td></tr>"
             "<tr><th>押印</th><td>要りません（署名又は記名）</td></tr>")
    today = datetime.date.today()
    rows = []
    for s in cfg["sessions"]:
        d = datetime.date.fromisoformat(s["open"])
        when = f"{s['open']} 開会"
        if d >= today:
            when += f"（あと{(d - today).days}日）"
        else:
            when += "（終了）"
        rows.append(f"<tr><th>{e(s['name'])}</th><td>{when}</td></tr>")
    return (html.replace("<!--COMMITTEES-->", com)
                .replace("<!--CLERK-->", clerk)
                .replace("<!--SESSIONS-->", "".join(rows)))


@app.get("/sitemap.xml")
def sitemap():
    base = "https://kurage.exbridge.jp/kchinjo.php/"
    urls = [""] + [f"{s}/" for s in (*_STATIC_PAGES, "nagoya")]
    body = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            + "".join(f"<url><loc>{base}{u}</loc></url>" for u in urls)
            + "</urlset>")
    return PlainTextResponse(body, media_type="application/xml")


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return ("User-agent: *\nAllow: /\n\n"
            "Sitemap: https://kurage.exbridge.jp/kchinjo.php/sitemap.xml\n")


@app.get("/llms.txt", response_class=PlainTextResponse)
def llms():
    """AI検索向けの要約。答えられることと、答えないことを先に書く。"""
    cfg = load()
    com = "\n".join(f"- {c['name']}: {c.get('what', '')}" for c in cfg["committees"])
    return f"""# Kurage 陳情ナビ（名古屋市）

> 困りごとを入れると、名古屋市会に出せる陳情書の体裁に組み上げ、所管の常任委員会・
> 提出先・次の定例会の開会日まで返すサイト。

## 陳情と請願の違い
- 陳情: 議員の紹介は要らない／押印は要らない（署名又は記名）／結果の通知は無い／
  委員会へ送付され、必要と認めたときに審査
- 請願: 紹介議員が要る／署名又は記名押印／結果の通知がある／本会議で議題とし、
  委員会に付議して審査

## 常任委員会の所管
{com}

## 答えないこと
- **締切日**: 名古屋市会は締切日を設けているが日付を公表していない。推測しない。
  開会日だけを示し、{cfg['clerk']['name']}（{cfg['clerk']['tel']}）へ確認を案内する。
- **委員会の判定**: 言葉の一致で選んでいるだけで、当たらないときは「判定できませんでした」と返す。

## 出典
- 名古屋市会「請願・陳情の案内」 {cfg['clerk']['guide_url']}
- 年間スケジュール {cfg['clerk']['schedule_url']}
"""


@app.get("/healthz")
def healthz():
    return {"ok": True}
