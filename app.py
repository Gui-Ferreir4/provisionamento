import streamlit as st
import pandas as pd
import json
import base64
import requests
from datetime import datetime, date, timedelta
from github import Github
import holidays

# --- CONFIGURAÇÕES ---
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

# --- VALIDAÇÕES DE DATAS ---
def eh_dia_util(d):
    return d.weekday() < 5 and d not in feriados_br

def retroceder_dias_uteis(d, dias):
    while dias > 0:
        d -= timedelta(days=1)
        if eh_dia_util(d):
            dias -= 1
    return d

def encontrar_data_disponivel(data_base, tipo_subtarefa, dados_existentes, data_final):
    tentativas = 0
    max_tentativas = 30
    alertas = []
    hoje = date.today()

    while tentativas < max_tentativas:
        tentativas += 1

        if data_base < hoje:
            alertas.append(f"📅 Subtarefa '{tipo_subtarefa}' foi ajustada porque {data_base} é anterior a hoje.")
            data_base = hoje

        if data_base.month != data_final.month or data_base.year != data_final.year:
            alertas.append(f"🚫 Quebra de mês detectada: subtarefa '{tipo_subtarefa}' ({data_base}) difere do mês da tarefa principal ({data_final}).")
            return None, alertas

        if not eh_dia_util(data_base):
            alertas.append(f"🛑 {data_base} é fim de semana ou feriado. Subtarefa '{tipo_subtarefa}' ajustada automaticamente.")
            data_base -= timedelta(days=1)
            continue

        ocupadas = sum(
            1 for d in dados_existentes
            if d["Data Entrega"] == str(data_base) and d["Tipo Subtarefa"] == tipo_subtarefa
        )

        if ocupadas >= 5:
            alertas.append(f"⚠️ Dia {data_base} já tem 5 subtarefas '{tipo_subtarefa}'. Tentando data anterior.")
            data_base -= timedelta(days=1)
            continue

        return data_base, alertas

    alertas.append(f"❌ Não foi possível encontrar data válida para subtarefa '{tipo_subtarefa}'.")
    return None, alertas

# --- FUNÇÕES AUXILIARES DE GITHUB E JSON ---

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
            # tenta atualizar se o arquivo existe
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
                # cria o arquivo se não existir
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

def gerar_proximo_id():
    arquivos = listar_arquivos_json()
    ids = []
    for arq in arquivos:
        ano, mes = arq.replace("tarefas_", "").replace(".json", "").split("_")
        dados, _ = carregar_json_github(ano, mes)
        ids += [int(d["ID Tarefa"]) for d in dados if d["ID Tarefa"].isdigit()]
    return max(ids) + 1 if ids else 1

# --- CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config("Provisionador de Tarefas", layout="wide")
st.title("🧩 Provisionador de Tarefas")

abas = st.tabs(["📋 Tarefas Cadastradas", "🔍 Consulta", "📜 LOG"])

