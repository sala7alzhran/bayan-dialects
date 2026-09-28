# Bayan dialect packs

Arabic dialect packs for the **Bayan (بيان)** keyboard: the everyday words of each dialect, how often they are used,
and what usually comes after them. The keyboard downloads a pack when you choose your dialect, so dialect
words are suggested and predicted, and are never "corrected" to standard Arabic.

حزم اللهجات العربية للوحة مفاتيح **بيان**: كلمات كل لهجة ومدى شيوعها وما يأتي بعدها عادةً. تُحمَّل الحزمة
عند اختيار لهجتك، فتُقترح كلمات اللهجة وتُتوقَّع ولا «تُصحَّح» إلى الفصحى.

| Pack | File | Sources | License |
|------|------|---------|---------|
| Gulf and Saudi (الخليجية والسعودية) | `packs/gulf.tsv` | Arabic Dialect Corpus | MIT |
| Egyptian (المصرية) | `packs/egyptian.tsv` | Arabic Dialect Corpus | MIT |
| Levantine (الشامية) | `packs/levantine.tsv` | Arabic Dialect Corpus, Shami Dialect Corpus | MIT and Apache License 2.0 |
| Iraqi (العراقية) | `packs/iraqi.tsv` | Arabic Dialect Corpus | MIT |
| Moroccan, Darija (المغربية) | `packs/moroccan.tsv` | Arabic Dialect Corpus, Moroccan Arabic Wikipedia | CC BY-SA 4.0 |

Every pack also contains a short core word list written for Bayan.

`packs.json` lists each pack with its size and SHA-256; the keyboard checks the hash of what it downloads.

## Sources

- **Arabic Dialect Corpus** by Dataflare, MIT License —
  https://huggingface.co/datasets/dataflare/arabic-dialect-corpus
- **Shami Dialect Corpus** by GU-CLASP, Apache License 2.0 — https://github.com/GU-CLASP/shami-corpus
- **Moroccan Arabic Wikipedia** (arywiki), text under CC BY-SA 4.0 — https://ary.wikipedia.org.
  Because the Moroccan pack contains data derived from it, that pack is shared under CC BY-SA 4.0.

The packs hold word counts and word pairs only, no sentences.

## Format

UTF-8 text. Lines starting with `#` are comments. After `#words`: `word<TAB>frequency[<TAB>c]` (frequency 1–255 on a
log scale; `c` marks a core word). After `#pairs`: `previous<TAB>next1 next2 …`.

## Rebuilding

`tools/build_packs.py <data dir> <main dictionary words tsv> <output dir>` (needs `pyarrow`). The data directory
holds the corpus parquet, the Shami text files and the arywiki dump.
