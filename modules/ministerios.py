"""
Módulo de Ministérios, Células e Pequenos Grupos
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date
from database.db import get_connection
from modules.auth import get_igreja_id, get_usuario_atual, registrar_log
from config.settings import formatar_data_br

# ========================================
# FUNÇÕES DE MINISTÉRIOS
# ========================================

def get_ministerios() -> list:
    """Busca todos os ministérios da igreja"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT m.*,
                   l.nome as lider_nome,
                   vl.nome as vice_lider_nome,
                   (SELECT COUNT(*) FROM pessoa_ministerios pm WHERE pm.ministerio_id = m.id AND pm.ativo = 1) as total_membros
            FROM ministerios m
            LEFT JOIN pessoas l ON m.lider_id = l.id
            LEFT JOIN pessoas vl ON m.vice_lider_id = vl.id
            WHERE m.igreja_id = ? AND m.ativo = 1
            ORDER BY m.nome
        ''', (igreja_id,))
        return [dict(row) for row in cursor.fetchall()]

def get_ministerio(ministerio_id: int) -> dict:
    """Busca um ministério específico"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT m.*,
                   l.nome as lider_nome,
                   vl.nome as vice_lider_nome
            FROM ministerios m
            LEFT JOIN pessoas l ON m.lider_id = l.id
            LEFT JOIN pessoas vl ON m.vice_lider_id = vl.id
            WHERE m.id = ? AND m.igreja_id = ?
        ''', (ministerio_id, igreja_id))
        row = cursor.fetchone()
        return dict(row) if row else None

def salvar_ministerio(dados: dict) -> int:
    """Salva ou atualiza um ministério"""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        if dados.get('id'):
            cursor.execute('''
                UPDATE ministerios
                SET nome = ?, descricao = ?, lider_id = ?, vice_lider_id = ?, cor = ?
                WHERE id = ? AND igreja_id = ?
            ''', (dados['nome'], dados.get('descricao'), dados.get('lider_id'),
                  dados.get('vice_lider_id'), dados.get('cor', '#3498db'),
                  dados['id'], igreja_id))
            registrar_log(usuario['id'], igreja_id, 'ministerio.atualizar', f"Ministério {dados['id']} atualizado")
            return dados['id']
        else:
            cursor.execute('''
                INSERT INTO ministerios (igreja_id, nome, descricao, lider_id, vice_lider_id, cor)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (igreja_id, dados['nome'], dados.get('descricao'), dados.get('lider_id'),
                  dados.get('vice_lider_id'), dados.get('cor', '#3498db')))
            registrar_log(usuario['id'], igreja_id, 'ministerio.criar', f"Ministério criado")
            return cursor.lastrowid

def get_membros_ministerio(ministerio_id: int) -> list:
    """Busca membros de um ministério"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.*, pm.funcao, pm.data_entrada
            FROM pessoas p
            JOIN pessoa_ministerios pm ON p.id = pm.pessoa_id
            WHERE pm.ministerio_id = ? AND pm.ativo = 1
            ORDER BY pm.funcao, p.nome
        ''', (ministerio_id,))
        return [dict(row) for row in cursor.fetchall()]

def adicionar_membro_ministerio(pessoa_id: int, ministerio_id: int, funcao: str = 'membro'):
    """Adiciona uma pessoa a um ministério"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO pessoa_ministerios (pessoa_id, ministerio_id, funcao, data_entrada, ativo)
            VALUES (?, ?, ?, ?, 1)
        ''', (pessoa_id, ministerio_id, funcao, date.today()))

def remover_membro_ministerio(pessoa_id: int, ministerio_id: int):
    """Remove (desativa) membro de um ministério"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE pessoa_ministerios
            SET ativo = 0, data_saida = ?
            WHERE pessoa_id = ? AND ministerio_id = ? AND ativo = 1
        ''', (date.today(), pessoa_id, ministerio_id))

# ========================================
# FUNÇÕES DE CÉLULAS
# ========================================

def get_celulas() -> list:
    """Busca todas as células da igreja"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.*,
                   l.nome as lider_nome,
                   cl.nome as co_lider_nome,
                   a.nome as anfitriao_nome,
                   r.nome as rede_nome,
                   (SELECT COUNT(*) FROM pessoa_celulas pc WHERE pc.celula_id = c.id AND pc.ativo = 1) as total_membros,
                   (SELECT AVG(total_presentes) FROM reunioes_celula rc WHERE rc.celula_id = c.id AND rc.data >= date('now', '-30 days')) as media_presenca
            FROM celulas c
            LEFT JOIN pessoas l ON c.lider_id = l.id
            LEFT JOIN pessoas cl ON c.co_lider_id = cl.id
            LEFT JOIN pessoas a ON c.anfitriao_id = a.id
            LEFT JOIN redes r ON c.rede_id = r.id
            WHERE c.igreja_id = ? AND c.ativo = 1
            ORDER BY c.nome
        ''', (igreja_id,))
        return [dict(row) for row in cursor.fetchall()]

