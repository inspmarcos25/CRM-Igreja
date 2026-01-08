"""
Sistema de Autenticação e Controle de Acesso (RBAC)
"""
import streamlit as st
import bcrypt
from datetime import datetime
from database.db import get_connection
from config.settings import PERFIS

def verificar_senha(senha: str, senha_hash: str) -> bool:
    """Verifica se a senha está correta"""
    return bcrypt.checkpw(senha.encode(), senha_hash.encode())

def hash_senha(senha: str) -> str:
    """Gera hash da senha"""
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()

def autenticar_usuario(email: str, senha: str) -> dict | None:
    """Autentica um usuário e retorna seus dados"""
    # Buscar e verificar usuário
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.*, i.nome as igreja_nome, i.plano as igreja_plano
            FROM usuarios u
            JOIN igrejas i ON u.igreja_id = i.id
            WHERE u.email = ? AND u.ativo = 1 AND i.ativo = 1
        ''', (email,))
        usuario = cursor.fetchone()
        
        if not usuario or not verificar_senha(senha, usuario['senha_hash']):
            return None
        
        usuario_dict = dict(usuario)
    
    # Atualizar último acesso em transação separada
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE usuarios SET ultimo_acesso = ? WHERE id = ?
            ''', (datetime.now(), usuario_dict['id']))
    except Exception as e:
        print(f"Erro ao atualizar ultimo acesso: {e}")
    
    # Registrar log de acesso (não-bloqueante)
    registrar_log(usuario_dict['id'], usuario_dict['igreja_id'], 'login', 'Login realizado com sucesso')
    
    return usuario_dict

def registrar_log(usuario_id: int, igreja_id: int, acao: str, detalhes: str = None, ip: str = None):
    """Registra um log de acesso/ação"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO logs_acesso (usuario_id, igreja_id, acao, detalhes, ip)
                VALUES (?, ?, ?, ?, ?)
            ''', (usuario_id, igreja_id, acao, detalhes, ip))
    except Exception as e:
        # Log falhou, mas não queremos bloquear a operação principal
        print(f"Erro ao registrar log: {e}")

def tem_permissao(usuario: dict, permissao: str) -> bool:
    """Verifica se o usuário tem uma determinada permissão"""
    if not usuario:
        return False
    
    perfil = usuario.get('perfil', '')
    if perfil not in PERFIS:
        return False
    
    permissoes = PERFIS[perfil]['permissoes']
    
    # Admin tem acesso total
    if '*' in permissoes:
        return True
    
    # Verifica permissão específica
    if permissao in permissoes:
        return True
    
    # Verifica permissão parcial (ex: "pessoas" está em "pessoas.ver")
    for p in permissoes:
        if p.startswith(permissao.split('.')[0]):
            return True
    
    return False

def requer_permissao(permissao: str):
    """Decorator para verificar permissão antes de executar função"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not st.session_state.get('usuario'):
                st.error("⚠️ Você precisa estar logado para acessar esta página.")
                st.stop()
            
            if not tem_permissao(st.session_state.usuario, permissao):
                st.error("🚫 Você não tem permissão para acessar esta funcionalidade.")
                st.stop()
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

def login_page():
    """Página de login"""
    st.markdown("""
        <style>
        .login-container {
            max-width: 400px;
            margin: 0 auto;
            padding: 2rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("## 🏛️ CRM Igreja")
        st.markdown("### Entrar no Sistema")
        
        with st.form("login_form"):
            email = st.text_input("📧 E-mail", placeholder="seu@email.com")
            senha = st.text_input("🔒 Senha", type="password", placeholder="Sua senha")
            
            submit = st.form_submit_button("🚀 Entrar", use_container_width=True)
            
            if submit:
                if not email or not senha:
                    st.error("Preencha todos os campos!")
                else:
                    usuario = autenticar_usuario(email, senha)
                    if usuario:
                        st.session_state.usuario = usuario
                        st.session_state.igreja_id = usuario['igreja_id']
                        st.success("✅ Login realizado com sucesso!")
                        st.rerun()
                    else:
                        st.error("❌ E-mail ou senha inválidos!")

        st.caption("Contas são criadas pelo administrador do sistema. Entre em contato para obter acesso.")
        
        st.markdown("---")
        st.markdown("""
            <div style='text-align: center; color: #666; font-size: 0.9rem;'>
                <p>👤 Demo: admin@demo.com</p>
                <p>🔑 Senha: admin123</p>
            </div>
        """, unsafe_allow_html=True)

def logout():
    """Realiza logout do usuário"""
    if st.session_state.get('usuario'):
        registrar_log(
            st.session_state.usuario['id'],
            st.session_state.usuario['igreja_id'],
            'logout',
            'Logout realizado'
        )
    
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def get_usuario_atual() -> dict | None:
    """Retorna o usuário atual logado"""
    return st.session_state.get('usuario')

def get_igreja_id() -> int | None:
    """Retorna o ID da igreja do usuário atual"""
    return st.session_state.get('igreja_id')

def sidebar_usuario():
    """Exibe informações do usuário na sidebar"""
    usuario = get_usuario_atual()
    if usuario:
        perfil_nome = PERFIS.get(usuario['perfil'], {}).get('nome', usuario['perfil'])
        st.sidebar.markdown(f"""
        <div style='padding: 0.3rem 0; font-size: 0.85rem;'>
            <div style='font-weight: bold; color: white;'>👤 {usuario['nome']}</div>
            <div style='color: rgba(255,255,255,0.7); font-size: 0.75rem;'>{perfil_nome}</div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.sidebar.button("🚪 Sair", use_container_width=True):
            logout()
