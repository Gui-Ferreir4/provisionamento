import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

def is_weekday(date):
    return date.weekday() < 5  # 0=segunda ... 4=sexta

def prev_working_day(date, offset=1):
    # Retorna a data anterior deslocada por 'offset' dias úteis
    days_subtracted = 0
    current_date = date
    while days_subtracted < offset:
        current_date -= timedelta(days=1)
        if is_weekday(current_date):
            days_subtracted += 1
    return current_date

st.title("Cadastro de Tarefas - Fase 2")

with st.form("form_tarefa"):
    nome_tarefa = st.text_input("Nome da tarefa", max_chars=50)
    deadline = st.date_input("Data de entrega final (HTML)", value=datetime.today())
    descricao = st.text_area("Descrição (opcional)")
    submitted = st.form_submit_button("Cadastrar")

if submitted:
    # Gerar subtarefas com prazos
    texto_data = prev_working_day(deadline, 2)
    layout_data = prev_working_day(deadline, 1)
    html_data = deadline

    subtarefas = pd.DataFrame([
        {"Tipo": "Texto", "Prazo": texto_data, "Status": "Pendente", "Tarefa": nome_tarefa},
        {"Tipo": "Layout", "Prazo": layout_data, "Status": "Pendente", "Tarefa": nome_tarefa},
        {"Tipo": "HTML", "Prazo": html_data, "Status": "Pendente", "Tarefa": nome_tarefa}
    ])

    st.success(f"Tarefa '{nome_tarefa}' cadastrada com sucesso!")
    st.dataframe(subtarefas)
