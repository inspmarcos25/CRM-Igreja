"""
Módulo de Notificações Inteligentes
Sistema de alertas e lembretes automatizados
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database.db import get_connection
from modules.auth import get_igreja_id, get_usuario_atual
from config.settings import formatar_data_br

# ==================== FUNÇÕES DE DADOS ====================

def get_notificacoes(lidas: bool = None, limite: int = 50) -> list:
    """Busca notificações do usuário"""
    usuario = get_usuario_atual()
    
    query = '''
        SELECT * FROM notificacoes
        WHERE usuario_id = ?
    '''
    params = [usuario['id']]
    
    if lidas is not None:
        query += ' AND lida = ?'
        params.append(1 if lidas else 0)
    
    query += ' ORDER BY data_criacao DESC LIMIT ?'
    params.append(limite)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def marcar_como_lida(notificacao_id: int):
    """Marca notificação como lida"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE notificacoes SET lida = 1, data_leitura = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (notificacao_id,))

def marcar_todas_lidas():
    """Marca todas as notificações como lidas"""
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE notificacoes SET lida = 1, data_leitura = CURRENT_TIMESTAMP
            WHERE usuario_id = ? AND lida = 0
        ''', (usuario['id'],))

def criar_notificacao(usuario_id: int, tipo: str, titulo: str, mensagem: str,
                      link: str = None, dados_extras: str = None):
    """Cria uma nova notificação"""
    igreja_id = get_igreja_id()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO notificacoes (igreja_id, usuario_id, tipo, titulo, mensagem, link, dados_extras)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (igreja_id, usuario_id, tipo, titulo, mensagem, link, dados_extras))

def contar_nao_lidas() -> int:
    """Conta notificações não lidas"""
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM notificacoes WHERE usuario_id = ? AND lida = 0
        ''', (usuario['id'],))
        return cursor.fetchone()[0]

