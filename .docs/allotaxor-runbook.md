# Allotaxor Runbook

Use `allotaxor.py` for one comparison at a time:

```powershell
& .\.venv\Scripts\python.exe .\allotaxor.py SYSTEM1 SYSTEM2 --alpha 0 1/12 1/6 1/3 1
```

## Example alpha sweep

```powershell
& .\.venv\Scripts\python.exe .\allotaxor.py `
  .\1-gram\humans.json `
  .\1-gram\Sapiens.json `
  --label1 humans `
  --label2 sapiens `
  --alpha 0 1/12 1/6 1/3 1
```

## 1-gram wiki vs each book

```powershell
$books = Get-ChildItem .\1-gram\*.json | Where-Object {
  $_.Name -notin @('humans.json', 'wikitext-103-raw-v1-1grams.json')
}

foreach ($book in $books) {
  & .\.venv\Scripts\python.exe .\allotaxor.py `
    .\1-gram\wikitext-103-raw-v1-1grams.json `
    $book.FullName `
    --label1 "wikitext 103 raw v1" `
    --alpha 0 1/12 1/6 1/3 1
}
```

## 2-gram wiki vs each book

```powershell
$books = Get-ChildItem .\2-gram\*.json | Where-Object {
  $_.Name -notin @('humans-2grams.json', 'wikitext-2-raw-v1-2grams.json')
}

foreach ($book in $books) {
  & .\.venv\Scripts\python.exe .\allotaxor.py `
    .\2-gram\wikitext-2-raw-v1-2grams.parquet `
    $book.FullName `
    --label1 "wikitext 2 raw v1" `
    --alpha 0 1/12 1/6 1/3 1
}
```

## Unordered 1-gram book pairs

```powershell
$books = Get-ChildItem .\1-gram\*.json | Where-Object {
  $_.Name -notin @('humans.json', 'wikitext-103-raw-v1-1grams.json')
}

for ($i = 0; $i -lt $books.Count; $i++) {
  for ($j = $i + 1; $j -lt $books.Count; $j++) {
    & .\.venv\Scripts\python.exe .\allotaxor.py `
      $books[$i].FullName `
      $books[$j].FullName `
      --output-dir .\figures\1grams\book-pairs `
      --alpha 0 1/12 1/6 1/3 1
  }
}
```

## Unordered 2-gram book pairs

```powershell
$books = Get-ChildItem .\2-gram\*.json | Where-Object {
  $_.Name -notin @('humans-2grams.json', 'wikitext-2-raw-v1-2grams.json')
}

for ($i = 0; $i -lt $books.Count; $i++) {
  for ($j = $i + 1; $j -lt $books.Count; $j++) {
    & .\.venv\Scripts\python.exe .\allotaxor.py `
      $books[$i].FullName `
      $books[$j].FullName `
      --output-dir .\figures\2grams\book-pairs `
      --alpha 0 1/12 1/6 1/3 1
  }
}
```
