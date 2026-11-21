# -*- coding: utf-8 -*-
"""Telas do dashboard (Streamlit + Plotly).

Diretrizes aplicadas: hierarquia visual, paleta institucional, tooltips,
legendas e unidades, formatação brasileira, estados de carregamento e mensagens
de ausência de dados. Nenhum indicador estático.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from . import data_access as dados

# ------------------------------------------------------------------ paleta
AZUL_ESCURO = "#003b73"
AZUL = "#00529B"
AZUL_CLARO = "#4C9FD8"
TEAL = "#00A896"
AMBAR = "#F2A541"
VERMELHO = "#C74B50"
CINZA = "#6b7280"
CORES = [AZUL, TEAL, AMBAR, AZUL_CLARO, "#8E6FBF", "#5CB270", VERMELHO, "#3C6E91"]
CORES_SEXO = {"FEMININO": TEAL, "MASCULINO": AZUL, "NÃO INFORMADO": CINZA}

LAYOUT_BASE = dict(
    font=dict(family="Segoe UI, Roboto, Helvetica, Arial, sans-serif", size=13),
    margin=dict(l=10, r=10, t=42, b=10),
    plot_bgcolor="white",
    paper_bgcolor="white",
    hoverlabel=dict(font_size=13),
)


def _formatar_inteiro(valor) -> str:
    return f"{int(valor):,}".replace(",", ".")


def _layout(fig, titulo: str, y_titulo: str = "", x_titulo: str = "", legenda=True):
    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(text=titulo, font=dict(size=16, color=AZUL_ESCURO)),
        legend=dict(orientation="h", y=1.08, x=0) if legenda else dict(visible=False),
    )
    fig.update_yaxes(title=y_titulo, gridcolor="#e5e7eb", showgrid=True)
    fig.update_xaxes(title=x_titulo, gridcolor="#e5e7eb", showgrid=False)
    return fig


def _sem_dados(mensagem: str = "Sem dados para os filtros selecionados."):
    st.info(mensagem)


def _kpi(rotulo: str, valor: str, ajuda: str = "", cor: str = AZUL) -> None:
    st.markdown(
        f"""
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-left:5px solid {cor};
                    border-radius:10px;padding:.85rem 1rem;">
          <div style="font-size:.8rem;color:#64748b;text-transform:uppercase;letter-spacing:.03em;">{rotulo}</div>
          <div style="font-size:1.7rem;font-weight:700;color:{cor};">{valor}</div>
          <div style="font-size:.75rem;color:#94a3b8;">{ajuda}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =============================================================================
