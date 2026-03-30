# Controle Integrado ES/MG — Dashboard

Dashboard de controle de demandas, orçamentos EAC, efetivo e CGO.

## Como publicar no Streamlit Cloud (gratuito)

### 1. Criar conta no GitHub
- Acesse https://github.com e crie uma conta gratuita

### 2. Criar repositório
- Clique em **New repository**
- Nome sugerido: `ci-es-mg-dashboard`
- Deixe como **Public** (necessário para o plano gratuito do Streamlit)
- Clique em **Create repository**

### 3. Fazer upload dos arquivos
Suba todos estes arquivos para o repositório:
```
app.py
requirements.txt
.streamlit/config.toml
data/CONTROLE_INTEGRADO_DE_DEMANDAS__ES-MG_.xlsx
data/CGO-ES_MG-03_03_2026.xlsm
data/EFETIVO_ES-REV_11_03_2026.xlsx
```
> Os arquivos EAC não precisam estar no repositório — você os carrega pela barra lateral do app.

### 4. Publicar no Streamlit Cloud
- Acesse https://share.streamlit.io
- Faça login com sua conta GitHub
- Clique em **New app**
- Escolha o repositório e o arquivo `app.py`
- Clique em **Deploy**

Em ~2 minutos o app estará online em um link tipo:
`https://seu-usuario.streamlit.app/ci-es-mg-dashboard`

## Como atualizar as planilhas

**Opção 1 — Pelo app (sem precisar do GitHub):**
- Use os uploaders na barra lateral para carregar versões novas
- O dashboard atualiza imediatamente

**Opção 2 — Atualização permanente:**
- Substitua os arquivos na pasta `data/` do repositório GitHub
- O Streamlit Cloud detecta a mudança e reinicia automaticamente

## Arquivos EAC
- Carregue múltiplos arquivos EAC-SS-*.xlsm pela barra lateral
- Revisões são detectadas automaticamente pelo número `ES_X` no nome
- O app mantém sempre a revisão mais recente de cada SS
