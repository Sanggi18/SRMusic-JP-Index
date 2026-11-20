#!/usr/bin/env python3
"""Build the SRMusic kanji index from KANJIDIC2 (EDRDG, CC BY-SA).

Outputs (in this directory):
  kanji.json           - 2136 Joyo kanji (grade 1-8) with on/kun readings + romaji
  lyric_overrides.json - lyric-aware pre-reading dictionary (jukujikun / special readings)
  README.md, NOTICE.md - docs + attribution

Romaji convention (matches SRMusic app):
  Hepburn, long vowels written doubled (not macron): yuube, kyou, toukyou.
  Digraphs: kya/sha/cha..., sokuon っ doubles the next consonant: gakkou.
  ん -> n (simple, deterministic).
"""
import gzip
import json
import random
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
KANJIDIC_GZ = HERE / "kanjidic2.xml.gz"
KANJI_JSON = HERE / "kanji.json"
OVERRIDES_JSON = HERE / "lyric_overrides.json"

# ---------------------------------------------------------------------------
# Kana -> romaji (Hepburn, long vowels doubled)
# ---------------------------------------------------------------------------
_HIRA_SINGLE = {
    "あ": "a", "い": "i", "う": "u", "え": "e", "お": "o",
    "か": "ka", "き": "ki", "く": "ku", "け": "ke", "こ": "ko",
    "さ": "sa", "し": "shi", "す": "su", "せ": "se", "そ": "so",
    "た": "ta", "ち": "chi", "つ": "tsu", "て": "te", "と": "to",
    "な": "na", "に": "ni", "ぬ": "nu", "ね": "ne", "の": "no",
    "は": "ha", "ひ": "hi", "ふ": "fu", "へ": "he", "ほ": "ho",
    "ま": "ma", "み": "mi", "む": "mu", "め": "me", "も": "mo",
    "や": "ya", "ゆ": "yu", "よ": "yo",
    "ら": "ra", "り": "ri", "る": "ru", "れ": "re", "ろ": "ro",
    "わ": "wa", "ゐ": "wi", "ゑ": "we", "を": "wo",
    "が": "ga", "ぎ": "gi", "ぐ": "gu", "げ": "ge", "ご": "go",
    "ざ": "za", "じ": "ji", "ず": "zu", "ぜ": "ze", "ぞ": "zo",
    "だ": "da", "ぢ": "ji", "づ": "zu", "で": "de", "ど": "do",
    "ば": "ba", "び": "bi", "ぶ": "bu", "べ": "be", "ぼ": "bo",
    "ぱ": "pa", "ぴ": "pi", "ぷ": "pu", "ぺ": "pe", "ぽ": "po",
    "ん": "n",
    "ぁ": "a", "ぃ": "i", "ぅ": "u", "ぇ": "e", "ぉ": "o",
    "ゃ": "ya", "ゅ": "yu", "ょ": "yo",
    "ゔ": "vu",
}
_KATA_SINGLE = {
    "ア": "a", "イ": "i", "ウ": "u", "エ": "e", "オ": "o",
    "カ": "ka", "キ": "ki", "ク": "ku", "ケ": "ke", "コ": "ko",
    "サ": "sa", "シ": "shi", "ス": "su", "セ": "se", "ソ": "so",
    "タ": "ta", "チ": "chi", "ツ": "tsu", "テ": "te", "ト": "to",
    "ナ": "na", "ニ": "ni", "ヌ": "nu", "ネ": "ne", "ノ": "no",
    "ハ": "ha", "ヒ": "hi", "フ": "fu", "ヘ": "he", "ホ": "ho",
    "マ": "ma", "ミ": "mi", "ム": "mu", "メ": "me", "モ": "mo",
    "ヤ": "ya", "ユ": "yu", "ヨ": "yo",
    "ラ": "ra", "リ": "ri", "ル": "ru", "レ": "re", "ロ": "ro",
    "ワ": "wa", "ヰ": "wi", "ヱ": "we", "ヲ": "wo",
    "ガ": "ga", "ギ": "gi", "グ": "gu", "ゲ": "ge", "ゴ": "go",
    "ザ": "za", "ジ": "ji", "ズ": "zu", "ゼ": "ze", "ゾ": "zo",
    "ダ": "da", "ヂ": "ji", "ヅ": "zu", "デ": "de", "ド": "do",
    "バ": "ba", "ビ": "bi", "ブ": "bu", "ベ": "be", "ボ": "bo",
    "パ": "pa", "ピ": "pi", "プ": "pu", "ペ": "pe", "ポ": "po",
    "ン": "n",
    "ァ": "a", "ィ": "i", "ゥ": "u", "ェ": "e", "ォ": "o",
    "ャ": "ya", "ュ": "yu", "ョ": "yo",
    "ヴ": "vu",
}
# consonant + small ya/yu/yo -> digraph romaji
_DIGRAPH_BASE = {
    "き": "ky", "ぎ": "gy", "し": "sh", "じ": "j", "ち": "ch", "ぢ": "j",
    "に": "ny", "ひ": "hy", "び": "by", "ぴ": "py", "み": "my", "り": "ry",
    "キ": "ky", "ギ": "gy", "シ": "sh", "ジ": "j", "チ": "ch", "ヂ": "j",
    "ニ": "ny", "ヒ": "hy", "ビ": "by", "ピ": "py", "ミ": "my", "リ": "ry",
}
_SMALL_Y = {"ゃ": "a", "ゅ": "u", "ょ": "o", "ャ": "a", "ュ": "u", "ョ": "o"}
_SOKUON = {"っ", "ッ"}
_CHOUON = {"ー"}
_SKIP = {".", "-", "・", " ", "　"}


