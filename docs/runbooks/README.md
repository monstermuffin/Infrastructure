# Runbooks

One markdown file per alert, named after the alert in kebab-case (`DiskFilling` -> `disk-filling.md`). Alert annotations link here by URL.

This directory is public. Do not put secrets, credentials, real IP addresses or network topology in a runbook; use label placeholders (`<host>`, `<site>`) and exact commands or queries instead.

Each runbook has, in this order:

1. What the alert means and what is impacted.
2. First three checks (exact commands or queries).
3. Common causes and fixes in this estate.
4. When it is safe to silence.

Write for a reader with no prior context. No tribal knowledge.

Note: `.gitignore` ignores `*au*.md` anywhere in the repo. A runbook whose file name contains `au` (for example one named after an auth or default alert) will be silently ignored by git; rename it or add a negation.
