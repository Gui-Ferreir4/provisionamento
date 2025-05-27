import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import calendar
import json
import os

# --- CONFIG ---
DATA_FILE = "tarefas.json"  # arquivo local para salvar as tarefas

st.set_page_config(layout="wide", page_title="Provisionamento Criação")

# --- FUNÇÕES AUXILIARES ---

def dias_uteis_no_mes(ano, mes):
    total_dias = calendar.monthrange(ano, mes)[1]
    dias_uteis = []
    for dia in range(1, total_dias + 1):
        dt = datetime(ano, mes, dia)
        if dt.weekday() < 5:
            dias_uteis.append(dt)
    return dias_uteis

def criar_subtarefas(nome, descricao, deadline, subtarefas_selecionadas):
    dias = dias_uteis_no_mes(deadline.year, deadline.month)
    while deadline.weekday() >= 5:
        deadline -= timedelta(days=1)
    try:
        idx = dias.index(deadline)
    except ValueError:
        idx = len(dias) - 1
    tarefas = []
    if 'texto' in subtarefas_selecionadas and idx - 2 >= 0:
        tarefas.append({'id': st.session_state['next_id'], 'tipo': 'Texto', 'data': dias[idx - 2].strftime("%Y-%m-%d"), 'titulo': f'{nome} - Texto', 'descricao': descricao, 'concluido': False})
        st.session_state['next_id'] += 1
    if 'layout' in subtarefas_selecionadas and idx - 1 >= 0:
        tarefas.append({'id': st.session_state['next_id'], 'tipo': 'Layout', 'data': dias[idx - 1].strftime("%Y-%m-%d"), 'titulo': f'{nome} - Layout', 'descricao': descricao, 'concluido': False})
        st.session_state['next_id'] += 1
    if 'html' in subtarefas_selecionadas:
        tarefas.append({'id': st.session_state['next_id'], 'tipo': 'HTML', 'data': dias[idx].strftime("%Y-%m-%d"), 'titulo': f'{nome} - HTML', 'descricao': descricao, 'concluido': False})
        st.session_state['next_id'] += 1
    return tarefas

def salvar_tarefas():
    with open(DATA_FILE, "w") as f:
        json.dump(st.session_state['tarefas'], f, indent=2)

def carregar_tarefas():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            dados = json.load(f)
        return dados
    return []

def atualizar_tarefa(edited):
    for idx, t in enumerate(st.session_state['tarefas']):
        if t['id'] == edited['id']:
            st.session_state['tarefas'][idx] = edited
            salvar_tarefas()
            st.success("Tarefa atualizada!")
            break

def deletar_tarefa(tarefa_id):
    st.session_state['tarefas'] = [t for t in st.session_state['tarefas'] if t['id'] != tarefa_id]
    salvar_tarefas()
    st.success("Tarefa deletada!")

# --- INICIALIZAÇÃO DO STATE ---

if 'tarefas' not in st.session_state:
    st.session_state['tarefas'] = carregar_tarefas()

if 'next_id' not in st.session_state:
    max_id = max([t['id'] for t in st.session_state['tarefas']], default=0)
    st.session_state['next_id'] = max_id + 1

if 'view' not in st.session_state:
    st.session_state['view'] = "kanban"  # ou "tabela"

# --- SIDEBAR: CADASTRO ---

st.sidebar.header("Cadastrar Tarefa")
nome = st.sidebar.text_input("Nome da tarefa")
deadline = st.sidebar.date_input("Deadline (subtarefa HTML)", datetime.now())
descricao = st.sidebar.text_area("Descrição (opcional)")
texto_chk = st.sidebar.checkbox("Texto", True)
layout_chk = st.sidebar.checkbox("Layout", True)
html_chk = st.sidebar.checkbox("HTML", True)

if st.sidebar.button("Cadastrar"):
    if not nome:
        st.sidebar.error("Nome é obrigatório")
    else:
        selecionadas = []
        if texto_chk: selecionadas.append('texto')
        if layout_chk: selecionadas.append('layout')
        if html_chk: selecionadas.append('html')
        if len(selecionadas) == 0:
            st.sidebar.error("Selecione pelo menos uma subtarefa")
        else:
            novas = criar_subtarefas(nome, descricao, deadline, selecionadas)
            st.session_state['tarefas'].extend(novas)
            salvar_tarefas()
            st.sidebar.success(f"Tarefa '{nome}' cadastrada com {len(novas)} subtarefas.")

