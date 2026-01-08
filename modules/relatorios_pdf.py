"""
Módulo de Relatórios PDF
Geração de relatórios profissionais em PDF
"""
import streamlit as st
import io
from datetime import datetime, date, timedelta
from database.db import get_connection
from modules.auth import get_igreja_id, get_usuario_atual
from config.settings import formatar_data_br

# Importação do ReportLab
try:
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_DISPONIVEL = True
except ImportError:
    REPORTLAB_DISPONIVEL = False

# ==================== FUNÇÕES DE DADOS ====================

def get_dados_membros(filtros: dict = None) -> list:
    """Busca dados de membros para relatório"""
    igreja_id = get_igreja_id()
    
    query = '''
        SELECT p.*, 
               GROUP_CONCAT(DISTINCT m.nome) as ministerios_nomes
        FROM pessoas p
        LEFT JOIN pessoa_ministerios pm ON p.id = pm.pessoa_id AND pm.ativo = 1
        LEFT JOIN ministerios m ON pm.ministerio_id = m.id
        WHERE p.igreja_id = ?
    '''
    params = [igreja_id]
    
    if filtros:
        if filtros.get('status'):
            query += ' AND p.status = ?'
            params.append(filtros['status'])
        
        if filtros.get('ministerio_id'):
            query += ' AND pm.ministerio_id = ?'
            params.append(filtros['ministerio_id'])
    
    query += ' GROUP BY p.id ORDER BY p.nome'
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def get_dados_financeiros(periodo_inicio: date, periodo_fim: date) -> dict:
    """Busca dados financeiros para relatório"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Entradas por categoria
        cursor.execute('''
            SELECT categoria, SUM(valor) as total
            FROM transacoes
            WHERE igreja_id = ? AND tipo = 'entrada'
            AND date(data) BETWEEN ? AND ?
            GROUP BY categoria
        ''', (igreja_id, periodo_inicio, periodo_fim))
        entradas = {row['categoria']: row['total'] for row in cursor.fetchall()}
        
        # Saídas por categoria
        cursor.execute('''
            SELECT categoria, SUM(valor) as total
            FROM transacoes
            WHERE igreja_id = ? AND tipo = 'saida'
            AND date(data) BETWEEN ? AND ?
            GROUP BY categoria
        ''', (igreja_id, periodo_inicio, periodo_fim))
        saidas = {row['categoria']: row['total'] for row in cursor.fetchall()}
        
        # Totais
        total_entradas = sum(entradas.values())
        total_saidas = sum(saidas.values())
        
        return {
            'entradas': entradas,
            'saidas': saidas,
            'total_entradas': total_entradas,
            'total_saidas': total_saidas,
            'saldo': total_entradas - total_saidas,
            'periodo_inicio': periodo_inicio,
            'periodo_fim': periodo_fim
        }

def get_dados_eventos(periodo_inicio: date, periodo_fim: date) -> list:
    """Busca dados de eventos para relatório"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT e.*, 
                   (SELECT COUNT(*) FROM presencas WHERE evento_id = e.id) as total_presencas
            FROM eventos e
            WHERE e.igreja_id = ?
            AND date(e.data) BETWEEN ? AND ?
            ORDER BY e.data
        ''', (igreja_id, periodo_inicio, periodo_fim))
        return [dict(row) for row in cursor.fetchall()]

def get_dados_visitantes(periodo_inicio: date, periodo_fim: date) -> list:
    """Busca dados de visitantes para relatório"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM visitantes
            WHERE igreja_id = ?
            AND date(data_visita) BETWEEN ? AND ?
            ORDER BY data_visita DESC
        ''', (igreja_id, periodo_inicio, periodo_fim))
        return [dict(row) for row in cursor.fetchall()]

