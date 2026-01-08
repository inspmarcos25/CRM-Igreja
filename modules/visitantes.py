"""
Módulo de Visitantes & Follow-up
Check-in rápido e acompanhamento de visitantes
Com integração WhatsApp, Dashboard visual e Alertas
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import qrcode
from io import BytesIO
import base64
import urllib.parse
from database.db import get_connection
from modules.auth import get_igreja_id, get_usuario_atual, registrar_log
from modules.pessoas import salvar_pessoa
from config.settings import formatar_data_br

# ==================== UTILITÁRIOS ====================

def gerar_qrcode(dados: str) -> str:
    """Gera QR Code e retorna como base64"""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(dados)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

def gerar_link_whatsapp(telefone: str, mensagem: str) -> str:
    """Gera link para enviar mensagem via WhatsApp"""
    # Limpar telefone (remover caracteres não numéricos)
    telefone_limpo = ''.join(filter(str.isdigit, telefone))
    
    # Adicionar código do Brasil se não tiver
    if len(telefone_limpo) <= 11:
        telefone_limpo = '55' + telefone_limpo
    
    # Codificar mensagem para URL
    mensagem_encoded = urllib.parse.quote(mensagem)
    
    return f"https://wa.me/{telefone_limpo}?text={mensagem_encoded}"

def get_templates_mensagem() -> dict:
    """Retorna templates de mensagens para WhatsApp"""
    return {
        'boas_vindas': """🙏 Olá {nome}!

É uma grande alegria ter recebido você em nossa igreja! Esperamos que tenha se sentido acolhido(a).

Se tiver qualquer dúvida ou precisar de algo, estamos à disposição.

Que Deus abençoe sua semana! 🙌

- Equipe de Recepção""",

        'convite_retorno': """🙏 Olá {nome}!

Sentimos sua falta! Já faz {dias} dias desde sua última visita.

Gostaríamos muito de revê-lo(a) em nossos cultos:
📅 Domingos: 9h e 19h
📅 Quartas: 19h30

Será um prazer recebê-lo(a) novamente!

Um abraço carinhoso! ❤️""",

        'convite_celula': """🙏 Olá {nome}!

Que bom que você tem nos visitado! 

Gostaria de convidá-lo(a) para participar de uma de nossas células (grupos pequenos). É uma ótima oportunidade para fazer amizades e crescer na fé!

Posso te passar mais informações? 📱

Abraços!""",

        'followup_primeiro': """🙏 Olá {nome}!

Tudo bem? Passando para saber como você está e se tem alguma dúvida sobre nossa igreja.

Foi muito bom ter você conosco! 😊

Se precisar de oração ou quiser conversar, estou à disposição.

Abraços!""",

        'aniversario': """🎂 Feliz Aniversário, {nome}! 🎉

Que Deus abençoe abundantemente sua vida neste novo ano!

Que seus sonhos se realizem e que você continue crescendo em graça e conhecimento.

Um forte abraço da família {igreja}! ❤️"""
    }

def enviar_whatsapp(telefone: str, mensagem: str, nome_pessoa: str = "") -> str:
    """Prepara envio de mensagem WhatsApp e retorna o link"""
    # Personalizar mensagem se tiver nome
    if nome_pessoa and "{nome}" in mensagem:
        mensagem = mensagem.replace("{nome}", nome_pessoa)
    
    return gerar_link_whatsapp(telefone, mensagem)

def registrar_visita(pessoa_id: int, evento_id: int = None, tipo_culto: str = None, como_conheceu: str = None):
    """Registra uma visita"""
    igreja_id = get_igreja_id()
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO visitas (pessoa_id, evento_id, data_visita, tipo_culto, como_conheceu, responsavel_recepcao_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (pessoa_id, evento_id, date.today(), tipo_culto, como_conheceu, usuario.get('pessoa_id')))
        
        # Criar follow-ups automáticos
        criar_followups_automaticos(pessoa_id)
        
        registrar_log(usuario['id'], igreja_id, 'visita.registrar', f"Visita registrada para pessoa {pessoa_id}")

def criar_followups_automaticos(pessoa_id: int):
    """Cria follow-ups automáticos baseados nos fluxos configurados"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Buscar fluxos ativos
        cursor.execute('''
            SELECT * FROM fluxos_followup
            WHERE igreja_id = ? AND ativo = 1 AND trigger_evento = 'primeira_visita'
        ''', (igreja_id,))
        fluxos = cursor.fetchall()
        
        for fluxo in fluxos:
            data_prevista = date.today() + timedelta(days=fluxo['dias_apos_trigger'])
            cursor.execute('''
                INSERT INTO followup (pessoa_id, tipo, data_prevista, observacoes)
                VALUES (?, ?, ?, ?)
            ''', (pessoa_id, fluxo['nome'], data_prevista, fluxo['template_mensagem']))

