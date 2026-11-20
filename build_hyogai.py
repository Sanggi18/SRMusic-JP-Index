#!/usr/bin/env python3
"""Build the SRMusic hyogai (non-Joyo) kanji supplement from KANJIDIC2.

Outputs (in this directory):
  hyogai.json - non-Joyo kanji that still show up in J-pop lyrics:
    * ALL grade 9 (jinmeiyo / name kanji)
    * ALL grade 10 (variants)
    * curated ungraded hyogai common in lyrics (e.g. 淋, 噂, 凛, 唄)

Format is the same as kanji.json, plus "hyogai": true on every entry.
Romaji reuses kana_to_romaji() from build_index.py (Hepburn, long vowels
doubled: yuube, kyou, toukyou; sokuon doubles the next consonant).

Does NOT touch kanji.json / lyric_overrides.json / build_index.py.
"""
import gzip
import json
import random
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_index import kana_to_romaji, dedupe, ROMAJI_TESTS  # noqa: E402

KANJIDIC_GZ = HERE / "kanjidic2.xml.gz"
KANJI_JSON = HERE / "kanji.json"
HYOGAI_JSON = HERE / "hyogai.json"

# Curated ungraded hyogai (no grade in KANJIDIC2) common in J-pop lyrics.
# Only entries that exist in KANJIDIC2 with at least one reading are kept;
# anything missing is reported and skipped (never invented).
CURATED_UNGRADED = [
    "淋", "噂", "凛", "唄", "嘘", "匂", "凪", "刹", "澪", "遙",
    "逢", "檎", "囁", "呟", "洒", "遼", "麓", "勿", "雁", "贖",
    "辿", "頬", "唇", "涙", "嵐", "霞", "雫", "耀", "曖", "昧",
    "淫", "惹", "捉", "掴", "掬", "捏", "捻", "揉", "撫", "漸",
    "狭", "弄", "乖", "亦", "乃", "之", "乎", "也", "哉",
]


def parse_hyogai(joyo_set):
    """Return (entries, counts, skipped_curated, skipped_no_reading)."""
    with gzip.open(KANJIDIC_GZ, "rb") as f:
        tree = ET.parse(f)
    root = tree.getroot()

    by_literal = {}
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
        by_literal[literal] = {
            "kanji": literal,
            "on": dedupe(on),
            "kun": dedupe(kun),
            "grade": grade,
            "strokes": strokes,
            "meanings": dedupe(meanings),
        }

    def make_entry(raw):
        return {
            "kanji": raw["kanji"],
            "on": raw["on"],
            "kun": raw["kun"],
            "on_romaji": [kana_to_romaji(r) for r in raw["on"]],
            "kun_romaji": [kana_to_romaji(r) for r in raw["kun"]],
            "grade": raw["grade"],
            "strokes": raw["strokes"],
            "meanings": raw["meanings"],
            "hyogai": True,
        }

    entries = []
    counts = {"grade9": 0, "grade10": 0, "ungraded": 0}
    skipped_no_reading = []
    for raw in by_literal.values():
        grade = raw["grade"]
        if grade not in (9, 10):
            continue
        if raw["kanji"] in joyo_set:
            continue  # must never overlap kanji.json
        if not raw["on"] and not raw["kun"]:
            skipped_no_reading.append(raw["kanji"])
            continue
        entries.append(make_entry(raw))
        counts["grade9" if grade == 9 else "grade10"] += 1

    # Curated ungraded: only if present in KANJIDIC2, not Joyo, has a reading.
    skipped_curated = []
    for literal in dedupe(CURATED_UNGRADED):
        raw = by_literal.get(literal)
        if raw is None:
            skipped_curated.append((literal, "not in KANJIDIC2"))
            continue
        if literal in joyo_set:
            skipped_curated.append((literal, "already in kanji.json (Joyo)"))
            continue
        if raw["grade"] in (9, 10):
            skipped_curated.append((literal, f"already included as grade {raw['grade']}"))
            continue
        if not raw["on"] and not raw["kun"]:
            skipped_curated.append((literal, "no readings in KANJIDIC2"))
            continue
        entries.append(make_entry(raw))
        counts["ungraded"] += 1

    # Order: grade 9, then 10, then ungraded (grade None); strokes, then kanji.
    def sort_key(e):
        g = e["grade"]
        group = 0 if g == 9 else 1 if g == 10 else 2
        return (group, e["strokes"] if e["strokes"] is not None else 99, e["kanji"])

    entries.sort(key=sort_key)
    return entries, counts, skipped_curated, skipped_no_reading


