import streamlit as st
import pandas as pd
import json
import base64
import requests
from datetime import datetime

# ===============================
# 🔧 Configurações iniciais
# ===============================

st.set_page_config(page_title="Provisionador de Tarefas", layout="wide")
st.title("🗂️ Provisionador de Tarefas e Subtarefas")

# ===============================
# 🔧 Configurações do GitHub
# ===============================

GITHUB_USER = "Gui-Ferreir4"
GITHUB_REPO = "provisionamento"
GITHUB_TOKEN = "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"
BRANCH = "main"

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
        return [], None  # Arquivo ainda não existe

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

# ===============================
# 🔧 Dados base (lista de tarefas)
# ===============================

if not dados:
    dados = []

df = pd.DataFrame(dados)

# ===============================
# 🔧 Cadastro de nova tarefa
# ===============================

st.subheader("➕ Cadastro de Tarefa e Subtarefa")

with st.form("form_tarefa"):
    col1, col2 = st.columns(2)
    with col1:
        id_tarefa = st.text_input("ID Tarefa")
        titulo_tarefa = st.text_input("Título da Tarefa")
    with col2:
        id_subtarefa = st.text_input("ID Subtarefa")
        titulo_subtarefa = st.text_input("Título da Subtarefa")

    tipo_subtarefa = st.selectbox("Tipo da Subtarefa", ["Análise", "Desenvolvimento", "Revisão", "Publicação"])
    descricao = st.text_area("Descrição da Subtarefa")
    data_cadastro = datetime.today().strftime('%Y-%m-%d')
    data_entrega = st.date_input("Data de Entrega")

    submitted = st.form_submit_button("💾 Cadastrar")

    if submitted:
        nova_tarefa = {
            "ID Tarefa": id_tarefa,
            "Título Tarefa": titulo_tarefa,
            "ID Subtarefa": id_subtarefa,
            "Título Subtarefa": titulo_subtarefa,
            "Tipo Subtarefa": tipo_subtarefa,
            "Descrição": descricao,
            "Data Cadastro": data_cadastro,
            "Data Entrega": str(data_entrega)
        }

        dados.append(nova_tarefa)
        salvar_json_github(ano, mes, dados, sha)
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
    st.info("Nenhuma tarefa cadastrada para este período.")