def get_visitantes_recentes(dias: int = 30) -> list:
    """Busca visitantes dos últimos X dias"""
    igreja_id = get_igreja_id()
    data_inicio = date.today() - timedelta(days=dias)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.*, v.data_visita, v.tipo_culto, v.como_conheceu,
                   COUNT(v2.id) as total_visitas
            FROM pessoas p
            JOIN visitas v ON p.id = v.pessoa_id
            LEFT JOIN visitas v2 ON p.id = v2.pessoa_id
            WHERE p.igreja_id = ? AND p.status = 'visitante'
            AND v.data_visita >= ?
            GROUP BY p.id
            ORDER BY v.data_visita DESC
        ''', (igreja_id, data_inicio))
        return [dict(row) for row in cursor.fetchall()]

def get_followups_pendentes() -> list:
    """Busca follow-ups pendentes"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT f.*, p.nome as pessoa_nome, p.celular, p.email,
                   r.nome as responsavel_nome
            FROM followup f
            JOIN pessoas p ON f.pessoa_id = p.id
            LEFT JOIN pessoas r ON f.responsavel_id = r.id
            WHERE p.igreja_id = ? AND f.status = 'pendente'
            ORDER BY f.data_prevista ASC
        ''', (igreja_id,))
        return [dict(row) for row in cursor.fetchall()]

def atualizar_followup(followup_id: int, status: str, resultado: str = None):
    """Atualiza status de um follow-up"""
    usuario = get_usuario_atual()
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE followup
            SET status = ?, resultado = ?, data_realizada = ?, responsavel_id = ?
            WHERE id = ?
        ''', (status, resultado, datetime.now(), usuario.get('pessoa_id'), followup_id))
        
        registrar_log(usuario['id'], igreja_id, 'followup.atualizar', f"Follow-up {followup_id} atualizado para {status}")

def get_relatorio_conversao() -> dict:
    """Gera relatório de conversão de visitantes"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Total de visitantes
        cursor.execute('''
            SELECT COUNT(*) FROM pessoas WHERE igreja_id = ? AND status = 'visitante'
        ''', (igreja_id,))
        total_visitantes = cursor.fetchone()[0]
        
        # Novos convertidos (nos últimos 90 dias)
        cursor.execute('''
            SELECT COUNT(*) FROM pessoas 
            WHERE igreja_id = ? AND status = 'novo_convertido'
            AND data_conversao >= date('now', '-90 days')
        ''', (igreja_id,))
        novos_convertidos = cursor.fetchone()[0]
        
        # Em integração
        cursor.execute('''
            SELECT COUNT(*) FROM pessoas 
            WHERE igreja_id = ? AND status = 'em_integracao'
        ''', (igreja_id,))
        em_integracao = cursor.fetchone()[0]
        
        # Membros (que vieram de visitantes nos últimos 12 meses)
        cursor.execute('''
            SELECT COUNT(*) FROM pessoas 
            WHERE igreja_id = ? AND status = 'membro'
            AND data_membresia >= date('now', '-365 days')
        ''', (igreja_id,))
        tornaram_membros = cursor.fetchone()[0]
        
        # Visitantes por mês (últimos 6 meses)
        cursor.execute('''
            SELECT strftime('%Y-%m', data_visita) as mes, COUNT(DISTINCT pessoa_id) as total
            FROM visitas v
            JOIN pessoas p ON v.pessoa_id = p.id
            WHERE p.igreja_id = ?
            AND data_visita >= date('now', '-180 days')
            GROUP BY mes
            ORDER BY mes
        ''', (igreja_id,))
        visitantes_por_mes = [dict(row) for row in cursor.fetchall()]
        
        # Visitantes por fonte de conhecimento
        cursor.execute('''
            SELECT como_conheceu, COUNT(*) as total
            FROM pessoas
            WHERE igreja_id = ? AND como_conheceu IS NOT NULL AND como_conheceu != ''
            GROUP BY como_conheceu
            ORDER BY total DESC
        ''', (igreja_id,))
        por_fonte = [dict(row) for row in cursor.fetchall()]
        
        # Taxa de retorno (visitantes que vieram mais de uma vez)
        cursor.execute('''
            SELECT COUNT(DISTINCT pessoa_id) 
            FROM (
                SELECT pessoa_id, COUNT(*) as visitas
                FROM visitas v
                JOIN pessoas p ON v.pessoa_id = p.id
                WHERE p.igreja_id = ?
                GROUP BY pessoa_id
                HAVING visitas > 1
            )
        ''', (igreja_id,))
        retornaram = cursor.fetchone()[0]
        
        # Total que visitou
        cursor.execute('''
            SELECT COUNT(DISTINCT v.pessoa_id)
            FROM visitas v
            JOIN pessoas p ON v.pessoa_id = p.id
            WHERE p.igreja_id = ?
        ''', (igreja_id,))
        total_que_visitou = cursor.fetchone()[0]
        
        return {
            'total_visitantes': total_visitantes,
            'novos_convertidos': novos_convertidos,
            'em_integracao': em_integracao,
            'tornaram_membros': tornaram_membros,
            'visitantes_por_mes': visitantes_por_mes,
            'por_fonte': por_fonte,
            'retornaram': retornaram,
            'total_que_visitou': total_que_visitou,
            'taxa_conversao': (tornaram_membros / total_visitantes * 100) if total_visitantes > 0 else 0,
            'taxa_retorno': (retornaram / total_que_visitou * 100) if total_que_visitou > 0 else 0
        }

def get_visitantes_nao_retornaram(dias_minimo: int = 14) -> list:
    """Busca visitantes que não voltaram após X dias"""
    igreja_id = get_igreja_id()
    data_limite = date.today() - timedelta(days=dias_minimo)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.*, 
                   MAX(v.data_visita) as ultima_visita,
                   COUNT(v.id) as total_visitas,
                   julianday('now') - julianday(MAX(v.data_visita)) as dias_ausente
            FROM pessoas p
            JOIN visitas v ON p.id = v.pessoa_id
            WHERE p.igreja_id = ? 
            AND p.status = 'visitante'
            GROUP BY p.id
            HAVING MAX(v.data_visita) <= ?
            ORDER BY dias_ausente DESC
        ''', (igreja_id, data_limite))
        return [dict(row) for row in cursor.fetchall()]

