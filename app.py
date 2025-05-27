import streamlit as st
from datetime import datetime, timedelta
import pandas as pd

# Funções para cálculo de dias úteis
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

# Iniciar ou recuperar lista de subtarefas no estado da sessão
if "subtarefas" not in st.session_state:
    st.session_state.subtarefas = pd.DataFrame(columns=["Tarefa", "Descricao", "Tipo", "Prazo", "Status"])

st.title("Cadastro e Visualização Kanban de Subtarefas")

with st.form("form_tarefa"):
    nome_tarefa = st.text_input("Nome da tarefa", max_chars=50)
    deadline = st.date_input("Data de entrega final (HTML)", value=datetime.today())
    descricao = st.text_area("Descrição (opcional)")
    
    st.markdown("**Selecione as subtarefas a criar:**")
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

# Exibir Kanban simples
st.markdown("---")
st.header("Visualização Kanban")

# Filtrar subtarefas por status
df = st.session_state.subtarefas.copy()

kanban_cols = ["Pendente", "Em andamento", "Concluído"]
cols = st.columns(len(kanban_cols))

for idx, status in enumerate(kanban_cols):
    with cols[idx]:
        st.subheader(status)
        tarefas_status = df[df["Status"] == status]
        if tarefas_status.empty:
            st.write("_Nenhuma tarefa aqui_")
        else:
            for _, row in tarefas_status.iterrows():
                st.markdown(f"""
                **{row['Tipo']}**  
                Tarefa: {row['Tarefa']}  
                Prazo: {row['Prazo'].strftime('%d/%m/%Y')}  
                Descrição: {row['Descricao'] if row['Descricao'] else '-'}  
                """)
