
# Datasets
  - because the story we're attempting to extract depends on accurately getting the raw story, decisions were made to 
  
    - clean rhe story corpora so that information loss would be minimal, 
    - reduce the size of the reference standard corpus (e.g. wikipedia) to a volume that could be processed into allotaxonometric representation within a tractable time without substantial loss of information.

  



# Downloaded Book Story wrangling

Source files in `books/` are downloaded `.txt` extractions and may contain layout junk, repeated headers, and mojibake.

## one-time raw book trimming

- On `2026-04-11`, a one-time manual pass trimmed the **raw** `books/*.txt` files to remove obvious frontmatter and backmatter before regeneration of `.cleaned.txt`, `1-gram`, and `2-gram` outputs.
- Principle:
  - keep the main argument / narrative text
  - keep core book introductions or prologues when they are part of the authored text
  - remove obvious publishing and navigation matter such as title pages, copyright pages, contents pages, acknowledgements, notes, references, bibliography, index, and publisher promo pages
- This pass was done on the raw `.txt` books, not on `.cleaned.txt`, so that regenerated cleaned texts continue to reflect source-level trimming rather than ad hoc edits to derived artifacts.
- `.cleaned.txt` remains useful as the canonical post-download, post-mojibake, pre-count artifact.
- Specific cut strategy used:
  - `How Compassion Made Us Human...txt`: start at `Prologue`, stop before `Notes`
  - `Sapiens.txt`: start at Chapter `1`, stop before `Notes`
  - `The Code Economy...txt`: start at `Introduction`, stop before `Acknowledgments`
  - `The Dawn of Everything...txt`: start at Chapter `1` / introductory opening, stop before `Notes`
  - `Ultrasociety...txt`: start at Chapter `1`, stop before `Acknowledgments`
- Deferred:
  - this is a one-time corpus cleanup, not yet a generalized scripted backmatter-removal rule
  - if more books are added later, revisit whether to formalize these cut rules in preprocessing

## Storywrangler rules

### pre-count
- Normalize common mojibake punctuation to simple ASCII equivalents before cleaning:
  - apostrophes like `Ã¢â‚¬â„¢` -> `'`
  - quotes like `Ã¢â‚¬Å“` / `Ã¢â‚¬Â` -> `"`
  - dashes like `Ã¢â‚¬â€œ` / `Ã¢â‚¬â€` -> `-`
  - ellipses like `Ã¢â‚¬Â¦` -> `...`
  - broken spaces like `Ã¢Â€Â‚` and non-breaking spaces -> normal spaces
- Keep punctuation only when it is inside a token:
  - keep `.` for `\w+\.\w+`
  - keep `,` for `\w+,\w+` including numbers like `40,000`
  - keep `-` for `\w+-\w+`
  - keep `'` for `\w+'\w+`
- Remove all other punctuation by replacing it with spaces.
- Preserve valid Unicode letters and diacritics that are already correct, such as `Delâge`, `Neuchâtel`, `Paléorient`, `Māori`.
- Remove repeated standalone title/header lines after the first kept occurrence when a title is explicitly provided to the cleaner.
- Remove obvious layout artifacts:
  - separator lines like `* * *`
  - isolated page-marker lines like roman numerals
  - isolated `Q` lines seen in extracted front matter
- Normalize whitespace after punctuation cleanup:


- remaining out of values treated in [OOV reconciliation](#oov)
  
### OOV
- the txt auto conversion downloaded from z-lib was mostly accurate, but some high-volume OOV tokens were leftover as line-break artifacts, lexical possessives, and similar token-shape issues
- examples from `zlib_stories_wrangled_but_oov.md` before reconciliation included: `produc-tion`, `algo-rithms`, `spe-cific`, `evolu-tion`, `im-provement`, `ad-vances`, `chap-ter`, `cre-ation`, `dig-ital`, `arti-ficial`, `ma-chines`, `learn-ing`, `de-pends`, `educa-tion`, `prog-ress`, `inno-vation`, `pub-lished`, `econ-omy`
- OOV reconciliation rules check that the OOV word, or its modified form, falls in wikipedia-lexicon:

  - if removing internal hyphenation yields a Wikipedia token, rewrite the cleaned story text to the joined form
  - if a dotted token is a word plus non-alphabetic note marker fragments such as `genes.6`, rewrite the cleaned story text to the lexical word
  - if a hyphenated compound is made of recognized lexical parts such as `non-egalitarian`, do not count it as OOV, but keep the text unchanged
  - if an apostrophe suffix such as `'s`, `n't`, `'d`, `'re`, `'ve`, `'ll`, or `'m` can be stripped to a recognized base token, do not count it as OOV, but keep the text unchanged
 
## Cleaning counted
  - until there's a principle to clean counted tokens from stories and wiki, leave ?

## 2-gram use for allotax

- For now, use the story 2-gram datasets in `2-gram/` as built, without an additional junk-bigram filter.
- Construction rule:
  - clean each book text first
  - tokenize the cleaned text
  - for each position `i`, count adjacent bigrams `(w[i], w[i+1])`
  - keep a bigram only when both tokens contain at least one alphabetic character
- Outputs:
  - one 2-gram CSV/JSON per cleaned book
  - one combined `humans-2grams` CSV/JSON built by summing bigram counts across all cleaned books
- Current decision:
  - use each story 2-gram dataset as input to py-allotax
  - compare each story against combined `humans-2grams`
- Deferred:
  - do not add URL / citation / note-fragment filtering yet
  - revisit junk-bigram filtering only after inspecting initial story-v-humans 2-gram allotax outputs



# Wikipedia

  Intended to be the opinionless reference standard which to compare the humans stories against, was sourced from an originally nearly 8M 1-gram corpus that was reduced to a size of 400K, about the maximum the author judged was computable by allotax within reasonable time.


## wikitext wrangling
 - use 103-raw-v1 as input to storywrangler
 - used raw so that all decisions to clean are transparent and can be equal for all corpora

### 2-gram builder

- Input:
  - start from the `text` field in `wikitext-103-raw-v1` parquet shards
  - use the raw subset rather than the non-raw subset so no `<unk>` replacement is introduced by the dataset
- Pre-count processing:
  - no additional `clean_text()` pass is applied before counting
  - parquet rows are streamed in batches rather than loading the entire dataset into memory at once
  - a small WikiText-specific raw normalization pass is applied before token counting:
    - rejoin `@-@` as `-`
    - rejoin `@,@` as `,`
    - rejoin `@.@` as `.`
  - rows are coerced to strings and tokenized on whitespace only
  - tokens are casefolded before counting
- Consistency with existing `storywrangler` rules:
  - reuse the shared `storywrangler` token counting functions for 1-grams and 2-grams
  - books and wiki now share the same pre-count token filter
  - count a unigram only when the token survives the shared token rules
  - count a bigram only when both adjacent tokens survive the same token rules
- Token-shape decisions:
  - a hyphenated word counts as one token only when WikiText already presents it as one whitespace token
  - standalone punctuation tokens are not counted because they fail the shared token rules
  - contraction-style apostrophe suffixes such as `'s`, `n't`, `'d`, `'re`, `'ve`, `'ll`, and `'m` are split off during counting
    - the lexical base token is kept
    - the apostrophe fragment is then dropped by the shared junk-token rules
    - bigrams are not bridged across the dropped apostrophe fragment
    - this intentionally equalizes books and wiki on contractions such as `it's -> it` and `we've -> we`
  - standalone apostrophe fragments such as `'s` are dropped before counting by the shared token rules
  - obvious web / domain / email-style tokens are filtered before counting
    - this includes bare `http`, `https`, and `www`
    - this also includes `http://...`, `https://...`, `www.*`, tokens with `@`, and common web-domain suffixes such as `.com`, `.org`, `.net`
  - isolated single-letter junk is filtered before counting
    - keep lexical `a` and `i`
    - drop citation-style residue such as `j`
  - obvious note / citation marker tokens are filtered before counting
    - examples include `s70`, `p355`, and note-like shapes such as `546n55`
  - historical numeric lexical tokens such as `19th`, `20th`, or `1960s` are not treated as junk by this filter
- Bigram boundary decision:
  - bigrams are counted only within each parquet row
  - no bigrams are formed across parquet row boundaries
  - junk tokens act as hard boundaries for bigram counting
    - if either side of an adjacent pair is junk, that pair is skipped and no bigram is bridged across the junk token
- Post-count filtering:
  - optional `--min-count` is applied after counting
- Output:
  - default 1-gram output path is `1-gram/wikitext-103-raw-v1-1grams.csv`
  - default 2-gram output path is `2-gram/wikitext-103-raw-v1-2grams.csv`
  - parquet output is supported when requested
  - parquet output stores only `types` and `counts` to keep the file smaller; `probs` and `total_unique` can be derived later if needed
  - exploratory laptop-friendly build choice:
    - use `wikitext-2-raw-v1` for quick 2-gram builds
    - store the result as parquet rather than csv
    - current artifact: `2-gram/wikitext-2-raw-v1-2grams.parquet`
- Deferred:
  - no special cleanup yet for WikiText-specific heading markers beyond the `@-@` / `@,@` / `@.@` join pass
  - no post-count junk filter beyond `min-count`
  - no attempt yet to force WikiText tokenization to match the downloaded-book cleaner exactly

### preferred unification direction

- Principle:
  - if the source corpus is available as raw text, make as many lexical filtering decisions as possible **before counting**
  - use the same token-level decisions for books and wiki whenever the issue is not corpus-specific
- Shared token-level decisions should feed both 1-grams and 2-grams:
  - 1-gram: count a token only if it survives the shared pre-count token rules
  - 2-gram: count `(w[i], w[i+1])` only if both tokens survive the same 1-gram rules
  - this keeps 2-gram logic simple and makes the 2-gram rules mostly "1-gram rules + adjacency"
- Corpus-specific pre-cleaning can still differ:
  - books need mojibake, layout, and likely bibliography / backmatter cleanup
  - wiki may need cleanup of WikiText artifacts such as `@-@`, `@,@`, and heading markers
- Post-count filtering should stay minimal:
  - good uses: `min-count`, diagnostics, or sanity-check reports
  - poor use: lexical cleanup that could have been decided from the raw token stream earlier

### consequence for current junk examples

- `http`, `https`, `pp`, `s70`:
  - these are best treated as token-level junk and removed **pre-count**
- `j`:
  - as seen in story outputs, this is usually a citation / initials residue rather than meaningful lexical content
  - best handled by a pre-count rule such as dropping isolated single-letter tokens other than truly lexical cases like `a` and `i`
- `cambridge university`:
  - this is **not** a unigram rule
  - do not solve it by banning `cambridge` or `university` individually
  - better options:
    - remove bibliography / reference backmatter earlier in the book cleaner
    - or skip known junk bigrams before incrementing the 2-gram count

### current recommendation

- For future harmonized book/wiki counting:
  - move token-level junk decisions into shared pre-count rules
  - keep the same shared token rules for both 1-gram and 2-gram counting
  - reserve separate book-only and wiki-only cleanup for corpus-specific artifacts
  - reserve post-count decisions mostly for thresholds and audits, not for ordinary lexical cleanup

## allotax todo
  - remove "cambridge university", http, j, pp, s70

# Results


 - how different can these humans stories be?
  - how do we answer 'how the same'?