def get_celula(celula_id: int) -> dict:
    """Busca uma célula específica"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.*,
                   l.nome as lider_nome,
                   cl.nome as co_lider_nome,
                   a.nome as anfitriao_nome,
                   r.nome as rede_nome
            FROM celulas c
            LEFT JOIN pessoas l ON c.lider_id = l.id
            LEFT JOIN pessoas cl ON c.co_lider_id = cl.id
            LEFT JOIN pessoas a ON c.anfitriao_id = a.id
            LEFT JOIN redes r ON c.rede_id = r.id
            WHERE c.id = ? AND c.igreja_id = ?
        ''', (celula_id, igreja_id))
        row = cursor.fetchone()
        return dict(row) if row else None

def salvar_celula(dados: dict) -> int:
    """Salva ou atualiza uma célula"""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        if dados.get('id'):
            cursor.execute('''
                UPDATE celulas
                SET nome = ?, descricao = ?, lider_id = ?, co_lider_id = ?, 
                    anfitriao_id = ?, endereco = ?, dia_semana = ?, horario = ?, rede_id = ?
                WHERE id = ? AND igreja_id = ?
            ''', (dados['nome'], dados.get('descricao'), dados.get('lider_id'),
                  dados.get('co_lider_id'), dados.get('anfitriao_id'), dados.get('endereco'),
                  dados.get('dia_semana'), dados.get('horario'), dados.get('rede_id'),
                  dados['id'], igreja_id))
            registrar_log(usuario['id'], igreja_id, 'celula.atualizar', f"Célula {dados['id']} atualizada")
            return dados['id']
        else:
            cursor.execute('''
                INSERT INTO celulas (igreja_id, nome, descricao, lider_id, co_lider_id, 
                                    anfitriao_id, endereco, dia_semana, horario, rede_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (igreja_id, dados['nome'], dados.get('descricao'), dados.get('lider_id'),
                  dados.get('co_lider_id'), dados.get('anfitriao_id'), dados.get('endereco'),
                  dados.get('dia_semana'), dados.get('horario'), dados.get('rede_id')))
            registrar_log(usuario['id'], igreja_id, 'celula.criar', f"Célula criada")
            return cursor.lastrowid

def get_membros_celula(celula_id: int) -> list:
    """Busca membros de uma célula"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.*, pc.funcao, pc.data_entrada
            FROM pessoas p
            JOIN pessoa_celulas pc ON p.id = pc.pessoa_id
            WHERE pc.celula_id = ? AND pc.ativo = 1
            ORDER BY pc.funcao DESC, p.nome
        ''', (celula_id,))
        return [dict(row) for row in cursor.fetchall()]

def adicionar_membro_celula(pessoa_id: int, celula_id: int, funcao: str = 'membro'):
    """Adiciona pessoa à célula"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO pessoa_celulas (pessoa_id, celula_id, funcao, data_entrada, ativo)
            VALUES (?, ?, ?, ?, 1)
        ''', (pessoa_id, celula_id, funcao, date.today()))

