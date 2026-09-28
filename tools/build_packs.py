"""
Builds Bayan's Arabic dialect packs (ARCHITECTURE D99) from open data:

- Arabic Dialect Corpus, Dataflare, MIT License
  https://huggingface.co/datasets/dataflare/arabic-dialect-corpus  (Gulf, Egyptian, Iraqi, Levantine, Maghrebi)
- Shami Dialect Corpus, GU-CLASP, Apache License 2.0
  https://github.com/GU-CLASP/shami-corpus  (Syrian, Lebanese, Palestinian, Jordanian)
- Moroccan Arabic Wikipedia (arywiki), CC BY-SA 4.0
  https://ary.wikipedia.org  (Moroccan Darija)
- Core words per dialect written for Bayan (core_words.py).

Each pack holds word frequencies (1–255, the main dictionary's log scale) and next-word lists. Spellings the
main dictionary writes differently (hamza, ة/ه, ى/ي, which the corpora drop) are counted toward the dictionary
spelling, so a pack never teaches a spelling the Arabic spelling rules would correct.

Usage: python build_packs.py <data dir> <main dictionary words tsv> <output dir>
Needs pyarrow (for the corpus parquet).
"""
import bz2
import collections
import math
import os
import re
import sys

import pyarrow.parquet as pq

from core_words import CORE

MARKS = re.compile('[ً-ٰٟـ]')
WORD = re.compile('[ء-غف-يٱ]+')
FOLD = str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا'})

PACKS = {
    'gulf': {'corpus': ['Khaleeji'], 'extra': []},
    'egyptian': {'corpus': ['Masri'], 'extra': []},
    'levantine': {'corpus': ['Levantine'], 'extra': ['shami']},
    'iraqi': {'corpus': ['Iraqi'], 'extra': []},
    'moroccan': {'corpus': ['Maghrebi'], 'extra': ['arywiki']},
}
SOURCES = {
    'corpus': 'Arabic Dialect Corpus (Dataflare, MIT License)',
    'shami': 'Shami Dialect Corpus (GU-CLASP, Apache License 2.0)',
    'arywiki': 'Moroccan Arabic Wikipedia (CC BY-SA 4.0)',
}
MAX_WORDS = 15000
MIN_COUNT = 3
MAX_PAIR_WORDS = 8000
NEXTS = 4
MIN_PAIR = 2
# A dictionary hamza spelling replaces the corpus's bare alef when it is this much more common (log scale),
# the same gap the keyboard's spelling rules use (ArabicOrthography, HAMZA). Other differences (ة/ه, ى/ي) are
# settled when the pack is loaded: a pack word the dictionary spells differently is not added.
SPELLING_GAP = 18


def main_dictionary(path):
    words = {}
    for line in open(path, encoding='utf-8'):
        parts = line.rstrip('\n').split('\t')
        if len(parts) >= 2:
            words[parts[0]] = int(parts[1])
    by_fold = collections.defaultdict(list)
    for w, f in words.items():
        by_fold[w.translate(FOLD)].append((f, w))
    best = {k: max(v)[1] for k, v in by_fold.items()}
    return words, best


def canonical(word, words, best):
    """The dictionary's hamza spelling for a corpus word (أنا for انا, إلى for الى), else the word itself."""
    target = best.get(word.translate(FOLD))
    if target is None or target == word:
        return word
    own = words.get(word, 0)
    return target if words[target] - own >= SPELLING_GAP else word


def tokens(text):
    return WORD.findall(MARKS.sub('', text))


BOT_ARTICLE = ('لفاميلات', 'عدد السكان', 'نسبة لبطالة', 'إحصاء')
# Words of Wikipedia's own apparatus (references, calendars), not of the dialect.
WIKI_NOISE = {'مرجع', 'ويب', 'مصادر', 'تقويم', 'لميلاد', 'نمرة', 'عيون', 'لكاتب', 'لوصلة', 'وصلة', 'واصلة', 'لولوج', 'ولوج'}
DROP_LINKS = re.compile(r'\[\[(?:تصنيف|Category|ملف|File|صورة|Image):[^\]]*\]\]')