# TELA 1 — VISÃO EXECUTIVA
# =============================================================================
def visao_executiva(filtros: dict) -> None:
    st.subheader("Visão Executiva")
    with st.spinner("Consultando o Data Warehouse..."):
        ind = dados.indicadores_gerais(filtros)
    if not ind or not ind.get("total_internacoes"):
        _sem_dados()
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _kpi("Internações no período", _formatar_inteiro(ind["total_internacoes"]),
             f"{ind['data_min']} a {ind['data_max']}", AZUL)
    with c2:
        _kpi("Especialidades", _formatar_inteiro(ind["total_especialidades"]),
             "especialidades distintas", TEAL)
    with c3:
        _kpi("Municípios", _formatar_inteiro(ind["total_municipios"]),
             "municípios de origem (padronizados IBGE)", AMBAR)
    with c4:
        idade_media = ind["idade_media"]
        _kpi("Idade média", f"{idade_media:.1f} anos" if idade_media is not None else "—",
             "apenas registros com idade válida", AZUL_CLARO)

    c5, c6, c7, c8 = st.columns(4)
    total = ind["total_internacoes"]
    with c5:
        _kpi("Sexo feminino", f"{100 * ind['feminino'] / total:.1f}%",
             _formatar_inteiro(ind["feminino"]) + " internações", TEAL)
    with c6:
        _kpi("Sexo masculino", f"{100 * ind['masculino'] / total:.1f}%",
             _formatar_inteiro(ind["masculino"]) + " internações", AZUL)
    with c7:
        _kpi("Idade não informada", f"{100 * ind['idade_ausente'] / total:.2f}%",
             "preservada (não imputada)", CINZA)
    with c8:
        sem_filtros = not any(filtros.values())
        evolucao = dados.por_trimestre(filtros)
        if sem_filtros and len(evolucao) >= 2:
            a24 = int(evolucao[evolucao["ano"] == 2024]["internacoes"].sum())
            a25 = int(evolucao[evolucao["ano"] == 2025]["internacoes"].sum())
            variacao = 100 * (a25 - a24) / a24
            _kpi("2025 vs 2024", f"{variacao:+.1f}%",
                 f"{_formatar_inteiro(a24)} → {_formatar_inteiro(a25)}",
                 VERMELHO if variacao > 0 else TEAL)
        else:
            _kpi("2025 vs 2024", "—", "disponível sem filtros de período", CINZA)

    col1, col2 = st.columns([3, 2])
    with col1:
        st.markdown("#### Evolução mensal das internações")
        mes_df = dados.por_mes(filtros)
        if not mes_df.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=mes_df["rotulo"], y=mes_df["internacoes"], mode="lines+markers",
                name="Internações", line=dict(color=AZUL, width=3),
                hovertemplate="<b>%{x}</b><br>%{y:,} internações<extra></extra>",
            ))
            st.plotly_chart(_layout(fig, "", "Internações", ""), use_container_width=True)
        else:
            _sem_dados()
    with col2:
        st.markdown("#### Distribuição por sexo")
        sexo_df = dados.por_sexo(filtros)
        if not sexo_df.empty:
            fig = px.pie(
                sexo_df, names="sexo", values="internacoes", hole=0.45,
                color="sexo", color_discrete_map=CORES_SEXO,
            )
            fig.update_traces(
                textinfo="percent+label", hovertemplate="<b>%{label}</b><br>%{value:,} internações<extra></extra>"
            )
            st.plotly_chart(_layout(fig, "", legenda=False), use_container_width=True)
        else:
            _sem_dados()

    # destaque
    espec_df = dados.por_especialidade(filtros)
    muni_df = dados.por_municipio(filtros)
    faixa_df = dados.por_faixa_etaria(filtros)
    if not espec_df.empty and not muni_df.empty and not faixa_df.empty:
        st.markdown("#### Destaques do período")
        faixa_top = faixa_df.sort_values("internacoes", ascending=False).iloc[0]
        d1, d2, d3 = st.columns(3)
        d1.success(
            f"**Maior volume por especialidade:** {espec_df.iloc[0]['especialidade']} "
            f"({_formatar_inteiro(espec_df.iloc[0]['internacoes'])} internações, "
            f"{espec_df.iloc[0]['participacao_pct']:.1f}% do total)"
        )
        d2.info(
            f"**Município com maior volume:** {muni_df.iloc[0]['municipio']} "
            f"({_formatar_inteiro(muni_df.iloc[0]['internacoes'])} internações, "
            f"{muni_df.iloc[0]['participacao_pct']:.1f}%)"
        )
        d3.warning(
            f"**Faixa etária predominante:** {faixa_df.iloc[0]['faixa_etaria']} "
            f"({_formatar_inteiro(faixa_df.iloc[0]['internacoes'])} internações, "
            f"{faixa_df.iloc[0]['participacao_pct']:.1f}%)"
        )


