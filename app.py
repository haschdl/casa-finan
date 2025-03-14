from math import nan
import math
import streamlit as st
from streamlit import session_state as ss
import pandas as pd
from pydantic import BaseModel, Field
from typing import Annotated, List, Optional, Sequence
import altair as alt
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta


class Payer(BaseModel):
    payer: str
    entrada: float
    saldo_devedor: float = 0


class Aporte(BaseModel):
    mes: Annotated[float, Field(strict=False, allow_inf_nan=True)]
    pagador: Optional[str]
    valor: Annotated[float, Field(strict=False, allow_inf_nan=True)]


# Default payers with initial contribution
default_payers = [
    Payer(payer="Pagador 1", entrada=50000),
    Payer(payer="Pagador 2", entrada=50000),
    Payer(payer="Pagador 3", entrada=50000),
]

aportes_default = [
    Aporte(mes=6, pagador="Pagador 1", valor=10000.0),
    Aporte(mes=12, pagador="Pagador 2", valor=20000.0),
    Aporte(mes=24, pagador="Pagador 3", valor=30000.0),
]

st.session_state.saldo_total = 450000


def calculate_individual_sac_tables(
    saldos_devedores, taxa_juros_anual: float, prazo_meses: int, aportes: List[Aporte]
):
    taxa_juros_mensal = (taxa_juros_anual / 100) / 12
    resultados = {}

    for p in saldos_devedores:
        amortizacao_mensal = p.saldo_devedor / prazo_meses
        saldo_atual = p.saldo_devedor
        dados = []

        for mes in range(1, prazo_meses + 1):

            juros_mes = saldo_atual * taxa_juros_mensal
            prestacao_mes = amortizacao_mensal + juros_mes
            saldo_atual -= amortizacao_mensal

            aportes_mes = [a for a in aportes if a.mes == mes and p.payer == a.pagador]
            for aporte in aportes_mes:
                if not math.isnan(aporte.valor):
                    saldo_atual -= aporte.valor

            if saldo_atual < 0:
                saldo_atual = 0

            dados.append(
                [
                    p.payer,
                    mes,
                    (ss.data_inicio_pagamento + relativedelta(months=mes)).strftime(
                        "%Y-%m"
                    ),
                    saldo_atual,
                    amortizacao_mensal,
                    juros_mes,
                    prestacao_mes,
                ]
            )

        df = pd.DataFrame(
            dados,
            columns=[
                "Pagador",
                "Mês_i",
                "Mês",
                "Saldo Devedor",
                "Amortização",
                "Juros",
                "Prestação",
            ],
        )
        resultados[p.payer] = df

    return resultados


def update_saldo(payers: Sequence[Payer]):
    saldos_devedores: List[Payer] = []
    for e in payers:
        saldo = (st.session_state.saldo_total / len(payers)) - e.entrada
        e.saldo_devedor = saldo
        saldos_devedores.append(e)
    return saldos_devedores


