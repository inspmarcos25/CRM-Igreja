"""
Módulo de Metas e OKRs
Definição e acompanhamento de metas da igreja
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
from database.db import get_connection
from modules.auth import get_igreja_id, get_usuario_atual, registrar_log
from config.settings import formatar_data_br

# ==================== FUNÇÕES DE DADOS ====================

def get_metas(status: str = None, categoria: str = None) -> list:
    """Busca metas da igreja"""
    igreja_id = get_igreja_id()
    
    query = '''
        SELECT m.*, p.nome as responsavel_nome,
               CASE 
                   WHEN m.valor_meta > 0 THEN ROUND((m.valor_atual / m.valor_meta) * 100, 1)
                   ELSE 0 
               END as percentual_atingido
        FROM metas m
        LEFT JOIN pessoas p ON m.responsavel_id = p.id
        WHERE m.igreja_id = ?
    '''
    params = [igreja_id]
    
    if status:
        query += ' AND m.status = ?'
        params.append(status)
    
    if categoria:
        query += ' AND m.categoria = ?'
        params.append(categoria)
    
    query += ' ORDER BY m.data_fim ASC'
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def get_meta(meta_id: int) -> dict:
    """Busca uma meta específica"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM metas WHERE id = ?', (meta_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def salvar_meta(dados: dict) -> int:
    """Salva ou atualiza uma meta"""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        if dados.get('id'):
            cursor.execute('''
                UPDATE metas
                SET titulo = ?, descricao = ?, categoria = ?, tipo_meta = ?,
                    valor_meta = ?, unidade = ?, data_inicio = ?, data_fim = ?,
                    responsavel_id = ?, status = ?
                WHERE id = ? AND igreja_id = ?
            ''', (dados['titulo'], dados.get('descricao'), dados.get('categoria'),
                  dados.get('tipo_meta', 'numero'), dados['valor_meta'],
                  dados.get('unidade'), dados['data_inicio'], dados['data_fim'],
                  dados.get('responsavel_id'), dados.get('status', 'em_andamento'),
                  dados['id'], igreja_id))
            return dados['id']
        else:
            cursor.execute('''
                INSERT INTO metas (igreja_id, titulo, descricao, categoria, tipo_meta,
                                  valor_inicial, valor_meta, valor_atual, unidade,
                                  data_inicio, data_fim, responsavel_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (igreja_id, dados['titulo'], dados.get('descricao'), dados.get('categoria'),
                  dados.get('tipo_meta', 'numero'), dados.get('valor_inicial', 0),
                  dados['valor_meta'], dados.get('valor_inicial', 0), dados.get('unidade'),
                  dados['data_inicio'], dados['data_fim'], dados.get('responsavel_id'),
                  dados.get('status', 'em_andamento')))
            
            registrar_log(usuario['id'], igreja_id, 'meta.criar', f"Meta criada: {dados['titulo']}")
            return cursor.lastrowid

def atualizar_valor_meta(meta_id: int, novo_valor: float, observacao: str = None):
    """Atualiza o valor atual de uma meta"""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Buscar valor anterior
        cursor.execute('SELECT valor_atual, valor_meta FROM metas WHERE id = ?', (meta_id,))
        meta = cursor.fetchone()
        valor_anterior = meta['valor_atual']
        
        # Atualizar valor
        cursor.execute('''
            UPDATE metas SET valor_atual = ? WHERE id = ?
        ''', (novo_valor, meta_id))
        
        # Registrar histórico
        cursor.execute('''
            INSERT INTO meta_atualizacoes (meta_id, valor_anterior, valor_novo, observacao, atualizado_por)
            VALUES (?, ?, ?, ?, ?)
        ''', (meta_id, valor_anterior, novo_valor, observacao, usuario['id']))
        
        # Verificar se atingiu a meta
        if novo_valor >= meta['valor_meta']:
            cursor.execute('UPDATE metas SET status = ? WHERE id = ?', ('atingida', meta_id))
        
        registrar_log(usuario['id'], igreja_id, 'meta.atualizar', f"Meta {meta_id} atualizada: {valor_anterior} -> {novo_valor}")

def get_historico_meta(meta_id: int) -> list:
    """Busca histórico de atualizações de uma meta"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT ma.*, u.nome as usuario_nome
            FROM meta_atualizacoes ma
            LEFT JOIN usuarios u ON ma.atualizado_por = u.id
            WHERE ma.meta_id = ?
            ORDER BY ma.data_atualizacao DESC
        ''', (meta_id,))
        return [dict(row) for row in cursor.fetchall()]