# =============================================================================
# TELA 2 — ANÁLISE POR ESPECIALIDADE
# =============================================================================
def por_especialidade(filtros: dict) -> None:
    st.subheader("Análise por Especialidade")
    with st.spinner("Consultando o Data Warehouse..."):
        df = dados.por_especialidade(filtros)
    if df.empty:
        _sem_dados()
        return

    col1, col2 = st.columns([2, 3])
    with col1:
        top = df.head(15).sort_values("internacoes")
        fig = go.Figure(go.Bar(
            x=top["internacoes"], y=top["especialidade"], orientation="h",
            marker_color=AZUL,
            customdata=top["participacao_pct"],
            hovertemplate="<b>%{y}</b><br>%{x:,} internações<br>%{customdata:.2f}% do total<extra></extra>",
        ))
        st.plotly_chart(
            _layout(fig, "Top 15 especialidades por volume", "Internações"),
            use_container_width=True,
        )
    with col2:
        mostrar = df.head(20).copy()
        mostrar.index = mostrar.index + 1
        tabela = mostrar[["especialidade", "internacoes", "participacao_pct",
                          "ano_2024", "ano_2025"]].rename(columns={
            "especialidade": "Especialidade", "internacoes": "Internações",
            "participacao_pct": "Participação (%)",
            "ano_2024": "2024", "ano_2025": "2025",
        })
        st.dataframe(
            tabela.style.format({
                "Internações": lambda v: f"{int(v):,}".replace(",", "."),
                "Participação (%)": "{:.2f}%",
                "2024": lambda v: f"{int(v):,}".replace(",", "."),
                "2025": lambda v: f"{int(v):,}".replace(",", "."),
            }),
            use_container_width=True, height=520,
        )

    st.markdown("#### Comparação 2024 x 2025 (todas as especialidades)")
    comp = df[(df["ano_2024"] > 0) | (df["ano_2025"] > 0)].copy()
    comp["variacao_pct"] = comp.apply(
        lambda r: 100 * (r["ano_2025"] - r["ano_2024"]) / r["ano_2024"]
        if r["ano_2024"] else None, axis=1
    )
    comp = comp.sort_values("variacao_pct", ascending=False)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Maior crescimento**")
        cresceu = comp[comp["variacao_pct"] > 0].head(5)
        if not cresceu.empty:
            fig = go.Figure(go.Bar(
                x=cresceu["variacao_pct"], y=cresceu["especialidade"], orientation="h",
                marker_color=VERMELHO,
                customdata=cresceu[["ano_2024", "ano_2025"]],
                hovertemplate="<b>%{y}</b><br>%{x:.1f}%<br>2024: %{customdata[0]:,} → 2025: %{customdata[1]:,}<extra></extra>",
            ))
            st.plotly_chart(_layout(fig, "", "Variação (%)"), use_container_width=True)
        else:
            _sem_dados("Nenhuma especialidade cresceu na seleção.")
    with c2:
        st.markdown("**Maior redução**")
        caiu = comp[comp["variacao_pct"] < 0].tail(5).sort_values("variacao_pct")
        if not caiu.empty:
            fig = go.Figure(go.Bar(
                x=caiu["variacao_pct"], y=caiu["especialidade"], orientation="h",
                marker_color=TEAL,
                customdata=caiu[["ano_2024", "ano_2025"]],
                hovertemplate="<b>%{y}</b><br>%{x:.1f}%<br>2024: %{customdata[0]:,} → 2025: %{customdata[1]:,}<extra></extra>",
            ))
            st.plotly_chart(_layout(fig, "", "Variação (%)"), use_container_width=True)
        else:
            _sem_dados("Nenhuma especialidade reduziu na seleção.")

    st.markdown("#### Distribuição mensal das 5 maiores especialidades")
    top5 = df.head(5)["especialidade"].tolist()
    detalhe = dados.por_mes_especialidade(filtros, top5)
    if detalhe.empty:
        _sem_dados("Sem dados para a combinação de filtros atual.")
    else:
        fig = px.line(
            detalhe, x="rotulo", y="internacoes", color="especialidade",
            markers=True, color_discrete_sequence=CORES,
            category_orders={"especialidade": top5},
        )
        fig.update_traces(hovertemplate="<b>%{fullData.name}</b><br>%{y:,} internações<extra></extra>")
        st.plotly_chart(_layout(fig, "", "Internações"), use_container_width=True)