def main():
    st.set_page_config(page_title="Parcelator", layout="centered")
    col1, col2 = st.columns([1, 3])
    with col1:
        st.image("parcelator.png", width=200)  # Add the logo here
    with col2:
        st.title("Simulador de Financiamento")
    st.subheader("Calcule parcelas com múltiplos pagadores e aportes adicionais")

    if "saldos_devedores" not in st.session_state:
        st.session_state.saldos_devedores = update_saldo(default_payers)

    if "aportes" not in st.session_state:
        st.session_state.aportes = aportes_default

    # Section 1: Loan Inputs
    st.header("1. Informações do Empréstimo")
    saldo_updated = st.number_input(
        "Saldo Devedor Total (R$)", value=st.session_state.saldo_total, step=10000
    )
    if saldo_updated:
        st.session_state.saldo_total = saldo_updated
        update_saldo(st.session_state.saldos_devedores)
    taxa_juros_anual = st.number_input("Taxa de Juros Anual (%)", value=7.5, step=0.1)
    prazo_meses = st.number_input("Duração (meses)", value=120, step=1)

    def last_day_of_next_month():
        today = date.today()
        first_day_next_month = date(
            today.year + today.month // 12, today.month % 12 + 1, 1
        )
        last_day_next_month = first_day_next_month + timedelta(days=-1)
        return last_day_next_month

    ss.data_inicio_pagamento = st.date_input(
        "Data de Início do Pagamento", value=last_day_of_next_month()
    )

    # Section 2: Entradas (Down Payments)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("2. Entradas")
        col_config = {
            "payer": st.column_config.TextColumn(label="Nome"),
            "entrada": st.column_config.NumberColumn(label="Entrada"),
            "saldo_devedor": st.column_config.NumberColumn(
                label="Saldo", format="R$ %.0f"
            ),
        }
        ss.saldos_df = pd.DataFrame(
            [e.model_dump() for e in st.session_state.saldos_devedores]
        )
        ss.entradas_df = st.data_editor(
            ss.saldos_df,
            column_config=col_config,
            num_rows="dynamic",
            key="entradas_changes",
            hide_index=True,
        )
        if not ss.entradas_df.equals(ss.saldos_df):
            st.session_state.saldos_devedores = update_saldo(
                [
                    Payer(**e)
                    for e in ss.entradas_df.to_dict(orient="records")
                    if e["payer"]
                ]
            )
            st.rerun()

    with col2:
        # Section 3: Aportes (Additional Payments)
        st.subheader("3. Aportes Adicionais")
        col_config = {
            "mes": st.column_config.NumberColumn(label="Mês"),
            "pagador": st.column_config.SelectboxColumn(
                label="Pagador", options=ss.entradas_df["payer"].tolist()
            ),
            "valor": st.column_config.NumberColumn(label="Valor"),
        }
        aportes_df = pd.DataFrame([a.model_dump() for a in st.session_state.aportes])
        aportes_modified = st.data_editor(
            aportes_df,
            num_rows="dynamic",
            column_config=col_config,
            key="aportes_changes",
        )
        # check if a complete row was added
        if not aportes_modified.equals(aportes_df):
            st.session_state.aportes = [
                Aporte(**a) for a in aportes_modified.to_dict(orient="records")
            ]
            st.rerun()

    # Calculate SAC Table for each payer
    resultados = calculate_individual_sac_tables(
        st.session_state.saldos_devedores,
        taxa_juros_anual,
        prazo_meses,
        st.session_state.aportes,
    )
    # flatten the results to a list
    results_flat = [v for _, v in resultados.items()]
    results_pd = pd.concat(results_flat)

    c = (
        alt.Chart(results_pd)
        .mark_line()
        .encode(x="Mês", y="Saldo Devedor", color="Pagador")
    )
    st.altair_chart(c)

    # Shows when each payer will have its last payment
    last_payment = results_pd.groupby("Pagador")["Mês_i"].max().to_dict()
    st.subheader("Último pagamento de cada pagador:")

    # display, calculating the year and month in the future
    last_payment_data = []
    for payer, df in resultados.items():
        last_non_zero_month = df[df["Saldo Devedor"] > 0]["Mês_i"].max()
        last_payment_data.append(
            {
                "Pagador": payer,
                "Último Mês de Pagamento": (
                    ss.data_inicio_pagamento + relativedelta(months=last_non_zero_month)
                ).strftime("%B/%Y"),
            }
        )
    last_payment_df = pd.DataFrame(last_payment_data)
    st.dataframe(last_payment_df, hide_index=True)

    # Display Results

    st.subheader("Tabelas de Pagamentos Individuais (Sistema SAC)")

    for payer, df_sac in resultados.items():
        col_config = {
            "Pagador": None,
            "Mês_i": st.column_config.NumberColumn(label="Parcela"),
            "Saldo Devedor": st.column_config.ProgressColumn(
                label="Saldo Devedor",
                format="R$ %.0f",
                min_value=0,
                max_value=df_sac["Saldo Devedor"].max(),
            ),
            "Prestação": st.column_config.NumberColumn(
                label="Prestação", format="R$ %0.2f"
            ),
            "Amortização": None,
            "Juros": st.column_config.ProgressColumn(
                label="Juros",
                format="R$ %.0f",
                min_value=0,
                max_value=df_sac["Juros"].max(),
            ),
        }
        st.subheader(f"Pagamentos de {payer}")
        st.dataframe(
            df_sac, column_config=col_config, hide_index=True, use_container_width=True
        )


if __name__ == "__main__":
    main()
