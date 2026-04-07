# humans decisions

## Datasets
  - because the story we're attempting to extract depends on accurately getting the raw story, decisions were made to 
  
    - clean rhe story corpora so that information loss would be minimal, 
    - reduce the size of the reference standard corpus (e.g. wikipedia) to a volume that could be processed into allotaxonometric representation within a tractable time without substantial loss of information.

  
#### Books

Downloaded the TXT format from z-library.im. 

  - Sapiens 
  - ...

Story wrangling

#### Google books
  - non trivial work to clean it up to use
  - numerous issues so deferred for future exploration in favor of time towards wikipedia unigrams and bigrams


#### Wikipedia

  Intended to be the opinionless reference standard which to compare the humans stories against, was sourced from an originally nearly 8M 1-gram corpus that was reduced to a size of 400K, about the maximum the author judged was computable by allotax within reasonable time.

  Rules used summary ...




## problems on dataset
For 1-grams, 2-grams
- BERT wikipedia dataset contains many words not comparable to english book corpora
- the dilution in ranks by injecting non-english words means that many words found in english literature are downranked
- not sure the validity of the dataset, credibility

## Wikipedia Decisions

- Start from wikitext-103 dataset
- Remove rows whose token is pure punctuation.
  - Examples: `(`, `)`, `,`, `.`, `"`, `````, `''`, `?`
- Remove standalone apostrophe-fragment tokens.
  - Examples: `'s`, `n't`, `'d`, `'m`, `'re`, `'ll`, `'ve`, `'em`
  - Rule intent: drop apostrophe-led or apostrophe-trailed shards and the standalone `n't` clitic, while keeping normal lexical tokens such as `don't`, `one's`, and `rock'n'roll`.


### wikitext
 - use 103-raw-v1 as input to storywrangler
 - used raw so that all decisions to clean are transparent and can be equal for all corpora
### desire to do 2-grams
- feasibility of bigrams depends on -aggressive filter
    
- the 2-grams english list is small, 
https://github.com/orgtre/google-books-ngram-frequency/blob/main/ngrams/2grams_english.csv

find a 2-gram list larger than that, but smaller than BERT's many non-english words dataset
  - or aggressively filter 

  - considered NRC VAD as a rule but the 20K word set was less than humans' set of types

  - n-grams are not simply all possible permutations, but empirically found



## Code

Code and datasets can be found at the github repo ...




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


- remaining treated in [OOV reconciliation](#oov)
  
### OOV
- the txt auto conversion downloaded from z-lib was mostly accurate, but some high-volume OOV tokens were leftover as line-break artifacts, lexical possessives, and similar token-shape issues
- examples from `zlib_stories_wrangled_but_oov.md` before reconciliation included: `produc-tion`, `algo-rithms`, `spe-cific`, `evolu-tion`, `im-provement`, `ad-vances`, `chap-ter`, `cre-ation`, `dig-ital`, `arti-ficial`, `ma-chines`, `learn-ing`, `de-pends`, `educa-tion`, `prog-ress`, `inno-vation`, `pub-lished`, `econ-omy`
- OOV reconciliation rules check that the OOV word, or its modified form, falls in wikipedia-lexicon:

  - if removing internal hyphenation yields a Wikipedia token, rewrite the cleaned story text to the joined form
  - if a dotted token is a word plus non-alphabetic note marker fragments such as `genes.6`, rewrite the cleaned story text to the lexical word
  - if a hyphenated compound is made of recognized lexical parts such as `non-egalitarian`, do not count it as OOV, but keep the text unchanged
  - if an apostrophe suffix such as `'s`, `n't`, `'d`, `'re`, `'ve`, `'ll`, or `'m` can be stripped to a recognized base token, do not count it as OOV, but keep the text unchanged
  


## Cleaned stories


### Cleaning counted
  - until there's a principle to clean counted tokens from stories and wiki, leave

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