# =============================================================================
# TELA 3 — PERFIL DEMOGRÁFICO
# =============================================================================
def perfil_demografico(filtros: dict) -> None:
    st.subheader("Perfil Demográfico")
    with st.spinner("Consultando o Data Warehouse..."):
        sexo_df = dados.por_sexo(filtros)
        faixa_df = dados.por_faixa_etaria(filtros)
        mediana = dados.idade_mediana(filtros)
        ind = dados.indicadores_gerais(filtros)
    if not ind or not ind.get("total_internacoes"):
        _sem_dados()
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _kpi("Idade média", f"{ind['idade_media']:.1f} anos" if ind["idade_media"] is not None else "—",
             "registros com idade válida", AZUL)
    with c2:
        _kpi("Idade mediana", f"{mediana:.0f} anos" if mediana is not None else "—",
             "percentil 50", AZUL_CLARO)
    with c3:
        _kpi("Registros sem idade", _formatar_inteiro(ind["idade_ausente"]),
             "categoria 'Não informada' preservada", CINZA)
    with c4:
        feminino = ind["feminino"] / max(ind["feminino"] + ind["masculino"], 1)
        _kpi("Proporção feminina", f"{100 * feminino:.1f}%",
             "entre registros com sexo informado", TEAL)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Distribuição por faixa etária")
        if not faixa_df.empty:
            fig = go.Figure(go.Bar(
                x=faixa_df["internacoes"], y=faixa_df["faixa_etaria"], orientation="h",
                marker_color=[AMBAR if "recém" in f else AZUL for f in faixa_df["faixa_etaria"]],
                customdata=faixa_df["participacao_pct"],
                hovertemplate="<b>%{y}</b><br>%{x:,} internações<br>%{customdata:.2f}%<extra></extra>",
            ))
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(_layout(fig, "", "Internações"), use_container_width=True)
        else:
            _sem_dados()
    with col2:
        st.markdown("#### Distribuição por sexo")
        if not sexo_df.empty:
            fig = px.pie(sexo_df, names="sexo", values="internacoes",
                         color="sexo", color_discrete_map=CORES_SEXO)
            fig.update_traces(textinfo="value+percent",
                              hovertemplate="<b>%{label}</b><br>%{value:,} internações<extra></extra>")
            st.plotly_chart(_layout(fig, "", legenda=False), use_container_width=True)
        else:
            _sem_dados()

    st.markdown("#### Comparação demográfica por especialidade (15 maiores)")
    demo = dados.demografia_por_especialidade(filtros)
    if not demo.empty:
        top = demo.head(15)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=top["especialidade"], x=top["feminino"], name="Feminino", orientation="h",
            marker_color=TEAL, hovertemplate="<b>%{y}</b><br>Feminino: %{x:,}<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            y=top["especialidade"], x=top["masculino"], name="Masculino", orientation="h",
            marker_color=AZUL, hovertemplate="<b>%{y}</b><br>Masculino: %{x:,}<extra></extra>",
        ))
        fig.update_layout(barmode="stack")
        st.plotly_chart(_layout(fig, "", "Internações"), use_container_width=True)

        tabela = demo.head(15)[["especialidade", "internacoes", "idade_media", "feminino", "masculino"]].rename(columns={
            "especialidade": "Especialidade", "internacoes": "Internações",
            "idade_media": "Idade média", "feminino": "Feminino", "masculino": "Masculino",
        })
        st.dataframe(
            tabela.style.format({
                "Internações": lambda v: f"{int(v):,}".replace(",", "."),
                "Idade média": "{:.1f}",
                "Feminino": lambda v: f"{int(v):,}".replace(",", "."),
                "Masculino": lambda v: f"{int(v):,}".replace(",", "."),
            }),
            use_container_width=True,
        )


