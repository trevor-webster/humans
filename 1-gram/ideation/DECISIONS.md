 - punctuation kept where meaningful (e.g., apostrophes in contractions, hyphens in compound words, \w+<\w+, etc.)

## Downloaded Book Cleaning

Source files in `books/` are downloaded `.txt` extractions and may contain layout junk, repeated headers, and mojibake.

### Deterministic cleaning rules

- Normalize common mojibake punctuation to simple ASCII equivalents before cleaning:
  - apostrophes like `â€™` -> `'`
  - quotes like `â€œ` / `â€` -> `"`
  - dashes like `â€“` / `â€”` -> `-`
  - ellipses like `â€¦` -> `...`
  - broken spaces like `â` and non-breaking spaces -> normal spaces
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

### Explicit non-decisions

- Do not apply broad cp1252/latin1-to-utf8 recoding across the whole document.
  - Reason: this merged legitimate word boundaries and degraded readable text in `The Code Economy`.
- Do not strip valid accented letters just because other mojibake exists nearby.
- Do not keep standalone punctuation such as `=`, quotes, or em dashes unless they survive the inner-token rule above.
- Pause further OOV reconciliation after obvious artifact classes are identified.
  - Example: `Kandiaronk` appearing in text while Wikipedia uses `Kondiaronk` is treated as a legitimate naming/spelling variant to note, not as a cleaner bug to auto-correct.

### Files cleaned with this rule set

- `books/The Code Economy A Forty-Thousand Year History (Philip E. Auerswald) (z-library.sk, 1lib.sk, z-lib.sk).txt`
- `books/The Dawn of Everything A New History of Humanity (David Graeber, David Wengrow) (z-library.sk, 1lib.sk, z-lib.sk).txt`

## Wikipedia

### Reference files

- Source reference unigram file:
  - `1-gram/data_structured/wikipedia.uncased.unigrams.csv`
- Filtered reference unigram file:
  - `1-gram/data_structured/wikipedia.uncased.unigrams.filtered.csv`
- Top-1,000,000 truncated reference unigram file:
  - `1-gram/data_structured/wikipedia.uncased.unigrams.filtered.top_1000000.csv`

### Decisions

- For the Wikipedia unigram reference, drop rows whose token is pure punctuation.
  - Examples: `(`, `)`, and other tokens with no alphanumeric characters.
- Also drop rows whose frequency/count is exactly `1`.
- Write the filtered file with Unix LF line endings.
- Keep all remaining tokens, including:
  - words
  - mixed alphanumeric tokens
  - tokens containing punctuation but not pure punctuation
- Some retained Wikipedia tokens are obviously not desirable as an English-only lexical reference.
  - Example classes include non-English forms, names, transliterations, and tokenization leftovers.
  - A future improvement may be to apply an additional lexicon filter on top of the frequency filter.

### Current filtered output stats

- kept rows: `3,721,315`
- removed pure punctuation rows: `2,054`
- removed count-1 rows: `4,181,041`
- output size: `44,314,305` bytes

### Top-1,000,000 truncation

- A further truncation was created by taking only the first `1,000,000` rows from `wikipedia.uncased.unigrams.filtered.csv`.
- Output file size: `11,937,846` bytes
- Last kept token at the 1,000,000 row cutoff: `kalidou`

### Lost from `humans.csv` at the top-1,000,000 cutoff

- unique `humans.csv` tokens no longer present in the truncated Wikipedia reference: `5,781`
- total token mass from `humans.csv` no longer present in the truncated Wikipedia reference: `9,098`
- examples of lost tokens:
  - `one's`
  - `what's`
  - `there's`
  - `kandiaronk`
  - `city's`
  - `wengrow`
  - `today's`
  - `lévi-strauss`
  - `here's`
  - `people's`
  - `humanity's`
  - `mega-sites`
  - `rousseau's`
  - `mohenjo-daro`
  - `history's`

### Top-2,000,000 with human-word preservation

- A `2,000,000` row cutoff was evaluated with the extra constraint: do not truncate away any token present in `humans.csv`.
- This constraint could not be satisfied within `2,000,000` rows.
- The last token from `humans.csv` still present in the filtered Wikipedia reference occurs at row `3,719,933` (0-based index `3,719,932`).
- Therefore, preserving all currently matched human words forces the cutoff to remain effectively the same as the existing tail-preserved file:
  - `1-gram/data_structured/wikipedia.uncased.unigrams.filtered.trimmed_to_humans.csv`
- A trial file was written:
  - `1-gram/data_structured/wikipedia.uncased.unigrams.filtered.top_2000000_preserve_humans.csv`
- But because full preservation requires extending the cutoff to row `3,719,933`, it is effectively equivalent in coverage/size to the existing human-tail-preserved file.

### Lexicon-filter note

- Because some tokens near the retained tail are obviously non-English or otherwise undesirable as reference vocabulary, a future lexicon-based filter may be preferable to simple rank truncation.
- That work is not applied yet; current Wikipedia filtering remains frequency-based plus special-case comparison against `humans.csv`.

### Top-300,000 plus human-overlap preservation

- A smaller working reference was created starting from:
  - `1-gram/data_structured/wikipedia.uncased.unigrams.filtered.trimmed_to_humans.csv`
- Keep rule:
  - keep the first `300,000` rows by rank
  - also keep any later row whose token appears in `humans.csv`
- Output file:
  - `1-gram/data_structured/wikipedia.uncased.unigrams.filtered.top_300000_plus_humans.csv`

### Current top-300,000 plus humans stats

- rows kept total: `302,679`
- rows kept from the top-300,000 block: `300,000`
- additional tail rows kept because they appear in `humans.csv`: `2,679`
- rows removed from the trimmed-to-humans source: `3,417,254`
- output size: `3,733,943` bytes

### Human-overlap preservation note

- Preservation was evaluated against tokens that actually appear in:
  - `1-gram/data_structured/wikipedia.uncased.unigrams.filtered.trimmed_to_humans.csv`
- `humans.csv` unique tokens: `34,603`
- human tokens also present in the trimmed Wikipedia source: `29,923`
- overlapping human tokens missing after the keep rule: `0`
- human tokens not present in the trimmed Wikipedia source to begin with: `4,680`
- Example human tokens absent from the Wikipedia source and therefore not preservable by this rule:
  - `0.25-gallon`
  - `09.pdf`
  - `1,000km`
  - `10,000-year-old`
  - `100,000-seater`

### Percentage baseline decision

- For any later percentage/probability calculations using the reduced Wikipedia references, use the total counts from the original unfiltered source:
  - `1-gram/data_structured/wikipedia.uncased.unigrams.csv`
- Do not renormalize percentages solely against the truncated working file unless a later decision explicitly changes that rule.

### Non-decisions

- No additional lexical cleaning or normalization was applied to the Wikipedia unigram file beyond:
  - dropping pure punctuation rows
  - dropping count-1 rows
  - rewriting with LF line endings
 
