# RTD Algorithm For Top RHS Words

This note gives a direct algorithm for finding the most RTD-heavy words on the right-hand side, for a chosen `alpha`, without changing the visual pipeline.

The goal is:

- input `System 1` counts
- input `System 2` counts
- choose `alpha`
- return the top `n` words most characteristic of `System 2`

This reproduces the same ranking logic used by the current `py-allotax` backend for wordshift data, but written out as a standalone procedure.

## Meaning of RHS

Assume the comparison order is:

```text
System 1 vs System 2
```

Then:

- RHS means `System 2`
- a word belongs to the RHS when it is relatively more prominent in `System 2`
- in the signed wordshift list, that corresponds to `metric > 0`

## Inputs

For each system, start from a token-count mapping such as:

```python
{"cooperation": 124, "war": 77, "ritual": 13}
```

Only counts are required. Probabilities can be derived from counts and are not needed for the top-RHS calculation.

## Exact Algorithm

Let:

- `c1(t)` = count of token `t` in `System 1`
- `c2(t)` = count of token `t` in `System 2`
- `V` = union of all tokens appearing in either system

### 1. Build the shared vocabulary

For every token `t` in `V`, assign missing counts as zero:

```text
c1(t) = 0 if t is absent from System 1
c2(t) = 0 if t is absent from System 2
```

### 2. Compute tied ranks separately for each system

Rank tokens by count in descending order:

- larger count = smaller rank
- ties get the average rank across the tied block

Example:

```text
counts: 10, 8, 8, 3
ranks:  1, 2.5, 2.5, 4
```

Call these ranks:

- `r1(t)` for `System 1`
- `r2(t)` for `System 2`

This is important: ranks are assigned across the full union vocabulary, including tokens whose count is zero in one system.

### 3. Compute disjoint-rank reference terms

Let:

- `N1` = number of tokens with `c1(t) > 0`
- `N2` = number of tokens with `c2(t) > 0`

Define:

```text
inv_r1_disjoint = 1 / (N2 + N1 / 2)
inv_r2_disjoint = 1 / (N1 + N2 / 2)
```

These are used only in the normalization term.

### 4. Compute each token's raw RTD contribution

For each token `t`, define:

```text
inv1 = 1 / r1(t)
inv2 = 1 / r2(t)
```

If `alpha = 0`:

```text
d_raw(t) = log10(max(r1(t), r2(t)) / min(r1(t), r2(t)))
```

If `alpha > 0`:

```text
d_raw(t) = ((alpha + 1) / alpha) * |inv1^alpha - inv2^alpha|^(1 / (alpha + 1))
```

If `alpha = inf`:

```text
d_raw(t) = 0                  if r1(t) = r2(t)
d_raw(t) = max(inv1, inv2)    otherwise
```

### 5. Compute the RTD normalization constant

If `alpha = 0`:

```text
Z =
  sum over t with c1(t) > 0 of |ln((1 / r1(t)) / inv_r2_disjoint)|
+ sum over t with c2(t) > 0 of |ln((1 / r2(t)) / inv_r1_disjoint)|
```

If `alpha > 0`:

```text
Z =
  sum over t with c1(t) > 0 of ((alpha + 1) / alpha) * |(1 / r1(t))^alpha - inv_r2_disjoint^alpha|^(1 / (alpha + 1))
+ sum over t with c2(t) > 0 of ((alpha + 1) / alpha) * |inv_r1_disjoint^alpha - (1 / r2(t))^alpha|^(1 / (alpha + 1))
```

If `alpha = inf`:

```text
Z =
  sum over t with c1(t) > 0 of 1 / r1(t)
+ sum over t with c2(t) > 0 of 1 / r2(t)
```

### 6. Normalize each token contribution

```text
d(t) = d_raw(t) / Z
```

### 7. Convert to signed wordshift metric

Define:

```text
rank_diff(t) = r1(t) - r2(t)
```

Then assign the signed metric:

```text
metric(t) = -d(t)   if rank_diff(t) < 0
metric(t) = +d(t)   otherwise
```

Interpretation:

- `metric(t) > 0` means the token pulls toward `System 2`, so it is on the RHS
- `metric(t) < 0` means the token pulls toward `System 1`, so it is on the LHS

### 8. Extract the top RHS words

Filter to:

```text
metric(t) > 0
```

Then sort by:

```text
metric descending
```

Take the first `n`.

That result is the top `n` RHS words for the chosen `alpha`.

## Plain Python Reference Implementation

This version uses only the standard library and dictionaries of token counts.

