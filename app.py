import streamlit as st
import pandas as pd
import json
import base64
import requests
from datetime import datetime, date, timedelta

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
# 🔧 Gerenciamento de Datas
# ===============================

def contar_subtarefas_por_data(lista_dados):
    contador = {}
    for item in lista_dados:
        data = item["Data Entrega"]
        tipo = item["Tipo Subtarefa"]
        chave = (data, tipo)
        contador[chave] = contador.get(chave, 0) + 1
    return contador

def encontrar_data_disponivel(data_base, tipo, dados_mes):
    contador = contar_subtarefas_por_data(dados_mes)
    data_check = data_base
    while True:
        chave = (str(data_check), tipo)
        if contador.get(chave, 0) < 5:
            return data_check
        data_check -= timedelta(days=1)

# ===============================
# 🔧 Seleção de Período + Refresh
# ===============================

st.subheader("🗂️ Selecione o período (Ano/Mês)")

if "periodos_disponiveis" not in st.session_state:
    arquivos_json = listar_arquivos_json()
    st.session_state.periodos_disponiveis = sorted(list(set(
        (a.replace("tarefas_", "").replace(".json", "")) for a in arquivos_json
    )))

col1, col2 = st.columns([4, 1])

with col1:
    periodo_selecionado = st.selectbox(
        "Período",
        st.session_state.periodos_disponiveis,
        format_func=lambda x: f"{x[:4]}/{x[5:]}",
        key="periodo_select"
    )

with col2:
    if st.button("🔄 Atualizar"):
        arquivos_json = listar_arquivos_json()
        st.session_state.periodos_disponiveis = sorted(list(set(
            (a.replace("tarefas_", "").replace(".json", "")) for a in arquivos_json
        )))
        st.success("🔄 Períodos atualizados com sucesso!")

# Carrega os dados do período selecionado
ano, mes = periodo_selecionado.split("_")
dados, sha = carregar_json_github(ano, mes)
if not dados:
    dados = []

# ===============================
# 🔧 Cadastro de Tarefa (Sidebar)
# ===============================

st.sidebar.header("➕ Cadastro de Nova Tarefa")

# 🔢 Gerar ID numérico incremental
if dados:
    ids_existentes = [int(item["ID Tarefa"]) for item in dados if item["ID Tarefa"].isdigit()]
    novo_id_tarefa = max(ids_existentes) + 1 if ids_existentes else 1
else:
    novo_id_tarefa = 1

titulo_tarefa = st.sidebar.text_input("Título da Tarefa")
descricao_tarefa = st.sidebar.text_area("Descrição da Tarefa")

st.sidebar.markdown("**Selecione as Subtarefas:**")
cria_texto = st.sidebar.checkbox("📝 Texto", value=True)
cria_layout = st.sidebar.checkbox("🎨 Layout", value=True)
cria_html = st.sidebar.checkbox("💻 HTML", value=True)

data_entrega = st.sidebar.date_input("Data de Entrega")

# 🔥 Validação de data mínima
data_minima = date(data_entrega.year, data_entrega.month, 3)
if data_entrega < data_minima:
    st.sidebar.warning("⚠️ A Data de Entrega não pode ser anterior ao dia 3 do mês.")

if st.sidebar.button("💾 Cadastrar Tarefa"):
    if not (cria_texto or cria_layout or cria_html):
        st.sidebar.warning("⚠️ Selecione pelo menos uma subtarefa.")
    elif data_entrega < data_minima:
        st.sidebar.error("❌ A Data de Entrega não pode ser anterior ao dia 3.")
    else:
        # 🔥 Definir período conforme a data de entrega
        ano_entrega = data_entrega.year
        mes_entrega = f"{data_entrega.month:02}"

        dados_entrega, sha_entrega = carregar_json_github(ano_entrega, mes_entrega)
        if not dados_entrega:
            dados_entrega = []

        subtarefas = []

        tipos_subtarefas = []
        if cria_texto: tipos_subtarefas.append("Texto")
        if cria_layout: tipos_subtarefas.append("Layout")
        if cria_html: tipos_subtarefas.append("HTML")

        # 🔥 Ordem: Texto > Layout > HTML
        tipos_subtarefas.sort(key=lambda x: ["Texto", "Layout", "HTML"].index(x))

        # 🔧 Definir datas conforme ordem e restrições
        datas_subtarefas = {}
        dias_ajuste = len(tipos_subtarefas) - 1
        for idx, tipo in enumerate(tipos_subtarefas):
            if len(tipos_subtarefas) == 1:
                data_base = data_entrega
            else:
                data_base = data_entrega - timedelta(days=dias_ajuste - idx)

            data_final = encontrar_data_disponivel(data_base, tipo, dados_entrega)
            datas_subtarefas[tipo] = data_final

        # 🔥 Gerar subtarefas
        for tipo in tipos_subtarefas:
            id_sub = str(["Texto", "Layout", "HTML"].index(tipo) + 1)
            subtarefas.append({
                "ID Tarefa": str(novo_id_tarefa),
                "Título Tarefa": titulo_tarefa,
                "Subtarefa": id_sub,
                "Título Subtarefa": f"{tipo}_{titulo_tarefa}",
                "Tipo Subtarefa": tipo,
                "Descrição": descricao_tarefa,
                "Data Cadastro": datetime.today().strftime('%Y-%m-%d'),
                "Data Entrega": str(datas_subtarefas[tipo])
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
