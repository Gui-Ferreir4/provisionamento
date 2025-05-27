import streamlit as st
from datetime import datetime, timedelta, date
import calendar
import pandas as pd

# Função para saber se é dia útil (seg a sex)
def is_weekday(d):
    return d.weekday() < 5

# Função para listar dias úteis de um mês/ano
def working_days(year, month):
    c = calendar.Calendar()
    days = [d for d in c.itermonthdates(year, month) if d.month == month and is_weekday(d)]
    return days

# Função para calcular dia útil anterior (offset)
def prev_working_day(d, offset=1):
    count = 0
    current = d
    while count < offset:
        current -= timedelta(days=1)
        if is_weekday(current):
            count += 1
    return current

# Inicializar dataframe de subtarefas no estado da sessão
if "subtarefas" not in st.session_state:
    st.session_state.subtarefas = pd.DataFrame(columns=["Tarefa", "Descricao", "Tipo", "Prazo", "Status"])

st.title("Cadastro de Tarefas com Subtarefas e Kanban Calendário")

with st.form("form_tarefa"):
    nome_tarefa = st.text_input("Nome da tarefa", max_chars=50)
    deadline = st.date_input("Data de entrega final (HTML)", value=datetime.today())
    descricao = st.text_area("Descrição (opcional)")
    criar_texto = st.checkbox("Texto (D-2 útil)", value=True)
    criar_layout = st.checkbox("Layout (D-1 útil)", value=True)
    criar_html = st.checkbox("HTML (D)", value=True)
    
    submitted = st.form_submit_button("Cadastrar")

if submitted:
    if not nome_tarefa.strip():
        st.error("O nome da tarefa é obrigatório.")
    else:
        subtarefas_list = []
        if criar_texto:
            texto_data = prev_working_day(deadline, 2)
            subtarefas_list.append({
                "Tarefa": nome_tarefa,
                "Descricao": descricao,
                "Tipo": "Texto",
                "Prazo": texto_data,
                "Status": "Pendente"
            })
        if criar_layout:
            layout_data = prev_working_day(deadline, 1)
            subtarefas_list.append({
                "Tarefa": nome_tarefa,
                "Descricao": descricao,
                "Tipo": "Layout",
                "Prazo": layout_data,
                "Status": "Pendente"
            })
        if criar_html:
            subtarefas_list.append({
                "Tarefa": nome_tarefa,
                "Descricao": descricao,
                "Tipo": "HTML",
                "Prazo": deadline,
                "Status": "Pendente"
            })

        if not subtarefas_list:
            st.error("Selecione ao menos uma subtarefa para criar.")
        else:
            df_novas = pd.DataFrame(subtarefas_list)
            st.session_state.subtarefas = pd.concat([st.session_state.subtarefas, df_novas], ignore_index=True)
            st.success(f"Tarefa '{nome_tarefa}' cadastrada com {len(df_novas)} subtarefa(s).")

# Exibir Kanban em formato calendário (colunas para cada dia útil do mês do deadline mais recente)

if not st.session_state.subtarefas.empty:
    # Pegar mês e ano do deadline mais recente cadastrado para exibir o calendário
    latest_deadline = st.session_state.subtarefas["Prazo"].max()
    year = latest_deadline.year
    month = latest_deadline.month
    
    dias_uteis = working_days(year, month)

    st.header(f"Kanban Calendário - {month}/{year}")

    cols = st.columns(len(dias_uteis))

    for idx, dia in enumerate(dias_uteis):
        with cols[idx]:
            st.markdown(f"### {dia.strftime('%d/%m')}")
            # Filtrar subtarefas do dia
            tarefas_dia = st.session_state.subtarefas[st.session_state.subtarefas["Prazo"] == dia]
            if tarefas_dia.empty:
                st.write("_Nenhuma subtarefa_")
            else:
                for _, row in tarefas_dia.iterrows():
                    st.markdown(f"""
                    **{row['Tipo']}**  
                    Tarefa: {row['Tarefa']}  
                    Status: {row['Status']}  
                    Descrição: {row['Descricao'] if row['Descricao'] else '-'}
                    """)
else:
    st.info("Nenhuma subtarefa cadastrada para exibir no Kanban.")