def get_info_igreja() -> dict:
    """Busca informações da igreja"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM igrejas WHERE id = ?', (igreja_id,))
        row = cursor.fetchone()
        return dict(row) if row else {}

# ==================== GERAÇÃO DE PDF ====================

def criar_estilos():
    """Cria estilos personalizados para o PDF"""
    styles = getSampleStyleSheet()
    
    styles.add(ParagraphStyle(
        name='TituloRelatorio',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#2c3e50')
    ))
    
    styles.add(ParagraphStyle(
        name='Subtitulo',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=20,
        spaceAfter=10,
        textColor=colors.HexColor('#34495e')
    ))
    
    styles.add(ParagraphStyle(
        name='Cabecalho',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#7f8c8d')
    ))
    
    return styles

def gerar_pdf_membros(filtros: dict = None) -> bytes:
    """Gera PDF de relatório de membros"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    styles = criar_estilos()
    elementos = []
    
    # Cabeçalho
    igreja = get_info_igreja()
    elementos.append(Paragraph(igreja.get('nome', 'Igreja'), styles['TituloRelatorio']))
    elementos.append(Paragraph(f"Relatório de Membros - {datetime.now().strftime('%d/%m/%Y')}", styles['Cabecalho']))
    elementos.append(Spacer(1, 20))
    
    # Dados
    membros = get_dados_membros(filtros)
    
    # Resumo
    elementos.append(Paragraph("Resumo", styles['Subtitulo']))
    
    por_status = {}
    for m in membros:
        status = m.get('status', 'ativo')
        por_status[status] = por_status.get(status, 0) + 1
    
    resumo_data = [
        ['Total de Membros', str(len(membros))],
        ['Ativos', str(por_status.get('ativo', 0))],
        ['Inativos', str(por_status.get('inativo', 0))],
        ['Visitantes', str(por_status.get('visitante', 0))]
    ]
    
    tabela_resumo = Table(resumo_data, colWidths=[10*cm, 5*cm])
    tabela_resumo.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#ecf0f1')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.white)
    ]))
    elementos.append(tabela_resumo)
    elementos.append(Spacer(1, 20))
    
    # Lista de membros
    elementos.append(Paragraph("Lista de Membros", styles['Subtitulo']))
    
    dados_tabela = [['Nome', 'Telefone', 'Email', 'Ministérios', 'Status']]
    
    for m in membros[:100]:  # Limitar para não ficar muito grande
        dados_tabela.append([
            m.get('nome', '')[:30],
            m.get('telefone', '') or m.get('celular', '') or '',
            m.get('email', '')[:25] if m.get('email') else '',
            (m.get('ministerios_nomes', '') or '')[:20],
            m.get('status', '')
        ])
    
    tabela_membros = Table(dados_tabela, colWidths=[5*cm, 3*cm, 4*cm, 3*cm, 1.5*cm])
    tabela_membros.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
    ]))
    elementos.append(tabela_membros)
    
    # Rodapé
    elementos.append(Spacer(1, 30))
    elementos.append(Paragraph(
        f"Documento gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} | CRM Igreja",
        styles['Cabecalho']
    ))
    
    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()