def get_estatisticas_funil() -> dict:
    """Retorna estatísticas detalhadas do funil de conversão"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Etapas do funil
        etapas = {
            'visitante': 0,
            'novo_convertido': 0,
            'em_integracao': 0,
            'membro': 0
        }
        
        for status in etapas.keys():
            cursor.execute('''
                SELECT COUNT(*) FROM pessoas 
                WHERE igreja_id = ? AND status = ?
            ''', (igreja_id, status))
            etapas[status] = cursor.fetchone()[0]
        
        # Conversões por mês (últimos 6 meses)
        cursor.execute('''
            SELECT strftime('%Y-%m', data_conversao) as mes,
                   COUNT(*) as conversoes
            FROM pessoas
            WHERE igreja_id = ? 
            AND data_conversao >= date('now', '-180 days')
            AND data_conversao IS NOT NULL
            GROUP BY mes
            ORDER BY mes
        ''', (igreja_id,))
        conversoes_mes = [dict(row) for row in cursor.fetchall()]
        
        # Tempo médio de conversão (visitante -> membro)
        cursor.execute('''
            SELECT AVG(julianday(data_membresia) - julianday(data_primeira_visita)) as tempo_medio
            FROM pessoas
            WHERE igreja_id = ?
            AND data_membresia IS NOT NULL
            AND data_primeira_visita IS NOT NULL
        ''', (igreja_id,))
        result = cursor.fetchone()
        tempo_medio = result['tempo_medio'] if result and result['tempo_medio'] else 0
        
        return {
            'etapas': etapas,
            'conversoes_mes': conversoes_mes,
            'tempo_medio_conversao': tempo_medio
        }

def render_checkin_rapido():
    """Renderiza formulário de check-in rápido de visitantes - COMPLETO"""
    st.subheader("⚡ Check-in Rápido de Visitante")
    
    # QR Code para check-in self-service
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        padding: 1.5rem; border-radius: 10px; margin-bottom: 1rem; color: white;'>
                <h4>📱 Formulário de Visitante</h4>
                <p>Preencha os dados abaixo para registrar um novo visitante:</p>
            </div>
        """, unsafe_allow_html=True)
        
        with st.form("checkin_visitante"):
            st.markdown("##### 📋 Dados Pessoais")
            
            nome = st.text_input("Nome completo *", placeholder="Digite o nome completo")
            
            col_a, col_b = st.columns(2)
            with col_a:
                celular = st.text_input("WhatsApp/Celular *", placeholder="(00) 00000-0000")
            with col_b:
                email = st.text_input("E-mail", placeholder="email@exemplo.com")
            
            col_c, col_d = st.columns(2)
            with col_c:
                data_nascimento = st.date_input(
                    "Data de Nascimento",
                    value=None,
                    format="DD/MM/YYYY",
                    min_value=date(1920, 1, 1),
                    max_value=date.today()
                )
            with col_d:
                sexo = st.selectbox("Sexo", options=['', 'Masculino', 'Feminino'])
            
            st.markdown("##### 🏠 Endereço")
            
            col_e, col_f = st.columns([3, 1])
            with col_e:
                endereco = st.text_input("Endereço", placeholder="Rua, número, complemento")
            with col_f:
                cep = st.text_input("CEP", placeholder="00000-000")
            
            col_g, col_h = st.columns(2)
            with col_g:
                bairro = st.text_input("Bairro")
            with col_h:
                cidade = st.text_input("Cidade")
            
            st.markdown("##### ⛪ Informações da Visita")
            
            col_i, col_j = st.columns(2)
            with col_i:
                como_conheceu = st.selectbox(
                    "Como conheceu nossa igreja?",
                    options=['', 'Convite de amigo/familiar', 'Redes sociais (Instagram, Facebook)', 
                            'YouTube', 'Passou em frente', 'Google/Internet', 'Evento especial', 
                            'Indicação de membro', 'Panfleto/Banner', 'Outro']
                )
            with col_j:
                tipo_culto = st.selectbox(
                    "Qual culto/evento está participando?",
                    options=['Culto Dominical Manhã', 'Culto Dominical Noite', 
                            'Culto de Oração (Quarta)', 'Culto de Jovens', 'Culto de Mulheres',
                            'Culto de Homens', 'Célula', 'Evento Especial', 'Outro']
                )
            
            # Quem convidou
            quem_convidou = st.text_input(
                "Quem te convidou? (nome do membro)",
                placeholder="Nome de quem fez o convite"
            )
            
            st.markdown("##### 🙏 Informações Espirituais")
            
            col_k, col_l = st.columns(2)
            with col_k:
                ja_frequentou_igreja = st.selectbox(
                    "Já frequentou outra igreja?",
                    options=['', 'Sim, frequento outra atualmente', 'Sim, mas não frequento mais', 
                            'Nunca frequentei igreja', 'Esta é minha primeira vez']
                )
            with col_l:
                batizado = st.selectbox(
                    "É batizado nas águas?",
                    options=['', 'Sim', 'Não', 'Desejo me batizar']
                )
            
            col_m, col_n = st.columns(2)
            with col_m:
                estado_civil = st.selectbox(
                    "Estado Civil",
                    options=['', 'Solteiro(a)', 'Casado(a)', 'Divorciado(a)', 'Viúvo(a)', 'União Estável']
                )
            with col_n:
                tem_filhos = st.selectbox(
                    "Tem filhos?",
                    options=['', 'Não', 'Sim, 1 filho', 'Sim, 2 filhos', 'Sim, 3 ou mais filhos']
                )
            
            st.markdown("##### 📝 Observações e Pedidos")
            
            pedido_oracao = st.text_area(
                "Pedido de Oração (opcional)",
                placeholder="Compartilhe seu pedido de oração...",
                height=80
            )
            
            interesses = st.multiselect(
                "Gostaria de saber mais sobre:",
                options=['Batismo', 'Células/Grupos pequenos', 'Ministério de Louvor', 
                        'Ministério Infantil', 'Ministério de Jovens', 'Ministério de Casais',
                        'Cursos e Discipulado', 'Ação Social', 'Escola Bíblica']
            )
            
            observacoes = st.text_area(
                "Observações adicionais",
                placeholder="Outras informações relevantes...",
                height=60
            )
            
            st.markdown("---")
            
            col_aceite1, col_aceite2 = st.columns(2)
            with col_aceite1:
                aceite_lgpd = st.checkbox(
                    "Concordo com o tratamento dos meus dados pessoais conforme a LGPD"
                )
            with col_aceite2:
                aceite_whatsapp = st.checkbox(
                    "Desejo receber mensagens por WhatsApp",
                    value=True
                )
            
            submit = st.form_submit_button("✅ Registrar Visita", use_container_width=True, type="primary")
            
            if submit:
                if not nome or not celular:
                    st.error("⚠️ Nome e celular são obrigatórios!")
                elif not aceite_lgpd:
                    st.error("⚠️ É necessário aceitar os termos de uso dos dados.")
                else:
                    # Criar pessoa com todos os dados
                    pessoa_data = {
                        'nome': nome,
                        'celular': celular,
                        'email': email,
                        'data_nascimento': data_nascimento,
                        'sexo': sexo,
                        'endereco': endereco,
                        'cep': cep,
                        'bairro': bairro,
                        'cidade': cidade,
                        'como_conheceu': como_conheceu,
                        'quem_convidou': quem_convidou,
                        'batizado': batizado == 'Sim',
                        'estado_civil': estado_civil,
                        'status': 'visitante',
                        'data_primeira_visita': date.today(),
                        'aceita_whatsapp': aceite_whatsapp,
                        'observacoes': observacoes
                    }
                    
                    pessoa_id = salvar_pessoa(pessoa_data)
                    
                    # Registrar visita
                    registrar_visita(pessoa_id, tipo_culto=tipo_culto, como_conheceu=como_conheceu)
                    
                    # Salvar pedido de oração se houver
                    if pedido_oracao:
                        salvar_pedido_oracao(pessoa_id, pedido_oracao)
                    
                    # Salvar interesses
                    if interesses:
                        salvar_interesses_visitante(pessoa_id, interesses)
                    
                    st.success(f"✅ Visitante {nome} registrado com sucesso!")
                    
                    # Oferecer envio de WhatsApp de boas-vindas
                    if aceite_whatsapp and celular:
                        st.session_state.novo_visitante_whatsapp = {
                            'nome': nome,
                            'celular': celular
                        }
                    
                    st.balloons()
                    st.rerun()
    
    with col2:
        st.markdown("""
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        padding: 1.5rem; border-radius: 10px; color: white; text-align: center;'>
                <h4>📲 QR Code Self-Service</h4>
                <p style='font-size: 0.9rem;'>Visitante pode escanear e preencher os dados pelo celular</p>
            </div>
        """, unsafe_allow_html=True)
        
        # Gerar QR Code (em produção, apontaria para URL do formulário)
        qr_url = "https://crmigreja.app/checkin/demo"
        qr_img = gerar_qrcode(qr_url)
        st.image(qr_img, width=200)
        st.caption("Escaneie para check-in")
        
        st.markdown("---")
        
        # Mostrar opção de enviar WhatsApp para novo visitante
        if 'novo_visitante_whatsapp' in st.session_state:
            visitante = st.session_state.novo_visitante_whatsapp
            st.markdown(f"""
                <div style='background: #25D366; padding: 1rem; border-radius: 10px; 
                            color: white; text-align: center; margin-bottom: 1rem;'>
                    <h5>📱 Enviar Boas-vindas</h5>
                    <p style='font-size: 0.85rem;'>Envie uma mensagem de boas-vindas para {visitante['nome']}</p>
                </div>
            """, unsafe_allow_html=True)
            
            templates = get_templates_mensagem()
            link = enviar_whatsapp(visitante['celular'], templates['boas_vindas'], visitante['nome'])
            
            st.markdown(f"""
                <a href="{link}" target="_blank" style="
                    display: inline-block;
                    background: #25D366;
                    color: white;
                    padding: 0.5rem 1rem;
                    border-radius: 8px;
                    text-decoration: none;
                    width: 100%;
                    text-align: center;
                ">📲 Abrir WhatsApp</a>
            """, unsafe_allow_html=True)
            
            if st.button("✓ Mensagem enviada", key="msg_enviada"):
                del st.session_state.novo_visitante_whatsapp
                st.rerun()
        
        # Estatísticas rápidas
        st.markdown("---")
        st.markdown("### 📊 Hoje")
        
        igreja_id = get_igreja_id()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM visitas v
                JOIN pessoas p ON v.pessoa_id = p.id
                WHERE p.igreja_id = ? AND v.data_visita = ?
            ''', (igreja_id, date.today()))
            visitas_hoje = cursor.fetchone()[0]
        
        st.metric("Visitas Registradas", visitas_hoje)

def salvar_pedido_oracao(pessoa_id: int, pedido: str):
    """Salva pedido de oração do visitante"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO pedidos_oracao (pessoa_id, igreja_id, pedido, data_pedido, status)
            VALUES (?, ?, ?, ?, 'ativo')
        ''', (pessoa_id, igreja_id, pedido, date.today()))