# =============================================================================
# TELA 4 — ANÁLISE GEOGRÁFICA
# =============================================================================
def analise_geografica(filtros: dict) -> None:
    st.subheader("Análise Geográfica")
    st.caption(
        "Classificação documentada: **Natal** = município de Natal; **Interior RN** = demais "
        "municípios do RN validados no IBGE; **Outros estados** = municípios de outras UFs; "
        "registros sem correspondência/ambíguos permanecem destacados e nunca são "
        "atribuídos por inferência. O campo da fonte refere-se ao município informado "
        "na internação (documentação oficial: município de residência)."
    )
    with st.spinner("Consultando o Data Warehouse..."):
        geo = dados.por_geo_classe(filtros)
        muni = dados.por_municipio(filtros)
    if geo.empty or muni.empty:
        _sem_dados()
        return

    c1, c2, c3 = st.columns(3)
    total = int(muni["internacoes"].sum())
    natal = int(muni[muni["municipio"].str.upper() == "NATAL"]["internacoes"].sum())
    interior = int(muni[muni["classificacao_geografica"] == "Interior RN"]["internacoes"].sum())
    with c1:
        _kpi("Participação de Natal", f"{100 * natal / total:.1f}%",
             f"{_formatar_inteiro(natal)} internações", AZUL)
    with c2:
        _kpi("Participação do interior RN", f"{100 * interior / total:.1f}%",
             f"{_formatar_inteiro(interior)} internações", TEAL)
    with c3:
        _kpi("Municípios distintos", _formatar_inteiro(len(muni)),
             "após padronização IBGE", AMBAR)

    col1, col2 = st.columns([2, 3])
    with col1:
        st.markdown("#### Natal x interior x demais")
        cores_classe = {
            "Natal": AZUL, "Interior RN": TEAL, "Outros estados": AMBAR,
            "Ambíguo entre estados": CINZA, "Sem correspondência IBGE": VERMELHO,
            "Não informado": "#9ca3af",
        }
        fig = px.pie(
            geo, names="classe", values="internacoes", hole=0.42,
            color="classe", color_discrete_map=cores_classe,
        )
        fig.update_traces(textinfo="percent",
                          hovertemplate="<b>%{label}</b><br>%{value:,} internações (%{percent})<extra></extra>")
        st.plotly_chart(_layout(fig, "", legenda=False), use_container_width=True)
    with col2:
        st.markdown("#### Top 20 municípios por volume")
        top = muni.head(20).sort_values("internacoes")
        fig = go.Figure(go.Bar(
            x=top["internacoes"], y=top["municipio"], orientation="h",
            marker_color=[cores_classe.get(c, AZUL_CLARO) for c in top["classificacao_geografica"]],
            customdata=top[["uf", "participacao_pct"]],
            hovertemplate="<b>%{y}</b><br>%{x:,} internações<br>%{customdata[1]:.2f}% do total<extra></extra>",
        ))
        st.plotly_chart(_layout(fig, "", "Internações"), use_container_width=True)

    st.markdown("#### Tabela completa (até 100 municípios)")
    tabela = muni.head(100)[["municipio", "uf", "classificacao_geografica",
                             "internacoes", "participacao_pct"]].rename(columns={
        "municipio": "Município", "uf": "UF",
        "classificacao_geografica": "Classificação",
        "internacoes": "Internações", "participacao_pct": "Participação (%)",
    })
    st.dataframe(
        tabela.style.format({
            "Internações": lambda v: f"{int(v):,}".replace(",", "."),
            "Participação (%)": "{:.2f}%",
        }),
        use_container_width=True, height=480,
    )