# --- FILTROS PRINCIPAIS ---

st.title("Provisionamento Criação")

col1, col2, col3 = st.columns(3)
with col1:
    ano_selec = st.number_input("Ano", min_value=2025, max_value=2030, value=datetime.now().year)
with col2:
    mes_selec = st.selectbox("Mês", options=list(range(1, 13)), format_func=lambda x: calendar.month_name[x], index=datetime.now().month-1)
with col3:
    qtd_pecas = st.number_input("Número de peças", min_value=1, max_value=100, value=1)

if st.button("Gerar Peças Automáticas"):
    dias_uteis = dias_uteis_no_mes(ano_selec, mes_selec)
    dias_validos = dias_uteis[2:-2] if len(dias_uteis) > 4 else dias_uteis
    for i in range(qtd_pecas):
        nome_auto = f"Peça {i + 1}"
        deadline_auto = dias_validos[min(i, len(dias_validos) - 1)]
        subtarefas = ['texto', 'layout', 'html']
        novas = criar_subtarefas(nome_auto, "", deadline_auto, subtarefas)
        st.session_state['tarefas'].extend(novas)
    salvar_tarefas()
    st.success(f"{qtd_pecas} peças criadas automaticamente.")

# --- BOTOES DE VISUALIZAÇÃO ---

col_a, col_b = st.columns(2)
with col_a:
    if st.button("Visualizar Kanban"):
        st.session_state['view'] = "kanban"
with col_b:
    if st.button("Visualizar Tabela"):
        st.session_state['view'] = "tabela"

# --- VISUALIZAÇÃO ---

tarefas_df = pd.DataFrame(st.session_state['tarefas'])
if not tarefas_df.empty:
    tarefas_df['data_dt'] = pd.to_datetime(tarefas_df['data'])
    tarefas_df = tarefas_df[(tarefas_df['data_dt'].dt.year == ano_selec) & (tarefas_df['data_dt'].dt.month == mes_selec)]
else:
    tarefas_df = pd.DataFrame()

if st.session_state['view'] == "kanban":
    st.subheader("Kanban / Calendário")

    dias_uteis = dias_uteis_no_mes(ano_selec, mes_selec)

    if tarefas_df.empty:
        st.info("Nenhuma tarefa para o período selecionado.")
    else:
        # Mostrar dias úteis com tarefas agrupadas
        for dia in dias_uteis:
            dia_str = dia.strftime("%Y-%m-%d")
            st.markdown(f"### {dia.strftime('%a, %d/%m/%Y')}")
            tarefas_dia = tarefas_df[tarefas_df['data'] == dia_str]
            if tarefas_dia.empty:
                st.markdown("_Nenhuma tarefa_")
            else:
                for _, t in tarefas_dia.iterrows():
                    cor = {"Texto": "primary", "Layout": "warning", "HTML": "success"}.get(t['tipo'], "secondary")
                    status = "✔️" if t['concluido'] else "❌"
                    st.markdown(f"- <span class='badge bg-{cor}'>{t['tipo']}</span> **{t['titulo']}** {status}", unsafe_allow_html=True)

elif st.session_state['view'] == "tabela":
    st.subheader("Tabela de Tarefas")

    if tarefas_df.empty:
        st.info("Nenhuma tarefa para o período selecionado.")
    else:
        # Função para editar e deletar (simplificada)
        for idx, tarefa in tarefas_df.iterrows():
            with st.expander(f"{tarefa['titulo']} ({tarefa['tipo']}) - {tarefa['data']}"):
                novo_titulo = st.text_input("Título", tarefa['titulo'], key=f"titulo_{tarefa['id']}")
                nova_desc = st.text_area("Descrição", tarefa.get('descricao', ''), key=f"desc_{tarefa['id']}")
                concluido = st.checkbox("Concluído", tarefa['concluido'], key=f"done_{tarefa['id']}")
                col_e, col_d = st.columns([1, 4])
                with col_e:
                    if st.button("Salvar", key=f"salvar_{tarefa['id']}"):
                        edit = tarefa.to_dict()
                        edit['titulo'] = novo_titulo
                        edit['descricao'] = nova_desc
                        edit['concluido'] = concluido
                        atualizar_tarefa(edit)
                with col_d:
                    if st.button("Deletar", key=f"del_{tarefa['id']}"):
                        deletar_tarefa(tarefa['id'])
                        st.experimental_rerun()

else:
    st.info("Selecione uma visualização no menu acima.")
