---
paths:
  - "engine/**"
  - "engine/tests/**"
---

pytest lives in `engine/`. Run `python -m pytest -q` from `engine/`.
Every public check needs a bad-input test that fails closed.
Do not mark a TASKS box DONE without pasting that output into the reply and into `docs/CURRENT.md`.
