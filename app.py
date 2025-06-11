# PARTE 1: Configurações iniciais, lista de projetos, e atualização das funções de arquivos por projeto

import streamlit as st
import pandas as pd
import time
import json
import base64
import requests
from datetime import datetime, date, timedelta
from github import Github
import holidays

# --- CONFIGS ---
GITHUB_USER = st.secrets["github"]["user"]
GITHUB_REPO = st.secrets["github"]["repo"]
GITHUB_TOKEN = st.secrets["github"]["token"]
BRANCH = st.secrets["github"]["branch"]
feriados_br = holidays.Brazil()

# --- LISTA DE PROJETOS ---
PROJETOS = [
    "ADCOS", "BANESE CARD", "CAIXA CONSÓRCIO", "CLARO - ENDOMARKETING",
    "CLUBE DO PADEIRO", "CONDOR", "COOP", "DAVÓ", "DROGA LESTE", "DALBEN",
    "ATACDÃO DIA  A DIA", "ELC-BRASIL - LAMER", "ELC-BRASIL - MAC", "ELC-BRASIL - TOOFACED",
    "ELC-BRASIL CLINIQUE", "ELC-BRASIL ESTÉE LAUDER", "ELC-BRASIL JO MALONE",
    "ELC-CHILE CLINIQUE", "ELC-CHILE ESTÉE LAUDER", "ELC-CHILE MAC",
    "EMBRATEL", "FEMSA", "GRUPO PEREIRA", "INTER SUPERMERCADOS", "MADERO",
    "MULVI PAY", "NISSEI", "SBT", "UNILEVER", "OMNI FINANCEIRA"
]

# --- LOG ---
if "log" not in st.session_state:
    st.session_state.log = []

def registrar_log(msg):
    hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.log.append(f"[{hora}] {msg}")

# --- FUNÇÕES AUXILIARES ---
def eh_dia_util(d): return d.weekday() < 5 and d not in feriados_br

def proximo_dia_util(d): return d + timedelta(days=1) if not eh_dia_util(d) else d

def retroceder_dias_uteis(d, dias):
    while dias > 0:
        d -= timedelta(days=1)
        if eh_dia_util(d): dias -= 1
    return d


def github_file_url(projeto, ano, mes):
    return f"data/{projeto}/tarefas_{ano}_{mes}.json"


def listar_arquivos_json(projeto):
    pasta = f"data/{projeto}"
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{pasta}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(url, headers=headers)
    return [f["name"] for f in r.json() if f["name"].endswith(".json")] if r.status_code == 200 else []


def carregar_json_github(projeto, ano, mes):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{github_file_url(projeto, ano, mes)}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        content = base64.b64decode(r.json()["content"])
        return json.loads(content), r.json()["sha"]
    return [], None


def salvar_arquivo_github(projeto, ano, mes, data):
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_user().get_repo(GITHUB_REPO)
        path = github_file_url(projeto, ano, mes)
        conteudo = json.dumps(data, ensure_ascii=False, indent=4)

        try:
            arquivo = repo.get_contents(path, ref=BRANCH)
            sha = arquivo.sha
            repo.update_file(
                path=path,
                message=f"Atualizando tarefas {ano}/{mes} ({projeto})",
                content=conteudo,
                sha=sha,
                branch=BRANCH
            )
            registrar_log(f"✅ Arquivo atualizado: {path}")
        except Exception as e:
            if "404" in str(e):
                repo.create_file(
                    path=path,
                    message=f"Criando novo arquivo tarefas_{ano}_{mes}.json ({projeto})",
                    content=conteudo,
                    branch=BRANCH
                )
                registrar_log(f"📄 Novo arquivo criado: {path}")
            else:
                raise e

        return True

    except Exception as e:
        erro_msg = f"❌ Erro ao salvar no GitHub: {e}"
        st.error(f"Erro: {e}")
        registrar_log(erro_msg)
        return False


def encontrar_data_disponivel(data_base, subtipo, dados):
    while True:
        if eh_dia_util(data_base):
            ocupadas = sum(1 for d in dados if d["Data Entrega"] == str(data_base) and d["Tipo Subtarefa"] == subtipo)
            if ocupadas < 5:
                return data_base
        data_base -= timedelta(days=1)


def gerar_proximo_id():
    ids = []
    for projeto in PROJETOS:
        arquivos = listar_arquivos_json(projeto)
        for arq in arquivos:
            ano, mes = arq.replace("tarefas_", "").replace(".json", "").split("_")
            dados, _ = carregar_json_github(projeto, ano, mes)
            ids += [int(d["ID Tarefa"]) for d in dados if d["ID Tarefa"].isdigit()]
    return max(ids) + 1 if ids else 1

# INÍCIO DAS ABAS
abas = st.tabs(["📋 Cadastro", "📋 Tarefas Cadastradas", "📜 LOG"])

