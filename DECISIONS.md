
# Datasets
  - because the story we're attempting to extract depends on accurately getting the raw story, decisions were made to 
  
    - clean rhe story corpora so that information loss would be minimal, 
    - reduce the size of the reference standard corpus (e.g. wikipedia) to a volume that could be processed into allotaxonometric representation within a tractable time without substantial loss of information.

  



# Downloaded Book Story wrangling

Source files in `books/` are downloaded `.txt` extractions and may contain layout junk, repeated headers, and mojibake.

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
- Meaning of `.decisions` in current output names:
  - `wikitext-103-raw-v1-1grams.decisions.csv` does **not** mean "all junk and citation residue removed"
  - in the current code, `.decisions` means:
    - build counts from raw WikiText text with a small pre-count junk-token filter
    - then apply a narrow post-count filter for punctuation/apostrophe-fragment cleanup
  - therefore the current `.decisions` file can still contain tokens such as `j`, `pp`, `s70`, and even bare `http`
- Pre-count processing:
  - no additional `clean_text()` pass is applied before counting
  - parquet rows are streamed in batches rather than loading the entire dataset into memory at once
  - rows are coerced to strings and tokenized on whitespace only
  - tokens are casefolded before counting
- Consistency with existing `storywrangler` rules:
  - reuse the shared `storywrangler` token counting functions for 1-grams and 2-grams
  - count a unigram only when the token contains at least one alphabetic character
  - count a bigram only when both adjacent tokens contain at least one alphabetic character
- Token-shape decisions:
  - a hyphenated word counts as one token only when WikiText already presents it as one whitespace token
  - no attempt is made to rejoin split WikiText artifacts such as `role @-@ playing`
  - standalone punctuation tokens are not counted because they fail the alphabetic-character check
  - standalone apostrophe fragments such as `'s` are left in the raw counts unless decision filters are explicitly requested
  - obvious web / domain / email-style tokens are filtered before counting to save memory and avoid keeping clear junk
    - current code catches tokens that start with `http://`, `https://`, or `www.`
    - current code also catches tokens containing `@` or common web-domain suffixes such as `.com`, `.org`, `.net`
    - note: bare tokens such as `http`, `https`, or `www` are **not** currently removed by this pre-count filter, which is why they can still appear in output
  - historical numeric lexical tokens such as `19th`, `20th`, or `1960s` are not treated as junk by this filter
- Bigram boundary decision:
  - bigrams are counted only within each parquet row
  - no bigrams are formed across parquet row boundaries
  - junk tokens act as hard boundaries for bigram counting
    - if either side of an adjacent pair is junk, that pair is skipped and no bigram is bridged across the junk token
- Post-count filtering:
  - optional `--apply-decisions-rules` filtering is available after counting
  - for 1-grams, this drops pure punctuation tokens and standalone apostrophe fragments
  - for 2-grams, this drops any bigram whose left or right token is a pure punctuation token or standalone apostrophe fragment
  - optional `--min-count` is applied after counting and after the optional decisions filter
- Output:
  - default 1-gram output path is `1-gram/wikitext-103-raw-v1-1grams.csv`
  - default 2-gram output path is `2-gram/wikitext-103-raw-v1-2grams.csv`
  - if decision filters are applied and no explicit output path is given, `.decisions` is inserted before `.csv`
  - parquet output is supported when requested
  - parquet output stores only `types` and `counts` to keep the file smaller; `probs` and `total_unique` can be derived later if needed
  - exploratory laptop-friendly build choice:
    - use `wikitext-2-raw-v1` for quick 2-gram builds
    - store the result as parquet rather than csv
    - current artifact: `2-gram/wikitext-2-raw-v1-2grams.parquet`
- Deferred:
  - no special cleanup yet for WikiText-specific markup artifacts such as `@-@`, `@,@`, or heading markers
  - no post-count junk filter beyond the pre-count junk-token filter, the optional apostrophe-fragment / punctuation rules, and `min-count`
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
  - -decisions
    - why is the name, what decisions

# Results


 - how different can these humans stories be?
  - how do we answer 'how the same'?
