# Archiv jednorázových skriptů

Opravy dat z konkrétních situací (s24, 2. 7. 2026, zavedení publish gate,
hromadné úpravy facts). Svou práci odvedly a nespouštějí se znovu; jsou tu
pro dohledání, co a proč se kdy měnilo. Cesty k repu v nich počítají se
složkou `scripts/`, před případným spuštěním je uprav.

Pozor: skripty zapisují přímo do `facts/`. U publikovaných vydání to od
zavedení zmrazení zachytí `publish-check` v CI (drift proti snapshotu);
změnu je pak potřeba potvrdit přes `./run-svejk.sh edition republish --reason "…"`.

Trvalé nástroje zůstávají v `scripts/`: `audit_all_published.py`,
`audit_published_*.py`, `audit_jednaci_den.py`, `fix_steno_published.py`,
`fix_stale_psp_url_cache.py`, `lint_site.py`, `check-*.sh`,
`deploy-subscribe-worker.sh`.