def gerar_pdf_financeiro(periodo_inicio: date, periodo_fim: date) -> bytes:
    """Gera PDF de relatório financeiro"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    styles = criar_estilos()
    elementos = []
    
    # Cabeçalho
    igreja = get_info_igreja()
    elementos.append(Paragraph(igreja.get('nome', 'Igreja'), styles['TituloRelatorio']))
    elementos.append(Paragraph(
        f"Relatório Financeiro - {formatar_data_br(str(periodo_inicio))} a {formatar_data_br(str(periodo_fim))}",
        styles['Cabecalho']
    ))
    elementos.append(Spacer(1, 20))
    
    # Dados
    dados = get_dados_financeiros(periodo_inicio, periodo_fim)
    
    # Resumo geral
    elementos.append(Paragraph("Resumo Financeiro", styles['Subtitulo']))
    
    resumo_data = [
        ['Total de Entradas', f"R$ {dados['total_entradas']:,.2f}"],
        ['Total de Saídas', f"R$ {dados['total_saidas']:,.2f}"],
        ['Saldo do Período', f"R$ {dados['saldo']:,.2f}"]
    ]
    
    cor_saldo = colors.green if dados['saldo'] >= 0 else colors.red
    
    tabela_resumo = Table(resumo_data, colWidths=[10*cm, 6*cm])
    tabela_resumo.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 1), colors.HexColor('#e8f5e9')),
        ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#e3f2fd') if dados['saldo'] >= 0 else colors.HexColor('#ffebee')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.white)
    ]))
    elementos.append(tabela_resumo)
    elementos.append(Spacer(1, 20))
    
    # Entradas por categoria
    if dados['entradas']:
        elementos.append(Paragraph("Entradas por Categoria", styles['Subtitulo']))
        
        entradas_data = [['Categoria', 'Valor']]
        for cat, valor in sorted(dados['entradas'].items(), key=lambda x: -x[1]):
            entradas_data.append([cat.replace('_', ' ').title(), f"R$ {valor:,.2f}"])
        
        tabela_entradas = Table(entradas_data, colWidths=[10*cm, 6*cm])
        tabela_entradas.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7'))
        ]))
        elementos.append(tabela_entradas)
        elementos.append(Spacer(1, 15))
    
    # Saídas por categoria
    if dados['saidas']:
        elementos.append(Paragraph("Saídas por Categoria", styles['Subtitulo']))
        
        saidas_data = [['Categoria', 'Valor']]
        for cat, valor in sorted(dados['saidas'].items(), key=lambda x: -x[1]):
            saidas_data.append([cat.replace('_', ' ').title(), f"R$ {valor:,.2f}"])
        
        tabela_saidas = Table(saidas_data, colWidths=[10*cm, 6*cm])
        tabela_saidas.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74c3c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7'))
        ]))
        elementos.append(tabela_saidas)
    
    # Rodapé
    elementos.append(Spacer(1, 30))
    elementos.append(Paragraph(
        f"Documento gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} | CRM Igreja",
        styles['Cabecalho']
    ))
    
    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()

def gerar_pdf_eventos(periodo_inicio: date, periodo_fim: date) -> bytes:
    """Gera PDF de relatório de eventos"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    styles = criar_estilos()
    elementos = []
    
    # Cabeçalho
    igreja = get_info_igreja()
    elementos.append(Paragraph(igreja.get('nome', 'Igreja'), styles['TituloRelatorio']))
    elementos.append(Paragraph(
        f"Relatório de Eventos - {formatar_data_br(str(periodo_inicio))} a {formatar_data_br(str(periodo_fim))}",
        styles['Cabecalho']
    ))
    elementos.append(Spacer(1, 20))
    
    # Dados
    eventos = get_dados_eventos(periodo_inicio, periodo_fim)
    
    # Resumo
    elementos.append(Paragraph("Resumo", styles['Subtitulo']))
    
    total_presencas = sum(e.get('total_presencas', 0) for e in eventos)
    media_presencas = total_presencas / len(eventos) if eventos else 0
    
    resumo_data = [
        ['Total de Eventos', str(len(eventos))],
        ['Total de Presenças', str(total_presencas)],
        ['Média de Presenças', f"{media_presencas:.1f}"]
    ]
    
    tabela_resumo = Table(resumo_data, colWidths=[10*cm, 6*cm])
    tabela_resumo.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e3f2fd')),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.white)
    ]))
    elementos.append(tabela_resumo)
    elementos.append(Spacer(1, 20))
    
    # Lista de eventos
    elementos.append(Paragraph("Lista de Eventos", styles['Subtitulo']))
    
    dados_tabela = [['Data', 'Evento', 'Tipo', 'Presenças']]
    
    for e in eventos:
        dados_tabela.append([
            formatar_data_br(e['data']),
            e.get('nome', '')[:40],
            e.get('tipo', ''),
            str(e.get('total_presencas', 0))
        ])
    
    tabela_eventos = Table(dados_tabela, colWidths=[3*cm, 8*cm, 3*cm, 2*cm])
    tabela_eventos.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#9b59b6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
    ]))
    elementos.append(tabela_eventos)
    
    # Rodapé
    elementos.append(Spacer(1, 30))
    elementos.append(Paragraph(
        f"Documento gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} | CRM Igreja",
        styles['Cabecalho']
    ))
    
    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()

