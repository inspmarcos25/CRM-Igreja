"""
Módulo de Agenda/Calendário
Visualização e gestão de compromissos da igreja
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database.db import get_connection
from modules.auth import get_igreja_id, get_usuario_atual, registrar_log
from config.settings import formatar_data_br

# ==================== FUNÇÕES DE DADOS ====================

def get_eventos_calendario(data_inicio: date, data_fim: date, filtros: dict = None) -> list:
    """Busca eventos do calendário"""
    igreja_id = get_igreja_id()
    
    query = '''
        SELECT a.*, 
               m.nome as ministerio_nome,
               c.nome as celula_nome,
               u.nome as criador_nome
        FROM agenda a
        LEFT JOIN ministerios m ON a.ministerio_id = m.id
        LEFT JOIN celulas c ON a.celula_id = c.id
        LEFT JOIN usuarios u ON a.criado_por = u.id
        WHERE a.igreja_id = ?
        AND date(a.data_inicio) BETWEEN ? AND ?
    '''
    params = [igreja_id, data_inicio, data_fim]
    
    if filtros:
        if filtros.get('tipo'):
            query += ' AND a.tipo = ?'
            params.append(filtros['tipo'])
        if filtros.get('ministerio_id'):
            query += ' AND a.ministerio_id = ?'
            params.append(filtros['ministerio_id'])
    
    query += ' ORDER BY a.data_inicio'
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def get_evento_agenda(evento_id: int) -> dict:
    """Busca um evento específico"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM agenda WHERE id = ?', (evento_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def salvar_evento_agenda(dados: dict) -> int:
    """Salva ou atualiza evento na agenda"""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        if dados.get('id'):
            cursor.execute('''
                UPDATE agenda
                SET titulo = ?, descricao = ?, tipo = ?, data_inicio = ?, data_fim = ?,
                    dia_todo = ?, local = ?, cor = ?, recorrencia = ?, lembrete_minutos = ?,
                    ministerio_id = ?, celula_id = ?
                WHERE id = ? AND igreja_id = ?
            ''', (dados['titulo'], dados.get('descricao'), dados.get('tipo', 'evento'),
                  dados['data_inicio'], dados.get('data_fim'), dados.get('dia_todo', 0),
                  dados.get('local'), dados.get('cor', '#3498db'), dados.get('recorrencia'),
                  dados.get('lembrete_minutos'), dados.get('ministerio_id'), dados.get('celula_id'),
                  dados['id'], igreja_id))
            return dados['id']
        else:
            cursor.execute('''
                INSERT INTO agenda (igreja_id, titulo, descricao, tipo, data_inicio, data_fim,
                                   dia_todo, local, cor, recorrencia, lembrete_minutos,
                                   criado_por, ministerio_id, celula_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (igreja_id, dados['titulo'], dados.get('descricao'), dados.get('tipo', 'evento'),
                  dados['data_inicio'], dados.get('data_fim'), dados.get('dia_todo', 0),
                  dados.get('local'), dados.get('cor', '#3498db'), dados.get('recorrencia'),
                  dados.get('lembrete_minutos'), usuario['id'], dados.get('ministerio_id'),
                  dados.get('celula_id')))
            
            registrar_log(usuario['id'], igreja_id, 'agenda.criar', f"Evento criado: {dados['titulo']}")
            return cursor.lastrowid

def excluir_evento_agenda(evento_id: int):
    """Exclui evento da agenda"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM agenda WHERE id = ? AND igreja_id = ?', (evento_id, igreja_id))

def get_proximos_compromissos(dias: int = 7) -> list:
    """Busca próximos compromissos"""
    igreja_id = get_igreja_id()
    data_fim = date.today() + timedelta(days=dias)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT a.*, m.nome as ministerio_nome
            FROM agenda a
            LEFT JOIN ministerios m ON a.ministerio_id = m.id
            WHERE a.igreja_id = ?
            AND date(a.data_inicio) BETWEEN date('now') AND ?
            ORDER BY a.data_inicio
            LIMIT 10
        ''', (igreja_id, data_fim))
        return [dict(row) for row in cursor.fetchall()]

