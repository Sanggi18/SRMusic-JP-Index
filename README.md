# SRMusic Kanji Index

Full Joyo kanji reading index + lyric-aware pre-reading overrides, for the
SRMusic Android app. The app fetches these files online at runtime instead of
bundling a dictionary in the APK.

## Files

| File | Size | Contents |
|---|---|---|
| `kanji.json` | ~402 KB | 2136 Joyo kanji (grade 1–8), sorted by grade then stroke count |
| `lyric_overrides.json` | ~2.6 KB | 23 lyric/jukujikun pre-reading overrides |
| `build_index.py` | — | Reproducible build script (KANJIDIC2 → `kanji.json`) |
| `kanjidic2.xml.gz` | ~1.5 MB | Source data, kept for reproducibility |

## `kanji.json` — entry format

```json
{"kanji": "日", "on": ["ニチ", "ジツ"], "kun": ["ひ", "-び", "-か"],
 "on_romaji": ["nichi", "jitsu"], "kun_romaji": ["hi", "bi", "ka"],
 "grade": 1, "strokes": 4, "meanings": ["day", "sun", "Japan", "counter for days"]}
```

- `on` / `kun`: readings exactly as in KANJIDIC2 (katakana / hiragana).
  KANJIDIC2 marks okurigana boundaries with `.` (e.g. `ひら.く`) and bound
  morphemes with `-` (e.g. `-び`); both are kept verbatim in the kana fields.
- `on_romaji` / `kun_romaji`: Hepburn romaji, long vowels written doubled
  (not macron): `ゆうべ` → `yuube`, `きょう` → `kyou`, `とうきょう` →
  `toukyou`. Digraphs (`しゃ` → `sha`), sokuon doubles the next consonant
  (`がっこう` → `gakkou`), `ん` → `n`.
- `grade`: KANJIDIC2 grade. 1–6 = kyouiku (1026 kanji), 8 = remaining Joyo
  (1110 kanji). Total 2136. Grades 9–10 (jinmeiyo / variants, 863 kanji)
  are excluded.
- `meanings`: English meanings only (entries without a language attribute
  in KANJIDIC2).

## `lyric_overrides.json` — entry format

```json
{"word": "昨夜", "reading": "ゆうべ", "romaji": "yuube", "source": "issue"}
```

Per-character kanji readings cannot solve lyric readings: 昨夜 is `サク`
+ `ヤ` per kanji (hence Google Translate's wrong `sakuya`), but in lyrics
it is read `ゆうべ` (yuube). These whole-word overrides are applied
**before** the online romanisation request (longest word first), so both
the displayed text (kanji stays as-is) and the furigana come out right.
`source` is `"issue"` (from the SRMusic issue report) or `"common"`
(very standard jukujikun). 明日 carries an extra `variants` entry
(`あした` / `ashita`, the common spoken reading vs lyric `あす` / `asu`).

## Fetching from the app

Once this repo exists on GitHub (e.g. `Sanggi18/srmusic-kanji-index`,
branch `main`), the app fetches the raw files — no API key, no auth:

```
https://raw.githubusercontent.com/Sanggi18/srmusic-kanji-index/main/kanji.json
https://raw.githubusercontent.com/Sanggi18/srmusic-kanji-index/main/lyric_overrides.json
```

Cache on device (24 h) and fall back to the bundled kana-only converter
when offline.

## Adding overrides

Append an entry to `lyric_overrides.json` (keep the list sorted by word
length descending, then alphabetically — the app greedy-matches longest
first). Verify the romaji with the converter in `build_index.py`
(`kana_to_romaji`) so it stays consistent with the app's convention.

## Rebuilding

```sh
python3 build_index.py
```

Requires `kanjidic2.xml.gz` in this directory (download from
https://www.edrdg.org/kanjidic/kanjidic2.xml.gz). The script asserts the
romaji test cases, the 2136 count, no duplicate kanji, and valid JSON.

## Limitations (honest)

- Per-kanji readings do not resolve sentence context: a kanji can have
  several valid readings and only the surrounding word (via overrides) or
  a dictionary lookup picks the right one. Compounds not in
  `lyric_overrides.json` fall back to per-kanji readings and may still be
  wrong (e.g. rare name readings).
- Some KANJIDIC2 readings are rare/archaic (e.g. `お-`, `-び` bound forms);
  they are kept verbatim for completeness.
- KANJIDIC2 does not cover readings outside the Joyo set (grade 9–10
  jinmeiyo kanji are not in `kanji.json`).

## License / attribution

KANJIDIC2 data © Electronic Dictionary Research and Development Group
(EDRDG), licensed CC BY-SA. See `NOTICE.md`.
