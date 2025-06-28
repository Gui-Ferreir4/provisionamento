import streamlit as st
import streamlit.components.v1 as components
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

PROJETOS = [
    'AB Mauri',
    'Adcos',
    'Coop',
    'Davo',
    'Nissei',
    'Pague menos',
    'Tenda',
    'Unilever',
    'Zona sul'    
]

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

def github_file_url(projeto, ano, mes):
    return f"data/{projeto}/tarefas_{ano}_{mes}.json"

def listar_arquivos_json_por_projeto(projeto):
    pasta = f"data/{projeto}"
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{pasta}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return [f["name"] for f in r.json() if f["name"].endswith(".json")]
    return []

def carregar_json_github(projeto, ano, mes):
    path = github_file_url(projeto, ano, mes)
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{path}"
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
            repo.update_file(
                path=path,
                message=f"Atualizando tarefas {ano}/{mes} ({projeto})",
                content=conteudo,
                sha=arquivo.sha,
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


# --- INÍCIO DAS ABAS ---
st.set_page_config(layout="wide")
abas = st.tabs(["📋 Cadastro", "📋 Tarefas Cadastradas", "📌 Kanban", "📜 LOG"])

# --- ABA CADASTRO ---
with abas[0]:
    col1, col2, col3 = st.columns([1, 4, 1])
    with col2:
        st.header("📋 Cadastro de Tarefa")
    
        with st.form("form_cadastro"):
            projeto = st.selectbox("Projeto", PROJETOS, index=0)
            titulo = st.text_input("Título da Tarefa")
            chamado = st.text_input("Chamado (CRIA-123)")
    
        with st.expander("📌 Subtarefas", expanded=True):
            t = st.checkbox("📝 Texto", value=True)
            l = st.checkbox("🎨 Layout", value=True)
            h = st.checkbox("💻 HTML", value=True)
    
        hoje = date.today()
        data_entrega = st.date_input("Data Final", value=proximo_dia_util(hoje), min_value=hoje)
    
        cadastrar = st.form_submit_button("💾 Cadastrar")
    
    if cadastrar:
        with st.spinner("Salvando tarefa..."):
            erros = []
    
            if not titulo.strip():
                erros.append("❌ O campo título é obrigatório.")
    
            if not chamado.strip():
                erros.append("❌ O campo 'Chamado' é obrigatório.")
            elif not chamado.isdigit():
                erros.append("❌ O campo 'Chamado' deve conter apenas números.")
            elif any(t["Chamado"] == chamado for t in dados):
                erros.append(f"❌ Já existe uma tarefa com o chamado {chamado}.")
    
            if not (t or l or h):
                erros.append("⚠️ Marque pelo menos uma subtarefa.")
    
            tipos = []
            if t: tipos.append("Texto")
            if l: tipos.append("Layout")
            if h: tipos.append("HTML")
    
            tipos.sort(key=lambda x: ["Texto", "Layout", "HTML"].index(x))
            ano, mes = data_entrega.year, f"{data_entrega.month:02}"
            dados, _ = carregar_json_github(projeto, ano, mes)
            for t in dados:
                t["ID Tarefa"] = t.get("Chamado", "")
    
            novas = []
            dias = len(tipos) - 1
            data_hoje = date.today()
            mes_final = data_entrega.month
    
            for i, tipo in enumerate(tipos):
                base = retroceder_dias_uteis(data_entrega, dias - i) if dias > 0 else data_entrega
                data_final = encontrar_data_disponivel(base, tipo, dados)
    
                if data_final < data_hoje:
                    erros.append(f"❌ A subtarefa '{tipo}' esta para uma data inválida: {data_final.strftime('%d/%m/%Y')}.\nAjuste a data final da tarefa.")
    
                if data_final.month < mes_final:
                    erros.append(f"❌ A subtarefa '{tipo}' não pode ser cadastrada em um mês diferente do selecionado na data final. ({data_final.strftime('%d/%m/%Y')}). \nAjuste a data final da tarefa.")
    
                novas.append({
                    "ID Tarefa": chamado,
                    "Título Tarefa": titulo,
                    "Subtarefa": str(["Texto", "Layout", "HTML"].index(tipo)+1),
                    "Título Subtarefa": f"{tipo}_{titulo}",
                    "Tipo Subtarefa": tipo,
                    "Chamado": chamado,
                    "Data Cadastro": datetime.today().strftime("%Y-%m-%d"),
                    "Data Entrega": str(data_final),
                    "Projeto": projeto
                })
    
            if erros:
                for erro in erros:
                    st.error(erro)
                registrar_log(f"❌ Erro(s) no cadastro da tarefa {chamado}: {' | '.join(erros)}")
            else:
                dados.extend(novas)
                if salvar_arquivo_github(projeto, ano, mes, dados):
                    st.success("✅ Tarefa cadastrada com sucesso!")
                    registrar_log(f"✅ Cadastro tarefa com chamado {chamado} em {projeto}/tarefas_{ano}_{mes}.json")


# --- ABA TAREFAS CADASTRADAS ---
with abas[1]:
    col1, col2, col3 = st.columns([1, 4, 1])
    with col2:
        st.header("📋 Tarefas Cadastradas")
        projeto_selecionado = st.selectbox("Projeto", PROJETOS, key="projeto_selecionado")

        arquivos = listar_arquivos_json_por_projeto(projeto_selecionado)
        periodos = sorted([a.replace("tarefas_", "").replace(".json", "") for a in arquivos])

        if not periodos:
            st.warning("⚠️ Nenhum arquivo encontrado para este projeto.")
        else:
            if "ultimo_periodo" not in st.session_state:
                st.session_state.ultimo_periodo = None

            periodo = st.selectbox(
                "Selecione o Ano/Mês", periodos,
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
            dados_json, _ = carregar_json_github(projeto_selecionado, ano, mes)

            if "modo_edicao" not in st.session_state:
                st.session_state["modo_edicao"] = False
            if "id_em_edicao" not in st.session_state:
                st.session_state["id_em_edicao"] = None

            if st.session_state.get("tarefa_atualizada"):
                st.success(f"✅ {st.session_state['tarefa_atualizada']}")
                del st.session_state["tarefa_atualizada"]

            id_input = st.text_input("✏️ Digite o número do Chamado para editar", value="")

            if not st.session_state.modo_edicao:
                if id_input:
                    tarefas = [t for t in dados_json if t["Chamado"] == id_input]
                    if not tarefas:
                        st.warning(f"❌ Nenhuma tarefa encontrada com o chamado {id_input}.")
                        registrar_log(f"⚠️ Chamado {id_input} não localizado em {projeto_selecionado}/tarefas_{ano}_{mes}.json")
                    else:
                        st.session_state.modo_edicao = True
                        st.session_state.id_em_edicao = id_input
                        st.rerun()
                else:
                    if dados_json:
                        st.markdown("### 📄 Tarefas no Período Selecionado")
                        df = pd.DataFrame(dados_json)
                        df = df.drop(columns=["ID Tarefa"], errors="ignore")  # oculta ID Tarefa, mantendo foco no Chamado
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("ℹ️ Nenhuma tarefa cadastrada neste período.")

            else:
                tarefas = [t for t in dados_json if t["Chamado"] == st.session_state.id_em_edicao]
                if not tarefas:
                    st.session_state["modo_edicao"] = False
                    st.session_state["id_em_edicao"] = None
                    st.rerun()

                ref = tarefas[0]
                titulo_antigo = ref["Título Tarefa"]
                chamado_antigo = ref["Chamado"]
                tipos_atuais = {t["Tipo Subtarefa"] for t in tarefas}
                datas_atuais = [datetime.strptime(t["Data Entrega"], "%Y-%m-%d").date() for t in tarefas]

                st.markdown("### 🛠️ Editar Tarefa")
                novo_titulo = st.text_input("Novo Título", value=titulo_antigo)
                novo_chamado = st.text_area("Novo Chamado (CRIA-123)", value=chamado_antigo, height=80)

                # Validação do novo chamado
                if not novo_chamado.strip():
                    st.error("❌ O campo 'Chamado' é obrigatório.")
                    return
                elif not novo_chamado.isdigit():
                    st.error("❌ O campo 'Chamado' deve conter apenas números.")
                    return
                elif novo_chamado != chamado_antigo and any(t["Chamado"] == novo_chamado for t in dados_json):
                    st.error(f"❌ Já existe uma tarefa com o chamado {novo_chamado}.")
                    return

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

                if st.button("💾 Atualizar Tarefa"):
                    try:
                        tipos_selecionados = [k for k, v in checkboxes_tipos.items() if v]
                        if not tipos_selecionados:
                            st.error("❌ Nenhuma subtarefa foi selecionada.")
                            registrar_log(f"❌ Cancelado: nenhuma subtarefa marcada para chamado {st.session_state.id_em_edicao}")
                        else:
                            registrar_log(f"🔄 Atualizando tarefa {st.session_state.id_em_edicao} em {projeto_selecionado}/tarefas_{ano}_{mes}.json")

                            dados_filtrados = [d for d in dados_json if d["Chamado"] != st.session_state.id_em_edicao]

                            novas_subs = []
                            dias_ajuste = len(tipos_selecionados) - 1
                            for i, tipo in enumerate(sorted(tipos_selecionados, key=lambda x: ["Texto", "Layout", "HTML"].index(x))):
                                base = retroceder_dias_uteis(nova_data, dias_ajuste - i) if dias_ajuste else nova_data
                                entrega = encontrar_data_disponivel(base, tipo, dados_filtrados)
                                status = "Concluído" if checkboxes_status.get(tipo) else "Pendente"
                                novas_subs.append({
                                    "ID Tarefa": novo_chamado,
                                    "Título Tarefa": novo_titulo,
                                    "Subtarefa": str(["Texto", "Layout", "HTML"].index(tipo)+1),
                                    "Título Subtarefa": f"{tipo}_{novo_titulo}",
                                    "Tipo Subtarefa": tipo,
                                    "Chamado": novo_chamado,
                                    "Data Cadastro": datetime.today().strftime("%Y-%m-%d"),
                                    "Data Entrega": str(entrega),
                                    "Status": status,
                                    "Projeto": projeto_selecionado
                                })

                            dados_filtrados.extend(novas_subs)

                            g = Github(GITHUB_TOKEN)
                            repo = g.get_user().get_repo(GITHUB_REPO)
                            caminho = github_file_url(projeto_selecionado, ano, mes)
                            arquivo = repo.get_contents(caminho, ref=BRANCH)
                            repo.update_file(
                                path=caminho,
                                message=f"Atualização da tarefa {novo_chamado}",
                                content=json.dumps(dados_filtrados, ensure_ascii=False, indent=4),
                                sha=arquivo.sha,
                                branch=BRANCH
                            )

                            registrar_log(f"✅ Tarefa com chamado {novo_chamado} atualizada.")
                            st.session_state["tarefa_atualizada"] = f"Tarefa {novo_chamado} atualizada com sucesso!"
                            st.session_state["modo_edicao"] = False
                            st.session_state["id_em_edicao"] = None

                            st.success(f"✅ {st.session_state['tarefa_atualizada']}")
                            del st.session_state["tarefa_atualizada"]

                            st.markdown("### 📄 Tarefas no Período Selecionado")
                            st.dataframe(pd.DataFrame(dados_filtrados), use_container_width=True)

                    except Exception as e:
                        st.error(f"❌ Erro: {e}")
                        registrar_log(f"❌ Erro na atualização da tarefa {st.session_state.get('id_em_edicao')}: {e}")


# Aba 2: Kanban (full-width)
with abas[2]:
    st.markdown("## 📌 Visualização Kanban")

    # Link para abrir o HTML em nova aba (modo tela cheia)
    url_raw = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{BRANCH}/kanban.html"
    st.markdown(f"[🔗 Abrir Kanban em nova aba]({url_raw})", unsafe_allow_html=True)

    # Renderização do Kanban em tela ampla (embed na página)
    try:
        url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/kanban.html"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            content = base64.b64decode(r.json().get("content", "")).decode("utf-8")
            components.html(content, height=1000, scrolling=True)
        else:
            st.error("❌ Não foi possível carregar o arquivo kanban.html.")
    except Exception as e:
        st.error(f"Erro ao exibir o Kanban: {e}")

# --- ABA LOG ---
with abas[3]:
    col1, col2, col3 = st.columns([1, 4, 1])
    with col2:
        st.header("📜 LOG do Sistema")
    
        if not st.session_state.log:
            st.info("ℹ️ Nenhuma ação registrada nesta sessão.")
        else:
            for linha in reversed(st.session_state.log):
                st.code(linha)