def salvar_interesses_visitante(pessoa_id: int, interesses: list):
    """Salva interesses do visitante"""
    with get_connection() as conn:
        cursor = conn.cursor()
        for interesse in interesses:
            cursor.execute('''
                INSERT INTO interesses_visitante (pessoa_id, interesse, data_registro)
                VALUES (?, ?, ?)
            ''', (pessoa_id, interesse, date.today()))

def render_lista_visitantes():
    """Renderiza lista de visitantes recentes com integração WhatsApp"""
    st.subheader("👋 Visitantes Recentes")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col2:
        dias = st.selectbox("Período", options=[7, 15, 30, 60, 90], 
                           format_func=lambda x: f"Últimos {x} dias")
    with col3:
        filtro_retorno = st.selectbox("Filtrar por", options=['Todos', 'Primeira visita', 'Retornaram'])
    
    visitantes = get_visitantes_recentes(dias)
    
    if filtro_retorno == 'Primeira visita':
        visitantes = [v for v in visitantes if v['total_visitas'] == 1]
    elif filtro_retorno == 'Retornaram':
        visitantes = [v for v in visitantes if v['total_visitas'] > 1]
    
    if not visitantes:
        st.info("Nenhum visitante no período selecionado.")
        return
    
    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de Visitantes", len(visitantes))
    col2.metric("Primeira Visita", len([v for v in visitantes if v['total_visitas'] == 1]))
    col3.metric("Retornaram", len([v for v in visitantes if v['total_visitas'] > 1]))
    taxa_retorno = len([v for v in visitantes if v['total_visitas'] > 1]) / len(visitantes) * 100 if visitantes else 0
    col4.metric("Taxa de Retorno", f"{taxa_retorno:.0f}%")
    
    st.markdown("---")
    
    # Ação em massa
    col_acao1, col_acao2 = st.columns([3, 1])
    with col_acao2:
        if st.button("📱 Enviar WhatsApp em massa", use_container_width=True):
            st.session_state.whatsapp_massa = True
    
    # Lista
    for visitante in visitantes:
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
            
            with col1:
                st.markdown(f"**{visitante['nome']}**")
                st.caption(f"📅 Visita: {formatar_data_br(visitante['data_visita'])}")
            
            with col2:
                if visitante['celular']:
                    st.write(f"📱 {visitante['celular']}")
                badge_visitas = "🟢" if visitante['total_visitas'] > 1 else "🟡"
                st.caption(f"{badge_visitas} {visitante['total_visitas']} visita(s)")
            
            with col3:
                if visitante['como_conheceu']:
                    st.caption(f"🔍 {visitante['como_conheceu']}")
            
            with col4:
                # Botões de ação
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if visitante['celular']:
                        templates = get_templates_mensagem()
                        link = enviar_whatsapp(visitante['celular'], templates['followup_primeiro'], visitante['nome'])
                        st.markdown(f"""
                            <a href="{link}" target="_blank" title="Enviar WhatsApp" style="
                                display: inline-block;
                                background: #25D366;
                                color: white;
                                padding: 0.3rem 0.6rem;
                                border-radius: 5px;
                                text-decoration: none;
                                font-size: 0.9rem;
                            ">📲</a>
                        """, unsafe_allow_html=True)
                with col_btn2:
                    if st.button("📋", key=f"detail_{visitante['id']}", help="Ver detalhes"):
                        st.session_state.ver_visitante = visitante['id']
        
        st.markdown("<hr style='margin: 0.5rem 0; opacity: 0.2;'>", unsafe_allow_html=True)

