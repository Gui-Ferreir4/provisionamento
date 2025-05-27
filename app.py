import streamlit as st
import pandas as pd
from pathlib import Path
from filelock import FileLock

# Caminho para o arquivo CSV e Lock
CSV_PATH = Path("dados.csv")
LOCK_PATH = Path("dados.csv.lock")

# Função para carregar tarefas
def carregar_dados():
    if CSV_PATH.exists():
        return pd.read_csv(CSV_PATH, sep=";")
    else:
        return pd.DataFrame(columns=["ID", "Tarefa", "Status"])

# Função para salvar tarefas
def salvar_dados(df):
    df.to_csv(CSV_PATH, index=False)

# Interface principal
st.set_page_config(page_title="Provisionamento de Tarefas", layout="wide")
st.title("📋 Provisionamento de Tarefas")

# Área de cadastro
with st.form("form_tarefa"):
    st.subheader("Adicionar nova tarefa")
    tarefa = st.text_input("Descrição da tarefa")
    status = st.selectbox("Status", ["Pendente", "Concluído"])
    submitted = st.form_submit_button("Salvar")

    if submitted and tarefa:
        with FileLock(LOCK_PATH):
            df = carregar_dados()
            novo_id = df["ID"].max() + 1 if not df.empty else 1
            nova_linha = pd.DataFrame([{"ID": novo_id, "Tarefa": tarefa, "Status": status}])
            df = pd.concat([df, nova_linha], ignore_index=True)
            salvar_dados(df)
            st.success("Tarefa cadastrada com sucesso!")

# Visualização das tarefas
st.subheader("📌 Tarefas cadastradas")
with FileLock(LOCK_PATH):
    df = carregar_dados()
st.dataframe(df, use_container_width=True)
