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

# --- ABA ✏️ EDIÇÃO (Reescrita do zero) ---
with abas[2]:
    st.header("✏️ Atualização de Tarefa")

    arquivos = listar_arquivos_json()
    periodos = sorted([a.replace("tarefas_", "").replace(".json", "") for a in arquivos])

    if not periodos:
        st.warning("⚠️ Nenhum período encontrado.")
    else:
        periodo = st.selectbox("📂 Período da Tarefa", periodos, format_func=lambda x: f"{x[:4]}/{x[5:]}")
        ano, mes = periodo.split("_")
        dados_json, _ = carregar_json_github(ano, mes)

        id_editar = st.text_input("🔍 Digite o ID da Tarefa que deseja editar:")

        if id_editar:
            tarefas = [t for t in dados_json if t["ID Tarefa"] == id_editar]

            if not tarefas:
                st.warning(f"❌ Nenhuma tarefa encontrada com ID {id_editar} no período selecionado.")
                registrar_log(f"⚠️ ID {id_editar} não localizado em tarefas_{ano}_{mes}.json")
            else:
                ref = tarefas[0]
                st.success(f"✅ Tarefa {id_editar} localizada. Preencha os novos dados abaixo para atualizar.")

                # Formulário de edição
                col1, col2, col3 = st.columns([1, 4, 1])
                with col2:
                    novo_titulo = st.text_input("Novo Título da Tarefa", value=ref["Título Tarefa"])
                    nova_desc = st.text_area("Nova Descrição", value=ref.get("Descrição", ""), height=80)

                    tipos_atuais = {t["Tipo Subtarefa"] for t in tarefas}
                    st.markdown("**Subtarefas Ativas:**")
                    t1 = st.checkbox("📝 Texto", value="Texto" in tipos_atuais)
                    t2 = st.checkbox("🎨 Layout", value="Layout" in tipos_atuis)
                    t3 = st.checkbox("💻 HTML", value="HTML" in tipos_atuais)

                    datas_atuais = [datetime.strptime(t["Data Entrega"], "%Y-%m-%d").date() for t in tarefas]
                    nova_data = st.date_input("Nova Data de Entrega", value=max(datas_atuais))

                st.markdown("—")
                confirmar = st.button("💾 Confirmar Atualização")

                if confirmar:
                    st.session_state["edicao_pendente"] = {
                        "id": id_editar,
                        "ano": ano,
                        "mes": mes,
                        "titulo": novo_titulo,
                        "descricao": nova_desc,
                        "tipos": {
                            "Texto": t1,
                            "Layout": t2,
                            "HTML": t3
                        },
                        "data_final": nova_data.isoformat(),
                        "original": dados_json
                    }
                    st.success("✅ Dados prontos para atualização. Clique abaixo para salvar.")

if "edicao_pendente" in st.session_state:
    st.markdown("### 💡 Revisar e Confirmar Atualização")

    if st.button("🚀 Executar Atualização da Tarefa"):
        try:
            dados = st.session_state["edicao_pendente"]
            id_editar = dados["id"]
            ano, mes = dados["ano"], dados["mes"]
            novo_titulo = dados["titulo"]
            nova_desc = dados["descricao"]
            tipos_selecionados = [k for k, v in dados["tipos"].items() if v]
            data_final = datetime.strptime(dados["data_final"], "%Y-%m-%d").date()
            dados_json = dados["original"]

            if not tipos_selecionados:
                st.error("❌ Nenhuma subtarefa selecionada.")
                registrar_log(f"❌ Atualização cancelada: nenhuma subtarefa marcada para ID {id_editar}")
                del st.session_state["edicao_pendente"]
            else:
                registrar_log(f"🔄 Atualizando tarefa {id_editar} em tarefas_{ano}_{mes}.json")

                # 1. Remover tarefa antiga
                dados_json_filtrado = [d for d in dados_json if d["ID Tarefa"] != id_editar]
                registrar_log(f"🗑️ Tarefa {id_editar} removida do conteúdo.")

                # 2. Recriar novas subtarefas
                novas_subs = []
                dias_ajuste = len(tipos_selecionados) - 1
                for i, tipo in enumerate(sorted(tipos_selecionados, key=lambda x: ["Texto", "Layout", "HTML"].index(x))):
                    base = retroceder_dias_uteis(data_final, dias_ajuste - i) if dias_ajuste else data_final
                    data_entrega = encontrar_data_disponivel(base, tipo, dados_json_filtrado)

                    novas_subs.append({
                        "ID Tarefa": id_editar,
                        "Título Tarefa": novo_titulo,
                        "Subtarefa": str(["Texto", "Layout", "HTML"].index(tipo) + 1),
                        "Título Subtarefa": f"{tipo}_{novo_titulo}",
                        "Tipo Subtarefa": tipo,
                        "Descrição": nova_desc,
                        "Data Cadastro": datetime.today().strftime("%Y-%m-%d"),
                        "Data Entrega": str(data_entrega)
                    })

                dados_json_filtrado.extend(novas_subs)

                # 3. Salvar no GitHub com SHA atual
                g = Github(GITHUB_TOKEN)
                repo = g.get_user().get_repo(GITHUB_REPO)
                caminho = github_file_url(ano, mes)
                arquivo = repo.get_contents(caminho, ref=BRANCH)
                sha_arquivo = arquivo.sha
                repo.update_file(
                    path=caminho,
                    message=f"Atualização da tarefa {id_editar}",
                    content=json.dumps(dados_json_filtrado, ensure_ascii=False, indent=4),
                    sha=sha_arquivo,
                    branch=BRANCH
                )

                st.success(f"✅ Tarefa {id_editar} atualizada com sucesso!")
                registrar_log(f"✅ Atualização da tarefa {id_editar} gravada no GitHub.")

                del st.session_state["edicao_pendente"]

        except Exception as e:
            st.error(f"❌ Erro ao atualizar tarefa: {e}")
            registrar_log(f"❌ Falha na atualização da tarefa {id_editar}: {e}")

# --- ABA LOG ---
with abas[3]:
    st.header("📜 LOG do Sistema")

    if not st.session_state.log:
        st.info("ℹ️ Nenhuma ação registrada nesta sessão.")
    else:
        for linha in reversed(st.session_state.log):
            st.code(linha)
