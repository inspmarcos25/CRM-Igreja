"""
Módulo de Escala de Ministérios
Criação automática de escalas, trocas e confirmações
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database.db import get_connection
from modules.auth import get_igreja_id, get_usuario_atual, registrar_log
from modules.visitantes import gerar_link_whatsapp
from config.settings import formatar_data_br

# ==================== FUNÇÕES DE DADOS ====================

def get_escalas(ministerio_id: int = None) -> list:
    """Busca escalas da igreja"""
    igreja_id = get_igreja_id()
    
    query = '''
        SELECT e.*, m.nome as ministerio_nome,
               (SELECT COUNT(*) FROM escala_itens ei WHERE ei.escala_id = e.id) as total_escalados
        FROM escalas e
        JOIN ministerios m ON e.ministerio_id = m.id
        WHERE e.igreja_id = ? AND e.ativo = 1
    '''
    params = [igreja_id]
    
    if ministerio_id:
        query += ' AND e.ministerio_id = ?'
        params.append(ministerio_id)
    
    query += ' ORDER BY e.data_inicio DESC'
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def get_escala(escala_id: int) -> dict:
    """Busca uma escala específica"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT e.*, m.nome as ministerio_nome
            FROM escalas e
            JOIN ministerios m ON e.ministerio_id = m.id
            WHERE e.id = ?
        ''', (escala_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def salvar_escala(dados: dict) -> int:
    """Salva ou atualiza uma escala"""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        if dados.get('id'):
            cursor.execute('''
                UPDATE escalas
                SET nome = ?, ministerio_id = ?, data_inicio = ?, data_fim = ?, recorrencia = ?
                WHERE id = ? AND igreja_id = ?
            ''', (dados['nome'], dados['ministerio_id'], dados['data_inicio'],
                  dados['data_fim'], dados.get('recorrencia', 'semanal'),
                  dados['id'], igreja_id))
            registrar_log(usuario['id'], igreja_id, 'escala.atualizar', f"Escala {dados['id']} atualizada")
            return dados['id']
        else:
            cursor.execute('''
                INSERT INTO escalas (igreja_id, ministerio_id, nome, data_inicio, data_fim, recorrencia)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (igreja_id, dados['ministerio_id'], dados['nome'], dados['data_inicio'],
                  dados['data_fim'], dados.get('recorrencia', 'semanal')))
            registrar_log(usuario['id'], igreja_id, 'escala.criar', f"Escala criada: {dados['nome']}")
            return cursor.lastrowid

def get_itens_escala(escala_id: int) -> list:
    """Busca itens de uma escala"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT ei.*, p.nome as pessoa_nome, p.celular
            FROM escala_itens ei
            JOIN pessoas p ON ei.pessoa_id = p.id
            WHERE ei.escala_id = ?
            ORDER BY ei.data, ei.horario
        ''', (escala_id,))
        return [dict(row) for row in cursor.fetchall()]

def adicionar_item_escala(dados: dict) -> int:
    """Adiciona pessoa à escala"""
    usuario = get_usuario_atual()
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO escala_itens (escala_id, pessoa_id, data, funcao, horario)
            VALUES (?, ?, ?, ?, ?)
        ''', (dados['escala_id'], dados['pessoa_id'], dados['data'],
              dados.get('funcao'), dados.get('horario')))
        
        registrar_log(usuario['id'], igreja_id, 'escala.adicionar_pessoa', 
                     f"Pessoa {dados['pessoa_id']} adicionada à escala")
        return cursor.lastrowid

def remover_item_escala(item_id: int):
    """Remove pessoa da escala"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM escala_itens WHERE id = ?', (item_id,))

