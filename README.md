# CRM Igreja

Sistema de CRM (Customer Relationship Management) desenvolvido especialmente para igrejas, com foco em gestão de pessoas, relacionamento pastoral, ministérios, comunicação, eventos e indicadores estratégicos.

## 🚀 Funcionalidades

### 👥 Módulo de Pessoas (Core)
- Cadastro único de pessoas (visitantes, novos convertidos, membros)
- Dados pessoais e familiares
- Histórico completo (presenças, ministérios, doações, aconselhamentos)
- Funil de relacionamento automático

### 👋 Visitantes & Follow-up
- Check-in rápido (formulário ou QR Code)
- Fluxos automáticos de acompanhamento
- Alertas para líderes e pastores
- Relatório de conversão de visitantes

### ⛪ Ministérios, Células e Pequenos Grupos
- Cadastro de ministérios e células
- Gestão de líderes
- Frequência por encontro
- Relatórios de crescimento e engajamento

### 💬 Comunicação Integrada
- Templates de mensagens
- Segmentação inteligente
- Campanhas de comunicação
- Suporte a WhatsApp, E-mail, SMS

### 📅 Eventos & Presença
- Cadastro de eventos
- Inscrição online
- Check-in por QR Code
- Relatórios de presença

### 💰 Doações & Financeiro
- Registro de dízimos e ofertas
- Histórico por membro (acesso restrito)
- Relatórios mensais e anuais
- Dashboard financeiro

### 🙏 Aconselhamento Pastoral
- Registro de atendimentos pastorais
- Controle rigoroso de acesso
- Criptografia de dados sensíveis
- Conformidade com LGPD

### 📊 Dashboard & Indicadores
- Crescimento de membros
- Taxa de retenção
- Conversão de visitantes
- Saúde das células
- Doações por período

## 🔐 Segurança & LGPD

- **Controle de acesso por perfil (RBAC)**:
  - Administrador
  - Pastor
  - Líder de ministério/célula
  - Secretaria
  - Financeiro
  
- Logs de acesso
- Criptografia de dados sensíveis
- Consentimento explícito

## ⚙️ Instalação e uso local

### Pré-requisitos

- Python 3.10 ou superior
- pip (gerenciador de pacotes Python)

### Passos

1. Clone o repositório ou acesse a pasta do projeto:
```bash
cd CRMigreja
```

2. Crie e ative um ambiente virtual (recomendado):
```bash
python -m venv .venv
.\.venv\Scripts\activate  # Windows
# ou
source .venv/bin/activate  # Linux/Mac
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Execute o aplicativo Streamlit:
```bash
streamlit run app.py
```

5. Acesse no navegador: `http://localhost:8501`

### Comandos rápidos

- Atualizar dependências: `pip install -U -r requirements.txt`
- Limpar cache do Streamlit: `streamlit cache clear`
- Desativar o venv: `deactivate`

### Notas de execução

- O banco SQLite é criado em `data/crm_igreja.db`; a pasta `data/uploads/galeria` guarda imagens enviadas.
- Evite abrir múltiplas instâncias de edição que escrevam no banco ao mesmo tempo para reduzir "database is locked".
- Warnings de `use_container_width` são do Streamlit; atualize componentes conforme necessário nas telas de dashboard.

## 🔑 Acesso Demo

- **E-mail**: admin@demo.com
- **Senha**: admin123

## 📁 Estrutura do Projeto

```
CRMigreja/
├── app.py                 # Aplicativo principal
├── requirements.txt       # Dependências
├── README.md             # Documentação
├── config/
│   ├── __init__.py
│   └── settings.py       # Configurações
├── database/
│   ├── __init__.py
│   └── db.py             # Banco de dados SQLite
├── modules/
│   ├── __init__.py
│   ├── auth.py           # Autenticação e RBAC
│   ├── dashboard.py      # Dashboard e indicadores
│   ├── pessoas.py        # Módulo de pessoas
│   ├── visitantes.py     # Visitantes e follow-up
│   ├── ministerios.py    # Ministérios e células
│   ├── comunicacao.py    # Comunicação integrada
│   ├── eventos.py        # Eventos e presença
│   ├── financeiro.py     # Doações e financeiro
│   └── aconselhamento.py # Aconselhamento pastoral
└── data/                  # Dados (criado automaticamente)
    └── crm_igreja.db     # Banco SQLite
```

## 🛠️ Tecnologias

- **Frontend**: Streamlit (Python)
- **Backend**: Python
- **Banco de Dados**: SQLite
- **Gráficos**: Plotly
- **Criptografia**: Fernet (cryptography)
- **Autenticação**: bcrypt

## 📱 Integrações (preparado para)

- WhatsApp Business API
- SendGrid (E-mail)
- Twilio (SMS)
- Gateways de pagamento

## 📝 Licença

Este projeto é proprietário. Todos os direitos reservados.

## 🤝 Suporte

Para suporte ou dúvidas, entre em contato com a equipe de desenvolvimento.

---

Desenvolvido com ❤️ para o Reino de Deus
