"""
Módulo de Comunicação Integrada
WhatsApp, E-mail, SMS
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date
from database.db import get_connection
from modules.auth import get_igreja_id, get_usuario_atual, registrar_log
from config.settings import STATUS_PESSOA, formatar_data_br

def get_templates() -> list:
    """Busca templates de mensagem"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM templates_mensagem
            WHERE igreja_id = ? AND ativo = 1
            ORDER BY categoria, nome
        ''', (igreja_id,))
        return [dict(row) for row in cursor.fetchall()]

def get_template(template_id: int) -> dict:
    """Busca um template específico"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM templates_mensagem
            WHERE id = ? AND igreja_id = ?
        ''', (template_id, igreja_id))
        row = cursor.fetchone()
        return dict(row) if row else None

def salvar_template(dados: dict) -> int:
    """Salva ou atualiza um template"""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        if dados.get('id'):
            cursor.execute('''
                UPDATE templates_mensagem
                SET nome = ?, categoria = ?, assunto = ?, conteudo = ?, tipo_canal = ?
                WHERE id = ? AND igreja_id = ?
            ''', (dados['nome'], dados.get('categoria'), dados.get('assunto'),
                  dados['conteudo'], dados.get('tipo_canal', 'whatsapp'),
                  dados['id'], igreja_id))
            return dados['id']
        else:
            cursor.execute('''
                INSERT INTO templates_mensagem (igreja_id, nome, categoria, assunto, conteudo, tipo_canal)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (igreja_id, dados['nome'], dados.get('categoria'), dados.get('assunto'),
                  dados['conteudo'], dados.get('tipo_canal', 'whatsapp')))
            return cursor.lastrowid

def get_campanhas() -> list:
    """Busca campanhas de comunicação"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.*, t.nome as template_nome
            FROM campanhas c
            LEFT JOIN templates_mensagem t ON c.template_id = t.id
            WHERE c.igreja_id = ?
            ORDER BY c.data_cadastro DESC
        ''', (igreja_id,))
        return [dict(row) for row in cursor.fetchall()]

def criar_campanha(dados: dict) -> int:
    """Cria uma nova campanha"""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO campanhas (igreja_id, nome, descricao, template_id, tipo_canal, segmentacao, status)
            VALUES (?, ?, ?, ?, ?, ?, 'rascunho')
        ''', (igreja_id, dados['nome'], dados.get('descricao'), dados.get('template_id'),
              dados.get('tipo_canal', 'whatsapp'), dados.get('segmentacao')))
        
        registrar_log(usuario['id'], igreja_id, 'campanha.criar', f"Campanha criada: {dados['nome']}")
        return cursor.lastrowid

def get_pessoas_por_segmento(segmento: str) -> list:
    """Busca pessoas por segmento"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        if segmento == 'todos':
            cursor.execute('''
                SELECT id, nome, celular, email FROM pessoas
                WHERE igreja_id = ? AND ativo = 1
            ''', (igreja_id,))
        elif segmento == 'visitantes':
            cursor.execute('''
                SELECT id, nome, celular, email FROM pessoas
                WHERE igreja_id = ? AND status = 'visitante' AND ativo = 1
            ''', (igreja_id,))
        elif segmento == 'membros':
            cursor.execute('''
                SELECT id, nome, celular, email FROM pessoas
                WHERE igreja_id = ? AND status = 'membro' AND ativo = 1
            ''', (igreja_id,))
        elif segmento == 'lideres':
            cursor.execute('''
                SELECT DISTINCT p.id, p.nome, p.celular, p.email FROM pessoas p
                LEFT JOIN ministerios m ON p.id = m.lider_id
                LEFT JOIN celulas c ON p.id = c.lider_id
                WHERE p.igreja_id = ? AND (m.id IS NOT NULL OR c.id IS NOT NULL) AND p.ativo = 1
            ''', (igreja_id,))
        elif segmento == 'aniversariantes':
            cursor.execute('''
                SELECT id, nome, celular, email FROM pessoas
                WHERE igreja_id = ? AND ativo = 1
                AND strftime('%m-%d', data_nascimento) = strftime('%m-%d', 'now')
            ''', (igreja_id,))
        else:
            # Segmento customizado (tag)
            cursor.execute('''
                SELECT p.id, p.nome, p.celular, p.email FROM pessoas p
                JOIN pessoa_tags pt ON p.id = pt.pessoa_id
                JOIN tags t ON pt.tag_id = t.id
                WHERE p.igreja_id = ? AND t.nome = ? AND p.ativo = 1
            ''', (igreja_id, segmento))
        
        return [dict(row) for row in cursor.fetchall()]

def enviar_mensagem(pessoa_id: int, canal: str, conteudo: str, campanha_id: int = None):
    """Registra uma mensagem enviada"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO mensagens_enviadas (campanha_id, pessoa_id, canal, conteudo, status)
            VALUES (?, ?, ?, ?, 'enviado')
        ''', (campanha_id, pessoa_id, canal, conteudo))
        return cursor.lastrowid