def kana_to_romaji(text: str) -> str:
    """Hepburn romaji, long vowels doubled. Input: hiragana or katakana."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in _SKIP:
            i += 1
            continue
        if c in _SOKUON:
            # double the first consonant of the next mora's romaji
            nxt = kana_to_romaji(text[i + 1:]) if i + 1 < n else ""
            if nxt and nxt[0] not in "aeiou":
                out.append(nxt[0])
            # if next mora starts with a vowel there is no consonant to double
            i += 1
            continue
        if c in _CHOUON:
            # repeat the last vowel
            if out:
                last = out[-1]
                for ch in reversed(last):
                    if ch in "aeiou":
                        out.append(ch)
                        break
            i += 1
            continue
        if c in _DIGRAPH_BASE and i + 1 < n and text[i + 1] in _SMALL_Y:
            out.append(_DIGRAPH_BASE[c] + _SMALL_Y[text[i + 1]])
            i += 2
            continue
        table = _HIRA_SINGLE if c in _HIRA_SINGLE else _KATA_SINGLE
        roma = table.get(c)
        if roma is None:
            # unknown char: keep it visible so anomalies are detectable
            out.append("?")
        else:
            out.append(roma)
        i += 1
    return "".join(out)


ROMAJI_TESTS = [
    ("ゆうべ", "yuube"), ("ふたり", "futari"), ("にどめ", "nidome"),
    ("おとな", "otona"), ("あなた", "anata"), ("きょう", "kyou"),
    ("とうきょう", "toukyou"), ("がっこう", "gakkou"), ("しゃ", "sha"),
    ("きゃ", "kya"), ("ほんとう", "hontou"), ("だいじょうぶ", "daijoubu"),
    ("ニチ", "nichi"), ("ジツ", "jitsu"), ("がくせい", "gakusei"),
    ("しんぶん", "shinbun"), ("ちょっと", "chotto"), ("さびしさ", "sabishisa"),
]


def dedupe(seq):
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


# ---------------------------------------------------------------------------
# KANJIDIC2 parsing
# ---------------------------------------------------------------------------
def parse_kanjidic():
    with gzip.open(KANJIDIC_GZ, "rb") as f:
        tree = ET.parse(f)
    root = tree.getroot()
    grade_counts = {}
    entries = []
    no_reading = []
    for ch in root.findall("character"):
        literal_el = ch.find("literal")
        if literal_el is None or not literal_el.text:
            continue
        literal = literal_el.text.strip()
        misc = ch.find("misc")
        grade_el = misc.find("grade") if misc is not None else None
        grade = int(grade_el.text) if grade_el is not None and grade_el.text else None
        strokes_el = misc.find("stroke_count") if misc is not None else None
        strokes = int(strokes_el.text) if strokes_el is not None and strokes_el.text else None
        if grade is not None:
            grade_counts[grade] = grade_counts.get(grade, 0) + 1
        if grade is None or grade < 1 or grade > 8:
            continue  # Joyo only: grades 1-6 (kyouiku) + 8 (joyo secondary)
        on, kun, meanings = [], [], []
        for rm in ch.findall("reading_meaning/rmgroup"):
            for r in rm.findall("reading"):
                rtype = r.get("r_type")
                if r.text is None:
                    continue
                val = r.text.strip()
                if rtype == "ja_on":
                    on.append(val)
                elif rtype == "ja_kun":
                    kun.append(val)
            for m in rm.findall("meaning"):
                if m.get("m_lang") is None and m.text and m.text.strip():
                    meanings.append(m.text.strip())
        on = dedupe(on)
        kun = dedupe(kun)
        meanings = dedupe(meanings)
        if not on and not kun:
            no_reading.append(literal)
            continue
        entries.append({
            "kanji": literal,
            "on": on,
            "kun": kun,
            "on_romaji": [kana_to_romaji(r) for r in on],
            "kun_romaji": [kana_to_romaji(r) for r in kun],
            "grade": grade,
            "strokes": strokes,
            "meanings": meanings,
        })
    entries.sort(key=lambda e: (e["grade"], e["strokes"] if e["strokes"] is not None else 99, e["kanji"]))
    return entries, grade_counts, no_reading


# ---------------------------------------------------------------------------
# Lyric overrides (from the user's issue + a few very standard jukujikun)
# ---------------------------------------------------------------------------
def build_overrides():
    def o(word, reading, romaji, source, **kw):
        d = {"word": word, "reading": reading, "romaji": romaji, "source": source}
        d.update(kw)
        return d

    items = [
        o("昨夜", "ゆうべ", "yuube", "issue"),
        o("二人", "ふたり", "futari", "issue"),
        o("一人", "ひとり", "hitori", "issue"),
        o("二度目", "にどめ", "nidome", "issue"),
        o("一度", "いちど", "ichido", "issue"),
        o("二度", "にど", "nido", "issue"),
        o("三度", "さんど", "sando", "issue"),
        o("大人", "おとな", "otona", "issue"),
        o("貴方", "あなた", "anata", "issue"),
        o("今日", "きょう", "kyou", "issue"),
        o("明日", "あす", "asu", "issue",
          variants=[{"reading": "あした", "romaji": "ashita"}],
          note="あす is the formal/lyric reading; あした is the common spoken reading"),
        o("昨日", "きのう", "kinou", "issue"),
        o("真夜中", "まよなか", "mayonaka", "issue"),
        o("思い出", "おもいで", "omoide", "issue"),
        o("言葉", "ことば", "kotoba", "issue"),
        o("淋しさ", "さびしさ", "sabishisa", "issue"),
        o("寂しさ", "さびしさ", "sabishisa", "issue"),
        o("大丈夫", "だいじょうぶ", "daijoubu", "issue"),
        o("本当", "ほんとう", "hontou", "issue"),
        o("彼女", "かのじょ", "kanojo", "common"),
        o("彼", "かれ", "kare", "common"),
        o("今", "いま", "ima", "common"),
        o("何", "なに", "nani", "common"),
    ]
    # longest word first so the app can greedy-match
    items.sort(key=lambda d: (-len(d["word"]), d["word"]))
    return items


def main():
    # 1. converter self-test (must pass before mass use)
    for kana, want in ROMAJI_TESTS:
        got = kana_to_romaji(kana)
        assert got == want, f"romaji {kana}: got {got}, want {want}"
    print(f"romaji converter: {len(ROMAJI_TESTS)} tests OK")

    # 2. parse KANJIDIC2
    entries, grade_counts, no_reading = parse_kanjidic()
    print(f"grade distribution in KANJIDIC2: {dict(sorted(grade_counts.items()))}")
    if no_reading:
        print(f"WARNING: {len(no_reading)} joyo kanji without readings, excluded: {no_reading}")
    print(f"joyo entries (grade 1-8): {len(entries)}")
    seen = set()
    dups = [e["kanji"] for e in entries if e["kanji"] in seen or seen.add(e["kanji"])]
    assert not dups, f"duplicate kanji: {dups}"
    for e in entries:
        assert e["on"] or e["kun"], f"no reading: {e['kanji']}"
        assert "?" not in "".join(e["on_romaji"] + e["kun_romaji"]), f"unmapped kana in {e['kanji']}"

    # 3. write kanji.json (one entry per line, compact)
    with open(KANJI_JSON, "w", encoding="utf-8") as f:
        f.write("[\n")
        for i, e in enumerate(entries):
            f.write(json.dumps(e, ensure_ascii=False, separators=(",", ":")))
            f.write(",\n" if i < len(entries) - 1 else "\n")
        f.write("]\n")

    # 4. write lyric_overrides.json
    overrides = build_overrides()
    for ov in overrides:
        assert kana_to_romaji(ov["reading"]) == ov["romaji"], f"override romaji mismatch: {ov}"
        for v in ov.get("variants", []):
            assert kana_to_romaji(v["reading"]) == v["romaji"], f"variant romaji mismatch: {ov}"
    with open(OVERRIDES_JSON, "w", encoding="utf-8") as f:
        json.dump(overrides, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # 5. verify outputs
    with open(KANJI_JSON, encoding="utf-8") as f:
        back = json.load(f)
    assert len(back) == len(entries)
    with open(OVERRIDES_JSON, encoding="utf-8") as f:
        back_ov = json.load(f)
    assert len(back_ov) == len(overrides)

    # spot-check 20 random kanji
    rng = random.Random(20261120)
    sample = rng.sample(back, 20)
    print("\nspot-check 20 random kanji:")
    for e in sample:
        print(f"  {e['kanji']} g{e['grade']} s{e['strokes']} on={e['on']}->{e['on_romaji']} "
              f"kun={e['kun']}->{e['kun_romaji']} meanings={e['meanings'][:3]}")

    print(f"\nkanji.json: {len(back)} entries, {KANJI_JSON.stat().st_size/1024:.1f} KB")
    print(f"lyric_overrides.json: {len(back_ov)} entries, {OVERRIDES_JSON.stat().st_size/1024:.1f} KB")
    print("BUILD OK")


if __name__ == "__main__":
    main()
