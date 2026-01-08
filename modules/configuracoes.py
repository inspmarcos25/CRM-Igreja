"""
Módulo de Configurações do Sistema
Gerenciamento de usuários, perfil, igreja e sistema
"""
import streamlit as st
import bcrypt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
from database.db import get_connection
from config.settings import PERFIS, formatar_data_br
from modules.auth import tem_permissao, get_usuario_atual, hash_senha, verificar_senha, registrar_log

# ========================================
# FUNÇÕES DE BANCO DE DADOS
# ========================================

def get_igreja_id():
    """Retorna o ID da igreja do usuário atual"""
    usuario = get_usuario_atual()
    return usuario.get('igreja_id') if usuario else None

def get_usuarios_igreja():
    """Retorna todos os usuários da igreja"""
    igreja_id = get_igreja_id()
    if not igreja_id:
        return []
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.*, p.nome as pessoa_nome
            FROM usuarios u
            LEFT JOIN pessoas p ON u.pessoa_id = p.id
            WHERE u.igreja_id = ?
            ORDER BY u.nome
        ''', (igreja_id,))
        return [dict(row) for row in cursor.fetchall()]

def get_usuario_por_id(usuario_id: int):
    """Retorna um usuário pelo ID"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.*, p.nome as pessoa_nome
            FROM usuarios u
            LEFT JOIN pessoas p ON u.pessoa_id = p.id
            WHERE u.id = ?
        ''', (usuario_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def criar_usuario(dados: dict):
    """Cria um novo usuário"""
    igreja_id = get_igreja_id()
    if not igreja_id:
        return None
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Verificar se email já existe
        cursor.execute('SELECT id FROM usuarios WHERE email = ?', (dados['email'],))
        if cursor.fetchone():
            return None
        
        cursor.execute('''
            INSERT INTO usuarios (igreja_id, nome, email, senha_hash, perfil, pessoa_id, ativo)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            igreja_id,
            dados['nome'],
            dados['email'],
            hash_senha(dados['senha']),
            dados['perfil'],
            dados.get('pessoa_id'),
            1
        ))
        
        return cursor.lastrowid

def atualizar_usuario(usuario_id: int, dados: dict):
    """Atualiza dados de um usuário"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Verificar se email já existe em outro usuário
        cursor.execute('SELECT id FROM usuarios WHERE email = ? AND id != ?', 
                      (dados['email'], usuario_id))
        if cursor.fetchone():
            return False
        
        cursor.execute('''
            UPDATE usuarios 
            SET nome = ?, email = ?, perfil = ?, pessoa_id = ?, ativo = ?
            WHERE id = ?
        ''', (
            dados['nome'],
            dados['email'],
            dados['perfil'],
            dados.get('pessoa_id'),
            dados.get('ativo', 1),
            usuario_id
        ))
        
        return True

def alterar_senha_usuario(usuario_id: int, nova_senha: str):
    """Altera a senha de um usuário"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE usuarios SET senha_hash = ? WHERE id = ?
        ''', (hash_senha(nova_senha), usuario_id))
        return True

def get_igreja_dados():
    """Retorna os dados da igreja do usuário atual"""
    igreja_id = get_igreja_id()
    if not igreja_id:
        return None
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM igrejas WHERE id = ?', (igreja_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def atualizar_igreja(dados: dict):
    """Atualiza os dados da igreja"""
    igreja_id = get_igreja_id()
    if not igreja_id:
        return False
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE igrejas 
            SET nome = ?, cnpj = ?, endereco = ?, cidade = ?, estado = ?, 
                cep = ?, telefone = ?, email = ?
            WHERE id = ?
        ''', (
            dados['nome'],
            dados.get('cnpj'),
            dados.get('endereco'),
            dados.get('cidade'),
            dados.get('estado'),
            dados.get('cep'),
            dados.get('telefone'),
            dados.get('email'),
            igreja_id
        ))
        return True

def get_logs_acesso(limite: int = 100):
    """Retorna os logs de acesso da igreja"""
    igreja_id = get_igreja_id()
    if not igreja_id:
        return []
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT l.*, u.nome as usuario_nome, u.email as usuario_email
            FROM logs_acesso l
            LEFT JOIN usuarios u ON l.usuario_id = u.id
            WHERE l.igreja_id = ?
            ORDER BY l.data_hora DESC
            LIMIT ?
        ''', (igreja_id, limite))
        return [dict(row) for row in cursor.fetchall()]

