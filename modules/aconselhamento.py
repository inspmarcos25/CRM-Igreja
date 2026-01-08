"""
Módulo de Aconselhamento Pastoral (Confidencial)
Registro de atendimentos com criptografia e controle de acesso rigoroso
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database.db import get_connection, encrypt_data, decrypt_data
from modules.auth import get_igreja_id, get_usuario_atual, registrar_log, tem_permissao
from config.settings import formatar_data_br

def get_aconselhamentos(filtros: dict = None) -> list:
    """Busca aconselhamentos (apenas metadados, não conteúdo)"""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    query = '''
        SELECT a.id, a.data_atendimento, a.tipo, a.status, a.proximo_encontro,
               p.id as pessoa_id, p.nome as pessoa_nome,
               c.nome as conselheiro_nome
        FROM aconselhamentos a
        JOIN pessoas p ON a.pessoa_id = p.id
        JOIN pessoas c ON a.conselheiro_id = c.id
        WHERE a.igreja_id = ?
    '''
    params = [igreja_id]
    
    # Líderes só veem seus próprios aconselhamentos
    if usuario['perfil'] == 'LIDER':
        query += ' AND a.conselheiro_id = ?'
        params.append(usuario.get('pessoa_id'))
    
    if filtros:
        if filtros.get('pessoa_id'):
            query += ' AND a.pessoa_id = ?'
            params.append(filtros['pessoa_id'])
        if filtros.get('status'):
            query += ' AND a.status = ?'
            params.append(filtros['status'])
        if filtros.get('conselheiro_id'):
            query += ' AND a.conselheiro_id = ?'
            params.append(filtros['conselheiro_id'])
    
    query += ' ORDER BY a.data_atendimento DESC'
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def get_aconselhamento_detalhes(aconselhamento_id: int) -> dict | None:
    """Busca detalhes de um aconselhamento com descriptografia"""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT a.*, p.nome as pessoa_nome, c.nome as conselheiro_nome
            FROM aconselhamentos a
            JOIN pessoas p ON a.pessoa_id = p.id
            JOIN pessoas c ON a.conselheiro_id = c.id
            WHERE a.id = ? AND a.igreja_id = ?
        ''', (aconselhamento_id, igreja_id))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        aconselhamento = dict(row)
        
        # Verificar permissão de acesso
        if usuario['perfil'] == 'LIDER' and aconselhamento['conselheiro_id'] != usuario.get('pessoa_id'):
            return None
        
        # Descriptografar dados sensíveis
        if aconselhamento.get('resumo_criptografado'):
            aconselhamento['resumo'] = decrypt_data(aconselhamento['resumo_criptografado'])
        if aconselhamento.get('notas_criptografadas'):
            aconselhamento['notas'] = decrypt_data(aconselhamento['notas_criptografadas'])
        
        # Registrar acesso ao dado sensível
        registrar_log(usuario['id'], igreja_id, 'aconselhamento.visualizar', 
                     f"Acesso ao aconselhamento {aconselhamento_id}")
        
        return aconselhamento

def registrar_aconselhamento(dados: dict) -> int:
    """Registra um novo aconselhamento com criptografia"""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    # Criptografar dados sensíveis
    resumo_cripto = encrypt_data(dados.get('resumo', '')) if dados.get('resumo') else None
    notas_cripto = encrypt_data(dados.get('notas', '')) if dados.get('notas') else None
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO aconselhamentos (igreja_id, pessoa_id, conselheiro_id, data_atendimento,
                                        tipo, resumo_criptografado, notas_criptografadas, status, proximo_encontro)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (igreja_id, dados['pessoa_id'], dados['conselheiro_id'], dados['data_atendimento'],
              dados.get('tipo'), resumo_cripto, notas_cripto, 
              dados.get('status', 'em_andamento'), dados.get('proximo_encontro')))
        
        aconselhamento_id = cursor.lastrowid
        registrar_log(usuario['id'], igreja_id, 'aconselhamento.criar', 
                     f"Aconselhamento {aconselhamento_id} criado para pessoa {dados['pessoa_id']}")
        
        return aconselhamento_id

def atualizar_aconselhamento(aconselhamento_id: int, dados: dict):
    """Atualiza um aconselhamento"""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    # Criptografar dados sensíveis se fornecidos
    resumo_cripto = encrypt_data(dados['resumo']) if dados.get('resumo') else None
    notas_cripto = encrypt_data(dados['notas']) if dados.get('notas') else None
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE aconselhamentos
            SET tipo = ?, resumo_criptografado = ?, notas_criptografadas = ?,
                status = ?, proximo_encontro = ?
            WHERE id = ? AND igreja_id = ?
        ''', (dados.get('tipo'), resumo_cripto, notas_cripto,
              dados.get('status'), dados.get('proximo_encontro'),
              aconselhamento_id, igreja_id))
        
        registrar_log(usuario['id'], igreja_id, 'aconselhamento.atualizar', 
                     f"Aconselhamento {aconselhamento_id} atualizado")

def get_conselheiros() -> list:
    """Busca pessoas que podem ser conselheiros (pastores e líderes)"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT p.id, p.nome
            FROM pessoas p
            LEFT JOIN usuarios u ON p.id = u.pessoa_id
            WHERE p.igreja_id = ? AND p.ativo = 1
            AND (p.status IN ('lider', 'membro') OR u.perfil IN ('ADMIN', 'PASTOR', 'LIDER'))
            ORDER BY p.nome
        ''', (igreja_id,))
        return [dict(row) for row in cursor.fetchall()]

def get_pessoas_para_aconselhamento() -> list:
    """Busca pessoas que podem receber aconselhamento"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, nome FROM pessoas
            WHERE igreja_id = ? AND ativo = 1
            ORDER BY nome
        ''', (igreja_id,))
        return [dict(row) for row in cursor.fetchall()]

