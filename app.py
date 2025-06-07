# app.py
import streamlit as st
import pandas as pd
import json
import base64
import requests
from datetime import datetime, date, timedelta
import holidays
from github import Github

# GitHub config
GITHUB_USER = st.secrets["github"]["user"]
GITHUB_REPO = st.secrets["github"]["repo"]
GITHUB_TOKEN = st.secrets["github"]["token"]
BRANCH = st.secrets["github"]["branch"]

feriados_br = holidays.Brazil()

# Inicializa log de sessão
if "log" not in st.session_state:
    st.session_state.log = []

def registrar_log(msg):
    data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.log.append(f"[{data_hora}] {msg}")

# Utilitários de datas
def eh_dia_util(data):
    return data.weekday() < 5 and data not in feriados_br

def proximo_dia_util(data):
    while not eh_dia_util(data):
        data += timedelta(days=1)
    return data

def retroceder_dias_uteis(base, dias_uteis):
    atual = base
    while dias_uteis > 0:
        atual -= timedelta(days=1)
        if eh_dia_util(atual) and atual.month == base.month:
            dias_uteis -= 1
    return atual

# Arquivo e GitHub
def github_file_url(ano, mes):
    return f"data/tarefas_{ano}_{mes}.json"

def listar_arquivos_json():
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/data"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return [a["name"] for a in response.json() if a["name"].endswith(".json")]
    return []

def carregar_json_github(ano, mes):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{github_file_url(ano, mes)}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        content = base64.b64decode(response.json()["content"])
        return json.loads(content), response.json()["sha"]
    return [], None

def salvar_arquivo_github(ano, mes, data):
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_user().get_repo(GITHUB_REPO)
        path = github_file_url(ano, mes)
        conteudo = json.dumps(data, ensure_ascii=False, indent=4)

        # Buscar SHA mais atual do arquivo
        try:
            arquivo = repo.get_contents(path, ref=BRANCH)
            sha_arquivo = arquivo.sha
            registrar_log(f"🔄 Atualizando arquivo existente: {path} (SHA: {sha_arquivo})")
        except Exception as e:
            registrar_log(f"⚠️ Arquivo {path} não existe no GitHub. Será criado.")
            sha_arquivo = None

        # Atualizar ou criar arquivo
        if sha_arquivo:
            repo.update_file(
                path=path,
                message=f"Atualizando tarefas {ano}/{mes}",
                content=conteudo,
                sha=sha_arquivo,
                branch=BRANCH
            )
            registrar_log(f"✅ Arquivo atualizado com sucesso: {path}")
        else:
            repo.create_file(
                path=path,
                message=f"Criando tarefas {ano}/{mes}",
                content=conteudo,
                branch=BRANCH
            )
            registrar_log(f"✅ Arquivo criado com sucesso: {path}")

        return True

    except Exception as e:
        erro_msg = f"❌ Erro ao salvar no GitHub: {e}"
        st.error(erro_msg)
        registrar_log(erro_msg)
        return False


def contar_subtarefas_por_data(lista):
    contador = {}
    for item in lista:
        chave = (item["Data Entrega"], item["Tipo Subtarefa"])
        contador[chave] = contador.get(chave, 0) + 1
    return contador

def encontrar_data_disponivel(base, tipo, dados):
    contagem = contar_subtarefas_por_data(dados)
    atual = base
    while True:
        if not eh_dia_util(atual):
            atual -= timedelta(days=1)
            continue
        if contagem.get((str(atual), tipo), 0) < 5:
            return atual
        atual -= timedelta(days=1)

def gerar_proximo_id_global():
    arquivos = listar_arquivos_json()
    ids = []
    for arq in arquivos:
        ano, mes = arq.replace("tarefas_", "").replace(".json", "").split("_")
        dados, _ = carregar_json_github(ano, mes)
        ids += [int(d["ID Tarefa"]) for d in dados if d["ID Tarefa"].isdigit()]
    return max(ids) + 1 if ids else 1

# Interface com abas
st.set_page_config(page_title="Provisionador de Tarefas", layout="wide")
st.title("🗂️ Provisionador de Tarefas")

aba = st.tabs(["📋 Cadastro", "🔍 Consulta", "✏️ Edição", "📜 LOG"])