def remover_membro_celula(pessoa_id: int, celula_id: int):
    """Remove (desativa) pessoa da célula"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE pessoa_celulas
            SET ativo = 0, data_saida = ?
            WHERE pessoa_id = ? AND celula_id = ? AND ativo = 1
        ''', (date.today(), pessoa_id, celula_id))

def registrar_reuniao_celula(celula_id: int, data: date, tema: str, presentes: list, visitantes: int = 0, oferta: float = 0):
    """Registra uma reunião de célula"""
    usuario = get_usuario_atual()
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Criar reunião
        cursor.execute('''
            INSERT INTO reunioes_celula (celula_id, data, tema, total_presentes, total_visitantes, oferta)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (celula_id, data, tema, len(presentes), visitantes, oferta))
        reuniao_id = cursor.lastrowid
        
        # Registrar presenças
        for pessoa_id in presentes:
            cursor.execute('''
                INSERT INTO presenca_celula (reuniao_id, pessoa_id, presente)
                VALUES (?, ?, 1)
            ''', (reuniao_id, pessoa_id))
        
        registrar_log(usuario['id'], igreja_id, 'celula.reuniao', f"Reunião da célula {celula_id} registrada")

def get_historico_celula(celula_id: int, limite: int = 12) -> list:
    """Busca histórico de reuniões de uma célula"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM reunioes_celula
            WHERE celula_id = ?
            ORDER BY data DESC
            LIMIT ?
        ''', (celula_id, limite))
        return [dict(row) for row in cursor.fetchall()]

def get_redes() -> list:
    """Busca todas as redes de células"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT r.*,
                   s.nome as supervisor_nome,
                   (SELECT COUNT(*) FROM celulas c WHERE c.rede_id = r.id AND c.ativo = 1) as total_celulas
            FROM redes r
            LEFT JOIN pessoas s ON r.supervisor_id = s.id
            WHERE r.igreja_id = ?
            ORDER BY r.nome
        ''', (igreja_id,))
        return [dict(row) for row in cursor.fetchall()]

# ========================================
# RENDERIZAÇÃO DA INTERFACE
# ========================================