# ========================================
# RENDERIZAÇÃO DA INTERFACE
# ========================================

def render_lista_aconselhamentos():
    """Renderiza lista de aconselhamentos"""
    st.subheader("🙏 Aconselhamentos Pastorais")
    
    st.warning("""
        ⚠️ **Área Confidencial** - Os dados aqui são protegidos por criptografia e 
        todos os acessos são registrados conforme LGPD.
    """)
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        status_filtro = st.selectbox("Status", 
                                    options=['todos', 'em_andamento', 'concluido', 'pausado'],
                                    format_func=lambda x: {
                                        'todos': 'Todos',
                                        'em_andamento': 'Em andamento',
                                        'concluido': 'Concluído',
                                        'pausado': 'Pausado'
                                    }.get(x, x))
    
    with col3:
        if st.button("➕ Novo", use_container_width=True):
            st.session_state.show_form_aconselhamento = True
    
    # Formulário de novo aconselhamento
    if st.session_state.get('show_form_aconselhamento'):
        render_form_aconselhamento()
        return
    
    # Detalhes de aconselhamento
    if st.session_state.get('aconselhamento_view'):
        render_detalhes_aconselhamento(st.session_state.aconselhamento_view)
        return
    
    # Lista
    filtros = {}
    if status_filtro != 'todos':
        filtros['status'] = status_filtro
    
    aconselhamentos = get_aconselhamentos(filtros)
    
    if not aconselhamentos:
        st.info("Nenhum aconselhamento encontrado.")
        return
    
    # Métricas
    col1, col2, col3 = st.columns(3)
    em_andamento = len([a for a in aconselhamentos if a['status'] == 'em_andamento'])
    col1.metric("Em andamento", em_andamento)
    col2.metric("Total", len(aconselhamentos))
    
    proximos = len([a for a in aconselhamentos if a.get('proximo_encontro') and 
                   str(a['proximo_encontro']) >= str(date.today())])
    col3.metric("Com agendamento", proximos)
    
    st.markdown("---")
    
    # Lista de aconselhamentos
    for acons in aconselhamentos:
        status_icon = {
            'em_andamento': '🟡',
            'concluido': '🟢',
            'pausado': '🔴'
        }.get(acons['status'], '⚪')
        
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
            
            with col1:
                st.markdown(f"**{acons['pessoa_nome']}**")
                st.caption(f"📅 {formatar_data_br(acons['data_atendimento'])}")
            
            with col2:
                st.write(f"👤 {acons['conselheiro_nome']}")
                if acons.get('tipo'):
                    st.caption(acons['tipo'])
            
            with col3:
                st.write(f"{status_icon} {acons['status'].replace('_', ' ').title()}")
                if acons.get('proximo_encontro'):
                    st.caption(f"📅 Próximo: {formatar_data_br(acons['proximo_encontro'])}")
            
            with col4:
                if st.button("👁️", key=f"ver_acons_{acons['id']}", help="Ver detalhes"):
                    st.session_state.aconselhamento_view = acons['id']
                    st.rerun()
        
        st.markdown("<hr style='margin: 0.5rem 0; opacity: 0.2;'>", unsafe_allow_html=True)

