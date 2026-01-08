"""
Módulo de Trilha de Discipulado
Cursos, turmas, matrículas e certificados
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from io import BytesIO
from database.db import get_connection
from modules.auth import get_igreja_id, get_usuario_atual, registrar_log
from config.settings import formatar_data_br

# ==================== FUNÇÕES DE DADOS ====================

def get_cursos() -> list:
    """Busca todos os cursos da igreja"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.*, 
                   p.nome as pre_requisito_nome,
                   (SELECT COUNT(*) FROM turmas t WHERE t.curso_id = c.id) as total_turmas,
                   (SELECT COUNT(*) FROM matriculas m 
                    JOIN turmas t ON m.turma_id = t.id 
                    WHERE t.curso_id = c.id AND m.status = 'concluida') as total_formados
            FROM cursos c
            LEFT JOIN cursos p ON c.pre_requisito_id = p.id
            WHERE c.igreja_id = ? AND c.ativo = 1
            ORDER BY c.ordem_trilha, c.nome
        ''', (igreja_id,))
        return [dict(row) for row in cursor.fetchall()]

def get_curso(curso_id: int) -> dict:
    """Busca um curso específico"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM cursos WHERE id = ?', (curso_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def salvar_curso(dados: dict) -> int:
    """Salva ou atualiza um curso"""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        if dados.get('id'):
            cursor.execute('''
                UPDATE cursos
                SET nome = ?, descricao = ?, categoria = ?, duracao_horas = ?,
                    pre_requisito_id = ?, ordem_trilha = ?, material_url = ?
                WHERE id = ? AND igreja_id = ?
            ''', (dados['nome'], dados.get('descricao'), dados.get('categoria'),
                  dados.get('duracao_horas'), dados.get('pre_requisito_id'),
                  dados.get('ordem_trilha', 0), dados.get('material_url'),
                  dados['id'], igreja_id))
            return dados['id']
        else:
            cursor.execute('''
                INSERT INTO cursos (igreja_id, nome, descricao, categoria, duracao_horas,
                                   pre_requisito_id, ordem_trilha, material_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (igreja_id, dados['nome'], dados.get('descricao'), dados.get('categoria'),
                  dados.get('duracao_horas'), dados.get('pre_requisito_id'),
                  dados.get('ordem_trilha', 0), dados.get('material_url')))
            registrar_log(usuario['id'], igreja_id, 'curso.criar', f"Curso criado: {dados['nome']}")
            return cursor.lastrowid

def get_turmas(curso_id: int = None, status: str = None) -> list:
    """Busca turmas de um curso"""
    igreja_id = get_igreja_id()
    
    query = '''
        SELECT t.*, c.nome as curso_nome, i.nome as instrutor_nome,
               (SELECT COUNT(*) FROM matriculas m WHERE m.turma_id = t.id) as total_matriculas
        FROM turmas t
        JOIN cursos c ON t.curso_id = c.id
        LEFT JOIN pessoas i ON t.instrutor_id = i.id
        WHERE c.igreja_id = ?
    '''
    params = [igreja_id]
    
    if curso_id:
        query += ' AND t.curso_id = ?'
        params.append(curso_id)
    
    if status:
        query += ' AND t.status = ?'
        params.append(status)
    
    query += ' ORDER BY t.data_inicio DESC'
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def salvar_turma(dados: dict) -> int:
    """Salva ou atualiza uma turma"""
    usuario = get_usuario_atual()
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        if dados.get('id'):
            cursor.execute('''
                UPDATE turmas
                SET nome = ?, instrutor_id = ?, data_inicio = ?, data_fim = ?,
                    horario = ?, local = ?, vagas = ?, status = ?
                WHERE id = ?
            ''', (dados['nome'], dados.get('instrutor_id'), dados.get('data_inicio'),
                  dados.get('data_fim'), dados.get('horario'), dados.get('local'),
                  dados.get('vagas', 30), dados.get('status', 'aberta'), dados['id']))
            return dados['id']
        else:
            cursor.execute('''
                INSERT INTO turmas (curso_id, nome, instrutor_id, data_inicio, data_fim,
                                   horario, local, vagas, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (dados['curso_id'], dados['nome'], dados.get('instrutor_id'),
                  dados.get('data_inicio'), dados.get('data_fim'), dados.get('horario'),
                  dados.get('local'), dados.get('vagas', 30), dados.get('status', 'aberta')))
            registrar_log(usuario['id'], igreja_id, 'turma.criar', f"Turma criada: {dados['nome']}")
            return cursor.lastrowid

def get_matriculas(turma_id: int) -> list:
    """Busca matrículas de uma turma"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT m.*, p.nome as pessoa_nome, p.celular, p.email
            FROM matriculas m
            JOIN pessoas p ON m.pessoa_id = p.id
            WHERE m.turma_id = ?
            ORDER BY p.nome
        ''', (turma_id,))
        return [dict(row) for row in cursor.fetchall()]

