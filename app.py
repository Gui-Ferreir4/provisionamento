import streamlit as st
import pandas as pd
import json
import base64
import requests
from datetime import datetime, date, timedelta
import holidays

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
# 🔧 Funções de Datas e Dias Úteis
# ===============================

# Definir feriados do Brasil
feriados_br = holidays.Brazil()

def eh_dia_util(data):
    return data.weekday() < 5 and data not in feriados_br

def proximo_dia_util(data):
    while not eh_dia_util(data):
        data += timedelta(days=1)
    return data

def dia_util_anterior(data):
    while not eh_dia_util(data):
        data -= timedelta(days=1)
    return data

# ===============================
# 🔧 Funções de Gerenciamento de Datas de Subtarefas
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
        if not eh_dia_util(data_check):
            data_check -= timedelta(days=1)
            continue
        chave = (str(data_check), tipo)
        if contador.get(chave, 0) < 5:
            return data_check
        data_check -= timedelta(days=1)

# ===============================
# 🔧 Função para Gerar o Próximo ID Global
# ===============================

def gerar_proximo_id_global():
    arquivos = listar_arquivos_json()
    ids_existentes = []

    for arquivo in arquivos:
        ano, mes = arquivo.replace("tarefas_", "").replace(".json", "").split("_")
        dados, _ = carregar_json_github(ano, mes)
        ids_arquivo = [int(item["ID Tarefa"]) for item in dados if item["ID Tarefa"].isdigit()]
        ids_existentes.extend(ids_arquivo)

    if ids_existentes:
        return max(ids_existentes) + 1
    else:
        return 1

# ===============================
# 🔧 Seleção de Período + Atualização Manual
# ===============================

st.set_page_config(page_title="Provisionador de Tarefas", layout="wide")
st.title("🗂️ Provisionador de Tarefas e Subtarefas")

st.subheader("🗂️ Selecione o Período (Ano/Mês)")

# Inicializa períodos disponíveis na sessão
if "periodos_disponiveis" not in st.session_state:
    arquivos_json = listar_arquivos_json()
    st.session_state.periodos_disponiveis = sorted(list(set(
        (a.replace("tarefas_", "").replace(".json", "")) for a in arquivos_json
    )))

# Layout: Lista suspensa + botão atualizar (na mesma linha)
col1, col2 = st.columns([4, 1])

with col1:
    periodo_selecionado = st.selectbox(
        "Período",
        st.session_state.periodos_disponiveis,
        format_func=lambda x: f"{x[:4]}/{x[5:]}",
        key="periodo_select"
    )

with col2:
    if st.button("🔄 Atualizar períodos"):
        arquivos_json = listar_arquivos_json()
        novos_periodos = sorted(list(set(
            (a.replace("tarefas_", "").replace(".json", "")) for a in arquivos_json
        )))

        if novos_periodos != st.session_state.periodos_disponiveis:
            st.session_state.periodos_disponiveis = novos_periodos
            st.success("🔄 Períodos atualizados com sucesso!")
        else:
            st.info("ℹ️ Nenhum novo período encontrado.")

# Carregar dados do período selecionado
ano, mes = periodo_selecionado.split("_")
dados, sha = carregar_json_github(ano, mes)
if not dados:
    dados = []

# ===============================
# 🔧 Cadastro de Nova Tarefa
# ===============================

st.subheader("➕ Cadastro de Nova Tarefa")

# 🔢 Gerar ID Global Único (verificando todos os arquivos)
novo_id_tarefa = gerar_proximo_id_global()