def wiki_text(path):
    """Plain article text from a Wikipedia XML dump (markup roughly removed, census bot pages skipped)."""
    in_text = False
    buf = []
    with bz2.open(path, 'rt', encoding='utf-8') as f:
        for line in f:
            if '<text' in line:
                in_text = True
                line = line[line.index('>') + 1:]
            if in_text:
                end = '</text>' in line
                if end:
                    line = line[:line.index('</text>')]
                line = DROP_LINKS.sub('', line)
                line = re.sub(r'\{\{[^}]*\}\}|\[\[(?:[^|\]]*\|)?([^\]]*)\]\]|<[^>]+>|&[a-z]+;|\[https?://\S+ ?([^\]]*)\]', r'\1\2', line)
                if not line.startswith(('{|', '|', '!', '#REDIRECT', '#تحويل', '[[', '*', '==')):
                    buf.append(' '.join(w for w in line.split() if w not in WIKI_NOISE))
                if end:
                    in_text = False
                    article = ' '.join(buf)
                    buf = []
                    if not any(marker in article for marker in BOT_ARTICLE):
                        yield article


def build(name, texts, words, best, out_dir):
    counts = collections.Counter()
    pairs = collections.defaultdict(collections.Counter)
    for text in texts:
        # Sentences, so pairs do not cross them.
        for sentence in re.split(r'[.!?؟\n،,؛:]+', text):
            previous = None
            for t in tokens(sentence):
                if t in WIKI_NOISE or (len(t) < 2 and t not in ('و', 'ب', 'ع', 'ف', 'ل')):
                    previous = None
                    continue
                w = canonical(t, words, best)
                counts[w] += 1
                if previous is not None:
                    pairs[previous][w] += 1
                previous = w
    for w in CORE[name]:
        counts[w] += max(counts.get(w, 0), 1) + 50
    top = [w for w, c in counts.most_common() if c >= MIN_COUNT][:MAX_WORDS]
    top_set = set(top)
    peak = counts[top[0]]
    lines = [f'# Bayan dialect pack: {name}', '# Built by tools/dialects/build_packs.py from:']
    for src in ['corpus'] + PACKS[name]['extra']:
        lines.append(f'#   {SOURCES[src]}')
    lines.append('#   Bayan core word list')
    if 'arywiki' in PACKS[name]['extra']:
        lines.append('# License of this pack: CC BY-SA 4.0 (it contains data derived from Wikipedia)')
    elif 'shami' in PACKS[name]['extra']:
        lines.append('# License of this pack: MIT and Apache License 2.0 (see the sources above)')
    else:
        lines.append('# License of this pack: MIT (see the source above)')
    lines.append('#words')
    for w in top:
        f = 60 + round(190 * math.log(counts[w] + 1) / math.log(peak + 1))
        if w in CORE[name]:
            lines.append(f'{w}\t{min(250, max(f, 200))}\tc')
        else:
            lines.append(f'{w}\t{min(250, f)}')
    lines.append('#pairs')
    heads = sorted((p for p in pairs if p in top_set), key=lambda p: -counts[p])[:MAX_PAIR_WORDS]
    for p in heads:
        nexts = [n for n, c in pairs[p].most_common(NEXTS * 2) if c >= MIN_PAIR and n in top_set][:NEXTS]
        if nexts:
            lines.append(f'{p}\t{" ".join(nexts)}')
    path = os.path.join(out_dir, f'{name}.tsv')
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
    print(name, len(top), 'words,', sum(1 for l in lines if '\t' in l) - len(top), 'pair lines,', os.path.getsize(path), 'bytes')


def main(data_dir, dict_path, out_dir):
    words, best = main_dictionary(dict_path)
    table = pq.read_table(os.path.join(data_dir, 'corpus.parquet'))
    dialects = table.column('dialect').to_pylist()
    texts = table.column('text').to_pylist()
    os.makedirs(out_dir, exist_ok=True)
    for name, spec in PACKS.items():
        chosen = [t for t, d in zip(texts, dialects) if d in spec['corpus']]
        if 'shami' in spec['extra']:
            for f in sorted(os.listdir(data_dir)):
                if f.startswith('shami_') and f.endswith('.txt'):
                    chosen += open(os.path.join(data_dir, f), encoding='utf-8', errors='ignore').read().splitlines()
        if 'arywiki' in spec['extra']:
            chosen += list(wiki_text(os.path.join(data_dir, 'arywiki.xml.bz2')))
        build(name, chosen, words, best, out_dir)


if __name__ == '__main__':
    main(*sys.argv[1:4])