def matricular_pessoa(turma_id: int, pessoa_id: int) -> int:
    """Matricula uma pessoa em uma turma"""
    usuario = get_usuario_atual()
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Verificar se já está matriculado
        cursor.execute('''
            SELECT id FROM matriculas WHERE turma_id = ? AND pessoa_id = ?
        ''', (turma_id, pessoa_id))
        
        if cursor.fetchone():
            return -1  # Já matriculado
        
        cursor.execute('''
            INSERT INTO matriculas (turma_id, pessoa_id, data_matricula, status)
            VALUES (?, ?, ?, 'ativa')
        ''', (turma_id, pessoa_id, date.today()))
        
        registrar_log(usuario['id'], igreja_id, 'matricula.criar', 
                     f"Pessoa {pessoa_id} matriculada na turma {turma_id}")
        return cursor.lastrowid

def atualizar_matricula(matricula_id: int, dados: dict):
    """Atualiza dados de uma matrícula"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        campos = []
        valores = []
        
        if 'status' in dados:
            campos.append('status = ?')
            valores.append(dados['status'])
        if 'nota_final' in dados:
            campos.append('nota_final = ?')
            valores.append(dados['nota_final'])
        if 'frequencia' in dados:
            campos.append('frequencia = ?')
            valores.append(dados['frequencia'])
        if 'data_conclusao' in dados:
            campos.append('data_conclusao = ?')
            valores.append(dados['data_conclusao'])
        if 'certificado_emitido' in dados:
            campos.append('certificado_emitido = ?')
            valores.append(dados['certificado_emitido'])
        
        if campos:
            valores.append(matricula_id)
            cursor.execute(f'''
                UPDATE matriculas SET {', '.join(campos)} WHERE id = ?
            ''', valores)

def get_trilha_pessoa(pessoa_id: int) -> list:
    """Busca a trilha de discipulado de uma pessoa"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.*, m.status as matricula_status, m.nota_final, m.data_conclusao,
                   t.nome as turma_nome
            FROM cursos c
            LEFT JOIN turmas t ON t.curso_id = c.id
            LEFT JOIN matriculas m ON m.turma_id = t.id AND m.pessoa_id = ?
            WHERE c.igreja_id = ? AND c.ativo = 1
            ORDER BY c.ordem_trilha
        ''', (pessoa_id, igreja_id))
        return [dict(row) for row in cursor.fetchall()]

def get_estatisticas_cursos() -> dict:
    """Retorna estatísticas dos cursos"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Total de cursos
        cursor.execute('SELECT COUNT(*) FROM cursos WHERE igreja_id = ? AND ativo = 1', (igreja_id,))
        total_cursos = cursor.fetchone()[0]
        
        # Total de turmas ativas
        cursor.execute('''
            SELECT COUNT(*) FROM turmas t
            JOIN cursos c ON t.curso_id = c.id
            WHERE c.igreja_id = ? AND t.status = 'aberta'
        ''', (igreja_id,))
        turmas_ativas = cursor.fetchone()[0]
        
        # Total de alunos matriculados
        cursor.execute('''
            SELECT COUNT(DISTINCT m.pessoa_id) FROM matriculas m
            JOIN turmas t ON m.turma_id = t.id
            JOIN cursos c ON t.curso_id = c.id
            WHERE c.igreja_id = ? AND m.status = 'ativa'
        ''', (igreja_id,))
        alunos_ativos = cursor.fetchone()[0]
        
        # Total de formados
        cursor.execute('''
            SELECT COUNT(*) FROM matriculas m
            JOIN turmas t ON m.turma_id = t.id
            JOIN cursos c ON t.curso_id = c.id
            WHERE c.igreja_id = ? AND m.status = 'concluida'
        ''', (igreja_id,))
        total_formados = cursor.fetchone()[0]
        
        return {
            'total_cursos': total_cursos,
            'turmas_ativas': turmas_ativas,
            'alunos_ativos': alunos_ativos,
            'total_formados': total_formados
        }

def gerar_certificado(matricula_id: int) -> bytes:
    """Gera certificado em PDF"""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm
    
    # Buscar dados da matrícula
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT m.*, p.nome as pessoa_nome, c.nome as curso_nome,
                   c.duracao_horas, t.data_fim, i.nome as instrutor_nome,
                   ig.nome as igreja_nome
            FROM matriculas m
            JOIN pessoas p ON m.pessoa_id = p.id
            JOIN turmas t ON m.turma_id = t.id
            JOIN cursos c ON t.curso_id = c.id
            LEFT JOIN pessoas i ON t.instrutor_id = i.id
            JOIN igrejas ig ON c.igreja_id = ig.id
            WHERE m.id = ?
        ''', (matricula_id,))
        dados = dict(cursor.fetchone())
    
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    
    # Fundo decorativo
    c.setFillColorRGB(0.95, 0.95, 0.98)
    c.rect(0, 0, width, height, fill=True, stroke=False)
    
    # Borda decorativa
    c.setStrokeColorRGB(0.4, 0.3, 0.6)
    c.setLineWidth(3)
    c.rect(30, 30, width - 60, height - 60, fill=False, stroke=True)
    c.setLineWidth(1)
    c.rect(40, 40, width - 80, height - 80, fill=False, stroke=True)
    
    # Título
    c.setFillColorRGB(0.3, 0.2, 0.5)
    c.setFont("Helvetica-Bold", 36)
    c.drawCentredString(width / 2, height - 100, "CERTIFICADO")
    
    # Texto principal
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.setFont("Helvetica", 14)
    c.drawCentredString(width / 2, height - 150, "Certificamos que")
    
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width / 2, height - 190, dados['pessoa_nome'].upper())
    
    c.setFont("Helvetica", 14)
    c.drawCentredString(width / 2, height - 230, "concluiu com êxito o curso")
    
    c.setFont("Helvetica-Bold", 20)
    c.setFillColorRGB(0.3, 0.2, 0.5)
    c.drawCentredString(width / 2, height - 270, dados['curso_nome'])
    
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.setFont("Helvetica", 12)
    
    if dados.get('duracao_horas'):
        c.drawCentredString(width / 2, height - 300, f"Carga horária: {dados['duracao_horas']} horas")
    
    if dados.get('data_conclusao'):
        data_formatada = formatar_data_br(dados['data_conclusao'])
        c.drawCentredString(width / 2, height - 330, f"Concluído em: {data_formatada}")
    
    # Igreja
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, height - 380, dados.get('igreja_nome', 'Igreja'))
    
    # Assinaturas
    c.setLineWidth(0.5)
    c.line(150, 100, 350, 100)
    c.line(width - 350, 100, width - 150, 100)
    
    c.setFont("Helvetica", 10)
    c.drawCentredString(250, 85, dados.get('instrutor_nome', 'Instrutor'))
    c.drawCentredString(width - 250, 85, "Coordenação")
    
    c.save()
    buffer.seek(0)
    return buffer.getvalue()