def confirmar_escala(item_id: int, confirmado: bool):
    """Confirma ou desconfirma presença na escala"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE escala_itens
            SET confirmado = ?, data_confirmacao = ?
            WHERE id = ?
        ''', (1 if confirmado else 0, datetime.now() if confirmado else None, item_id))

def get_minha_escala(pessoa_id: int = None) -> list:
    """Busca escalas de uma pessoa específica"""
    igreja_id = get_igreja_id()
    
    if not pessoa_id:
        usuario = get_usuario_atual()
        pessoa_id = usuario.get('pessoa_id')
    
    if not pessoa_id:
        return []
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT ei.*, e.nome as escala_nome, m.nome as ministerio_nome
            FROM escala_itens ei
            JOIN escalas e ON ei.escala_id = e.id
            JOIN ministerios m ON e.ministerio_id = m.id
            WHERE ei.pessoa_id = ?
            AND e.igreja_id = ?
            AND ei.data >= date('now')
            ORDER BY ei.data
        ''', (pessoa_id, igreja_id))
        return [dict(row) for row in cursor.fetchall()]

def solicitar_troca(item_id: int, motivo: str) -> int:
    """Solicita troca de escala"""
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trocas_escala (escala_item_id, solicitante_id, motivo)
            VALUES (?, ?, ?)
        ''', (item_id, usuario.get('pessoa_id'), motivo))
        return cursor.lastrowid

def get_trocas_pendentes() -> list:
    """Busca trocas pendentes"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.*, 
                   ei.data, ei.funcao, ei.horario,
                   p.nome as solicitante_nome,
                   ps.nome as substituto_nome,
                   e.nome as escala_nome,
                   m.nome as ministerio_nome
            FROM trocas_escala t
            JOIN escala_itens ei ON t.escala_item_id = ei.id
            JOIN escalas e ON ei.escala_id = e.id
            JOIN ministerios m ON e.ministerio_id = m.id
            JOIN pessoas p ON t.solicitante_id = p.id
            LEFT JOIN pessoas ps ON t.substituto_id = ps.id
            WHERE e.igreja_id = ? AND t.status = 'pendente'
            ORDER BY ei.data
        ''', (igreja_id,))
        return [dict(row) for row in cursor.fetchall()]

def aceitar_troca(troca_id: int, pessoa_id: int):
    """Aceita uma troca de escala"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Buscar informações da troca
        cursor.execute('SELECT * FROM trocas_escala WHERE id = ?', (troca_id,))
        troca = cursor.fetchone()
        
        if troca:
            # Atualizar a troca
            cursor.execute('''
                UPDATE trocas_escala
                SET substituto_id = ?, status = 'aceita', data_resposta = ?
                WHERE id = ?
            ''', (pessoa_id, datetime.now(), troca_id))
            
            # Atualizar o item da escala
            cursor.execute('''
                UPDATE escala_itens
                SET pessoa_id = ?
                WHERE id = ?
            ''', (pessoa_id, troca['escala_item_id']))

def get_membros_ministerio(ministerio_id: int) -> list:
    """Busca membros de um ministério"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.id, p.nome, p.celular
            FROM pessoa_ministerios pm
            JOIN pessoas p ON pm.pessoa_id = p.id
            WHERE pm.ministerio_id = ? AND pm.ativo = 1 AND p.ativo = 1
            ORDER BY p.nome
        ''', (ministerio_id,))
        return [dict(row) for row in cursor.fetchall()]

def gerar_escala_automatica(escala_id: int, membros: list, datas: list, funcoes: list):
    """Gera escala automaticamente distribuindo membros"""
    import random
    
    if not membros or not datas:
        return
    
    # Embaralhar membros para distribuição aleatória
    membros_disponiveis = membros.copy()
    random.shuffle(membros_disponiveis)
    
    idx = 0
    for data in datas:
        for funcao in funcoes:
            if idx >= len(membros_disponiveis):
                membros_disponiveis = membros.copy()
                random.shuffle(membros_disponiveis)
                idx = 0
            
            adicionar_item_escala({
                'escala_id': escala_id,
                'pessoa_id': membros_disponiveis[idx]['id'],
                'data': data,
                'funcao': funcao
            })
            idx += 1

# ==================== RENDERIZAÇÃO ====================

def render_escalas():
    """Função principal do módulo de escalas"""
    st.title("📅 Escala de Ministérios")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Escalas", 
        "➕ Nova Escala", 
        "🔄 Trocas", 
        "👤 Minha Escala"
    ])
    
    with tab1:
        render_lista_escalas()
    
    with tab2:
        render_nova_escala()
    
    with tab3:
        render_trocas()
    
    with tab4:
        render_minha_escala()