def excluir_meta(meta_id: int):
    """Exclui uma meta"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM meta_atualizacoes WHERE meta_id = ?', (meta_id,))
        cursor.execute('DELETE FROM metas WHERE id = ? AND igreja_id = ?', (meta_id, igreja_id))

def get_estatisticas_metas() -> dict:
    """Retorna estatísticas das metas"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Total por status
        cursor.execute('''
            SELECT status, COUNT(*) as total
            FROM metas WHERE igreja_id = ?
            GROUP BY status
        ''', (igreja_id,))
        por_status = {row['status']: row['total'] for row in cursor.fetchall()}
        
        # Metas que vencem este mês
        cursor.execute('''
            SELECT COUNT(*) FROM metas
            WHERE igreja_id = ? AND status = 'em_andamento'
            AND date(data_fim) BETWEEN date('now') AND date('now', '+30 days')
        ''', (igreja_id,))
        vence_mes = cursor.fetchone()[0]
        
        # Média de progresso
        cursor.execute('''
            SELECT AVG(
                CASE WHEN valor_meta > 0 THEN (valor_atual / valor_meta) * 100 ELSE 0 END
            ) as media_progresso
            FROM metas WHERE igreja_id = ? AND status = 'em_andamento'
        ''', (igreja_id,))
        media = cursor.fetchone()['media_progresso'] or 0
        
        return {
            'total': sum(por_status.values()),
            'em_andamento': por_status.get('em_andamento', 0),
            'atingidas': por_status.get('atingida', 0),
            'nao_atingidas': por_status.get('nao_atingida', 0),
            'vence_mes': vence_mes,
            'media_progresso': media
        }

# ==================== RENDERIZAÇÃO ====================

def render_metas():
    """Função principal do módulo de metas"""
    st.title("🎯 Metas e OKRs")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Dashboard",
        "📋 Todas as Metas",
        "➕ Nova Meta",
        "📈 Histórico"
    ])
    
    with tab1:
        render_dashboard_metas()
    
    with tab2:
        render_lista_metas()
    
    with tab3:
        render_nova_meta()
    
    with tab4:
        render_historico()

