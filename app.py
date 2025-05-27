import streamlit as st
from datetime import date, datetime
from tarefa_utils import gerar_tarefas, filtrar_tarefas, inicializar_estado

# Inicializa variáveis na sessão
inicializar_estado()

st.title("📌 Provisionamento de Demandas de Criação")

# Entrada de dados
col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
with col1:
    ano = st.number_input("Ano", min_value=2024, max_value=2030, value=date.today().year)
with col2:
    mes = st.selectbox("Mês", options=list(range(1, 13)), format_func=lambda m: date(2023, m, 1).strftime("%B").capitalize())
with col3:
    demandas = st.number_input("Peças/Mês", min_value=1, max_value=100, value=1)
with col4:
    if st.button("📥 Aplicar"):
        gerar_tarefas(ano, mes, demandas)

# Visualização em tabela
tarefas = filtrar_tarefas(st.session_state.tarefas, ano, mes)
if tarefas:
    st.subheader("📋 Tarefas Geradas")
    st.dataframe(tarefas)
else:
    st.info("Nenhuma tarefa encontrada para este período.")
