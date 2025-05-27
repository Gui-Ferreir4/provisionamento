from datetime import date
import random
import string
import pandas as pd

def gerarUUID():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8)) + str(int(date.today().timestamp()))

def inicializar_estado():
    if 'tarefas' not in st.session_state:
        st.session_state.tarefas = []

def filtrar_tarefas(tarefas, ano, mes):
    return [t for t in tarefas if t['ano'] == ano and t['mes'] == mes]

def gerar_tarefas(ano, mes, demandas):
    dias_no_mes = date(ano, mes % 12 + 1, 1).replace(day=1).day if mes != 12 else 31
    dias_uteis = [d for d in range(1, dias_no_mes + 1)
                  if date(ano, mes, d).weekday() < 5]

    if len(dias_uteis) < 3:
        return

    primeiro, segundo = dias_uteis[0], dias_uteis[1]
    penultimo, ultimo = dias_uteis[-2], dias_uteis[-1]

    novas = []
    idx = 0
    cnt = 0
    while cnt < demandas:
        t, l, h = dias_uteis[idx % len(dias_uteis)], dias_uteis[(idx+1) % len(dias_uteis)], dias_uteis[(idx+2) % len(dias_uteis)]
        if t not in [penultimo, ultimo] and l not in [primeiro, ultimo] and h not in [primeiro, segundo]:
            for tipo, dia in zip(['texto', 'layout', 'html'], [t, l, h]):
                novas.append({
                    "id": gerarUUID(),
                    "titulo": "Tarefa XYZ",
                    "concluido": False,
                    "tipo": tipo,
                    "dia": dia,
                    "mes": mes,
                    "ano": ano
                })
            cnt += 1
        idx += 1

    # Remove duplicadas do mesmo mês
    st.session_state.tarefas = [
        t for t in st.session_state.tarefas
        if t['ano'] != ano or t['mes'] != mes
    ] + novas
