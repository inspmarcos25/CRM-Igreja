"""
Módulo de Mural & Comunicação Interna
Posts, avisos, pedidos de oração e interações
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database.db import get_connection
from modules.auth import get_igreja_id, get_usuario_atual, registrar_log
from config.settings import formatar_data_br

# ==================== FUNÇÕES DE DADOS ====================

def get_posts(tipo: str = None, destino: str = None, limite: int = 20) -> list:
    """Busca posts do mural"""
    igreja_id = get_igreja_id()
    
    query = '''
        SELECT p.*, 
               u.nome as autor_nome,
               m.nome as ministerio_nome,
               c.nome as celula_nome,
               (SELECT COUNT(*) FROM mural_curtidas mc WHERE mc.post_id = p.id) as total_curtidas,
               (SELECT COUNT(*) FROM mural_comentarios mcom WHERE mcom.post_id = p.id) as total_comentarios
        FROM mural_posts p
        JOIN usuarios u ON p.autor_id = u.id
        LEFT JOIN ministerios m ON p.ministerio_id = m.id
        LEFT JOIN celulas c ON p.celula_id = c.id
        WHERE p.igreja_id = ?
        AND (p.data_expiracao IS NULL OR p.data_expiracao >= date('now'))
    '''
    params = [igreja_id]
    
    if tipo:
        query += ' AND p.tipo = ?'
        params.append(tipo)
    
    if destino and destino != 'todos':
        query += ' AND p.destino = ?'
        params.append(destino)
    
    query += ' ORDER BY p.fixado DESC, p.data_cadastro DESC LIMIT ?'
    params.append(limite)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def criar_post(dados: dict) -> int:
    """Cria um novo post no mural"""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO mural_posts (igreja_id, autor_id, titulo, conteudo, tipo, destino,
                                    ministerio_id, celula_id, fixado, permite_comentarios, data_expiracao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (igreja_id, usuario['id'], dados.get('titulo'), dados['conteudo'],
              dados.get('tipo', 'aviso'), dados.get('destino', 'todos'),
              dados.get('ministerio_id'), dados.get('celula_id'),
              dados.get('fixado', 0), dados.get('permite_comentarios', 1),
              dados.get('data_expiracao')))
        
        registrar_log(usuario['id'], igreja_id, 'mural.criar', f"Post criado")
        return cursor.lastrowid

def curtir_post(post_id: int) -> bool:
    """Curte ou descurte um post"""
    usuario = get_usuario_atual()
    pessoa_id = usuario.get('id')
    
    if not pessoa_id:
        return False
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Verificar se já curtiu
        cursor.execute('''
            SELECT id FROM mural_curtidas WHERE post_id = ? AND pessoa_id = ?
        ''', (post_id, pessoa_id))
        
        if cursor.fetchone():
            # Descurtir
            cursor.execute('''
                DELETE FROM mural_curtidas WHERE post_id = ? AND pessoa_id = ?
            ''', (post_id, pessoa_id))
            return False
        else:
            # Curtir
            cursor.execute('''
                INSERT INTO mural_curtidas (post_id, pessoa_id) VALUES (?, ?)
            ''', (post_id, pessoa_id))
            return True

def comentar_post(post_id: int, conteudo: str) -> int:
    """Adiciona comentário a um post"""
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO mural_comentarios (post_id, autor_id, conteudo)
            VALUES (?, ?, ?)
        ''', (post_id, usuario['id'], conteudo))
        return cursor.lastrowid

def get_comentarios(post_id: int) -> list:
    """Busca comentários de um post"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.*, u.nome as autor_nome
            FROM mural_comentarios c
            JOIN usuarios u ON c.autor_id = u.id
            WHERE c.post_id = ?
            ORDER BY c.data_cadastro ASC
        ''', (post_id,))
        return [dict(row) for row in cursor.fetchall()]

def usuario_curtiu(post_id: int) -> bool:
    """Verifica se usuário atual curtiu o post"""
    usuario = get_usuario_atual()
    pessoa_id = usuario.get('id')
    
    if not pessoa_id:
        return False
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM mural_curtidas WHERE post_id = ? AND pessoa_id = ?
        ''', (post_id, pessoa_id))
        return cursor.fetchone() is not None

