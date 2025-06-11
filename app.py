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

        try:
            arquivo = repo.get_contents(path, ref=BRANCH)
            sha = arquivo.sha
            repo.update_file(
                path=path,
                message=f"Atualizando tarefas {ano}/{mes}",
                content=conteudo,
                sha=sha,
                branch=BRANCH
            )
            registrar_log(f"✅ Arquivo atualizado: {path}")
        except Exception as e:
            if "404" in str(e):
                repo.create_file(
                    path=path,
                    message=f"Criando novo arquivo tarefas_{ano}_{mes}.json",
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

abas = st.tabs(["📋 Cadastro", "📋 Tarefas Cadastradas", "📜 LOG"])

# --- ABA CADASTRO ---
with abas[0]:
    st.header("📋 Cadastro de Tarefa")
    novo_id = gerar_proximo_id()

    with st.form("form_cadastro"):
        col1, col2, col3 = st.columns([1, 4, 1])
        with col2:
            titulo = st.text_input("Título da Tarefa")
            chamado = st.text_input("Chamado (número do Hike)")
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
                    "Chamado": chamado,
                    "Data Cadastro": datetime.today().strftime("%Y-%m-%d"),
                    "Data Entrega": str(data_final)
                })

            dados.extend(novas)
            if salvar_arquivo_github(ano, mes, dados):
                st.success("✅ Tarefa cadastrada com sucesso!")
                registrar_log(f"✅ Cadastro tarefa {novo_id} em tarefas_{ano}_{mes}.json")