def get_pessoas_lista():
    """Retorna lista de pessoas para vincular a usuário"""
    igreja_id = get_igreja_id()
    if not igreja_id:
        return []
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, nome, email
            FROM pessoas
            WHERE igreja_id = ? AND (ativo IS NULL OR ativo = 1)
            ORDER BY nome
        ''', (igreja_id,))
        return [dict(row) for row in cursor.fetchall()]

def exportar_dados_pessoa(pessoa_id: int):
    """Exporta todos os dados de uma pessoa (LGPD)"""
    igreja_id = get_igreja_id()
    if not igreja_id:
        return None
    
    dados = {}
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Dados pessoais
        cursor.execute('SELECT * FROM pessoas WHERE id = ? AND igreja_id = ?', 
                      (pessoa_id, igreja_id))
        dados['dados_pessoais'] = dict(cursor.fetchone()) if cursor.fetchone() else {}
        
        # Participação em ministérios
        cursor.execute('''
            SELECT m.nome, mp.funcao, mp.data_entrada
            FROM membros_ministerio mp
            JOIN ministerios m ON mp.ministerio_id = m.id
            WHERE mp.pessoa_id = ?
        ''', (pessoa_id,))
        dados['ministerios'] = [dict(row) for row in cursor.fetchall()]
        
        # Participação em células
        cursor.execute('''
            SELECT c.nome, mc.data_entrada
            FROM membros_celula mc
            JOIN celulas c ON mc.celula_id = c.id
            WHERE mc.pessoa_id = ?
        ''', (pessoa_id,))
        dados['celulas'] = [dict(row) for row in cursor.fetchall()]
        
        # Doações (sem valores específicos, apenas totais)
        cursor.execute('''
            SELECT tipo, COUNT(*) as quantidade, SUM(valor) as total
            FROM doacoes
            WHERE pessoa_id = ?
            GROUP BY tipo
        ''', (pessoa_id,))
        dados['doacoes_resumo'] = [dict(row) for row in cursor.fetchall()]
    
    return dados

def anonimizar_pessoa(pessoa_id: int):
    """Anonimiza os dados de uma pessoa (LGPD - Direito ao esquecimento)"""
    igreja_id = get_igreja_id()
    if not igreja_id:
        return False
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Anonimizar dados pessoais
        cursor.execute('''
            UPDATE pessoas 
            SET nome = 'Usuário Anonimizado',
                email = NULL,
                telefone = NULL,
                celular = NULL,
                data_nascimento = NULL,
                endereco = NULL,
                numero = NULL,
                complemento = NULL,
                bairro = NULL,
                cidade = NULL,
                estado = NULL,
                cep = NULL,
                observacoes = NULL,
                ativo = 0
            WHERE id = ? AND igreja_id = ?
        ''', (pessoa_id, igreja_id))
        
        # Anonimizar doações
        cursor.execute('''
            UPDATE doacoes SET pessoa_id = NULL, anonimo = 1
            WHERE pessoa_id = ?
        ''', (pessoa_id,))
        
        return True

# ========================================
# RENDERIZAÇÃO DA INTERFACE
# ========================================

def render_meu_perfil():
    """Renderiza configurações do perfil do usuário"""
    st.subheader("👤 Meu Perfil")
    
    usuario = get_usuario_atual()
    if not usuario:
        st.error("Usuário não encontrado!")
        return
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Informações do usuário
        st.markdown("### 📋 Informações da Conta")
        
        st.markdown(f"""
        <div style='background: #f8f9fa; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;'>
            <p><strong>Nome:</strong> {usuario['nome']}</p>
            <p><strong>E-mail:</strong> {usuario['email']}</p>
            <p><strong>Perfil:</strong> {PERFIS.get(usuario['perfil'], {}).get('nome', usuario['perfil'])}</p>
            <p><strong>Igreja:</strong> {usuario.get('igreja_nome', 'N/A')}</p>
            <p><strong>Último acesso:</strong> {formatar_data_br(usuario.get('ultimo_acesso')) if usuario.get('ultimo_acesso') else 'N/A'}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Alterar senha
        st.markdown("### 🔐 Alterar Senha")
        
        with st.form("form_alterar_senha"):
            senha_atual = st.text_input("Senha atual", type="password")
            nova_senha = st.text_input("Nova senha", type="password")
            confirmar_senha = st.text_input("Confirmar nova senha", type="password")
            
            if st.form_submit_button("🔄 Alterar Senha", use_container_width=True):
                if not senha_atual or not nova_senha or not confirmar_senha:
                    st.error("Preencha todos os campos!")
                elif nova_senha != confirmar_senha:
                    st.error("As senhas não coincidem!")
                elif len(nova_senha) < 6:
                    st.error("A senha deve ter pelo menos 6 caracteres!")
                elif not verificar_senha(senha_atual, usuario['senha_hash']):
                    st.error("Senha atual incorreta!")
                else:
                    alterar_senha_usuario(usuario['id'], nova_senha)
                    registrar_log(usuario['id'], usuario['igreja_id'], 'alterar_senha', 
                                 'Usuário alterou sua própria senha')
                    st.success("✅ Senha alterada com sucesso!")
                    st.rerun()
    
    with col2:
        # Permissões do perfil
        st.markdown("### 🔑 Minhas Permissões")
        
        perfil_info = PERFIS.get(usuario['perfil'], {})
        permissoes = perfil_info.get('permissoes', [])
        
        if '*' in permissoes:
            st.success("✅ Acesso Total (Administrador)")
        else:
            for perm in permissoes:
                st.write(f"✅ {perm}")

def render_gerenciar_usuarios():
    """Renderiza gerenciamento de usuários"""
    st.subheader("👥 Gerenciar Usuários")
    
    usuario = get_usuario_atual()
    
    # Verificar permissão
    if not tem_permissao(usuario, 'configuracoes.usuarios'):
        st.error("🚫 Você não tem permissão para gerenciar usuários.")
        return
    
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("➕ Novo Usuário", use_container_width=True):
            st.session_state.show_form_usuario = True
    
    # Formulário de novo usuário
    if st.session_state.get('show_form_usuario') or st.session_state.get('usuario_edit'):
        usuario_edit = None
        if st.session_state.get('usuario_edit'):
            usuario_edit = get_usuario_por_id(st.session_state.usuario_edit)
        
        with st.expander("📝 " + ("Editar Usuário" if usuario_edit else "Novo Usuário"), expanded=True):
            with st.form("form_usuario"):
                nome = st.text_input("Nome *", value=usuario_edit.get('nome', '') if usuario_edit else '')
                email = st.text_input("E-mail *", value=usuario_edit.get('email', '') if usuario_edit else '')
                
                col1, col2 = st.columns(2)
                with col1:
                    perfil_opcoes = [(k, v['nome']) for k, v in PERFIS.items()]
                    perfil_atual = usuario_edit.get('perfil', 'secretaria') if usuario_edit else 'secretaria'
                    perfil = st.selectbox("Perfil *", 
                                         options=[p[0] for p in perfil_opcoes],
                                         format_func=lambda x: dict(perfil_opcoes).get(x, x),
                                         index=[p[0] for p in perfil_opcoes].index(perfil_atual) if perfil_atual in [p[0] for p in perfil_opcoes] else 0)
                
                with col2:
                    pessoas = get_pessoas_lista()
                    pessoas_opcoes = [(0, "Não vincular")] + [(p['id'], p['nome']) for p in pessoas]
                    pessoa_atual = usuario_edit.get('pessoa_id', 0) if usuario_edit else 0
                    pessoa_id = st.selectbox("Vincular a pessoa",
                                            options=[p[0] for p in pessoas_opcoes],
                                            format_func=lambda x: dict(pessoas_opcoes).get(x, ''),
                                            index=next((i for i, p in enumerate(pessoas_opcoes) if p[0] == pessoa_atual), 0))
                
                if not usuario_edit:
                    col1, col2 = st.columns(2)
                    with col1:
                        senha = st.text_input("Senha *", type="password")
                    with col2:
                        confirmar_senha = st.text_input("Confirmar senha *", type="password")
                else:
                    ativo = st.checkbox("Usuário ativo", value=usuario_edit.get('ativo', 1) == 1)
                
                col1, col2 = st.columns(2)
                with col1:
                    submit = st.form_submit_button("💾 Salvar", use_container_width=True)
                with col2:
                    if st.form_submit_button("❌ Cancelar", use_container_width=True):
                        st.session_state.show_form_usuario = False
                        st.session_state.usuario_edit = None
                        st.rerun()
                
                if submit:
                    if not nome or not email:
                        st.error("Nome e e-mail são obrigatórios!")
                    elif not usuario_edit and (not senha or senha != confirmar_senha):
                        st.error("As senhas não coincidem!")
                    elif not usuario_edit and len(senha) < 6:
                        st.error("A senha deve ter pelo menos 6 caracteres!")
                    else:
                        dados = {
                            'nome': nome,
                            'email': email,
                            'perfil': perfil,
                            'pessoa_id': pessoa_id if pessoa_id else None
                        }
                        
                        if usuario_edit:
                            dados['ativo'] = 1 if ativo else 0
                            if atualizar_usuario(usuario_edit['id'], dados):
                                registrar_log(usuario['id'], usuario['igreja_id'], 'editar_usuario',
                                            f"Editou usuário: {email}")
                                st.success("✅ Usuário atualizado!")
                                st.session_state.usuario_edit = None
                                st.rerun()
                            else:
                                st.error("Este e-mail já está em uso!")
                        else:
                            dados['senha'] = senha
                            if criar_usuario(dados):
                                registrar_log(usuario['id'], usuario['igreja_id'], 'criar_usuario',
                                            f"Criou usuário: {email}")
                                st.success("✅ Usuário criado!")
                                st.session_state.show_form_usuario = False
                                st.rerun()
                            else:
                                st.error("Este e-mail já está em uso!")
    
    # Lista de usuários
    usuarios = get_usuarios_igreja()
    
    if not usuarios:
        st.info("Nenhum usuário cadastrado.")
        return
    
    # Tabela de usuários
    st.markdown("### 📋 Usuários Cadastrados")
    
    for u in usuarios:
        status_cor = "🟢" if u['ativo'] else "🔴"
        perfil_nome = PERFIS.get(u['perfil'], {}).get('nome', u['perfil'])
        
        col1, col2, col3, col4, col5 = st.columns([3, 3, 2, 1, 1])
        
        with col1:
            st.write(f"{status_cor} **{u['nome']}**")
        with col2:
            st.caption(u['email'])
        with col3:
            st.caption(perfil_nome)
        with col4:
            if st.button("✏️", key=f"edit_usr_{u['id']}", help="Editar"):
                st.session_state.usuario_edit = u['id']
                st.rerun()
        with col5:
            if u['id'] != usuario['id']:  # Não pode resetar própria senha aqui
                if st.button("🔑", key=f"reset_usr_{u['id']}", help="Resetar senha"):
                    st.session_state.reset_senha_usuario = u['id']
        
        st.markdown("<hr style='margin: 0.3rem 0;'>", unsafe_allow_html=True)
    
    # Modal para resetar senha
    if st.session_state.get('reset_senha_usuario'):
        usr_reset = get_usuario_por_id(st.session_state.reset_senha_usuario)
        if usr_reset:
            st.markdown(f"### 🔑 Resetar Senha - {usr_reset['nome']}")
            
            with st.form("form_reset_senha"):
                nova_senha = st.text_input("Nova senha", type="password")
                confirmar = st.text_input("Confirmar senha", type="password")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("🔄 Resetar", use_container_width=True):
                        if nova_senha and nova_senha == confirmar and len(nova_senha) >= 6:
                            alterar_senha_usuario(usr_reset['id'], nova_senha)
                            registrar_log(usuario['id'], usuario['igreja_id'], 'resetar_senha',
                                        f"Resetou senha do usuário: {usr_reset['email']}")
                            st.success("✅ Senha resetada!")
                            st.session_state.reset_senha_usuario = None
                            st.rerun()
                        else:
                            st.error("Senhas não coincidem ou muito curta (mín. 6 caracteres)")
                with col2:
                    if st.form_submit_button("❌ Cancelar", use_container_width=True):
                        st.session_state.reset_senha_usuario = None
                        st.rerun()

def render_dados_igreja():
    """Renderiza configurações da igreja"""
    st.subheader("⛪ Dados da Igreja")
    
    usuario = get_usuario_atual()
    
    # Verificar permissão
    if not tem_permissao(usuario, 'configuracoes.igreja'):
        st.error("🚫 Você não tem permissão para editar os dados da igreja.")
        return
    
    igreja = get_igreja_dados()
    if not igreja:
        st.error("Dados da igreja não encontrados!")
        return
    
    with st.form("form_igreja"):
        st.markdown("### 📋 Informações Básicas")
        
        col1, col2 = st.columns(2)
        with col1:
            nome = st.text_input("Nome da Igreja *", value=igreja.get('nome', ''))
            cnpj = st.text_input("CNPJ", value=igreja.get('cnpj', ''))
            telefone = st.text_input("Telefone", value=igreja.get('telefone', ''))
        
        with col2:
            email = st.text_input("E-mail", value=igreja.get('email', ''))
            st.text_input("Plano", value=igreja.get('plano', 'BASICO'), disabled=True)
            st.text_input("Cadastrado em", 
                         value=formatar_data_br(igreja.get('data_cadastro')) if igreja.get('data_cadastro') else '', 
                         disabled=True)
        
        st.markdown("### 📍 Endereço")
        
        endereco = st.text_input("Endereço", value=igreja.get('endereco', ''))
        
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            cidade = st.text_input("Cidade", value=igreja.get('cidade', ''))
        with col2:
            estado = st.text_input("Estado", value=igreja.get('estado', ''))
        with col3:
            cep = st.text_input("CEP", value=igreja.get('cep', ''))
        
        if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
            if not nome:
                st.error("O nome da igreja é obrigatório!")
            else:
                atualizar_igreja({
                    'nome': nome,
                    'cnpj': cnpj,
                    'endereco': endereco,
                    'cidade': cidade,
                    'estado': estado,
                    'cep': cep,
                    'telefone': telefone,
                    'email': email
                })
                registrar_log(usuario['id'], usuario['igreja_id'], 'editar_igreja',
                            'Atualizou dados da igreja')
                st.success("✅ Dados da igreja atualizados!")
                st.rerun()

def render_logs_acesso():
    """Renderiza logs de acesso do sistema"""
    st.subheader("📊 Logs de Acesso")
    
    usuario = get_usuario_atual()
    
    # Verificar permissão
    if not tem_permissao(usuario, 'configuracoes.logs'):
        st.error("🚫 Você não tem permissão para visualizar os logs.")
        return
    
    st.info("📋 Registro de todas as ações realizadas no sistema (LGPD)")
    
    logs = get_logs_acesso(200)
    
    if not logs:
        st.info("Nenhum log registrado.")
        return
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        acoes = list(set([l['acao'] for l in logs]))
        filtro_acao = st.selectbox("Filtrar por ação", options=['Todas'] + acoes)
    with col2:
        usuarios_log = list(set([l['usuario_nome'] for l in logs if l.get('usuario_nome')]))
        filtro_usuario = st.selectbox("Filtrar por usuário", options=['Todos'] + usuarios_log)
    
    # Aplicar filtros
    logs_filtrados = logs
    if filtro_acao != 'Todas':
        logs_filtrados = [l for l in logs_filtrados if l['acao'] == filtro_acao]
    if filtro_usuario != 'Todos':
        logs_filtrados = [l for l in logs_filtrados if l.get('usuario_nome') == filtro_usuario]
    
    # Mostrar logs
    for log in logs_filtrados[:100]:
        acao_icon = {
            'login': '🔐',
            'logout': '🚪',
            'criar_usuario': '👤',
            'editar_usuario': '✏️',
            'resetar_senha': '🔑',
            'alterar_senha': '🔄',
            'editar_igreja': '⛪',
            'acesso_aconselhamento': '🙏'
        }.get(log['acao'], '📝')
        
        data_hora = formatar_data_br(log['data_hora']) if log.get('data_hora') else 'N/A'
        
        st.markdown(f"""
        <div style='background: #f8f9fa; padding: 0.5rem 1rem; border-radius: 6px; margin-bottom: 0.5rem; border-left: 3px solid #3498db;'>
            <small style='color: #666;'>{data_hora}</small>
            <br>
            <strong>{acao_icon} {log['acao']}</strong> - {log.get('usuario_nome', 'Sistema')}
            <br>
            <small style='color: #888;'>{log.get('detalhes', '')}</small>
        </div>
        """, unsafe_allow_html=True)

def render_lgpd():
    """Renderiza ferramentas LGPD"""
    st.subheader("🔒 Privacidade e LGPD")
    
    usuario = get_usuario_atual()
    
    # Verificar permissão
    if not tem_permissao(usuario, 'configuracoes.lgpd'):
        st.error("🚫 Você não tem permissão para acessar as ferramentas LGPD.")
        return
    
    st.markdown("""
    ### 📋 Lei Geral de Proteção de Dados
    
    Este módulo permite gerenciar os direitos dos titulares de dados conforme a LGPD:
    
    - **Direito de Acesso:** Exportar todos os dados de uma pessoa
    - **Direito ao Esquecimento:** Anonimizar dados de uma pessoa
    - **Portabilidade:** Exportar dados em formato estruturado
    """)
    
    st.markdown("---")
    
    # Selecionar pessoa
    pessoas = get_pessoas_lista()
    pessoas_opcoes = [(0, "Selecione...")] + [(p['id'], f"{p['nome']} ({p.get('email', 'sem email')})") for p in pessoas]
    
    pessoa_id = st.selectbox("Selecione a pessoa",
                            options=[p[0] for p in pessoas_opcoes],
                            format_func=lambda x: dict(pessoas_opcoes).get(x, ''))
    
    if pessoa_id:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📤 Exportar Dados")
            st.write("Exporta todos os dados da pessoa em formato legível.")
            
            if st.button("📥 Gerar Relatório de Dados", use_container_width=True):
                dados = exportar_dados_pessoa(pessoa_id)
                if dados:
                    st.json(dados)
                    registrar_log(usuario['id'], usuario['igreja_id'], 'exportar_dados_lgpd',
                                f"Exportou dados da pessoa ID: {pessoa_id}")
        
        with col2:
            st.markdown("### 🗑️ Anonimizar Dados")
            st.warning("⚠️ Esta ação é irreversível!")
            st.write("Remove todos os dados pessoais identificáveis.")
            
            confirmar = st.checkbox("Confirmo que desejo anonimizar os dados desta pessoa")
            
            if st.button("🗑️ Anonimizar Dados", use_container_width=True, disabled=not confirmar):
                if anonimizar_pessoa(pessoa_id):
                    registrar_log(usuario['id'], usuario['igreja_id'], 'anonimizar_dados_lgpd',
                                f"Anonimizou dados da pessoa ID: {pessoa_id}")
                    st.success("✅ Dados anonimizados com sucesso!")
                    st.rerun()

def render_backup():
    """Renderiza opções de backup"""
    st.subheader("💾 Backup e Restauração")
    
    usuario = get_usuario_atual()
    
    # Verificar permissão
    if not tem_permissao(usuario, 'configuracoes.backup'):
        st.error("🚫 Você não tem permissão para gerenciar backups.")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📥 Exportar Backup")
        st.write("Exporta todos os dados da igreja em formato SQL.")
        
        if st.button("📥 Gerar Backup", use_container_width=True):
            st.info("🔄 Funcionalidade em desenvolvimento...")
            # TODO: Implementar exportação de backup
    
    with col2:
        st.markdown("### 📤 Restaurar Backup")
        st.warning("⚠️ Esta ação substituirá todos os dados atuais!")
        
        arquivo = st.file_uploader("Selecione o arquivo de backup", type=['sql', 'sqlite'])
        
        if arquivo:
            st.info("🔄 Funcionalidade em desenvolvimento...")
            # TODO: Implementar restauração de backup

# ========================================
# RELATÓRIOS FINANCEIROS (ADMIN)
# ========================================

def get_dados_financeiros_periodo(data_inicio: date, data_fim: date):
    """Retorna dados financeiros de um período"""
    igreja_id = get_igreja_id()
    if not igreja_id:
        return []
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT d.*, p.nome as pessoa_nome
            FROM doacoes d
            LEFT JOIN pessoas p ON d.pessoa_id = p.id
            WHERE d.igreja_id = ? AND date(d.data) BETWEEN ? AND ?
            ORDER BY d.data DESC
        ''', (igreja_id, data_inicio, data_fim))
        return [dict(row) for row in cursor.fetchall()]