```python
from math import inf, isfinite, log, log10


def tied_rank_desc(values):
    if not values:
        return []

    positions_by_value = {}
    for i, value in enumerate(values):
        positions_by_value.setdefault(value, []).append(i)

    ranks = [None] * len(values)
    current_rank = 1

    for value in sorted(positions_by_value.keys(), reverse=True):
        idxs = positions_by_value[value]
        tie_count = len(idxs)
        avg_rank = current_rank + (tie_count - 1) / 2
        for idx in idxs:
            ranks[idx] = avg_rank
        current_rank += tie_count

    return ranks


def top_rhs_rtd_words(counts1, counts2, alpha, top_n=20):
    vocab = sorted(set(counts1) | set(counts2))

    c1 = [counts1.get(token, 0) for token in vocab]
    c2 = [counts2.get(token, 0) for token in vocab]

    r1 = tied_rank_desc(c1)
    r2 = tied_rank_desc(c2)

    n1 = sum(1 for x in c1 if x > 0)
    n2 = sum(1 for x in c2 if x > 0)

    inv_r1_disjoint = 1 / (n2 + n1 / 2)
    inv_r2_disjoint = 1 / (n1 + n2 / 2)

    raw = []
    normalization = 0.0

    if alpha == inf or (isinstance(alpha, float) and not isfinite(alpha)):
        for i in range(len(vocab)):
            inv1 = 1 / r1[i]
            inv2 = 1 / r2[i]
            delta = 0.0 if r1[i] == r2[i] else max(inv1, inv2)
            raw.append(delta)
            if c1[i] > 0:
                normalization += inv1
            if c2[i] > 0:
                normalization += inv2

    elif alpha == 0:
        for i in range(len(vocab)):
            max_rank = max(r1[i], r2[i])
            min_rank = min(r1[i], r2[i])
            delta = log10(max_rank / min_rank)
            raw.append(delta)

            if c1[i] > 0:
                normalization += abs(log((1 / r1[i]) / inv_r2_disjoint))
            if c2[i] > 0:
                normalization += abs(log((1 / r2[i]) / inv_r1_disjoint))

    else:
        prefactor = (alpha + 1) / alpha
        exponent = 1 / (alpha + 1)
        inv_r1_disjoint_pow = inv_r1_disjoint ** alpha
        inv_r2_disjoint_pow = inv_r2_disjoint ** alpha

        for i in range(len(vocab)):
            inv1 = 1 / r1[i]
            inv2 = 1 / r2[i]
            inv1_pow = inv1 ** alpha
            inv2_pow = inv2 ** alpha

            delta = prefactor * abs(inv1_pow - inv2_pow) ** exponent
            raw.append(delta)

            if c1[i] > 0:
                normalization += prefactor * abs(inv1_pow - inv_r2_disjoint_pow) ** exponent
            if c2[i] > 0:
                normalization += prefactor * abs(inv_r1_disjoint_pow - inv2_pow) ** exponent

    rows = []
    for i, token in enumerate(vocab):
        d = raw[i] / normalization
        rank_diff = r1[i] - r2[i]
        metric = -d if rank_diff < 0 else d
        rows.append(
            {
                "type": token,
                "count1": c1[i],
                "count2": c2[i],
                "rank1": r1[i],
                "rank2": r2[i],
                "rank_diff": rank_diff,
                "metric": metric,
                "abs_metric": abs(metric),
            }
        )

    rhs = [row for row in rows if row["metric"] > 0]
    rhs.sort(key=lambda row: row["metric"], reverse=True)
    return rhs[:top_n]
```

## Minimal Usage Pattern

```python
counts1 = {"war": 50, "kinship": 10, "ritual": 4}
counts2 = {"war": 18, "kinship": 25, "cooperation": 20}

top_rhs = top_rhs_rtd_words(counts1, counts2, alpha=1/3, top_n=10)
for row in top_rhs:
    print(row["type"], row["metric"], row["rank1"], row["rank2"])
```

## If Starting From Allotax JSON

If your input is the allotax JSON array form:

```json
[
  {"types": "war", "counts": 50, "totalunique": 3, "probs": 0.7812},
  {"types": "kinship", "counts": 10, "totalunique": 3, "probs": 0.1562}
]
```

convert it first with:

```python
counts = {row["types"]: row["counts"] for row in data}
```

Then pass those `counts` dictionaries into `top_rhs_rtd_words`.

## Short Practical Rule

For a fixed `alpha`, the most RTD-heavy RHS words are the tokens that:

1. end up with positive signed RTD contribution
2. have the largest positive `metric`

That is the direct non-visual way to recover the RHS word list.
