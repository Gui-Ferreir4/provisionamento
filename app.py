import pandas as pd
import streamlit as st
from datetime import datetime
from pandas.tseries.offsets import BDay

# Caminho do CSV temporário
CSV_PATH = "dados.csv"

# Inicializa o DataFrame
def carregar_dados():
    try:
        return pd.read_csv(CSV_PATH, sep=";")
    except FileNotFoundError:
        return pd.DataFrame(columns=["ID_Tarefa", "Nome_Tarefa", "Tipo_Subtarefa", "Prazo", "Status"])

# Salva os dados no CSV
def salvar_dados(df):
    df.to_csv(CSV_PATH, index=False, sep=";")

# Gera subtarefas com base na data de entrega
def gerar_subtarefas(id_tarefa, nome_tarefa, data_entrega):
    subtarefas = ["Texto", "Layout", "HTML"]
    dias_offset = [-2, -1, 0]  # Dias úteis regressivos
    linhas = []

    for tipo, offset in zip(subtarefas, dias_offset):
        prazo = (data_entrega + BDay(offset)).date()
        linhas.append({
            "ID_Tarefa": id_tarefa,
            "Nome_Tarefa": nome_tarefa,
            "Tipo_Subtarefa": tipo,
            "Prazo": prazo.strftime("%Y-%m-%d"),
            "Status": "Pendente"
        })

    return pd.DataFrame(linhas)

# Interface Streamlit
st.title("📋 Cadastro de Tarefa com Subtarefas Automáticas")

# Carrega dados existentes
df = carregar_dados()

# Formulário
with st.form("nova_tarefa"):
    nome_tarefa = st.text_input("Nome da Tarefa")
    data_entrega = st.date_input("Data de Entrega Final (HTML)")
    enviar = st.form_submit_button("Cadastrar")

    if enviar and nome_tarefa and data_entrega:
        id_tarefa = df["ID_Tarefa"].max() + 1 if not df.empty else 1
        novas_subtarefas = gerar_subtarefas(id_tarefa, nome_tarefa, pd.to_datetime(data_entrega))
        df = pd.concat([df, novas_subtarefas], ignore_index=True)
        salvar_dados(df)
        st.success(f"Tarefa '{nome_tarefa}' cadastrada com 3 subtarefas.")

# Exibição dos dados
st.subheader("📄 Subtarefas Cadastradas")
if df.empty:
    st.info("Nenhuma tarefa cadastrada ainda.")
else:
    df["Prazo"] = pd.to_datetime(df["Prazo"])
    df = df.sort_values(by=["Prazo", "ID_Tarefa", "Tipo_Subtarefa"])
    st.dataframe(df, use_container_width=True)