# ==================== RENDERIZAÇÃO ====================

def render_discipulado():
    """Função principal do módulo de discipulado"""
    st.title("🎓 Trilha de Discipulado")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📚 Cursos",
        "👥 Turmas",
        "📝 Matrículas",
        "🎯 Minha Trilha",
        "📊 Estatísticas"
    ])
    
    with tab1:
        render_cursos()
    
    with tab2:
        render_turmas()
    
    with tab3:
        render_matriculas()
    
    with tab4:
        render_minha_trilha()
    
    with tab5:
        render_estatisticas()

def render_cursos():
    """Renderiza gestão de cursos"""
    st.subheader("📚 Cursos Disponíveis")
    
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("➕ Novo Curso", use_container_width=True):
            st.session_state.novo_curso = True
    
    # Formulário de novo curso
    if st.session_state.get('novo_curso'):
        with st.form("form_curso"):
            st.markdown("### ➕ Novo Curso")
            
            nome = st.text_input("Nome do Curso *")
            descricao = st.text_area("Descrição")
            
            col1, col2 = st.columns(2)
            with col1:
                categoria = st.selectbox(
                    "Categoria",
                    options=['Fundamentos', 'Discipulado', 'Liderança', 'Ministérios', 'Especial']
                )
            with col2:
                duracao = st.number_input("Duração (horas)", min_value=1, value=8)
            
            col3, col4 = st.columns(2)
            with col3:
                ordem = st.number_input("Ordem na Trilha", min_value=0, value=0)
            with col4:
                cursos = get_cursos()
                pre_req = st.selectbox(
                    "Pré-requisito",
                    options=[None] + cursos,
                    format_func=lambda x: x['nome'] if x else 'Nenhum'
                )
            
            col_a, col_b = st.columns(2)
            with col_a:
                if st.form_submit_button("💾 Salvar", use_container_width=True):
                    if nome:
                        salvar_curso({
                            'nome': nome,
                            'descricao': descricao,
                            'categoria': categoria,
                            'duracao_horas': duracao,
                            'ordem_trilha': ordem,
                            'pre_requisito_id': pre_req['id'] if pre_req else None
                        })
                        st.success("Curso criado!")
                        del st.session_state.novo_curso
                        st.rerun()
            with col_b:
                if st.form_submit_button("❌ Cancelar", use_container_width=True):
                    del st.session_state.novo_curso
                    st.rerun()
    
    # Lista de cursos
    cursos = get_cursos()
    
    if not cursos:
        st.info("Nenhum curso cadastrado.")
        return
    
    # Visualização da trilha
    st.markdown("### 🛤️ Trilha de Formação")
    
    cols = st.columns(min(len(cursos), 4))
    for i, curso in enumerate(cursos):
        with cols[i % 4]:
            cor = {'Fundamentos': '#3498db', 'Discipulado': '#9b59b6', 
                   'Liderança': '#e74c3c', 'Ministérios': '#2ecc71', 'Especial': '#f39c12'}
            
            st.markdown(f"""
                <div style='background: {cor.get(curso.get('categoria', 'Fundamentos'), '#3498db')}; 
                            padding: 1rem; border-radius: 10px; color: white; 
                            min-height: 150px; margin-bottom: 1rem;'>
                    <h4 style='margin: 0;'>{curso['nome']}</h4>
                    <p style='font-size: 0.85rem; opacity: 0.9;'>{curso.get('categoria', '')}</p>
                    <hr style='opacity: 0.3;'>
                    <small>⏱️ {curso.get('duracao_horas', 0)}h | 🎓 {curso.get('total_formados', 0)} formados</small>
                </div>
            """, unsafe_allow_html=True)

