# app.py
import streamlit as st
import pandas as pd
import json
import base64
import requests
from datetime import datetime, date, timedelta
import holidays
from github import Github
import os

# GitHub config
GITHUB_USER = st.secrets["github"]["user"]
GITHUB_REPO = st.secrets["github"]["repo"]
GITHUB_TOKEN = st.secrets["github"]["token"]
BRANCH = st.secrets["github"]["branch"]

feriados_br = holidays.Brazil()

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

def caminho_arquivo_local(ano, mes):
    return f"/tmp/tarefas_{ano}_{mes}.json"

def baixar_arquivo_json_local(ano, mes, caminho_local):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{github_file_url(ano, mes)}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        content = base64.b64decode(response.json()["content"])
        with open(caminho_local, "wb") as f:
            f.write(content)
        return response.json()["sha"]
    else:
        st.error(f"❌ Falha ao baixar arquivo do GitHub: {response.status_code}")
        return None

def sobrescrever_arquivo_github(ano, mes, caminho_local, sha_antigo):
    g = Github(GITHUB_TOKEN)
    repo = g.get_user().get_repo(GITHUB_REPO)
    path = github_file_url(ano, mes)

    with open(caminho_local, "r", encoding="utf-8") as f:
        conteudo = f.read()

    try:
        repo.update_file(
            path=path,
            message=f"Tarefa editada via app - {ano}/{mes}",
            content=conteudo,
            sha=sha_antigo,
            branch=BRANCH
        )
        return True
    except Exception as e:
        st.error(f"❌ Erro ao sobrescrever no GitHub: {e}")
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

# Interface principal com abas
st.set_page_config(page_title="Provisionador de Tarefas", layout="wide")
st.title("🗂️ Provisionador de Tarefas")

# Abas principais
aba = st.tabs(["📋 Cadastro", "🔍 Consulta", "✏️ Edição"])

# --- Aba Edição ---
with aba[2]:
    st.header("✏️ Edição de Tarefas")

    arquivos_json = listar_arquivos_json()
    periodos = sorted([a.replace("tarefas_", "").replace(".json", "") for a in arquivos_json])

    if not periodos:
        st.warning("⚠️ Nenhum período encontrado.")
    else:
        periodo_edicao = st.selectbox("📁 Período para edição", periodos, format_func=lambda x: f"{x[:4]}/{x[5:]}")
        ano_e, mes_e = periodo_edicao.split("_")

        caminho_local = caminho_arquivo_local(ano_e, mes_e)
        sha_arquivo = baixar_arquivo_json_local(ano_e, mes_e, caminho_local)

        if sha_arquivo and os.path.exists(caminho_local):
            with open(caminho_local, "r", encoding="utf-8") as f:
                dados_arquivo = json.load(f)

            with st.form("form_buscar_edicao"):
                col1, col2, col3, col4 = st.columns([1, 3, 3, 1])
                with col2:
                    id_editar = st.text_input("Informe o ID da Tarefa")
                    buscar = st.form_submit_button("🔍 Carregar Tarefa")

            if buscar and id_editar:
                tarefas_encontradas = [t for t in dados_arquivo if t["ID Tarefa"] == id_editar]

                if not tarefas_encontradas:
                    st.warning("❌ Tarefa não encontrada neste período.")
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
                            dados_filtrados = [d for d in dados_arquivo if d["ID Tarefa"] != id_editar]

                            datas_subs = {}
                            dias_ajuste = len(novos_tipos) - 1
                            for i, tipo in enumerate(novos_tipos):
                                base = retroceder_dias_uteis(data_final, dias_ajuste - i) if len(novos_tipos) > 1 else data_final
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

                            # Salva localmente o novo conteúdo
                            with open(caminho_local, "w", encoding="utf-8") as f:
                                json.dump(dados_filtrados, f, ensure_ascii=False, indent=4)

                            sucesso = sobrescrever_arquivo_github(ano_e, mes_e, caminho_local, sha_arquivo)

                            if sucesso:
                                st.success("✅ Tarefa atualizada com sucesso!")
                                st.experimental_rerun()
                            else:
                                st.error("❌ Falha ao salvar no GitHub.")
