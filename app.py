import streamlit as st
import pandas as pd
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

# --- LOG ---
if "log" not in st.session_state:
    st.session_state.log = []

def registrar_log(msg):
    hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.log.append(f"[{hora}] {msg}")

# --- FUNÇÕES ---
def eh_dia_util(d): return d.weekday() < 5 and d not in feriados_br
def proximo_dia_util(d): return d + timedelta(days=1) if not eh_dia_util(d) else d
def retroceder_dias_uteis(d, dias):
    while dias > 0:
        d -= timedelta(days=1)
        if eh_dia_util(d): dias -= 1
    return d

def github_file_url(ano, mes):
    return f"data/tarefas_{ano}_{mes}.json"

def listar_arquivos_json():
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/data"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(url, headers=headers)
    return [f["name"] for f in r.json() if f["name"].endswith(".json")] if r.status_code == 200 else []

def carregar_json_github(ano, mes):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{github_file_url(ano, mes)}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        content = base64.b64decode(r.json()["content"])
        return json.loads(content), r.json()["sha"]
    return [], None

def salvar_arquivo_github(ano, mes, data):
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_user().get_repo(GITHUB_REPO)
        path = github_file_url(ano, mes)
        conteudo = json.dumps(data, ensure_ascii=False, indent=4)
        arquivo = repo.get_contents(path, ref=BRANCH)
        repo.update_file(
            path=path,
            message=f"Atualizando tarefas {ano}/{mes}",
            content=conteudo,
            sha=arquivo.sha,
            branch=BRANCH
        )
        registrar_log(f"✅ Arquivo atualizado: {path}")
        return True
    except Exception as e:
        registrar_log(f"❌ Erro ao atualizar: {e}")
        st.error(f"Erro: {e}")
        return False

def encontrar_data_disponivel(data_base, subtipo, dados):
    while True:
        if eh_dia_util(data_base):
            ocupadas = sum(1 for d in dados if d["Data Entrega"] == str(data_base) and d["Tipo Subtarefa"] == subtipo)
            if ocupadas < 5:
                return data_base
        data_base -= timedelta(days=1)

def gerar_proximo_id():
    arquivos = listar_arquivos_json()
    ids = []
    for arq in arquivos:
        ano, mes = arq.replace("tarefas_", "").replace(".json", "").split("_")
        dados, _ = carregar_json_github(ano, mes)
        ids += [int(d["ID Tarefa"]) for d in dados if d["ID Tarefa"].isdigit()]
    return max(ids) + 1 if ids else 1
# --- INTERFACE ---
st.set_page_config("Provisionador de Tarefas", layout="wide")
st.title("🧩 Provisionador de Tarefas")

abas = st.tabs(["📋 Cadastro", "🔍 Consulta", "✏️ Edição", "📜 LOG"])

# --- ABA CADASTRO ---
with abas[0]:
    st.header("📋 Cadastro de Tarefa")
    novo_id = gerar_proximo_id()

    with st.form("form_cadastro"):
        col1, col2, col3, col4 = st.columns([1, 3, 3, 1])
        with col2:
            titulo = st.text_input("Título da Tarefa")
            descricao = st.text_area("Descrição", height=80)
            st.markdown("**Subtarefas:**")
            t = st.checkbox("📝 Texto", value=True)
            l = st.checkbox("🎨 Layout", value=True)
            h = st.checkbox("💻 HTML", value=True)
            hoje = date.today()
            data_entrega = st.date_input("Data Final", value=proximo_dia_util(hoje), min_value=hoje)
            cadastrar = st.form_submit_button("💾 Cadastrar")

    if cadastrar:
        if not (t or l or h):
            st.warning("⚠️ Marque pelo menos uma subtarefa.")
        else:
            tipos = []
            if t: tipos.append("Texto")
            if l: tipos.append("Layout")
            if h: tipos.append("HTML")

            tipos.sort(key=lambda x: ["Texto", "Layout", "HTML"].index(x))
            ano, mes = data_entrega.year, f"{data_entrega.month:02}"
            dados, _ = carregar_json_github(ano, mes)

            novas = []
            dias = len(tipos) - 1
            for i, tipo in enumerate(tipos):
                base = retroceder_dias_uteis(data_entrega, dias - i) if dias > 0 else data_entrega
                data_final = encontrar_data_disponivel(base, tipo, dados)
                novas.append({
                    "ID Tarefa": str(novo_id),
                    "Título Tarefa": titulo,
                    "Subtarefa": str(["Texto", "Layout", "HTML"].index(tipo)+1),
                    "Título Subtarefa": f"{tipo}_{titulo}",
                    "Tipo Subtarefa": tipo,
                    "Descrição": descricao,
                    "Data Cadastro": datetime.today().strftime("%Y-%m-%d"),
                    "Data Entrega": str(data_final)
                })

            dados.extend(novas)
            if salvar_arquivo_github(ano, mes, dados):
                st.success("✅ Tarefa cadastrada com sucesso!")
                registrar_log(f"✅ Cadastro tarefa {novo_id} em tarefas_{ano}_{mes}.json")

# --- ABA CONSULTA ---
with abas[1]:
    st.header("🔍 Consulta de Tarefas")

    arquivos = listar_arquivos_json()
    periodos = sorted([a.replace("tarefas_", "").replace(".json", "") for a in arquivos])

    if not periodos:
        st.warning("⚠️ Nenhum arquivo encontrado.")
    else:
        periodo = st.selectbox("📂 Selecione o período", periodos, format_func=lambda x: f"{x[:4]}/{x[5:]}")
        ano, mes = periodo.split("_")
        dados, _ = carregar_json_github(ano, mes)

        if dados:
            st.dataframe(pd.DataFrame(dados), use_container_width=True)
        else:
            st.info("ℹ️ Nenhuma tarefa cadastrada neste período.")

