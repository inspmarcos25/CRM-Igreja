"""
Módulo de Eventos & Presença
Cadastro de eventos, inscrições e check-in
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import qrcode
from io import BytesIO
import base64
import uuid
from database.db import get_connection
from modules.auth import get_igreja_id, get_usuario_atual, registrar_log
from config.settings import TIPOS_EVENTO, formatar_data_br

def gerar_qrcode(dados: str) -> str:
    """Gera QR Code e retorna como base64"""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(dados)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

def get_eventos(filtro: str = 'proximos') -> list:
    """Busca eventos da igreja"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        query = '''
            SELECT e.*,
                   (SELECT COUNT(*) FROM inscricoes_evento ie WHERE ie.evento_id = e.id) as total_inscritos,
                   (SELECT COUNT(*) FROM presenca_evento pe WHERE pe.evento_id = e.id) as total_presentes
            FROM eventos e
            WHERE e.igreja_id = ? AND e.ativo = 1
        '''
        params = [igreja_id]
        
        if filtro == 'proximos':
            query += ' AND e.data_inicio >= date("now")'
        elif filtro == 'passados':
            query += ' AND e.data_inicio < date("now")'
        elif filtro == 'hoje':
            query += ' AND date(e.data_inicio) = date("now")'
        
        query += ' ORDER BY e.data_inicio'
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def get_evento(evento_id: int) -> dict:
    """Busca um evento específico"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM eventos
            WHERE id = ? AND igreja_id = ?
        ''', (evento_id, igreja_id))
        row = cursor.fetchone()
        return dict(row) if row else None

def salvar_evento(dados: dict) -> int:
    """Salva ou atualiza um evento"""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        qrcode_str = str(uuid.uuid4())[:8].upper()
        
        if dados.get('id'):
            cursor.execute('''
                UPDATE eventos
                SET nome = ?, descricao = ?, tipo = ?, data_inicio = ?, data_fim = ?,
                    local = ?, capacidade = ?, valor_inscricao = ?, requer_inscricao = ?
                WHERE id = ? AND igreja_id = ?
            ''', (dados['nome'], dados.get('descricao'), dados.get('tipo'),
                  dados['data_inicio'], dados.get('data_fim'), dados.get('local'),
                  dados.get('capacidade'), dados.get('valor_inscricao', 0),
                  dados.get('requer_inscricao', 0), dados['id'], igreja_id))
            registrar_log(usuario['id'], igreja_id, 'evento.atualizar', f"Evento {dados['id']} atualizado")
            return dados['id']
        else:
            cursor.execute('''
                INSERT INTO eventos (igreja_id, nome, descricao, tipo, data_inicio, data_fim,
                                    local, capacidade, valor_inscricao, requer_inscricao, qrcode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (igreja_id, dados['nome'], dados.get('descricao'), dados.get('tipo'),
                  dados['data_inicio'], dados.get('data_fim'), dados.get('local'),
                  dados.get('capacidade'), dados.get('valor_inscricao', 0),
                  dados.get('requer_inscricao', 0), qrcode_str))
            registrar_log(usuario['id'], igreja_id, 'evento.criar', f"Evento criado: {dados['nome']}")
            return cursor.lastrowid

def inscrever_pessoa(evento_id: int, pessoa_id: int):
    """Inscreve uma pessoa em um evento"""
    qrcode_str = str(uuid.uuid4())[:8].upper()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO inscricoes_evento (evento_id, pessoa_id, qrcode_checkin)
            VALUES (?, ?, ?)
        ''', (evento_id, pessoa_id, qrcode_str))

def registrar_presenca(evento_id: int, pessoa_id: int, tipo: str = 'manual'):
    """Registra presença de uma pessoa em um evento"""
    usuario = get_usuario_atual()
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Verificar se já tem presença registrada
        cursor.execute('''
            SELECT id FROM presenca_evento WHERE evento_id = ? AND pessoa_id = ?
        ''', (evento_id, pessoa_id))
        
        if cursor.fetchone():
            return False  # Já tem presença
        
        cursor.execute('''
            INSERT INTO presenca_evento (evento_id, pessoa_id, tipo_checkin)
            VALUES (?, ?, ?)
        ''', (evento_id, pessoa_id, tipo))
        
        registrar_log(usuario['id'], igreja_id, 'evento.presenca', f"Presença registrada: evento {evento_id}, pessoa {pessoa_id}")
        return True

