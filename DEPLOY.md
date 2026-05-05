# Guia de Deploy — Streamlit Cloud + Núcleo OS (Airtable) + Auth

Step-by-step para pôr o tool acessível à equipa numa URL `nucleo-avaliador.streamlit.app`, com submissão directa ao Núcleo OS (tabelas Activos + Triagem I + Contactos) e auth com password.

Tempo estimado: 30-45 min primeira vez. Depois cada update é `git push`.

---

## Prerequisitos

- Conta GitHub (privada)
- Acesso à base "Núcleo OS" no Airtable (tu já tens)
- Conta Streamlit Cloud (https://share.streamlit.io)
- Git instalado (https://git-scm.com/download/win)

---

## Passo 1 — Airtable: Personal Access Token

1. https://airtable.com/create/tokens → **Create token**
2. Configura:
   - Name: `nucleo-avaliador-streamlit`
   - Scopes: `data.records:read`, `data.records:write`, `schema.bases:read`
   - Access: selecciona **Núcleo OS**
3. Cria, copia o token (`pat...`).

Anota também o Base ID (do URL: `airtable.com/appnv3Q8pmFUzaxgx/...`) → `appnv3Q8pmFUzaxgx`.

---

## Passo 2 — GitHub: criar repo privado

1. https://github.com → **New repository**
2. Nome: `nucleo-avaliador`
3. **Private**
4. Não inicializar com nada
5. Create

---

## Passo 3 — Push do código

PowerShell na pasta:

```powershell
cd "C:\Users\joaos\OneDrive\Desktop\Claude Cowork\OUTPUTS\Avaliador de propriedades\Avaliador de Propriedades"
git --version  # confirmar git instalado
```

Inicializar e push (substitui `<teu-username>`):

```powershell
git init
git add .
git commit -m "v3 — integração Núcleo OS (Activos + Triagem I + Contactos)"
git branch -M main
git remote add origin https://github.com/<teu-username>/nucleo-avaliador.git
git push -u origin main
```

Primeira vez pede credentials. Username GitHub + **Personal Access Token** (não a password — GitHub deprecou). Cria PAT em https://github.com/settings/tokens (Classic, scope `repo`).

---

## Passo 4 — Gerar passwords bcrypt

PowerShell com `.venv` activo:

```powershell
.venv\Scripts\activate.bat
python -c "import streamlit_authenticator as stauth; print(stauth.Hasher(['minhapassword']).generate()[0])"
```

Substitui `minhapassword`. Copia o hash (`$2b$12$...`) para cada user.

Cookie key:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Passo 5 — Streamlit Cloud: deploy

1. https://share.streamlit.io → **New app**
2. Conecta GitHub
3. Preenche:
   - Repository: `<teu-username>/nucleo-avaliador`
   - Branch: `main`
   - Main file: `app.py`
   - URL: `nucleo-avaliador` (ou outro)
4. **Advanced settings** → **Secrets** — cola:

```toml
[airtable]
token = "patXXXXXXXXXXXXX.YYYYYYYYY"  # Passo 1
base_id = "appnv3Q8pmFUzaxgx"          # Núcleo OS
table_activos = "Activos"
table_triagem_i = "Triagem I"
table_contactos = "Contactos"

[auth]
cookie_name = "avaliador_nucleo"
cookie_key = "<cookie key gerada no passo 4>"
cookie_expiry_days = 30

[auth.credentials.usernames.joao]
email = "joaoserragrilo@gmail.com"
name = "Joao Grilo"
password = "<bcrypt hash>"

[auth.credentials.usernames.colaborador1]
email = "X@nucleoassets.com"
name = "Nome Real"
password = "<bcrypt hash>"
```

Python version: 3.12.

5. **Deploy**. ~3-5 min.

---

## Passo 6 — Validar

Abre `https://nucleo-avaliador.streamlit.app` (ou o URL que escolheste).

1. **Login**: ecrã pede username + password. Mete um dos que configuraste.
2. **Importar anúncio**: cola um link real de Idealista/Remax/Imovirtual ou cola texto.
3. **Análise**: confere que os dados foram pré-preenchidos. Ajusta o que falte (estado conservação, freguesia INE).
4. **Analisar**: vê o veredicto + métricas + simulação preço máx.
5. **Submeter ao Núcleo OS**: preenche dados do agente (parcer pode ter extraído algo) + canal de origem. Clica.
6. Vai à base **Núcleo OS** no Airtable → **Activos**: vê o registo novo (ou actualizado se já existia por Link anúncio). → **Triagem I**: vê a entrada com Recomendação/Confiança/Notas. → **Contactos**: se metes-te um agente novo, deve estar lá.

---

## O que fica no Núcleo OS depois de submeter uma análise

**Activos** (criado se Link anúncio é novo, ou actualizado se já existia):
- Tipo, Tipologia, Estado Conservação, Área, Preço pedido, Link anúncio, Freguesia
- Estado: "Em triagem I"
- Data entrada: hoje
- Canal origem
- Contacto (linked) ao agente, se foi fornecido

**Triagem I** (criada nova de cada vez):
- Activo (linked)
- Data triagem: hoje
- Recomendação: Visitar (verde) / Monitorizar (amarelo) / Excluir (vermelho)
- Confiança: Alta / Média / Baixa (calculada de INE + nº comparáveis)
- Valor actual est. = preço pedido
- Valor após obra est. = preço venda usado
- Custo obra est. = obra com IVA + contingência
- Notas: resumo do veredicto + flags

**Contactos** (criado se nome novo, linkado se já existe):
- Primeiro Nome / Último Nome
- Sou: Agente Imobiliário / Proprietário
- Telemóvel / Email (se preenchidos)

---

## Updates futuros

```powershell
cd "C:\Users\joaos\OneDrive\Desktop\Claude Cowork\OUTPUTS\Avaliador de propriedades\Avaliador de Propriedades"
git add .
git commit -m "descrição"
git push
```

Streamlit Cloud detecta e re-deploy automático em ~1-2 min.

---

## Adicionar membro à equipa

Streamlit Cloud → App → Settings → Secrets, adiciona:

```toml
[auth.credentials.usernames.nome_da_pessoa]
email = "..."
name = "..."
password = "<hash>"
```

Save. App reinicia. Pessoa entra imediatamente. Não precisa de re-deploy.

---

## Troubleshooting

**"Tabela não encontrada":** confirma os nomes em secrets (`Activos`, `Triagem I`, `Contactos`). Atenção ao espaço em "Triagem I".

**"Field 'X' não existe":** o schema mudou no Airtable. Ajusta `lib/airtable_io.py` para os novos nomes. `git push` automaticamente re-deploy.

**Activo duplicado:** o tool detecta duplicados por `Link anúncio`. Se vês duplicados, é porque o Link anúncio mudou ou estava vazio.

**Login não funciona:** confirma que copiaste o hash bcrypt todo (incluindo `$2b$12$`).

**App em sleep:** acordar demora ~30s. Para manter warm: UptimeRobot free (https://uptimerobot.com), pinga URL a cada 5 min.

---

## Custos

- Streamlit Cloud: 0€ (free tier)
- Airtable Núcleo OS: já tens
- GitHub privado: 0€

**Total: 0€/mês.**
