"""Migra dados do SQLite local para o Turso.

Recomendação: use apenas depois de validar o banco Turso vazio.

Uso no CMD/PowerShell, com ambiente ativado:

set TURSO_DATABASE_URL=libsql://...
set TURSO_AUTH_TOKEN=...
python scripts/migrar_sqlite_para_turso.py
"""

import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from database.db import DB_PATH, init_db, get_conn, get_db_mode

TABELAS = [
    "categorias",
    "mercados",
    "produtos",
    "compras",
    "itens_compra",
    "mapeamentos_produto",
]

if not DB_PATH.exists():
    print(f"Banco local não encontrado: {DB_PATH}")
    raise SystemExit(1)

if get_db_mode() != "turso":
    print("Turso não configurado. Configure TURSO_DATABASE_URL e TURSO_AUTH_TOKEN.")
    raise SystemExit(1)

init_db()
local = sqlite3.connect(DB_PATH)
local.row_factory = sqlite3.Row

with get_conn() as remoto:
    for tabela in TABELAS:
        rows = local.execute(f"SELECT * FROM {tabela}").fetchall()
        if not rows:
            print(f"{tabela}: sem registros")
            continue
        cols = [d[0] for d in local.execute(f"SELECT * FROM {tabela} LIMIT 1").description]
        placeholders = ",".join(["?"] * len(cols))
        col_sql = ",".join(cols)
        sql = f"INSERT OR IGNORE INTO {tabela} ({col_sql}) VALUES ({placeholders})"
        for row in rows:
            remoto.execute(sql, tuple(row[c] for c in cols))
        print(f"{tabela}: {len(rows)} registros migrados")

local.close()
print("Migração concluída.")