def render_dashboard_metas():
    """Renderiza dashboard de metas"""
    st.subheader("📊 Dashboard de Metas")
    
    stats = get_estatisticas_metas()
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📋 Total de Metas", stats['total'])
    col2.metric("⏳ Em Andamento", stats['em_andamento'])
    col3.metric("✅ Atingidas", stats['atingidas'])
    col4.metric("⚠️ Vencem em 30 dias", stats['vence_mes'])
    
    st.markdown("---")
    
    # Progresso médio
    col1, col2 = st.columns([1, 2])
    
    with col1:
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=stats['media_progresso'],
            title={'text': "Progresso Médio"},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': "#3498db"},
                'steps': [
                    {'range': [0, 50], 'color': "#ffebee"},
                    {'range': [50, 75], 'color': "#fff8e1"},
                    {'range': [75, 100], 'color': "#e8f5e9"}
                ]
            }
        ))
        fig_gauge.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig_gauge, use_container_width=True)
    
    with col2:
        # Metas em destaque (próximas a vencer)
        st.markdown("### ⏰ Metas com Prazo Próximo")
        
        metas = get_metas(status='em_andamento')
        metas_proximas = [m for m in metas if m['data_fim'] and 
                        datetime.strptime(str(m['data_fim'])[:10], '%Y-%m-%d').date() <= date.today() + timedelta(days=30)]
        
        if metas_proximas:
            for meta in metas_proximas[:5]:
                progresso = meta.get('percentual_atingido', 0)
                cor = "#e74c3c" if progresso < 50 else "#f39c12" if progresso < 80 else "#27ae60"
                
                st.markdown(f"""
                    <div style='background: #f8f9fa; padding: 0.5rem; border-radius: 5px; 
                                margin-bottom: 0.5rem; border-left: 4px solid {cor};'>
                        <strong>{meta['titulo']}</strong><br>
                        <small>📅 Prazo: {formatar_data_br(meta['data_fim'])} | 📊 {progresso}%</small>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Nenhuma meta com prazo próximo.")
    
    st.markdown("---")
    
    # Gráfico de progresso das metas
    st.markdown("### 📈 Progresso das Metas Ativas")
    
    metas_ativas = get_metas(status='em_andamento')
    
    if metas_ativas:
        df = pd.DataFrame([{
            'Meta': m['titulo'][:30] + '...' if len(m['titulo']) > 30 else m['titulo'],
            'Progresso': m.get('percentual_atingido', 0)
        } for m in metas_ativas])
        
        fig = px.bar(df, x='Progresso', y='Meta', orientation='h',
                    color='Progresso',
                    color_continuous_scale=['#e74c3c', '#f39c12', '#27ae60'])
        
        fig.update_layout(
            height=max(300, len(metas_ativas) * 40),
            margin=dict(l=20, r=20, t=20, b=20),
            showlegend=False
        )
        fig.add_vline(x=100, line_dash="dash", line_color="green")
        
        st.plotly_chart(fig, use_container_width=True)

def render_lista_metas():
    """Renderiza lista de metas"""
    st.subheader("📋 Todas as Metas")
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        status_filtro = st.selectbox(
            "Status",
            options=['Todas', 'em_andamento', 'atingida', 'nao_atingida', 'cancelada'],
            format_func=lambda x: {'Todas': 'Todas', 'em_andamento': '⏳ Em Andamento',
                                   'atingida': '✅ Atingidas', 'nao_atingida': '❌ Não Atingidas',
                                   'cancelada': '🚫 Canceladas'}[x]
        )
    with col2:
        categoria_filtro = st.selectbox(
            "Categoria",
            options=['Todas', 'crescimento', 'financeiro', 'discipulado', 'evangelismo', 'social']
        )
    
    metas = get_metas(
        status=status_filtro if status_filtro != 'Todas' else None,
        categoria=categoria_filtro if categoria_filtro != 'Todas' else None
    )
    
    if not metas:
        st.info("Nenhuma meta encontrada.")
        return
    
    for meta in metas:
        render_card_meta(meta)

def render_card_meta(meta: dict):
    """Renderiza card de uma meta"""
    progresso = meta.get('percentual_atingido', 0)
    
    status_icon = {
        'em_andamento': '⏳',
        'atingida': '✅',
        'nao_atingida': '❌',
        'cancelada': '🚫'
    }
    
    cor_progresso = "#e74c3c" if progresso < 50 else "#f39c12" if progresso < 80 else "#27ae60"
    
    with st.expander(f"{status_icon.get(meta['status'], '📋')} {meta['titulo']}", expanded=False):
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write(f"**Descrição:** {meta.get('descricao', 'Sem descrição')}")
            st.write(f"**Categoria:** {meta.get('categoria', 'Geral')}")
            st.write(f"**Responsável:** {meta.get('responsavel_nome', 'Não definido')}")
            st.write(f"**Período:** {formatar_data_br(meta['data_inicio'])} a {formatar_data_br(meta['data_fim'])}")
        
        with col2:
            st.metric("Valor Atual", f"{meta['valor_atual']:.1f} {meta.get('unidade', '')}")
            st.metric("Meta", f"{meta['valor_meta']:.1f} {meta.get('unidade', '')}")
        
        # Barra de progresso
        st.markdown(f"""
            <div style='background: #e0e0e0; border-radius: 10px; height: 20px; margin: 1rem 0;'>
                <div style='background: {cor_progresso}; width: {min(progresso, 100)}%; 
                            height: 100%; border-radius: 10px; text-align: center; color: white;
                            font-size: 0.8rem; line-height: 20px;'>
                    {progresso:.1f}%
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Ações
        if meta['status'] == 'em_andamento':
            st.markdown("**📝 Atualizar Progresso:**")
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                novo_valor = st.number_input(
                    "Novo valor",
                    min_value=0.0,
                    value=float(meta['valor_atual']),
                    key=f"valor_{meta['id']}"
                )
            
            with col2:
                obs = st.text_input("Observação", key=f"obs_{meta['id']}")
            
            with col3:
                st.write("")
                st.write("")
                if st.button("💾", key=f"save_{meta['id']}"):
                    atualizar_valor_meta(meta['id'], novo_valor, obs)
                    st.success("Atualizado!")
                    st.rerun()
        
        # Botão excluir
        if st.button("🗑️ Excluir Meta", key=f"del_{meta['id']}"):
            excluir_meta(meta['id'])
            st.rerun()

def render_nova_meta():
    """Renderiza formulário de nova meta"""
    st.subheader("➕ Criar Nova Meta")
    
    with st.form("nova_meta"):
        titulo = st.text_input("Título da Meta *", placeholder="Ex: Aumentar membros ativos")
        descricao = st.text_area("Descrição", placeholder="Descreva a meta em detalhes...")
        
        col1, col2 = st.columns(2)
        with col1:
            categoria = st.selectbox(
                "Categoria",
                options=['crescimento', 'financeiro', 'discipulado', 'evangelismo', 'social'],
                format_func=lambda x: {
                    'crescimento': '📈 Crescimento',
                    'financeiro': '💰 Financeiro',
                    'discipulado': '📚 Discipulado',
                    'evangelismo': '🙏 Evangelismo',
                    'social': '❤️ Ação Social'
                }[x]
            )
        
        with col2:
            tipo_meta = st.selectbox(
                "Tipo de Medição",
                options=['numero', 'percentual', 'moeda'],
                format_func=lambda x: {'numero': '🔢 Número', 'percentual': '📊 Percentual',
                                       'moeda': '💵 Valor em R$'}[x]
            )
        
        col3, col4 = st.columns(2)
        with col3:
            valor_inicial = st.number_input("Valor Inicial", min_value=0.0, value=0.0)
        with col4:
            valor_meta = st.number_input("Valor Meta *", min_value=0.1, value=100.0)
        
        unidade = st.text_input("Unidade (opcional)", placeholder="Ex: pessoas, %, R$")
        
        col5, col6 = st.columns(2)
        with col5:
            data_inicio = st.date_input("Data Início *", format="DD/MM/YYYY")
        with col6:
            data_fim = st.date_input("Data Fim *", format="DD/MM/YYYY",
                                    value=date.today() + timedelta(days=90))
        
        from modules.pessoas import get_pessoas
        pessoas = get_pessoas()
        responsavel = st.selectbox(
            "Responsável",
            options=[None] + pessoas,
            format_func=lambda x: x['nome'] if x else 'Não definido'
        )
        
        submit = st.form_submit_button("💾 Criar Meta", use_container_width=True)
        
        if submit:
            if not titulo:
                st.error("Título é obrigatório!")
            elif valor_meta <= 0:
                st.error("Valor meta deve ser maior que zero!")
            else:
                salvar_meta({
                    'titulo': titulo,
                    'descricao': descricao,
                    'categoria': categoria,
                    'tipo_meta': tipo_meta,
                    'valor_inicial': valor_inicial,
                    'valor_meta': valor_meta,
                    'unidade': unidade,
                    'data_inicio': data_inicio,
                    'data_fim': data_fim,
                    'responsavel_id': responsavel['id'] if responsavel else None
                })
                st.success("✅ Meta criada com sucesso!")
                st.rerun()

def render_historico():
    """Renderiza histórico de atualizações"""
    st.subheader("📈 Histórico de Progresso")
    
    metas = get_metas()
    
    if not metas:
        st.info("Nenhuma meta cadastrada.")
        return
    
    meta_selecionada = st.selectbox(
        "Selecione a Meta",
        options=metas,
        format_func=lambda x: x['titulo']
    )
    
    if meta_selecionada:
        historico = get_historico_meta(meta_selecionada['id'])
        
        if not historico:
            st.info("Nenhuma atualização registrada para esta meta.")
            return
        
        # Gráfico de evolução
        df = pd.DataFrame([{
            'Data': h['data_atualizacao'],
            'Valor': h['valor_novo']
        } for h in reversed(historico)])
        
        fig = px.line(df, x='Data', y='Valor', markers=True)
        fig.add_hline(y=meta_selecionada['valor_meta'], line_dash="dash", 
                     line_color="green", annotation_text="Meta")
        fig.update_layout(height=300)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Lista de atualizações
        st.markdown("### 📋 Atualizações")
        for h in historico:
            st.markdown(f"""
                <div style='background: #f8f9fa; padding: 0.5rem; border-radius: 5px; margin-bottom: 0.5rem;'>
                    <strong>{formatar_data_br(str(h['data_atualizacao'])[:10])}</strong>
                    | {h['valor_anterior']} → {h['valor_novo']}
                    <br><small>👤 {h.get('usuario_nome', 'Sistema')} | {h.get('observacao', '')}</small>
                </div>
            """, unsafe_allow_html=True)