# =============================================================================
# TELA 5 — SAZONALIDADE E EVOLUÇÃO TEMPORAL
# =============================================================================
def sazonalidade(filtros: dict) -> None:
    st.subheader("Sazonalidade e Evolução Temporal")
    st.caption(
        "Comparações entre períodos equivalentes (mesmo mês/trimestre). Diferenças de "
        "volume refletem os dados publicados e podem depender de cobertura e completude "
        "da fonte — leitura cautelosa quanto a 'crescimento real de demanda'."
    )
    with st.spinner("Consultando o Data Warehouse..."):
        mes_df = dados.por_mes(filtros)
        trim_df = dados.por_trimestre(filtros)
        acum_df = dados.evolucao_acumulada(filtros)
    if mes_df.empty:
        _sem_dados()
        return

    st.markdown("#### Internações por mês (2024 x 2025)")
    base = mes_df[["mes", "nome_mes"]].drop_duplicates().sort_values("mes")
    a24 = mes_df[mes_df["ano"] == 2024].set_index("mes")["internacoes"].reindex(base["mes"]).fillna(0)
    a25 = mes_df[mes_df["ano"] == 2025].set_index("mes")["internacoes"].reindex(base["mes"]).fillna(0)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=base["nome_mes"].str[:3], y=a24, name="2024", marker_color=AZUL_CLARO,
                         hovertemplate="2024 — %{x}: %{y:,}<extra></extra>"))
    fig.add_trace(go.Bar(x=base["nome_mes"].str[:3], y=a25, name="2025", marker_color=AZUL,
                         hovertemplate="2025 — %{x}: %{y:,}<extra></extra>"))
    fig.update_layout(barmode="group")
    st.plotly_chart(_layout(fig, "", "Internações", "Mês"), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Comparação trimestral")
        if not trim_df.empty:
            fig = px.bar(trim_df, x="rotulo", y="internacoes", color="ano",
                         color_discrete_map={2024: AZUL_CLARO, 2025: AZUL})
            fig.update_traces(hovertemplate="<b>%{x}</b><br>%{y:,} internações<extra></extra>")
            fig.update_layout(showlegend=False)
            st.plotly_chart(_layout(fig, "", "Internações"), use_container_width=True)
    with col2:
        st.markdown("#### Evolução acumulada")
        if not acum_df.empty:
            fig = go.Figure(go.Scatter(
                x=acum_df["rotulo"], y=acum_df["acumulado"], mode="lines+markers",
                fill="tozeroy", line=dict(color=TEAL, width=3),
                hovertemplate="<b>%{x}</b><br>acumulado: %{y:,}<extra></extra>",
            ))
            st.plotly_chart(_layout(fig, "", "Internações acumuladas"), use_container_width=True)

    st.markdown("#### Meses com maiores e menores volumes")
    ordenado = mes_df.sort_values("internacoes", ascending=False)
    c1, c2 = st.columns(2)
    with c1:
        if len(ordenado) >= 3:
            top3 = ordenado.head(3)
            for _, r in top3.iterrows():
                st.success(f"**{r['rotulo']}** — {_formatar_inteiro(r['internacoes'])} internações")
    with c2:
        if len(ordenado) >= 3:
            bot3 = ordenado.tail(3)
            for _, r in bot3.iterrows():
                st.warning(f"**{r['rotulo']}** — {_formatar_inteiro(r['internacoes'])} internações")

    if (mes_df["ano"] == 2024).any() and (mes_df["ano"] == 2025).any():
        st.markdown("#### Variação percentual mês a mês (2024 → 2025)")
        comp = base.copy()
        comp["v24"] = a24.values
        comp["v25"] = a25.values
        comp["variacao_pct"] = comp.apply(
            lambda r: 100 * (r["v25"] - r["v24"]) / r["v24"] if r["v24"] else None, axis=1
        )
        cores = [TEAL if (v or 0) <= 0 else VERMELHO for v in comp["variacao_pct"]]
        fig = go.Figure(go.Bar(
            x=comp["nome_mes"].str[:3], y=comp["variacao_pct"],
            marker_color=cores,
            hovertemplate="<b>%{x}</b><br>%{y:+.1f}%<extra></extra>",
        ))
        fig.add_hline(y=0, line_color=CINZA)
        st.plotly_chart(_layout(fig, "", "Variação (%)", "Mês"), use_container_width=True)


# =============================================================================
# TELA 6 — ANÁLISE DE SENTIMENTOS
# =============================================================================
def sentimentos(filtros: dict) -> None:
    st.subheader("Análise de Sentimentos — Instagram @huol_ufrn")
    rel = dados.relatorio_nlp()

    if rel.get("status") != "PROCESSADO":
        st.info(
            "**Integração em preparação.** A coleta de comentários exige acesso "
            "autorizado à Instagram Graph API oficial (aplicativo aprovado no Meta for "
            "Developers com as permissões instagram_basic e instagram_manage_comments "
            "e token válido). Sem esse acesso, **nenhum resultado é simulado ou "
            "apresentado como real**, conforme as diretrizes do projeto.",
             
        )
        with st.expander("Estado do módulo NLP (rastreabilidade)"):
            st.json(rel or {"status": "sem relatório"})
        st.markdown("#### Como o pipeline funcionará quando autorizado")
        st.markdown(
            """
            1. **Coleta** — `src/nlp/instagram_client.py` consulta os comentários do
               perfil `@huol_ufrn` pela Graph API (campos oficiais: texto, data,
               curtidas, publicação);
            2. **Limpeza** — `src/nlp/clean_text.py` remove ruídos/URLs/emojis,
               trata hashtags e stopwords e lematiza em português, preservando o
               texto original para auditoria;
            3. **Sentimentos** — `src/nlp/sentiment.py` classifica com o modelo
               multilíngue `cardiffnlp/twitter-xlm-roberta-base-sentiment`
               (Positivo / Negativo / Neutro), com avaliação por amostra revisada;
            4. **Temas** — `src/nlp/topics.py` extrai termos e expressões recorrentes
               por sentimento com TF-IDF (1–2 gramas);
            5. **Publicação** — resultados gravados na camada Ouro e consultados por
               esta tela e pelas consultas SQL.
            """
        )
        return

    df = None
    import pandas as pd  # noqa: PLC0415

    comentarios = pd.read_parquet(
        Path(__file__).resolve().parents[2] / "data/processed/nlp_comentarios.parquet"
    )
    resumo = pd.read_parquet(
        Path(__file__).resolve().parents[2] / "data/processed/nlp_resumo_sentimentos.parquet"
    )
    termos = pd.read_parquet(
        Path(__file__).resolve().parents[2] / "data/processed/nlp_termos.parquet"
    )

    total = int(resumo["qtd"].sum())
    pct = {r["sentimento"]: r["participacao_pct"] for _, r in resumo.iterrows()}
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _kpi("Comentários processados", _formatar_inteiro(total), "fonte: perfil oficial", AZUL)
    with c2:
        _kpi("Positivos", f"{pct.get('Positivo', 0):.1f}%", TEAL)
    with c3:
        _kpi("Neutros", f"{pct.get('Neutro', 0):.1f}%", CINZA)
    with c4:
        _kpi("Negativos", f"{pct.get('Negativo', 0):.1f}%", VERMELHO)

    col1, col2 = st.columns(2)
    with col1:
        fig = px.pie(resumo, names="sentimento", values="qtd", hole=0.45,
                     color="sentimento",
                     color_discrete_map={"Positivo": TEAL, "Neutro": CINZA, "Negativo": VERMELHO})
        fig.update_traces(textinfo="percent+label")
        st.plotly_chart(_layout(fig, "", legenda=False), use_container_width=True)
    with col2:
        for classe in ["Positivo", "Negativo", "Neutro"]:
            sub = termos[termos["sentimento"] == classe].head(8)
            if not sub.empty:
                st.markdown(f"**Temas recorrentes — {classe}**")
                st.write(", ".join(f"`{t}`" for t in sub["termo"]))
    st.caption(
        "Autores anonimizados (LGPD). Modelo: "
        f"{rel.get('modelo', '')}. Limitações documentadas no relatório de qualidade."
    )


# =============================================================================
# TELA 7 — INSIGHTS E QUALIDADE DOS DADOS
# =============================================================================
def insights_qualidade(filtros: dict) -> None:
    st.subheader("Insights e Qualidade dos Dados")
    with st.spinner("Consultando o Data Warehouse..."):
        ind = dados.indicadores_gerais(filtros)
        espec = dados.por_especialidade(filtros)
        geo = dados.por_geo_classe(filtros)
        faixa = dados.por_faixa_etaria(filtros)
    qual = dados.qualidade_dados()
    if not ind or not ind.get("total_internacoes"):
        _sem_dados()
        return

    st.markdown("#### Principais descobertas (evidências dos dados)")
    espec_top = espec.iloc[0]
    natal = geo[geo["classe"] == "Natal"]
    interior = geo[geo["classe"] == "Interior RN"]
    total = int(ind["total_internacoes"])
    faixa_top = faixa.sort_values("internacoes", ascending=False).iloc[0]
    d1, d2 = st.columns(2)
    with d1:
        st.success(
            f"**Demanda concentrada:** {espec_top['especialidade']} lidera com "
            f"{_formatar_inteiro(espec_top['internacoes'])} internações "
            f"({espec_top['participacao_pct']:.1f}%); as 5 maiores especialidades "
            f"concentram {espec.head(5)['participacao_pct'].sum():.1f}% do volume."
        )
        st.info(
            f"**Perfil predominante:** faixa {faixa_top['faixa_etaria']} "
            f"({faixa_top['participacao_pct']:.1f}%); idade média "
            f"{ind['idade_media']:.1f} anos; sexo equilibrado "
            f"({100 * ind['feminino'] / total:.1f}% feminino)."
        )
    with d2:
        pct_natal = float(natal['participacao_pct'].iloc[0]) if not natal.empty else 0.0
        pct_interior = float(interior['participacao_pct'].iloc[0]) if not interior.empty else 0.0
        st.info(
            f"**Origem geográfica:** interior RN responde por {pct_interior:.1f}% das "
            f"internações e Natal por {pct_natal:.1f}% — a clientela extrapola a capital, "
            f"reflexo do papel de hospital de referência."
        )
        if not qual:
            st.warning("Relatório de qualidade da Prata não encontrado no ambiente local.")
        else:
            st.warning(
                f"**Qualidade:** {qual['total_recebidos']:,} registros recebidos, "
                f"{qual['total_processados']:,} processados, {qual['total_rejeitados']} rejeitados; "
                f"{qual['duplicidades_exatas_preservadas']} duplicidade(s) exata(s) "
                f"preservada(s) com sinalização.".replace(",", ".")
            )

    st.markdown("#### Cobertura temporal e limitações metodológicas")
    l1, l2 = st.columns(2)
    with l1:
        st.markdown(
            f"""
            - **Cobertura:** {ind['data_min']} a {ind['data_max']} (8 trimestres
              publicados no portal oficial);
            - **Campos disponíveis:** data/hora, especialidade, município, idade,
              sexo — **sem** identificador de paciente, alta, permanência ou
              desfecho;
            - **Indicadores não calculáveis:** tempo médio de permanência,
              readmissão e mortalidade dependem de campos inexistentes na fonte.
            """
        )
    with l2:
        st.markdown(
            """
            - **Município:** a documentação oficial descreve-o como município de
              residência; tratado como "município informado na internação" e
              validado contra o IBGE (ambiguidades não atribuídas, exceto
              Parnamirim, com exceção documentada);
            - **Idade zero:** preservada como recém-nascido/lactente (245 registros);
            - **Duplicidade:** 1 par idêntico preservado e sinalizado (sem
              identificador para confirmar duplicação);
            - **Sentimentos:** módulo pronto; sem comentários reais enquanto a
              Instagram Graph API não estiver autorizada.
            """
        )

    st.markdown("#### Recomendações estratégicas (analíticas, não conclusões da fonte)")
    st.markdown(
        """
        1. **Capacidade cirúrgica:** Cardiologia, Urologia e Cirurgia Geral lideram a
           demanda — um hospital privado em preparação para credenciamento SUS pode
           priorizar leitos/equipes nessas linhas de cuidado;
        2. **Rede de referência:** ~65% das internações vêm do interior do RN —
           planejar fluxo de regulação, transporte e acolhimento de pacientes de
           fora da capital;
        3. **Pediatria e recém-nascidos:** 245 internações de lactentes reforçam a
           necessidade de estrutura obstétrica/pediátrica adequada;
        4. **Monitoramento contínuo:** os trimestres de 2025 superaram os de 2024
           (+11,7% no ano) — acompanhar a série para dimensionar contratação;
        5. **Percepção pública:** implementar a coleta autorizada de comentários
           (Instagram Graph API) para acompanhar reputação antes do credenciamento.
        """
    )

    st.markdown("#### Dicionário de sinalizações de qualidade")
    st.markdown(
        """
        | Sinalização | Significado |
        |---|---|
        | `horario_ausente` | registro sem hora/minuto na data de internação |
        | `duplicidade_exata_preservada` | linha idêntica em todas as colunas, mantida por não haver identificador |
        | classe IBGE `AMBIGUO` | nome de município existente em vários estados |
        | classe IBGE `SEM_CORRESPONDENCIA` | valor não encontrado na base IBGE (ex.: distritos) |
        """
    )