def criar_lembrete(agenda_id: int, pessoa_id: int, data_lembrete: datetime, canal: str = 'whatsapp'):
    """Cria um lembrete para um evento"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO lembretes (agenda_id, pessoa_id, data_lembrete, canal)
            VALUES (?, ?, ?, ?)
        ''', (agenda_id, pessoa_id, data_lembrete, canal))

def get_eventos_hoje() -> list:
    """Busca eventos de hoje"""
    return get_eventos_calendario(date.today(), date.today())

# ==================== RENDERIZAÇÃO ====================

def render_agenda():
    """Função principal do módulo de agenda"""
    st.title("📅 Agenda & Calendário")
    
    tab1, tab2, tab3 = st.tabs([
        "📆 Calendário",
        "📋 Lista",
        "➕ Novo Evento"
    ])
    
    with tab1:
        render_calendario()
    
    with tab2:
        render_lista_eventos()
    
    with tab3:
        render_novo_evento()

def render_calendario():
    """Renderiza visualização de calendário"""
    st.subheader("📆 Calendário Mensal")
    
    # Controles de navegação
    col1, col2, col3 = st.columns([1, 2, 1])
    
    if 'mes_atual' not in st.session_state:
        st.session_state.mes_atual = date.today().replace(day=1)
    
    with col1:
        if st.button("◀️ Anterior"):
            st.session_state.mes_atual = (st.session_state.mes_atual - timedelta(days=1)).replace(day=1)
            st.rerun()
    
    with col2:
        meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        st.markdown(f"<h3 style='text-align: center;'>{meses[st.session_state.mes_atual.month - 1]} {st.session_state.mes_atual.year}</h3>", unsafe_allow_html=True)
    
    with col3:
        if st.button("Próximo ▶️"):
            proximo = st.session_state.mes_atual + timedelta(days=32)
            st.session_state.mes_atual = proximo.replace(day=1)
            st.rerun()
    
    # Calcular dias do mês
    mes_inicio = st.session_state.mes_atual
    if mes_inicio.month == 12:
        mes_fim = date(mes_inicio.year + 1, 1, 1) - timedelta(days=1)
    else:
        mes_fim = date(mes_inicio.year, mes_inicio.month + 1, 1) - timedelta(days=1)
    
    # Buscar eventos do mês
    eventos = get_eventos_calendario(mes_inicio, mes_fim)
    
    # Agrupar eventos por dia
    eventos_por_dia = {}
    for e in eventos:
        data_str = str(e['data_inicio'])[:10]
        if data_str not in eventos_por_dia:
            eventos_por_dia[data_str] = []
        eventos_por_dia[data_str].append(e)
    
    # Renderizar calendário
    st.markdown("""
        <style>
        .cal-header { 
            text-align: center; 
            font-weight: bold; 
            padding: 0.5rem;
            background: #f0f2f6;
        }
        .cal-day {
            min-height: 80px;
            border: 1px solid #ddd;
            padding: 0.3rem;
            vertical-align: top;
        }
        .cal-day-num {
            font-weight: bold;
            font-size: 0.9rem;
        }
        .cal-event {
            font-size: 0.7rem;
            padding: 2px 4px;
            border-radius: 3px;
            margin: 1px 0;
            color: white;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .cal-today {
            background: #e3f2fd !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Cabeçalho da semana
    dias_semana = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']
    cols = st.columns(7)
    for i, dia in enumerate(dias_semana):
        cols[i].markdown(f"<div class='cal-header'>{dia}</div>", unsafe_allow_html=True)
    
    # Dias do mês
    dia_semana_inicio = mes_inicio.weekday()
    dia_semana_inicio = (dia_semana_inicio + 1) % 7  # Ajustar para domingo = 0
    
    dia_atual = 1
    total_dias = mes_fim.day
    
    # Preencher semanas
    semana = 0
    while dia_atual <= total_dias:
        cols = st.columns(7)
        
        for i in range(7):
            if semana == 0 and i < dia_semana_inicio:
                cols[i].write("")
            elif dia_atual <= total_dias:
                data_str = f"{mes_inicio.year}-{mes_inicio.month:02d}-{dia_atual:02d}"
                is_hoje = date.today() == date(mes_inicio.year, mes_inicio.month, dia_atual)
                
                html_eventos = ""
                if data_str in eventos_por_dia:
                    for e in eventos_por_dia[data_str][:3]:
                        cor = e.get('cor', '#3498db')
                        html_eventos += f"<div class='cal-event' style='background:{cor};'>{e['titulo']}</div>"
                    if len(eventos_por_dia[data_str]) > 3:
                        html_eventos += f"<small>+{len(eventos_por_dia[data_str]) - 3} mais</small>"
                
                classe_hoje = "cal-today" if is_hoje else ""
                
                cols[i].markdown(f"""
                    <div class='cal-day {classe_hoje}'>
                        <span class='cal-day-num'>{dia_atual}</span>
                        {html_eventos}
                    </div>
                """, unsafe_allow_html=True)
                
                dia_atual += 1
            else:
                cols[i].write("")
        
        semana += 1
    
    # Legenda de tipos
    st.markdown("---")
    st.markdown("**Legenda:**")
    col1, col2, col3, col4 = st.columns(4)
    col1.markdown("🔵 Culto/Evento")
    col2.markdown("🟢 Célula")
    col3.markdown("🟡 Reunião")
    col4.markdown("🔴 Especial")

def render_lista_eventos():
    """Renderiza lista de eventos"""
    st.subheader("📋 Lista de Eventos")
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        periodo = st.selectbox(
            "Período",
            options=['Esta semana', 'Este mês', 'Próximos 30 dias', 'Todos'],
            index=2
        )
    with col2:
        tipo = st.selectbox(
            "Tipo",
            options=['Todos', 'evento', 'culto', 'reuniao', 'celula', 'especial'],
            format_func=lambda x: {'Todos': 'Todos', 'evento': 'Evento', 'culto': 'Culto',
                                   'reuniao': 'Reunião', 'celula': 'Célula', 'especial': 'Especial'}[x]
        )
    
    # Definir período
    hoje = date.today()
    if periodo == 'Esta semana':
        data_inicio = hoje - timedelta(days=hoje.weekday())
        data_fim = data_inicio + timedelta(days=6)
    elif periodo == 'Este mês':
        data_inicio = hoje.replace(day=1)
        if hoje.month == 12:
            data_fim = date(hoje.year + 1, 1, 1) - timedelta(days=1)
        else:
            data_fim = date(hoje.year, hoje.month + 1, 1) - timedelta(days=1)
    elif periodo == 'Próximos 30 dias':
        data_inicio = hoje
        data_fim = hoje + timedelta(days=30)
    else:
        data_inicio = hoje - timedelta(days=365)
        data_fim = hoje + timedelta(days=365)
    
    filtros = {}
    if tipo != 'Todos':
        filtros['tipo'] = tipo
    
    eventos = get_eventos_calendario(data_inicio, data_fim, filtros)
    
    if not eventos:
        st.info("Nenhum evento encontrado no período.")
        return
    
    # Agrupar por data
    eventos_por_data = {}
    for e in eventos:
        data = str(e['data_inicio'])[:10]
        if data not in eventos_por_data:
            eventos_por_data[data] = []
        eventos_por_data[data].append(e)
    
    for data, lista in eventos_por_data.items():
        st.markdown(f"### 📅 {formatar_data_br(data)}")
        
        for evento in lista:
            cor = evento.get('cor', '#3498db')
            hora = str(evento['data_inicio'])[11:16] if len(str(evento['data_inicio'])) > 10 else ""
            
            col1, col2, col3 = st.columns([4, 2, 1])
            
            with col1:
                st.markdown(f"""
                    <div style='border-left: 4px solid {cor}; padding-left: 1rem;'>
                        <strong>{evento['titulo']}</strong><br>
                        <small>🕐 {hora or 'Dia todo'} | 📍 {evento.get('local', 'A definir')}</small>
                    </div>
                """, unsafe_allow_html=True)
            
            with col2:
                if evento.get('ministerio_nome'):
                    st.caption(f"🎵 {evento['ministerio_nome']}")
            
            with col3:
                if st.button("🗑️", key=f"del_{evento['id']}", help="Excluir"):
                    excluir_evento_agenda(evento['id'])
                    st.rerun()
        
        st.markdown("---")

def render_novo_evento():
    """Renderiza formulário de novo evento"""
    st.subheader("➕ Novo Evento na Agenda")
    
    with st.form("novo_evento_agenda"):
        titulo = st.text_input("Título *")
        descricao = st.text_area("Descrição")
        
        col1, col2 = st.columns(2)
        with col1:
            tipo = st.selectbox(
                "Tipo",
                options=['evento', 'culto', 'reuniao', 'celula', 'especial'],
                format_func=lambda x: {'evento': '📌 Evento', 'culto': '⛪ Culto', 
                                       'reuniao': '👥 Reunião', 'celula': '🏠 Célula',
                                       'especial': '⭐ Especial'}[x]
            )
        with col2:
            cor = st.color_picker("Cor", value='#3498db')
        
        col3, col4 = st.columns(2)
        with col3:
            data_evento = st.date_input("Data *", format="DD/MM/YYYY")
        with col4:
            dia_todo = st.checkbox("Dia todo")
        
        if not dia_todo:
            col5, col6 = st.columns(2)
            with col5:
                hora_inicio = st.time_input("Hora início")
            with col6:
                hora_fim = st.time_input("Hora fim")
        
        local = st.text_input("Local")
        
        # Vinculação opcional
        st.markdown("**Vincular a (opcional):**")
        col7, col8 = st.columns(2)
        
        with col7:
            from modules.ministerios import get_ministerios
            ministerios = get_ministerios()
            ministerio = st.selectbox(
                "Ministério",
                options=[None] + ministerios,
                format_func=lambda x: x['nome'] if x else 'Nenhum'
            )
        
        with col8:
            from modules.ministerios import get_celulas
            celulas = get_celulas()
            celula = st.selectbox(
                "Célula",
                options=[None] + celulas,
                format_func=lambda x: x['nome'] if x else 'Nenhuma'
            )
        
        # Recorrência
        recorrencia = st.selectbox(
            "Recorrência",
            options=[None, 'diaria', 'semanal', 'quinzenal', 'mensal'],
            format_func=lambda x: {'diaria': 'Diária', 'semanal': 'Semanal',
                                   'quinzenal': 'Quinzenal', 'mensal': 'Mensal'}.get(x, 'Sem recorrência')
        )
        
        submit = st.form_submit_button("💾 Salvar", use_container_width=True)
        
        if submit:
            if not titulo:
                st.error("Título é obrigatório!")
            else:
                if dia_todo:
                    data_inicio = datetime.combine(data_evento, datetime.min.time())
                    data_fim = datetime.combine(data_evento, datetime.max.time())
                else:
                    data_inicio = datetime.combine(data_evento, hora_inicio)
                    data_fim = datetime.combine(data_evento, hora_fim)
                
                salvar_evento_agenda({
                    'titulo': titulo,
                    'descricao': descricao,
                    'tipo': tipo,
                    'data_inicio': data_inicio,
                    'data_fim': data_fim,
                    'dia_todo': 1 if dia_todo else 0,
                    'local': local,
                    'cor': cor,
                    'recorrencia': recorrencia,
                    'ministerio_id': ministerio['id'] if ministerio else None,
                    'celula_id': celula['id'] if celula else None
                })
                
                st.success("✅ Evento criado com sucesso!")
                st.rerun()
