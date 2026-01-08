"""
Módulo de Dashboard & Indicadores Estratégicos
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
from database.db import get_connection
from modules.auth import get_igreja_id, get_usuario_atual, tem_permissao
from config.settings import formatar_data_br

@st.cache_data(ttl=120, show_spinner=False)
def get_metricas_gerais() -> dict:
    """Coleta métricas gerais da igreja (cache curto para aliviar consultas repetidas)."""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Total de pessoas por status
        cursor.execute('''
            SELECT status, COUNT(*) as total
            FROM pessoas
            WHERE igreja_id = ? AND ativo = 1
            GROUP BY status
        ''', (igreja_id,))
        por_status = {row['status']: row['total'] for row in cursor.fetchall()}
        
        # Total geral
        total_pessoas = sum(por_status.values())
        
        # Novos membros no mês
        cursor.execute('''
            SELECT COUNT(*) FROM pessoas
            WHERE igreja_id = ? AND ativo = 1
            AND data_membresia >= date('now', 'start of month')
        ''', (igreja_id,))
        novos_membros_mes = cursor.fetchone()[0]
        
        # Visitantes no mês
        cursor.execute('''
            SELECT COUNT(DISTINCT pessoa_id) FROM visitas
            WHERE data_visita >= date('now', 'start of month')
            AND pessoa_id IN (SELECT id FROM pessoas WHERE igreja_id = ?)
        ''', (igreja_id,))
        visitantes_mes = cursor.fetchone()[0]
        
        # Total de células
        cursor.execute('''
            SELECT COUNT(*) FROM celulas
            WHERE igreja_id = ? AND ativo = 1
        ''', (igreja_id,))
        total_celulas = cursor.fetchone()[0]
        
        # Total de ministérios
        cursor.execute('''
            SELECT COUNT(*) FROM ministerios
            WHERE igreja_id = ? AND ativo = 1
        ''', (igreja_id,))
        total_ministerios = cursor.fetchone()[0]
        
        return {
            'total_pessoas': total_pessoas,
            'por_status': por_status,
            'membros': por_status.get('membro', 0),
            'visitantes': por_status.get('visitante', 0),
            'novos_convertidos': por_status.get('novo_convertido', 0),
            'novos_membros_mes': novos_membros_mes,
            'visitantes_mes': visitantes_mes,
            'total_celulas': total_celulas,
            'total_ministerios': total_ministerios
        }

@st.cache_data(ttl=120, show_spinner=False)
def get_crescimento_mensal(meses: int = 12) -> list:
    """Retorna dados de crescimento mensal no intervalo solicitado."""
    igreja_id = get_igreja_id()
    intervalo = f'-{meses} months'
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Membros novos por mês (últimos 12 meses)
        cursor.execute('''
            SELECT strftime('%Y-%m', data_membresia) as mes, COUNT(*) as novos
            FROM pessoas
            WHERE igreja_id = ? AND data_membresia IS NOT NULL
            AND data_membresia >= date('now', ?)
            GROUP BY mes
            ORDER BY mes
        ''', (igreja_id, intervalo))
        
        return [dict(row) for row in cursor.fetchall()]

@st.cache_data(ttl=120, show_spinner=False)
def get_visitantes_conversao(meses_visitantes: int = 6, janela_conversao_dias: int = 365) -> dict:
    """Retorna dados de visitantes e conversão."""
    igreja_id = get_igreja_id()
    mod_visitantes = f'-{meses_visitantes} months'
    mod_conversao = f'-{janela_conversao_dias} days'
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Visitantes por mês
        cursor.execute('''
            SELECT strftime('%Y-%m', v.data_visita) as mes, 
                   COUNT(DISTINCT v.pessoa_id) as visitantes
            FROM visitas v
            JOIN pessoas p ON v.pessoa_id = p.id
            WHERE p.igreja_id = ?
            AND v.data_visita >= date('now', ?)
            GROUP BY mes
            ORDER BY mes
        ''', (igreja_id, mod_visitantes))
        visitantes_mes = [dict(row) for row in cursor.fetchall()]
        
        # Taxa de conversão (visitantes que se tornaram membros)
        cursor.execute('''
            SELECT COUNT(*) FROM pessoas
            WHERE igreja_id = ? AND status = 'membro'
            AND data_primeira_visita IS NOT NULL
            AND data_membresia >= date('now', ?)
        ''', (igreja_id, mod_conversao))
        convertidos = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) FROM pessoas
            WHERE igreja_id = ?
            AND data_primeira_visita >= date('now', ?)
        ''', (igreja_id, mod_conversao))
        total_visitantes_ano = cursor.fetchone()[0]
        
        taxa_conversao = (convertidos / total_visitantes_ano * 100) if total_visitantes_ano > 0 else 0
        
        return {
            'visitantes_mes': visitantes_mes,
            'convertidos': convertidos,
            'total_visitantes_ano': total_visitantes_ano,
            'taxa_conversao': taxa_conversao
        }

@st.cache_data(ttl=120, show_spinner=False)
def get_frequencia_media(dias: int = 30) -> dict:
    """Retorna dados de frequência média para o período indicado."""
    igreja_id = get_igreja_id()
    mod_dias = f'-{dias} days'
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Média de presença em cultos (últimos 30 dias)
        cursor.execute('''
            SELECT e.nome, e.data_inicio, COUNT(pe.id) as presentes
            FROM eventos e
            LEFT JOIN presenca_evento pe ON e.id = pe.evento_id
            WHERE e.igreja_id = ? AND e.tipo = 'Culto Dominical'
            AND e.data_inicio >= date('now', ?)
            GROUP BY e.id
            ORDER BY e.data_inicio DESC
        ''', (igreja_id, mod_dias))
        presenca_cultos = [dict(row) for row in cursor.fetchall()]
        
        media = sum([p['presentes'] for p in presenca_cultos]) / len(presenca_cultos) if presenca_cultos else 0
        
        return {
            'presenca_cultos': presenca_cultos,
            'media_presenca': media
        }

@st.cache_data(ttl=120, show_spinner=False)
def get_saude_celulas() -> list:
    """Retorna indicadores de saúde das células."""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT c.id, c.nome, l.nome as lider_nome,
                   (SELECT COUNT(*) FROM pessoa_celulas pc WHERE pc.celula_id = c.id AND pc.ativo = 1) as membros,
                   (SELECT AVG(total_presentes) FROM reunioes_celula rc WHERE rc.celula_id = c.id AND rc.data >= date('now', '-30 days')) as media_presenca,
                   (SELECT COUNT(*) FROM reunioes_celula rc WHERE rc.celula_id = c.id AND rc.data >= date('now', '-30 days')) as reunioes_mes
            FROM celulas c
            LEFT JOIN pessoas l ON c.lider_id = l.id
            WHERE c.igreja_id = ? AND c.ativo = 1
            ORDER BY c.nome
        ''', (igreja_id,))
        
        celulas = []
        for row in cursor.fetchall():
            celula = dict(row)
            membros = celula['membros'] or 0
            media = celula['media_presenca'] or 0
            reunioes = celula['reunioes_mes'] or 0
            
            # Calcular score de saúde
            score = 0
            if membros >= 5:
                score += 25
            if media >= membros * 0.7:
                score += 25
            if reunioes >= 4:
                score += 25
            if membros <= 15:  # Não muito grande
                score += 25
            
            celula['score'] = score
            celula['status'] = 'saudavel' if score >= 75 else ('atencao' if score >= 50 else 'critico')
            celulas.append(celula)
        
        return celulas

@st.cache_data(ttl=120, show_spinner=False)
def get_doacoes_periodo(meses: int = 6) -> dict:
    """Retorna dados de doações do período."""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    # Verificar permissão
    if not tem_permissao(usuario, 'doacoes.ver'):
        return None
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Total do mês atual
        cursor.execute('''
            SELECT SUM(valor) FROM doacoes
            WHERE igreja_id = ? AND data >= date('now', 'start of month')
        ''', (igreja_id,))
        total_mes = cursor.fetchone()[0] or 0
        
        # Total do mês anterior
        cursor.execute('''
            SELECT SUM(valor) FROM doacoes
            WHERE igreja_id = ? 
            AND data >= date('now', 'start of month', '-1 month')
            AND data < date('now', 'start of month')
        ''', (igreja_id,))
        total_mes_anterior = cursor.fetchone()[0] or 0
        
        variacao = ((total_mes - total_mes_anterior) / total_mes_anterior * 100) if total_mes_anterior > 0 else 0
        
        # Por tipo no mês
        cursor.execute('''
            SELECT tipo, SUM(valor) as total
            FROM doacoes
            WHERE igreja_id = ? AND data >= date('now', 'start of month')
            GROUP BY tipo
        ''', (igreja_id,))
        por_tipo = {row['tipo']: row['total'] for row in cursor.fetchall()}
        
        # Evolução mensal
        mod_meses = f'-{meses} months'
        cursor.execute('''
            SELECT strftime('%Y-%m', data) as mes, SUM(valor) as total
            FROM doacoes
            WHERE igreja_id = ? AND data >= date('now', ?)
            GROUP BY mes
            ORDER BY mes
        ''', (igreja_id, mod_meses))
        evolucao = [dict(row) for row in cursor.fetchall()]
        
        return {
            'total_mes': total_mes,
            'total_mes_anterior': total_mes_anterior,
            'variacao': variacao,
            'por_tipo': por_tipo,
            'evolucao': evolucao
        }

# ========================================
# RENDERIZAÇÃO DOS DASHBOARDS
# ========================================

def render_dashboard_geral():
    """Renderiza dashboard geral"""
    st.subheader("📊 Visão Geral")
    
    meses_crescimento = st.slider("Meses para gráfico de crescimento", 6, 24, 12, 1, key="dash_mes_cresc")
    metricas = get_metricas_gerais()
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric(
        "Total de Pessoas",
        metricas['total_pessoas'],
        f"+{metricas['novos_membros_mes']} este mês"
    )
    
    col2.metric(
        "Membros",
        metricas['membros']
    )
    
    col3.metric(
        "Visitantes (mês)",
        metricas['visitantes_mes']
    )
    
    col4.metric(
        "Células",
        metricas['total_celulas']
    )
    
    st.markdown("---")
    
    # Gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 👥 Distribuição por Status")
        if metricas['por_status']:
            df_status = pd.DataFrame([
                {'Status': k.replace('_', ' ').title(), 'Total': v}
                for k, v in metricas['por_status'].items()
            ])
            fig = px.pie(df_status, values='Total', names='Status', hole=0.4)
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados")
    
    with col2:
        st.markdown("### 📈 Crescimento de Membros")
        crescimento = get_crescimento_mensal(meses_crescimento)
        if crescimento:
            df_cresc = pd.DataFrame(crescimento)
            df_cresc['mes'] = pd.to_datetime(df_cresc['mes'])
            df_cresc = df_cresc.sort_values('mes')
            fig = px.bar(df_cresc, x='mes', y='novos', 
                        labels={'mes': 'Mês', 'novos': 'Novos Membros'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados de crescimento")

def render_dashboard_visitantes():
    """Renderiza dashboard de visitantes e conversão"""
    st.subheader("👋 Visitantes & Conversão")
    
    meses_vis = st.slider("Meses no gráfico de visitantes", 3, 12, 6, 1, key="dash_mes_vis")
    janela_conv = st.slider("Janela de conversão (dias)", 90, 540, 365, 15, key="dash_conv_dias")
    dados = get_visitantes_conversao(meses_vis, janela_conv)
    
    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric("Visitantes no Ano", dados['total_visitantes_ano'])
    col2.metric("Convertidos", dados['convertidos'])
    col3.metric("Taxa de Conversão", f"{dados['taxa_conversao']:.1f}%")
    col4.metric("Meta", "30%")
    
    st.markdown("---")
    
    # Funil de conversão
    st.markdown("### 🎯 Funil de Relacionamento")
    
    igreja_id = get_igreja_id()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT status, COUNT(*) as total FROM pessoas
            WHERE igreja_id = ? AND ativo = 1
            GROUP BY status
        ''', (igreja_id,))
        funil_data = {row['status']: row['total'] for row in cursor.fetchall()}
    
    # Criar funil visual
    etapas = [
        ('visitante', 'Visitantes', funil_data.get('visitante', 0)),
        ('novo_convertido', 'Novos Convertidos', funil_data.get('novo_convertido', 0)),
        ('em_integracao', 'Em Integração', funil_data.get('em_integracao', 0)),
        ('membro', 'Membros', funil_data.get('membro', 0)),
        ('lider', 'Líderes', funil_data.get('lider', 0))
    ]
    
    fig = go.Figure(go.Funnel(
        y=[e[1] for e in etapas],
        x=[e[2] for e in etapas],
        textinfo="value+percent initial"
    ))
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    # Visitantes por mês
    st.markdown("### 📊 Visitantes por Mês")
    if dados['visitantes_mes']:
        df_vis = pd.DataFrame(dados['visitantes_mes'])
        df_vis['mes'] = pd.to_datetime(df_vis['mes'])
        df_vis = df_vis.sort_values('mes')
        fig = px.line(df_vis, x='mes', y='visitantes', markers=True,
                     labels={'mes': 'Mês', 'visitantes': 'Visitantes'})
        st.plotly_chart(fig, use_container_width=True)

def render_dashboard_celulas():
    """Renderiza dashboard de células"""
    st.subheader("🏠 Saúde das Células")
    
    celulas = get_saude_celulas()
    
    if not celulas:
        st.info("Nenhuma célula cadastrada.")
        return
    
    # Resumo
    saudaveis = len([c for c in celulas if c['status'] == 'saudavel'])
    atencao = len([c for c in celulas if c['status'] == 'atencao'])
    criticos = len([c for c in celulas if c['status'] == 'critico'])
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de Células", len(celulas))
    col2.metric("🟢 Saudáveis", saudaveis)
    col3.metric("🟡 Atenção", atencao)
    col4.metric("🔴 Críticas", criticos)
    
    st.markdown("---")
    
    # Detalhes por célula
    st.markdown("### 📋 Detalhamento")
    
    for celula in celulas:
        status_icon = {'saudavel': '🟢', 'atencao': '🟡', 'critico': '🔴'}.get(celula['status'], '⚪')
        
        with st.expander(f"{status_icon} {celula['nome']} - Score: {celula['score']}%"):
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Membros", celula['membros'] or 0)
            col2.metric("Média Presença", f"{celula['media_presenca'] or 0:.0f}")
            col3.metric("Reuniões/Mês", celula['reunioes_mes'] or 0)
            col4.write(f"**Líder:** {celula['lider_nome'] or 'N/A'}")

def render_dashboard_financeiro():
    """Renderiza dashboard financeiro"""
    st.subheader("💰 Indicadores Financeiros")
    
    meses_evol = st.slider("Meses na evolução", 3, 12, 6, 1, key="dash_mes_fin")
    dados = get_doacoes_periodo(meses_evol)
    
    if dados is None:
        st.warning("🔒 Você não tem permissão para visualizar dados financeiros.")
        return
    
    # Métricas
    col1, col2, col3 = st.columns(3)
    
    col1.metric(
        "Total do Mês",
        f"R$ {dados['total_mes']:,.2f}",
        f"{dados['variacao']:+.1f}% vs mês anterior"
    )
    
    col2.metric("Dízimos", f"R$ {dados['por_tipo'].get('Dízimo', 0):,.2f}")
    col3.metric("Ofertas", f"R$ {dados['por_tipo'].get('Oferta', 0):,.2f}")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📊 Por Tipo de Doação")
        if dados['por_tipo']:
            df_tipo = pd.DataFrame([
                {'Tipo': k, 'Valor': v}
                for k, v in dados['por_tipo'].items()
            ])
            fig = px.pie(df_tipo, values='Valor', names='Tipo', hole=0.3)
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### 📈 Evolução Mensal")
        if dados['evolucao']:
            df_evol = pd.DataFrame(dados['evolucao'])
            df_evol['mes'] = pd.to_datetime(df_evol['mes'])
            df_evol = df_evol.sort_values('mes')
            fig = px.area(df_evol, x='mes', y='total',
                         labels={'mes': 'Mês', 'total': 'Total (R$)'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

def render_dashboard_frequencia():
    """Renderiza dashboard de frequência"""
    st.subheader("📊 Frequência & Engajamento")
    
    dias_freq = st.slider("Dias considerados", 14, 120, 30, 7, key="dash_dias_freq")
    frequencia = get_frequencia_media(dias_freq)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Média de Presença (Cultos)", f"{frequencia['media_presenca']:.0f}")
    
    st.markdown("---")
    
    st.markdown("### 📋 Últimos Cultos")
    if frequencia['presenca_cultos']:
        df_freq = pd.DataFrame(frequencia['presenca_cultos'])
        df_freq['data_inicio'] = pd.to_datetime(df_freq['data_inicio'])
        df_freq = df_freq.sort_values('data_inicio')
        fig = px.bar(df_freq, x='data_inicio', y='presentes',
                    labels={'data_inicio': 'Data', 'presentes': 'Presentes'})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nenhum dado de presença registrado.")

def render_dashboard():
    """Função principal do módulo de dashboard"""
    st.title("📊 Dashboard")
    
    usuario = get_usuario_atual()
    
    # Tabs de dashboard
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Geral", "👋 Visitantes", "🏠 Células", "📈 Frequência", "💰 Financeiro"
    ])
    
    with tab1:
        render_dashboard_geral()
    
    with tab2:
        render_dashboard_visitantes()
    
    with tab3:
        render_dashboard_celulas()
    
    with tab4:
        render_dashboard_frequencia()
    
    with tab5:
        if tem_permissao(usuario, 'doacoes.ver'):
            render_dashboard_financeiro()
        else:
            st.info("🔒 Acesso restrito ao perfil Financeiro")