def render_alertas_visitantes():
    """Renderiza alertas de visitantes que não voltaram"""
    st.subheader("🚨 Alertas - Visitantes que Não Voltaram")
    
    col1, col2 = st.columns([3, 1])
    with col2:
        dias_minimo = st.selectbox(
            "Ausentes há mais de:",
            options=[7, 14, 21, 30, 45, 60],
            index=1,
            format_func=lambda x: f"{x} dias"
        )
    
    visitantes_ausentes = get_visitantes_nao_retornaram(dias_minimo)
    
    if not visitantes_ausentes:
        st.success("🎉 Nenhum visitante ausente neste período!")
        return
    
    # Métricas de alerta
    col1, col2, col3 = st.columns(3)
    col1.metric("🔴 Total Ausentes", len(visitantes_ausentes))
    col2.metric("⚠️ Críticos (+30 dias)", len([v for v in visitantes_ausentes if v['dias_ausente'] > 30]))
    col3.metric("📞 Com telefone", len([v for v in visitantes_ausentes if v.get('celular')]))
    
    st.markdown("---")
    
    # Classificar por urgência
    criticos = [v for v in visitantes_ausentes if v['dias_ausente'] > 30]
    atencao = [v for v in visitantes_ausentes if 14 < v['dias_ausente'] <= 30]
    recentes = [v for v in visitantes_ausentes if v['dias_ausente'] <= 14]
    
    # Ação em massa
    st.markdown("### 📱 Ações em Massa")
    col_a1, col_a2, col_a3 = st.columns(3)
    
    with col_a1:
        if st.button("📲 WhatsApp para todos críticos", use_container_width=True, type="primary"):
            st.info(f"Preparando mensagens para {len(criticos)} visitantes críticos...")
            st.session_state.whatsapp_lista = criticos
    
    with col_a2:
        if st.button("📲 WhatsApp para atenção", use_container_width=True):
            st.info(f"Preparando mensagens para {len(atencao)} visitantes...")
            st.session_state.whatsapp_lista = atencao
    
    st.markdown("---")
    
    # Lista de críticos
    if criticos:
        st.markdown("### 🔴 Críticos (mais de 30 dias)")
        for v in criticos[:10]:
            render_card_visitante_ausente(v, 'critico')
    
    # Lista de atenção
    if atencao:
        st.markdown("### 🟡 Atenção (14-30 dias)")
        for v in atencao[:10]:
            render_card_visitante_ausente(v, 'atencao')
    
    # Mostrar lista para WhatsApp se selecionada
    if 'whatsapp_lista' in st.session_state:
        st.markdown("---")
        st.markdown("### 📱 Enviar Mensagens")
        
        templates = get_templates_mensagem()
        
        for v in st.session_state.whatsapp_lista:
            if v.get('celular'):
                dias = int(v['dias_ausente']) if v['dias_ausente'] else 0
                mensagem = templates['convite_retorno'].replace('{dias}', str(dias))
                link = enviar_whatsapp(v['celular'], mensagem, v['nome'])
                
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{v['nome']}** - {v['celular']} ({dias} dias ausente)")
                with col2:
                    st.markdown(f"""
                        <a href="{link}" target="_blank" style="
                            display: inline-block;
                            background: #25D366;
                            color: white;
                            padding: 0.3rem 0.8rem;
                            border-radius: 5px;
                            text-decoration: none;
                        ">📲 Enviar</a>
                    """, unsafe_allow_html=True)
        
        if st.button("✓ Concluído", key="limpar_lista"):
            del st.session_state.whatsapp_lista
            st.rerun()

