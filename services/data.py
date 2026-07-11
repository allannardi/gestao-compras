import pandas as pd
from database.db import get_conn
from services.utils import normalizar_texto


def _row_get(row, key, default=None):
    """Acessa linhas SQLite/libSQL por nome com fallback por índice.

    No SQLite local, row['campo'] funciona. No Turso/libSQL, algumas
    respostas podem vir como tuplas. Esse helper evita erro do tipo:
    tuple indices must be integers or slices, not str.
    """
    if row is None:
        return default
    try:
        return row[key]
    except Exception:
        pass
    index_map = {
        'id': 0,
        'nome_padronizado': 1,
        'marca': 2,
        'categoria_id': 3,
        'unidade_padrao': 4,
        'quantidade_padrao': 5,
        'ativo': 6,
        'criado_em': 7,
        'cnpj': 2,
    }
    idx = index_map.get(key)
    if idx is not None:
        try:
            return row[idx]
        except Exception:
            return default
    return default


def _row_to_dict(row, columns=None):
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    try:
        return dict(row)
    except Exception:
        if columns:
            return {columns[i]: row[i] for i in range(min(len(columns), len(row)))}
        return {}


def query_df(sql, params=()):
    """Executa SELECT e retorna DataFrame.

    Evita pd.read_sql_query diretamente porque conexões libSQL/Turso
    podem não ser reconhecidas pelo pandas no Streamlit Cloud.
    """
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
        columns = [desc[0] for desc in (cur.description or [])]
        normalized_rows = []
        for row in rows:
            if isinstance(row, dict):
                normalized_rows.append(row)
            else:
                try:
                    normalized_rows.append(dict(row))
                except Exception:
                    normalized_rows.append({columns[i]: row[i] for i in range(len(columns))})
        return pd.DataFrame(normalized_rows, columns=columns)


def execute(sql, params=()):
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        last_id = getattr(cur, "lastrowid", None)
        if last_id is not None:
            return last_id
        try:
            row = conn.execute("SELECT last_insert_rowid()").fetchone()
            if row is not None:
                try:
                    return row[0]
                except Exception:
                    return row["last_insert_rowid()"]
        except Exception:
            pass
        return None


def get_categorias(ativas=True):
    where = "WHERE ativo = 1" if ativas else ""
    return query_df(f"SELECT * FROM categorias {where} ORDER BY nome")


def add_categoria(nome, grupo='Geral'):
    return execute("INSERT INTO categorias (nome, grupo) VALUES (?, ?)", (nome.strip(), grupo.strip() or 'Geral'))


def update_categoria(id, nome, grupo, ativo):
    execute("UPDATE categorias SET nome=?, grupo=?, ativo=? WHERE id=?", (nome, grupo, int(ativo), id))


def delete_categoria(id):
    execute("DELETE FROM categorias WHERE id=?", (id,))


def get_mercados(ativos=True):
    where = "WHERE ativo = 1" if ativos else ""
    return query_df(f"SELECT * FROM mercados {where} ORDER BY nome")


def add_mercado(nome, cnpj='', cidade='', bairro='', uf=''):
    return execute("INSERT INTO mercados (nome, cnpj, cidade, bairro, uf) VALUES (?, ?, ?, ?, ?)", (nome.strip(), cnpj, cidade, bairro, uf))


def update_mercado(id, nome, cnpj, cidade, bairro, uf, ativo):
    execute("UPDATE mercados SET nome=?, cnpj=?, cidade=?, bairro=?, uf=?, ativo=? WHERE id=?", (nome, cnpj, cidade, bairro, uf, int(ativo), id))


def get_produtos(ativos=True):
    where = "WHERE p.ativo = 1" if ativos else ""
    return query_df(f"""
        SELECT p.*, c.nome AS categoria
        FROM produtos p
        LEFT JOIN categorias c ON c.id = p.categoria_id
        {where}
        ORDER BY p.nome_padronizado
    """)


def add_produto(nome_padronizado, marca='', categoria_id=None, unidade_padrao='un', quantidade_padrao=1):
    return execute(
        "INSERT INTO produtos (nome_padronizado, marca, categoria_id, unidade_padrao, quantidade_padrao) VALUES (?, ?, ?, ?, ?)",
        (nome_padronizado.strip(), marca.strip(), categoria_id, unidade_padrao, quantidade_padrao),
    )