def render_turmas():
    """Renderiza gestão de turmas"""
    st.subheader("👥 Turmas")
    
    cursos = get_cursos()
    
    if not cursos:
        st.warning("Cadastre cursos primeiro!")
        return
    
    col1, col2 = st.columns([3, 1])
    with col1:
        curso_filtro = st.selectbox(
            "Filtrar por Curso",
            options=[None] + cursos,
            format_func=lambda x: x['nome'] if x else 'Todos os Cursos'
        )
    with col2:
        if st.button("➕ Nova Turma", use_container_width=True):
            st.session_state.nova_turma = True
    
    # Formulário de nova turma
    if st.session_state.get('nova_turma'):
        with st.form("form_turma"):
            st.markdown("### ➕ Nova Turma")
            
            curso = st.selectbox("Curso *", options=cursos, format_func=lambda x: x['nome'])
            nome = st.text_input("Nome da Turma *", placeholder="Ex: Turma 2026.1")
            
            from modules.pessoas import get_pessoas
            pessoas = get_pessoas()
            instrutor = st.selectbox(
                "Instrutor",
                options=[None] + pessoas,
                format_func=lambda x: x['nome'] if x else 'Selecione...'
            )
            
            col1, col2 = st.columns(2)
            with col1:
                data_inicio = st.date_input("Data Início", format="DD/MM/YYYY")
            with col2:
                data_fim = st.date_input("Data Fim", format="DD/MM/YYYY", 
                                        value=date.today() + timedelta(days=60))
            
            col3, col4 = st.columns(2)
            with col3:
                horario = st.text_input("Horário", placeholder="Ex: Sábados 9h às 12h")
            with col4:
                vagas = st.number_input("Vagas", min_value=1, value=30)
            
            local = st.text_input("Local", placeholder="Ex: Sala 1 - Anexo")
            
            col_a, col_b = st.columns(2)
            with col_a:
                if st.form_submit_button("💾 Salvar", use_container_width=True):
                    if nome and curso:
                        salvar_turma({
                            'curso_id': curso['id'],
                            'nome': nome,
                            'instrutor_id': instrutor['id'] if instrutor else None,
                            'data_inicio': data_inicio,
                            'data_fim': data_fim,
                            'horario': horario,
                            'local': local,
                            'vagas': vagas
                        })
                        st.success("Turma criada!")
                        del st.session_state.nova_turma
                        st.rerun()
            with col_b:
                if st.form_submit_button("❌ Cancelar", use_container_width=True):
                    del st.session_state.nova_turma
                    st.rerun()
    
    # Lista de turmas
    turmas = get_turmas(curso_filtro['id'] if curso_filtro else None)
    
    if not turmas:
        st.info("Nenhuma turma cadastrada.")
        return
    
    for turma in turmas:
        status_cor = {'aberta': '🟢', 'em_andamento': '🟡', 'concluida': '🔵', 'cancelada': '🔴'}
        
        with st.expander(f"{status_cor.get(turma['status'], '⚪')} {turma['nome']} - {turma['curso_nome']}"):
            col1, col2, col3 = st.columns(3)
            col1.write(f"**Instrutor:** {turma.get('instrutor_nome', 'A definir')}")
            col2.write(f"**Período:** {formatar_data_br(turma['data_inicio'])} a {formatar_data_br(turma['data_fim'])}")
            col3.write(f"**Matriculados:** {turma['total_matriculas']}/{turma['vagas']}")
            
            st.write(f"📍 {turma.get('local', 'A definir')} | 🕐 {turma.get('horario', 'A definir')}")