# --- ABA UNIFICADA: 📋 Tarefas Cadastradas ---
with abas[1]:
    col_prin = st.columns([1, 4, 1])
        with col_prin[1]:
            st.header("📋 Tarefas Cadastradas")
        
            arquivos = listar_arquivos_json()
            periodos = sorted([a.replace("tarefas_", "").replace(".json", "") for a in arquivos])
        
            if not periodos:
                st.warning("⚠️ Nenhum arquivo encontrado.")
            else:
                if "ultimo_periodo" not in st.session_state:
                    st.session_state.ultimo_periodo = None
        
                st.markdown("### 📂 Selecione o Período")
        col_top = st.columns([1, 4, 1])
        with col_top[1]:
            periodo = st.selectbox(
                "", periodos,
                format_func=lambda x: f"{x[:4]}/{x[5:]}",
                key="periodo_selecionado"
            )

        if st.session_state.ultimo_periodo is not None and st.session_state.ultimo_periodo != st.session_state.periodo_selecionado:
            st.session_state.ultimo_periodo = st.session_state.periodo_selecionado
            st.session_state["modo_edicao"] = False
            st.session_state["id_em_edicao"] = None
            st.rerun()
        else:
            st.session_state.ultimo_periodo = st.session_state.periodo_selecionado

        ano, mes = st.session_state.periodo_selecionado.split("_")
        dados_json, _ = carregar_json_github(ano, mes)

        if "modo_edicao" not in st.session_state:
            st.session_state["modo_edicao"] = False
        if "id_em_edicao" not in st.session_state:
            st.session_state["id_em_edicao"] = None

        col_main = st.columns([1, 4, 1])
        with col_main[1]:
            st.markdown("### ✏️ Digite o ID da Tarefa para editar")

            # Exibe mensagem de sucesso se tarefa foi atualizada
            if st.session_state.get("tarefa_atualizada"):
                st.success(f"✅ {st.session_state['tarefa_atualizada']}")
                del st.session_state["tarefa_atualizada"]

            id_input = st.text_input("ID da Tarefa", value="")

            if not st.session_state.modo_edicao:
                if id_input:
                    tarefas = [t for t in dados_json if t["ID Tarefa"] == id_input]
                    if not tarefas:
                        st.warning(f"❌ Nenhuma tarefa encontrada com ID {id_input}.")
                        registrar_log(f"⚠️ ID {id_input} não localizado em tarefas_{ano}_{mes}.json")
                    else:
                        st.session_state.modo_edicao = True
                        st.session_state.id_em_edicao = id_input
                        st.rerun()
                else:
                    if dados_json:
                        st.markdown("### 📄 Tarefas no Período Selecionado")
                        st.dataframe(pd.DataFrame(dados_json), use_container_width=True)
                    else:
                        st.info("ℹ️ Nenhuma tarefa cadastrada neste período.")

            else:
                tarefas = [t for t in dados_json if t["ID Tarefa"] == st.session_state.id_em_edicao]
                if not tarefas:
                    st.session_state["modo_edicao"] = False
                    st.session_state["id_em_edicao"] = None
                    st.rerun()

                ref = tarefas[0]
                titulo_antigo = ref["Título Tarefa"]
                chamado_antigo = ref.get("Chamado", "")
                tipos_atuais = {t["Tipo Subtarefa"] for t in tarefas}
                datas_atuais = [datetime.strptime(t["Data Entrega"], "%Y-%m-%d").date() for t in tarefas]

                st.markdown("### 🛠️ Editar Tarefa")
                novo_titulo = st.text_input("Novo Título", value=titulo_antigo)
                novo_chamado = st.text_area("Novo Chamado (número do Hike)", value=chamado_antigo, height=80)

                st.markdown("**Subtarefas e Status:**")
                tipos = ["Texto", "Layout", "HTML"]
                checkboxes_tipos = {}
                checkboxes_status = {}

                for tipo in tipos:
                    col_sub, col_stat = st.columns([1, 1])
                    with col_sub:
                        existe = tipo in tipos_atuais
                        checkboxes_tipos[tipo] = st.checkbox(f"✅ {tipo}", value=existe, key=f"tipo_{tipo}")
                    with col_stat:
                        if existe:
                            concluido = any(t["Tipo Subtarefa"] == tipo and t.get("Status") == "Concluído" for t in tarefas)
                            checkboxes_status[tipo] = st.checkbox(f"✔️ Concluído", value=concluido, key=f"stat_{tipo}")

                nova_data = st.date_input("Nova Data de Entrega", value=max(datas_atuais))

                col_btn = col_main
                with col_btn[1]:
                    if st.button("💾 Atualizar Tarefa"):
                        try:
                            tipos_selecionados = [k for k, v in checkboxes_tipos.items() if v]
                            if not tipos_selecionados:
                                st.error("❌ Nenhuma subtarefa foi selecionada.")
                                registrar_log(f"❌ Cancelado: nenhuma subtarefa marcada para ID {st.session_state.id_em_edicao}")
                            else:
                                registrar_log(f"🔄 Atualizando tarefa {st.session_state.id_em_edicao} no arquivo tarefas_{ano}_{mes}.json")

                                dados_filtrados = [d for d in dados_json if d["ID Tarefa"] != st.session_state.id_em_edicao]

                                novas_subs = []
                                dias_ajuste = len(tipos_selecionados) - 1
                                for i, tipo in enumerate(sorted(tipos_selecionados, key=lambda x: ["Texto", "Layout", "HTML"].index(x))):
                                    base = retroceder_dias_uteis(nova_data, dias_ajuste - i) if dias_ajuste else nova_data
                                    entrega = encontrar_data_disponivel(base, tipo, dados_filtrados)
                                    status = "Concluído" if checkboxes_status.get(tipo) else "Pendente"
                                    novas_subs.append({
                                        "ID Tarefa": st.session_state.id_em_edicao,
                                        "Título Tarefa": novo_titulo,
                                        "Subtarefa": str(["Texto", "Layout", "HTML"].index(tipo)+1),
                                        "Título Subtarefa": f"{tipo}_{novo_titulo}",
                                        "Tipo Subtarefa": tipo,
                                        "Chamado": novo_chamado,
                                        "Data Cadastro": datetime.today().strftime("%Y-%m-%d"),
                                        "Data Entrega": str(entrega),
                                        "Status": status
                                    })

                                dados_filtrados.extend(novas_subs)

                                g = Github(GITHUB_TOKEN)
                                repo = g.get_user().get_repo(GITHUB_REPO)
                                caminho = github_file_url(ano, mes)
                                arquivo = repo.get_contents(caminho, ref=BRANCH)
                                repo.update_file(
                                    path=caminho,
                                    message=f"Atualização da tarefa {st.session_state.id_em_edicao}",
                                    content=json.dumps(dados_filtrados, ensure_ascii=False, indent=4),
                                    sha=arquivo.sha,
                                    branch=BRANCH
                                )

                                registrar_log(f"✅ Tarefa {st.session_state.id_em_edicao} atualizada.")
                                st.session_state["tarefa_atualizada"] = f"Tarefa {st.session_state.id_em_edicao} atualizada com sucesso!"
                                    
                                # Corrige o estado da aba para retornar à visualização da tabela
                                st.session_state["modo_edicao"] = False
                                st.session_state["id_em_edicao"] = None
                                
                                # Exibição da tabela novamente se não estiver em modo de edição
                                if not st.session_state.modo_edicao:
                                    if dados_json:
                                        st.markdown("### 📄 Tarefas no Período Selecionado")
                                        st.dataframe(pd.DataFrame(dados_json), use_container_width=True)
                                    else:
                                        st.info("ℹ️ Nenhuma tarefa cadastrada neste período.")
                                else:
                                    # Garante limpeza do ID se for None
                                    if st.session_state.get("id_em_edicao") is None:
                                        st.session_state.pop("id_em_edicao", None)
                                #st.rerun()

                        except Exception as e:
                            st.error(f"❌ Erro: {e}")
                            registrar_log(f"❌ Erro na atualização da tarefa {st.session_state.get('id_em_edicao')}: {e}")


# --- ABA LOG ---
with abas[2]:
    st.header("📜 LOG do Sistema")

    if not st.session_state.log:
        st.info("ℹ️ Nenhuma ação registrada nesta sessão.")
    else:
        for linha in reversed(st.session_state.log):
            st.code(linha)