def render_lista_escalas():
    """Renderiza lista de escalas"""
    st.subheader("📋 Escalas Ativas")
    
    # Filtro por ministério
    from modules.ministerios import get_ministerios
    ministerios = get_ministerios()
    
    opcoes_ministerio = [{'id': None, 'nome': 'Todos os Ministérios'}] + ministerios
    ministerio_selecionado = st.selectbox(
        "Filtrar por Ministério",
        options=opcoes_ministerio,
        format_func=lambda x: x['nome'],
        key="filtro_ministerio_escala"
    )
    
    escalas = get_escalas(ministerio_selecionado['id'] if ministerio_selecionado['id'] else None)
    
    if not escalas:
        st.info("Nenhuma escala cadastrada.")
        return
    
    for escala in escalas:
        with st.expander(f"📅 {escala['nome']} - {escala['ministerio_nome']}", expanded=False):
            col1, col2, col3 = st.columns(3)
            col1.write(f"**Período:** {formatar_data_br(escala['data_inicio'])} a {formatar_data_br(escala['data_fim'])}")
            col2.write(f"**Recorrência:** {escala['recorrencia']}")
            col3.write(f"**Escalados:** {escala['total_escalados']}")
            
            st.markdown("---")
            
            # Itens da escala
            itens = get_itens_escala(escala['id'])
            
            if itens:
                # Agrupar por data
                datas = {}
                for item in itens:
                    data = item['data']
                    if data not in datas:
                        datas[data] = []
                    datas[data].append(item)
                
                for data, pessoas in datas.items():
                    st.markdown(f"**📆 {formatar_data_br(data)}**")
                    
                    for pessoa in pessoas:
                        col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                        
                        with col1:
                            status_icon = "✅" if pessoa['confirmado'] else "⏳"
                            st.write(f"{status_icon} {pessoa['pessoa_nome']}")
                        
                        with col2:
                            st.write(f"🎯 {pessoa.get('funcao', 'Geral')}")
                        
                        with col3:
                            if pessoa['celular']:
                                msg = f"Olá {pessoa['pessoa_nome']}! Lembrete: você está escalado(a) para {escala['ministerio_nome']} no dia {formatar_data_br(data)}."
                                link = gerar_link_whatsapp(pessoa['celular'], msg)
                                st.markdown(f"[📱]({link})", unsafe_allow_html=True)
                        
                        with col4:
                            if st.button("🗑️", key=f"rem_{pessoa['id']}", help="Remover"):
                                remover_item_escala(pessoa['id'])
                                st.rerun()
            else:
                st.warning("Nenhuma pessoa escalada ainda.")
            
            # Adicionar pessoa
            st.markdown("---")
            st.markdown("**➕ Adicionar à Escala**")
            
            membros = get_membros_ministerio(escala['ministerio_id'])
            
            if membros:
                col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                
                with col1:
                    pessoa = st.selectbox(
                        "Pessoa",
                        options=membros,
                        format_func=lambda x: x['nome'],
                        key=f"pessoa_{escala['id']}"
                    )
                
                with col2:
                    data_escala = st.date_input(
                        "Data",
                        min_value=date.today(),
                        format="DD/MM/YYYY",
                        key=f"data_{escala['id']}"
                    )
                
                with col3:
                    funcao = st.text_input("Função", key=f"funcao_{escala['id']}")
                
                with col4:
                    st.write("")
                    st.write("")
                    if st.button("➕", key=f"add_{escala['id']}"):
                        adicionar_item_escala({
                            'escala_id': escala['id'],
                            'pessoa_id': pessoa['id'],
                            'data': data_escala,
                            'funcao': funcao
                        })
                        st.success("Adicionado!")
                        st.rerun()

def render_nova_escala():
    """Renderiza formulário de nova escala"""
    st.subheader("➕ Criar Nova Escala")
    
    from modules.ministerios import get_ministerios
    ministerios = get_ministerios()
    
    if not ministerios:
        st.warning("Cadastre ministérios primeiro!")
        return
    
    with st.form("nova_escala"):
        nome = st.text_input("Nome da Escala *", placeholder="Ex: Escala de Louvor - Janeiro 2026")
        
        ministerio = st.selectbox(
            "Ministério *",
            options=ministerios,
            format_func=lambda x: x['nome']
        )
        
        col1, col2 = st.columns(2)
        with col1:
            data_inicio = st.date_input("Data Início *", format="DD/MM/YYYY")
        with col2:
            data_fim = st.date_input("Data Fim *", format="DD/MM/YYYY", value=date.today() + timedelta(days=30))
        
        recorrencia = st.selectbox(
            "Recorrência",
            options=['semanal', 'quinzenal', 'mensal'],
            format_func=lambda x: {'semanal': 'Semanal', 'quinzenal': 'Quinzenal', 'mensal': 'Mensal'}[x]
        )
        
        st.markdown("---")
        st.markdown("**🤖 Geração Automática (opcional)**")
        
        gerar_auto = st.checkbox("Gerar escala automaticamente")
        
        funcoes = []
        if gerar_auto:
            funcoes_texto = st.text_input(
                "Funções (separadas por vírgula)",
                placeholder="Ex: Vocal, Guitarra, Baixo, Bateria, Teclado"
            )
            if funcoes_texto:
                funcoes = [f.strip() for f in funcoes_texto.split(',')]
        
        submit = st.form_submit_button("💾 Criar Escala", use_container_width=True)
        
        if submit:
            if not nome:
                st.error("Nome é obrigatório!")
            elif data_fim <= data_inicio:
                st.error("Data fim deve ser maior que data início!")
            else:
                escala_id = salvar_escala({
                    'nome': nome,
                    'ministerio_id': ministerio['id'],
                    'data_inicio': data_inicio,
                    'data_fim': data_fim,
                    'recorrencia': recorrencia
                })
                
                if gerar_auto and funcoes:
                    # Gerar datas baseado na recorrência
                    datas = []
                    data_atual = data_inicio
                    delta = {'semanal': 7, 'quinzenal': 14, 'mensal': 30}[recorrencia]
                    
                    while data_atual <= data_fim:
                        datas.append(data_atual)
                        data_atual += timedelta(days=delta)
                    
                    membros = get_membros_ministerio(ministerio['id'])
                    if membros:
                        gerar_escala_automatica(escala_id, membros, datas, funcoes)
                
                st.success("✅ Escala criada com sucesso!")
                st.rerun()

