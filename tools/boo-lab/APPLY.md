# Apply on the desktop repo (I cannot git push from this sandbox)

Copy into `tools/boo-lab/`:

- PROTOCOL.md
- QUALITY.md
- src/boo_lab/schema.py
- src/boo_lab/audit.py
- tests/test_schema.py

Then patch existing files as in PATCHES.md.

Do **not** apply `artifacts/labyrinth-lock.patch`. That is writer-side. Lab only.

Verify:

```bat
cd tools\boo-lab
python -m pytest tests\test_schema.py -q
python -m boo_lab.cli audit
```

`structure` must print that it writes `data/drafts.jsonl` and must not open `sections.jsonl` for write.