# --- Aba Cadastro ---
with aba[0]:
    st.header("➕ Cadastro de Nova Tarefa")
    novo_id = gerar_proximo_id_global()

    with st.form("form_cadastro"):
        col1, col2, col3, col4 = st.columns([1, 3, 3, 1])
        with col2:
            titulo = st.text_input("Título da Tarefa")
            descricao = st.text_area("Descrição da Tarefa", height=80)
            st.markdown("**Subtarefas:**")
            t = st.checkbox("📝 Texto", value=True)
            l = st.checkbox("🎨 Layout", value=True)
            h = st.checkbox("💻 HTML", value=True)
            hoje = date.today()
            data_final = st.date_input("Data de Entrega", value=proximo_dia_util(hoje), min_value=hoje)
            enviar = st.form_submit_button("💾 Cadastrar Tarefa")

    if enviar:
        if not (t or l or h):
            st.warning("⚠️ Selecione pelo menos uma subtarefa.")
        elif not eh_dia_util(data_final):
            st.error("❌ A data deve ser útil e não feriado.")
        else:
            tipos = []
            if t: tipos.append("Texto")
            if l: tipos.append("Layout")
            if h: tipos.append("HTML")

            tipos.sort(key=lambda x: ["Texto", "Layout", "HTML"].index(x))
            ano_e, mes_e = data_final.year, f"{data_final.month:02}"
            dados_json, _ = carregar_json_github(ano_e, mes_e)
            if not dados_json:
                dados_json = []

            dias = len(tipos) - 1
            datas = {}
            for i, tipo in enumerate(tipos):
                base = retroceder_dias_uteis(data_final, dias - i) if len(tipos) > 1 else data_final
                datas[tipo] = encontrar_data_disponivel(base, tipo, dados_json)

            for tipo in tipos:
                id_sub = str(["Texto", "Layout", "HTML"].index(tipo) + 1)
                dados_json.append({
                    "ID Tarefa": str(novo_id),
                    "Título Tarefa": titulo,
                    "Subtarefa": id_sub,
                    "Título Subtarefa": f"{tipo}_{titulo}",
                    "Tipo Subtarefa": tipo,
                    "Descrição": descricao,
                    "Data Cadastro": datetime.today().strftime('%Y-%m-%d'),
                    "Data Entrega": str(datas[tipo])
                })

            sucesso = salvar_arquivo_github(ano_e, mes_e, dados_json)
            if sucesso:
                st.success(f"✅ Tarefa '{titulo}' cadastrada com sucesso!")
                registrar_log(f"✅ Tarefa {novo_id} cadastrada no arquivo tarefas_{ano_e}_{mes_e}.json")
                st.rerun()
            else:
                st.error("❌ Erro ao salvar a tarefa.")
                registrar_log(f"❌ Falha ao cadastrar tarefa {novo_id} em tarefas_{ano_e}_{mes_e}.json")

# --- Aba Consulta ---
with aba[1]:
    st.header("🔍 Consulta de Tarefas")

    arquivos_json = listar_arquivos_json()
    periodos = sorted([a.replace("tarefas_", "").replace(".json", "") for a in arquivos_json])

    if not periodos:
        st.warning("⚠️ Nenhum período encontrado.")
    else:
        periodo_consulta = st.selectbox("📁 Período", periodos, format_func=lambda x: f"{x[:4]}/{x[5:]}")
        ano_c, mes_c = periodo_consulta.split("_")
        dados_consulta, _ = carregar_json_github(ano_c, mes_c)

        st.subheader("📄 Tarefas cadastradas")
        if dados_consulta:
            st.dataframe(pd.DataFrame(dados_consulta), use_container_width=True)
        else:
            st.info("ℹ️ Nenhuma tarefa cadastrada neste período.")

