"""
Módulo de Galeria de Fotos
Armazenamento e visualização de fotos de eventos
"""
import streamlit as st
import os
from datetime import datetime, date
from pathlib import Path
from database.db import get_connection
from modules.auth import get_igreja_id, get_usuario_atual, registrar_log
from config.settings import formatar_data_br

# Diretório para uploads
UPLOAD_DIR = Path("data/uploads/galeria")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ==================== FUNÇÕES DE DADOS ====================

def get_albuns() -> list:
    """Busca álbuns da igreja"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT a.*, 
                   (SELECT COUNT(*) FROM fotos WHERE album_id = a.id) as total_fotos,
                   e.nome as evento_nome
            FROM albuns a
            LEFT JOIN eventos e ON a.evento_id = e.id
            WHERE a.igreja_id = ?
            ORDER BY a.data_cadastro DESC
        ''', (igreja_id,))
        return [dict(row) for row in cursor.fetchall()]

def get_album(album_id: int) -> dict:
    """Busca um álbum específico"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT a.*, e.nome as evento_nome
            FROM albuns a
            LEFT JOIN eventos e ON a.evento_id = e.id
            WHERE a.id = ?
        ''', (album_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def salvar_album(dados: dict) -> int:
    """Cria ou atualiza um álbum"""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        if dados.get('id'):
            cursor.execute('''
                UPDATE albuns
                SET nome = ?, descricao = ?, evento_id = ?, data_evento = ?, publico = ?
                WHERE id = ? AND igreja_id = ?
            ''', (dados['nome'], dados.get('descricao'), dados.get('evento_id'),
                  dados.get('data_album'), 1 if dados.get('visibilidade') == 'publico' else 0,
                  dados['id'], igreja_id))
            return dados['id']
        else:
            cursor.execute('''
                INSERT INTO albuns (igreja_id, nome, descricao, evento_id, data_evento, publico)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (igreja_id, dados['nome'], dados.get('descricao'), dados.get('evento_id'),
                  dados.get('data_album'), 1 if dados.get('visibilidade') == 'publico' else 0))
            
            registrar_log(usuario['id'], igreja_id, 'album.criar', f"Álbum criado: {dados['nome']}")
            return cursor.lastrowid

def excluir_album(album_id: int):
    """Exclui um álbum e suas fotos"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Buscar fotos para remover arquivos
        cursor.execute('SELECT caminho FROM fotos WHERE album_id = ?', (album_id,))
        fotos = cursor.fetchall()
        
        for foto in fotos:
            try:
                arquivo = Path(foto['caminho'])
                if arquivo.exists():
                    arquivo.unlink()
            except:
                pass
        
        # Remover registros
        cursor.execute('DELETE FROM fotos WHERE album_id = ?', (album_id,))
        cursor.execute('DELETE FROM albuns WHERE id = ? AND igreja_id = ?', (album_id, igreja_id))

def get_fotos(album_id: int) -> list:
    """Busca fotos de um álbum"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT f.*, p.nome as fotografo_nome
            FROM fotos f
            LEFT JOIN pessoas p ON f.fotografo_id = p.id
            WHERE f.album_id = ?
            ORDER BY f.data_upload DESC
        ''', (album_id,))
        return [dict(row) for row in cursor.fetchall()]

def salvar_foto(album_id: int, arquivo, legenda: str = None) -> int:
    """Salva uma foto no álbum"""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    # Criar diretório do álbum
    album_dir = UPLOAD_DIR / str(igreja_id) / str(album_id)
    album_dir.mkdir(parents=True, exist_ok=True)
    
    # Gerar nome único
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    nome_arquivo = f"{timestamp}_{arquivo.name}"
    caminho = album_dir / nome_arquivo
    
    # Salvar arquivo
    with open(caminho, 'wb') as f:
        f.write(arquivo.getbuffer())
    
    # Registrar no banco
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO fotos (album_id, url, descricao)
            VALUES (?, ?, ?)
        ''', (album_id, str(caminho), legenda))
        
        return cursor.lastrowid

def excluir_foto(foto_id: int):
    """Exclui uma foto"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Buscar caminho
        cursor.execute('SELECT url FROM fotos WHERE id = ?', (foto_id,))
        foto = cursor.fetchone()
        
        if foto:
            try:
                arquivo = Path(foto['url'])
                if arquivo.exists():
                    arquivo.unlink()
            except:
                pass
        
        cursor.execute('DELETE FROM fotos WHERE id = ?', (foto_id,))

def atualizar_legenda(foto_id: int, legenda: str):
    """Atualiza legenda de uma foto"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE fotos SET descricao = ? WHERE id = ?', (legenda, foto_id))

