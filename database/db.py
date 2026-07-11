import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager

BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "database"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "gestao_compras.db"
TURSO_REPLICA_PATH = DB_DIR / "gestao_compras_turso_replica.db"


def _value_from_mapping(mapping, *keys):
    """Lê chaves diretas e aliases dentro de um dicionário/TOML."""
    aliases = {
        "TURSO_DATABASE_URL": ["TURSO_DATABASE_URL", "database_url", "url", "db_url"],
        "TURSO_AUTH_TOKEN": ["TURSO_AUTH_TOKEN", "auth_token", "token"],
        "APP_DATABASE_MODE": ["APP_DATABASE_MODE", "app_database_mode", "database_mode", "mode"],
    }
    for key in keys:
        for alias in aliases.get(key, [key]):
            try:
                value = mapping.get(alias)
            except Exception:
                value = None
            if value:
                return str(value).strip()
    return ""


def _get_secret_value(*keys):
    """Busca configuração em variável de ambiente, .streamlit/secrets.toml ou st.secrets.

    Isso permite que scripts executados pelo CMD também encontrem o Turso,
    não apenas o app rodando via Streamlit.
    """
    # 1) Variáveis de ambiente
    for key in keys:
        value = os.environ.get(key)
        if value:
            return str(value).strip()

    # 2) Arquivo local .streamlit/secrets.toml, útil para scripts
    secrets_path = BASE_DIR / ".streamlit" / "secrets.toml"
    if secrets_path.exists():
        try:
            import tomllib
            data = tomllib.loads(secrets_path.read_text(encoding="utf-8"))
            value = _value_from_mapping(data, *keys)
            if value:
                return value
            turso_cfg = data.get("turso", {}) if isinstance(data, dict) else {}
            value = _value_from_mapping(turso_cfg, *keys)
            if value:
                return value
        except Exception:
            pass

    # 3) st.secrets, útil no Streamlit Cloud
    try:
        import streamlit as st
        value = _value_from_mapping(st.secrets, *keys)
        if value:
            return value
        if "turso" in st.secrets:
            value = _value_from_mapping(st.secrets["turso"], *keys)
            if value:
                return value
    except Exception:
        pass

    return ""


def get_db_mode():
    """Retorna o modo de banco.

    Use app_database_mode = "sqlite" para validações offline rápidas no PC.
    Use app_database_mode = "turso" no Streamlit Cloud/celular.
    Se não informar, escolhe Turso quando URL+token existirem.
    """
    explicit_mode = (_get_secret_value("APP_DATABASE_MODE") or "").strip().lower()
    if explicit_mode in ("sqlite", "local"):
        return "sqlite"
    if explicit_mode in ("turso", "online"):
        return "turso"
    url = _get_secret_value("TURSO_DATABASE_URL")
    token = _get_secret_value("TURSO_AUTH_TOKEN")
    return "turso" if url and token else "sqlite"


def get_db_label():
    return "Turso online" if get_db_mode() == "turso" else "SQLite local rápido"


@contextmanager
def get_conn():
    """Abre conexão local SQLite ou remota Turso/libSQL.

    Para uso local, mantém SQLite normal.
    Para Streamlit Cloud, se TURSO_DATABASE_URL e TURSO_AUTH_TOKEN estiverem
    configurados, usa libsql conectado ao Turso.
    """
    if get_db_mode() == "turso":
        try:
            import libsql
        except Exception as exc:
            raise RuntimeError(
                "Modo Turso configurado, mas a biblioteca 'libsql' não está instalada. "
                "Rode: pip install -r requirements.txt"
            ) from exc
        conn = libsql.connect(
            database=_get_secret_value("TURSO_DATABASE_URL"),
            auth_token=_get_secret_value("TURSO_AUTH_TOKEN"),
        )
        # Algumas versões do libsql aceitam row_factory; se não aceitarem,
        # o restante do app continua usando pandas para as consultas principais.
        try:
            conn.row_factory = sqlite3.Row
        except Exception:
            pass
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _execute_schema(conn, schema_sql):
    """Executa schema em SQLite ou libSQL, mesmo quando executescript não existir."""
    if hasattr(conn, "executescript"):
        conn.executescript(schema_sql)
        return
    statements = [s.strip() for s in schema_sql.split(";") if s.strip()]
    for stmt in statements:
        conn.execute(stmt)