def excluir_notificacao(notificacao_id: int):
    """Exclui uma notificação"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM notificacoes WHERE id = ?', (notificacao_id,))

def limpar_notificacoes_antigas(dias: int = 30):
    """Remove notificações antigas lidas"""
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM notificacoes
            WHERE usuario_id = ? AND lida = 1
            AND date(data_criacao) < date('now', ? || ' days')
        ''', (usuario['id'], f'-{dias}'))

# ==================== GERAÇÃO AUTOMÁTICA ====================

def gerar_alertas_automaticos():
    """Gera alertas automáticos baseados em eventos"""
    igreja_id = get_igreja_id()
    alertas = []
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Aniversariantes da semana
        cursor.execute('''
            SELECT id, nome, data_nascimento FROM pessoas
            WHERE igreja_id = ? AND data_nascimento IS NOT NULL
            AND strftime('%m-%d', data_nascimento) BETWEEN strftime('%m-%d', 'now')
            AND strftime('%m-%d', 'now', '+7 days')
        ''', (igreja_id,))
        aniversariantes = cursor.fetchall()
        
        for p in aniversariantes:
            alertas.append({
                'tipo': 'aniversario',
                'icone': '🎂',
                'titulo': f"Aniversário: {p['nome']}",
                'mensagem': f"Aniversário em {formatar_data_br(p['data_nascimento'])}",
                'prioridade': 'media'
            })
        
        # Membros ausentes (sem presença há mais de 30 dias)
        cursor.execute('''
            SELECT p.id, p.nome, MAX(pr.data) as ultima_presenca
            FROM pessoas p
            LEFT JOIN presencas pr ON p.id = pr.pessoa_id
            WHERE p.igreja_id = ? AND p.status = 'ativo'
            GROUP BY p.id
            HAVING ultima_presenca < date('now', '-30 days') OR ultima_presenca IS NULL
        ''', (igreja_id,))
        ausentes = cursor.fetchall()
        
        for p in ausentes:
            alertas.append({
                'tipo': 'ausencia',
                'icone': '⚠️',
                'titulo': f"Membro ausente: {p['nome']}",
                'mensagem': f"Última presença: {formatar_data_br(p['ultima_presenca']) if p['ultima_presenca'] else 'Nunca'}",
                'prioridade': 'alta'
            })
        
        # Visitantes sem retorno há mais de 7 dias
        cursor.execute('''
            SELECT v.id, v.nome, v.data_visita
            FROM visitantes v
            WHERE v.igreja_id = ? AND v.status = 'primeiro_contato'
            AND date(v.data_visita) < date('now', '-7 days')
        ''', (igreja_id,))
        visitantes = cursor.fetchall()
        
        for v in visitantes:
            alertas.append({
                'tipo': 'visitante',
                'icone': '👋',
                'titulo': f"Follow-up pendente: {v['nome']}",
                'mensagem': f"Visitou em {formatar_data_br(v['data_visita'])}",
                'prioridade': 'alta'
            })
        
        # Eventos próximos (próximos 7 dias)
        cursor.execute('''
            SELECT id, nome, data, horario FROM eventos
            WHERE igreja_id = ? AND date(data) BETWEEN date('now') AND date('now', '+7 days')
            ORDER BY data
        ''', (igreja_id,))
        eventos = cursor.fetchall()
        
        for e in eventos:
            alertas.append({
                'tipo': 'evento',
                'icone': '📅',
                'titulo': f"Evento: {e['nome']}",
                'mensagem': f"{formatar_data_br(e['data'])} às {e['horario'] or ''}",
                'prioridade': 'media'
            })
        
        # Metas próximas do prazo
        cursor.execute('''
            SELECT id, titulo, data_fim, 
                   CASE WHEN valor_meta > 0 THEN (valor_atual / valor_meta) * 100 ELSE 0 END as progresso
            FROM metas
            WHERE igreja_id = ? AND status = 'em_andamento'
            AND date(data_fim) BETWEEN date('now') AND date('now', '+14 days')
        ''', (igreja_id,))
        metas = cursor.fetchall()
        
        for m in metas:
            alertas.append({
                'tipo': 'meta',
                'icone': '🎯',
                'titulo': f"Meta vence em breve: {m['titulo']}",
                'mensagem': f"Prazo: {formatar_data_br(m['data_fim'])} | Progresso: {m['progresso']:.0f}%",
                'prioridade': 'alta' if m['progresso'] < 50 else 'media'
            })
    
    return alertas

def get_config_notificacoes() -> dict:
    """Busca configurações de notificação do usuário"""
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM config_notificacoes WHERE usuario_id = ?
        ''', (usuario['id'],))
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        
        # Criar configuração padrão
        cursor.execute('''
            INSERT INTO config_notificacoes (usuario_id)
            VALUES (?)
        ''', (usuario['id'],))
        conn.commit()
        
        return {
            'aniversarios': True,
            'ausencias': True,
            'visitantes': True,
            'eventos': True,
            'financeiro': True,
            'metas': True
        }

def salvar_config_notificacoes(config: dict):
    """Salva configurações de notificação"""
    usuario = get_usuario_atual()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE config_notificacoes
            SET aniversarios = ?, ausencias = ?, visitantes = ?,
                eventos = ?, financeiro = ?, metas = ?
            WHERE usuario_id = ?
        ''', (config['aniversarios'], config['ausencias'], config['visitantes'],
              config['eventos'], config['financeiro'], config['metas'],
              usuario['id']))

# ==================== RENDERIZAÇÃO ====================

def render_notificacoes():
    """Função principal do módulo de notificações"""
    st.title("🔔 Central de Notificações")
    
    nao_lidas = contar_nao_lidas()
    if nao_lidas > 0:
        st.info(f"📬 Você tem **{nao_lidas}** notificações não lidas")
    
    tab1, tab2, tab3 = st.tabs([
        "📥 Notificações",
        "⚡ Alertas Automáticos",
        "⚙️ Configurações"
    ])
    
    with tab1:
        render_lista_notificacoes()
    
    with tab2:
        render_alertas_automaticos()
    
    with tab3:
        render_configuracoes()

def render_lista_notificacoes():
    """Renderiza lista de notificações"""
    st.subheader("📥 Suas Notificações")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        filtro = st.radio("Filtrar", ['Todas', 'Não lidas', 'Lidas'], horizontal=True)
    
    with col2:
        if st.button("✓ Marcar todas como lidas"):
            marcar_todas_lidas()
            st.rerun()
    
    with col3:
        if st.button("🧹 Limpar antigas"):
            limpar_notificacoes_antigas(30)
            st.success("Notificações antigas removidas!")
            st.rerun()
    
    lidas = None if filtro == 'Todas' else (filtro == 'Lidas')
    notificacoes = get_notificacoes(lidas=lidas)
    
    if not notificacoes:
        st.info("📭 Nenhuma notificação encontrada.")
        return
    
    for notif in notificacoes:
        render_notificacao(notif)

def render_notificacao(notif: dict):
    """Renderiza uma notificação"""
    icones = {
        'aniversario': '🎂',
        'ausencia': '⚠️',
        'visitante': '👋',
        'evento': '📅',
        'financeiro': '💰',
        'meta': '🎯',
        'sistema': '🔔'
    }
    
    cor_fundo = '#fff3e0' if not notif['lida'] else '#f5f5f5'
    icone = icones.get(notif['tipo'], '🔔')
    
    with st.container():
        col1, col2, col3 = st.columns([0.5, 8, 1.5])
        
        with col1:
            st.write(icone)
        
        with col2:
            st.markdown(f"""
                <div style='background: {cor_fundo}; padding: 0.5rem; border-radius: 5px;'>
                    <strong>{notif['titulo']}</strong><br>
                    <small>{notif['mensagem']}</small><br>
                    <small style='color: #666;'>{formatar_data_br(str(notif['data_criacao'])[:10])}</small>
                </div>
            """, unsafe_allow_html=True)
        
        with col3:
            if not notif['lida']:
                if st.button("✓", key=f"ler_{notif['id']}"):
                    marcar_como_lida(notif['id'])
                    st.rerun()
            
            if st.button("🗑️", key=f"del_{notif['id']}"):
                excluir_notificacao(notif['id'])
                st.rerun()
        
        st.markdown("<hr style='margin: 0.3rem 0;'>", unsafe_allow_html=True)

def render_alertas_automaticos():
    """Renderiza alertas gerados automaticamente"""
    st.subheader("⚡ Alertas Automáticos")
    
    st.info("Os alertas abaixo são gerados automaticamente com base nos dados da igreja.")
    
    if st.button("🔄 Atualizar Alertas"):
        st.rerun()
    
    alertas = gerar_alertas_automaticos()
    
    if not alertas:
        st.success("✅ Nenhum alerta no momento!")
        return
    
    # Agrupar por tipo
    alertas_por_tipo = {}
    for alerta in alertas:
        tipo = alerta['tipo']
        if tipo not in alertas_por_tipo:
            alertas_por_tipo[tipo] = []
        alertas_por_tipo[tipo].append(alerta)
    
    # Ordenar por prioridade
    ordem_tipo = ['ausencia', 'visitante', 'meta', 'evento', 'aniversario']
    
    for tipo in ordem_tipo:
        if tipo not in alertas_por_tipo:
            continue
        
        alertas_tipo = alertas_por_tipo[tipo]
        
        titulos_tipo = {
            'aniversario': '🎂 Aniversariantes',
            'ausencia': '⚠️ Membros Ausentes',
            'visitante': '👋 Follow-up Pendente',
            'evento': '📅 Eventos Próximos',
            'meta': '🎯 Metas com Prazo'
        }
        
        with st.expander(f"{titulos_tipo.get(tipo, tipo)} ({len(alertas_tipo)})", expanded=(tipo in ['ausencia', 'visitante'])):
            for alerta in alertas_tipo:
                cor = '#ffebee' if alerta['prioridade'] == 'alta' else '#fff8e1' if alerta['prioridade'] == 'media' else '#f5f5f5'
                
                st.markdown(f"""
                    <div style='background: {cor}; padding: 0.5rem; border-radius: 5px; margin-bottom: 0.3rem;'>
                        <strong>{alerta['titulo']}</strong><br>
                        <small>{alerta['mensagem']}</small>
                    </div>
                """, unsafe_allow_html=True)

def render_configuracoes():
    """Renderiza configurações de notificação"""
    st.subheader("⚙️ Configurações de Notificações")
    
    config = get_config_notificacoes()
    
    st.write("Escolha quais tipos de alertas você deseja receber:")
    
    with st.form("config_notif"):
        col1, col2 = st.columns(2)
        
        with col1:
            aniversarios = st.checkbox("🎂 Aniversários", value=config.get('aniversarios', True))
            ausencias = st.checkbox("⚠️ Membros ausentes", value=config.get('ausencias', True))
            visitantes = st.checkbox("👋 Follow-up de visitantes", value=config.get('visitantes', True))
        
        with col2:
            eventos = st.checkbox("📅 Eventos próximos", value=config.get('eventos', True))
            financeiro = st.checkbox("💰 Alertas financeiros", value=config.get('financeiro', True))
            metas = st.checkbox("🎯 Metas próximas do prazo", value=config.get('metas', True))
        
        if st.form_submit_button("💾 Salvar Configurações"):
            salvar_config_notificacoes({
                'aniversarios': aniversarios,
                'ausencias': ausencias,
                'visitantes': visitantes,
                'eventos': eventos,
                'financeiro': financeiro,
                'metas': metas
            })
            st.success("✅ Configurações salvas!")

def render_badge_notificacoes():
    """Renderiza badge com contagem de notificações (para sidebar)"""
    nao_lidas = contar_nao_lidas()
    if nao_lidas > 0:
        return f"🔔 Notificações ({nao_lidas})"
    return "🔔 Notificações"
