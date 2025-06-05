import streamlit as st
import pandas as pd
import json
import base64
import requests
import os
from datetime import datetime
from dateutil import parser

# ===============================
# 🔧 Configurações do GitHub
# ===============================

GITHUB_USER = st.secrets["github"]["user"]
GITHUB_REPO = st.secrets["github"]["repo"]
GITHUB_TOKEN = st.secrets["github"]["token"]
BRANCH = st.secrets["github"]["branch"]

# ===============================
# 🔧 Funções utilitárias GitHub
# ===============================

def listar_arquivos_json():
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/data"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        arquivos = response.json()
        jsons = [a["name"] for a in arquivos if a["name"].endswith(".json")]
        return sorted(jsons)
    else:
        st.error("❌ Erro ao listar arquivos do GitHub")
        return []

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
        return [], None

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

    if response.status_code not in [200, 201]:
        st.error(f"❌ Erro ao salvar no GitHub: {response.json()}")

# ===============================
# 🔧 Obter lista de períodos existentes
# ===============================

arquivos_json = listar_arquivos_json()

if arquivos_json:
    periodos = sorted(list(set(
        (a.replace("tarefas_", "").replace(".json", "")) for a in arquivos_json
    )))
else:
    periodos = []

periodo_selecionado = st.selectbox(
    "🗂️ Selecione o período (Ano/Mês)",
    periodos,
    format_func=lambda x: f"{x[:4]}/{x[5:]}"
)

ano, mes = periodo_selecionado.split("_")

dados, sha = carregar_json_github(ano, mes)
if not dados:
    dados = []

# ===============================
# 🔧 Cadastro de Nova Tarefa (Sidebar)
# ===============================

st.sidebar.header("➕ Cadastro de Nova Tarefa")

# 🔢 Gerar ID numérico incremental da tarefa principal
if dados:
    ids_existentes = [int(item["ID Tarefa"]) for item in dados if item["ID Tarefa"].isdigit()]
    novo_id_tarefa = max(ids_existentes) + 1 if ids_existentes else 1
else:
    novo_id_tarefa = 1

titulo_tarefa = st.sidebar.text_input("Título da Tarefa")
descricao_tarefa = st.sidebar.text_area("Descrição da Tarefa")

st.sidebar.markdown("**Selecione as Subtarefas:**")
col1 = st.sidebar.columns(1)
with col1:
    cria_texto = st.checkbox("📝 Texto (D-2)", value=True)
    cria_layout = st.checkbox("🎨 Layout (D-1)", value=True)
    cria_html = st.checkbox("💻 HTML (D)", value=True)

data_entrega = st.sidebar.date_input("Data de Entrega")

# 🔥 Validação da Data de Entrega
data_minima = datetime(data_entrega.year, data_entrega.month, 3)
if data_entrega < data_minima:
    st.sidebar.warning("⚠️ A Data de Entrega não pode ser anterior ao dia 3 do mês.")

if st.sidebar.button("💾 Cadastrar Tarefa"):
    if not (cria_texto or cria_layout or cria_html):
        st.sidebar.warning("⚠️ Selecione pelo menos uma subtarefa.")
    elif data_entrega < data_minima:
        st.sidebar.error("❌ A Data de Entrega não pode ser anterior ao dia 3.")
    else:
        # 🔥 Definir o período de cadastro conforme a data de entrega
        ano_entrega = data_entrega.year
        mes_entrega = f"{data_entrega.month:02}"

        dados_entrega, sha_entrega = carregar_json_github(ano_entrega, mes_entrega)
        if not dados_entrega:
            dados_entrega = []

        subtarefas = []

        if cria_texto:
            subtarefas.append({
                "ID Tarefa": str(novo_id_tarefa),
                "Título Tarefa": titulo_tarefa,
                "ID Subtarefa": "ID1",
                "Título Subtarefa": f"Texto_{titulo_tarefa}",
                "Tipo Subtarefa": "Texto (D-2)",
                "Descrição": descricao_tarefa,
                "Data Cadastro": datetime.today().strftime('%Y-%m-%d'),
                "Data Entrega": str(data_entrega)
            })
        if cria_layout:
            subtarefas.append({
                "ID Tarefa": str(novo_id_tarefa),
                "Título Tarefa": titulo_tarefa,
                "ID Subtarefa": "ID2",
                "Título Subtarefa": f"Layout_{titulo_tarefa}",
                "Tipo Subtarefa": "Layout (D-1)",
                "Descrição": descricao_tarefa,
                "Data Cadastro": datetime.today().strftime('%Y-%m-%d'),
                "Data Entrega": str(data_entrega)
            })
        if cria_html:
            subtarefas.append({
                "ID Tarefa": str(novo_id_tarefa),
                "Título Tarefa": titulo_tarefa,
                "ID Subtarefa": "ID3",
                "Título Subtarefa": f"HTML_{titulo_tarefa}",
                "Tipo Subtarefa": "HTML (D)",
                "Descrição": descricao_tarefa,
                "Data Cadastro": datetime.today().strftime('%Y-%m-%d'),
                "Data Entrega": str(data_entrega)
            })

        dados_entrega.extend(subtarefas)
        salvar_json_github(ano_entrega, mes_entrega, dados_entrega, sha_entrega)
        st.sidebar.success(f"✅ Tarefa '{titulo_tarefa}' cadastrada com sucesso!")

# ===============================
# 🔧 Edição das tarefas
# ===============================

st.subheader(f"📄 Tarefas cadastradas para {ano}/{mes}")

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
else:
    st.info("ℹ️ Nenhuma tarefa cadastrada para este período.")
