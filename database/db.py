"""
Configuração e gerenciamento do banco de dados SQLite
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import bcrypt
from cryptography.fernet import Fernet
import base64
import hashlib

from config.settings import DATABASE_PATH, SECRET_KEY

def get_encryption_key():
    """Gera chave de criptografia baseada na SECRET_KEY"""
    key = hashlib.sha256(SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(key)

FERNET = Fernet(get_encryption_key())

def encrypt_data(data: str) -> str:
    """Criptografa dados sensíveis"""
    if not data:
        return data
    return FERNET.encrypt(data.encode()).decode()

def decrypt_data(data: str) -> str:
    """Descriptografa dados sensíveis"""
    if not data:
        return data
    try:
        return FERNET.decrypt(data.encode()).decode()
    except:
        return data

@contextmanager
def get_connection():
    """Context manager para conexão com o banco"""
    conn = sqlite3.connect(DATABASE_PATH, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Habilitar WAL mode para melhor concorrência
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=30000')
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def init_database():
    """Inicializa o banco de dados com todas as tabelas"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # ========================================
        # TABELAS DE AUTENTICAÇÃO E CONTROLE
        # ========================================
        
        # Igreja/Organização (multi-tenant)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS igrejas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                cnpj TEXT,
                endereco TEXT,
                cidade TEXT,
                estado TEXT,
                cep TEXT,
                telefone TEXT,
                email TEXT,
                logo_url TEXT,
                plano TEXT DEFAULT 'BASICO',
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ativo INTEGER DEFAULT 1,
                configuracoes TEXT
            )
        ''')
        
        # Usuários do sistema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                igreja_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                senha_hash TEXT NOT NULL,
                perfil TEXT NOT NULL,
                pessoa_id INTEGER,
                ativo INTEGER DEFAULT 1,
                ultimo_acesso TIMESTAMP,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id),
                FOREIGN KEY (pessoa_id) REFERENCES pessoas(id)
            )
        ''')
        
        # Logs de acesso (LGPD)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs_acesso (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER,
                igreja_id INTEGER,
                acao TEXT NOT NULL,
                detalhes TEXT,
                ip TEXT,
                data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id)
            )
        ''')
        
        # Consentimento LGPD
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS consentimentos_lgpd (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pessoa_id INTEGER NOT NULL,
                tipo_consentimento TEXT NOT NULL,
                aceito INTEGER DEFAULT 0,
                data_consentimento TIMESTAMP,
                ip TEXT,
                texto_consentimento TEXT,
                FOREIGN KEY (pessoa_id) REFERENCES pessoas(id)
            )
        ''')
        
        # ========================================
        # MÓDULO DE PESSOAS (CORE)
        # ========================================
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pessoas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                igreja_id INTEGER NOT NULL,
                
                -- Dados básicos
                nome TEXT NOT NULL,
                email TEXT,
                telefone TEXT,
                celular TEXT,
                data_nascimento DATE,
                genero TEXT,
                estado_civil TEXT,
                foto_url TEXT,
                
                -- Endereço
                endereco TEXT,
                numero TEXT,
                complemento TEXT,
                bairro TEXT,
                cidade TEXT,
                estado TEXT,
                cep TEXT,
                
                -- Dados eclesiásticos
                status TEXT DEFAULT 'visitante',
                data_primeira_visita DATE,
                data_conversao DATE,
                data_batismo DATE,
                data_membresia DATE,
                igreja_anterior TEXT,
                como_conheceu TEXT,
                
                -- Profissional
                profissao TEXT,
                empresa TEXT,
                
                -- Família
                familia_id INTEGER,
                papel_familia TEXT,
                
                -- Controle
                observacoes TEXT,
                dados_sensiveis_criptografados TEXT,
                ativo INTEGER DEFAULT 1,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_atualizacao TIMESTAMP,
                
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id),
                FOREIGN KEY (familia_id) REFERENCES familias(id)
            )
        ''')
        
        # Famílias
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS familias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                igreja_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id)
            )
        ''')
        
        # Tags/Categorias de pessoas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                igreja_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                cor TEXT DEFAULT '#3498db',
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pessoa_tags (
                pessoa_id INTEGER,
                tag_id INTEGER,
                PRIMARY KEY (pessoa_id, tag_id),
                FOREIGN KEY (pessoa_id) REFERENCES pessoas(id),
                FOREIGN KEY (tag_id) REFERENCES tags(id)
            )
        ''')
        
        # ========================================
        # MÓDULO DE VISITANTES & FOLLOW-UP
        # ========================================
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS visitas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pessoa_id INTEGER NOT NULL,
                evento_id INTEGER,
                data_visita DATE NOT NULL,
                tipo_culto TEXT,
                como_conheceu TEXT,
                observacoes TEXT,
                responsavel_recepcao_id INTEGER,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pessoa_id) REFERENCES pessoas(id),
                FOREIGN KEY (evento_id) REFERENCES eventos(id),
                FOREIGN KEY (responsavel_recepcao_id) REFERENCES pessoas(id)
            )
        ''')
        
        # Follow-up de visitantes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS followup (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pessoa_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                status TEXT DEFAULT 'pendente',
                data_prevista DATE,
                data_realizada DATE,
                responsavel_id INTEGER,
                observacoes TEXT,
                resultado TEXT,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pessoa_id) REFERENCES pessoas(id),
                FOREIGN KEY (responsavel_id) REFERENCES pessoas(id)
            )
        ''')
        
        # Fluxos automáticos de follow-up
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fluxos_followup (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                igreja_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                descricao TEXT,
                trigger_evento TEXT,
                dias_apos_trigger INTEGER DEFAULT 0,
                tipo_acao TEXT,
                template_mensagem TEXT,
                ativo INTEGER DEFAULT 1,
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id)
            )
        ''')
        
        # Pedidos de oração dos visitantes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pedidos_oracao (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pessoa_id INTEGER NOT NULL,
                igreja_id INTEGER NOT NULL,
                pedido TEXT NOT NULL,
                data_pedido DATE NOT NULL,
                status TEXT DEFAULT 'ativo',
                data_resposta DATE,
                observacoes TEXT,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pessoa_id) REFERENCES pessoas(id),
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id)
            )
        ''')
        
        # Interesses dos visitantes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interesses_visitante (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pessoa_id INTEGER NOT NULL,
                interesse TEXT NOT NULL,
                data_registro DATE NOT NULL,
                atendido INTEGER DEFAULT 0,
                data_atendimento DATE,
                FOREIGN KEY (pessoa_id) REFERENCES pessoas(id)
            )
        ''')
        
        # ========================================
        # MÓDULO DE MINISTÉRIOS E CÉLULAS
        # ========================================
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ministerios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                igreja_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                descricao TEXT,
                lider_id INTEGER,
                vice_lider_id INTEGER,
                cor TEXT DEFAULT '#3498db',
                icone TEXT,
                ativo INTEGER DEFAULT 1,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id),
                FOREIGN KEY (lider_id) REFERENCES pessoas(id),
                FOREIGN KEY (vice_lider_id) REFERENCES pessoas(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pessoa_ministerios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pessoa_id INTEGER NOT NULL,
                ministerio_id INTEGER NOT NULL,
                funcao TEXT DEFAULT 'membro',
                data_entrada DATE,
                data_saida DATE,
                ativo INTEGER DEFAULT 1,
                FOREIGN KEY (pessoa_id) REFERENCES pessoas(id),
                FOREIGN KEY (ministerio_id) REFERENCES ministerios(id)
            )
        ''')
        
        # Células/Pequenos Grupos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS celulas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                igreja_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                descricao TEXT,
                lider_id INTEGER,
                co_lider_id INTEGER,
                anfitriao_id INTEGER,
                endereco TEXT,
                dia_semana TEXT,
                horario TEXT,
                rede_id INTEGER,
                ativo INTEGER DEFAULT 1,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id),
                FOREIGN KEY (lider_id) REFERENCES pessoas(id),
                FOREIGN KEY (co_lider_id) REFERENCES pessoas(id),
                FOREIGN KEY (anfitriao_id) REFERENCES pessoas(id),
                FOREIGN KEY (rede_id) REFERENCES redes(id)
            )
        ''')
        
        # Redes de células
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS redes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                igreja_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                supervisor_id INTEGER,
                cor TEXT DEFAULT '#3498db',
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id),
                FOREIGN KEY (supervisor_id) REFERENCES pessoas(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pessoa_celulas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pessoa_id INTEGER NOT NULL,
                celula_id INTEGER NOT NULL,
                funcao TEXT DEFAULT 'membro',
                data_entrada DATE,
                data_saida DATE,
                ativo INTEGER DEFAULT 1,
                FOREIGN KEY (pessoa_id) REFERENCES pessoas(id),
                FOREIGN KEY (celula_id) REFERENCES celulas(id)
            )
        ''')
        
        # Reuniões de célula
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reunioes_celula (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                celula_id INTEGER NOT NULL,
                data DATE NOT NULL,
                tema TEXT,
                total_presentes INTEGER DEFAULT 0,
                total_visitantes INTEGER DEFAULT 0,
                oferta REAL DEFAULT 0,
                observacoes TEXT,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (celula_id) REFERENCES celulas(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS presenca_celula (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reuniao_id INTEGER NOT NULL,
                pessoa_id INTEGER NOT NULL,
                presente INTEGER DEFAULT 1,
                visitante INTEGER DEFAULT 0,
                FOREIGN KEY (reuniao_id) REFERENCES reunioes_celula(id),
                FOREIGN KEY (pessoa_id) REFERENCES pessoas(id)
            )
        ''')
        
        # ========================================
        # MÓDULO DE EVENTOS & PRESENÇA
        # ========================================
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS eventos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                igreja_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                descricao TEXT,
                tipo TEXT,
                data_inicio TIMESTAMP NOT NULL,
                data_fim TIMESTAMP,
                local TEXT,
                capacidade INTEGER,
                valor_inscricao REAL DEFAULT 0,
                requer_inscricao INTEGER DEFAULT 0,
                qrcode TEXT,
                banner_url TEXT,
                ativo INTEGER DEFAULT 1,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inscricoes_evento (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evento_id INTEGER NOT NULL,
                pessoa_id INTEGER NOT NULL,
                status TEXT DEFAULT 'inscrito',
                data_inscricao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                valor_pago REAL DEFAULT 0,
                data_pagamento TIMESTAMP,
                qrcode_checkin TEXT,
                FOREIGN KEY (evento_id) REFERENCES eventos(id),
                FOREIGN KEY (pessoa_id) REFERENCES pessoas(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS presenca_evento (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evento_id INTEGER NOT NULL,
                pessoa_id INTEGER NOT NULL,
                data_checkin TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tipo_checkin TEXT DEFAULT 'manual',
                FOREIGN KEY (evento_id) REFERENCES eventos(id),
                FOREIGN KEY (pessoa_id) REFERENCES pessoas(id)
            )
        ''')
        
        # ========================================
        # MÓDULO DE COMUNICAÇÃO
        # ========================================
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS templates_mensagem (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                igreja_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                categoria TEXT,
                assunto TEXT,
                conteudo TEXT NOT NULL,
                variaveis TEXT,
                tipo_canal TEXT,
                ativo INTEGER DEFAULT 1,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS campanhas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                igreja_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                descricao TEXT,
                template_id INTEGER,
                tipo_canal TEXT,
                segmentacao TEXT,
                status TEXT DEFAULT 'rascunho',
                data_envio TIMESTAMP,
                total_enviados INTEGER DEFAULT 0,
                total_entregues INTEGER DEFAULT 0,
                total_abertos INTEGER DEFAULT 0,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id),
                FOREIGN KEY (template_id) REFERENCES templates_mensagem(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mensagens_enviadas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campanha_id INTEGER,
                pessoa_id INTEGER NOT NULL,
                canal TEXT NOT NULL,
                conteudo TEXT,
                status TEXT DEFAULT 'enviado',
                data_envio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_entrega TIMESTAMP,
                data_leitura TIMESTAMP,
                erro TEXT,
                FOREIGN KEY (campanha_id) REFERENCES campanhas(id),
                FOREIGN KEY (pessoa_id) REFERENCES pessoas(id)
            )
        ''')
        
        # ========================================
        # MÓDULO DE DOAÇÕES/FINANCEIRO
        # ========================================
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS doacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                igreja_id INTEGER NOT NULL,
                pessoa_id INTEGER,
                tipo TEXT NOT NULL,
                valor REAL NOT NULL,
                data DATE NOT NULL,
                forma_pagamento TEXT,
                referencia TEXT,
                observacoes TEXT,
                anonimo INTEGER DEFAULT 0,
                comprovante_url TEXT,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                registrado_por INTEGER,
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id),
                FOREIGN KEY (pessoa_id) REFERENCES pessoas(id),
                FOREIGN KEY (registrado_por) REFERENCES usuarios(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categorias_financeiras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                igreja_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                tipo TEXT NOT NULL,
                descricao TEXT,
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id)
            )
        ''')
        
        # ========================================
        # MÓDULO DE ACONSELHAMENTO PASTORAL
        # ========================================
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS aconselhamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                igreja_id INTEGER NOT NULL,
                pessoa_id INTEGER NOT NULL,
                conselheiro_id INTEGER NOT NULL,
                data_atendimento TIMESTAMP NOT NULL,
                tipo TEXT,
                resumo_criptografado TEXT,
                notas_criptografadas TEXT,
                status TEXT DEFAULT 'em_andamento',
                proximo_encontro TIMESTAMP,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id),
                FOREIGN KEY (pessoa_id) REFERENCES pessoas(id),
                FOREIGN KEY (conselheiro_id) REFERENCES pessoas(id)
            )
        ''')
        
        # ========================================
        # ÍNDICES PARA PERFORMANCE
        # ========================================
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pessoas_igreja ON pessoas(igreja_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pessoas_status ON pessoas(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pessoas_nome ON pessoas(nome)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_doacoes_pessoa ON doacoes(pessoa_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_doacoes_data ON doacoes(data)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_presenca_evento ON presenca_evento(evento_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_presenca_pessoa ON presenca_evento(pessoa_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_usuario ON logs_acesso(usuario_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_data ON logs_acesso(data_hora)')
        
        # ========================================
        # ADICIONAR COLUNAS FALTANTES (MIGRAÇÕES)
        # ========================================
        
        # Adicionar novas colunas à tabela pessoas se não existirem
        try:
            cursor.execute('ALTER TABLE pessoas ADD COLUMN quem_convidou TEXT')
        except:
            pass
        
        try:
            cursor.execute('ALTER TABLE pessoas ADD COLUMN batizado INTEGER DEFAULT 0')
        except:
            pass
        
        try:
            cursor.execute('ALTER TABLE pessoas ADD COLUMN aceita_whatsapp INTEGER DEFAULT 1')
        except:
            pass
        
        try:
            cursor.execute('ALTER TABLE pessoas ADD COLUMN sexo TEXT')
        except:
            pass
        
        # ========================================
        # NOVAS TABELAS - ESCALA DE MINISTÉRIOS
        # ========================================
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS escalas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                igreja_id INTEGER NOT NULL,
                ministerio_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                data_inicio DATE NOT NULL,
                data_fim DATE NOT NULL,
                recorrencia TEXT DEFAULT 'semanal',
                ativo INTEGER DEFAULT 1,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id),
                FOREIGN KEY (ministerio_id) REFERENCES ministerios(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS escala_itens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                escala_id INTEGER NOT NULL,
                pessoa_id INTEGER NOT NULL,
                data DATE NOT NULL,
                funcao TEXT,
                horario TEXT,
                confirmado INTEGER DEFAULT 0,
                data_confirmacao TIMESTAMP,
                observacoes TEXT,
                FOREIGN KEY (escala_id) REFERENCES escalas(id),
                FOREIGN KEY (pessoa_id) REFERENCES pessoas(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trocas_escala (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                escala_item_id INTEGER NOT NULL,
                solicitante_id INTEGER NOT NULL,
                substituto_id INTEGER,
                motivo TEXT,
                status TEXT DEFAULT 'pendente',
                data_solicitacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_resposta TIMESTAMP,
                FOREIGN KEY (escala_item_id) REFERENCES escala_itens(id),
                FOREIGN KEY (solicitante_id) REFERENCES pessoas(id),
                FOREIGN KEY (substituto_id) REFERENCES pessoas(id)
            )
        ''')
        
        # ========================================
        # NOVAS TABELAS - TRILHA DE DISCIPULADO
        # ========================================
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cursos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                igreja_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                descricao TEXT,
                categoria TEXT,
                duracao_horas INTEGER,
                pre_requisito_id INTEGER,
                ordem_trilha INTEGER DEFAULT 0,
                material_url TEXT,
                ativo INTEGER DEFAULT 1,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id),
                FOREIGN KEY (pre_requisito_id) REFERENCES cursos(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS turmas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                curso_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                instrutor_id INTEGER,
                data_inicio DATE,
                data_fim DATE,
                horario TEXT,
                local TEXT,
                vagas INTEGER DEFAULT 30,
                status TEXT DEFAULT 'aberta',
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (curso_id) REFERENCES cursos(id),
                FOREIGN KEY (instrutor_id) REFERENCES pessoas(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS matriculas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turma_id INTEGER NOT NULL,
                pessoa_id INTEGER NOT NULL,
                data_matricula DATE NOT NULL,
                status TEXT DEFAULT 'ativa',
                nota_final REAL,
                frequencia REAL,
                data_conclusao DATE,
                certificado_emitido INTEGER DEFAULT 0,
                observacoes TEXT,
                FOREIGN KEY (turma_id) REFERENCES turmas(id),
                FOREIGN KEY (pessoa_id) REFERENCES pessoas(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS aulas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turma_id INTEGER NOT NULL,
                numero INTEGER NOT NULL,
                titulo TEXT,
                data DATE,
                conteudo TEXT,
                FOREIGN KEY (turma_id) REFERENCES turmas(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS presenca_aula (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                aula_id INTEGER NOT NULL,
                pessoa_id INTEGER NOT NULL,
                presente INTEGER DEFAULT 0,
                FOREIGN KEY (aula_id) REFERENCES aulas(id),
                FOREIGN KEY (pessoa_id) REFERENCES pessoas(id)
            )
        ''')
        
        # ========================================
        # NOVAS TABELAS - AGENDA/CALENDÁRIO
        # ========================================
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agenda (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                igreja_id INTEGER NOT NULL,
                titulo TEXT NOT NULL,
                descricao TEXT,
                tipo TEXT DEFAULT 'evento',
                data_inicio TIMESTAMP NOT NULL,
                data_fim TIMESTAMP,
                dia_todo INTEGER DEFAULT 0,
                local TEXT,
                cor TEXT DEFAULT '#3498db',
                recorrencia TEXT,
                lembrete_minutos INTEGER,
                criado_por INTEGER,
                ministerio_id INTEGER,
                celula_id INTEGER,
                evento_id INTEGER,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id),
                FOREIGN KEY (criado_por) REFERENCES usuarios(id),
                FOREIGN KEY (ministerio_id) REFERENCES ministerios(id),
                FOREIGN KEY (celula_id) REFERENCES celulas(id),
                FOREIGN KEY (evento_id) REFERENCES eventos(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lembretes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agenda_id INTEGER NOT NULL,
                pessoa_id INTEGER NOT NULL,
                data_lembrete TIMESTAMP NOT NULL,
                enviado INTEGER DEFAULT 0,
                canal TEXT DEFAULT 'whatsapp',
                data_envio TIMESTAMP,
                FOREIGN KEY (agenda_id) REFERENCES agenda(id),
                FOREIGN KEY (pessoa_id) REFERENCES pessoas(id)
            )
        ''')
        
        # ========================================
        # NOVAS TABELAS - MURAL/CHAT
        # ========================================
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mural_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                igreja_id INTEGER NOT NULL,
                autor_id INTEGER NOT NULL,
                titulo TEXT,
                conteudo TEXT NOT NULL,
                tipo TEXT DEFAULT 'aviso',
                destino TEXT DEFAULT 'todos',
                ministerio_id INTEGER,
                celula_id INTEGER,
                fixado INTEGER DEFAULT 0,
                permite_comentarios INTEGER DEFAULT 1,
                data_expiracao DATE,
                visualizacoes INTEGER DEFAULT 0,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id),
                FOREIGN KEY (autor_id) REFERENCES pessoas(id),
                FOREIGN KEY (ministerio_id) REFERENCES ministerios(id),
                FOREIGN KEY (celula_id) REFERENCES celulas(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mural_comentarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                autor_id INTEGER NOT NULL,
                conteudo TEXT NOT NULL,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES mural_posts(id),
                FOREIGN KEY (autor_id) REFERENCES pessoas(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mural_curtidas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                pessoa_id INTEGER NOT NULL,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES mural_posts(id),
                FOREIGN KEY (pessoa_id) REFERENCES pessoas(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pedidos_oracao_mural (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                igreja_id INTEGER NOT NULL,
                autor_id INTEGER NOT NULL,
                pedido TEXT NOT NULL,
                anonimo INTEGER DEFAULT 0,
                status TEXT DEFAULT 'ativo',
                total_orando INTEGER DEFAULT 0,
                data_resposta DATE,
                testemunho TEXT,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id),
                FOREIGN KEY (autor_id) REFERENCES pessoas(id)
            )
        ''')
        
        # ========================================
        # NOVAS TABELAS - METAS E OKRs
        # ========================================
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                igreja_id INTEGER NOT NULL,
                titulo TEXT NOT NULL,
                descricao TEXT,
                categoria TEXT,
                tipo_meta TEXT DEFAULT 'numero',
                valor_inicial REAL DEFAULT 0,
                valor_meta REAL NOT NULL,
                valor_atual REAL DEFAULT 0,
                unidade TEXT,
                data_inicio DATE NOT NULL,
                data_fim DATE NOT NULL,
                responsavel_id INTEGER,
                status TEXT DEFAULT 'em_andamento',
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id),
                FOREIGN KEY (responsavel_id) REFERENCES pessoas(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS meta_atualizacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meta_id INTEGER NOT NULL,
                valor_anterior REAL,
                valor_novo REAL,
                observacao TEXT,
                atualizado_por INTEGER,
                data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (meta_id) REFERENCES metas(id),
                FOREIGN KEY (atualizado_por) REFERENCES usuarios(id)
            )
        ''')
        
        # ========================================
        # NOVAS TABELAS - NOTIFICAÇÕES
        # ========================================
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notificacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                igreja_id INTEGER NOT NULL,
                pessoa_id INTEGER,
                usuario_id INTEGER,
                tipo TEXT NOT NULL,
                titulo TEXT NOT NULL,
                mensagem TEXT,
                link TEXT,
                lida INTEGER DEFAULT 0,
                data_leitura TIMESTAMP,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id),
                FOREIGN KEY (pessoa_id) REFERENCES pessoas(id),
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config_notificacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                igreja_id INTEGER NOT NULL,
                tipo_notificacao TEXT NOT NULL,
                ativo INTEGER DEFAULT 1,
                canal TEXT DEFAULT 'sistema',
                antecedencia_dias INTEGER DEFAULT 1,
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id)
            )
        ''')
        
        # ========================================
        # NOVAS TABELAS - GALERIA DE FOTOS
        # ========================================
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS albuns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                igreja_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                descricao TEXT,
                evento_id INTEGER,
                celula_id INTEGER,
                ministerio_id INTEGER,
                data_evento DATE,
                capa_url TEXT,
                publico INTEGER DEFAULT 0,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (igreja_id) REFERENCES igrejas(id),
                FOREIGN KEY (evento_id) REFERENCES eventos(id),
                FOREIGN KEY (celula_id) REFERENCES celulas(id),
                FOREIGN KEY (ministerio_id) REFERENCES ministerios(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fotos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                album_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                thumbnail_url TEXT,
                descricao TEXT,
                fotografo_id INTEGER,
                data_upload TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (album_id) REFERENCES albuns(id),
                FOREIGN KEY (fotografo_id) REFERENCES pessoas(id)
            )
        ''')
        
        # ========================================
        # NOVAS TABELAS - SEGURANÇA 2FA
        # ========================================
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS autenticacao_2fa (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL UNIQUE,
                ativo INTEGER DEFAULT 0,
                metodo TEXT DEFAULT 'email',
                segredo TEXT,
                backup_codes TEXT,
                data_ativacao TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessoes_ativas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                token TEXT NOT NULL,
                ip TEXT,
                user_agent TEXT,
                data_inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_expiracao TIMESTAMP,
                ativo INTEGER DEFAULT 1,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            )
        ''')
        
        conn.commit()
        print("✅ Banco de dados inicializado com sucesso!")

def criar_usuario_admin(igreja_id: int, nome: str, email: str, senha: str):
    """Cria um usuário administrador"""
    senha_hash = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO usuarios (igreja_id, nome, email, senha_hash, perfil)
            VALUES (?, ?, ?, ?, 'ADMIN')
        ''', (igreja_id, nome, email, senha_hash))
        return cursor.lastrowid

def criar_igreja_demo():
    """Cria uma igreja de demonstração com dados iniciais"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Verificar se já existe
        cursor.execute('SELECT id FROM igrejas WHERE email = ?', ('demo@crmigreja.com',))
        if cursor.fetchone():
            print("Igreja demo já existe!")
            return
        
        # Criar igreja
        cursor.execute('''
            INSERT INTO igrejas (nome, email, cidade, estado, plano)
            VALUES (?, ?, ?, ?, ?)
        ''', ('Igreja Demonstração', 'demo@crmigreja.com', 'São Paulo', 'SP', 'PRO'))
        igreja_id = cursor.lastrowid
        
        # Criar usuário admin
        senha_hash = bcrypt.hashpw('admin123'.encode(), bcrypt.gensalt()).decode()
        cursor.execute('''
            INSERT INTO usuarios (igreja_id, nome, email, senha_hash, perfil)
            VALUES (?, ?, ?, ?, ?)
        ''', (igreja_id, 'Administrador', 'admin@demo.com', senha_hash, 'ADMIN'))
        
        # Criar tags padrão
        tags = [
            ('Jovens', '#FF6B6B'),
            ('Casais', '#4ECDC4'),
            ('Voluntários', '#45B7D1'),
            ('Líderes', '#96CEB4'),
            ('Músicos', '#FFEAA7')
        ]
        for nome, cor in tags:
            cursor.execute('INSERT INTO tags (igreja_id, nome, cor) VALUES (?, ?, ?)',
                          (igreja_id, nome, cor))
        
        # Criar ministérios padrão
        ministerios = [
            'Louvor e Adoração',
            'Infantil',
            'Jovens',
            'Casais',
            'Intercessão',
            'Mídia',
            'Recepção',
            'Ação Social'
        ]
        for nome in ministerios:
            cursor.execute('INSERT INTO ministerios (igreja_id, nome) VALUES (?, ?)',
                          (igreja_id, nome))
        
        # Criar templates de mensagem
        templates = [
            ('Boas-vindas Visitante', 'boas_vindas', 'Bem-vindo à nossa igreja!', 
             'Olá {nome}! Foi uma alegria ter você conosco. Esperamos que tenha se sentido acolhido. Volte sempre!', 'whatsapp'),
            ('Convite Célula', 'convite', 'Convite especial para você',
             'Olá {nome}! Gostaríamos de convidá-lo para participar de uma de nossas células. É um momento especial de comunhão!', 'whatsapp'),
            ('Aniversário', 'aniversario', 'Feliz Aniversário!',
             'Parabéns {nome}! 🎂 Que Deus abençoe abundantemente sua vida neste novo ano!', 'whatsapp'),
            ('Lembrete Evento', 'evento', 'Lembrete: {evento}',
             'Olá {nome}! Lembramos que {evento} acontecerá em {data}. Esperamos você!', 'email')
        ]
        for nome, cat, assunto, conteudo, canal in templates:
            cursor.execute('''
                INSERT INTO templates_mensagem (igreja_id, nome, categoria, assunto, conteudo, tipo_canal)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (igreja_id, nome, cat, assunto, conteudo, canal))
        
        # Criar fluxos de follow-up
        fluxos = [
            ('Boas-vindas 24h', 'Enviar mensagem de boas-vindas após primeira visita', 
             'primeira_visita', 1, 'mensagem', 'Olá {nome}! Foi uma alegria ter você conosco ontem!'),
            ('Convite Célula 7 dias', 'Convidar para célula após uma semana',
             'primeira_visita', 7, 'mensagem', 'Olá {nome}! Que tal participar de uma de nossas células?'),
            ('Follow-up 30 dias', 'Verificar engajamento após um mês',
             'primeira_visita', 30, 'tarefa', 'Ligar para {nome} e verificar interesse em continuar')
        ]
        for nome, desc, trigger, dias, tipo, template in fluxos:
            cursor.execute('''
                INSERT INTO fluxos_followup (igreja_id, nome, descricao, trigger_evento, dias_apos_trigger, tipo_acao, template_mensagem)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (igreja_id, nome, desc, trigger, dias, tipo, template))
        
        conn.commit()
        print("✅ Igreja demo criada com sucesso!")
        print("📧 Email: admin@demo.com")
        print("🔑 Senha: admin123")

def popular_dados_demonstracao():
    """Popula o banco de dados com 100 pessoas e dados de demonstração"""
    import random
    from datetime import date, timedelta
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Verificar se já existem dados
        cursor.execute('SELECT COUNT(*) FROM pessoas WHERE igreja_id = 1')
        if cursor.fetchone()[0] > 10:
            print("⚠️ Dados de demonstração já existem!")
            return
        
        igreja_id = 1
        
        # Listas de nomes brasileiros
        nomes_masculinos = [
            'João', 'Pedro', 'Lucas', 'Mateus', 'Gabriel', 'Rafael', 'Daniel', 'Bruno',
            'Carlos', 'André', 'Felipe', 'Marcos', 'Paulo', 'Thiago', 'Leonardo', 'Gustavo',
            'Ricardo', 'Fernando', 'Roberto', 'Eduardo', 'Henrique', 'Diego', 'Vinicius',
            'Samuel', 'Davi', 'José', 'Antonio', 'Francisco', 'Luiz', 'Marcelo', 'Alexandre',
            'Rodrigo', 'Fabio', 'Sergio', 'Jorge', 'Renato', 'Claudio', 'Leandro', 'Julio'
        ]
        
        nomes_femininos = [
            'Maria', 'Ana', 'Julia', 'Beatriz', 'Larissa', 'Amanda', 'Camila', 'Fernanda',
            'Patricia', 'Bruna', 'Carolina', 'Leticia', 'Gabriela', 'Mariana', 'Vanessa',
            'Juliana', 'Aline', 'Priscila', 'Raquel', 'Sandra', 'Luciana', 'Daniela',
            'Cristina', 'Regina', 'Marta', 'Helena', 'Lucia', 'Teresa', 'Rosa', 'Simone',
            'Elaine', 'Adriana', 'Renata', 'Claudia', 'Silvia', 'Monica', 'Carla', 'Paula'
        ]
        
        sobrenomes = [
            'Silva', 'Santos', 'Oliveira', 'Souza', 'Rodrigues', 'Ferreira', 'Alves',
            'Pereira', 'Lima', 'Gomes', 'Costa', 'Ribeiro', 'Martins', 'Carvalho',
            'Almeida', 'Lopes', 'Soares', 'Fernandes', 'Vieira', 'Barbosa', 'Rocha',
            'Dias', 'Nascimento', 'Andrade', 'Moreira', 'Nunes', 'Marques', 'Machado',
            'Mendes', 'Freitas', 'Cardoso', 'Ramos', 'Gonçalves', 'Santana', 'Teixeira'
        ]
        
        bairros = [
            'Centro', 'Jardim das Flores', 'Vila Nova', 'Boa Vista', 'Santa Maria',
            'São José', 'Jardim América', 'Vila Rica', 'Parque Industrial', 'Jardim Europa'
        ]
        
        status_lista = [
            ('visitante', 10),
            ('novo_convertido', 8),
            ('em_integracao', 7),
            ('membro', 35),
            ('dizimista', 20),
            ('lider', 8),
            ('obreiro', 5),
            ('diacono', 3),
            ('pastor_auxiliar', 2),
            ('pastor', 2)
        ]
        
        como_conheceu = [
            'Convite de amigo/familiar', 'Redes sociais', 'Passou em frente', 
            'Evento', 'Indicação', 'Internet', 'Outro'
        ]
        
        # Gerar pessoas
        pessoas_ids = []
        pessoa_count = 0
        
        for status, quantidade in status_lista:
            for _ in range(quantidade):
                # Gerar dados aleatórios
                is_male = random.random() > 0.45
                nome = random.choice(nomes_masculinos if is_male else nomes_femininos)
                sobrenome1 = random.choice(sobrenomes)
                sobrenome2 = random.choice(sobrenomes)
                nome_completo = f"{nome} {sobrenome1} {sobrenome2}"
                
                email = f"{nome.lower()}.{sobrenome1.lower()}{random.randint(1, 99)}@email.com"
                celular = f"(11) 9{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"
                
                # Data de nascimento (18 a 70 anos)
                idade = random.randint(18, 70)
                data_nasc = date.today() - timedelta(days=idade*365 + random.randint(0, 364))
                
                genero = 'Masculino' if is_male else 'Feminino'
                estado_civil = random.choice(['Solteiro(a)', 'Casado(a)', 'Divorciado(a)', 'Viúvo(a)'])
                
                # Endereço
                endereco = f"Rua {random.choice(['das Flores', 'Principal', 'da Paz', 'São Paulo', 'Brasil', 'das Américas'])}"
                numero = str(random.randint(10, 999))
                bairro = random.choice(bairros)
                
                # Data de primeira visita (últimos 3 anos)
                dias_atras = random.randint(30, 1095)
                data_primeira_visita = date.today() - timedelta(days=dias_atras)
                
                # Data de batismo (para membros e acima)
                data_batismo = None
                if status not in ['visitante', 'novo_convertido']:
                    dias_batismo = random.randint(30, dias_atras - 30) if dias_atras > 60 else 30
                    data_batismo = date.today() - timedelta(days=dias_batismo)
                
                cursor.execute('''
                    INSERT INTO pessoas (
                        igreja_id, nome, email, celular, data_nascimento, genero, estado_civil,
                        endereco, numero, bairro, cidade, estado, cep, status, 
                        como_conheceu, data_primeira_visita, data_batismo, ativo
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ''', (
                    igreja_id, nome_completo, email, celular, data_nasc, genero, estado_civil,
                    endereco, numero, bairro, 'São Paulo', 'SP', f'0{random.randint(1000, 9999)}-{random.randint(100, 999)}',
                    status, random.choice(como_conheceu), data_primeira_visita, data_batismo
                ))
                
                pessoas_ids.append((cursor.lastrowid, status, nome_completo))
                pessoa_count += 1
        
        print(f"✅ {pessoa_count} pessoas cadastradas!")
        
        # Criar ministérios se não existirem
        ministerios = [
            ('Louvor e Adoração', '#3498db'),
            ('Ministério Infantil', '#e74c3c'),
            ('Juventude', '#9b59b6'),
            ('Casais', '#e91e63'),
            ('Intercessão', '#f39c12'),
            ('Mídia e Comunicação', '#2ecc71'),
            ('Recepção e Acolhimento', '#1abc9c'),
            ('Ação Social', '#34495e'),
            ('Discipulado', '#8e44ad'),
            ('Evangelismo', '#d35400')
        ]
        
        ministerios_ids = []
        for nome, cor in ministerios:
            cursor.execute('SELECT id FROM ministerios WHERE igreja_id = ? AND nome = ?', (igreja_id, nome))
            row = cursor.fetchone()
            if row:
                ministerios_ids.append(row[0])
            else:
                cursor.execute('INSERT INTO ministerios (igreja_id, nome, cor) VALUES (?, ?, ?)',
                              (igreja_id, nome, cor))
                ministerios_ids.append(cursor.lastrowid)
        
        # Atribuir líderes aos ministérios
        lideres = [p for p in pessoas_ids if p[1] in ['lider', 'obreiro', 'diacono', 'pastor_auxiliar', 'pastor']]
        for i, min_id in enumerate(ministerios_ids):
            if i < len(lideres):
                cursor.execute('UPDATE ministerios SET lider_id = ? WHERE id = ?', (lideres[i][0], min_id))
        
        # Adicionar membros aos ministérios
        membros_ministerio = [p for p in pessoas_ids if p[1] not in ['visitante', 'novo_convertido']]
        for pessoa_id, status, nome in membros_ministerio:
            # Cada pessoa participa de 1-3 ministérios
            qtd_ministerios = random.randint(1, 3)
            ministerios_pessoa = random.sample(ministerios_ids, min(qtd_ministerios, len(ministerios_ids)))
            
            for min_id in ministerios_pessoa:
                funcao = 'Membro'
                if status in ['lider', 'obreiro']:
                    funcao = random.choice(['Líder', 'Coordenador', 'Membro'])
                
                try:
                    cursor.execute('''
                        INSERT INTO membros_ministerio (ministerio_id, pessoa_id, funcao, data_entrada)
                        VALUES (?, ?, ?, ?)
                    ''', (min_id, pessoa_id, funcao, date.today() - timedelta(days=random.randint(30, 365))))
                except:
                    pass
        
        print("✅ Membros adicionados aos ministérios!")
        
        # Criar células
        celulas_nomes = [
            'Célula Esperança', 'Célula Vida Nova', 'Célula Restauração', 'Célula Aliança',
            'Célula Graça', 'Célula Fé', 'Célula Amor', 'Célula Vitória', 'Célula Paz',
            'Célula Família', 'Célula Jovens do Rei', 'Célula Mulheres de Valor'
        ]
        
        dias_semana = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado']
        
        celulas_ids = []
        for i, nome_celula in enumerate(celulas_nomes):
            lider = lideres[i % len(lideres)] if lideres else pessoas_ids[0]
            
            cursor.execute('''
                INSERT INTO celulas (igreja_id, nome, lider_id, endereco, dia_semana, horario)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                igreja_id, nome_celula, lider[0],
                f"Rua {random.choice(['das Flores', 'Principal', 'da Paz'])}, {random.randint(10, 500)}",
                random.choice(dias_semana), f"{random.randint(19, 20)}:00"
            ))
            celulas_ids.append(cursor.lastrowid)
        
        # Adicionar membros às células
        for pessoa_id, status, nome in pessoas_ids:
            if status not in ['visitante']:
                celula_id = random.choice(celulas_ids)
                try:
                    cursor.execute('''
                        INSERT INTO membros_celula (celula_id, pessoa_id, data_entrada)
                        VALUES (?, ?, ?)
                    ''', (celula_id, pessoa_id, date.today() - timedelta(days=random.randint(30, 365))))
                except:
                    pass
        
        print("✅ Células criadas e membros adicionados!")
        
        # Registrar reuniões de células (últimos 3 meses)
        for celula_id in celulas_ids:
            # 12 reuniões por célula
            for semana in range(12):
                data_reuniao = date.today() - timedelta(days=semana * 7 + random.randint(0, 3))
                
                cursor.execute('''
                    INSERT INTO reunioes_celula (celula_id, data, tema, total_presentes, total_visitantes, oferta)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    celula_id, data_reuniao,
                    random.choice(['Estudo Bíblico', 'Oração', 'Louvor', 'Testemunhos', 'Comunhão']),
                    random.randint(5, 15), random.randint(0, 3), random.uniform(50, 200)
                ))
        
        print("✅ Reuniões de células registradas!")
        
        # Criar eventos
        tipos_evento = ['Culto Dominical', 'Culto de Oração', 'Congresso', 'Conferência', 'Curso', 'Batismo', 'Retiro']
        
        eventos_ids = []
        for i in range(20):
            dias_evento = random.randint(-60, 30)  # Passados e futuros
            data_evento = date.today() + timedelta(days=dias_evento)
            
            tipo = random.choice(tipos_evento)
            nome_evento = f"{tipo} - {data_evento.strftime('%B %Y')}"
            
            cursor.execute('''
                INSERT INTO eventos (igreja_id, nome, tipo, data_inicio, local, capacidade)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                igreja_id, nome_evento, tipo, 
                datetime.combine(data_evento, datetime.strptime('19:00', '%H:%M').time()),
                'Templo Principal', random.randint(100, 500)
            ))
            eventos_ids.append(cursor.lastrowid)
        
        # Registrar presenças nos eventos passados
        eventos_passados = [e for e in eventos_ids[:15]]  # Primeiros 15 são passados
        for evento_id in eventos_passados:
            # 30-80% de presença
            presentes = random.sample(pessoas_ids, k=random.randint(30, min(80, len(pessoas_ids))))
            for pessoa_id, _, _ in presentes:
                try:
                    cursor.execute('''
                        INSERT INTO presenca_evento (evento_id, pessoa_id, tipo_checkin, data_checkin)
                        VALUES (?, ?, 'manual', ?)
                    ''', (evento_id, pessoa_id, datetime.now() - timedelta(days=random.randint(1, 60))))
                except:
                    pass
        
        print("✅ Eventos criados com presenças!")
        
        # Registrar doações (últimos 12 meses)
        tipos_doacao = ['Dízimo', 'Oferta', 'Campanha', 'Missões']
        formas_pagamento = ['Dinheiro', 'PIX', 'Cartão Débito', 'Transferência']
        
        # Dizimistas e membros ativos doam
        doadores = [p for p in pessoas_ids if p[1] in ['dizimista', 'membro', 'lider', 'obreiro', 'diacono', 'pastor_auxiliar', 'pastor']]
        
        for pessoa_id, status, nome in doadores:
            # Dizimistas doam todos os meses
            if status == 'dizimista':
                meses_doacao = 12
            elif status in ['pastor', 'pastor_auxiliar', 'diacono']:
                meses_doacao = random.randint(10, 12)
            elif status in ['lider', 'obreiro']:
                meses_doacao = random.randint(8, 12)
            else:
                meses_doacao = random.randint(3, 8)
            
            for mes in range(meses_doacao):
                data_doacao = date.today() - timedelta(days=mes * 30 + random.randint(0, 15))
                
                # Dízimo
                valor_dizimo = random.uniform(200, 2000)
                cursor.execute('''
                    INSERT INTO doacoes (igreja_id, pessoa_id, tipo, valor, data, forma_pagamento, anonimo)
                    VALUES (?, ?, 'Dízimo', ?, ?, ?, 0)
                ''', (igreja_id, pessoa_id, round(valor_dizimo, 2), data_doacao, random.choice(formas_pagamento)))
                
                # Ofertas (ocasionalmente)
                if random.random() > 0.6:
                    valor_oferta = random.uniform(20, 200)
                    cursor.execute('''
                        INSERT INTO doacoes (igreja_id, pessoa_id, tipo, valor, data, forma_pagamento, anonimo)
                        VALUES (?, ?, 'Oferta', ?, ?, ?, 0)
                    ''', (igreja_id, pessoa_id, round(valor_oferta, 2), data_doacao, random.choice(formas_pagamento)))
        
        # Doações anônimas
        for _ in range(30):
            data_doacao = date.today() - timedelta(days=random.randint(1, 365))
            cursor.execute('''
                INSERT INTO doacoes (igreja_id, tipo, valor, data, forma_pagamento, anonimo)
                VALUES (?, ?, ?, ?, ?, 1)
            ''', (igreja_id, random.choice(['Oferta', 'Campanha']), 
                  round(random.uniform(50, 500), 2), data_doacao, random.choice(formas_pagamento)))
        
        print("✅ Doações registradas!")
        
        # Registrar aconselhamentos
        pastores = [p for p in pessoas_ids if p[1] in ['pastor', 'pastor_auxiliar']]
        if not pastores:
            pastores = [pessoas_ids[0]]
        
        tipos_aconselhamento = ['Casamento', 'Família', 'Emocional', 'Espiritual', 'Financeiro', 'Profissional']
        
        for _ in range(25):
            pessoa = random.choice(pessoas_ids)
            conselheiro = random.choice(pastores)
            
            data_atendimento = date.today() - timedelta(days=random.randint(1, 180))
            
            cursor.execute('''
                INSERT INTO aconselhamentos (
                    igreja_id, pessoa_id, conselheiro_id, data_atendimento, tipo, status, resumo_criptografado
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                igreja_id, pessoa[0], conselheiro[0], data_atendimento,
                random.choice(tipos_aconselhamento),
                random.choice(['em_andamento', 'concluido', 'concluido', 'concluido']),
                'Atendimento pastoral realizado conforme solicitação.'
            ))
        
        print("✅ Aconselhamentos registrados!")
        
        # Criar follow-ups para visitantes (pessoas com status visitante)
        cursor.execute('''
            SELECT id, nome FROM pessoas 
            WHERE igreja_id = ? AND status = 'visitante'
        ''', (igreja_id,))
        visitantes = cursor.fetchall()
        
        for visitante in visitantes:
            responsavel = random.choice(lideres) if lideres else pessoas_ids[0]
            
            cursor.execute('''
                INSERT INTO followup (
                    pessoa_id, responsavel_id, tipo, data_prevista, status, observacoes
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                visitante[0], responsavel[0],
                random.choice(['ligacao', 'mensagem', 'visita']),
                date.today() + timedelta(days=random.randint(-7, 14)),
                random.choice(['pendente', 'realizado', 'pendente']),
                f"Contato com {visitante[1]}"
            ))
        
        print("✅ Follow-ups criados!")
        
        conn.commit()
        print("\n🎉 DADOS DE DEMONSTRAÇÃO CRIADOS COM SUCESSO!")
        print(f"📊 Resumo:")
        print(f"   • {pessoa_count} pessoas cadastradas")
        print(f"   • {len(celulas_ids)} células criadas")
        print(f"   • {len(eventos_ids)} eventos criados")
        print(f"   • {len(visitantes)} visitantes registrados")
        print(f"   • Doações, aconselhamentos e presenças registrados")

if __name__ == '__main__':
    init_database()
    criar_igreja_demo()
    popular_dados_demonstracao()