def render_trocas():
    """Renderiza gestão de trocas de escala"""
    st.subheader("🔄 Solicitações de Troca")
    
    trocas = get_trocas_pendentes()
    
    if not trocas:
        st.success("🎉 Nenhuma solicitação de troca pendente!")
        return
    
    for troca in trocas:
        with st.container():
            st.markdown(f"""
                <div style='background: #fff3cd; padding: 1rem; border-radius: 10px; margin-bottom: 1rem;'>
                    <strong>🔄 {troca['solicitante_nome']}</strong> solicita troca<br>
                    <small>
                        📅 {formatar_data_br(troca['data'])} | 
                        🎯 {troca.get('funcao', 'Geral')} | 
                        🎵 {troca['ministerio_nome']}
                    </small><br>
                    <small>💬 Motivo: {troca.get('motivo', 'Não informado')}</small>
                </div>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("✅ Aceitar Troca", key=f"aceitar_{troca['id']}", use_container_width=True):
                    usuario = get_usuario_atual()
                    aceitar_troca(troca['id'], usuario.get('pessoa_id'))
                    st.success("Troca aceita!")
                    st.rerun()
            
            st.markdown("---")

def render_minha_escala():
    """Renderiza escalas do usuário logado"""
    st.subheader("👤 Minha Escala")
    
    escalas = get_minha_escala()
    
    if not escalas:
        st.info("Você não está em nenhuma escala no momento.")
        return
    
    st.markdown("### 📅 Próximos Compromissos")
    
    for item in escalas:
        with st.container():
            col1, col2, col3 = st.columns([3, 2, 2])
            
            with col1:
                st.markdown(f"**📆 {formatar_data_br(item['data'])}**")
                st.caption(f"🎵 {item['ministerio_nome']} - {item['escala_nome']}")
            
            with col2:
                st.write(f"🎯 {item.get('funcao', 'Geral')}")
                st.caption(f"🕐 {item.get('horario', 'A definir')}")
            
            with col3:
                if not item['confirmado']:
                    if st.button("✅ Confirmar", key=f"conf_{item['id']}"):
                        confirmar_escala(item['id'], True)
                        st.success("Confirmado!")
                        st.rerun()
                    
                    if st.button("🔄 Solicitar Troca", key=f"troca_{item['id']}"):
                        st.session_state[f"troca_modal_{item['id']}"] = True
                else:
                    st.success("✅ Confirmado")
            
            # Modal de troca
            if st.session_state.get(f"troca_modal_{item['id']}"):
                motivo = st.text_input("Motivo da troca:", key=f"motivo_{item['id']}")
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("Enviar", key=f"env_{item['id']}"):
                        solicitar_troca(item['id'], motivo)
                        st.success("Solicitação enviada!")
                        del st.session_state[f"troca_modal_{item['id']}"]
                        st.rerun()
                with col_b:
                    if st.button("Cancelar", key=f"canc_{item['id']}"):
                        del st.session_state[f"troca_modal_{item['id']}"]
                        st.rerun()
        
        st.markdown("<hr style='margin: 0.5rem 0; opacity: 0.2;'>", unsafe_allow_html=True)