def get_inscritos_evento(evento_id: int) -> list:
    """Busca inscritos em um evento"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.id, p.nome, p.celular, p.email, ie.status, ie.data_inscricao,
                   (SELECT COUNT(*) FROM presenca_evento pe WHERE pe.evento_id = ie.evento_id AND pe.pessoa_id = p.id) as presente
            FROM pessoas p
            JOIN inscricoes_evento ie ON p.id = ie.pessoa_id
            WHERE ie.evento_id = ?
            ORDER BY p.nome
        ''', (evento_id,))
        return [dict(row) for row in cursor.fetchall()]

def get_presentes_evento(evento_id: int) -> list:
    """Busca presenças em um evento"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.id, p.nome, p.celular, pe.data_checkin, pe.tipo_checkin
            FROM pessoas p
            JOIN presenca_evento pe ON p.id = pe.pessoa_id
            WHERE pe.evento_id = ?
            ORDER BY pe.data_checkin DESC
        ''', (evento_id,))
        return [dict(row) for row in cursor.fetchall()]

def get_pessoas_para_checkin(evento_id: int) -> list:
    """Busca pessoas disponíveis para check-in"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.id, p.nome, p.celular
            FROM pessoas p
            WHERE p.igreja_id = ? AND p.ativo = 1
            AND p.id NOT IN (SELECT pessoa_id FROM presenca_evento WHERE evento_id = ?)
            ORDER BY p.nome
        ''', (igreja_id, evento_id))
        return [dict(row) for row in cursor.fetchall()]

# ========================================
# RENDERIZAÇÃO DA INTERFACE
# ========================================

def render_lista_eventos():
    """Renderiza lista de eventos"""
    st.subheader("📅 Eventos")
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        filtro = st.selectbox("Filtrar", options=['proximos', 'hoje', 'passados', 'todos'],
                             format_func=lambda x: {'proximos': 'Próximos', 'hoje': 'Hoje', 
                                                   'passados': 'Passados', 'todos': 'Todos'}.get(x, x))
    
    with col3:
        if st.button("➕ Novo Evento", use_container_width=True):
            st.session_state.show_form_evento = True
    
    # Formulário de novo evento
    if st.session_state.get('show_form_evento'):
        with st.expander("➕ Novo Evento", expanded=True):
            with st.form("form_evento"):
                nome = st.text_input("Nome do evento *")
                descricao = st.text_area("Descrição", height=80)
                
                col1, col2 = st.columns(2)
                with col1:
                    tipo = st.selectbox("Tipo", options=TIPOS_EVENTO)
                    data_inicio = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
                    hora_inicio = st.time_input("Horário")
                
                with col2:
                    local = st.text_input("Local")
                    capacidade = st.number_input("Capacidade", min_value=0, value=0, 
                                                help="0 = ilimitado")
                    valor = st.number_input("Valor inscrição (R$)", min_value=0.0, value=0.0)
                
                requer_inscricao = st.checkbox("Requer inscrição prévia")
                
                col1, col2 = st.columns(2)
                with col1:
                    submit = st.form_submit_button("💾 Salvar", use_container_width=True)
                with col2:
                    if st.form_submit_button("❌ Cancelar", use_container_width=True):
                        st.session_state.show_form_evento = False
                        st.rerun()
                
                if submit:
                    if not nome:
                        st.error("Nome é obrigatório!")
                    else:
                        data_inicio_completa = datetime.combine(data_inicio, hora_inicio)
                        salvar_evento({
                            'nome': nome,
                            'descricao': descricao,
                            'tipo': tipo,
                            'data_inicio': data_inicio_completa,
                            'local': local,
                            'capacidade': capacidade if capacidade > 0 else None,
                            'valor_inscricao': valor,
                            'requer_inscricao': 1 if requer_inscricao else 0
                        })
                        st.success("✅ Evento criado!")
                        st.session_state.show_form_evento = False
                        st.rerun()
    
    # Lista de eventos
    eventos = get_eventos(filtro)
    
    if not eventos:
        st.info("Nenhum evento encontrado.")
        return
    
    for evento in eventos:
        tipo_icon = {
            'Culto Dominical': '⛪',
            'Culto de Oração': '🙏',
            'Célula': '🏠',
            'Congresso': '🎤',
            'Conferência': '📢',
            'Curso': '📚',
            'Batismo': '💧',
            'Retiro': '🏕️'
        }.get(evento.get('tipo', ''), '📅')
        
        data_evento = evento['data_inicio']
        if isinstance(data_evento, str):
            try:
                data_evento = datetime.fromisoformat(data_evento)
            except:
                data_evento = None
        
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
            
            with col1:
                st.markdown(f"**{tipo_icon} {evento['nome']}**")
                if data_evento:
                    st.caption(f"📅 {data_evento.strftime('%d/%m/%Y %H:%M')}")
            
            with col2:
                if evento.get('local'):
                    st.caption(f"📍 {evento['local']}")
                st.write(f"📝 {evento['tipo']}")
            
            with col3:
                col_a, col_b = st.columns(2)
                with col_a:
                    st.metric("Inscritos", evento['total_inscritos'])
                with col_b:
                    st.metric("Presentes", evento['total_presentes'])
            
            with col4:
                if st.button("👁️", key=f"ver_evt_{evento['id']}", help="Ver evento"):
                    st.session_state.evento_view = evento['id']
                    st.rerun()
                if st.button("✅", key=f"checkin_evt_{evento['id']}", help="Check-in"):
                    st.session_state.evento_checkin = evento['id']
                    st.rerun()
        
        st.markdown("<hr style='margin: 0.5rem 0; opacity: 0.2;'>", unsafe_allow_html=True)