def processar_variaveis(template: str, pessoa: dict) -> str:
    """Substitui variáveis no template"""
    mensagem = template
    mensagem = mensagem.replace('{nome}', pessoa.get('nome', '').split()[0])
    mensagem = mensagem.replace('{nome_completo}', pessoa.get('nome', ''))
    mensagem = mensagem.replace('{email}', pessoa.get('email', ''))
    return mensagem

def simular_envio_whatsapp(celular: str, mensagem: str) -> bool:
    """Simula envio de WhatsApp (integrar com API real)"""
    # Em produção, aqui seria a integração com WhatsApp Business API
    # Por exemplo: requests.post(WHATSAPP_API_URL, ...)
    print(f"[SIMULAÇÃO] WhatsApp para {celular}: {mensagem[:50]}...")
    return True

def simular_envio_email(email: str, assunto: str, mensagem: str) -> bool:
    """Simula envio de e-mail (integrar com SendGrid/SMTP)"""
    # Em produção, aqui seria a integração com SendGrid ou SMTP
    print(f"[SIMULAÇÃO] E-mail para {email}: {assunto}")
    return True

# ========================================
# RENDERIZAÇÃO DA INTERFACE
# ========================================

def render_templates():
    """Renderiza gestão de templates"""
    st.subheader("📝 Templates de Mensagem")
    
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("➕ Novo Template", use_container_width=True):
            st.session_state.show_form_template = True
    
    # Formulário de template
    if st.session_state.get('show_form_template'):
        with st.expander("➕ Novo Template", expanded=True):
            with st.form("form_template"):
                nome = st.text_input("Nome do template *")
                
                col1, col2 = st.columns(2)
                with col1:
                    categoria = st.selectbox("Categoria",
                                            options=['boas_vindas', 'convite', 'aniversario', 'evento', 'aviso', 'outro'])
                with col2:
                    tipo_canal = st.selectbox("Canal", options=['whatsapp', 'email', 'sms'])
                
                assunto = st.text_input("Assunto (para e-mail)")
                
                st.markdown("**Variáveis disponíveis:** `{nome}`, `{nome_completo}`, `{email}`, `{evento}`, `{data}`")
                conteudo = st.text_area("Conteúdo da mensagem *", height=150)
                
                col1, col2 = st.columns(2)
                with col1:
                    submit = st.form_submit_button("💾 Salvar", use_container_width=True)
                with col2:
                    if st.form_submit_button("❌ Cancelar", use_container_width=True):
                        st.session_state.show_form_template = False
                        st.rerun()
                
                if submit:
                    if not nome or not conteudo:
                        st.error("Nome e conteúdo são obrigatórios!")
                    else:
                        salvar_template({
                            'nome': nome,
                            'categoria': categoria,
                            'assunto': assunto,
                            'conteudo': conteudo,
                            'tipo_canal': tipo_canal
                        })
                        st.success("✅ Template salvo!")
                        st.session_state.show_form_template = False
                        st.rerun()
    
    # Lista de templates
    templates = get_templates()
    
    if not templates:
        st.info("Nenhum template cadastrado.")
        return
    
    # Agrupar por categoria
    categorias = {}
    for t in templates:
        cat = t.get('categoria', 'outro')
        if cat not in categorias:
            categorias[cat] = []
        categorias[cat].append(t)
    
    for categoria, lista in categorias.items():
        with st.expander(f"📁 {categoria.replace('_', ' ').title()} ({len(lista)})"):
            for template in lista:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.markdown(f"**{template['nome']}**")
                    st.caption(f"📱 {template['tipo_canal']} | {template['conteudo'][:50]}...")
                with col2:
                    canal_icon = {'whatsapp': '💬', 'email': '📧', 'sms': '📱'}.get(template['tipo_canal'], '📝')
                    st.write(canal_icon)
                with col3:
                    if st.button("✏️", key=f"edit_tpl_{template['id']}"):
                        st.session_state.template_edit = template['id']

