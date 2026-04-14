# Allotax Wordshift Notes For RHS / System 2

This note is for the task: find the most divergent words on the right-hand side of the word bar list.

In allotax, the bar list is directional. The command is always ordered as:

```powershell
python allotaxor.py SYSTEM1 SYSTEM2 ...
```

That order matters because the wordshift header is interpreted as:

```text
← System 1 · Divergence contribution · System 2 →
```

So:

- left-hand side = `System 1`
- right-hand side = `System 2`
- if you want words most characteristic of the second corpus, that corpus must be passed as `system2`

## What the bar list means

Each bar is a word or n-gram with a signed divergence contribution.

- `metric > 0` means the bar belongs to the right-hand side, that is `System 2`
- `metric < 0` means the bar belongs to the left-hand side, that is `System 1`
- larger `abs(metric)` means a stronger contribution to the divergence

The internal sign rule is built from:

```text
rank_diff = rank1 - rank2
```

where smaller rank means more frequent.

So:

- if `rank2 < rank1`, the term is more prominent in `System 2`, and it appears on the RHS with positive `metric`
- if `rank1 < rank2`, the term is more prominent in `System 1`, and it appears on the LHS with negative `metric`

## Practical rule for the new task

To get the most divergent RHS words:

1. run the comparison in the correct order
2. export `rtd-json`
3. filter to rows with `metric > 0`
4. sort descending by `metric`

That is the same as: "find the strongest `System 2` words in the bar list."

## Recommended usage

Example, if the book should be treated as the RHS target:

```powershell
& .\.venv\Scripts\python.exe .\allotaxor.py `
  .\1-gram\wikitext-103-raw-v1-1grams.json `
  .\1-gram\Sapiens.json `
  --alpha 1/3 `
  --format rtd-json `
  --output-dir .\figures\1grams `
  --force
```

This makes:

- `wikitext103` = `System 1`
- `Sapiens` = `System 2`
- positive bars = words pulling toward `Sapiens`

## `rtd-json` schema

The JSON export contains:

- `rtd.normalization`
- `rtd.divergence_elements`
- `barData`
- `total_words`

Each `barData` row has:

- `type`: token or n-gram
- `rank1`: rank in `System 1`
- `rank2`: rank in `System 2`
- `rank_diff`: `rank1 - rank2`
- `metric`: signed divergence contribution

The rows are already sorted by descending `abs(metric)`.

## PowerShell extraction

To pull the RHS / `System 2` words from an export:

```powershell
$json = Get-Content -Raw .\figures\1grams\wikitext103-v-sapiens.alpha-1-3.json | ConvertFrom-Json

$json.barData |
  Where-Object { $_.metric -gt 0 } |
  Sort-Object metric -Descending |
  Select-Object -First 20 type, rank1, rank2, rank_diff, metric
```

To pull the LHS / `System 1` words instead:

```powershell
$json.barData |
  Where-Object { $_.metric -lt 0 } |
  Sort-Object metric |
  Select-Object -First 20 type, rank1, rank2, rank_diff, metric
```

## Important caveat

Right now `rtd-json` returns the top wordshift rows, not the full union of words.

- `barData` is the visible ranked word list
- `total_words` tells you how many words existed before truncation

So this export is suitable for:

- "what are the top RHS / System 2 words?"
- "what are the top LHS / System 1 words?"

It is not yet the full exhaustive ranked list of all words. If later we want every word, the next change should be to expose a `top_n` or `all_words` option through `allotaxor.py`.

## Short interpretation summary

For this project, read the bar list this way:

- RHS = `System 2`
- positive `metric` = favors `System 2`
- negative `metric` = favors `System 1`
- to study words distinctive of the RHS text, pass that text as `system2`