# PARTE 2: CADASTRO
with abas[0]:
    st.title("📋 Cadastro de Tarefa")

    projeto = st.selectbox("Selecione o Projeto", PROJETOS)
    novo_id = gerar_proximo_id()

    titulo = st.text_input("Título da Tarefa")
    chamado = st.text_input("Chamado (número do Hike)")

    col1, col2, col3 = st.columns(3)
    with col1:
        t1 = st.checkbox("📝 Texto")
    with col2:
        t2 = st.checkbox("🎨 Layout")
    with col3:
        t3 = st.checkbox("💻 HTML")

    data_final = st.date_input("Data Final de Entrega", value=datetime.today())

    if st.button("✅ Cadastrar Tarefa"):
        if not titulo or not chamado:
            st.error("Preencha o título e o chamado.")
        elif not any([t1, t2, t3]):
            st.error("Selecione pelo menos um tipo de subtarefa.")
        elif data_final < datetime.today().date():
            st.error("A data final não pode ser anterior à data de hoje.")
        else:
            try:
                ano = str(datetime.today().year)
                mes = f"{datetime.today().month:02d}"
                dados_existentes, _ = carregar_json_github(projeto, ano, mes)

                novas = []
                tipos = {"Texto": t1, "Layout": t2, "HTML": t3}
                tipos_selecionados = [k for k, v in tipos.items() if v]
                dias_ajuste = len(tipos_selecionados) - 1

                for i, tipo in enumerate(sorted(tipos_selecionados, key=lambda x: ["Texto", "Layout", "HTML"].index(x))):
                    base = retroceder_dias_uteis(data_final, dias_ajuste - i)
                    entrega = encontrar_data_disponivel(base, tipo, dados_existentes)
                    novas.append({
                        "ID Tarefa": str(novo_id),
                        "Título Tarefa": titulo,
                        "Subtarefa": str(i+1),
                        "Título Subtarefa": f"{tipo}_{titulo}",
                        "Tipo Subtarefa": tipo,
                        "Chamado": chamado,
                        "Data Cadastro": datetime.today().strftime("%Y-%m-%d"),
                        "Data Entrega": str(entrega),
                        "Status": "Pendente"
                    })

                dados_existentes.extend(novas)
                sucesso = salvar_arquivo_github(projeto, ano, mes, dados_existentes)

                if sucesso:
                    st.success(f"Tarefa {novo_id} cadastrada com sucesso.")
            except Exception as e:
                st.error(f"Erro ao cadastrar: {e}")
                registrar_log(f"❌ Erro ao cadastrar tarefa {novo_id}: {e}")

# PARTE 3: TAREFAS CADASTRADAS
with abas[1]:
    st.title("📋 Tarefas Cadastradas")

    projeto_sel = st.selectbox("Selecione o Projeto para Consulta", PROJETOS, key="projeto_consulta")

    arquivos = listar_arquivos_json(projeto_sel)
    periodos = sorted([a.replace("tarefas_", "").replace(".json", "") for a in arquivos])

    if not periodos:
        st.warning("⚠️ Nenhum arquivo encontrado para este projeto.")
    else:
        if "ultimo_periodo" not in st.session_state:
            st.session_state.ultimo_periodo = None

        col_top = st.columns([1, 4, 1])
        with col_top[1]:
            periodo = st.selectbox("📂 Selecione o Período", periodos, key="periodo_consulta")

        if st.session_state.ultimo_periodo != st.session_state.periodo_consulta:
            st.session_state.ultimo_periodo = st.session_state.periodo_consulta
            st.session_state.pop("modo_edicao", None)
            st.session_state.pop("id_em_edicao", None)
            st.rerun()

        ano, mes = st.session_state.periodo_consulta.split("_")
        dados_json, _ = carregar_json_github(projeto_sel, ano, mes)

        if "modo_edicao" not in st.session_state:
            st.session_state.modo_edicao = False

        col_main = st.columns([1, 4, 1])
        with col_main[1]:
            id_input = st.text_input("🔍 Digite o ID da Tarefa que deseja editar:")

            if not st.session_state.modo_edicao:
                if id_input:
                    tarefas = [t for t in dados_json if t["ID Tarefa"] == id_input]
                    if not tarefas:
                        st.warning(f"❌ Nenhuma tarefa encontrada com ID {id_input}.")
                        registrar_log(f"⚠️ ID {id_input} não localizado em {projeto_sel}/tarefas_{ano}_{mes}.json")
                    else:
                        st.session_state.modo_edicao = True
                        st.session_state.id_em_edicao = id_input
                        st.rerun()
                else:
                    st.markdown("### 📄 Tarefas no Período Selecionado")
                    st.dataframe(pd.DataFrame(dados_json), use_container_width=True)

# PARTE 4: LOG
with abas[2]:
    st.title("📜 LOG DE ATIVIDADES")

    if st.session_state.log:
        st.markdown("### 🧾 Histórico de ações executadas nesta sessão:")
        for linha in reversed(st.session_state.log):
            st.markdown(f"- {linha}")
    else:
        st.info("ℹ️ Nenhuma atividade registrada ainda.")