def render_nova_campanha():
    """Renderiza criação de nova campanha/envio"""
    st.subheader("📤 Nova Campanha / Envio")
    
    templates = get_templates()
    if not templates:
        st.warning("Crie pelo menos um template antes de enviar mensagens.")
        return
    
    with st.form("form_campanha"):
        nome = st.text_input("Nome da campanha *")
        descricao = st.text_area("Descrição", height=60)
        
        col1, col2 = st.columns(2)
        with col1:
            template_opcoes = [(0, "Selecione...")] + [(t['id'], t['nome']) for t in templates]
            template_id = st.selectbox("Template",
                                       options=[t[0] for t in template_opcoes],
                                       format_func=lambda x: dict(template_opcoes).get(x, ''))
            
            segmento = st.selectbox("Segmento",
                                   options=['todos', 'visitantes', 'membros', 'lideres', 
                                           'aniversariantes', 'novo_convertido'])
        
        with col2:
            canal = st.selectbox("Canal de envio", options=['whatsapp', 'email', 'sms'])
        
        # Preview
        if template_id:
            template = get_template(template_id)
            if template:
                st.markdown("### 👁️ Preview")
                st.info(template['conteudo'])
        
        # Contagem de destinatários
        if segmento:
            destinatarios = get_pessoas_por_segmento(segmento)
            st.metric("Destinatários", len(destinatarios))
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("📤 Enviar Agora", use_container_width=True):
                if not nome or not template_id:
                    st.error("Preencha todos os campos obrigatórios!")
                else:
                    # Criar campanha
                    campanha_id = criar_campanha({
                        'nome': nome,
                        'descricao': descricao,
                        'template_id': template_id,
                        'tipo_canal': canal,
                        'segmentacao': segmento
                    })
                    
                    # Enviar mensagens
                    template = get_template(template_id)
                    destinatarios = get_pessoas_por_segmento(segmento)
                    
                    enviados = 0
                    for pessoa in destinatarios:
                        mensagem = processar_variaveis(template['conteudo'], pessoa)
                        
                        if canal == 'whatsapp' and pessoa.get('celular'):
                            if simular_envio_whatsapp(pessoa['celular'], mensagem):
                                enviar_mensagem(pessoa['id'], canal, mensagem, campanha_id)
                                enviados += 1
                        elif canal == 'email' and pessoa.get('email'):
                            if simular_envio_email(pessoa['email'], template.get('assunto', ''), mensagem):
                                enviar_mensagem(pessoa['id'], canal, mensagem, campanha_id)
                                enviados += 1
                    
                    # Atualizar contagem
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE campanhas SET status = 'enviada', total_enviados = ?, data_envio = ?
                            WHERE id = ?
                        ''', (enviados, datetime.now(), campanha_id))
                    
                    st.success(f"✅ Campanha enviada! {enviados} mensagens processadas.")
                    st.rerun()
        
        with col2:
            st.form_submit_button("📅 Agendar", use_container_width=True, disabled=True)

def render_historico_campanhas():
    """Renderiza histórico de campanhas"""
    st.subheader("📊 Histórico de Campanhas")
    
    campanhas = get_campanhas()
    
    if not campanhas:
        st.info("Nenhuma campanha realizada.")
        return
    
    for campanha in campanhas:
        status_cor = {
            'rascunho': '🟡',
            'agendada': '🔵',
            'enviada': '🟢',
            'cancelada': '🔴'
        }.get(campanha['status'], '⚪')
        
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
            
            with col1:
                st.markdown(f"**{campanha['nome']}**")
                st.caption(f"📝 {campanha.get('template_nome', 'N/A')}")
            
            with col2:
                st.write(f"{status_cor} {campanha['status'].title()}")
                if campanha['data_envio']:
                    st.caption(f"📅 {formatar_data_br(campanha['data_envio'])}")
            
            with col3:
                st.metric("Enviados", campanha['total_enviados'])
            
            with col4:
                st.metric("Abertos", campanha['total_abertos'])
        
        st.markdown("<hr style='margin: 0.5rem 0; opacity: 0.2;'>", unsafe_allow_html=True)

def render_envio_individual():
    """Renderiza envio individual de mensagem"""
    st.subheader("💬 Envio Individual")
    
    igreja_id = get_igreja_id()
    
    # Buscar pessoas
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, nome, celular, email FROM pessoas
            WHERE igreja_id = ? AND ativo = 1
            ORDER BY nome
        ''', (igreja_id,))
        pessoas = [dict(row) for row in cursor.fetchall()]
    
    if not pessoas:
        st.info("Nenhuma pessoa cadastrada.")
        return
    
    pessoa_opcoes = [(0, "Selecione...")] + [(p['id'], f"{p['nome']} ({p.get('celular', 'sem celular')})") for p in pessoas]
    
    with st.form("form_envio_individual"):
        pessoa_id = st.selectbox("Destinatário",
                                options=[p[0] for p in pessoa_opcoes],
                                format_func=lambda x: dict(pessoa_opcoes).get(x, ''))
        
        canal = st.selectbox("Canal", options=['whatsapp', 'email', 'sms'])
        
        # Templates rápidos
        templates = get_templates()
        template_opcoes = [(0, "Mensagem personalizada")] + [(t['id'], t['nome']) for t in templates]
        template_id = st.selectbox("Template (opcional)",
                                  options=[t[0] for t in template_opcoes],
                                  format_func=lambda x: dict(template_opcoes).get(x, ''))
        
        mensagem = st.text_area("Mensagem", height=100)
        
        if st.form_submit_button("📤 Enviar", use_container_width=True):
            if not pessoa_id or not mensagem:
                st.error("Selecione um destinatário e escreva a mensagem!")
            else:
                pessoa = next((p for p in pessoas if p['id'] == pessoa_id), None)
                if pessoa:
                    if canal == 'whatsapp' and pessoa.get('celular'):
                        simular_envio_whatsapp(pessoa['celular'], mensagem)
                        enviar_mensagem(pessoa_id, canal, mensagem)
                        st.success(f"✅ Mensagem enviada para {pessoa['nome']}!")
                        st.rerun()
                    elif canal == 'email' and pessoa.get('email'):
                        simular_envio_email(pessoa['email'], "Mensagem", mensagem)
                        enviar_mensagem(pessoa_id, canal, mensagem)
                        st.success(f"✅ E-mail enviado para {pessoa['nome']}!")
                        st.rerun()
                    else:
                        st.error(f"A pessoa não tem {canal} cadastrado!")

def render_comunicacao():
    """Função principal do módulo de comunicação"""
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Nova Campanha", "📝 Templates", "💬 Individual", "📊 Histórico"])
    
    with tab1:
        render_nova_campanha()
    
    with tab2:
        render_templates()
    
    with tab3:
        render_envio_individual()
    
    with tab4:
        render_historico_campanhas()