def get_pessoas_para_select() -> list:
    """Busca pessoas para seleção em dropdowns"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, nome FROM pessoas
            WHERE igreja_id = ? AND ativo = 1
            ORDER BY nome
        ''', (igreja_id,))
        return [dict(row) for row in cursor.fetchall()]

def render_detalhe_ministerio(ministerio_id: int):
    ministerio = get_ministerio(ministerio_id)
    if not ministerio:
        st.error("Ministério não encontrado")
        st.session_state.ministerio_view = None
        return

    st.subheader(f"⛪ {ministerio['nome']}")

    if st.button("← Voltar"):
        st.session_state.ministerio_view = None
        st.rerun()

    st.caption(ministerio.get('descricao', ''))

    col1, col2 = st.columns(2)
    col1.write(f"👤 Líder: {ministerio.get('lider_nome', 'Não definido')}")
    col2.write(f"🤝 Vice-líder: {ministerio.get('vice_lider_nome', 'Não definido')}")

    st.markdown("### 👥 Membros")
    membros = get_membros_ministerio(ministerio_id)
    membros_ids = {m['id'] for m in membros}

    if membros:
        for m in membros:
            col_a, col_b, col_c = st.columns([4, 2, 1])
            col_a.write(m['nome'])
            col_b.write(m.get('funcao', 'membro'))
            if col_c.button("🗑️", key=f"rm_min_{ministerio_id}_{m['id']}"):
                remover_membro_ministerio(m['id'], ministerio_id)
                st.rerun()
    else:
        st.info("Nenhum membro vinculado.")

    st.markdown("#### ➕ Adicionar membro")
    with st.form(f"form_add_membro_min_{ministerio_id}"):
        pessoas = [p for p in get_pessoas_para_select() if p['id'] not in membros_ids]
        pessoa_sel = st.selectbox("Pessoa", options=[0] + [p['id'] for p in pessoas],
                                  format_func=lambda x: next((p['nome'] for p in pessoas if p['id'] == x), "Selecione..."))
        funcao = st.selectbox("Função", options=['membro', 'líder', 'vice-líder', 'assistente'])
        if st.form_submit_button("Adicionar", use_container_width=True):
            if pessoa_sel:
                adicionar_membro_ministerio(pessoa_sel, ministerio_id, funcao)
                st.success("Membro adicionado")
                st.rerun()
            else:
                st.error("Selecione uma pessoa")

def render_detalhe_celula(celula_id: int):
    celula = get_celula(celula_id)
    if not celula:
        st.error("Célula não encontrada")
        st.session_state.celula_view = None
        return

    st.subheader(f"🏠 {celula['nome']}")

    col_top = st.columns([1, 1, 1])
    with col_top[0]:
        if st.button("← Voltar"):
            st.session_state.celula_view = None
            st.rerun()
    with col_top[1]:
        if st.button("📝 Registrar Reunião", use_container_width=True):
            st.session_state.celula_reuniao = celula_id
            st.rerun()
    with col_top[2]:
        st.caption(f"Rede: {celula.get('rede_nome', 'Nenhuma')}")

    st.write(celula.get('descricao', ''))
    st.caption(f"👤 Líder: {celula.get('lider_nome', 'Sem líder')} | 🤝 Co-líder: {celula.get('co_lider_nome', 'Sem co-líder')}")
    if celula.get('dia_semana'):
        st.caption(f"📅 {celula['dia_semana']} {celula.get('horario', '')}")
    if celula.get('endereco'):
        st.caption(f"📍 {celula['endereco']}")

    st.markdown("### 👥 Membros")
    membros = get_membros_celula(celula_id)
    membros_ids = {m['id'] for m in membros}

    if membros:
        for m in membros:
            col_a, col_b, col_c = st.columns([4, 2, 1])
            col_a.write(m['nome'])
            col_b.write(m.get('funcao', 'membro'))
            if col_c.button("🗑️", key=f"rm_cel_{celula_id}_{m['id']}"):
                remover_membro_celula(m['id'], celula_id)
                st.rerun()
    else:
        st.info("Nenhum membro vinculado.")

    st.markdown("#### ➕ Adicionar membro")
    with st.form(f"form_add_membro_cel_{celula_id}"):
        pessoas = [p for p in get_pessoas_para_select() if p['id'] not in membros_ids]
        pessoa_sel = st.selectbox("Pessoa", options=[0] + [p['id'] for p in pessoas],
                                  format_func=lambda x: next((p['nome'] for p in pessoas if p['id'] == x), "Selecione..."))
        funcao = st.selectbox("Função", options=['membro', 'líder', 'anfitrião', 'assistente'])
        if st.form_submit_button("Adicionar", use_container_width=True):
            if pessoa_sel:
                adicionar_membro_celula(pessoa_sel, celula_id, funcao)
                st.success("Membro adicionado")
                st.rerun()
            else:
                st.error("Selecione uma pessoa")

    st.markdown("### 📈 Últimas reuniões")
    historico = get_historico_celula(celula_id, limite=6)
    if historico:
        df_hist = pd.DataFrame(historico)
        df_hist['data'] = df_hist['data'].apply(formatar_data_br)
        st.dataframe(df_hist[['data', 'tema', 'total_presentes', 'total_visitantes', 'oferta']], use_container_width=True)
    else:
        st.info("Nenhuma reunião registrada.")

def render_ministerios():
    """Renderiza gestão de ministérios"""
    st.subheader("⛪ Ministérios")
    
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("➕ Novo Ministério", use_container_width=True):
            st.session_state.show_form_ministerio = True
    
    # Formulário de novo ministério
    if st.session_state.get('show_form_ministerio'):
        with st.expander("➕ Novo Ministério", expanded=True):
            pessoas = get_pessoas_para_select()
            pessoas_opcoes = [(0, "Selecione...")] + [(p['id'], p['nome']) for p in pessoas]
            
            with st.form("form_ministerio"):
                nome = st.text_input("Nome do Ministério *")
                descricao = st.text_area("Descrição", height=80)
                
                col1, col2 = st.columns(2)
                with col1:
                    lider_id = st.selectbox("Líder", options=[p[0] for p in pessoas_opcoes],
                                           format_func=lambda x: dict(pessoas_opcoes).get(x, ''))
                with col2:
                    vice_lider_id = st.selectbox("Vice-líder", options=[p[0] for p in pessoas_opcoes],
                                                format_func=lambda x: dict(pessoas_opcoes).get(x, ''))
                
                cor = st.color_picker("Cor identificadora", value="#3498db")
                
                col1, col2 = st.columns(2)
                with col1:
                    submit = st.form_submit_button("💾 Salvar", use_container_width=True)
                with col2:
                    if st.form_submit_button("❌ Cancelar", use_container_width=True):
                        st.session_state.show_form_ministerio = False
                        st.rerun()
                
                if submit:
                    if not nome:
                        st.error("Nome é obrigatório!")
                    else:
                        salvar_ministerio({
                            'nome': nome,
                            'descricao': descricao,
                            'lider_id': lider_id if lider_id else None,
                            'vice_lider_id': vice_lider_id if vice_lider_id else None,
                            'cor': cor
                        })
                        st.success("✅ Ministério criado!")
                        st.session_state.show_form_ministerio = False
                        st.rerun()
    
    # Lista de ministérios
    ministerios = get_ministerios()
    
    if not ministerios:
        st.info("Nenhum ministério cadastrado.")
        return
    
    # Grid de ministérios
    cols = st.columns(3)
    for i, ministerio in enumerate(ministerios):
        with cols[i % 3]:
            st.markdown(f"""
                <div style='background: linear-gradient(135deg, {ministerio.get('cor', '#3498db')}22 0%, {ministerio.get('cor', '#3498db')}44 100%);
                            border-left: 4px solid {ministerio.get('cor', '#3498db')};
                            padding: 1rem; border-radius: 8px; margin-bottom: 1rem;'>
                    <h4 style='margin: 0 0 0.5rem 0;'>{ministerio['nome']}</h4>
                    <p style='margin: 0; font-size: 0.9rem;'>
                        👤 Líder: {ministerio.get('lider_nome', 'Não definido')}<br>
                        👥 Membros: {ministerio['total_membros']}
                    </p>
                </div>
            """, unsafe_allow_html=True)
            
            if st.button("Ver detalhes", key=f"min_{ministerio['id']}", use_container_width=True):
                st.session_state.ministerio_view = ministerio['id']
                st.rerun()

def render_celulas():
    """Renderiza gestão de células"""
    st.subheader("🏠 Células / Pequenos Grupos")
    
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("➕ Nova Célula", use_container_width=True):
            st.session_state.show_form_celula = True
    
    # Formulário de nova célula
    if st.session_state.get('show_form_celula'):
        with st.expander("➕ Nova Célula", expanded=True):
            pessoas = get_pessoas_para_select()
            pessoas_opcoes = [(0, "Selecione...")] + [(p['id'], p['nome']) for p in pessoas]
            redes = get_redes()
            redes_opcoes = [(0, "Nenhuma")] + [(r['id'], r['nome']) for r in redes]
            
            with st.form("form_celula"):
                nome = st.text_input("Nome da Célula *")
                descricao = st.text_area("Descrição", height=80)
                
                col1, col2 = st.columns(2)
                with col1:
                    lider_id = st.selectbox("Líder", options=[p[0] for p in pessoas_opcoes],
                                           format_func=lambda x: dict(pessoas_opcoes).get(x, ''))
                    dia_semana = st.selectbox("Dia da semana", 
                                             options=['', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'])
                with col2:
                    co_lider_id = st.selectbox("Co-líder", options=[p[0] for p in pessoas_opcoes],
                                              format_func=lambda x: dict(pessoas_opcoes).get(x, ''))
                    horario = st.text_input("Horário", placeholder="19:30")
                
                endereco = st.text_input("Endereço da reunião")
                
                rede_id = st.selectbox("Rede", options=[r[0] for r in redes_opcoes],
                                      format_func=lambda x: dict(redes_opcoes).get(x, ''))
                
                col1, col2 = st.columns(2)
                with col1:
                    submit = st.form_submit_button("💾 Salvar", use_container_width=True)
                with col2:
                    if st.form_submit_button("❌ Cancelar", use_container_width=True):
                        st.session_state.show_form_celula = False
                        st.rerun()
                
                if submit:
                    if not nome:
                        st.error("Nome é obrigatório!")
                    else:
                        salvar_celula({
                            'nome': nome,
                            'descricao': descricao,
                            'lider_id': lider_id if lider_id else None,
                            'co_lider_id': co_lider_id if co_lider_id else None,
                            'endereco': endereco,
                            'dia_semana': dia_semana,
                            'horario': horario,
                            'rede_id': rede_id if rede_id else None
                        })
                        st.success("✅ Célula criada!")
                        st.session_state.show_form_celula = False
                        st.rerun()
    
    # Lista de células
    celulas = get_celulas()
    
    if not celulas:
        st.info("Nenhuma célula cadastrada.")
        return
    
    # Métricas gerais
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de Células", len(celulas))
    col2.metric("Total de Membros", sum([c['total_membros'] for c in celulas]))
    col3.metric("Média por Célula", f"{sum([c['total_membros'] for c in celulas]) / len(celulas):.1f}")
    medias_validas = [c['media_presenca'] for c in celulas if c['media_presenca'] is not None]
    media_geral = sum(medias_validas) / len(medias_validas) if medias_validas else None
    col4.metric("Média Presença", f"{media_geral:.0f}" if media_geral is not None else "N/A")
    
    st.markdown("---")
    
    # Grid de células
    for celula in celulas:
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
            
            with col1:
                st.markdown(f"**🏠 {celula['nome']}**")
                st.caption(f"👤 {celula.get('lider_nome', 'Sem líder')}")
            
            with col2:
                if celula['dia_semana']:
                    st.write(f"📅 {celula['dia_semana']} {celula.get('horario', '')}")
                endereco = celula.get('endereco') or ''
                if endereco:
                    st.caption(f"📍 {endereco[:30]}...")
            
            with col3:
                st.metric("Membros", celula['total_membros'])
            
            with col4:
                if st.button("👁️", key=f"cel_{celula['id']}", help="Ver célula"):
                    st.session_state.celula_view = celula['id']
                    st.rerun()
                if st.button("✏️", key=f"cel_edit_{celula['id']}", help="Registrar reunião"):
                    st.session_state.celula_reuniao = celula['id']
                    st.rerun()
        
        st.markdown("<hr style='margin: 0.5rem 0; opacity: 0.2;'>", unsafe_allow_html=True)

def render_registro_reuniao():
    """Renderiza formulário de registro de reunião de célula"""
    celula_id = st.session_state.get('celula_reuniao')
    celula = get_celula(celula_id)
    
    if not celula:
        st.error("Célula não encontrada!")
        return
    
    st.subheader(f"📝 Registrar Reunião - {celula['nome']}")
    
    if st.button("← Voltar"):
        st.session_state.celula_reuniao = None
        st.rerun()
    
    membros = get_membros_celula(celula_id)
    
    with st.form("form_reuniao"):
        col1, col2 = st.columns(2)
        with col1:
            data_reuniao = st.date_input("Data da reunião", value=date.today(), format="DD/MM/YYYY")
        with col2:
            tema = st.text_input("Tema/Estudo")
        
        st.markdown("### ✅ Lista de Presença")
        
        presentes = []
        for membro in membros:
            if st.checkbox(membro['nome'], key=f"pres_{membro['id']}"):
                presentes.append(membro['id'])
        
        col1, col2 = st.columns(2)
        with col1:
            visitantes = st.number_input("Visitantes", min_value=0, value=0)
        with col2:
            oferta = st.number_input("Oferta (R$)", min_value=0.0, value=0.0, step=10.0)
        
        observacoes = st.text_area("Observações", height=80)
        
        if st.form_submit_button("💾 Registrar Reunião", use_container_width=True):
            registrar_reuniao_celula(celula_id, data_reuniao, tema, presentes, visitantes, oferta)
            st.success("✅ Reunião registrada com sucesso!")
            st.session_state.celula_reuniao = None
            st.rerun()

def render_relatorio_celulas():
    """Renderiza relatórios de células"""
    st.subheader("📊 Relatórios de Células")
    
    celulas = get_celulas()
    
    if not celulas:
        st.info("Nenhuma célula cadastrada.")
        return
    
    # Saúde das células
    st.markdown("### 💚 Saúde das Células")
    
    dados_saude = []
    for celula in celulas:
        historico = get_historico_celula(celula['id'], limite=4)
        if historico:
            media = sum([h['total_presentes'] for h in historico]) / len(historico)
            tendencia = "📈" if len(historico) > 1 and historico[0]['total_presentes'] > historico[-1]['total_presentes'] else "📉"
        else:
            media = 0
            tendencia = "➖"
        
        dados_saude.append({
            'Célula': celula['nome'],
            'Líder': celula.get('lider_nome', 'N/A'),
            'Membros': celula['total_membros'],
            'Média Presença': f"{media:.1f}",
            'Tendência': tendencia
        })
    
    df = pd.DataFrame(dados_saude)
    st.dataframe(df, use_container_width=True)

def render_ministerios_celulas():
    """Função principal do módulo de ministérios e células"""
    # Verificar estados especiais
    if st.session_state.get('ministerio_view'):
        render_detalhe_ministerio(st.session_state.ministerio_view)
        return

    if st.session_state.get('celula_view'):
        render_detalhe_celula(st.session_state.celula_view)
        return

    if st.session_state.get('celula_reuniao'):
        render_registro_reuniao()
        return
    
    tab1, tab2, tab3 = st.tabs(["⛪ Ministérios", "🏠 Células", "📊 Relatórios"])
    
    with tab1:
        render_ministerios()
    
    with tab2:
        render_celulas()
    
    with tab3:
        render_relatorio_celulas()
