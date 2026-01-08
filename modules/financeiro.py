"""
Módulo de Doações & Financeiro
Registro de dízimos, ofertas e relatórios financeiros
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from io import BytesIO
from database.db import get_connection
from modules.auth import get_igreja_id, get_usuario_atual, registrar_log, tem_permissao
from config.settings import TIPOS_DOACAO, formatar_data_br

def get_doacoes(filtros: dict = None) -> list:
    """Busca doações com filtros"""
    igreja_id = get_igreja_id()
    
    query = '''
        SELECT d.*, p.nome as pessoa_nome
        FROM doacoes d
        LEFT JOIN pessoas p ON d.pessoa_id = p.id
        WHERE d.igreja_id = ?
    '''
    params = [igreja_id]
    
    if filtros:
        if filtros.get('data_inicio'):
            query += ' AND d.data >= ?'
            params.append(filtros['data_inicio'])
        if filtros.get('data_fim'):
            query += ' AND d.data <= ?'
            params.append(filtros['data_fim'])
        if filtros.get('tipo'):
            query += ' AND d.tipo = ?'
            params.append(filtros['tipo'])
        if filtros.get('pessoa_id'):
            query += ' AND d.pessoa_id = ?'
            params.append(filtros['pessoa_id'])
    
    query += ' ORDER BY d.data DESC'
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def registrar_doacao(dados: dict) -> int:
    """Registra uma nova doação"""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO doacoes (igreja_id, pessoa_id, tipo, valor, data, forma_pagamento,
                                referencia, observacoes, anonimo, registrado_por)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (igreja_id, dados.get('pessoa_id'), dados['tipo'], dados['valor'],
              dados['data'], dados.get('forma_pagamento'), dados.get('referencia'),
              dados.get('observacoes'), dados.get('anonimo', 0), usuario['id']))
        
        registrar_log(usuario['id'], igreja_id, 'doacao.registrar', 
                     f"Doação registrada: R$ {dados['valor']:.2f} - {dados['tipo']}")
        return cursor.lastrowid

def get_resumo_financeiro(periodo: str = 'mes') -> dict:
    """Gera resumo financeiro do período"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Definir período
        if periodo == 'mes':
            data_inicio = date.today().replace(day=1)
        elif periodo == 'ano':
            data_inicio = date.today().replace(month=1, day=1)
        elif periodo == 'semana':
            data_inicio = date.today() - timedelta(days=date.today().weekday())
        else:
            data_inicio = date.today() - timedelta(days=30)
        
        # Total por tipo
        cursor.execute('''
            SELECT tipo, SUM(valor) as total, COUNT(*) as quantidade
            FROM doacoes
            WHERE igreja_id = ? AND data >= ?
            GROUP BY tipo
        ''', (igreja_id, data_inicio))
        por_tipo = {row['tipo']: {'total': row['total'], 'qtd': row['quantidade']} 
                   for row in cursor.fetchall()}
        
        # Total geral
        cursor.execute('''
            SELECT SUM(valor) as total, COUNT(*) as quantidade
            FROM doacoes
            WHERE igreja_id = ? AND data >= ?
        ''', (igreja_id, data_inicio))
        row = cursor.fetchone()
        total_geral = row['total'] or 0
        qtd_geral = row['quantidade'] or 0
        
        # Comparação com período anterior
        dias_periodo = (date.today() - data_inicio).days + 1
        data_anterior = data_inicio - timedelta(days=dias_periodo)
        
        cursor.execute('''
            SELECT SUM(valor) as total
            FROM doacoes
            WHERE igreja_id = ? AND data >= ? AND data < ?
        ''', (igreja_id, data_anterior, data_inicio))
        total_anterior = cursor.fetchone()['total'] or 0
        
        variacao = ((total_geral - total_anterior) / total_anterior * 100) if total_anterior > 0 else 0
        
        # Maiores contribuintes (anonimizado para LGPD)
        cursor.execute('''
            SELECT p.id, SUBSTR(p.nome, 1, INSTR(p.nome, ' ')) || '***' as nome_parcial,
                   SUM(d.valor) as total
            FROM doacoes d
            JOIN pessoas p ON d.pessoa_id = p.id
            WHERE d.igreja_id = ? AND d.data >= ? AND d.anonimo = 0
            GROUP BY p.id
            ORDER BY total DESC
            LIMIT 5
        ''', (igreja_id, data_inicio))
        top_contribuintes = [dict(row) for row in cursor.fetchall()]
        
        return {
            'total_geral': total_geral,
            'quantidade': qtd_geral,
            'por_tipo': por_tipo,
            'variacao': variacao,
            'top_contribuintes': top_contribuintes,
            'data_inicio': data_inicio
        }