def get_resumo_mensal(ano: int):
    """Retorna resumo mensal do ano"""
    igreja_id = get_igreja_id()
    if not igreja_id:
        return []
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                strftime('%m', data) as mes,
                tipo,
                SUM(valor) as total,
                COUNT(*) as quantidade
            FROM doacoes
            WHERE igreja_id = ? AND strftime('%Y', data) = ?
            GROUP BY strftime('%m', data), tipo
            ORDER BY mes
        ''', (igreja_id, str(ano)))
        return [dict(row) for row in cursor.fetchall()]

def get_top_contribuintes(ano: int, limite: int = 10):
    """Retorna os maiores contribuintes do ano"""
    igreja_id = get_igreja_id()
    if not igreja_id:
        return []
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                p.nome,
                SUM(d.valor) as total,
                COUNT(*) as quantidade,
                GROUP_CONCAT(DISTINCT d.tipo) as tipos
            FROM doacoes d
            JOIN pessoas p ON d.pessoa_id = p.id
            WHERE d.igreja_id = ? AND strftime('%Y', d.data) = ? AND d.anonimo = 0
            GROUP BY d.pessoa_id
            ORDER BY total DESC
            LIMIT ?
        ''', (igreja_id, str(ano), limite))
        return [dict(row) for row in cursor.fetchall()]