def render_card_visitante_ausente(visitante: dict, tipo: str):
    """Renderiza card de visitante ausente"""
    cores = {'critico': '#ffebee', 'atencao': '#fff8e1', 'recente': '#e8f5e9'}
    icones = {'critico': '🔴', 'atencao': '🟡', 'recente': '🟢'}
    
    dias = int(visitante['dias_ausente']) if visitante['dias_ausente'] else 0
    
    with st.container():
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
        
        with col1:
            st.markdown(f"{icones[tipo]} **{visitante['nome']}**")
            st.caption(f"Última visita: {formatar_data_br(visitante['ultima_visita'])}")
        
        with col2:
            st.write(f"📱 {visitante.get('celular', 'N/A')}")
            st.caption(f"{visitante['total_visitas']} visita(s) no total")
        
        with col3:
            st.metric("Dias Ausente", dias, delta=None)
        
        with col4:
            if visitante.get('celular'):
                templates = get_templates_mensagem()
                mensagem = templates['convite_retorno'].replace('{dias}', str(dias))
                link = enviar_whatsapp(visitante['celular'], mensagem, visitante['nome'])
                st.markdown(f"""
                    <a href="{link}" target="_blank" style="
                        display: inline-block;
                        background: #25D366;
                        color: white;
                        padding: 0.4rem 0.8rem;
                        border-radius: 5px;
                        text-decoration: none;
                    ">📲 WhatsApp</a>
                """, unsafe_allow_html=True)
    
    st.markdown("<hr style='margin: 0.3rem 0; opacity: 0.15;'>", unsafe_allow_html=True)