def get_historico_pessoa(pessoa_id: int) -> list:
    """Busca histórico de doações de uma pessoa (acesso restrito)"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT d.*, 
                   SUM(d.valor) OVER () as total_geral,
                   SUM(CASE WHEN d.tipo = 'Dízimo' THEN d.valor ELSE 0 END) OVER () as total_dizimo
            FROM doacoes d
            WHERE d.igreja_id = ? AND d.pessoa_id = ?
            ORDER BY d.data DESC
        ''', (igreja_id, pessoa_id))
        return [dict(row) for row in cursor.fetchall()]

def exportar_relatorio_excel(dados: list, titulo: str) -> BytesIO:
    """Exporta relatório para Excel"""
    df = pd.DataFrame(dados)
    
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=titulo[:31], index=False)
    buffer.seek(0)
    
    return buffer

# ========================================
# RENDERIZAÇÃO DA INTERFACE
# ========================================

def render_registrar_doacao():
    """Renderiza formulário de registro de doação"""
    st.subheader("➕ Registrar Doação")
    
    igreja_id = get_igreja_id()
    
    # Buscar pessoas para seleção
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, nome FROM pessoas
            WHERE igreja_id = ? AND ativo = 1
            ORDER BY nome
        ''', (igreja_id,))
        pessoas = [dict(row) for row in cursor.fetchall()]
    
    pessoas_opcoes = [(0, "Anônimo/Não identificado")] + [(p['id'], p['nome']) for p in pessoas]
    
    with st.form("form_doacao"):
        col1, col2 = st.columns(2)
        
        with col1:
            tipo = st.selectbox("Tipo *", options=TIPOS_DOACAO)
            valor = st.number_input("Valor (R$) *", min_value=0.01, value=100.0, step=10.0)
            data = st.date_input("Data *", value=date.today(), format="DD/MM/YYYY")
        
        with col2:
            pessoa_id = st.selectbox("Contribuinte",
                                    options=[p[0] for p in pessoas_opcoes],
                                    format_func=lambda x: dict(pessoas_opcoes).get(x, ''))
            forma_pagamento = st.selectbox("Forma de pagamento",
                                          options=['Dinheiro', 'PIX', 'Cartão Débito', 
                                                  'Cartão Crédito', 'Transferência', 'Cheque'])
            referencia = st.text_input("Referência/Comprovante")
        
        observacoes = st.text_area("Observações", height=60)
        anonimo = st.checkbox("Registrar como doação anônima")
        
        if st.form_submit_button("💾 Registrar Doação", use_container_width=True):
            if valor <= 0:
                st.error("O valor deve ser maior que zero!")
            else:
                registrar_doacao({
                    'tipo': tipo,
                    'valor': valor,
                    'data': data,
                    'pessoa_id': pessoa_id if pessoa_id and not anonimo else None,
                    'forma_pagamento': forma_pagamento,
                    'referencia': referencia,
                    'observacoes': observacoes,
                    'anonimo': 1 if anonimo or not pessoa_id else 0
                })
                st.success(f"✅ Doação de R$ {valor:.2f} registrada com sucesso!")
                st.balloons()
                st.rerun()

def render_lista_doacoes():
    """Renderiza lista de doações"""
    st.subheader("📋 Doações Registradas")
    
    # Filtros
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        data_inicio = st.date_input("De", value=date.today().replace(day=1), format="DD/MM/YYYY")
    with col2:
        data_fim = st.date_input("Até", value=date.today(), format="DD/MM/YYYY")
    with col3:
        tipo = st.selectbox("Tipo", options=['Todos'] + TIPOS_DOACAO)
    with col4:
        st.markdown("<br>", unsafe_allow_html=True)
        exportar = st.button("📥 Exportar Excel")
    
    # Buscar doações
    filtros = {
        'data_inicio': data_inicio,
        'data_fim': data_fim
    }
    if tipo != 'Todos':
        filtros['tipo'] = tipo
    
    doacoes = get_doacoes(filtros)
    
    if not doacoes:
        st.info("Nenhuma doação encontrada no período.")
        return
    
    # Totais
    total = sum([d['valor'] for d in doacoes])
    st.metric("Total no Período", f"R$ {total:,.2f}")
    
    # Exportar
    if exportar:
        df_export = [{
            'Data': d['data'],
            'Tipo': d['tipo'],
            'Valor': d['valor'],
            'Contribuinte': d.get('pessoa_nome', 'Anônimo'),
            'Forma Pagamento': d.get('forma_pagamento', ''),
            'Referência': d.get('referencia', '')
        } for d in doacoes]
        
        excel_file = exportar_relatorio_excel(df_export, 'Doações')
        st.download_button(
            label="📥 Baixar Excel",
            data=excel_file,
            file_name=f"doacoes_{data_inicio}_{data_fim}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    st.markdown("---")
    
    # Lista
    for doacao in doacoes:
        tipo_icon = {
            'Dízimo': '💰',
            'Oferta': '🎁',
            'Missões': '✈️',
            'Construção': '🏗️',
            'Ação Social': '❤️'
        }.get(doacao['tipo'], '💵')
        
        with st.container():
            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
            
            with col1:
                st.markdown(f"**{tipo_icon} {doacao['tipo']}**")
                st.caption(f"📅 {formatar_data_br(doacao['data'])}")
            
            with col2:
                nome = doacao.get('pessoa_nome', 'Anônimo')
                if doacao.get('anonimo'):
                    nome = '🔒 Anônimo'
                st.write(f"👤 {nome}")
            
            with col3:
                st.markdown(f"### R$ {doacao['valor']:,.2f}")
            
            with col4:
                if doacao.get('forma_pagamento'):
                    st.caption(doacao['forma_pagamento'])
        
        st.markdown("<hr style='margin: 0.5rem 0; opacity: 0.2;'>", unsafe_allow_html=True)

def render_dashboard_financeiro():
    """Renderiza dashboard financeiro"""
    st.subheader("📊 Dashboard Financeiro")
    
    col1, col2 = st.columns([3, 1])
    with col2:
        periodo = st.selectbox("Período", 
                              options=['mes', 'semana', 'ano'],
                              format_func=lambda x: {'mes': 'Este mês', 'semana': 'Esta semana', 
                                                    'ano': 'Este ano'}.get(x, x))
    
    resumo = get_resumo_financeiro(periodo)
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric(
        "Total Arrecadado",
        f"R$ {resumo['total_geral']:,.2f}",
        f"{resumo['variacao']:+.1f}% vs período anterior"
    )
    
    dizimo = resumo['por_tipo'].get('Dízimo', {}).get('total', 0)
    col2.metric("Dízimos", f"R$ {dizimo:,.2f}")
    
    oferta = resumo['por_tipo'].get('Oferta', {}).get('total', 0)
    col3.metric("Ofertas", f"R$ {oferta:,.2f}")
    
    col4.metric("Nº de Doações", resumo['quantidade'])
    
    st.markdown("---")
    
    # Gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📊 Por Tipo de Doação")
        if resumo['por_tipo']:
            df_tipo = pd.DataFrame([
                {'Tipo': tipo, 'Valor': dados['total']}
                for tipo, dados in resumo['por_tipo'].items()
            ])
            st.bar_chart(df_tipo.set_index('Tipo'))
        else:
            st.info("Sem dados no período")
    
    with col2:
        st.markdown("### 🏆 Maiores Contribuintes")
        if resumo['top_contribuintes']:
            for i, c in enumerate(resumo['top_contribuintes'], 1):
                st.write(f"{i}. {c['nome_parcial']} - R$ {c['total']:,.2f}")
        else:
            st.info("Sem dados no período")
    
    # Evolução mensal
    st.markdown("### 📈 Evolução Mensal")
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT strftime('%Y-%m', data) as mes, SUM(valor) as total
            FROM doacoes
            WHERE igreja_id = ? AND data >= date('now', '-12 months')
            GROUP BY mes
            ORDER BY mes
        ''', (igreja_id,))
        evolucao = [dict(row) for row in cursor.fetchall()]
    
    if evolucao:
        df_evolucao = pd.DataFrame(evolucao)
        st.line_chart(df_evolucao.set_index('mes'))

def render_relatorios():
    """Renderiza relatórios financeiros"""
    st.subheader("📑 Relatórios")
    
    tipo_relatorio = st.selectbox(
        "Tipo de Relatório",
        options=['mensal', 'anual', 'por_pessoa'],
        format_func=lambda x: {
            'mensal': 'Relatório Mensal',
            'anual': 'Relatório Anual',
            'por_pessoa': 'Por Contribuinte'
        }.get(x, x)
    )
    
    if tipo_relatorio == 'mensal':
        col1, col2 = st.columns(2)
        with col1:
            mes = st.selectbox("Mês", options=range(1, 13), 
                              format_func=lambda x: ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril',
                                                    'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro',
                                                    'Outubro', 'Novembro', 'Dezembro'][x],
                              index=date.today().month - 1)
        with col2:
            ano = st.selectbox("Ano", options=range(2020, 2030), index=date.today().year - 2020)
        
        data_inicio = date(ano, mes, 1)
        if mes == 12:
            data_fim = date(ano + 1, 1, 1) - timedelta(days=1)
        else:
            data_fim = date(ano, mes + 1, 1) - timedelta(days=1)
        
        doacoes = get_doacoes({'data_inicio': data_inicio, 'data_fim': data_fim})
        
        if doacoes:
            st.markdown(f"### Relatório de {['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'][mes]}/{ano}")
            
            # Resumo por tipo
            df = pd.DataFrame(doacoes)
            resumo = df.groupby('tipo').agg({'valor': ['sum', 'count']}).reset_index()
            resumo.columns = ['Tipo', 'Total', 'Quantidade']
            st.table(resumo)
            
            total = df['valor'].sum()
            st.metric("**Total Geral**", f"R$ {total:,.2f}")
            
            # Exportar
            excel_file = exportar_relatorio_excel(doacoes, f'Doacoes_{mes}_{ano}')
            st.download_button(
                label="📥 Exportar Excel",
                data=excel_file,
                file_name=f"relatorio_{mes}_{ano}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("Nenhuma doação no período selecionado.")
    
    elif tipo_relatorio == 'anual':
        ano = st.selectbox("Ano", options=range(2020, 2030), index=date.today().year - 2020)
        
        data_inicio = date(ano, 1, 1)
        data_fim = date(ano, 12, 31)
        
        doacoes = get_doacoes({'data_inicio': data_inicio, 'data_fim': data_fim})
        
        if doacoes:
            st.markdown(f"### Relatório Anual {ano}")
            
            df = pd.DataFrame(doacoes)
            df['mes'] = pd.to_datetime(df['data']).dt.month
            
            # Por mês
            por_mes = df.groupby('mes')['valor'].sum().reset_index()
            por_mes['mes'] = por_mes['mes'].apply(lambda x: ['', 'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 
                                                            'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'][x])
            st.bar_chart(por_mes.set_index('mes'))
            
            total = df['valor'].sum()
            st.metric("**Total Anual**", f"R$ {total:,.2f}")

def render_financeiro():
    """Função principal do módulo financeiro"""
    usuario = get_usuario_atual()
    
    # Verificar permissão
    if not tem_permissao(usuario, 'doacoes.ver'):
        st.error("🚫 Você não tem permissão para acessar este módulo.")
        return
    
    tab1, tab2, tab3, tab4 = st.tabs(["➕ Registrar", "📋 Doações", "📊 Dashboard", "📑 Relatórios"])
    
    with tab1:
        if tem_permissao(usuario, 'doacoes.editar'):
            render_registrar_doacao()
        else:
            st.warning("Você não tem permissão para registrar doações.")
    
    with tab2:
        render_lista_doacoes()
    
    with tab3:
        render_dashboard_financeiro()
    
    with tab4:
        render_relatorios()