def gerar_pdf_visitantes(periodo_inicio: date, periodo_fim: date) -> bytes:
    """Gera PDF de relatório de visitantes"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    styles = criar_estilos()
    elementos = []
    
    # Cabeçalho
    igreja = get_info_igreja()
    elementos.append(Paragraph(igreja.get('nome', 'Igreja'), styles['TituloRelatorio']))
    elementos.append(Paragraph(
        f"Relatório de Visitantes - {formatar_data_br(str(periodo_inicio))} a {formatar_data_br(str(periodo_fim))}",
        styles['Cabecalho']
    ))
    elementos.append(Spacer(1, 20))
    
    # Dados
    visitantes = get_dados_visitantes(periodo_inicio, periodo_fim)
    
    # Por status
    por_status = {}
    for v in visitantes:
        status = v.get('status', 'primeiro_contato')
        por_status[status] = por_status.get(status, 0) + 1
    
    # Resumo
    elementos.append(Paragraph("Resumo", styles['Subtitulo']))
    
    status_labels = {
        'primeiro_contato': 'Primeiro Contato',
        'retornou': 'Retornou',
        'convertido': 'Convertido',
        'membro': 'Virou Membro',
        'desistente': 'Desistente'
    }
    
    resumo_data = [['Total de Visitantes', str(len(visitantes))]]
    for status, qtd in por_status.items():
        resumo_data.append([status_labels.get(status, status), str(qtd)])
    
    tabela_resumo = Table(resumo_data, colWidths=[10*cm, 6*cm])
    tabela_resumo.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f39c12')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fef9e7')),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.white)
    ]))
    elementos.append(tabela_resumo)
    elementos.append(Spacer(1, 20))
    
    # Lista
    elementos.append(Paragraph("Lista de Visitantes", styles['Subtitulo']))
    
    dados_tabela = [['Data', 'Nome', 'Telefone', 'Status']]
    
    for v in visitantes[:50]:
        dados_tabela.append([
            formatar_data_br(v['data_visita']),
            v.get('nome', '')[:30],
            v.get('telefone', ''),
            status_labels.get(v.get('status'), v.get('status', ''))
        ])
    
    tabela_visit = Table(dados_tabela, colWidths=[3*cm, 6*cm, 3.5*cm, 3.5*cm])
    tabela_visit.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f39c12')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fef9e7')])
    ]))
    elementos.append(tabela_visit)
    
    # Rodapé
    elementos.append(Spacer(1, 30))
    elementos.append(Paragraph(
        f"Documento gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} | CRM Igreja",
        styles['Cabecalho']
    ))
    
    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()

# ==================== RENDERIZAÇÃO ====================

def render_relatorios():
    """Função principal do módulo de relatórios"""
    st.title("📄 Relatórios PDF")
    
    if not REPORTLAB_DISPONIVEL:
        st.error("⚠️ A biblioteca ReportLab não está instalada. Execute: `pip install reportlab`")
        return
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "👥 Membros",
        "💰 Financeiro",
        "📅 Eventos",
        "👋 Visitantes"
    ])
    
    with tab1:
        render_relatorio_membros()
    
    with tab2:
        render_relatorio_financeiro()
    
    with tab3:
        render_relatorio_eventos()
    
    with tab4:
        render_relatorio_visitantes()

def render_relatorio_membros():
    """Renderiza opções de relatório de membros"""
    st.subheader("👥 Relatório de Membros")
    
    st.write("Gere um relatório completo dos membros da igreja.")

    pdf_bytes = None  # Armazena PDF fora do form para permitir download
    
    with st.form("form_rel_membros"):
        status = st.selectbox(
            "Filtrar por Status",
            options=['Todos', 'ativo', 'inativo', 'visitante', 'afastado'],
            format_func=lambda x: x.title() if x != 'Todos' else x
        )
        
        submit = st.form_submit_button("📥 Gerar PDF", use_container_width=True)
        
        if submit:
            filtros = {}
            if status != 'Todos':
                filtros['status'] = status
            
            with st.spinner("Gerando relatório..."):
                pdf_bytes = gerar_pdf_membros(filtros)

    if pdf_bytes:
        st.download_button(
            label="⬇️ Baixar Relatório",
            data=pdf_bytes,
            file_name=f"relatorio_membros_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf"
        )

def render_relatorio_financeiro():
    """Renderiza opções de relatório financeiro"""
    st.subheader("💰 Relatório Financeiro")
    
    st.write("Gere um relatório financeiro detalhado do período.")

    pdf_bytes = None
    
    with st.form("form_rel_financeiro"):
        col1, col2 = st.columns(2)
        
        with col1:
            inicio = st.date_input(
                "Data Início",
                value=date.today().replace(day=1),
                format="DD/MM/YYYY"
            )
        
        with col2:
            fim = st.date_input(
                "Data Fim",
                value=date.today(),
                format="DD/MM/YYYY"
            )
        
        submit = st.form_submit_button("📥 Gerar PDF", use_container_width=True)
        
        if submit:
            with st.spinner("Gerando relatório..."):
                pdf_bytes = gerar_pdf_financeiro(inicio, fim)

    if pdf_bytes:
        st.download_button(
            label="⬇️ Baixar Relatório",
            data=pdf_bytes,
            file_name=f"relatorio_financeiro_{inicio}_{fim}.pdf",
            mime="application/pdf"
        )

def render_relatorio_eventos():
    """Renderiza opções de relatório de eventos"""
    st.subheader("📅 Relatório de Eventos")
    
    st.write("Gere um relatório dos eventos e presenças.")

    pdf_bytes = None
    
    with st.form("form_rel_eventos"):
        col1, col2 = st.columns(2)
        
        with col1:
            inicio = st.date_input(
                "Data Início",
                value=date.today() - timedelta(days=30),
                format="DD/MM/YYYY"
            )
        
        with col2:
            fim = st.date_input(
                "Data Fim",
                value=date.today(),
                format="DD/MM/YYYY"
            )
        
        submit = st.form_submit_button("📥 Gerar PDF", use_container_width=True)
        
        if submit:
            with st.spinner("Gerando relatório..."):
                pdf_bytes = gerar_pdf_eventos(inicio, fim)

    if pdf_bytes:
        st.download_button(
            label="⬇️ Baixar Relatório",
            data=pdf_bytes,
            file_name=f"relatorio_eventos_{inicio}_{fim}.pdf",
            mime="application/pdf"
        )

def render_relatorio_visitantes():
    """Renderiza opções de relatório de visitantes"""
    st.subheader("👋 Relatório de Visitantes")
    
    st.write("Gere um relatório dos visitantes e funil de conversão.")

    pdf_bytes = None
    
    with st.form("form_rel_visitantes"):
        col1, col2 = st.columns(2)
        
        with col1:
            inicio = st.date_input(
                "Data Início",
                value=date.today() - timedelta(days=90),
                format="DD/MM/YYYY"
            )
        
        with col2:
            fim = st.date_input(
                "Data Fim",
                value=date.today(),
                format="DD/MM/YYYY"
            )
        
        submit = st.form_submit_button("📥 Gerar PDF", use_container_width=True)
        
        if submit:
            with st.spinner("Gerando relatório..."):
                pdf_bytes = gerar_pdf_visitantes(inicio, fim)

    if pdf_bytes:
        st.download_button(
            label="⬇️ Baixar Relatório",
            data=pdf_bytes,
            file_name=f"relatorio_visitantes_{inicio}_{fim}.pdf",
            mime="application/pdf"
        )