def _table_columns(conn, table_name):
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    cols = []
    for row in rows:
        try:
            cols.append(row[1])
        except Exception:
            cols.append(row["name"])
    return cols


def init_db():
    with get_conn() as conn:
        _execute_schema(
            conn,
            """
            CREATE TABLE IF NOT EXISTS categorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                grupo TEXT DEFAULT 'Geral',
                ativo INTEGER DEFAULT 1,
                criado_em TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS mercados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                cnpj TEXT,
                cidade TEXT,
                bairro TEXT,
                uf TEXT,
                ativo INTEGER DEFAULT 1,
                criado_em TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_padronizado TEXT NOT NULL,
                marca TEXT,
                categoria_id INTEGER,
                unidade_padrao TEXT DEFAULT 'un',
                quantidade_padrao REAL DEFAULT 1,
                ativo INTEGER DEFAULT 1,
                criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (categoria_id) REFERENCES categorias(id)
            );

            CREATE TABLE IF NOT EXISTS compras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mercado_id INTEGER,
                data_compra TEXT NOT NULL,
                valor_total REAL DEFAULT 0,
                chave_nfce TEXT,
                url_qrcode TEXT,
                origem TEXT DEFAULT 'Manual',
                status_leitura TEXT DEFAULT 'Manual',
                forma_pagamento TEXT,
                valor_pago REAL DEFAULT 0,
                observacoes TEXT,
                criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (mercado_id) REFERENCES mercados(id)
            );

            CREATE TABLE IF NOT EXISTS itens_compra (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                compra_id INTEGER NOT NULL,
                descricao_original TEXT,
                produto_id INTEGER,
                quantidade REAL DEFAULT 1,
                unidade TEXT DEFAULT 'un',
                valor_unitario REAL DEFAULT 0,
                valor_total REAL DEFAULT 0,
                desconto REAL DEFAULT 0,
                criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (compra_id) REFERENCES compras(id) ON DELETE CASCADE,
                FOREIGN KEY (produto_id) REFERENCES produtos(id)
            );

            CREATE TABLE IF NOT EXISTS mapeamentos_produto (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                descricao_original TEXT NOT NULL,
                produto_id INTEGER NOT NULL,
                mercado_id INTEGER,
                confianca REAL DEFAULT 1,
                criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (produto_id) REFERENCES produtos(id),
                FOREIGN KEY (mercado_id) REFERENCES mercados(id)
            );
            """,
        )
        # Migrações leves para quem substituir arquivos mantendo banco antigo.
        cols = _table_columns(conn, "compras")
        if "forma_pagamento" not in cols:
            conn.execute("ALTER TABLE compras ADD COLUMN forma_pagamento TEXT")
        if "valor_pago" not in cols:
            conn.execute("ALTER TABLE compras ADD COLUMN valor_pago REAL DEFAULT 0")
        seed_defaults(conn)


def seed_defaults(conn):
    categorias = [
        ("Alimentos básicos", "Alimentos"),
        ("Carnes", "Alimentos"),
        ("Hortifruti", "Alimentos"),
        ("Laticínios", "Alimentos"),
        ("Bebidas", "Bebidas"),
        ("Limpeza", "Casa"),
        ("Higiene", "Casa"),
        ("Pet", "Casa"),
        ("Farmácia", "Saúde"),
        ("Alimentos secundários", "Alimentos"),
        ("Outros", "Geral"),
    ]
    for nome, grupo in categorias:
        conn.execute(
            "INSERT OR IGNORE INTO categorias (nome, grupo) VALUES (?, ?)",
            (nome, grupo),
        )
