# -*- coding: utf-8 -*-
"""Dashboard BI do HUOL/UFRN — Streamlit + Plotly + PostgreSQL.

Execução (a partir da raiz do projeto):
    streamlit run src/dashboard/app.py

Todas as métricas são derivadas do Data Warehouse (esquema estrela) ou de
conjuntos analíticos da camada Ouro — nenhum valor estático ou simulado.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import streamlit as st

from src.dashboard import data_access as dados
from src.dashboard import telas

st.set_page_config(
    page_title="HUOL/UFRN — BI de Internações Hospitalares",
    page_icon=":hospital:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------- filtros globais
def montar_filtros() -> dict:
    with st.sidebar:
        st.markdown("## :mag: Filtros")
        alternativas = dados.alternativas_filtros()

        with st.expander("Período", expanded=True):
            ano = st.selectbox(
                "Ano", ["Todos"] + [str(a) for a in alternativas["anos"]], key="f_ano"
            )
            trimestre = st.selectbox(
                "Trimestre", ["Todos", "1", "2", "3", "4"], key="f_trim"
            )
            mes = st.selectbox(
                "Mês",
                ["Todos"] + [f"{i} — {dados.MESES_NOME[i]}" for i in range(1, 13)],
                key="f_mes",
            )

        with st.expander("Perfil e origem", expanded=True):
            especialidade = st.selectbox(
                "Especialidade", ["Todas"] + alternativas["especialidades"], key="f_esp"
            )
            municipio = st.selectbox(
                "Município", ["Todos"] + alternativas["municipios"], key="f_mun"
            )
            sexo = st.selectbox("Sexo", ["Todos"] + alternativas["sexos"], key="f_sexo")
            faixa = st.selectbox(
                "Faixa etária", ["Todas"] + alternativas["faixas"], key="f_faixa"
            )

        if st.button(":wastebasket: Limpar filtros", use_container_width=True):
            for k in ["f_ano", "f_trim", "f_mes", "f_esp", "f_mun", "f_sexo", "f_faixa"]:
                st.session_state.pop(k, None)
            st.rerun()

        st.markdown("---")
        st.caption(
            "Fonte: dados abertos oficiais do HUOL/UFRN (gov.br), 2024–2025. "
            "Indicadores derivados do Data Warehouse validado."
        )

    return {
        "ano": int(ano) if ano != "Todos" else None,
        "trimestre": int(trimestre) if trimestre != "Todos" else None,
        "mes": int(mes.split(" —")[0]) if mes != "Todos" else None,
        "especialidade": especialidade if especialidade != "Todas" else None,
        "municipio": municipio if municipio != "Todos" else None,
        "sexo": sexo if sexo != "Todos" else None,
        "faixa_etaria": faixa if faixa != "Todas" else None,
    }


def main() -> None:
    st.markdown(
        """
        <div style="padding:1.1rem 1.4rem;background:linear-gradient(90deg,#003b73 0%,#00529B 60%,#0077b6 100%);
                    border-radius:12px;margin-bottom:1.2rem;">
          <h1 style="color:#ffffff;font-size:1.65rem;margin:0;">Hospital Universitário Onofre Lopes — UFRN/EBSERH</h1>
          <p style="color:#dbe9f5;font-size:1rem;margin:.35rem 0 0 0;">
            Business Intelligence de Internações Hospitalares 2024–2025 · Rumo ao credenciamento SUS
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    filtros = montar_filtros()

    telas.TELAS = {
        "Visão Executiva": telas.visao_executiva,
        "Análise por Especialidade": telas.por_especialidade,
        "Perfil Demográfico": telas.perfil_demografico,
        "Análise Geográfica": telas.analise_geografica,
        "Sazonalidade e Evolução": telas.sazonalidade,
        "Análise de Sentimentos": telas.sentimentos,
        "Insights e Qualidade dos Dados": telas.insights_qualidade,
    }
    escolha = st.sidebar.radio(
        "Navegação",
        list(telas.TELAS.keys()),
        key="navegacao",
        label_visibility="collapsed",
    )

    try:
        telas.TELAS[escolha](filtros)
    except Exception as exc:  # erro de conexão etc. — estado explícito
        st.error(
            "Não foi possível consultar o Data Warehouse. Verifique se o serviço "
            "PostgreSQL está ativo (`docker compose up -d`) e recarregue a página."
        )
        st.caption(f"Detalhe técnico: {exc}")


if __name__ == "__main__":
    main()