# --- Aba Edição ---
with aba[2]:
    st.header("✏️ Edição de Tarefas")

    arquivos_json = listar_arquivos_json()
    periodos = sorted([a.replace("tarefas_", "").replace(".json", "") for a in arquivos_json])

    if not periodos:
        st.warning("⚠️ Nenhum período encontrado.")
    else:
        periodo_edicao = st.selectbox("📁 Período para edição", periodos, format_func=lambda x: f"{x[:4]}/{x[5:]}")
        ano, mes = periodo_edicao.split("_")
        path_arquivo = github_file_url(ano, mes)

        g = Github(GITHUB_TOKEN)
        repo = g.get_user().get_repo(GITHUB_REPO)

        try:
            conteudo = repo.get_contents(path_arquivo, ref=BRANCH)
            dados_json = json.loads(conteudo.decoded_content.decode())
            sha_atual = conteudo.sha
            registrar_log(f"📂 Arquivo carregado: {path_arquivo} (SHA: {sha_atual})")
        except Exception as e:
            st.error(f"❌ Erro ao carregar o arquivo: {e}")
            registrar_log(f"❌ Erro ao carregar {path_arquivo}: {e}")
            dados_json = []
            sha_atual = None

        with st.form("form_buscar_edicao"):
            col1, col2, col3, col4 = st.columns([1, 3, 3, 1])
            with col2:
                id_editar = st.text_input("Informe o ID da Tarefa")
                buscar = st.form_submit_button("🔍 Carregar Tarefa")

        if buscar and id_editar:
            tarefas_encontradas = [t for t in dados_json if t["ID Tarefa"] == id_editar]

            if not tarefas_encontradas:
                st.warning("❌ Tarefa não encontrada neste período.")
                registrar_log(f"⚠️ ID {id_editar} não encontrado em {path_arquivo}")
            else:
                ref = tarefas_encontradas[0]
                titulo_antigo = ref["Título Tarefa"]
                descricao_antiga = ref.get("Descrição", "")
                tipos_atuais = {t["Tipo Subtarefa"] for t in tarefas_encontradas}
                datas_atuais = [datetime.strptime(t["Data Entrega"], "%Y-%m-%d").date() for t in tarefas_encontradas]

                with st.form("form_edicao_tarefa"):
                    col1, col2, col3, col4 = st.columns([1, 3, 3, 1])
                    with col2:
                        novo_titulo = st.text_input("Título da Tarefa", value=titulo_antigo)
                        nova_desc = st.text_area("Descrição da Tarefa", value=descricao_antiga, height=80)
                        st.markdown("**Subtarefas:**")
                        t1 = st.checkbox("📝 Texto", value="Texto" in tipos_atuais)
                        t2 = st.checkbox("🎨 Layout", value="Layout" in tipos_atuais)
                        t3 = st.checkbox("💻 HTML", value="HTML" in tipos_atuais)
                        data_final = st.date_input("Nova Data de Entrega", value=max(datas_atuais))
                        atualizar = st.form_submit_button("💾 Atualizar Tarefa")

                if atualizar:
                    novos_tipos = []
                    if t1: novos_tipos.append("Texto")
                    if t2: novos_tipos.append("Layout")
                    if t3: novos_tipos.append("HTML")
                
                    if not novos_tipos:
                        st.warning("⚠️ Selecione ao menos uma subtarefa.")
                    elif not eh_dia_util(data_final):
                        st.error("❌ A data de entrega precisa ser um dia útil.")
                    else:
                        novos_tipos.sort(key=lambda x: ["Texto", "Layout", "HTML"].index(x))
                        dados_filtrados = [d for d in dados_json if d["ID Tarefa"] != id_editar]
                
                        datas_subs = {}
                        dias_ajuste = len(novos_tipos) - 1
                        for i, tipo in enumerate(novos_tipos):
                            base = retroceder_dias_uteis(data_final, dias_ajuste - i) if dias_ajuste else data_final
                            datas_subs[tipo] = encontrar_data_disponivel(base, tipo, dados_filtrados)
                
                        novas_subs = []
                        for tipo in novos_tipos:
                            id_sub = str(["Texto", "Layout", "HTML"].index(tipo) + 1)
                            novas_subs.append({
                                "ID Tarefa": id_editar,
                                "Título Tarefa": novo_titulo,
                                "Subtarefa": id_sub,
                                "Título Subtarefa": f"{tipo}_{novo_titulo}",
                                "Tipo Subtarefa": tipo,
                                "Descrição": nova_desc,
                                "Data Cadastro": datetime.today().strftime("%Y-%m-%d"),
                                "Data Entrega": str(datas_subs[tipo])
                            })
                
                        dados_filtrados.extend(novas_subs)
                
                        # Usa a função unificada de gravação
                        sucesso = salvar_arquivo_github(ano, mes, dados_filtrados)
                
                        if sucesso:
                            st.success(f"✅ Tarefa {id_editar} atualizada com sucesso!")
                            registrar_log(f"✅ Tarefa {id_editar} atualizada com sucesso no arquivo {path_arquivo}")
                            st.rerun()
                        else:
                            st.error("❌ Falha ao salvar a atualização.")
                            registrar_log(f"❌ Falha ao atualizar tarefa {id_editar} no arquivo {path_arquivo}")


# --- Aba LOG ---
with aba[3]:
    st.header("📜 LOG do Sistema")

    if not st.session_state.log:
        st.info("ℹ️ Nenhum log registrado ainda.")
    else:
        for linha in reversed(st.session_state.log):
            st.code(linha)
