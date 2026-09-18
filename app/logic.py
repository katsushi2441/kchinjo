"""困りごとから、陳情書の形と提出先・日程を組み立てる。

**推測しない。** 陳情の締切日は市会が「各定例会等で締切日を設けています」と
書いているだけで、具体的な日付を公表していない。だから当サイトは締切を
書かない。開会日を示し、締切は事務局に確認するよう案内する。

**市のサイトの本文は転載しない。** 持つのは事実（日付・所管・様式の項目）と
出典URLだけ。
"""
from __future__ import annotations

import datetime
import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def load(city: str = "nagoya") -> dict:
    return json.loads((DATA / f"{city}.json").read_text(encoding="utf-8"))


def pick_committee(topic: str, cfg: dict, reason: str = "") -> tuple[dict | None, list]:
    """語の一致で所管の常任委員会を選ぶ。**LLMを使わない**（説明できる判定にする）。

    **困りごと本文を、理由より重く見る。** 「通学路の歩道を広げてほしい」の理由に
    「児童が」と書くと、理由の語に引かれて教育子ども委員会になってしまう。
    歩道は土木交通の所管なので、求めていること（topic）を優先する。

    当たらなければ None を返す。当てずっぽうで1つ選ばない。
    """
    topic, reason = str(topic or ""), str(reason or "")
    scored = []
    for c in cfg["committees"]:
        in_topic = [w for w in c["words"] if w and w in topic]
        in_reason = [w for w in c["words"] if w and w in reason and w not in in_topic]
        score = len(in_topic) * 3 + len(in_reason)
        if score:
            scored.append((score, c, in_topic + in_reason))
    if not scored:
        return None, []
    scored.sort(key=lambda x: -x[0])
    top = scored[0]
    others = [{"name": c["name"], "words": h} for _, c, h in scored[1:3]]
    return {"name": top[1]["name"], "what": top[1]["what"], "words": top[2],
            "others": others}, [c for _, c, _ in scored]


def next_session(cfg: dict, today: datetime.date | None = None) -> dict | None:
    """次に開会する会期。無ければ None（年度替わりで一覧が切れることがある）。"""
    today = today or datetime.date.today()
    for s in cfg["sessions"]:
        if datetime.date.fromisoformat(s["open"]) >= today:
            return dict(s, days_until=(datetime.date.fromisoformat(s["open"]) - today).days)
    return None


# 「〜てほしい」で書かれた困りごとを、陳情書の言い回しに直す。
# **文法をでっち上げない。** 「〜てほしい」→「〜ていただく」は機械的に置き換えられる
# 唯一安全な形なので、それだけをやる。当たらない書き方はそのまま使い、
# 画面側で件名を直せるようにしておく。
_ASK_SUFFIX = (("てほしい", "ていただき"), ("て欲しい", "ていただき"),
               ("てください", "ていただき"), ("して下さい", "していただき"))


def _to_request_form(topic: str) -> tuple[str, str]:
    """(陳情事項に使う形, 件名に使う形) を返す。

    「通学路の歩道を広げてほしい」→（"通学路の歩道を広げていただき",
                                  "通学路の歩道を広げていただくこと"）
    """
    for suf, rep in _ASK_SUFFIX:
        if topic.endswith(suf):
            stem = topic[: -len(suf)] + rep
            return stem, stem[:-1] + "くこと"      # 「…いただき」→「…いただくこと」
    # 名詞で書かれたとき（「防災訓練の実施」）。動詞を足すと壊れるので、
    # 「〜について」の形にして、件名はそのまま名詞を使う。
    if topic and topic[-1] not in "うくすつぬむるいたてでにを":
        return f"{topic}についてご検討いただき", topic
    return topic, f"{topic}こと"


def build_document(topic: str, reason: str, name: str, address: str,
                   cfg: dict, today: datetime.date | None = None) -> dict:
    """陳情書の本文を組み立てる。**様式は市会の書式例に合わせる。**

    陳情は「署名又は記名」で、押印は要らない（請願は「署名又は記名押印」で
    紹介議員も要る）。ここを取り違えると受理されない。
    """
    today = today or datetime.date.today()
    topic = " ".join(str(topic or "").split())
    ask, req = _to_request_form(topic)
    era_y = today.year - 2018            # 令和
    date_ja = f"令和{era_y}年{today.month}月{today.day}日"
    title = topic if topic.endswith("陳情書") else f"{req}を求める陳情書"
    body = [
        title,
        "",
        "陳情事項",
        f"　{ask}ますよう、お願いします。",
        "",
        "理由",
    ]
    for line in [x.strip() for x in str(reason or "").splitlines() if x.strip()]:
        body.append(f"　{line}")
    body += ["", f"　　　　　　　　　　{date_ja}", "",
             f"{cfg['addressee']}　様", "",
             f"　陳情者住所　{address or '（住所）'}",
             f"　氏名　　　　{name or '（氏名）'}"]
    return {"title": title, "text": "\n".join(body), "date_ja": date_ja}