# --- ABA UNIFICADA ---
with abas[0]:
    st.header("📋 Tarefas Cadastradas")

    arquivos = listar_arquivos_json()
    periodos = sorted([a.replace("tarefas_", "").replace(".json", "") for a in arquivos])

    if not periodos:
        st.warning("⚠️ Nenhum período disponível.")
    else:
        col1, col2, col3 = st.columns([1, 4, 1])
        with col2:
            periodo = st.selectbox("📂 Período", periodos, format_func=lambda x: f"{x[:4]}/{x[5:]}")
            ano, mes = periodo.split("_")
            dados_json, _ = carregar_json_github(ano, mes)

            if dados_json:
                st.markdown("### 📄 Tarefas Cadastradas no Período")
                st.dataframe(pd.DataFrame(dados_json), use_container_width=True)
            else:
                st.info("ℹ️ Nenhuma tarefa cadastrada neste período.")

        st.markdown("---")
        st.markdown("### 🆕 Cadastrar Nova Tarefa")

        novo_id = gerar_proximo_id()

        with col2:
            with st.form("form_cadastro"):
                titulo = st.text_input("Título da Tarefa")
                descricao = st.text_area("Descrição", height=80)
                st.markdown("**Subtarefas:**")
                t = st.checkbox("📝 Texto", value=True)
                l = st.checkbox("🎨 Layout", value=True)
                h = st.checkbox("💻 HTML", value=True)
                hoje = date.today()
                data_entrega = st.date_input("Data Final", value=hoje + timedelta(days=1), min_value=hoje)
                cadastrar = st.form_submit_button("💾 Cadastrar")

        if cadastrar:
            if not (t or l or h):
                st.warning("⚠️ Marque pelo menos uma subtarefa.")
            elif data_entrega < date.today():
                st.error("❌ A data final não pode ser anterior a hoje.")
            else:
                tipos = []
                if t: tipos.append("Texto")
                if l: tipos.append("Layout")
                if h: tipos.append("HTML")

                tipos.sort(key=lambda x: ["Texto", "Layout", "HTML"].index(x))
                novas = []
                alertas_total = []
                dias = len(tipos) - 1
                bloquear = False
                
                for i, tipo in enumerate(tipos):
                    base = retroceder_dias_uteis(data_entrega, dias - i) if dias > 0 else data_entrega
                    data_validada, alertas = encontrar_data_disponivel(base, tipo, dados_json, data_entrega)
                
                    if data_validada is None:
                        st.error(f"❌ Subtarefa '{tipo}' não pôde ser agendada. Verifique o mês ou restrições da data.")
                        registrar_log(f"❌ Subtarefa '{tipo}' rejeitada. Motivo: {alertas}")
                        bloquear = True
                        break
                
                    novas.append({
                        "ID Tarefa": str(novo_id),
                        "Título Tarefa": titulo,
                        "Subtarefa": str(["Texto", "Layout", "HTML"].index(tipo)+1),
                        "Título Subtarefa": f"{tipo}_{titulo}",
                        "Tipo Subtarefa": tipo,
                        "Descrição": descricao,
                        "Data Cadastro": datetime.today().strftime("%Y-%m-%d"),
                        "Data Entrega": str(data_validada)
                    })
                    alertas_total.extend(alertas)
                
                if not bloquear and len(novas) == len(tipos):
                    dados_json.extend(novas)
                    if salvar_arquivo_github(ano, mes, dados_json):
                        st.success("✅ Tarefa cadastrada com sucesso!")
                        registrar_log(f"✅ Cadastro tarefa {novo_id} em tarefas_{ano}_{mes}.json")
                
                for a in alertas_total:
                    st.warning(a)

        st.markdown("---")
        st.markdown("### ✏️ Editar Tarefa Existente")

        with col2:
            id_editar = st.text_input("🔍 Digite o ID da Tarefa a editar:")

        if id_editar:
            tarefas = [t for t in dados_json if t["ID Tarefa"] == id_editar]

            if not tarefas:
                with col2:
                    st.warning(f"❌ Nenhuma tarefa encontrada com ID {id_editar}.")
            else:
                ref = tarefas[0]
                titulo_antigo = ref["Título Tarefa"]
                descricao_antiga = ref.get("Descrição", "")
                tipos_atuais = {t["Tipo Subtarefa"] for t in tarefas}
                datas_atuais = [datetime.strptime(t["Data Entrega"], "%Y-%m-%d").date() for t in tarefas]

                with col2:
                    novo_titulo = st.text_input("Novo Título", value=titulo_antigo)
                    nova_desc = st.text_area("Nova Descrição", value=descricao_antiga, height=80)
                    st.markdown("**Subtarefas:**")
                    t1 = st.checkbox("📝 Texto", value="Texto" in tipos_atuais)
                    t2 = st.checkbox("🎨 Layout", value="Layout" in tipos_atuais)
                    t3 = st.checkbox("💻 HTML", value="HTML" in tipos_atuais)
                    nova_data = st.date_input("Nova Data de Entrega", value=max(datas_atuais), min_value=date.today())

                with col2:
                    if st.button("💾 Atualizar Tarefa"):
                        novos_tipos = []
                        if t1: novos_tipos.append("Texto")
                        if t2: novos_tipos.append("Layout")
                        if t3: novos_tipos.append("HTML")

                        if not novos_tipos:
                            st.warning("⚠️ Marque pelo menos uma subtarefa.")
                        else:
                            registrar_log(f"🔄 Atualizando tarefa {id_editar}")

                            dados_filtrados = [d for d in dados_json if d["ID Tarefa"] != id_editar]
                            novas_subs = []
                            alertas_total = []
                            dias = len(novos_tipos) - 1
                            bloquear = False
                            
                            for i, tipo in enumerate(sorted(novos_tipos, key=lambda x: ["Texto", "Layout", "HTML"].index(x))):
                                base = retroceder_dias_uteis(nova_data, dias - i) if dias > 0 else nova_data
                                data_validada, alertas = encontrar_data_disponivel(base, tipo, dados_filtrados, nova_data)
                            
                                if data_validada is None:
                                    st.error(f"❌ Subtarefa '{tipo}' não pôde ser agendada. Verifique o mês ou restrições.")
                                    registrar_log(f"❌ Subtarefa '{tipo}' rejeitada. Motivo: {alertas}")
                                    bloquear = True
                                    break
                            
                                novas_subs.append({
                                    "ID Tarefa": id_editar,
                                    "Título Tarefa": novo_titulo,
                                    "Subtarefa": str(["Texto", "Layout", "HTML"].index(tipo)+1),
                                    "Título Subtarefa": f"{tipo}_{novo_titulo}",
                                    "Tipo Subtarefa": tipo,
                                    "Descrição": nova_desc,
                                    "Data Cadastro": datetime.today().strftime("%Y-%m-%d"),
                                    "Data Entrega": str(data_validada)
                                })
                                alertas_total.extend(alertas)
                            
                            if not bloquear and len(novas_subs) == len(novos_tipos):
                                dados_filtrados.extend(novas_subs)
                                if salvar_arquivo_github(ano, mes, dados_filtrados):
                                    st.success("✅ Tarefa atualizada com sucesso!")
                                    registrar_log(f"✅ Tarefa {id_editar} atualizada em {ano}/{mes}")
                            
                            for a in alertas_total:
                                st.warning(a)

# --- ABA DE LOG ---
with abas[2]:
    st.header("📜 LOG do Sistema")

    if not st.session_state.log:
        st.info("ℹ️ Nenhuma ação registrada nesta sessão.")
    else:
        for linha in reversed(st.session_state.log):
            st.code(linha)