def render_followups():
    """Renderiza gestão de follow-ups"""
    st.subheader("📋 Follow-up de Visitantes")
    
    tab1, tab2 = st.tabs(["⏳ Pendentes", "✅ Realizados"])
    
    with tab1:
        followups = get_followups_pendentes()
        
        if not followups:
            st.success("🎉 Nenhum follow-up pendente!")
            return
        
        # Separar por urgência
        hoje = date.today()
        atrasados = [f for f in followups if f['data_prevista'] and f['data_prevista'] < str(hoje)]
        para_hoje = [f for f in followups if f['data_prevista'] and f['data_prevista'] == str(hoje)]
        proximos = [f for f in followups if f['data_prevista'] and f['data_prevista'] > str(hoje)]
        
        if atrasados:
            st.markdown("### 🔴 Atrasados")
            for f in atrasados:
                render_followup_card(f, "atrasado")
        
        if para_hoje:
            st.markdown("### 🟡 Para Hoje")
            for f in para_hoje:
                render_followup_card(f, "hoje")
        
        if proximos:
            st.markdown("### 🟢 Próximos")
            for f in proximos[:10]:
                render_followup_card(f, "proximo")
    
    with tab2:
        st.info("Histórico de follow-ups realizados")

def render_followup_card(followup: dict, urgencia: str):
    """Renderiza card de follow-up com integração WhatsApp"""
    cores = {"atrasado": "#ffebee", "hoje": "#fff8e1", "proximo": "#e8f5e9"}
    
    with st.container():
        st.markdown(f"""
            <div style='background: {cores[urgencia]}; padding: 1rem; border-radius: 8px; margin-bottom: 0.5rem;'>
                <strong>{followup['pessoa_nome']}</strong> - {followup['tipo']}<br>
                <small>📅 {formatar_data_br(followup['data_prevista'])} | 📱 {followup.get('celular', 'N/A')}</small>
            </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("✅ Realizado", key=f"done_{followup['id']}"):
                atualizar_followup(followup['id'], 'realizado')
                st.rerun()
        with col2:
            if st.button("📅 Remarcar", key=f"reschedule_{followup['id']}"):
                pass
        with col3:
            if st.button("❌ Cancelar", key=f"cancel_{followup['id']}"):
                atualizar_followup(followup['id'], 'cancelado')
                st.rerun()
        with col4:
            # Botão WhatsApp
            if followup.get('celular'):
                templates = get_templates_mensagem()
                link = enviar_whatsapp(followup['celular'], templates['followup_primeiro'], followup['pessoa_nome'])
                st.markdown(f"""
                    <a href="{link}" target="_blank" style="
                        display: inline-block;
                        background: #25D366;
                        color: white;
                        padding: 0.3rem 0.6rem;
                        border-radius: 5px;
                        text-decoration: none;
                        font-size: 0.85rem;
                    ">📲 WhatsApp</a>
                """, unsafe_allow_html=True)

def render_dashboard_funil():
    """Renderiza dashboard visual do funil de conversão"""
    st.subheader("📊 Dashboard - Funil de Conversão")
    
    relatorio = get_relatorio_conversao()
    estatisticas = get_estatisticas_funil()
    
    # Métricas principais em cards coloridos
    st.markdown("""
        <style>
        .metric-card {
            padding: 1.5rem;
            border-radius: 10px;
            text-align: center;
            color: white;
            margin-bottom: 1rem;
        }
        .metric-value {
            font-size: 2.5rem;
            font-weight: bold;
            margin: 0.5rem 0;
        }
        .metric-label {
            font-size: 0.9rem;
            opacity: 0.9;
        }
        </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
            <div class="metric-card" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                <div class="metric-label">👋 Visitantes</div>
                <div class="metric-value">{relatorio['total_visitantes']}</div>
                <div class="metric-label">Total no sistema</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
            <div class="metric-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                <div class="metric-label">✨ Novos Convertidos</div>
                <div class="metric-value">{relatorio['novos_convertidos']}</div>
                <div class="metric-label">Últimos 90 dias</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
            <div class="metric-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
                <div class="metric-label">📚 Em Integração</div>
                <div class="metric-value">{relatorio['em_integracao']}</div>
                <div class="metric-label">Fazendo curso</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
            <div class="metric-card" style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);">
                <div class="metric-label">🎉 Membros</div>
                <div class="metric-value">{relatorio['tornaram_membros']}</div>
                <div class="metric-label">Últimos 12 meses</div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Gráficos lado a lado
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        st.markdown("### 🔄 Funil de Conversão")
        
        # Gráfico de funil
        etapas = estatisticas['etapas']
        fig_funil = go.Figure(go.Funnel(
            y=['Visitantes', 'Novos Convertidos', 'Em Integração', 'Membros'],
            x=[etapas['visitante'], etapas['novo_convertido'], etapas['em_integracao'], etapas['membro']],
            textinfo="value+percent initial",
            marker=dict(color=['#667eea', '#f093fb', '#4facfe', '#38ef7d']),
            connector=dict(line=dict(color="royalblue", dash="dot", width=3))
        ))
        
        fig_funil.update_layout(
            margin=dict(l=20, r=20, t=20, b=20),
            height=350,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        st.plotly_chart(fig_funil, use_container_width=True)
    
    with col_g2:
        st.markdown("### 📈 Visitantes por Mês")
        
        if relatorio['visitantes_por_mes']:
            df_visitantes = pd.DataFrame(relatorio['visitantes_por_mes'])
            
            fig_linha = px.area(
                df_visitantes,
                x='mes',
                y='total',
                labels={'mes': 'Mês', 'total': 'Visitantes'},
                color_discrete_sequence=['#667eea']
            )
            
            fig_linha.update_layout(
                margin=dict(l=20, r=20, t=20, b=20),
                height=350,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)')
            )
            
            st.plotly_chart(fig_linha, use_container_width=True)
        else:
            st.info("Sem dados de visitantes nos últimos 6 meses")
    
    st.markdown("---")
    
    # Segunda linha de gráficos
    col_g3, col_g4 = st.columns(2)
    
    with col_g3:
        st.markdown("### 🔍 Como Nos Conheceram")
        
        if relatorio['por_fonte']:
            df_fonte = pd.DataFrame(relatorio['por_fonte'])
            
            fig_pizza = px.pie(
                df_fonte,
                values='total',
                names='como_conheceu',
                color_discrete_sequence=px.colors.sequential.RdBu,
                hole=0.4
            )
            
            fig_pizza.update_layout(
                margin=dict(l=20, r=20, t=20, b=20),
                height=300,
                paper_bgcolor='rgba(0,0,0,0)',
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.3)
            )
            
            st.plotly_chart(fig_pizza, use_container_width=True)
        else:
            st.info("Sem dados de origem dos visitantes")
    
    with col_g4:
        st.markdown("### 📊 Indicadores de Performance")
        
        # KPIs em gauge charts
        col_kpi1, col_kpi2 = st.columns(2)
        
        with col_kpi1:
            fig_gauge1 = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=relatorio['taxa_conversao'],
                title={'text': "Taxa Conversão"},
                delta={'reference': 10},
                gauge={
                    'axis': {'range': [0, 100]},
                    'bar': {'color': "#38ef7d"},
                    'steps': [
                        {'range': [0, 30], 'color': "#ffebee"},
                        {'range': [30, 70], 'color': "#fff8e1"},
                        {'range': [70, 100], 'color': "#e8f5e9"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 90
                    }
                }
            ))
            fig_gauge1.update_layout(
                height=200,
                margin=dict(l=20, r=20, t=50, b=20),
                paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_gauge1, use_container_width=True)
        
        with col_kpi2:
            fig_gauge2 = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=relatorio['taxa_retorno'],
                title={'text': "Taxa Retorno"},
                delta={'reference': 30},
                gauge={
                    'axis': {'range': [0, 100]},
                    'bar': {'color': "#667eea"},
                    'steps': [
                        {'range': [0, 30], 'color': "#ffebee"},
                        {'range': [30, 70], 'color': "#fff8e1"},
                        {'range': [70, 100], 'color': "#e8f5e9"}
                    ]
                }
            ))
            fig_gauge2.update_layout(
                height=200,
                margin=dict(l=20, r=20, t=50, b=20),
                paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_gauge2, use_container_width=True)
        
        # Tempo médio de conversão
        tempo_medio = estatisticas['tempo_medio_conversao']
        st.markdown(f"""
            <div style='background: #f8f9fa; padding: 1rem; border-radius: 10px; text-align: center;'>
                <h4 style='margin: 0;'>⏱️ Tempo Médio de Conversão</h4>
                <p style='font-size: 1.5rem; font-weight: bold; color: #667eea; margin: 0.5rem 0;'>
                    {tempo_medio:.0f} dias
                </p>
                <small>Da primeira visita até se tornar membro</small>
            </div>
        """, unsafe_allow_html=True)

def render_visitantes():
    """Função principal do módulo de visitantes"""
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "⚡ Check-in", 
        "👋 Visitantes", 
        "🚨 Alertas",
        "📋 Follow-up", 
        "📊 Dashboard"
    ])
    
    with tab1:
        render_checkin_rapido()
    
    with tab2:
        render_lista_visitantes()
    
    with tab3:
        render_alertas_visitantes()
    
    with tab4:
        render_followups()
    
    with tab5:
        render_dashboard_funil()