def render_detalhes_evento(evento_id: int):
    """Renderiza detalhes de um evento"""
    evento = get_evento(evento_id)
    
    if not evento:
        st.error("Evento não encontrado!")
        return
    
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("← Voltar"):
            st.session_state.evento_view = None
            st.rerun()
    
    # Cabeçalho do evento
    st.markdown(f"""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 2rem; border-radius: 10px; color: white; margin-bottom: 1rem;'>
            <h2 style='margin: 0;'>{evento['nome']}</h2>
            <p style='margin: 0.5rem 0 0 0; opacity: 0.9;'>{evento.get('tipo', '')}</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Informações e QR Code
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 📋 Informações")
        
        data_evento = evento['data_inicio']
        if isinstance(data_evento, str):
            try:
                data_evento = datetime.fromisoformat(data_evento)
            except:
                data_evento = None
        
        if data_evento:
            st.write(f"📅 **Data:** {data_evento.strftime('%d/%m/%Y às %H:%M')}")
        if evento.get('local'):
            st.write(f"📍 **Local:** {evento['local']}")
        if evento.get('capacidade'):
            st.write(f"👥 **Capacidade:** {evento['capacidade']} pessoas")
        if evento.get('valor_inscricao') and evento['valor_inscricao'] > 0:
            st.write(f"💰 **Valor:** R$ {evento['valor_inscricao']:.2f}")
        
        if evento.get('descricao'):
            st.markdown("### 📝 Descrição")
            st.write(evento['descricao'])
    
    with col2:
        st.markdown("### 📱 QR Code Check-in")
        qr_data = f"CRM-IGREJA-CHECKIN:{evento['qrcode']}"
        qr_img = gerar_qrcode(qr_data)
        st.image(qr_img, width=200)
        st.caption(f"Código: {evento['qrcode']}")
    
    # Tabs de gestão
    tab1, tab2, tab3 = st.tabs(["✅ Presenças", "📝 Inscritos", "📊 Relatório"])
    
    with tab1:
        presentes = get_presentes_evento(evento_id)
        st.metric("Total de Presenças", len(presentes))
        
        if presentes:
            for p in presentes:
                st.write(f"✅ {p['nome']} - {p['data_checkin']}")
        else:
            st.info("Nenhuma presença registrada ainda.")
    
    with tab2:
        inscritos = get_inscritos_evento(evento_id)
        st.metric("Total de Inscritos", len(inscritos))
        
        if inscritos:
            for i in inscritos:
                presente_icon = "✅" if i['presente'] else "⬜"
                st.write(f"{presente_icon} {i['nome']} - {i.get('celular', 'N/A')}")
        else:
            st.info("Nenhuma inscrição registrada.")
    
    with tab3:
        st.markdown("### 📊 Estatísticas")
        
        inscritos = get_inscritos_evento(evento_id)
        presentes = get_presentes_evento(evento_id)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Inscritos", len(inscritos))
        col2.metric("Presentes", len(presentes))
        
        if len(inscritos) > 0:
            taxa = len(presentes) / len(inscritos) * 100
            col3.metric("Taxa de Presença", f"{taxa:.1f}%")

def render_checkin(evento_id: int):
    """Renderiza tela de check-in"""
    evento = get_evento(evento_id)
    
    if not evento:
        st.error("Evento não encontrado!")
        return
    
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("← Voltar"):
            st.session_state.evento_checkin = None
            st.rerun()
    
    st.subheader(f"✅ Check-in: {evento['nome']}")
    
    # Métricas em tempo real
    presentes = get_presentes_evento(evento_id)
    col1, col2, col3 = st.columns(3)
    col1.metric("Check-ins Realizados", len(presentes))
    if evento.get('capacidade'):
        col2.metric("Capacidade", evento['capacidade'])
        col3.metric("Disponível", evento['capacidade'] - len(presentes))
    
    st.markdown("---")
    
    # Check-in rápido
    tab1, tab2 = st.tabs(["🔍 Buscar Pessoa", "📱 QR Code"])
    
    with tab1:
        pessoas = get_pessoas_para_checkin(evento_id)
        
        if not pessoas:
            st.success("🎉 Todos já fizeram check-in!")
        else:
            busca = st.text_input("🔍 Buscar por nome ou celular")
            
            pessoas_filtradas = pessoas
            if busca:
                pessoas_filtradas = [p for p in pessoas if busca.lower() in p['nome'].lower() 
                                    or (p.get('celular') and busca in p.get('celular', ''))]
            
            for pessoa in pessoas_filtradas[:20]:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"👤 {pessoa['nome']}")
                    if pessoa.get('celular'):
                        st.caption(pessoa['celular'])
                with col2:
                    if st.button("✅ Check-in", key=f"chk_{pessoa['id']}"):
                        if registrar_presenca(evento_id, pessoa['id'], 'manual'):
                            st.success(f"✅ {pessoa['nome']} registrado!")
                            st.rerun()
                        else:
                            st.warning("Presença já registrada!")
    
    with tab2:
        st.markdown("### 📱 Check-in por QR Code")
        st.info("Em produção, aqui seria integrado com câmera para leitura de QR Code")
        
        codigo = st.text_input("Digite o código do QR Code")
        if st.button("Verificar"):
            st.warning("Funcionalidade de QR Code em desenvolvimento")
    
    # Lista de presenças recentes
    st.markdown("---")
    st.markdown("### 📋 Últimos Check-ins")
    
    for p in presentes[:10]:
        st.write(f"✅ {p['nome']} - {p['data_checkin']}")

def render_relatorios_presenca():
    """Renderiza relatórios de presença"""
    st.subheader("📊 Relatórios de Presença")
    
    igreja_id = get_igreja_id()
    
    # Presença por período
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Eventos dos últimos 30 dias com presença
        cursor.execute('''
            SELECT e.nome, e.tipo, e.data_inicio,
                   (SELECT COUNT(*) FROM presenca_evento pe WHERE pe.evento_id = e.id) as total_presentes
            FROM eventos e
            WHERE e.igreja_id = ? AND e.data_inicio >= date('now', '-30 days')
            ORDER BY e.data_inicio DESC
        ''', (igreja_id,))
        eventos_recentes = [dict(row) for row in cursor.fetchall()]
    
    if eventos_recentes:
        st.markdown("### 📅 Últimos 30 dias")
        
        df = pd.DataFrame(eventos_recentes)
        df.columns = ['Evento', 'Tipo', 'Data', 'Presenças']
        st.dataframe(df, use_container_width=True)
        
        # Gráfico
        st.bar_chart(df.set_index('Evento')['Presenças'])
    else:
        st.info("Nenhum evento no período.")

def render_eventos():
    """Função principal do módulo de eventos"""
    
    # Verificar estados especiais
    if st.session_state.get('evento_view'):
        render_detalhes_evento(st.session_state.evento_view)
        return
    
    if st.session_state.get('evento_checkin'):
        render_checkin(st.session_state.evento_checkin)
        return
    
    tab1, tab2 = st.tabs(["📅 Eventos", "📊 Relatórios"])
    
    with tab1:
        render_lista_eventos()
    
    with tab2:
        render_relatorios_presenca()