# --- ABA EDIÇÃO ---
with abas[2]:
    st.header("✏️ Edição de Tarefa")

    arquivos = listar_arquivos_json()
    periodos = sorted([a.replace("tarefas_", "").replace(".json", "") for a in arquivos])

    if not periodos:
        st.warning("⚠️ Nenhum arquivo encontrado.")
    else:
        periodo = st.selectbox("📂 Período da tarefa", periodos, format_func=lambda x: f"{x[:4]}/{x[5:]}")
        ano, mes = periodo.split("_")
        dados_json, _ = carregar_json_github(ano, mes)

        with st.form("form_busca_edicao"):
            col1, col2, col3 = st.columns([1, 4, 1])
            with col2:
                id_editar = st.text_input("Informe o ID da Tarefa")
                buscar = st.form_submit_button("🔍 Carregar Tarefa")

        if buscar and id_editar:
            tarefas = [t for t in dados_json if t["ID Tarefa"] == id_editar]

            if not tarefas:
                st.warning("❌ Tarefa não encontrada.")
                registrar_log(f"⚠️ Tarefa {id_editar} não localizada para edição.")
            else:
                ref = tarefas[0]
                titulo_antigo = ref["Título Tarefa"]
                descricao_antiga = ref.get("Descrição", "")
                tipos_atuais = {t["Tipo Subtarefa"] for t in tarefas}
                datas_atuais = [datetime.strptime(t["Data Entrega"], "%Y-%m-%d").date() for t in tarefas]

                with st.form("form_edicao_tarefa", clear_on_submit=False):
                    col1, col2, col3 = st.columns([1, 4, 1])
                    with col2:
                        novo_titulo = st.text_input("Título da Tarefa", value=titulo_antigo)
                        nova_desc = st.text_area("Descrição", value=descricao_antiga, height=80)
                        st.markdown("**Subtarefas:**")
                        t1 = st.checkbox("📝 Texto", value="Texto" in tipos_atuais)
                        t2 = st.checkbox("🎨 Layout", value="Layout" in tipos_atuais)
                        t3 = st.checkbox("💻 HTML", value="HTML" in tipos_atuais)
                        nova_data = st.date_input("Nova data de entrega", value=max(datas_atuais))
                
                # Botão fora do form
                atualizar = st.button("💾 Atualizar Tarefa")
                
                # Execução da lógica fora do form
                if atualizar:
                    st.info("⏳ Iniciando atualização da tarefa...")
                
                    novos_tipos = []
                    if t1: novos_tipos.append("Texto")
                    if t2: novos_tipos.append("Layout")
                    if t3: novos_tipos.append("HTML")
                
                    if not novos_tipos:
                        st.warning("⚠️ Selecione ao menos uma subtarefa.")
                    elif not eh_dia_util(nova_data):
                        st.error("❌ A data de entrega precisa ser um dia útil.")
                    else:
                        try:
                            # Etapa 1: carrega SHA atual
                            g = Github(GITHUB_TOKEN)
                            repo = g.get_user().get_repo(GITHUB_REPO)
                            caminho = github_file_url(ano, mes)
                            arquivo = repo.get_contents(caminho, ref=BRANCH)
                            conteudo = json.loads(arquivo.decoded_content.decode())
                            sha_arquivo = arquivo.sha
                            registrar_log(f"📂 SHA atualizado: {sha_arquivo}")
                            st.success("✅ SHA carregado com sucesso.")
                
                            # Etapa 2: remove tarefa antiga
                            conteudo = [item for item in conteudo if item["ID Tarefa"] != id_editar]
                            registrar_log(f"🗑️ Tarefa {id_editar} removida.")
                
                            # Etapa 3: monta novas subtarefas
                            novas_subs = []
                            dias_ajuste = len(novos_tipos) - 1
                            for i, tipo in enumerate(sorted(novos_tipos, key=lambda x: ["Texto", "Layout", "HTML"].index(x))):
                                base = retroceder_dias_uteis(nova_data, dias_ajuste - i) if dias_ajuste else nova_data
                                data_final = encontrar_data_disponivel(base, tipo, conteudo)
                                novas_subs.append({
                                    "ID Tarefa": id_editar,
                                    "Título Tarefa": novo_titulo,
                                    "Subtarefa": str(["Texto", "Layout", "HTML"].index(tipo)+1),
                                    "Título Subtarefa": f"{tipo}_{novo_titulo}",
                                    "Tipo Subtarefa": tipo,
                                    "Descrição": nova_desc,
                                    "Data Cadastro": datetime.today().strftime("%Y-%m-%d"),
                                    "Data Entrega": str(data_final)
                                })
                
                            conteudo.extend(novas_subs)
                
                            # Etapa 4: grava com update_file
                            repo.update_file(
                                path=caminho,
                                message=f"Atualizando tarefa {id_editar}",
                                content=json.dumps(conteudo, ensure_ascii=False, indent=4),
                                sha=sha_arquivo,
                                branch=BRANCH
                            )
                
                            st.success("✅ Tarefa atualizada com sucesso!")
                            registrar_log(f"✅ Tarefa {id_editar} atualizada no GitHub com SHA {sha_arquivo}.")
                
                        except Exception as e:
                            erro_msg = f"❌ Erro ao atualizar: {e}"
                            st.error(erro_msg)
                            registrar_log(erro_msg)


# --- ABA LOG ---
with abas[3]:
    st.header("📜 LOG do Sistema")

    if not st.session_state.log:
        st.info("ℹ️ Nenhuma ação registrada nesta sessão.")
    else:
        for linha in reversed(st.session_state.log):
            st.code(linha)