def main():
    # 1. converter self-test (same as build_index.py)
    for kana, want in ROMAJI_TESTS:
        got = kana_to_romaji(kana)
        assert got == want, f"romaji {kana}: got {got}, want {want}"
    print(f"romaji converter: {len(ROMAJI_TESTS)} tests OK")

    # 2. load Joyo set (overlap guard)
    with open(KANJI_JSON, encoding="utf-8") as f:
        joyo = json.load(f)
    joyo_set = {e["kanji"] for e in joyo}
    print(f"kanji.json (Joyo): {len(joyo_set)} kanji loaded")

    # 3. build hyogai entries
    entries, counts, skipped_curated, skipped_no_reading = parse_hyogai(joyo_set)
    print(f"hyogai breakdown: grade 9={counts['grade9']}, "
          f"grade 10={counts['grade10']}, ungraded curated={counts['ungraded']}, "
          f"total={len(entries)}")
    if skipped_no_reading:
        print(f"WARNING: grade 9/10 without readings, excluded: {skipped_no_reading}")
    if skipped_curated:
        print("curated kanji skipped:")
        for lit, why in skipped_curated:
            print(f"  {lit}: {why}")

    # 4. assertions
    seen = set()
    dups = [e["kanji"] for e in entries if e["kanji"] in seen or seen.add(e["kanji"])]
    assert not dups, f"duplicate kanji: {dups}"
    overlap = [e["kanji"] for e in entries if e["kanji"] in joyo_set]
    assert not overlap, f"overlap with kanji.json: {overlap}"
    for e in entries:
        assert e["on"] or e["kun"], f"no reading: {e['kanji']}"
        assert e["hyogai"] is True
        assert "?" not in "".join(e["on_romaji"] + e["kun_romaji"]), \
            f"unmapped kana in {e['kanji']}"
    print("assertions OK: no duplicates, zero overlap with kanji.json, "
          "every entry has >=1 reading, all romaji mapped")

    # 5. write hyogai.json (one entry per line, compact — same as kanji.json)
    with open(HYOGAI_JSON, "w", encoding="utf-8") as f:
        f.write("[\n")
        for i, e in enumerate(entries):
            f.write(json.dumps(e, ensure_ascii=False, separators=(",", ":")))
            f.write(",\n" if i < len(entries) - 1 else "\n")
        f.write("]\n")

    # 6. verify output by reloading
    with open(HYOGAI_JSON, encoding="utf-8") as f:
        back = json.load(f)
    assert len(back) == len(entries)

    # spot-check: the three kanji the user confirmed + 7 random
    by_kanji = {e["kanji"]: e for e in back}
    print("\nspot-check (required):")
    for k in ["淋", "噂", "凛"]:
        e = by_kanji.get(k)
        assert e is not None, f"missing required kanji: {k}"
        print(f"  {k} g{e['grade']} s{e['strokes']} on={e['on']}->{e['on_romaji']} "
              f"kun={e['kun']}->{e['kun_romaji']} meanings={e['meanings'][:3]}")
    rng = random.Random(20261120)
    print("spot-check (7 random):")
    for e in rng.sample(back, 7):
        print(f"  {e['kanji']} g{e['grade']} s{e['strokes']} on={e['on']}->{e['on_romaji']} "
              f"kun={e['kun']}->{e['kun_romaji']} meanings={e['meanings'][:3]}")

    print(f"\nhyogai.json: {len(back)} entries, {HYOGAI_JSON.stat().st_size/1024:.1f} KB")
    print("BUILD OK")


if __name__ == "__main__":
    main()