def update_produto(id, nome_padronizado, marca, categoria_id, unidade_padrao, quantidade_padrao, ativo):
    execute(
        "UPDATE produtos SET nome_padronizado=?, marca=?, categoria_id=?, unidade_padrao=?, quantidade_padrao=?, ativo=? WHERE id=?",
        (nome_padronizado, marca, categoria_id, unidade_padrao, quantidade_padrao, int(ativo), id),
    )


def get_compras():
    return query_df("""
        SELECT co.*, m.nome AS mercado
        FROM compras co
        LEFT JOIN mercados m ON m.id = co.mercado_id
        ORDER BY co.data_compra DESC, co.id DESC
    """)


def get_compra(compra_id):
    df = query_df("""
        SELECT co.*, m.nome AS mercado, m.cnpj AS mercado_cnpj
        FROM compras co
        LEFT JOIN mercados m ON m.id = co.mercado_id
        WHERE co.id = ?
        LIMIT 1
    """, (compra_id,))
    return df.iloc[0].to_dict() if not df.empty else None


def get_compra_por_chave(chave_nfce):
    chave_nfce = (chave_nfce or '').strip()
    if not chave_nfce:
        return None
    df = query_df("""
        SELECT co.*, m.nome AS mercado
        FROM compras co
        LEFT JOIN mercados m ON m.id = co.mercado_id
        WHERE co.chave_nfce = ?
        ORDER BY co.id DESC
        LIMIT 1
    """, (chave_nfce,))
    return df.iloc[0].to_dict() if not df.empty else None


def add_compra(mercado_id, data_compra, valor_total, chave_nfce='', url_qrcode='', origem='Manual', status_leitura='Manual', observacoes='', forma_pagamento='', valor_pago=0):
    return execute(
        """INSERT INTO compras (mercado_id, data_compra, valor_total, chave_nfce, url_qrcode, origem, status_leitura, forma_pagamento, valor_pago, observacoes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (mercado_id, data_compra, valor_total, chave_nfce, url_qrcode, origem, status_leitura, forma_pagamento, valor_pago, observacoes),
    )


def update_compra(id, mercado_id, data_compra, valor_total, chave_nfce, url_qrcode, origem, status_leitura, observacoes, forma_pagamento='', valor_pago=0):
    execute(
        """UPDATE compras SET mercado_id=?, data_compra=?, valor_total=?, chave_nfce=?, url_qrcode=?, origem=?, status_leitura=?, forma_pagamento=?, valor_pago=?, observacoes=? WHERE id=?""",
        (mercado_id, data_compra, valor_total, chave_nfce, url_qrcode, origem, status_leitura, forma_pagamento, valor_pago, observacoes, id),
    )


def delete_compra(id):
    execute("DELETE FROM compras WHERE id=?", (id,))


def get_itens(compra_id=None):
    params = ()
    where = ""
    if compra_id:
        where = "WHERE i.compra_id = ?"
        params = (compra_id,)
    return query_df(f"""
        SELECT i.*, co.data_compra, m.nome AS mercado, p.nome_padronizado AS produto, c.nome AS categoria
        FROM itens_compra i
        JOIN compras co ON co.id = i.compra_id
        LEFT JOIN mercados m ON m.id = co.mercado_id
        LEFT JOIN produtos p ON p.id = i.produto_id
        LEFT JOIN categorias c ON c.id = p.categoria_id
        {where}
        ORDER BY co.data_compra DESC, i.id DESC
    """, params)


def add_item(compra_id, descricao_original, produto_id, quantidade, unidade, valor_unitario, valor_total=None, desconto=0):
    if valor_total is None:
        valor_total = float(quantidade or 0) * float(valor_unitario or 0) - float(desconto or 0)
    item_id = execute(
        """INSERT INTO itens_compra (compra_id, descricao_original, produto_id, quantidade, unidade, valor_unitario, valor_total, desconto)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (compra_id, descricao_original, produto_id, quantidade, unidade, valor_unitario, valor_total, desconto),
    )
    if descricao_original and produto_id:
        salvar_mapeamento(descricao_original, produto_id, compra_id)
    return item_id


def delete_item(id):
    execute("DELETE FROM itens_compra WHERE id=?", (id,))