def get_eventos_para_album() -> list:
    """Busca eventos para vincular a álbuns"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, nome, data_inicio as data FROM eventos
            WHERE igreja_id = ?
            ORDER BY data_inicio DESC
            LIMIT 50
        ''', (igreja_id,))
        return [dict(row) for row in cursor.fetchall()]

def get_estatisticas_galeria() -> dict:
    """Retorna estatísticas da galeria"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM albuns WHERE igreja_id = ?', (igreja_id,))
        total_albuns = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) FROM fotos f
            JOIN albuns a ON f.album_id = a.id
            WHERE a.igreja_id = ?
        ''', (igreja_id,))
        total_fotos = cursor.fetchone()[0]
        
        return {
            'total_albuns': total_albuns,
            'total_fotos': total_fotos
        }

# ==================== RENDERIZAÇÃO ====================

def render_galeria():
    """Função principal do módulo de galeria"""
    st.title("📸 Galeria de Fotos")
    
    tab1, tab2, tab3 = st.tabs([
        "🖼️ Álbuns",
        "➕ Novo Álbum",
        "📊 Estatísticas"
    ])
    
    with tab1:
        render_albuns()
    
    with tab2:
        render_novo_album()
    
    with tab3:
        render_estatisticas()

def render_albuns():
    """Renderiza lista de álbuns"""
    st.subheader("🖼️ Álbuns de Fotos")
    
    albuns = get_albuns()
    
    if not albuns:
        st.info("📭 Nenhum álbum criado ainda.")
        return
    
    # Grid de álbuns
    cols = st.columns(3)
    
    for i, album in enumerate(albuns):
        with cols[i % 3]:
            render_card_album(album)

def render_card_album(album: dict):
    """Renderiza card de um álbum"""
    fotos = get_fotos(album['id'])
    capa = fotos[0] if fotos else None
    
    data_exibir = album.get('data_evento') or str(album.get('data_cadastro', ''))[:10]
    
    st.markdown(f"""
        <div style='background: #f8f9fa; border-radius: 10px; padding: 1rem; margin-bottom: 1rem;
                    border: 1px solid #dee2e6;'>
            <h4 style='margin: 0;'>📁 {album['nome']}</h4>
            <p style='color: #666; font-size: 0.9rem; margin: 0.5rem 0;'>
                {album.get('descricao', '')[:100] if album.get('descricao') else ''}...
            </p>
            <small>
                📅 {formatar_data_br(data_exibir) if data_exibir else 'Sem data'} |
                📷 {album['total_fotos']} fotos
            </small>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("👁️ Ver", key=f"ver_{album['id']}"):
            st.session_state['album_selecionado'] = album['id']
            st.rerun()
    
    with col2:
        if st.button("🗑️", key=f"del_album_{album['id']}"):
            excluir_album(album['id'])
            st.rerun()

def render_visualizar_album():
    """Renderiza visualização de um álbum"""
    album_id = st.session_state.get('album_selecionado')
    
    if not album_id:
        return
    
    album = get_album(album_id)
    
    if not album:
        st.error("Álbum não encontrado!")
        return
    
    col1, col2 = st.columns([4, 1])
    with col1:
        st.subheader(f"📁 {album['nome']}")
    with col2:
        if st.button("← Voltar"):
            del st.session_state['album_selecionado']
            st.rerun()
    
    st.write(album.get('descricao', ''))
    
    if album.get('evento_nome'):
        st.info(f"📅 Evento: {album['evento_nome']}")
    
    st.markdown("---")
    
    # Upload de fotos
    st.markdown("### ➕ Adicionar Fotos")
    
    uploaded_files = st.file_uploader(
        "Selecione as fotos",
        type=['jpg', 'jpeg', 'png', 'gif'],
        accept_multiple_files=True,
        key="upload_fotos"
    )
    
    if uploaded_files:
        legenda = st.text_input("Legenda (opcional)")
        
        if st.button("📤 Enviar Fotos"):
            for arquivo in uploaded_files:
                salvar_foto(album_id, arquivo, legenda)
            st.success(f"✅ {len(uploaded_files)} foto(s) enviada(s)!")
            st.rerun()
    
    st.markdown("---")
    
    # Grade de fotos
    st.markdown("### 📷 Fotos")
    
    fotos = get_fotos(album_id)
    
    if not fotos:
        st.info("📭 Nenhuma foto neste álbum.")
        return
    
    cols = st.columns(4)
    
    for i, foto in enumerate(fotos):
        with cols[i % 4]:
            render_foto(foto)

def render_foto(foto: dict):
    """Renderiza uma foto"""
    try:
        st.image(foto['url'], caption=foto.get('descricao', ''), use_container_width=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✏️", key=f"edit_foto_{foto['id']}"):
                st.session_state[f'editando_foto_{foto["id"]}'] = True
        
        with col2:
            if st.button("🗑️", key=f"del_foto_{foto['id']}"):
                excluir_foto(foto['id'])
                st.rerun()
        
        # Editar legenda
        if st.session_state.get(f'editando_foto_{foto["id"]}'):
            nova_legenda = st.text_input("Nova legenda", value=foto.get('descricao', ''),
                                        key=f"legenda_{foto['id']}")
            if st.button("💾 Salvar", key=f"salvar_legenda_{foto['id']}"):
                atualizar_legenda(foto['id'], nova_legenda)
                del st.session_state[f'editando_foto_{foto["id"]}']
                st.rerun()
    
    except Exception as e:
        st.warning(f"⚠️ Erro ao carregar imagem")

def render_novo_album():
    """Renderiza formulário de novo álbum"""
    st.subheader("➕ Criar Novo Álbum")
    
    with st.form("novo_album"):
        nome = st.text_input("Nome do Álbum *", placeholder="Ex: Culto de Natal 2024")
        descricao = st.text_area("Descrição", placeholder="Descrição do álbum...")
        
        data_album = st.date_input("Data", format="DD/MM/YYYY")
        
        # Vincular a evento
        eventos = get_eventos_para_album()
        evento = st.selectbox(
            "Vincular a Evento (opcional)",
            options=[None] + eventos,
            format_func=lambda x: f"{x['nome']} ({formatar_data_br(x['data'])})" if x else "Nenhum"
        )
        
        visibilidade = st.radio(
            "Visibilidade",
            options=['publico', 'membros', 'lideres'],
            format_func=lambda x: {'publico': '🌐 Público', 'membros': '👥 Apenas Membros',
                                   'lideres': '👑 Apenas Líderes'}[x],
            horizontal=True
        )
        
        submit = st.form_submit_button("💾 Criar Álbum", use_container_width=True)
        
        if submit:
            if not nome:
                st.error("Nome é obrigatório!")
            else:
                album_id = salvar_album({
                    'nome': nome,
                    'descricao': descricao,
                    'data_album': data_album,
                    'evento_id': evento['id'] if evento else None,
                    'visibilidade': visibilidade
                })
                st.success("✅ Álbum criado com sucesso!")
                st.session_state['album_selecionado'] = album_id
                st.rerun()

def render_estatisticas():
    """Renderiza estatísticas da galeria"""
    st.subheader("📊 Estatísticas da Galeria")
    
    stats = get_estatisticas_galeria()
    
    col1, col2 = st.columns(2)
    col1.metric("📁 Total de Álbuns", stats['total_albuns'])
    col2.metric("📷 Total de Fotos", stats['total_fotos'])
    
    st.markdown("---")
    
    # Últimos álbuns
    st.markdown("### 📋 Últimos Álbuns")
    
    albuns = get_albuns()[:10]
    
    if albuns:
        for album in albuns:
            data_exibir = album.get('data_evento') or str(album.get('data_cadastro', ''))[:10]
            st.markdown(f"""
                <div style='background: #f8f9fa; padding: 0.5rem; border-radius: 5px; margin-bottom: 0.3rem;'>
                    <strong>{album['nome']}</strong> | 
                    📷 {album['total_fotos']} fotos |
                    📅 {formatar_data_br(data_exibir) if data_exibir else 'Sem data'}
                </div>
            """, unsafe_allow_html=True)

# Wrapper para verificar álbum selecionado
def render():
    """Renderiza o módulo de galeria"""
    if st.session_state.get('album_selecionado'):
        render_visualizar_album()
    else:
        render_galeria()
