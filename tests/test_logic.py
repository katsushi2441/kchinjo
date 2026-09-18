"""判定と文面の決まりを固定する。**ここが崩れたら直す前に気づくため。**"""
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.logic import build_document, load, next_session, pick_committee  # noqa: E402

CFG = load()

# 所管の振り分け。**「通学路」は道路であって学校ではない**（一度間違えた）
ROUTING = [
    ("通学路の歩道を広げてほしい", "児童が車道にはみ出しています", "土木交通委員会"),
    ("学校の給食費を下げてほしい", "子育て世帯の負担が重い", "教育子ども委員会"),
    ("公園の遊具を直してほしい", "子どもが遊べません", "土木交通委員会"),
    ("避難所の場所をわかりやすくしてほしい", "高齢の親が分かりません", "都市消防委員会"),
    ("ごみ集積場所を増やしてほしい", "", "総務環境委員会"),
    ("市バスの本数を増やしてほしい", "", "土木交通委員会"),
    ("介護保険の窓口を増やしてほしい", "", "財政福祉委員会"),
    ("水道料金を下げてほしい", "", "経済水道委員会"),
]


def test_routing():
    for topic, reason, want in ROUTING:
        got, _ = pick_committee(topic, CFG, reason)
        assert got and got["name"] == want, f"{topic} → {got and got['name']}（期待 {want}）"


def test_unknown_is_not_guessed():
    """当たらないときに、当てずっぽうで1つ選ばないこと。"""
    got, _ = pick_committee("宇宙人が来たので対応してほしい", CFG)
    assert got is None


def test_document_reads_naturally():
    """「〜てほしいを求める陳情書」のような壊れた日本語を出さないこと。"""
    d = build_document("通学路の歩道を広げてほしい", "理由。", "名古屋 花子", "中区", CFG)
    assert d["title"] == "通学路の歩道を広げていただくことを求める陳情書"
    assert "広げていただきますよう、お願いします。" in d["text"]
    # 名詞で書かれても壊れない
    n = build_document("防災訓練の実施", "理由。", "花子", "中区", CFG)
    assert n["title"] == "防災訓練の実施を求める陳情書"
    assert "についてご検討いただきますよう" in n["text"]


def test_document_has_required_parts():
    """市会の書式例にある項目がそろっていること。**陳情に押印は要らない。**"""
    d = build_document("公園の遊具を直してほしい", "壊れています。", "名古屋 花子",
                       "名古屋市中区三の丸1-1-1", CFG)
    t = d["text"]
    for part in ("陳情事項", "理由", "名古屋市会議長", "陳情者住所", "氏名"):
        assert part in t, part
    assert "押印" not in t


def test_deadline_is_never_invented():
    """**締切日を作らないこと。** 市会が公表していない。"""
    assert "締切" not in build_document("公園の遊具を直してほしい", "", "", "", CFG)["text"]
    assert "公表されていない" in CFG["deadline_note"]


def test_next_session():
    s = next_session(CFG, datetime.date(2026, 9, 19))
    assert s and s["name"] == "令和8年11月定例会" and s["days_until"] == 55
    # 一覧の最後より後なら None（推測で延長しない）
    assert next_session(CFG, datetime.date(2027, 4, 1)) is None