def excluir_post(post_id: int):
    """Exclui um post"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM mural_curtidas WHERE post_id = ?', (post_id,))
        cursor.execute('DELETE FROM mural_comentarios WHERE post_id = ?', (post_id,))
        cursor.execute('DELETE FROM mural_posts WHERE id = ? AND igreja_id = ?', (post_id, igreja_id))

# ==================== PEDIDOS DE ORAÇÃO ====================

def get_pedidos_oracao(status: str = 'ativo') -> list:
    """Busca pedidos de oração"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT po.*, u.nome as autor_nome
            FROM pedidos_oracao_mural po
            JOIN usuarios u ON po.autor_id = u.id
            WHERE po.igreja_id = ? AND po.status = ?
            ORDER BY po.data_cadastro DESC
        ''', (igreja_id, status))
        return [dict(row) for row in cursor.fetchall()]

def criar_pedido_oracao(pedido: str, anonimo: bool = False) -> int:
    """Cria um pedido de oração"""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO pedidos_oracao_mural (igreja_id, autor_id, pedido, anonimo)
            VALUES (?, ?, ?, ?)
        ''', (igreja_id, usuario['id'], pedido, 1 if anonimo else 0))
        return cursor.lastrowid

def orar_por_pedido(pedido_id: int):
    """Registra que está orando por um pedido"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE pedidos_oracao_mural
            SET total_orando = total_orando + 1
            WHERE id = ?
        ''', (pedido_id,))

def marcar_respondido(pedido_id: int, testemunho: str = None):
    """Marca pedido como respondido"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE pedidos_oracao_mural
            SET status = 'respondido', data_resposta = ?, testemunho = ?
            WHERE id = ?
        ''', (date.today(), testemunho, pedido_id))

# ==================== RENDERIZAÇÃO ====================

def render_mural():
    """Função principal do módulo de mural"""
    st.title("📣 Mural & Comunicação")
    
    tab1, tab2, tab3 = st.tabs([
        "📰 Mural",
        "🙏 Pedidos de Oração",
        "➕ Novo Post"
    ])
    
    with tab1:
        render_feed_mural()
    
    with tab2:
        render_pedidos_oracao()
    
    with tab3:
        render_novo_post()

def render_feed_mural():
    """Renderiza feed do mural"""
    st.subheader("📰 Feed de Notícias")
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        tipo_filtro = st.selectbox(
            "Tipo",
            options=['Todos', 'aviso', 'devocional', 'testemunho', 'anuncio'],
            format_func=lambda x: {'Todos': 'Todos', 'aviso': '📢 Avisos', 
                                   'devocional': '📖 Devocionais', 'testemunho': '✨ Testemunhos',
                                   'anuncio': '📣 Anúncios'}.get(x, x)
        )
    
    posts = get_posts(tipo=tipo_filtro if tipo_filtro != 'Todos' else None)
    
    if not posts:
        st.info("Nenhum post no mural.")
        return
    
    for post in posts:
        render_card_post(post)

def render_card_post(post: dict):
    """Renderiza card de um post"""
    usuario = get_usuario_atual()
    
    # Ícones por tipo
    icones = {
        'aviso': '📢',
        'devocional': '📖',
        'testemunho': '✨',
        'anuncio': '📣'
    }
    
    fixado = "📌 " if post.get('fixado') else ""
    
    with st.container():
        # Cabeçalho
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"""
                <div style='margin-bottom: 0.5rem;'>
                    <strong>{fixado}{icones.get(post['tipo'], '📝')} {post.get('titulo', 'Sem título')}</strong>
                </div>
            """, unsafe_allow_html=True)
            st.caption(f"👤 {post['autor_nome']} • {formatar_data_br(str(post['data_cadastro'])[:10])}")
        
        with col2:
            if post.get('ministerio_nome'):
                st.caption(f"🎵 {post['ministerio_nome']}")
        
        # Conteúdo
        st.write(post['conteudo'])
        
        # Ações
        col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
        
        with col1:
            curtiu = usuario_curtiu(post['id'])
            icone_curtir = "❤️" if curtiu else "🤍"
            if st.button(f"{icone_curtir} {post['total_curtidas']}", key=f"like_{post['id']}"):
                curtir_post(post['id'])
                st.rerun()
        
        with col2:
            if st.button(f"💬 {post['total_comentarios']}", key=f"com_{post['id']}"):
                st.session_state[f"show_comments_{post['id']}"] = not st.session_state.get(f"show_comments_{post['id']}", False)
                st.rerun()
        
        with col3:
            if usuario.get('id') == post['autor_id']:
                if st.button("🗑️", key=f"del_{post['id']}", help="Excluir"):
                    excluir_post(post['id'])
                    st.rerun()
        
        # Comentários
        if st.session_state.get(f"show_comments_{post['id']}"):
            st.markdown("---")
            comentarios = get_comentarios(post['id'])
            
            for com in comentarios:
                st.markdown(f"""
                    <div style='background: #f5f5f5; padding: 0.5rem; border-radius: 5px; margin: 0.3rem 0;'>
                        <small><strong>{com['autor_nome']}</strong></small><br>
                        <small>{com['conteudo']}</small>
                    </div>
                """, unsafe_allow_html=True)
            
            # Novo comentário
            if post['permite_comentarios']:
                novo_com = st.text_input("Adicionar comentário", key=f"input_com_{post['id']}")
                if st.button("Enviar", key=f"btn_com_{post['id']}"):
                    if novo_com:
                        comentar_post(post['id'], novo_com)
                        st.rerun()
        
        st.markdown("<hr style='margin: 1rem 0; opacity: 0.2;'>", unsafe_allow_html=True)

def render_pedidos_oracao():
    """Renderiza pedidos de oração"""
    st.subheader("🙏 Pedidos de Oração")
    
    # Novo pedido
    with st.expander("➕ Fazer um Pedido de Oração", expanded=False):
        with st.form("novo_pedido_oracao"):
            pedido = st.text_area("Seu pedido de oração", height=100)
            anonimo = st.checkbox("Publicar de forma anônima")
            
            if st.form_submit_button("🙏 Enviar Pedido", use_container_width=True):
                if pedido:
                    criar_pedido_oracao(pedido, anonimo)
                    st.success("Pedido enviado! A igreja está orando por você.")
                    st.rerun()
    
    # Tabs de status
    tab_ativos, tab_respondidos = st.tabs(["⏳ Ativos", "✅ Respondidos"])
    
    with tab_ativos:
        pedidos = get_pedidos_oracao('ativo')
        
        if not pedidos:
            st.info("Nenhum pedido de oração ativo no momento.")
        
        for p in pedidos:
            autor = "Anônimo" if p['anonimo'] else p['autor_nome']
            
            st.markdown(f"""
                <div style='background: #f8f9fa; padding: 1rem; border-radius: 10px; 
                            margin-bottom: 1rem; border-left: 4px solid #3498db;'>
                    <small>👤 {autor} • {formatar_data_br(str(p['data_cadastro'])[:10])}</small>
                    <p style='margin: 0.5rem 0;'>{p['pedido']}</p>
                    <small>🙏 {p['total_orando']} pessoas orando</small>
                </div>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🙏 Estou Orando", key=f"orar_{p['id']}", use_container_width=True):
                    orar_por_pedido(p['id'])
                    st.success("Obrigado por orar!")
                    st.rerun()
            
            with col2:
                usuario = get_usuario_atual()
                if usuario.get('id') == p['autor_id']:
                    if st.button("✅ Deus Respondeu!", key=f"resp_{p['id']}", use_container_width=True):
                        st.session_state[f"testemunho_{p['id']}"] = True
            
            # Modal testemunho
            if st.session_state.get(f"testemunho_{p['id']}"):
                testemunho = st.text_area("Compartilhe como Deus respondeu (opcional):", key=f"test_txt_{p['id']}")
                if st.button("Confirmar", key=f"conf_{p['id']}"):
                    marcar_respondido(p['id'], testemunho)
                    del st.session_state[f"testemunho_{p['id']}"]
                    st.success("Glória a Deus! Testemunho registrado.")
                    st.rerun()
    
    with tab_respondidos:
        pedidos = get_pedidos_oracao('respondido')
        
        if not pedidos:
            st.info("Nenhum testemunho de oração respondida ainda.")
        
        for p in pedidos:
            autor = "Anônimo" if p['anonimo'] else p['autor_nome']
            
            st.markdown(f"""
                <div style='background: #d4edda; padding: 1rem; border-radius: 10px; 
                            margin-bottom: 1rem; border-left: 4px solid #28a745;'>
                    <small>👤 {autor} • Respondido em {formatar_data_br(p['data_resposta'])}</small>
                    <p><strong>Pedido:</strong> {p['pedido']}</p>
                    {f"<p><strong>✨ Testemunho:</strong> {p['testemunho']}</p>" if p.get('testemunho') else ""}
                </div>
            """, unsafe_allow_html=True)

def render_novo_post():
    """Renderiza formulário de novo post"""
    st.subheader("➕ Criar Novo Post")
    
    with st.form("novo_post_mural"):
        titulo = st.text_input("Título")
        conteudo = st.text_area("Conteúdo *", height=150)
        
        col1, col2 = st.columns(2)
        with col1:
            tipo = st.selectbox(
                "Tipo",
                options=['aviso', 'devocional', 'testemunho', 'anuncio'],
                format_func=lambda x: {'aviso': '📢 Aviso', 'devocional': '📖 Devocional',
                                       'testemunho': '✨ Testemunho', 'anuncio': '📣 Anúncio'}[x]
            )
        
        with col2:
            destino = st.selectbox(
                "Destinatário",
                options=['todos', 'lideres', 'ministerio', 'celula'],
                format_func=lambda x: {'todos': '👥 Todos', 'lideres': '👔 Líderes',
                                       'ministerio': '🎵 Ministério', 'celula': '🏠 Célula'}[x]
            )
        
        # Se destino específico
        ministerio_id = None
        celula_id = None
        
        if destino == 'ministerio':
            from modules.ministerios import get_ministerios
            ministerios = get_ministerios()
            ministerio = st.selectbox("Selecione o Ministério", options=ministerios,
                                     format_func=lambda x: x['nome'])
            if ministerio:
                ministerio_id = ministerio['id']
        
        elif destino == 'celula':
            from modules.ministerios import get_celulas
            celulas = get_celulas()
            celula = st.selectbox("Selecione a Célula", options=celulas,
                                 format_func=lambda x: x['nome'])
            if celula:
                celula_id = celula['id']
        
        col3, col4 = st.columns(2)
        with col3:
            fixado = st.checkbox("📌 Fixar no topo")
        with col4:
            permite_comentarios = st.checkbox("💬 Permitir comentários", value=True)
        
        data_expiracao = st.date_input(
            "Data de expiração (opcional)",
            value=None,
            format="DD/MM/YYYY"
        )
        
        submit = st.form_submit_button("📤 Publicar", use_container_width=True)
        
        if submit:
            if not conteudo:
                st.error("Conteúdo é obrigatório!")
            else:
                criar_post({
                    'titulo': titulo,
                    'conteudo': conteudo,
                    'tipo': tipo,
                    'destino': destino,
                    'ministerio_id': ministerio_id,
                    'celula_id': celula_id,
                    'fixado': 1 if fixado else 0,
                    'permite_comentarios': 1 if permite_comentarios else 0,
                    'data_expiracao': data_expiracao
                })
                st.success("✅ Post publicado com sucesso!")
                st.rerun()