def get_comparativo_anual():
    """Retorna comparativo entre anos"""
    igreja_id = get_igreja_id()
    if not igreja_id:
        return []
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                strftime('%Y', data) as ano,
                tipo,
                SUM(valor) as total,
                COUNT(*) as quantidade
            FROM doacoes
            WHERE igreja_id = ?
            GROUP BY strftime('%Y', data), tipo
            ORDER BY ano DESC
        ''', (igreja_id,))
        return [dict(row) for row in cursor.fetchall()]

def get_estatisticas_dizimistas(ano: int):
    """Retorna estatísticas de dizimistas"""
    igreja_id = get_igreja_id()
    if not igreja_id:
        return {}
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Total de membros ativos
        cursor.execute('''
            SELECT COUNT(*) FROM pessoas 
            WHERE igreja_id = ? AND (ativo IS NULL OR ativo = 1)
            AND status IN ('membro', 'dizimista', 'lider', 'obreiro', 'diacono', 
                          'presbitero', 'evangelista', 'missionario', 'pastor_auxiliar', 'pastor', 'apostolo')
        ''', (igreja_id,))
        total_membros = cursor.fetchone()[0]
        
        # Dizimistas ativos no ano (que deram pelo menos um dízimo)
        cursor.execute('''
            SELECT COUNT(DISTINCT pessoa_id) FROM doacoes
            WHERE igreja_id = ? AND tipo = 'Dízimo' AND strftime('%Y', data) = ?
            AND pessoa_id IS NOT NULL
        ''', (igreja_id, str(ano)))
        dizimistas_ativos = cursor.fetchone()[0]
        
        # Média de dízimo
        cursor.execute('''
            SELECT AVG(valor) FROM doacoes
            WHERE igreja_id = ? AND tipo = 'Dízimo' AND strftime('%Y', data) = ?
        ''', (igreja_id, str(ano)))
        media_dizimo = cursor.fetchone()[0] or 0
        
        # Dizimistas fiéis (todos os meses)
        cursor.execute('''
            SELECT pessoa_id, COUNT(DISTINCT strftime('%m', data)) as meses
            FROM doacoes
            WHERE igreja_id = ? AND tipo = 'Dízimo' AND strftime('%Y', data) = ?
            AND pessoa_id IS NOT NULL
            GROUP BY pessoa_id
            HAVING meses >= 10
        ''', (igreja_id, str(ano)))
        dizimistas_fieis = len(cursor.fetchall())
        
        return {
            'total_membros': total_membros,
            'dizimistas_ativos': dizimistas_ativos,
            'media_dizimo': media_dizimo,
            'dizimistas_fieis': dizimistas_fieis,
            'percentual_dizimistas': (dizimistas_ativos / total_membros * 100) if total_membros > 0 else 0
        }

def render_relatorios_financeiros():
    """Renderiza relatórios financeiros detalhados (Admin)"""
    st.subheader("📈 Relatórios Financeiros")
    
    usuario = get_usuario_atual()
    
    # Apenas admin
    if usuario.get('perfil') != 'ADMIN':
        st.error("🚫 Apenas administradores podem acessar os relatórios financeiros.")
        return
    
    # Seleção de período
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        ano_atual = date.today().year
        ano = st.selectbox("Ano", options=list(range(ano_atual, ano_atual - 5, -1)), index=0)
    
    with col2:
        meses = ['Todos', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        mes_selecionado = st.selectbox("Mês", options=meses, index=0)
    
    # Definir período
    if mes_selecionado == 'Todos':
        data_inicio = date(ano, 1, 1)
        data_fim = date(ano, 12, 31)
    else:
        mes_num = meses.index(mes_selecionado)
        data_inicio = date(ano, mes_num, 1)
        if mes_num == 12:
            data_fim = date(ano, 12, 31)
        else:
            data_fim = date(ano, mes_num + 1, 1) - timedelta(days=1)
    
    # Tabs de relatórios
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Visão Geral", "📈 Gráficos", "👥 Contribuintes", "📋 Detalhado"])
    
    with tab1:
        render_visao_geral_financeiro(ano, data_inicio, data_fim)
    
    with tab2:
        render_graficos_financeiros(ano)
    
    with tab3:
        render_analise_contribuintes(ano)
    
    with tab4:
        render_relatorio_detalhado(data_inicio, data_fim)

def render_visao_geral_financeiro(ano: int, data_inicio: date, data_fim: date):
    """Renderiza visão geral financeira"""
    st.markdown("### 💰 Resumo Financeiro")
    
    dados = get_dados_financeiros_periodo(data_inicio, data_fim)
    
    if not dados:
        st.info("Nenhum dado financeiro encontrado para o período.")
        return
    
    # Calcular totais por tipo
    totais = {}
    for d in dados:
        tipo = d['tipo']
        if tipo not in totais:
            totais[tipo] = {'valor': 0, 'quantidade': 0}
        totais[tipo]['valor'] += d['valor']
        totais[tipo]['quantidade'] += 1
    
    # Métricas principais
    total_geral = sum([t['valor'] for t in totais.values()])
    total_dizimos = totais.get('Dízimo', {}).get('valor', 0)
    total_ofertas = totais.get('Oferta', {}).get('valor', 0)
    total_campanhas = totais.get('Campanha', {}).get('valor', 0)
    
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric("💵 Total Geral", f"R$ {total_geral:,.2f}")
    col2.metric("🙏 Dízimos", f"R$ {total_dizimos:,.2f}", 
                f"{(total_dizimos/total_geral*100):.1f}%" if total_geral > 0 else "0%")
    col3.metric("💝 Ofertas", f"R$ {total_ofertas:,.2f}",
                f"{(total_ofertas/total_geral*100):.1f}%" if total_geral > 0 else "0%")
    col4.metric("🎯 Campanhas", f"R$ {total_campanhas:,.2f}",
                f"{(total_campanhas/total_geral*100):.1f}%" if total_geral > 0 else "0%")
    
    st.markdown("---")
    
    # Estatísticas de dizimistas
    st.markdown("### 📊 Estatísticas de Dizimistas")
    
    stats = get_estatisticas_dizimistas(ano)
    
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric("👥 Total de Membros", stats['total_membros'])
    col2.metric("💰 Dizimistas Ativos", stats['dizimistas_ativos'],
                f"{stats['percentual_dizimistas']:.1f}% dos membros")
    col3.metric("⭐ Dizimistas Fiéis", stats['dizimistas_fieis'],
                "10+ meses no ano")
    col4.metric("📈 Média por Dízimo", f"R$ {stats['media_dizimo']:,.2f}")
    
    st.markdown("---")
    
    # Resumo por tipo
    st.markdown("### 📋 Resumo por Tipo de Contribuição")
    
    if totais:
        df_totais = pd.DataFrame([
            {
                'Tipo': tipo,
                'Quantidade': dados['quantidade'],
                'Valor Total': f"R$ {dados['valor']:,.2f}",
                'Média': f"R$ {dados['valor']/dados['quantidade']:,.2f}" if dados['quantidade'] > 0 else "R$ 0,00",
                'Percentual': f"{dados['valor']/total_geral*100:.1f}%" if total_geral > 0 else "0%"
            }
            for tipo, dados in totais.items()
        ])
        st.dataframe(df_totais, use_container_width=True, hide_index=True)

def render_graficos_financeiros(ano: int):
    """Renderiza gráficos financeiros"""
    st.markdown("### 📈 Análise Gráfica")
    
    dados_mensais = get_resumo_mensal(ano)
    
    if not dados_mensais:
        st.info("Nenhum dado encontrado para gerar gráficos.")
        return
    
    # Preparar dados para gráficos
    meses_nome = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
    
    # Organizar dados por mês e tipo
    dados_por_mes = {m: {} for m in range(1, 13)}
    for d in dados_mensais:
        mes = int(d['mes'])
        dados_por_mes[mes][d['tipo']] = d['total']
    
    # Gráfico de linha - Evolução mensal
    st.markdown("#### 📊 Evolução Mensal")
    
    tipos = list(set([d['tipo'] for d in dados_mensais]))
    
    fig_linha = go.Figure()
    
    cores = {
        'Dízimo': '#3498db',
        'Oferta': '#2ecc71',
        'Campanha': '#e74c3c',
        'Missões': '#9b59b6',
        'Construção': '#f39c12',
        'Outro': '#95a5a6'
    }
    
    for tipo in tipos:
        valores = [dados_por_mes[m].get(tipo, 0) for m in range(1, 13)]
        fig_linha.add_trace(go.Scatter(
            x=meses_nome,
            y=valores,
            mode='lines+markers',
            name=tipo,
            line=dict(color=cores.get(tipo, '#666666'), width=3),
            marker=dict(size=8)
        ))
    
    fig_linha.update_layout(
        title=f'Evolução das Contribuições - {ano}',
        xaxis_title='Mês',
        yaxis_title='Valor (R$)',
        hovermode='x unified',
        template='plotly_white',
        height=400
    )
    
    st.plotly_chart(fig_linha, use_container_width=True)
    
    # Gráficos lado a lado
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🥧 Distribuição por Tipo")
        
        totais_tipo = {}
        for d in dados_mensais:
            if d['tipo'] not in totais_tipo:
                totais_tipo[d['tipo']] = 0
            totais_tipo[d['tipo']] += d['total']
        
        fig_pizza = px.pie(
            values=list(totais_tipo.values()),
            names=list(totais_tipo.keys()),
            color=list(totais_tipo.keys()),
            color_discrete_map=cores,
            hole=0.4
        )
        fig_pizza.update_layout(height=350)
        st.plotly_chart(fig_pizza, use_container_width=True)
    
    with col2:
        st.markdown("#### 📊 Total Mensal")
        
        totais_mes = [sum(dados_por_mes[m].values()) for m in range(1, 13)]
        
        fig_barras = px.bar(
            x=meses_nome,
            y=totais_mes,
            color_discrete_sequence=['#3498db']
        )
        fig_barras.update_layout(
            xaxis_title='Mês',
            yaxis_title='Total (R$)',
            height=350,
            showlegend=False
        )
        st.plotly_chart(fig_barras, use_container_width=True)
    
    # Comparativo anual
    st.markdown("---")
    st.markdown("#### 📈 Comparativo Anual")
    
    dados_anuais = get_comparativo_anual()
    
    if dados_anuais:
        # Agrupar por ano
        anos_dados = {}
        for d in dados_anuais:
            ano_d = d['ano']
            if ano_d not in anos_dados:
                anos_dados[ano_d] = 0
            anos_dados[ano_d] += d['total']
        
        fig_anual = px.bar(
            x=list(anos_dados.keys()),
            y=list(anos_dados.values()),
            color_discrete_sequence=['#2ecc71']
        )
        fig_anual.update_layout(
            xaxis_title='Ano',
            yaxis_title='Total (R$)',
            height=300
        )
        st.plotly_chart(fig_anual, use_container_width=True)

def render_analise_contribuintes(ano: int):
    """Renderiza análise de contribuintes"""
    st.markdown("### 👥 Análise de Contribuintes")
    
    # Top contribuintes
    st.markdown("#### 🏆 Maiores Contribuintes do Ano")
    
    top = get_top_contribuintes(ano, 15)
    
    if not top:
        st.info("Nenhum contribuinte encontrado.")
        return
    
    # Tabela de ranking
    df_top = pd.DataFrame([
        {
            'Posição': f"🥇 {i+1}" if i < 3 else f"{i+1}º",
            'Nome': c['nome'],
            'Total': f"R$ {c['total']:,.2f}",
            'Contribuições': c['quantidade'],
            'Tipos': c['tipos']
        }
        for i, c in enumerate(top)
    ])
    
    st.dataframe(df_top, use_container_width=True, hide_index=True)
    
    # Gráfico de barras dos top 10
    st.markdown("#### 📊 Top 10 Contribuintes")
    
    fig_top = px.bar(
        x=[c['nome'][:20] for c in top[:10]],
        y=[c['total'] for c in top[:10]],
        color=[c['total'] for c in top[:10]],
        color_continuous_scale='Blues'
    )
    fig_top.update_layout(
        xaxis_title='Contribuinte',
        yaxis_title='Total (R$)',
        height=400,
        showlegend=False
    )
    st.plotly_chart(fig_top, use_container_width=True)
    
    # Análise de fidelidade
    st.markdown("---")
    st.markdown("#### ⭐ Análise de Fidelidade (Dizimistas)")
    
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Distribuição por frequência
        cursor.execute('''
            SELECT 
                pessoa_id,
                p.nome,
                COUNT(DISTINCT strftime('%m', d.data)) as meses
            FROM doacoes d
            JOIN pessoas p ON d.pessoa_id = p.id
            WHERE d.igreja_id = ? AND d.tipo = 'Dízimo' AND strftime('%Y', d.data) = ?
            AND d.pessoa_id IS NOT NULL
            GROUP BY d.pessoa_id
            ORDER BY meses DESC
        ''', (igreja_id, str(ano)))
        
        fidelidade = [dict(row) for row in cursor.fetchall()]
    
    if fidelidade:
        # Categorizar
        categorias = {
            'Fiéis (10-12 meses)': len([f for f in fidelidade if f['meses'] >= 10]),
            'Regulares (6-9 meses)': len([f for f in fidelidade if 6 <= f['meses'] < 10]),
            'Ocasionais (3-5 meses)': len([f for f in fidelidade if 3 <= f['meses'] < 6]),
            'Esporádicos (1-2 meses)': len([f for f in fidelidade if f['meses'] < 3])
        }
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig_fidelidade = px.pie(
                values=list(categorias.values()),
                names=list(categorias.keys()),
                color_discrete_sequence=['#27ae60', '#3498db', '#f39c12', '#e74c3c']
            )
            fig_fidelidade.update_layout(height=300)
            st.plotly_chart(fig_fidelidade, use_container_width=True)
        
        with col2:
            st.markdown("**Distribuição:**")
            for cat, qtd in categorias.items():
                percent = qtd / len(fidelidade) * 100 if fidelidade else 0
                st.write(f"• {cat}: **{qtd}** ({percent:.1f}%)")

def render_relatorio_detalhado(data_inicio: date, data_fim: date):
    """Renderiza relatório detalhado"""
    st.markdown("### 📋 Relatório Detalhado")
    
    dados = get_dados_financeiros_periodo(data_inicio, data_fim)
    
    if not dados:
        st.info("Nenhum dado encontrado para o período.")
        return
    
    # Filtros
    col1, col2 = st.columns(2)
    
    with col1:
        tipos = ['Todos'] + list(set([d['tipo'] for d in dados]))
        tipo_filtro = st.selectbox("Filtrar por tipo", options=tipos, key="filtro_tipo_det")
    
    with col2:
        formas = ['Todas'] + list(set([d.get('forma_pagamento', 'N/A') for d in dados if d.get('forma_pagamento')]))
        forma_filtro = st.selectbox("Forma de pagamento", options=formas, key="filtro_forma_det")
    
    # Aplicar filtros
    dados_filtrados = dados
    if tipo_filtro != 'Todos':
        dados_filtrados = [d for d in dados_filtrados if d['tipo'] == tipo_filtro]
    if forma_filtro != 'Todas':
        dados_filtrados = [d for d in dados_filtrados if d.get('forma_pagamento') == forma_filtro]
    
    # Totais
    total = sum([d['valor'] for d in dados_filtrados])
    st.metric("Total Filtrado", f"R$ {total:,.2f}", f"{len(dados_filtrados)} registros")
    
    # Tabela
    df = pd.DataFrame([
        {
            'Data': formatar_data_br(d['data']),
            'Tipo': d['tipo'],
            'Valor': f"R$ {d['valor']:,.2f}",
            'Contribuinte': d.get('pessoa_nome', 'Anônimo') if not d.get('anonimo') else 'Anônimo',
            'Forma Pgto': d.get('forma_pagamento', 'N/A'),
            'Referência': d.get('referencia', '')[:30] if d.get('referencia') else ''
        }
        for d in dados_filtrados
    ])
    
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Exportar
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📥 Exportar para Excel", use_container_width=True):
            # Criar DataFrame para exportação
            df_export = pd.DataFrame([
                {
                    'Data': d['data'],
                    'Tipo': d['tipo'],
                    'Valor': d['valor'],
                    'Contribuinte': d.get('pessoa_nome', 'Anônimo') if not d.get('anonimo') else 'Anônimo',
                    'Forma Pagamento': d.get('forma_pagamento', ''),
                    'Referência': d.get('referencia', ''),
                    'Observações': d.get('observacoes', '')
                }
                for d in dados_filtrados
            ])
            
            # Converter para Excel
            import io
            buffer = io.BytesIO()
            df_export.to_excel(buffer, index=False, engine='openpyxl')
            buffer.seek(0)
            
            st.download_button(
                label="📥 Baixar Excel",
                data=buffer,
                file_name=f"relatorio_financeiro_{data_inicio}_{data_fim}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

def render_configuracoes():
    """Função principal do módulo de configurações"""
    usuario = get_usuario_atual()
    
    if not usuario:
        st.error("Você precisa estar logado para acessar as configurações.")
        return
    
    # Tabs de configuração
    tabs_disponiveis = ["👤 Meu Perfil"]
    
    if tem_permissao(usuario, 'configuracoes.usuarios'):
        tabs_disponiveis.append("👥 Usuários")
    
    if tem_permissao(usuario, 'configuracoes.igreja'):
        tabs_disponiveis.append("⛪ Igreja")
    
    # Relatórios financeiros - apenas para ADMIN
    if usuario.get('perfil') == 'ADMIN':
        tabs_disponiveis.append("📈 Relatórios Financeiros")
    
    if tem_permissao(usuario, 'configuracoes.logs'):
        tabs_disponiveis.append("📊 Logs")
    
    if tem_permissao(usuario, 'configuracoes.lgpd'):
        tabs_disponiveis.append("🔒 LGPD")
    
    if tem_permissao(usuario, 'configuracoes.backup'):
        tabs_disponiveis.append("💾 Backup")
    
    tabs = st.tabs(tabs_disponiveis)
    
    tab_index = 0
    
    with tabs[tab_index]:
        render_meu_perfil()
    tab_index += 1
    
    if tem_permissao(usuario, 'configuracoes.usuarios'):
        with tabs[tab_index]:
            render_gerenciar_usuarios()
        tab_index += 1
    
    if tem_permissao(usuario, 'configuracoes.igreja'):
        with tabs[tab_index]:
            render_dados_igreja()
        tab_index += 1
    
    # Relatórios financeiros - apenas para ADMIN
    if usuario.get('perfil') == 'ADMIN':
        with tabs[tab_index]:
            render_relatorios_financeiros()
        tab_index += 1
    
    if tem_permissao(usuario, 'configuracoes.logs'):
        with tabs[tab_index]:
            render_logs_acesso()
        tab_index += 1
    
    if tem_permissao(usuario, 'configuracoes.lgpd'):
        with tabs[tab_index]:
            render_lgpd()
        tab_index += 1
    
    if tem_permissao(usuario, 'configuracoes.backup'):
        with tabs[tab_index]:
            render_backup()
