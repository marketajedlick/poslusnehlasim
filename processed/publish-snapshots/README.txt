Produkční HTML pro vydání v publish-approved.json → held (dočasně na webu, dokud se nedoladí lokální facts).

Stáhnout z webu:

  ./run-svejk.sh publish-snapshot-fetch 2025/22/11.06.2026 --overwrite

Nebo najednou: python3 scripts/init_publish_gate.py

Po doladění lokálních facts přesuň klíč z held do approved a snapshot smaž.

hidden v publish-approved.json = vydání úplně mimo web (např. neprošlo review). Snapshoty pro hidden se nepoužívají.