def salvar_mapeamento(descricao_original, produto_id, compra_id):
    desc_norm = normalizar_texto(descricao_original)
    with get_conn() as conn:
        mercado = conn.execute("SELECT mercado_id FROM compras WHERE id=?", (compra_id,)).fetchone()
        mercado_id = mercado[0] if mercado else None
        exists = conn.execute(
            "SELECT id FROM mapeamentos_produto WHERE descricao_original=? AND produto_id=? AND IFNULL(mercado_id,0)=IFNULL(?,0)",
            (desc_norm, produto_id, mercado_id),
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO mapeamentos_produto (descricao_original, produto_id, mercado_id, confianca) VALUES (?, ?, ?, 1)",
                (desc_norm, produto_id, mercado_id),
            )


def sugerir_produto(descricao_original):
    desc_norm = normalizar_texto(descricao_original)
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT p.id, p.nome_padronizado
            FROM mapeamentos_produto mp
            JOIN produtos p ON p.id = mp.produto_id
            WHERE mp.descricao_original = ?
            ORDER BY mp.confianca DESC, mp.id DESC
            LIMIT 1
            """,
            (desc_norm,),
        ).fetchone()
        if row:
            return dict(row)
    return None


def dashboard_data():
    compras = get_compras()
    itens = get_itens()
    return compras, itens


def get_categoria_id_por_nome(nome):
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM categorias WHERE nome = ? LIMIT 1", (nome,)).fetchone()
        return int(row[0]) if row else None


def get_or_create_mercado(nome, cnpj='', cidade='', bairro='', uf=''):
    nome = (nome or '').strip() or 'Mercado não identificado'
    cnpj = (cnpj or '').strip()
    cidade = (cidade or '').strip()
    bairro = (bairro or '').strip()
    uf = (uf or '').strip().upper()
    with get_conn() as conn:
        if cnpj:
            row = conn.execute("SELECT * FROM mercados WHERE REPLACE(REPLACE(REPLACE(cnpj,'.',''),'/',''),'-','') = REPLACE(REPLACE(REPLACE(?,'.',''),'/',''),'-','') LIMIT 1", (cnpj,)).fetchone()
            if row:
                # Atualiza dados vazios sem duplicar o mercado.
                conn.execute(
                    "UPDATE mercados SET nome=COALESCE(NULLIF(?,''),nome), cidade=COALESCE(NULLIF(?,''),cidade), bairro=COALESCE(NULLIF(?,''),bairro), uf=COALESCE(NULLIF(?,''),uf) WHERE id=?",
                    (nome, cidade, bairro, uf, _row_get(row, 'id')),
                )
                return int(_row_get(row, 'id'))
        row = conn.execute("SELECT * FROM mercados WHERE UPPER(nome) = UPPER(?) LIMIT 1", (nome,)).fetchone()
        if row:
            if cnpj and not (_row_get(row, 'cnpj') or '').strip():
                conn.execute("UPDATE mercados SET cnpj=? WHERE id=?", (cnpj, _row_get(row, 'id')))
            return int(_row_get(row, 'id'))
        cur = conn.execute("INSERT INTO mercados (nome, cnpj, cidade, bairro, uf) VALUES (?, ?, ?, ?, ?)", (nome, cnpj, cidade, bairro, uf))
        return int(cur.lastrowid)



def _tokens(texto):
    return [t for t in normalizar_texto(texto).split() if len(t) >= 3]


MARCAS_CONHECIDAS = [
    'ITALAC', 'PIRACANJUBA', 'NESTLE', 'NINHO', 'YOKI', 'SADIA', 'PERDIGAO',
    'SEARA', 'FRIBOI', 'AURORA', 'CAMIL', 'TIO JOAO', 'KICALDO', 'UNIAO',
    'QUALITA', 'TAUSTE', 'COCA COLA', 'PEPSI', 'ANTARCTICA', 'FANTA', 'SPRITE',
    'DANONE', 'BATAVO', 'VIGOR', 'PRESIDENT', 'PILAO', 'MELITTA', '3 CORACOES',
    'BOMBRIL', 'YPE', 'OMO', 'ARIEL', 'VEJA', 'MINUANO', 'ASSOLAN', 'DOVE',
    'REXONA', 'COLGATE', 'SENSODYNE', 'PALMOLIVE', 'JOHNSON', 'NEUTROGENA',
    'MONSTER', 'RED BULL', 'LOBATO', 'ELEFANTE', 'VISCONTI', 'BAUDUCCO',
    'KELLOGGS', 'NESCAU', 'TODDY', 'HELLMANNS', 'HEINZ', 'AJINOMOTO'
]

ABREVIACOES = {
    'TRADICIO': 'Tradicional',
    'TRAD': 'Tradicional',
    'INT': 'Integral',
    'INTEG': 'Integral',
    'DESNAT': 'Desnatado',
    'SEMI': 'Semidesnatado',
    'COND': 'Condensado',
    'REF': 'Refinado',
    'CR': 'Creme',
    'QJO': 'Queijo',
    'MUSSAREL': 'Mussarela',
    'MUSSARELA': 'Mussarela',
    'PCT': 'Pacote',
    'CX': 'Caixa',
    'UND': 'Unidade',
    'UN': 'Unidade',
    'KG': 'kg',
    'LT': 'L',
    'L': 'L',
    'ML': 'ml',
    'GR': 'g',
    'G': 'g',
}

PALAVRAS_DESCARTAR = {
    'PC', 'UN', 'PT', 'KG', 'LT', 'ML', 'GR', 'G', 'FD', 'CX', 'PCT', 'EMB',
    'COD', 'CODIGO', 'ITEM', 'PROMO', 'OFERTA'
}

REGRAS_CATEGORIA = [
    ('Laticínios', ['LEITE', 'IOGUR', 'QUEIJO', 'MUSSARELA', 'MOZZARELA', 'REQUEIJAO', 'MANTEIGA', 'MARGARINA', 'CREME DE LEITE', 'LEITE COND', 'NESTLE', 'DANONE', 'BATAVO', 'VIGOR', 'PRESIDENT']),
    ('Bebidas', ['REFRIG', 'COCA', 'GUARANA', 'SUCO', 'AGUA', 'CERVEJA', 'ENERG', 'BEBIDA', 'VINHO', 'CHA', 'ISOTONICO', 'MONSTER', 'RED BULL', 'LOBATO']),
    ('Hortifruti', ['BANANA', 'MACA', 'MELAO', 'MELANCIA', 'LARANJA', 'LIMAO', 'BATATA', 'CEBOLA', 'TOMATE', 'ALFACE', 'CENOURA', 'ABOB', 'UVA', 'MAMAO', 'MANGA', 'VERDURA', 'FRUTA', 'LEGUME']),
    ('Carnes', ['CARNE', 'FRANGO', 'LINGUICA', 'BOV', 'SUINO', 'PEIXE', 'FILE', 'PATINHO', 'ACEM', 'COXAO', 'BACON', 'PRESUNTO', 'SALSICHA', 'STROGONOFF', 'MUSCULO', 'COSTELA']),
    ('Limpeza', ['DETERG', 'SABAO', 'AMACIANTE', 'DESINF', 'AGUA SANIT', 'LIMP', 'ESPONJA', 'ALCOOL', 'CLORO', 'VEJA', 'BOMBRIL', 'YPE', 'OMO', 'ARIEL', 'ASSOLAN']),
    ('Higiene', ['SHAMPOO', 'CONDIC', 'SABONETE', 'CREME DENT', 'PASTA DENT', 'ESCOVA', 'PAPEL HIG', 'DESOD', 'ABSORVENTE', 'FRALDA', 'DOVE', 'REXONA', 'COLGATE']),
    ('Pet', ['RACAO', 'PET', 'GATO', 'CAO', 'CACHORRO', 'AREIA HIG']),
    ('Farmácia', ['DOR', 'DIPIRONA', 'PARACETAMOL', 'MEDIC', 'CURATIVO', 'VITAMINA']),
    ('Alimentos secundários', ['SALGAD', 'BOLACHA', 'BISCOITO', 'COOKIE', 'WAFER', 'CHIPS', 'SNACK', 'DORITOS', 'RUFFLES', 'FANDANGOS', 'CHEETOS', 'TORCIDA', 'ELMA', 'BATATA FRITA', 'BATATA PALHA', 'CHOCOLATE', 'DOCE', 'BALA', 'PIRULITO', 'BOMBOM', 'SORVETE', 'PIPOCA', 'AMENDOIM']),
    ('Alimentos básicos', ['ARROZ', 'FEIJAO', 'ACUC', 'CAFE', 'OLEO', 'FARINHA', 'MACARRAO', 'SAL', 'OVO', 'PAO', 'MOLHO', 'EXTRATO', 'MAIONESE', 'KETCHUP', 'CEREAL', 'AVEIA', 'YOKI', 'VISCONTI', 'UNIAO', 'ELEFANTE']),
]


def _title_produto(texto):
    texto = (texto or '').strip()
    if not texto:
        return ''
    partes = []
    marcas_norm = {normalizar_texto(m): m for m in MARCAS_CONHECIDAS}
    for token in normalizar_texto(texto).split():
        if token in PALAVRAS_DESCARTAR:
            continue
        if token in ABREVIACOES:
            partes.append(ABREVIACOES[token])
        elif token in marcas_norm:
            partes.append(marcas_norm[token].title())
        elif token.isdigit():
            partes.append(token)
        else:
            partes.append(token.capitalize())
    # remove duplicatas consecutivas preservando ordem
    final = []
    for parte in partes:
        if not final or normalizar_texto(final[-1]) != normalizar_texto(parte):
            final.append(parte)
    return ' '.join(final)


def extrair_marca(nome_produto):
    nome_norm = normalizar_texto(nome_produto)
    # prioriza marcas com mais palavras para evitar conflito parcial
    for marca in sorted(MARCAS_CONHECIDAS, key=lambda x: len(x), reverse=True):
        if normalizar_texto(marca) in nome_norm:
            return marca.title()
    return ''


def padronizar_nome_produto(descricao_original, unidade=''):
    """Transforma a descrição fiscal em um nome mais legível.

    Não tenta inventar produto demais. A regra principal é limpar abreviações comuns,
    preservar marca quando encontrada e evitar criar duplicatas visualmente diferentes.
    """
    desc = (descricao_original or '').strip()
    if not desc:
        return ''
    nome = _title_produto(desc)
    # Padroniza algumas expressões comuns depois do title.
    ajustes = {
        'Acuc': 'Açúcar',
        'Cafe': 'Café',
        'Pao': 'Pão',
        'Agua': 'Água',
        'Qjo': 'Queijo',
        'Ovo E Bco': 'Ovo Branco',
        'Bco': 'Branco',
        'Pa': '',
    }
    for antigo, novo in ajustes.items():
        nome = nome.replace(antigo, novo).strip()
    nome = ' '.join(nome.split())
    return nome or desc


def _score_similaridade(a, b):
    ta = set(_tokens(a))
    tb = set(_tokens(b))
    if not ta or not tb:
        return 0
    inter = ta.intersection(tb)
    return len(inter) / max(len(ta.union(tb)), 1)


def buscar_produto_parecido(nome_produto, unidade=''):
    nome_norm = normalizar_texto(nome_produto)
    tokens = set(_tokens(nome_produto))
    unidade_norm = normalizar_texto(unidade)
    best = None
    best_score = 0
    with get_conn() as conn:
        rows = conn.execute("SELECT id, nome_padronizado, categoria_id, unidade_padrao FROM produtos WHERE ativo = 1").fetchall()
        for row in rows:
            row_norm = normalizar_texto(_row_get(row, 'nome_padronizado'))
            if row_norm == nome_norm:
                return _row_to_dict(row, ['id','nome_padronizado','marca','categoria_id','unidade_padrao','quantidade_padrao','ativo','criado_em']), 1.0
            score = _score_similaridade(nome_produto, _row_get(row, 'nome_padronizado'))
            # Pequeno bônus quando a unidade bate.
            if unidade_norm and normalizar_texto(_row_get(row, 'unidade_padrao') or '') == unidade_norm:
                score += 0.08
            if score > best_score:
                best_score = score
                best = row
    return (_row_to_dict(best, ['id','nome_padronizado','marca','categoria_id','unidade_padrao','quantidade_padrao','ativo','criado_em']), best_score) if best else (None, 0)


def inferir_categoria_id(nome_produto):
    """Tenta categorizar automaticamente um produto novo.

    Ordem de decisão:
    1) Produto parecido já cadastrado: reaproveita a categoria dele.
    2) Regras por palavras-chave de supermercado.
    3) Categoria Outros como fallback seguro.
    """
    nome = (nome_produto or '').strip()
    nome_norm = normalizar_texto(nome)

    parecido, score = buscar_produto_parecido(nome)
    if parecido and score >= 0.42 and parecido.get('categoria_id'):
        return int(parecido['categoria_id'])

    for categoria, palavras in REGRAS_CATEGORIA:
        for palavra in palavras:
            if normalizar_texto(palavra) in nome_norm:
                cat = get_categoria_id_por_nome(categoria)
                if cat:
                    return cat

    return get_categoria_id_por_nome('Outros')


def get_or_create_produto_simples(nome, unidade='un'):
    """Cria/reutiliza produto com padronização e categorização automática.

    - Se a descrição já foi mapeada antes, reaproveita o mesmo produto.
    - Se houver produto parecido com boa confiança, reaproveita esse produto para evitar duplicidade.
    - Se for novo, cria com nome limpo, marca extraída e categoria sugerida.
    """
    nome = (nome or '').strip()
    if not nome:
        return None

    sugestao = sugerir_produto(nome)
    if sugestao and sugestao.get('id'):
        return int(sugestao['id'])

    nome_padronizado = padronizar_nome_produto(nome, unidade)
    parecido, score = buscar_produto_parecido(nome_padronizado, unidade)
    if parecido and score >= 0.55:
        return int(parecido['id'])

    cat_id = inferir_categoria_id(nome_padronizado)
    marca = extrair_marca(nome_padronizado)
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO produtos (nome_padronizado, marca, categoria_id, unidade_padrao, quantidade_padrao) VALUES (?, ?, ?, ?, ?)",
            (nome_padronizado, marca, cat_id, unidade or 'un', 1),
        )
        return int(cur.lastrowid)


def recategorizar_produtos_sem_categoria():
    """Reprocessa produtos existentes que estão em Outros/Sem categoria."""
    outros_id = get_categoria_id_por_nome('Outros')
    atualizados = 0
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, nome_padronizado, categoria_id FROM produtos WHERE ativo = 1"
        ).fetchall()
        for row in rows:
            categoria_atual = _row_get(row, 'categoria_id')
            if categoria_atual and outros_id and int(categoria_atual) != int(outros_id):
                continue
            nova_categoria = inferir_categoria_id(_row_get(row, 'nome_padronizado'))
            if nova_categoria and (not categoria_atual or int(nova_categoria) != int(categoria_atual)):
                conn.execute("UPDATE produtos SET categoria_id=? WHERE id=?", (nova_categoria, _row_get(row, 'id')))
                atualizados += 1
    return atualizados

def add_compra_com_itens_nfce(mercado_nome, cnpj, data_compra, valor_total, chave_nfce, url_qrcode, itens, observacoes='', forma_pagamento='', valor_pago=0):
    """Registra compra NFC-e e todos os itens.

    Se algum item falhar, remove a compra parcial para evitar o problema
    de compra salva com apenas 1 item.
    """
    mercado_id = get_or_create_mercado(mercado_nome, cnpj) if mercado_nome or cnpj else None
    status = 'Conferida' if itens else 'Pendente'
    compra_id = add_compra(mercado_id, data_compra, valor_total, chave_nfce, url_qrcode, 'QR Code', status, observacoes, forma_pagamento, valor_pago)
    try:
        for item in itens or []:
            desc = (item.get('descricao_original') or '').strip()
            if not desc:
                continue
            unidade = item.get('unidade') or 'un'
            produto_id = get_or_create_produto_simples(desc, unidade)
            add_item(
                compra_id,
                desc,
                produto_id,
                float(item.get('quantidade') or 1),
                unidade,
                float(item.get('valor_unitario') or 0),
                float(item.get('valor_total') or 0),
                float(item.get('desconto') or 0),
            )
    except Exception:
        # Evita registro parcial quando o banco online falha no meio do loop.
        try:
            execute("DELETE FROM itens_compra WHERE compra_id=?", (compra_id,))
            execute("DELETE FROM compras WHERE id=?", (compra_id,))
        except Exception:
            pass
        raise
    return compra_id


def resumo_compra(compra_id):
    compra = get_compra(compra_id)
    itens = get_itens(compra_id)
    total_itens = float(itens['valor_total'].sum()) if not itens.empty else 0.0
    qtd_itens = int(len(itens)) if not itens.empty else 0
    diferenca = float((compra or {}).get('valor_total') or 0) - total_itens if compra else 0.0
    return {
        'compra': compra,
        'itens': itens,
        'total_itens': total_itens,
        'qtd_itens': qtd_itens,
        'diferenca': diferenca,
    }
