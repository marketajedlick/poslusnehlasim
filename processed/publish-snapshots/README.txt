Produkční HTML pro vydání v publish-approved.json → held.
Stáhnout z webu:

  ./run-svejk.sh publish-snapshot-fetch 2025/22/11.06.2026 --overwrite
  ./run-svejk.sh publish-snapshot-fetch 2025/23/11.06.2026 --overwrite

Nebo najednou: python3 scripts/init_publish_gate.py

Po doladění lokálních facts přesuň klíč z held do approved a snapshot smaž.