with st.form("form_cadastro"):
    col1, col2 = st.columns(2)
    with col1:
        titulo_tarefa = st.text_input("Título da Tarefa")
    with col2:
        descricao_tarefa = st.text_area("Descrição da Tarefa", height=38)

    st.markdown("**Selecione as Subtarefas:**")
    col1, col2, col3 = st.columns(3)
    with col1:
        cria_texto = st.checkbox("📝 Texto", value=True)
    with col2:
        cria_layout = st.checkbox("🎨 Layout", value=True)
    with col3:
        cria_html = st.checkbox("💻 HTML", value=True)

    # 🔥 Calendário inteligente: permite apenas dias úteis
    today = date.today()
    data_entrega = st.date_input(
        "Data de Entrega (Somente dias úteis e não feriados)",
        min_value=today,
        value=today if eh_dia_util(today) else proximo_dia_util(today)
    )

    if not eh_dia_util(data_entrega):
        st.warning("⚠️ A data selecionada não é um dia útil ou é feriado!")

    enviar = st.form_submit_button("💾 Cadastrar Tarefa")

if enviar:
    if not (cria_texto or cria_layout or cria_html):
        st.warning("⚠️ Selecione pelo menos uma subtarefa.")
    elif not eh_dia_util(data_entrega):
        st.error("❌ A Data de Entrega deve ser um dia útil e não pode ser feriado.")
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

        # 🔧 Definir datas conforme ordem, dias úteis e restrições
        datas_subtarefas = {}
        dias_ajuste = len(tipos_subtarefas) - 1
        for idx, tipo in enumerate(tipos_subtarefas):
            if len(tipos_subtarefas) == 1:
                data_base = data_entrega
            else:
                data_base = data_entrega - timedelta(days=dias_ajuste - idx)

            data_base = dia_util_anterior(data_base)
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

        st.success(f"✅ Tarefa '{titulo_tarefa}' cadastrada com sucesso!")

# ===============================
# 🔧 Tabela de Visualização (Somente Leitura)
# ===============================

st.subheader(f"📄 Tarefas cadastradas para {ano}/{mes}")

if dados:
    df = pd.DataFrame(dados)
    st.dataframe(df, use_container_width=True)
else:
    st.info("ℹ️ Nenhuma tarefa cadastrada para este período.")

# ===============================
# 🔧 Bloco de Edição de Tarefas
# ===============================

st.subheader("✏️ Edição de Tarefa Existente")

with st.form("form_edicao"):
    col1, col2 = st.columns(2)
    with col1:
        periodo_edicao = st.selectbox(
            "Selecione o Período (Ano_Mês)",
            st.session_state.periodos_disponiveis,
            index=st.session_state.periodos_disponiveis.index(periodo_selecionado)
        )
    with col2:
        id_tarefa_edicao = st.text_input("Informe o ID da Tarefa para Edição")

    carregar = st.form_submit_button("🔍 Carregar Tarefa")

