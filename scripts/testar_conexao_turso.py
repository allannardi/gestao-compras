"""Teste simples de conexão Turso para o Gestão de Compras.

Uso no CMD/PowerShell, com ambiente ativado:

Opção A: configurar .streamlit/secrets.toml
[turso]
database_url = "libsql://..."
auth_token = "..."

Opção B: usar variáveis de ambiente
set TURSO_DATABASE_URL=libsql://...
set TURSO_AUTH_TOKEN=...

python scripts/testar_conexao_turso.py
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from database.db import get_db_mode, get_db_label, init_db, get_conn

print(f"Modo detectado: {get_db_label()}")

if get_db_mode() != "turso":
    print("Turso não configurado. Configure .streamlit/secrets.toml ou TURSO_DATABASE_URL e TURSO_AUTH_TOKEN.")
    raise SystemExit(1)

init_db()
with get_conn() as conn:
    row = conn.execute("SELECT COUNT(*) FROM categorias").fetchone()
    total = row[0] if row else 0
    print(f"Conexão OK. Categorias no banco: {total}")
