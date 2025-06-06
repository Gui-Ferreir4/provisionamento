# app.py
import streamlit as st
import pandas as pd
import json
import base64
import requests
from datetime import datetime, date, timedelta
import holidays

# GitHub config
GITHUB_USER = st.secrets["github"]["user"]
GITHUB_REPO = st.secrets["github"]["repo"]
GITHUB_TOKEN = st.secrets["github"]["token"]
BRANCH = st.secrets["github"]["branch"]

# Feriados nacionais
feriados_br = holidays.Brazil()

def eh_dia_util(data):
    return data.weekday() < 5 and data not in feriados_br

def dia_util_anterior(data):
    while not eh_dia_util(data):
        data -= timedelta(days=1)
    return data

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

def salvar_json_github(ano, mes, data, sha=None):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{github_file_url(ano, mes)}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    conteudo = json.dumps(data, ensure_ascii=False, indent=4)
    payload = {
        "message": f"Atualizando tarefas {ano}/{mes}",
        "content": base64.b64encode(conteudo.encode()).decode(),
        "branch": BRANCH
    }
    if sha:
        payload["sha"] = sha
    requests.put(url, headers=headers, json=payload)

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

# Interface principal com abas
st.set_page_config(page_title="Provisionador de Tarefas", layout="wide")
st.title("🗂️ Provisionador de Tarefas")

aba = st.tabs(["📋 Cadastro", "🔍 Consulta"])

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
            data_final = st.date_input("Data de Entrega", value=hoje if eh_dia_util(hoje) else proximo_dia_util(hoje), min_value=hoje)
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
            dados_json, sha = carregar_json_github(ano_e, mes_e)
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

            salvar_json_github(ano_e, mes_e, dados_json, sha)
            st.success(f"✅ Tarefa '{titulo}' cadastrada com sucesso!")
# --- Aba Consulta ---
with aba[1]:
    st.header("🔍 Consulta e Edição de Tarefas")
    arquivos_json = listar_arquivos_json()
    if arquivos_json:
        periodos = sorted(list(set(
            (a.replace("tarefas_", "").replace(".json", "")) for a in arquivos_json
        )))
    else:
        st.warning("⚠️ Nenhum período encontrado.")
        st.stop()

    periodo_consulta = st.selectbox(
        "📅 Selecione o período para consulta e edição",
        periodos,
        format_func=lambda x: f"{x[:4]}/{x[5:]}"
    )

    ano_c, mes_c = periodo_consulta.split("_")
    dados_consulta, sha_consulta = carregar_json_github(ano_c, mes_c)

    if dados_consulta:
        st.subheader(f"📄 Tarefas cadastradas para {ano_c}/{mes_c}")
        df = pd.DataFrame(dados_consulta)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("ℹ️ Nenhuma tarefa cadastrada para este período.")
        st.stop()

    st.subheader("✏️ Edição de Tarefa")
    with st.form("form_editar_tarefa"):
        col1, col2, col3, col4 = st.columns([1, 3, 3, 1])
        with col2:
            id_editar = st.text_input("ID da Tarefa que deseja editar")
            buscar = st.form_submit_button("🔍 Carregar tarefa")

    if buscar:
        tarefas = [t for t in dados_consulta if t["ID Tarefa"] == id_editar]
        if not tarefas:
            st.warning("⚠️ Tarefa não encontrada no período selecionado.")
        else:
            tarefa_ref = tarefas[0]
            titulo_atual = tarefa_ref["Título Tarefa"]
            descricao_atual = tarefa_ref.get("Descrição", "")
            tipos_atuais = {t["Tipo Subtarefa"] for t in tarefas}
            datas_entregas = [datetime.strptime(t["Data Entrega"], "%Y-%m-%d").date() for t in tarefas]

            with st.form("form_editar_campos"):
                col1, col2, col3, col4 = st.columns([1, 3, 3, 1])
                with col2:
                    novo_titulo = st.text_input("Título da Tarefa", value=titulo_atual)
                    nova_descricao = st.text_area("Descrição da Tarefa", value=descricao_atual, height=80)
                    st.markdown("**Atualize as Subtarefas:**")
                    editar_texto = st.checkbox("📝 Texto", value="Texto" in tipos_atuais)
                    editar_layout = st.checkbox("🎨 Layout", value="Layout" in tipos_atuais)
                    editar_html = st.checkbox("💻 HTML", value="HTML" in tipos_atuais)
                    data_entrega_nova = st.date_input("Nova Data de Entrega", value=max(datas_entregas))
                    confirmar = st.form_submit_button("💾 Atualizar Tarefa")

            if confirmar:
                if not (editar_texto or editar_layout or editar_html):
                    st.warning("⚠️ Selecione ao menos uma subtarefa.")
                elif not eh_dia_util(data_entrega_nova):
                    st.error("❌ A data de entrega deve ser dia útil e não feriado.")
                else:
                    # Remove todas as subtarefas antigas
                    dados_consulta = [d for d in dados_consulta if d["ID Tarefa"] != id_editar]
            
                    # Recria subtarefas conforme nova seleção
                    tipos_novos = []
                    if editar_texto: tipos_novos.append("Texto")
                    if editar_layout: tipos_novos.append("Layout")
                    if editar_html: tipos_novos.append("HTML")
            
                    tipos_novos.sort(key=lambda x: ["Texto", "Layout", "HTML"].index(x))
                    datas_subtarefas = {}
                    dias_ajuste = len(tipos_novos) - 1
            
                    for idx, tipo in enumerate(tipos_novos):
                        base = data_entrega_nova if len(tipos_novos) == 1 else retroceder_dias_uteis(data_entrega_nova, dias_ajuste - idx)
                        datas_subtarefas[tipo] = encontrar_data_disponivel(base, tipo, dados_consulta)
            
                    novas_subs = []
                    for tipo in tipos_novos:
                        id_sub = str(["Texto", "Layout", "HTML"].index(tipo) + 1)
                        novas_subs.append({
                            "ID Tarefa": id_editar,
                            "Título Tarefa": novo_titulo,
                            "Subtarefa": id_sub,
                            "Título Subtarefa": f"{tipo}_{novo_titulo}",
                            "Tipo Subtarefa": tipo,
                            "Descrição": nova_descricao,
                            "Data Cadastro": datetime.today().strftime('%Y-%m-%d'),
                            "Data Entrega": str(datas_subtarefas[tipo])
                        })
            
                    dados_consulta.extend(novas_subs)
                    salvar_json_github(ano_c, mes_c, dados_consulta, sha_consulta)
                    st.success(f"✅ Tarefa {id_editar} atualizada com sucesso.")
                    st.experimental_rerun()
