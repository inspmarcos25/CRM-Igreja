"""
Módulo de Pessoas (Core do CRM)
Cadastro e gerenciamento de membros e visitantes
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date
from database.db import get_connection
from modules.auth import get_igreja_id, tem_permissao, get_usuario_atual, registrar_log
from config.settings import STATUS_PESSOA, formatar_data_br

def get_pessoas(filtros: dict = None) -> list:
    """Busca pessoas com filtros opcionais"""
    igreja_id = get_igreja_id()
    
    query = '''
        SELECT p.*, 
               f.nome as familia_nome,
               GROUP_CONCAT(DISTINCT t.nome) as tags
        FROM pessoas p
        LEFT JOIN familias f ON p.familia_id = f.id
        LEFT JOIN pessoa_tags pt ON p.id = pt.pessoa_id
        LEFT JOIN tags t ON pt.tag_id = t.id
        WHERE p.igreja_id = ? AND (p.ativo IS NULL OR p.ativo = 1)
    '''
    params = [igreja_id]
    
    if filtros:
        if filtros.get('status'):
            query += ' AND p.status = ?'
            params.append(filtros['status'])
        if filtros.get('busca'):
            query += ' AND (p.nome LIKE ? OR p.email LIKE ? OR p.celular LIKE ?)'
            busca = f"%{filtros['busca']}%"
            params.extend([busca, busca, busca])
        if filtros.get('tag_id'):
            query += ' AND pt.tag_id = ?'
            params.append(filtros['tag_id'])
    
    query += ' GROUP BY p.id ORDER BY p.nome'
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def get_pessoa(pessoa_id: int) -> dict | None:
    """Busca uma pessoa pelo ID"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.*, f.nome as familia_nome
            FROM pessoas p
            LEFT JOIN familias f ON p.familia_id = f.id
            WHERE p.id = ? AND p.igreja_id = ?
        ''', (pessoa_id, igreja_id))
        row = cursor.fetchone()
        return dict(row) if row else None

def verificar_pessoa_duplicada(nome: str, email: str = None, celular: str = None, pessoa_id: int = None) -> bool:
    """Verifica se já existe uma pessoa com os mesmos dados"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Verificar por nome exato (apenas pessoas ativas e diferentes da atual)
        query = 'SELECT id FROM pessoas WHERE igreja_id = ? AND LOWER(TRIM(nome)) = LOWER(TRIM(?)) AND (ativo IS NULL OR ativo = 1)'
        params = [igreja_id, nome]
        
        # Se tiver ID, excluir da busca (para permitir edição)
        if pessoa_id:
            query += ' AND id != ?'
            params.append(pessoa_id)
        
        cursor.execute(query, params)
        resultado = cursor.fetchone()
        if resultado:
            return True
        
        # Verificar por email (se fornecido e não vazio)
        if email and email.strip():
            query = 'SELECT id FROM pessoas WHERE igreja_id = ? AND TRIM(email) = TRIM(?) AND (ativo IS NULL OR ativo = 1)'
            params = [igreja_id, email]
            if pessoa_id:
                query += ' AND id != ?'
                params.append(pessoa_id)
            cursor.execute(query, params)
            resultado = cursor.fetchone()
            if resultado:
                return True
        
        # Verificar por celular (se fornecido e não vazio)
        if celular and celular.strip():
            query = 'SELECT id FROM pessoas WHERE igreja_id = ? AND TRIM(celular) = TRIM(?) AND (ativo IS NULL OR ativo = 1)'
            params = [igreja_id, celular]
            if pessoa_id:
                query += ' AND id != ?'
                params.append(pessoa_id)
            cursor.execute(query, params)
            resultado = cursor.fetchone()
            if resultado:
                return True
    
    return False

def salvar_pessoa(dados: dict) -> int:
    """Salva ou atualiza uma pessoa"""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        if dados.get('id'):
            # Atualizar
            campos = ', '.join([f"{k} = ?" for k in dados.keys() if k != 'id'])
            valores = [v for k, v in dados.items() if k != 'id']
            valores.extend([datetime.now(), dados['id'], igreja_id])
            
            cursor.execute(f'''
                UPDATE pessoas SET {campos}, data_atualizacao = ?
                WHERE id = ? AND igreja_id = ?
            ''', valores)
            
            registrar_log(usuario['id'], igreja_id, 'pessoa.atualizar', f"Pessoa ID {dados['id']} atualizada")
            return dados['id']
        else:
            # Inserir
            dados['igreja_id'] = igreja_id
            dados['data_cadastro'] = datetime.now()
            
            campos = ', '.join(dados.keys())
            placeholders = ', '.join(['?' for _ in dados])
            
            cursor.execute(f'''
                INSERT INTO pessoas ({campos}) VALUES ({placeholders})
            ''', list(dados.values()))
            
            pessoa_id = cursor.lastrowid
            registrar_log(usuario['id'], igreja_id, 'pessoa.criar', f"Pessoa ID {pessoa_id} criada")
            return pessoa_id

def excluir_pessoa(pessoa_id: int) -> bool:
    """Exclui uma pessoa (soft delete)"""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Verificar se a pessoa existe
            cursor.execute('SELECT id FROM pessoas WHERE id = ? AND igreja_id = ?', (pessoa_id, igreja_id))
            if not cursor.fetchone():
                return False
            
            # Fazer soft delete (marcar como inativo)
            cursor.execute('''
                UPDATE pessoas 
                SET ativo = 0, data_atualizacao = ?
                WHERE id = ? AND igreja_id = ?
            ''', (datetime.now(), pessoa_id, igreja_id))
            
            registrar_log(usuario['id'], igreja_id, 'pessoa.excluir', f"Pessoa ID {pessoa_id} excluída")
            return True
    except Exception as e:
        print(f"Erro ao excluir pessoa: {e}")
        return False

def get_tags() -> list:
    """Busca todas as tags da igreja"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tags WHERE igreja_id = ?', (igreja_id,))
        return [dict(row) for row in cursor.fetchall()]

def get_historico_pessoa(pessoa_id: int) -> dict:
    """Busca histórico completo de uma pessoa"""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    historico = {
        'presencas': [],
        'ministerios': [],
        'celulas': [],
        'followups': [],
        'aconselhamentos': []
    }
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Presenças em eventos
        cursor.execute('''
            SELECT pe.*, e.nome as evento_nome, e.tipo as evento_tipo, e.data_inicio
            FROM presenca_evento pe
            JOIN eventos e ON pe.evento_id = e.id
            WHERE pe.pessoa_id = ?
            ORDER BY e.data_inicio DESC
            LIMIT 50
        ''', (pessoa_id,))
        historico['presencas'] = [dict(row) for row in cursor.fetchall()]
        
        # Ministérios
        cursor.execute('''
            SELECT pm.*, m.nome as ministerio_nome
            FROM pessoa_ministerios pm
            JOIN ministerios m ON pm.ministerio_id = m.id
            WHERE pm.pessoa_id = ?
            ORDER BY pm.data_entrada DESC
        ''', (pessoa_id,))
        historico['ministerios'] = [dict(row) for row in cursor.fetchall()]
        
        # Células
        cursor.execute('''
            SELECT pc.*, c.nome as celula_nome
            FROM pessoa_celulas pc
            JOIN celulas c ON pc.celula_id = c.id
            WHERE pc.pessoa_id = ?
            ORDER BY pc.data_entrada DESC
        ''', (pessoa_id,))
        historico['celulas'] = [dict(row) for row in cursor.fetchall()]
        
        # Follow-ups
        cursor.execute('''
            SELECT f.*, p.nome as responsavel_nome
            FROM followup f
            LEFT JOIN pessoas p ON f.responsavel_id = p.id
            WHERE f.pessoa_id = ?
            ORDER BY f.data_cadastro DESC
        ''', (pessoa_id,))
        historico['followups'] = [dict(row) for row in cursor.fetchall()]
        
        # Aconselhamentos (apenas para quem tem permissão)
        if tem_permissao(usuario, 'aconselhamento.ver'):
            cursor.execute('''
                SELECT a.id, a.data_atendimento, a.tipo, a.status, p.nome as conselheiro_nome
                FROM aconselhamentos a
                JOIN pessoas p ON a.conselheiro_id = p.id
                WHERE a.pessoa_id = ? AND a.igreja_id = ?
                ORDER BY a.data_atendimento DESC
            ''', (pessoa_id, igreja_id))
            historico['aconselhamentos'] = [dict(row) for row in cursor.fetchall()]
    
    return historico

def render_lista_pessoas():
    """Renderiza a lista de pessoas"""
    st.subheader("👥 Pessoas")
    
    # Filtros
    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
    
    with col1:
        busca = st.text_input("🔍 Buscar", placeholder="Nome, e-mail ou telefone...")
    
    with col2:
        status_opcoes = [("", "Todos")] + [(s[0], s[1]) for s in STATUS_PESSOA]
        status = st.selectbox("Status", options=[s[0] for s in status_opcoes], 
                             format_func=lambda x: dict(status_opcoes).get(x, x))
    
    with col3:
        tags = get_tags()
        tag_opcoes = [("", "Todas as tags")] + [(str(t['id']), t['nome']) for t in tags]
        tag = st.selectbox("Tag", options=[t[0] for t in tag_opcoes],
                          format_func=lambda x: dict(tag_opcoes).get(x, x))
    
    with col4:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ Nova Pessoa", use_container_width=True):
            st.session_state.pessoa_edit = None
            st.session_state.show_form = True
    
    # Buscar pessoas
    filtros = {}
    if busca:
        filtros['busca'] = busca
    if status:
        filtros['status'] = status
    if tag:
        filtros['tag_id'] = int(tag)
    
    pessoas = get_pessoas(filtros)
    
    if not pessoas:
        st.info("Nenhuma pessoa encontrada.")
        return
    
    # Estatísticas rápidas
    col1, col2, col3, col4 = st.columns(4)
    total = len(pessoas)
    membros = len([p for p in pessoas if p['status'] == 'membro'])
    visitantes = len([p for p in pessoas if p['status'] == 'visitante'])
    novos = len([p for p in pessoas if p['status'] == 'novo_convertido'])
    
    col1.metric("Total", total)
    col2.metric("Membros", membros)
    col3.metric("Visitantes", visitantes)
    col4.metric("Novos Convertidos", novos)
    
    st.markdown("---")
    
    # Lista de pessoas
    for pessoa in pessoas:
        status_info = next((s for s in STATUS_PESSOA if s[0] == pessoa['status']), None)
        status_cor = status_info[2] if status_info else '#808080'
        status_nome = status_info[1] if status_info else pessoa['status']
        
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
            
            with col1:
                st.markdown(f"**{pessoa['nome']}**")
                if pessoa['email']:
                    st.caption(f"📧 {pessoa['email']}")
            
            with col2:
                if pessoa['celular']:
                    st.caption(f"📱 {pessoa['celular']}")
                if pessoa['tags']:
                    st.caption(f"🏷️ {pessoa['tags']}")
            
            with col3:
                st.markdown(f"<span style='background-color: {status_cor}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.8rem;'>{status_nome}</span>", unsafe_allow_html=True)
            
            with col4:
                col_view, col_edit = st.columns(2)
                with col_view:
                    if st.button("👁️", key=f"ver_{pessoa['id']}", help="Ver detalhes"):
                        st.session_state.pessoa_view = pessoa['id']
                        st.rerun()
                with col_edit:
                    if st.button("✏️", key=f"edit_{pessoa['id']}", help="Editar"):
                        st.session_state.pessoa_edit = pessoa['id']
                        st.session_state.show_form = True
                        st.rerun()
        
        st.markdown("<hr style='margin: 0.5rem 0; opacity: 0.2;'>", unsafe_allow_html=True)

def render_form_pessoa(pessoa_id: int = None):
    """Renderiza formulário de cadastro/edição de pessoa"""
    
    pessoa = get_pessoa(pessoa_id) if pessoa_id else {}
    
    titulo = "✏️ Editar Pessoa" if pessoa_id else "➕ Nova Pessoa"
    st.subheader(titulo)
    
    if st.button("← Voltar"):
        st.session_state.show_form = False
        st.session_state.pessoa_edit = None
        st.rerun()
    
    with st.form("form_pessoa"):
        # Dados básicos
        st.markdown("### 📋 Dados Básicos")
        col1, col2 = st.columns(2)
        
        with col1:
            nome = st.text_input("Nome completo *", value=pessoa.get('nome', ''))
            email = st.text_input("E-mail", value=pessoa.get('email', ''))
            data_nascimento = st.date_input("Data de nascimento", 
                                           value=pessoa.get('data_nascimento') if pessoa.get('data_nascimento') else None,
                                           min_value=date(1900, 1, 1),
                                           max_value=date.today(),
                                           format="DD/MM/YYYY")
        
        with col2:
            celular = st.text_input("Celular", value=pessoa.get('celular', ''))
            telefone = st.text_input("Telefone fixo", value=pessoa.get('telefone', ''))
            genero = st.selectbox("Gênero", options=['', 'Masculino', 'Feminino', 'Outro'],
                                 index=['', 'Masculino', 'Feminino', 'Outro'].index(pessoa.get('genero', '')))
        
        estado_civil = st.selectbox("Estado civil", 
                                    options=['', 'Solteiro(a)', 'Casado(a)', 'Divorciado(a)', 'Viúvo(a)'],
                                    index=['', 'Solteiro(a)', 'Casado(a)', 'Divorciado(a)', 'Viúvo(a)'].index(pessoa.get('estado_civil', '')))
        
        # Endereço
        st.markdown("### 📍 Endereço")
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            endereco = st.text_input("Endereço", value=pessoa.get('endereco', ''))
        with col2:
            numero = st.text_input("Número", value=pessoa.get('numero', ''))
        with col3:
            complemento = st.text_input("Complemento", value=pessoa.get('complemento', ''))
        
        col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
        with col1:
            bairro = st.text_input("Bairro", value=pessoa.get('bairro', ''))
        with col2:
            cidade = st.text_input("Cidade", value=pessoa.get('cidade', ''))
        with col3:
            estado = st.text_input("Estado", value=pessoa.get('estado', ''))
        with col4:
            cep = st.text_input("CEP", value=pessoa.get('cep', ''))
        
        # Dados eclesiásticos
        st.markdown("### ⛪ Dados Eclesiásticos")
        col1, col2 = st.columns(2)
        
        with col1:
            status_opcoes = [(s[0], s[1]) for s in STATUS_PESSOA]
            status_atual = pessoa.get('status', 'visitante')
            status = st.selectbox("Status", 
                                 options=[s[0] for s in status_opcoes],
                                 format_func=lambda x: dict(status_opcoes).get(x, x),
                                 index=[s[0] for s in status_opcoes].index(status_atual))
            
            como_conheceu = st.selectbox("Como conheceu a igreja?",
                                         options=['', 'Convite de amigo/familiar', 'Redes sociais', 
                                                 'Passou em frente', 'Evento', 'Outro'],
                                         index=0)
        
        with col2:
            data_primeira_visita = st.date_input("Data da primeira visita",
                                                 value=pessoa.get('data_primeira_visita') if pessoa.get('data_primeira_visita') else None,
                                                 format="DD/MM/YYYY")
            data_batismo = st.date_input("Data do batismo",
                                        value=pessoa.get('data_batismo') if pessoa.get('data_batismo') else None,
                                        format="DD/MM/YYYY")
        
        igreja_anterior = st.text_input("Igreja anterior", value=pessoa.get('igreja_anterior', ''))
        
        # Observações
        st.markdown("### 📝 Observações")
        observacoes = st.text_area("Observações", value=pessoa.get('observacoes', ''), height=100)
        
        # Botões
        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("💾 Salvar", use_container_width=True)
        with col2:
            excluir = False
            if pessoa_id:
                excluir = st.form_submit_button("🗑️ Excluir", use_container_width=True, type="secondary")
        
        if submit:
            if not nome:
                st.error("O nome é obrigatório!")
            else:
                # Normalizar dados vazios para None
                email_verificar = email.strip() if email and email.strip() else None
                celular_verificar = celular.strip() if celular and celular.strip() else None
                
                # Verificar duplicação
                if verificar_pessoa_duplicada(nome, email_verificar, celular_verificar, pessoa_id):
                    st.error("❌ Já existe uma pessoa cadastrada com esses dados (nome, email ou celular)!")
                else:
                    # Verificar se não foi salvo recentemente (prevenir duplo submit)
                    ultima_acao = st.session_state.get('ultima_acao_pessoa', '')
                    timestamp_acao = st.session_state.get('timestamp_acao_pessoa', 0)
                    acao_atual = f"salvar_{nome}_{email}_{celular}_{pessoa_id}"
                    
                    if ultima_acao == acao_atual and (datetime.now().timestamp() - timestamp_acao) < 2:
                        st.warning("⚠️ Pessoa já foi salva. Aguarde...")
                    else:
                        dados = {
                            'nome': nome,
                            'email': email,
                            'celular': celular,
                            'telefone': telefone,
                            'data_nascimento': data_nascimento if data_nascimento else None,
                            'genero': genero if genero else None,
                            'estado_civil': estado_civil if estado_civil else None,
                            'endereco': endereco,
                            'numero': numero,
                            'complemento': complemento,
                            'bairro': bairro,
                            'cidade': cidade,
                            'estado': estado,
                            'cep': cep,
                            'status': status,
                            'como_conheceu': como_conheceu if como_conheceu else None,
                            'data_primeira_visita': data_primeira_visita if data_primeira_visita else None,
                            'data_batismo': data_batismo if data_batismo else None,
                            'igreja_anterior': igreja_anterior,
                            'observacoes': observacoes
                        }
                        
                        if pessoa_id:
                            dados['id'] = pessoa_id
                        
                        salvar_pessoa(dados)
                        
                        # Registrar ação para evitar duplicação
                        st.session_state.ultima_acao_pessoa = acao_atual
                        st.session_state.timestamp_acao_pessoa = datetime.now().timestamp()
                        
                        st.success("✅ Pessoa salva com sucesso!")
                        st.session_state.show_form = False
                        st.session_state.pessoa_edit = None
                        st.rerun()
        
        if excluir:
            if excluir_pessoa(pessoa_id):
                st.success("✅ Pessoa excluída com sucesso!")
                st.session_state.show_form = False
                st.session_state.pessoa_edit = None
                st.rerun()
            else:
                st.error("❌ Erro ao excluir pessoa!")

def render_detalhes_pessoa(pessoa_id: int):
    """Renderiza detalhes de uma pessoa"""
    pessoa = get_pessoa(pessoa_id)
    
    if not pessoa:
        st.error("Pessoa não encontrada!")
        return
    
    # Botões de ação
    col1, col2, col3, col4 = st.columns([1, 1, 1, 3])
    
    with col1:
        if st.button("← Voltar"):
            st.session_state.pessoa_view = None
            st.rerun()
    
    with col2:
        if st.button("✏️ Editar"):
            st.session_state.pessoa_edit = pessoa_id
            st.session_state.show_form = True
            st.session_state.pessoa_view = None
            st.rerun()
    
    with col3:
        if st.button("📱 Mensagem"):
            st.session_state.enviar_mensagem = pessoa_id
    
    # Cabeçalho
    status_info = next((s for s in STATUS_PESSOA if s[0] == pessoa['status']), None)
    status_cor = status_info[2] if status_info else '#808080'
    status_nome = status_info[1] if status_info else pessoa['status']
    
    st.markdown(f"""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2rem; border-radius: 10px; color: white; margin-bottom: 1rem;'>
            <h2 style='margin: 0;'>{pessoa['nome']}</h2>
            <span style='background-color: {status_cor}; padding: 4px 12px; border-radius: 15px; font-size: 0.9rem;'>{status_nome}</span>
        </div>
    """, unsafe_allow_html=True)
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Dados", "📊 Histórico", "⛪ Ministérios", "📞 Follow-up"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Contato")
            if pessoa['email']:
                st.write(f"📧 {pessoa['email']}")
            if pessoa['celular']:
                st.write(f"📱 {pessoa['celular']}")
            if pessoa['telefone']:
                st.write(f"📞 {pessoa['telefone']}")
            
            st.markdown("#### Pessoal")
            if pessoa['data_nascimento']:
                st.write(f"🎂 {formatar_data_br(pessoa['data_nascimento'])}")
            if pessoa['genero']:
                st.write(f"👤 {pessoa['genero']}")
            if pessoa['estado_civil']:
                st.write(f"💍 {pessoa['estado_civil']}")
        
        with col2:
            st.markdown("#### Endereço")
            endereco_completo = []
            if pessoa['endereco']:
                endereco_completo.append(f"{pessoa['endereco']}, {pessoa.get('numero', '')}")
            if pessoa['bairro']:
                endereco_completo.append(pessoa['bairro'])
            if pessoa['cidade']:
                endereco_completo.append(f"{pessoa['cidade']}/{pessoa.get('estado', '')}")
            if pessoa['cep']:
                endereco_completo.append(f"CEP: {pessoa['cep']}")
            
            st.write("📍 " + " - ".join(endereco_completo) if endereco_completo else "Não informado")
            
            st.markdown("#### Igreja")
            if pessoa['data_primeira_visita']:
                st.write(f"📅 Primeira visita: {formatar_data_br(pessoa['data_primeira_visita'])}")
            if pessoa['data_batismo']:
                st.write(f"💧 Batismo: {formatar_data_br(pessoa['data_batismo'])}")
            if pessoa['data_membresia']:
                st.write(f"🏠 Membresia: {formatar_data_br(pessoa['data_membresia'])}")
        
        if pessoa['observacoes']:
            st.markdown("#### Observações")
            st.write(pessoa['observacoes'])
    
    with tab2:
        historico = get_historico_pessoa(pessoa_id)
        
        st.markdown("#### Últimas presenças")
        if historico['presencas']:
            for p in historico['presencas'][:10]:
                st.write(f"✅ {p['evento_nome']} - {formatar_data_br(p['data_inicio'])}")
        else:
            st.info("Nenhuma presença registrada")
    
    with tab3:
        historico = get_historico_pessoa(pessoa_id)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Ministérios")
            if historico['ministerios']:
                for m in historico['ministerios']:
                    status = "🟢" if m['ativo'] else "🔴"
                    st.write(f"{status} {m['ministerio_nome']} ({m['funcao']})")
            else:
                st.info("Não participa de ministérios")
        
        with col2:
            st.markdown("#### Células")
            if historico['celulas']:
                for c in historico['celulas']:
                    status = "🟢" if c['ativo'] else "🔴"
                    st.write(f"{status} {c['celula_nome']} ({c['funcao']})")
            else:
                st.info("Não participa de células")
    
    with tab4:
        historico = get_historico_pessoa(pessoa_id)
        
        st.markdown("#### Histórico de Follow-up")
        if historico['followups']:
            for f in historico['followups']:
                status_icon = {"pendente": "🟡", "realizado": "🟢", "cancelado": "🔴"}.get(f['status'], "⚪")
                st.write(f"{status_icon} {f['tipo']} - {formatar_data_br(f['data_prevista'])} ({f['status']})")
                if f['observacoes']:
                    st.caption(f['observacoes'])
        else:
            st.info("Nenhum follow-up registrado")

def render_pessoas():
    """Função principal do módulo de pessoas"""
    
    # Verificar se está visualizando detalhes
    if st.session_state.get('pessoa_view'):
        render_detalhes_pessoa(st.session_state.pessoa_view)
        return
    
    # Verificar se está editando/criando
    if st.session_state.get('show_form'):
        render_form_pessoa(st.session_state.get('pessoa_edit'))
        return
    
    # Lista padrão
    render_lista_pessoas()
