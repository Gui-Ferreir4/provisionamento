import streamlit as st
from datetime import datetime, timedelta
import pandas as pd

def is_weekday(date):
    return date.weekday() < 5  # Segunda a sexta

def prev_working_day(date, offset=1):
    days_subtracted = 0
    current_date = date
    while days_subtracted < offset:
        current_date -= timedelta(days=1)
        if is_weekday(current_date):
            days_subtracted += 1
    return current_date

st.title("Cadastro de Tarefas - Com Subtarefas Selecionáveis")

with st.form("form_tarefa"):
    nome_tarefa = st.text_input("Nome da tarefa", max_chars=50)
    deadline = st.date_input("Data de entrega final (HTML)", value=datetime.today())
    descricao = st.text_area("Descrição (opcional)")
    
    st.markdown("**Subtarefas a criar:**")
    criar_texto = st.checkbox("Texto (D-2 útil)", value=True)
    criar_layout = st.checkbox("Layout (D-1 útil)", value=True)
    criar_html = st.checkbox("HTML (D)", value=True)
    
    submitted = st.form_submit_button("Cadastrar")

if submitted:
    subtarefas_list = []
    
    if criar_texto:
        texto_data = prev_working_day(deadline, 2)
        subtarefas_list.append({"Tipo": "Texto", "Prazo": texto_data, "Status": "Pendente", "Tarefa": nome_tarefa})
    if criar_layout:
        layout_data = prev_working_day(deadline, 1)
        subtarefas_list.append({"Tipo": "Layout", "Prazo": layout_data, "Status": "Pendente", "Tarefa": nome_tarefa})
    if criar_html:
        subtarefas_list.append({"Tipo": "HTML", "Prazo": deadline, "Status": "Pendente", "Tarefa": nome_tarefa})

    if not subtarefas_list:
        st.error("Selecione ao menos uma subtarefa para criar.")
    else:
        subtarefas = pd.DataFrame(subtarefas_list)
        st.success(f"Tarefa '{nome_tarefa}' cadastrada com {len(subtarefas)} subtarefa(s).")
        st.dataframe(subtarefas)