if carregar:
    ano_edicao, mes_edicao = periodo_edicao.split("_")
    dados_edicao, sha_edicao = carregar_json_github(ano_edicao, mes_edicao)

    tarefas_filtradas = [
        item for item in dados_edicao if item["ID Tarefa"] == id_tarefa_edicao
    ]

    if not tarefas_filtradas:
        st.warning("⚠️ Tarefa não encontrada neste período.")
    else:
        tarefa_base = tarefas_filtradas[0]
        titulo_atual = tarefa_base["Título Tarefa"]
        descricao_atual = tarefa_base.get("Descrição", "")

        st.subheader(f"🛠️ Editando Tarefa: {titulo_atual} (ID {id_tarefa_edicao})")

        with st.form("form_editar"):
            col1, col2 = st.columns(2)
            with col1:
                novo_titulo = st.text_input("Título da Tarefa", value=titulo_atual)
            with col2:
                nova_descricao = st.text_area("Descrição da Tarefa", value=descricao_atual, height=38)

            tipos_existentes = {item["Tipo Subtarefa"] for item in tarefas_filtradas}

            st.markdown("**Selecione as Subtarefas:**")
            col1, col2, col3 = st.columns(3)
            with col1:
                edit_texto = st.checkbox("📝 Texto", value="Texto" in tipos_existentes)
            with col2:
                edit_layout = st.checkbox("🎨 Layout", value="Layout" in tipos_existentes)
            with col3:
                edit_html = st.checkbox("💻 HTML", value="HTML" in tipos_existentes)

            datas_entregas = [datetime.strptime(item["Data Entrega"], "%Y-%m-%d").date() for item in tarefas_filtradas]
            data_entrega_nova = st.date_input(
                "Data de Entrega (Somente dias úteis e não feriados)",
                value=max(datas_entregas) if datas_entregas else date.today()
            )

            atualizar = st.form_submit_button("💾 Atualizar Tarefa")

        if atualizar:
            if not (edit_texto or edit_layout or edit_html):
                st.warning("⚠️ Selecione pelo menos uma subtarefa.")
            elif not eh_dia_util(data_entrega_nova):
                st.error("❌ A Data de Entrega deve ser um dia útil e não feriado.")
            else:
                # 🔥 Remove subtarefas antigas dessa tarefa
                dados_edicao = [
                    item for item in dados_edicao if item["ID Tarefa"] != id_tarefa_edicao
                ]

                tipos_subtarefas = []
                if edit_texto: tipos_subtarefas.append("Texto")
                if edit_layout: tipos_subtarefas.append("Layout")
                if edit_html: tipos_subtarefas.append("HTML")

                # 🔥 Ordem correta
                tipos_subtarefas.sort(key=lambda x: ["Texto", "Layout", "HTML"].index(x))

                datas_subtarefas = {}
                dias_ajuste = len(tipos_subtarefas) - 1
                for idx, tipo in enumerate(tipos_subtarefas):
                    if len(tipos_subtarefas) == 1:
                        data_base = data_entrega_nova
                    else:
                        data_base = data_entrega_nova - timedelta(days=dias_ajuste - idx)

                    data_base = dia_util_anterior(data_base)
                    data_final = encontrar_data_disponivel(data_base, tipo, dados_edicao)
                    datas_subtarefas[tipo] = data_final

                novas_subtarefas = []
                for tipo in tipos_subtarefas:
                    id_sub = str(["Texto", "Layout", "HTML"].index(tipo) + 1)
                    novas_subtarefas.append({
                        "ID Tarefa": id_tarefa_edicao,
                        "Título Tarefa": novo_titulo,
                        "Subtarefa": id_sub,
                        "Título Subtarefa": f"{tipo}_{novo_titulo}",
                        "Tipo Subtarefa": tipo,
                        "Descrição": nova_descricao,
                        "Data Cadastro": datetime.today().strftime('%Y-%m-%d'),
                        "Data Entrega": str(datas_subtarefas[tipo])
                    })

                dados_edicao.extend(novas_subtarefas)
                salvar_json_github(ano_edicao, mes_edicao, dados_edicao, sha_edicao)

                st.success(f"✅ Tarefa '{novo_titulo}' atualizada com sucesso!")

# ===============================
# 🔧 Encerramento
# ===============================

st.divider()
st.caption("🚀 Desenvolvido para gerenciar tarefas e subtarefas com controle de datas, restrições, feriados e dias úteis, integrando diretamente com GitHub como backend de dados.")

st.markdown(
    """
    ### ✅ Funcionalidades atuais:
    - Cadastro de tarefas com geração de subtarefas: Texto, Layout, HTML.
    - Validação de dias úteis e feriados.
    - Limite de até 5 subtarefas do mesmo tipo por dia.
    - Geração de IDs únicos globalmente considerando todos os arquivos JSON.
    - Seleção de período com atualização manual.
    - Edição completa de tarefas existentes:
        - Alteração de título, descrição, datas e subtarefas.
    - Dados armazenados diretamente no GitHub (JSON por Ano e Mês).

    ---
    ### 💡 Melhorias futuras sugeridas:
    - ✔️ Integração de um Kanban visual baseado nos dados do JSON.
    - ✔️ Download/exportação dos dados em Excel ou CSV.
    - ✔️ Filtros inteligentes por datas, tipos ou status de tarefas.
    - ✔️ Geração de dashboards e gráficos analíticos.

    ---
    """
)
