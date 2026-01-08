"""
CRM Igreja - Sistema de Gestão para Igrejas
Aplicativo principal Streamlit
"""
import streamlit as st
from pathlib import Path
import sys

# Adicionar o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

from database.db import init_database, criar_igreja_demo
from modules.auth import login_page, get_usuario_atual, sidebar_usuario, tem_permissao
from modules.dashboard import render_dashboard
from modules.pessoas import render_pessoas
from modules.visitantes import render_visitantes
from modules.ministerios import render_ministerios_celulas
from modules.comunicacao import render_comunicacao
from modules.eventos import render_eventos
from modules.financeiro import render_financeiro
from modules.aconselhamento import render_aconselhamento
from modules.configuracoes import render_configuracoes
# Novos módulos
from modules.escalas import render_escalas
from modules.discipulado import render_discipulado
from modules.agenda import render_agenda
from modules.mural import render_mural
from modules.metas import render_metas
from modules.notificacoes import render_notificacoes, render_badge_notificacoes
from modules.galeria import render as render_galeria
from modules.relatorios_pdf import render_relatorios

# Configuração da página
st.set_page_config(
    page_title="CRM Igreja",
    page_icon="⛪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado para interface mobile-first e moderna
st.markdown("""
    <style>
    /* Reset e base */
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 1.5rem;
        max-width: 1400px;
    }
    
    /* Sidebar - Ajustes de tamanho e espaçamento */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    }
    
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 0.5rem !important;
        padding-bottom: 0.5rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }
    
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.3rem !important;
    }
    
    [data-testid="stSidebar"] .stMarkdown {
        color: white;
    }
    
    [data-testid="stSidebar"] .stMarkdown p {
        margin-bottom: 0.3rem;
    }
    
    /* Botões do sidebar */
    [data-testid="stSidebar"] .stButton > button {
        font-size: 0.85rem;
        padding: 0.4rem 0.5rem;
        margin: 0.15rem 0;
        border-radius: 6px;
        background-color: rgba(255,255,255,0.1);
        color: white;
        border: 1px solid rgba(255,255,255,0.2);
    }
    
    [data-testid="stSidebar"] .stButton > button:hover {
        background-color: rgba(255,255,255,0.2);
        border-color: rgba(255,255,255,0.4);
    }
    
    /* Botões */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    /* Cards e containers */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    
    /* Inputs */
    .stTextInput > div > div > input {
        border-radius: 8px;
    }
    
    .stSelectbox > div > div {
        border-radius: 8px;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
    }
    
    /* Formulários */
    .stForm {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 12px;
    }
    
    /* Métricas */
    [data-testid="metric-container"] {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    
    /* Menu lateral personalizado */
    .sidebar-menu-item {
        padding: 0.75rem 1rem;
        margin: 0.25rem 0;
        border-radius: 8px;
        cursor: pointer;
        transition: background 0.2s;
    }
    
    .sidebar-menu-item:hover {
        background: rgba(255,255,255,0.1);
    }
    
    .sidebar-menu-item.active {
        background: rgba(255,255,255,0.2);
    }
    
    /* Esconder menu hamburguer em desktop */
    @media (min-width: 768px) {
        [data-testid="stSidebarNav"] {
            display: none;
        }
    }
    
    /* Responsivo mobile */
    @media (max-width: 768px) {
        .main .block-container {
            padding: 1rem;
        }
        
        [data-testid="column"] {
            padding: 0.25rem;
        }
    }
    </style>
""", unsafe_allow_html=True)

def init_app():
    """Inicializa o aplicativo"""
    # Inicializar banco de dados
    init_database()
    
    # Criar dados demo se não existirem
    criar_igreja_demo()

def render_sidebar():
    """Renderiza a sidebar com menu de navegação"""
    usuario = get_usuario_atual()
    
    st.sidebar.markdown("""
        <div style='text-align: center; padding: 0.3rem 0; border-bottom: 1px solid rgba(255,255,255,0.1); margin-bottom: 0.3rem;'>
            <div style='color: white; font-size: 1.1rem; font-weight: bold; margin: 0;'>⛪ CRM Igreja</div>
            <div style='color: rgba(255,255,255,0.6); font-size: 0.7rem;'>Sistema de Gestão</div>
        </div>
    """, unsafe_allow_html=True)
    
    # Informações do usuário
    sidebar_usuario()
    
    st.sidebar.markdown("---")
    
    # Menu de navegação
    menu_items = [
        ("📊 Dashboard", "dashboard", "dashboard.ver"),
        ("👥 Pessoas", "pessoas", "pessoas.ver"),
        ("👋 Visitantes", "visitantes", "visitantes.ver"),
        ("⛪ Ministérios & Células", "ministerios", "ministerios.ver"),
        ("📅 Eventos", "eventos", "eventos.ver"),
        ("📆 Agenda/Calendário", "agenda", "eventos.ver"),
        ("📋 Escalas", "escalas", "ministerios.ver"),
        ("📚 Discipulado", "discipulado", "pessoas.ver"),
        ("📌 Mural", "mural", "comunicacao.ver"),
        ("🎯 Metas e OKRs", "metas", "dashboard.ver"),
        ("💬 Comunicação", "comunicacao", "comunicacao.ver"),
        ("💰 Financeiro", "financeiro", "doacoes.ver"),
        ("🙏 Aconselhamento", "aconselhamento", "aconselhamento.ver"),
        ("📸 Galeria", "galeria", "eventos.ver"),
        ("📄 Relatórios PDF", "relatorios", "dashboard.ver"),
        (render_badge_notificacoes(), "notificacoes", None),  # Central de notificações
        ("⚙️ Configurações", "configuracoes", None),  # Disponível para todos
    ]
    
    # Inicializar página atual
    if 'pagina_atual' not in st.session_state:
        st.session_state.pagina_atual = 'dashboard'
    
    for label, key, permissao in menu_items:
        if permissao is None or tem_permissao(usuario, permissao):
            if st.sidebar.button(label, key=f"menu_{key}", use_container_width=True):
                st.session_state.pagina_atual = key
                # Limpar estados de visualização
                for state_key in list(st.session_state.keys()):
                    if state_key.endswith('_view') or state_key.endswith('_edit') or state_key.startswith('show_form'):
                        del st.session_state[state_key]
                st.rerun()
    
    # Rodapé
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
        <div style='text-align: center; color: rgba(255,255,255,0.5); font-size: 0.7rem; line-height: 1.3;'>
            <p style='margin: 0.3rem 0;'>v2.0</p>
            <p style='margin: 0.3rem 0;'>© 2024</p>
        </div>
    """, unsafe_allow_html=True)

def main():
    """Função principal"""
    
    # Inicializar app
    init_app()
    
    # Verificar autenticação
    if not get_usuario_atual():
        login_page()
        return
    
    # Renderizar sidebar
    render_sidebar()
    
    # Renderizar página atual
    pagina = st.session_state.get('pagina_atual', 'dashboard')
    
    if pagina == 'dashboard':
        render_dashboard()
    elif pagina == 'pessoas':
        render_pessoas()
    elif pagina == 'visitantes':
        render_visitantes()
    elif pagina == 'ministerios':
        render_ministerios_celulas()
    elif pagina == 'comunicacao':
        render_comunicacao()
    elif pagina == 'eventos':
        render_eventos()
    elif pagina == 'financeiro':
        render_financeiro()
    elif pagina == 'aconselhamento':
        render_aconselhamento()
    elif pagina == 'configuracoes':
        render_configuracoes()
    elif pagina == 'escalas':
        render_escalas()
    elif pagina == 'discipulado':
        render_discipulado()
    elif pagina == 'agenda':
        render_agenda()
    elif pagina == 'mural':
        render_mural()
    elif pagina == 'metas':
        render_metas()
    elif pagina == 'notificacoes':
        render_notificacoes()
    elif pagina == 'galeria':
        render_galeria()
    elif pagina == 'relatorios':
        render_relatorios()
    else:
        render_dashboard()

if __name__ == "__main__":
    main()
