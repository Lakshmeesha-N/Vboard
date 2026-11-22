"""Build Vboard words_en.txt: core-100 + 12dicts bands, ~20k words. Stdlib only."""
import os

DATA = "C:/Users/laksh/Desktop/scowl/wordlist-1/wordlist-1/alt12dicts"
OUT = "C:/Users/laksh/Desktop/Vboard/Vboard-android/app/src/main/assets/words_en.txt"
TARGET = 20000

CORE = ("the of and a to in is you that it he was for on are as with his they i "
        "at be this have from or one had by word but not what all were we when your "
        "can said there use an each which she do how their if will up other about "
        "out many then them these so some her would make like him into time has "
        "look two more write go see number no way could people my than first water "
        "been call who oil its now find long down day did get come made may part").split()


def clean(token):
    t = token.strip()
    if not t or any(c.isupper() for c in t):
        return ""
    t = t.lower().strip("'")
    if not t or any(not ("a" <= c <= "z" or c == "'") for c in t):
        return ""
    if len(t) == 1 and t not in ("a", "i"):
        return ""
    return t


def load_band(name):
    raw = 0
    seen, order = set(), []
    with open(DATA + "/" + name, encoding="latin-1") as f:
        for line in f:
            raw += 1
            w = clean(line)
            if w and w not in seen:
                seen.add(w)
                order.append(w)
    return raw, order


ranked, used = [], set()
for w in CORE:
    if w not in used:
        used.add(w)
        ranked.append(w)
print("core: kept %d of %d" % (len(ranked), len(CORE)))

for name in ("3esl.txt", "2of4brif.txt", "2of12full.txt"):
    if len(ranked) >= TARGET:
        print("%s: skipped (target reached)" % name)
        continue
    raw, words = load_band(name)
    fresh = sorted(w for w in words if w not in used)
    added = 0
    for w in fresh:
        if len(ranked) >= TARGET:
            break
        used.add(w)
        ranked.append(w)
        added += 1
    print("%s: raw=%d kept-after-clean=%d new-added=%d" % (name, raw, len(words), added))

header = """# words_en.txt - English suggestion word list for Vboard.
# Format: word<TAB>rank, rank 1 = most common. Order: hand-ordered core-100,
# then 12dicts 3esl, 2of4brif, 2of12full, alphabetical inside each band.
# Filter: lowercase a-z + apostrophe only, no abbreviations,
# no single letters except a/i.
# Sources: 12dicts (Alan Beale) + SCOWL/ESDB (Kevin Atkinson).
# 12dicts license: "The 12dicts lists were compiled by Alan Beale. I explicitly
# release them to the public domain, but request acknowledgment of their use."
# SCOWL license: "Copyright 2000-2018 by Kevin Atkinson. Permission to use, copy,
# modify, distribute and sell these word lists, the associated scripts, the
# output created from the scripts, and its documentation for any purpose is
# hereby granted without fee, provided that the above copyright notice appears
# in all copies and that both that copyright notice and this permission notice
# appear in supporting documentation."
"""

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(header)
    for i, w in enumerate(ranked, 1):
        f.write("%s\t%d\n" % (w, i))

size = os.path.getsize(OUT)
print("TOTAL words=%d file-bytes=%d" % (len(ranked), size))
pos = {w: i + 1 for i, w in enumerate(ranked)}
for w in ("the", "that", "then", "zebra", "don't", "quixotic"):
    print("rank(%s)=%s" % (w, pos.get(w, "absent")))
print("first5=%s" % ranked[:5])
print("last5=%s" % ranked[-5:])