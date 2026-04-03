 - used nomenclature "Humans" :) Prof. advise
 - Google books
  - non trivial work to clean it up to use
  - numerous issues so deferred in favor of wikipedia unigrams and bigrams
  
 - alpha 
 - bigram


## Downloaded Book Cleaning

Source files in `books/` are downloaded `.txt` extractions and may contain layout junk, repeated headers, and mojibake.

### Deterministic cleaning rules

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
  - collapse repeated spaces
  - trim line edges
  - collapse 3+ blank lines to 2

- remaining treated in [OOV reconciliation](#oov)
  
### OOV
- the txt auto conversion downloaded from z-lib was mostly accurate, but some high-volume OOV tokens were leftover as line-break artifacts, lexical possessives, and similar token-shape issues
- examples from `zlib_stories_wrangled_but_oov.md` before reconciliation included: `produc-tion`, `algo-rithms`, `spe-cific`, `evolu-tion`, `im-provement`, `ad-vances`, `chap-ter`, `cre-ation`, `dig-ital`, `arti-ficial`, `ma-chines`, `learn-ing`, `de-pends`, `educa-tion`, `prog-ress`, `inno-vation`, `pub-lished`, `econ-omy`
- OOV reconciliation is allowed only for safe, lexicon-backed cases:
  - if removing internal hyphenation yields a Wikipedia token, rewrite the cleaned story text to the joined form
  - if a dotted token is a word plus non-alphabetic note marker fragments such as `genes.6`, rewrite the cleaned story text to the lexical word
  - if a hyphenated compound is made of recognized lexical parts such as `non-egalitarian`, do not count it as OOV, but keep the text unchanged
  - if an apostrophe suffix such as `'s`, `n't`, `'d`, `'re`, `'ve`, `'ll`, or `'m` can be stripped to a recognized base token, do not count it as OOV, but keep the text unchanged
  
### Explicit non-decisions
- Pause further OOV reconciliation after obvious artifact classes are identified.
  - Example: `Kandiaronk` appearing in text while Wikipedia uses `Kondiaronk` is treated as a legitimate naming/spelling variant to note, not as a cleaner bug to auto-correct.

### Files cleaned with this rule set

- `books/The Code Economy A Forty-Thousand Year History.txt`
- `books/The Dawn of Everything A New History of Humanity.txt`

## Wikipedia
 - was too large for py-allotax, so scripts cleaned the dataset from BERT

### Reference files

- Source reference unigram file:
  - `1-gram/data_structured/wikipedia.uncased.unigrams.csv`
- Wrangled reference unigram file:
  - `1-gram/data_structured/wikipedia.uncased.unigrams.wrangled.csv`

### Decisions

- Start from `1-gram/data_structured/wikipedia.uncased.unigrams.csv`.
- Remove rows whose token is pure punctuation.
  - Examples: `(`, `)`, `,`, `.`, `"`, `````, `''`, `?`
- Remove standalone apostrophe-fragment tokens.
  - Examples: `'s`, `n't`, `'d`, `'m`, `'re`, `'ll`, `'ve`, `'em`
  - Rule intent: drop apostrophe-led or apostrophe-trailed shards and the standalone `n't` clitic, while keeping normal lexical tokens such as `don't`, `one's`, and `rock'n'roll`.
- Apply a frequency cutoff of `count >= 40`.
- Write the wrangled file with Unix LF line endings.

### Current wrangled output

- Output file:
  - `1-gram/data_structured/wikipedia.uncased.unigrams.wrangled.csv`
- Output rows:
  - `420,148`
- Output size:
  - `5,090,474` bytes

### Non-decisions

- No additional lexical cleaning or language filtering is applied beyond:
  - dropping pure punctuation rows
  - dropping standalone apostrophe fragments
  - applying the `count >= 40` cutoff