def render_form_aconselhamento():
    """Renderiza formulário de novo aconselhamento"""
    st.subheader("➕ Novo Aconselhamento")
    
    if st.button("← Voltar"):
        st.session_state.show_form_aconselhamento = False
        st.rerun()
    
    pessoas = get_pessoas_para_aconselhamento()
    conselheiros = get_conselheiros()
    usuario = get_usuario_atual()
    
    pessoas_opcoes = [(0, "Selecione...")] + [(p['id'], p['nome']) for p in pessoas]
    conselheiros_opcoes = [(0, "Selecione...")] + [(c['id'], c['nome']) for c in conselheiros]
    
    with st.form("form_aconselhamento"):
        col1, col2 = st.columns(2)
        
        with col1:
            pessoa_id = st.selectbox("Pessoa *",
                                    options=[p[0] for p in pessoas_opcoes],
                                    format_func=lambda x: dict(pessoas_opcoes).get(x, ''))
            
            data_atendimento = st.date_input("Data do atendimento", value=date.today(), format="DD/MM/YYYY")
            
            tipo = st.selectbox("Tipo de aconselhamento",
                               options=['', 'Casamento', 'Família', 'Emocional', 
                                       'Espiritual', 'Financeiro', 'Profissional', 'Outro'])
        
        with col2:
            # Pré-selecionar o próprio usuário como conselheiro se tiver pessoa_id
            default_conselheiro = 0
            if usuario.get('pessoa_id'):
                default_conselheiro = usuario['pessoa_id']
            
            conselheiro_id = st.selectbox("Conselheiro *",
                                         options=[c[0] for c in conselheiros_opcoes],
                                         format_func=lambda x: dict(conselheiros_opcoes).get(x, ''),
                                         index=next((i for i, c in enumerate(conselheiros_opcoes) 
                                                   if c[0] == default_conselheiro), 0))
            
            proximo_encontro = st.date_input("Próximo encontro (opcional)", value=None, format="DD/MM/YYYY")
            
            status = st.selectbox("Status",
                                 options=['em_andamento', 'concluido', 'pausado'],
                                 format_func=lambda x: x.replace('_', ' ').title())
        
        st.markdown("### 📝 Notas do Atendimento (Criptografadas)")
        st.info("ℹ️ Estas informações serão criptografadas e apenas pessoas autorizadas terão acesso.")
        
        resumo = st.text_area("Resumo do atendimento", height=100,
                             help="Descreva brevemente o que foi tratado")
        
        notas = st.text_area("Notas detalhadas (confidencial)", height=150,
                            help="Informações detalhadas que ficarão criptografadas")
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("💾 Salvar", use_container_width=True)
        with col2:
            if st.form_submit_button("❌ Cancelar", use_container_width=True):
                st.session_state.show_form_aconselhamento = False
                st.rerun()
        
        if submit:
            if not pessoa_id or not conselheiro_id:
                st.error("Selecione a pessoa e o conselheiro!")
            else:
                registrar_aconselhamento({
                    'pessoa_id': pessoa_id,
                    'conselheiro_id': conselheiro_id,
                    'data_atendimento': data_atendimento,
                    'tipo': tipo if tipo else None,
                    'status': status,
                    'proximo_encontro': proximo_encontro,
                    'resumo': resumo,
                    'notas': notas
                })
                st.success("✅ Aconselhamento registrado com sucesso!")
                st.session_state.show_form_aconselhamento = False
                st.rerun()

def render_detalhes_aconselhamento(aconselhamento_id: int):
    """Renderiza detalhes de um aconselhamento"""
    
    if st.button("← Voltar"):
        st.session_state.aconselhamento_view = None
        st.rerun()
    
    aconselhamento = get_aconselhamento_detalhes(aconselhamento_id)
    
    if not aconselhamento:
        st.error("Aconselhamento não encontrado ou você não tem permissão para visualizá-lo.")
        return
    
    st.subheader(f"🙏 Aconselhamento - {aconselhamento['pessoa_nome']}")
    
    st.warning("⚠️ Este acesso está sendo registrado conforme LGPD.")
    
    # Informações básicas
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📋 Informações")
        st.write(f"**Pessoa:** {aconselhamento['pessoa_nome']}")
        st.write(f"**Conselheiro:** {aconselhamento['conselheiro_nome']}")
        st.write(f"**Data:** {formatar_data_br(aconselhamento['data_atendimento'])}")
        if aconselhamento.get('tipo'):
            st.write(f"**Tipo:** {aconselhamento['tipo']}")
    
    with col2:
        status_icon = {
            'em_andamento': '🟡',
            'concluido': '🟢',
            'pausado': '🔴'
        }.get(aconselhamento['status'], '⚪')
        
        st.markdown("### 📊 Status")
        st.write(f"**Status:** {status_icon} {aconselhamento['status'].replace('_', ' ').title()}")
        if aconselhamento.get('proximo_encontro'):
            st.write(f"**Próximo encontro:** {aconselhamento['proximo_encontro']}")
    
    st.markdown("---")
    
    # Conteúdo confidencial
    st.markdown("### 🔒 Conteúdo Confidencial")
    
    if aconselhamento.get('resumo'):
        st.markdown("**Resumo:**")
        st.text_area("", value=aconselhamento['resumo'], height=100, disabled=True, key="resumo_view")
    
    if aconselhamento.get('notas'):
        st.markdown("**Notas detalhadas:**")
        st.text_area("", value=aconselhamento['notas'], height=150, disabled=True, key="notas_view")
    
    # Ações
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("✏️ Editar", use_container_width=True):
            st.session_state.aconselhamento_edit = aconselhamento_id
    
    with col2:
        if aconselhamento['status'] != 'concluido':
            if st.button("✅ Concluir", use_container_width=True):
                atualizar_aconselhamento(aconselhamento_id, {'status': 'concluido'})
                st.success("Aconselhamento concluído!")
                st.rerun()

def render_aconselhamento():
    """Função principal do módulo de aconselhamento"""
    usuario = get_usuario_atual()
    
    # Verificar permissão
    if not tem_permissao(usuario, 'aconselhamento.ver'):
        st.error("🚫 Você não tem permissão para acessar este módulo.")
        st.info("O módulo de Aconselhamento Pastoral é restrito a pastores e líderes autorizados.")
        return
    
    render_lista_aconselhamentos()
