"""
Configurações do CRM Igreja
"""
import os
from pathlib import Path
from datetime import datetime, date

# Função para formatar datas no padrão brasileiro
def formatar_data_br(data) -> str:
    """Formata uma data para o padrão brasileiro dd/mm/yyyy"""
    if data is None:
        return ""
    if isinstance(data, str):
        if not data:
            return ""
        try:
            # Tentar converter de yyyy-mm-dd para dd/mm/yyyy
            if '-' in data:
                partes = data.split(' ')[0].split('-')
                if len(partes) == 3:
                    return f"{partes[2]}/{partes[1]}/{partes[0]}"
        except:
            pass
        return data
    if isinstance(data, (datetime, date)):
        return data.strftime("%d/%m/%Y")
    return str(data)

# Diretórios
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"

# Criar diretórios se não existirem
DATA_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)

# Banco de dados
DATABASE_PATH = DATA_DIR / "crm_igreja.db"

# Configurações de segurança
SECRET_KEY = os.getenv("SECRET_KEY", "sua-chave-secreta-aqui-mude-em-producao")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "chave-criptografia-32bytes!")

# Perfis de usuário (RBAC)
PERFIS = {
    "ADMIN": {
        "nome": "Administrador",
        "permissoes": ["*"]  # Acesso total
    },
    "PASTOR": {
        "nome": "Pastor",
        "permissoes": [
            "pessoas.ver", "pessoas.editar",
            "visitantes.ver", "visitantes.editar",
            "ministerios.ver", "ministerios.editar",
            "celulas.ver", "celulas.editar",
            "eventos.ver", "eventos.editar",
            "comunicacao.ver", "comunicacao.enviar",
            "aconselhamento.ver", "aconselhamento.editar",
            "dashboard.ver",
            "relatorios.ver",
            "configuracoes.usuarios", "configuracoes.igreja", "configuracoes.logs"
        ]
    },
    "LIDER": {
        "nome": "Líder de Ministério/Célula",
        "permissoes": [
            "pessoas.ver",
            "visitantes.ver",
            "ministerios.ver",
            "celulas.ver", "celulas.editar_proprio",
            "eventos.ver",
            "comunicacao.ver", "comunicacao.enviar_grupo",
            "dashboard.ver_proprio"
        ]
    },
    "SECRETARIA": {
        "nome": "Secretaria",
        "permissoes": [
            "pessoas.ver", "pessoas.editar",
            "visitantes.ver", "visitantes.editar",
            "ministerios.ver",
            "celulas.ver",
            "eventos.ver", "eventos.editar",
            "comunicacao.ver", "comunicacao.enviar",
            "relatorios.ver",
            "configuracoes.igreja"
        ]
    },
    "FINANCEIRO": {
        "nome": "Financeiro",
        "permissoes": [
            "pessoas.ver",
            "doacoes.ver", "doacoes.editar",
            "relatorios.financeiro",
            "dashboard.financeiro"
        ]
    }
}

# Status de pessoas (Funil de relacionamento)
STATUS_PESSOA = [
    ("visitante", "Visitante", "#FFA500"),
    ("novo_convertido", "Novo Convertido", "#90EE90"),
    ("em_integracao", "Em Integração", "#87CEEB"),
    ("membro", "Membro", "#4169E1"),
    ("dizimista", "Dizimista", "#2E8B57"),
    ("lider", "Líder", "#9370DB"),
    ("obreiro", "Obreiro", "#6B8E23"),
    ("diacono", "Diácono", "#8B4513"),
    ("presbitero", "Presbítero", "#4682B4"),
    ("evangelista", "Evangelista", "#FF6347"),
    ("missionario", "Missionário", "#20B2AA"),
    ("pastor_auxiliar", "Pastor Auxiliar", "#9932CC"),
    ("pastor", "Pastor", "#800080"),
    ("apostolo", "Apóstolo", "#DAA520"),
    ("inativo", "Inativo", "#808080")
]

# Tipos de evento
TIPOS_EVENTO = [
    "Culto Dominical",
    "Culto de Oração",
    "Célula",
    "Congresso",
    "Conferência",
    "Curso",
    "Batismo",
    "Casamento",
    "Retiro",
    "Outro"
]

# Tipos de doação
TIPOS_DOACAO = [
    "Dízimo",
    "Oferta",
    "Missões",
    "Construção",
    "Ação Social",
    "Outro"
]

# Configurações de comunicação
WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
TWILIO_SID = os.getenv("TWILIO_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN", "")

# Planos SaaS
PLANOS = {
    "BASICO": {
        "nome": "Básico",
        "preco": 99.90,
        "limite_membros": 200,
        "limite_usuarios": 3,
        "recursos": ["pessoas", "visitantes", "celulas", "eventos"]
    },
    "PRO": {
        "nome": "Pro",
        "preco": 199.90,
        "limite_membros": 1000,
        "limite_usuarios": 10,
        "recursos": ["pessoas", "visitantes", "celulas", "eventos", "comunicacao", "doacoes", "relatorios"]
    },
    "PREMIUM": {
        "nome": "Premium",
        "preco": 399.90,
        "limite_membros": -1,  # Ilimitado
        "limite_usuarios": -1,
        "recursos": ["*"],  # Todos
        "multi_campus": True
    }
}
