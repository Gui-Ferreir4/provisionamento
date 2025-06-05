import streamlit as st
import pandas as pd
import json
import base64
import requests
from datetime import datetime

# ===============================
# 🔧 Configurações do GitHub
# ===============================

GITHUB_USER = "Gui-Ferreir4"
GITHUB_REPO = "provisionamento"
GITHUB_TOKEN = "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"
BRANCH = "main"

# ===============================
# 🔧 Configurações do App
# ===============================

st.set_page_config(page_title="Provisionador de Tarefas", layout="wide")
st.title("🗂️ Provisionador de Tarefas e Subtarefas")

# ===============================
# 🔧 Funções utilitárias GitHub
# ===============================

def github_file_url(ano, mes):
    return f"data/tarefas_{ano}_{mes}.json"

def carregar_json_github(ano, mes):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{github_file_url(ano, mes)}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        content = base64.b64decode(response.json()["content"])
        data = json.loads(content)
        sha = response.json()["sha"]
        return data, sha
    else:
        return [], None  # Arquivo não existe ainda

def salvar_json_github(ano, mes, data, sha=None):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{github_file_url(ano, mes)}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    conteudo = json.dumps(data, ensure_ascii=False, indent=4)
    b64_content = base64.b64encode(conteudo.encode()).decode()

    payload = {
        "message": f"Atualizando tarefas {ano}/{mes}",
        "content": b64_content,
        "branch": BRANCH
    }
    if sha:
        payload["sha"] = sha

    response = requests.put(url, headers=headers, json=payload)

    if response.status_code in [200, 201]:
        st.success("✅ Dados salvos no GitHub com sucesso!")
    else:
        st.error(f"❌ Erro ao salvar no GitHub: {response.json()}")

# ===============================
# 🔧 Provisionamento (Ano e Mês)
# ===============================

st.sidebar.header("📅 Provisionamento")
ano = st.sidebar.selectbox("Ano", [2023, 2024, 2025], index=1)
mes = st.sidebar.selectbox("Mês", list(range(1, 13)), format_func=lambda x: f"{x:02}")

dados, sha = carregar_json_github(ano, mes)

if not dados:
    dados = []

# ===============================
# 🔧 Cadastro de nova tarefa
# ===============================

st.subheader("➕ Cadastro de Nova Tarefa")

# 🔢 Gerar ID numérico incremental da tarefa principal
if dados:
    ids_existentes = [int(item["ID Tarefa"]) for item in dados if item["ID Tarefa"].isdigit()]
    novo_id_tarefa = max(ids_existentes) + 1 if ids_existentes else 1
else:
    novo_id_tarefa = 1

titulo_tarefa = st.text_input("Título da Tarefa")

st.markdown("**Selecione as Subtarefas que deseja criar:**")
col1, col2, col3 = st.columns(3)
with col1:
    cria_texto = st.checkbox("📝 Texto (D-2)", value=True)
with col2:
    cria_layout = st.checkbox("🎨 Layout (D-1)", value=True)
with col3:
    cria_html = st.checkbox("💻 HTML (D)", value=True)

data_cadastro = datetime.today().strftime('%Y-%m-%d')
data_entrega = st.date_input("Data de Entrega")

if st.button("💾 Cadastrar Tarefa"):
    subtarefas = []

    if cria_texto:
        subtarefas.append({
            "ID Tarefa": str(novo_id_tarefa),
            "Título Tarefa": titulo_tarefa,
            "ID Subtarefa": "ID1",
            "Título Subtarefa": f"Texto_{titulo_tarefa}",
            "Tipo Subtarefa": "Texto (D-2)",
            "Descrição": "",
            "Data Cadastro": data_cadastro,
            "Data Entrega": str(data_entrega)
        })
    if cria_layout:
        subtarefas.append({
            "ID Tarefa": str(novo_id_tarefa),
            "Título Tarefa": titulo_tarefa,
            "ID Subtarefa": "ID2",
            "Título Subtarefa": f"Layout_{titulo_tarefa}",
            "Tipo Subtarefa": "Layout (D-1)",
            "Descrição": "",
            "Data Cadastro": data_cadastro,
            "Data Entrega": str(data_entrega)
        })
    if cria_html:
        subtarefas.append({
            "ID Tarefa": str(novo_id_tarefa),
            "Título Tarefa": titulo_tarefa,
            "ID Subtarefa": "ID3",
            "Título Subtarefa": f"HTML_{titulo_tarefa}",
            "Tipo Subtarefa": "HTML (D)",
            "Descrição": "",
            "Data Cadastro": data_cadastro,
            "Data Entrega": str(data_entrega)
        })

    if not subtarefas:
        st.warning("⚠️ Selecione pelo menos uma subtarefa para cadastrar.")
    else:
        dados.extend(subtarefas)
        salvar_json_github(ano, mes, dados, sha)
        st.success(f"✅ Tarefa '{titulo_tarefa}' e {len(subtarefas)} subtarefa(s) cadastradas com sucesso!")
        st.experimental_rerun()

# ===============================
# 🔧 Edição das tarefas
# ===============================

st.subheader(f"📄 Tarefas cadastradas para {mes:02}/{ano}")

if dados:
    df = pd.DataFrame(dados)

    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        key="editor_tarefas"
    )

    if st.button("💾 Salvar alterações na tabela"):
        dados_atualizados = edited_df.to_dict(orient="records")
        salvar_json_github(ano, mes, dados_atualizados, sha)
        st.success("✅ Alterações salvas no GitHub com sucesso!")
        st.experimental_rerun()
else:
    st.info("ℹ️ Nenhuma tarefa cadastrada para este período.")
