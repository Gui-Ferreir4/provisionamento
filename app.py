import streamlit as st
import pandas as pd
import time
import json
import base64
import requests
from datetime import datetime, date, timedelta
from github import Github
import holidays
from contextlib import contextmanager

# --- CONFIGS ---
GITHUB_USER = st.secrets["github"]["user"]
GITHUB_REPO = st.secrets["github"]["repo"]
GITHUB_TOKEN = st.secrets["github"]["token"]
BRANCH = st.secrets["github"]["branch"]
feriados_br = holidays.Brazil()

PROJETOS = [
    "ADCOS", "BANESE CARD", "CAIXA CONSÓRCIO", "CLARO - ENDOMARKETING", "CLUBE DO PADEIRO", "CONDOR",
    "COOP", "DAVÓ", "DROGA LESTE", "DALBEN", "ATACDÃO DIA  A DIA", "ELC-BRASIL - LAMER",
    "ELC-BRASIL - MAC", "ELC-BRASIL - TOOFACED", "ELC-BRASIL CLINIQUE", "ELC-BRASIL ESTÉE LAUDER",
    "ELC-BRASIL JO MALONE", "ELC-CHILE CLINIQUE", "ELC-CHILE ESTÉE LAUDER", "ELC-CHILE MAC", "EMBRATEL",
    "FEMSA", "GRUPO PEREIRA", "INTER SUPERMERCADOS", "MADERO", "MULVI PAY", "NISSEI", "SBT",
    "UNILEVER", "OMNI FINANCEIRA"
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

def validar_datas_subtarefas_no_mes(data_fim, tipos, projeto, ano, mes):
    """
    Verifica se todas as subtarefas retrocedidas ainda pertencem ao mesmo mês da data final.
    Se alguma cair no mês anterior, retorna False.
    """
    dias = len(tipos) - 1
    dados, _ = carregar_json_github(projeto, ano, mes)
    for i, tipo in enumerate(sorted(tipos, key=lambda x: ["Texto", "Layout", "HTML"].index(x))):
        base = retroceder_dias_uteis(data_fim, dias - i) if dias > 0 else data_fim
        entrega = encontrar_data_disponivel(base, tipo, dados)
        if entrega.month != data_fim.month:
            return False
    return True

def gerar_proximo_id():
    ids = []
    for projeto in PROJETOS:
        arquivos = listar_arquivos_json_por_projeto(projeto)
        for arq in arquivos:
            try:
                ano, mes = arq.replace("tarefas_", "").replace(".json", "").split("_")
                dados, _ = carregar_json_github(projeto, ano, mes)
                ids += [int(d["ID Tarefa"]) for d in dados if d["ID Tarefa"].isdigit()]
            except:
                continue
    return max(ids) + 1 if ids else 1

@contextmanager
def carregando(texto="Processando..."):
    with st.spinner(texto):
        yield

# --- ABA CADASTRO ---
with abas[0]:
    st.header("📝 Cadastro de Nova Tarefa")
    novo_id = gerar_proximo_id()

    with st.form("form_cadastro"):
        col1, col2, col3 = st.columns([1, 4, 1])
        with col2:
            projeto = st.selectbox("Projeto", PROJETOS, index=0)
            st.markdown("### Informações da Tarefa")
            titulo = st.text_input("Título da Tarefa")
            chamado = st.text_input("Chamado (número do Hike)")
            
            with st.expander("📌 Subtarefas"):
                t = st.checkbox("📝 Texto", value=True)
                l = st.checkbox("🎨 Layout", value=True)
                h = st.checkbox("💻 HTML", value=True)

            hoje = date.today()
            data_entrega = st.date_input("Data Final de Entrega", value=proximo_dia_util(hoje), min_value=hoje)
            cadastrar = st.form_submit_button("💾 Cadastrar Tarefa")

    if cadastrar:
        erros = []

        if not titulo.strip():
            erros.append("⚠️ O título da tarefa é obrigatório.")

        if not chamado.strip():
            erros.append("⚠️ O número do chamado é obrigatório.")

        tipos = []
        if t: tipos.append("Texto")
        if l: tipos.append("Layout")
        if h: tipos.append("HTML")

        if not tipos:
            erros.append("⚠️ Marque pelo menos uma subtarefa.")

        ano, mes = data_entrega.year, f"{data_entrega.month:02}"

        if not erros:
            if not validar_datas_subtarefas_no_mes(data_entrega, tipos, projeto, ano, mes):
                erros.append("❌ As subtarefas não podem ser atribuídas ao mês anterior. Altere a data final para evitar quebra de mês.")

        if erros:
            for erro in erros:
                st.error(erro)
        else:
            with carregando("Salvando tarefa no GitHub..."):
                dados, _ = carregar_json_github(projeto, ano, mes)

                novas = []
                dias = len(tipos) - 1
                for i, tipo in enumerate(sorted(tipos, key=lambda x: ["Texto", "Layout", "HTML"].index(x))):
                    base = retroceder_dias_uteis(data_entrega, dias - i) if dias > 0 else data_entrega
                    data_final = encontrar_data_disponivel(base, tipo, dados)
                    novas.append({
                        "ID Tarefa": str(novo_id),
                        "Título Tarefa": titulo.strip(),
                        "Subtarefa": str(["Texto", "Layout", "HTML"].index(tipo)+1),
                        "Título Subtarefa": f"{tipo}_{titulo.strip()}",
                        "Tipo Subtarefa": tipo,
                        "Chamado": chamado.strip(),
                        "Data Cadastro": datetime.today().strftime("%Y-%m-%d"),
                        "Data Entrega": str(data_final),
                        "Projeto": projeto
                    })

                dados.extend(novas)
                if salvar_arquivo_github(projeto, ano, mes, dados):
                    st.success("✅ Tarefa cadastrada com sucesso!")
                    registrar_log(f"✅ Cadastro tarefa {novo_id} em {projeto}/tarefas_{ano}_{mes}.json")

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
    checkboxes_tipos = {}
    checkboxes_status = {}

    with st.expander("📌 Subtarefas da Tarefa"):
        tipos = ["Texto", "Layout", "HTML"]
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

    col_btn = st.columns([1, 6, 1])
    with col_btn[1]:
        if st.button("💾 Atualizar Tarefa"):
            erros = []

            if not novo_titulo.strip():
                erros.append("⚠️ O título da tarefa é obrigatório.")

            if not novo_chamado.strip():
                erros.append("⚠️ O número do chamado é obrigatório.")

            tipos_selecionados = [k for k, v in checkboxes_tipos.items() if v]
            if not tipos_selecionados:
                erros.append("⚠️ Selecione pelo menos uma subtarefa.")

            if not erros:
                if not validar_datas_subtarefas_no_mes(nova_data, tipos_selecionados, projeto_selecionado, ano, mes):
                    erros.append("❌ As subtarefas não podem ser atribuídas ao mês anterior. Altere a data final para evitar quebra de mês.")

            if erros:
                for erro in erros:
                    st.error(erro)
            else:
                try:
                    with carregando("Salvando alterações no GitHub..."):
                        dados_filtrados = [d for d in dados_json if d["ID Tarefa"] != st.session_state.id_em_edicao]

                        novas_subs = []
                        dias_ajuste = len(tipos_selecionados) - 1
                        for i, tipo in enumerate(sorted(tipos_selecionados, key=lambda x: ["Texto", "Layout", "HTML"].index(x))):
                            base = retroceder_dias_uteis(nova_data, dias_ajuste - i) if dias_ajuste else nova_data
                            entrega = encontrar_data_disponivel(base, tipo, dados_filtrados)
                            status = "Concluído" if checkboxes_status.get(tipo) else "Pendente"
                            novas_subs.append({
                                "ID Tarefa": st.session_state.id_em_edicao,
                                "Título Tarefa": novo_titulo.strip(),
                                "Subtarefa": str(["Texto", "Layout", "HTML"].index(tipo)+1),
                                "Título Subtarefa": f"{tipo}_{novo_titulo.strip()}",
                                "Tipo Subtarefa": tipo,
                                "Chamado": novo_chamado.strip(),
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
                            message=f"Atualização da tarefa {st.session_state.id_em_edicao}",
                            content=json.dumps(dados_filtrados, ensure_ascii=False, indent=4),
                            sha=arquivo.sha,
                            branch=BRANCH
                        )

                        registrar_log(f"✅ Tarefa {st.session_state.id_em_edicao} atualizada.")
                        st.success(f"✅ Tarefa {st.session_state.id_em_edicao} atualizada com sucesso!")
                        st.session_state["modo_edicao"] = False
                        st.session_state["id_em_edicao"] = None

                        st.markdown("### 📄 Tarefas no Período Selecionado")
                        st.dataframe(pd.DataFrame(dados_filtrados), use_container_width=True)

                except Exception as e:
                    st.error(f"❌ Erro: {e}")
                    registrar_log(f"❌ Erro na atualização da tarefa {st.session_state.get('id_em_edicao')}: {e}")