def render_matriculas():
    """Renderiza gestão de matrículas"""
    st.subheader("📝 Matrículas")
    
    turmas = get_turmas(status='aberta')
    
    if not turmas:
        st.warning("Nenhuma turma aberta para matrícula.")
        return
    
    turma_selecionada = st.selectbox(
        "Selecione a Turma",
        options=turmas,
        format_func=lambda x: f"{x['curso_nome']} - {x['nome']}"
    )
    
    if turma_selecionada:
        matriculas = get_matriculas(turma_selecionada['id'])
        
        st.markdown(f"### 📋 Alunos Matriculados ({len(matriculas)}/{turma_selecionada['vagas']})")
        
        # Matricular nova pessoa
        st.markdown("**➕ Nova Matrícula**")
        
        from modules.pessoas import get_pessoas
        pessoas = get_pessoas()
        
        # Filtrar pessoas não matriculadas
        ids_matriculados = [m['pessoa_id'] for m in matriculas]
        pessoas_disponiveis = [p for p in pessoas if p['id'] not in ids_matriculados]
        
        col1, col2 = st.columns([3, 1])
        with col1:
            pessoa = st.selectbox(
                "Pessoa",
                options=pessoas_disponiveis,
                format_func=lambda x: x['nome']
            )
        with col2:
            st.write("")
            st.write("")
            if st.button("➕ Matricular"):
                if pessoa:
                    resultado = matricular_pessoa(turma_selecionada['id'], pessoa['id'])
                    if resultado > 0:
                        st.success(f"{pessoa['nome']} matriculado(a)!")
                        st.rerun()
                    else:
                        st.error("Pessoa já matriculada!")
        
        st.markdown("---")
        
        # Lista de matriculados
        if matriculas:
            for m in matriculas:
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                
                with col1:
                    st.write(f"👤 {m['pessoa_nome']}")
                
                with col2:
                    status_label = {'ativa': '📚 Ativa', 'concluida': '🎓 Concluída', 
                                   'cancelada': '❌ Cancelada', 'trancada': '⏸️ Trancada'}
                    st.write(status_label.get(m['status'], m['status']))
                
                with col3:
                    if m['status'] == 'ativa':
                        if st.button("🎓", key=f"conc_{m['id']}", help="Concluir"):
                            atualizar_matricula(m['id'], {
                                'status': 'concluida',
                                'data_conclusao': date.today()
                            })
                            st.rerun()
                
                with col4:
                    if m['status'] == 'concluida' and not m['certificado_emitido']:
                        if st.button("📜", key=f"cert_{m['id']}", help="Certificado"):
                            pdf = gerar_certificado(m['id'])
                            st.download_button(
                                "⬇️ PDF",
                                pdf,
                                file_name=f"certificado_{m['pessoa_nome']}.pdf",
                                mime="application/pdf",
                                key=f"down_{m['id']}"
                            )

def render_minha_trilha():
    """Renderiza trilha de discipulado do usuário"""
    st.subheader("🎯 Minha Trilha de Discipulado")
    
    usuario = get_usuario_atual()
    pessoa_id = usuario.get('pessoa_id')
    
    if not pessoa_id:
        st.warning("Seu usuário não está vinculado a um cadastro de pessoa.")
        return
    
    trilha = get_trilha_pessoa(pessoa_id)
    cursos = get_cursos()
    
    if not cursos:
        st.info("Nenhum curso disponível no momento.")
        return
    
    # Progresso geral
    total = len(cursos)
    concluidos = len([t for t in trilha if t.get('matricula_status') == 'concluida'])
    
    st.progress(concluidos / total if total > 0 else 0)
    st.write(f"**Progresso:** {concluidos}/{total} cursos concluídos")
    
    st.markdown("---")
    
    # Lista de cursos
    for curso in cursos:
        # Buscar status da matrícula
        matricula = next((t for t in trilha if t['id'] == curso['id'] and t.get('matricula_status')), None)
        
        if matricula and matricula.get('matricula_status') == 'concluida':
            icon = "✅"
            status = "Concluído"
            cor = "#2ecc71"
        elif matricula:
            icon = "📚"
            status = "Em andamento"
            cor = "#f39c12"
        else:
            icon = "⭕"
            status = "Não iniciado"
            cor = "#95a5a6"
        
        st.markdown(f"""
            <div style='background: {cor}22; border-left: 4px solid {cor}; 
                        padding: 1rem; border-radius: 5px; margin-bottom: 0.5rem;'>
                <strong>{icon} {curso['nome']}</strong>
                <span style='float: right; color: {cor};'>{status}</span>
                <br><small>{curso.get('descricao', '')}</small>
            </div>
        """, unsafe_allow_html=True)

def render_estatisticas():
    """Renderiza estatísticas dos cursos"""
    st.subheader("📊 Estatísticas")
    
    stats = get_estatisticas_cursos()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📚 Cursos", stats['total_cursos'])
    col2.metric("👥 Turmas Ativas", stats['turmas_ativas'])
    col3.metric("📖 Alunos Ativos", stats['alunos_ativos'])
    col4.metric("🎓 Total Formados", stats['total_formados'])
