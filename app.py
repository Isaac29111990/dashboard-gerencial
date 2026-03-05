import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import io
import unicodedata
from datetime import date, timedelta

LINK_ENERGIA = "https://usinaxavantes-my.sharepoint.com/:x:/g/personal/jefferson_ferreira_usinaxavantes_onmicrosoft_com/IQDdqWDpJPZzS5sWsTULHWMPAaPbvF6rFiA99uybNJx7zh4?e=iDHkEG"
LINK_CONSUMO = "https://usinaxavantes-my.sharepoint.com/:x:/g/personal/jefferson_ferreira_usinaxavantes_onmicrosoft_com/IQDKVJdv3LvzQY4AjhJiPbiZAYzb7lg5BPZK9-O52ctFqq4?e=RboNX9"

CONFIG_PLANILHAS = {
    "Amajari": {
        "aba_consumo": "Amajari", "aba_energia": "Energia_Amajari",
        "col_data_c": "DATA", "col_consumo": "Consumo Calculado",
        "col_data_e": "DATA", "col_energia": "ENERGIA GERADA TOTAL MWh",
        "dias_antecedencia": 2,
    },
    "Pacaraima": {
        "aba_consumo": "Pacaraima", "aba_energia": "Energia_Pacaraima",
        "col_data_c": "DATA", "col_consumo": "Consumo Calculado",
        "col_data_e": "DATA", "col_energia": "ENERGIA GERADA TOTAL MWh",
        "dias_antecedencia": 2,
    },
    "Uiramutã": {
        "aba_consumo": "Uiramutã", "aba_energia": "Energia_Uiramutã",
        "col_data_c": "DATA", "col_consumo": "Consumo Calculado",
        "col_data_e": "Data", "col_energia": "Energia Gerada MWh",
        "dias_antecedencia": 3,
    },
}

st.set_page_config(page_title="Dashboard Energético", page_icon="⚡", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0f0f1a; }
    h1, h2, h3, h4, p, label { color: #e0e0f0 !important; }
    [data-testid="metric-container"] {
        background-color: #1e1e2e; border-radius: 12px;
        padding: 16px 20px; border: 1px solid #2a2a4a;
    }
    [data-testid="metric-container"] label { color: #8888aa !important; font-size: 12px !important; }
    [data-testid="stMetricValue"] { color: #e0e0f0 !important; font-size: 22px !important; font-weight: bold; }
    [data-testid="stSidebar"] { background-color: #1e1e2e; }
    [data-testid="stSidebar"] * { color: #e0e0f0 !important; }
    .stTabs [data-baseweb="tab-list"] { background-color: #1e1e2e; border-radius: 10px; padding: 4px; gap: 4px; }
    .stTabs [data-baseweb="tab"] { background-color: #2a2a3e; color: #8888aa !important; border-radius: 8px; padding: 8px 20px; font-weight: 600; }
    .stTabs [aria-selected="true"] { background-color: #5c52c8 !important; color: white !important; }
    .stSelectbox > div > div,
    .stNumberInput > div > div > input { background-color: #1e1e2e !important; color: #e0e0f0 !important; border: 1px solid #2a2a4a !important; border-radius: 8px !important; }
    .separador { border: none; border-top: 1px solid #2a2a4a; margin: 20px 0; }
    .badge-unidade { display: inline-block; padding: 4px 14px; border-radius: 20px; font-size: 13px; font-weight: 600; margin-bottom: 12px; }
    .total-box { background: linear-gradient(135deg, #5c52c8, #7c6af7); border-radius: 14px; padding: 24px; text-align: center; margin-top: 10px; }
    .total-box h2 { color: white !important; margin: 0; font-size: 32px; }
    .total-box p { color: rgba(255,255,255,0.75) !important; margin: 4px 0 0 0; font-size: 13px; }
    .block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)

UNIDADES = {
    "Amajari":   {"cor": "#7c6af7", "icone": "🔵"},
    "Pacaraima": {"cor": "#f97316", "icone": "🟠"},
    "Uiramutã":  {"cor": "#22c55e", "icone": "🟢"},
}

COR_CONSUMO = "#60a5fa"
COR_ENERGIA = "#facc15"
DESCONTO    = 1.0530
BOMBEAMENTO = 0.135
PLOG = {
    "Amajari":      0.4668,
    "Pacaraima":    0.4919,
    "Uiramutã_FOB": 0.0769,
    "Uiramutã_CIF": 0.6269,
}


def fmt_br(valor, decimais=0):
    if valor is None:
        return "—"
    s = f"{valor:,.{decimais}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def norm(texto):
    t = str(texto).strip()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.upper()


def converter_link(link):
    sep = "&" if "?" in link else "?"
    return link + sep + "download=1"


def encontrar_coluna(colunas, alvo):
    for c in colunas:
        if norm(str(c)) == norm(alvo):
            return c
    return None


def ler_aba_excel(xl_file, sheet_name, col_data_alvo, col_valor_alvo):
    df_raw = pd.read_excel(xl_file, sheet_name=sheet_name, header=None, nrows=20)
    header_row = None
    for i, row in df_raw.iterrows():
        valores = [norm(str(v)) for v in row.values]
        if norm(col_data_alvo) in valores and norm(col_valor_alvo) in valores:
            header_row = i
            break
    if header_row is None:
        celulas = []
        for i, row in df_raw.iterrows():
            for v in row.values:
                s = str(v).strip()
                if s and s != "nan":
                    celulas.append(s)
        return None, f"Cabeçalho não encontrado. Células visíveis: {celulas[:10]}"
    df = pd.read_excel(xl_file, sheet_name=sheet_name, header=header_row)
    col_data  = encontrar_coluna(df.columns, col_data_alvo)
    col_valor = encontrar_coluna(df.columns, col_valor_alvo)
    if col_data is None or col_valor is None:
        return None, f"Colunas não encontradas. Disponíveis: {list(df.columns)}"
    df = df[[col_data, col_valor]].copy()
    df.columns = ["data", "valor"]
    df["data"]  = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna().sort_values("data").reset_index(drop=True)
    return df, None


@st.cache_data(ttl=300)
def carregar_dados():
    dados = {}
    erros = []
    xl_consumo = None
    xl_energia = None
    try:
        r = requests.get(converter_link(LINK_CONSUMO), timeout=20)
        r.raise_for_status()
        xl_consumo = pd.ExcelFile(io.BytesIO(r.content))
    except Exception as e:
        erros.append(f"Erro ao baixar planilha de consumo: {e}")
    try:
        r = requests.get(converter_link(LINK_ENERGIA), timeout=20)
        r.raise_for_status()
        xl_energia = pd.ExcelFile(io.BytesIO(r.content))
    except Exception as e:
        erros.append(f"Erro ao baixar planilha de energia: {e}")

    for unidade, cfg in CONFIG_PLANILHAS.items():
        df_consumo = None
        df_energia = None
        if xl_consumo is not None:
            try:
                df_c, erro = ler_aba_excel(xl_consumo, cfg["aba_consumo"],
                                           cfg["col_data_c"], cfg["col_consumo"])
                if erro:
                    erros.append(f"{unidade} — Consumo: {erro}")
                else:
                    df_consumo = df_c.rename(columns={"valor": "consumo"})
            except Exception as e:
                erros.append(f"{unidade} — Aba consumo: {e}")
        if xl_energia is not None:
            try:
                df_e, erro = ler_aba_excel(xl_energia, cfg["aba_energia"],
                                           cfg["col_data_e"], cfg["col_energia"])
                if erro:
                    erros.append(f"{unidade} — Energia: {erro}")
                else:
                    df_energia = df_e.rename(columns={"valor": "energia_gerada"})
            except Exception as e:
                erros.append(f"{unidade} — Aba energia: {e}")

        if df_consumo is not None and df_energia is not None:
            df_m = pd.merge(df_consumo, df_energia, on="data", how="inner")
            df_m["consumo_especifico"] = (
                df_m["consumo"] / df_m["energia_gerada"]
            ).replace([float("inf"), float("-inf")], None)
            dados[unidade] = df_m.sort_values("data").reset_index(drop=True)
        elif df_consumo is not None:
            df_consumo["energia_gerada"]     = None
            df_consumo["consumo_especifico"] = None
            dados[unidade] = df_consumo
        elif df_energia is not None:
            df_energia["consumo"]            = None
            df_energia["consumo_especifico"] = None
            dados[unidade] = df_energia
    return dados, erros


def gerar_periodos(df, tipo):
    if tipo == "Ano":
        return sorted(df["data"].dt.year.unique().astype(str).tolist(), reverse=True)
    elif tipo == "Mês":
        return sorted([str(p) for p in df["data"].dt.to_period("M").unique()], reverse=True)
    elif tipo == "Semana":
        df = df.copy()
        df["lbl"] = df["data"].apply(lambda d: f"Semana {d.isocalendar()[1]:02d}/{d.year}")
        return sorted(df["lbl"].unique().tolist(), reverse=True)
    return []


def filtrar(df, tipo, periodo):
    if tipo == "Ano":
        return df[df["data"].dt.year == int(periodo)]
    elif tipo == "Mês":
        return df[df["data"].dt.to_period("M").astype(str) == periodo]
    elif tipo == "Semana":
        df = df.copy()
        df["lbl"] = df["data"].apply(lambda d: f"Semana {d.isocalendar()[1]:02d}/{d.year}")
        return df[df["lbl"] == periodo]
    return df


def layout_base(titulo, unidade_medida):
    return dict(
        title=dict(text=titulo, font=dict(color="#e0e0f0", size=13)),
        paper_bgcolor="#0f0f1a", plot_bgcolor="#0f0f1a",
        font=dict(color="#e0e0f0"), separators=",.",
        xaxis=dict(showgrid=False, color="#ccccdd", tickformat="%d/%m/%Y", tickfont=dict(color="#ccccdd")),
        yaxis=dict(showgrid=True, gridcolor="#2a2a4a", color="#ccccdd", title=unidade_medida, tickfont=dict(color="#ccccdd")),
        legend=dict(bgcolor="#1e1e2e", bordercolor="#4a4a6a", borderwidth=1, font=dict(size=11, color="#e0e0f0")),
        hovermode="x unified", margin=dict(t=45, b=30, l=60, r=20), height=300,
    )


def grafico_barras(df, coluna, titulo, unidade_medida, cor_barra):
    if coluna not in df.columns or df[coluna].dropna().empty:
        return None
    serie = df.dropna(subset=[coluna])
    media = serie[coluna].mean()
    r, g, b = int(cor_barra[1:3], 16), int(cor_barra[3:5], 16), int(cor_barra[5:7], 16)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=serie["data"], y=serie[coluna], name=titulo,
        marker_color=f"rgba({r},{g},{b},0.80)", marker_line_color=cor_barra, marker_line_width=0.8,
        hovertemplate=f"<b>%{{x|%d/%m/%Y}}</b><br>{titulo}: %{{y:,.2f}} {unidade_medida}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=[serie["data"].min(), serie["data"].max()], y=[media, media],
        mode="lines", name=f"Média: {fmt_br(media, 2)} {unidade_medida}",
        line=dict(color="#f97316", width=2.5, dash="dash"), hoverinfo="skip",
    ))
    lay = layout_base(f"{titulo} — Média: <b>{fmt_br(media, 2)} {unidade_medida}</b>", unidade_medida)
    lay["bargap"] = 0.15
    fig.update_layout(**lay)
    return fig


def grafico_consumo_especifico(df, cor):
    coluna = "consumo_especifico"
    if coluna not in df.columns or df[coluna].dropna().empty:
        return None
    serie = df.dropna(subset=[coluna])
    media = serie[coluna].mean()
    r, g, b = int(cor[1:3], 16), int(cor[3:5], 16), int(cor[5:7], 16)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=serie["data"], y=serie[coluna], name="Cons. Específico",
        marker_color=f"rgba({r},{g},{b},0.80)", marker_line_color=cor, marker_line_width=0.8,
        hovertemplate="<b>%{x|%d/%m/%Y}</b><br>Cons. Específico: %{y:,.2f} L/MWh<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=[serie["data"].min(), serie["data"].max()], y=[media, media],
        mode="lines", name=f"Média: {fmt_br(media, 2)} L/MWh",
        line=dict(color="#f97316", width=2.5, dash="dash"), hoverinfo="skip",
    ))
    lay = layout_base(f"Consumo Específico — Média: <b>{fmt_br(media, 2)} L/MWh</b>", "L/MWh")
    lay["bargap"] = 0.15
    fig.update_layout(**lay)
    return fig


def secao_unidade(nome, df, tipo_filtro, periodo):
    cor   = UNIDADES[nome]["cor"]
    icone = UNIDADES[nome]["icone"]
    st.markdown(
        f"<span class='badge-unidade' style='background:{cor}22; color:{cor}; border:1px solid {cor}44;'>"
        f"{icone} {nome}</span>",
        unsafe_allow_html=True
    )
    df_f = filtrar(df, tipo_filtro, periodo)
    if df_f.empty:
        st.warning("Sem dados para o período selecionado.")
        return

    tem_consumo = "consumo"        in df_f.columns and df_f["consumo"].notna().any()
    tem_energia = "energia_gerada" in df_f.columns and df_f["energia_gerada"].notna().any()
    consumo_total = float(df_f["consumo"].sum())        if tem_consumo else None
    media_consumo = float(df_f["consumo"].mean())       if tem_consumo else None
    energia_total = float(df_f["energia_gerada"].sum()) if tem_energia else None
    cons_esp = (consumo_total / energia_total) if (consumo_total and energia_total and energia_total > 0) else None

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("⛽ Consumo Total",    f"{fmt_br(consumo_total, 0)} L")
    with c2: st.metric("📊 Média de Consumo", f"{fmt_br(media_consumo, 0)} L/dia")
    with c3: st.metric("⚡ Energia Gerada",   f"{fmt_br(energia_total, 2)} MWh")
    with c4: st.metric("🔢 Cons. Específico", f"{fmt_br(cons_esp, 2)} L/MWh")
    with c5: st.metric("📅 Registros",        str(len(df_f)))

    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        fig_c = grafico_barras(df_f, "consumo", "Consumo", "L", COR_CONSUMO)
        if fig_c is not None:
            st.plotly_chart(fig_c, use_container_width=True)
        else:
            st.info("Dados de consumo indisponíveis.")
    with col2:
        fig_e = grafico_barras(df_f, "energia_gerada", "Energia Gerada", "MWh", COR_ENERGIA)
        if fig_e is not None:
            st.plotly_chart(fig_e, use_container_width=True)
        else:
            st.info("Dados de energia indisponíveis.")

    cols_esp = st.columns(2)
    with cols_esp[0]:
        fig_esp = grafico_consumo_especifico(df_f, cor)
        if fig_esp is not None:
            st.plotly_chart(fig_esp, use_container_width=True)
        else:
            st.info("Dados de cons. específico indisponíveis.")

    with st.expander("📋 Ver dados do período"):
        cols_exib = [c for c in ["data", "consumo", "energia_gerada", "consumo_especifico"] if c in df_f.columns]
        df_exibir = df_f[cols_exib].copy()
        df_exibir["data"] = df_exibir["data"].dt.strftime("%d/%m/%Y")
        for col in ["consumo", "energia_gerada", "consumo_especifico"]:
            if col in df_exibir.columns:
                df_exibir[col] = df_exibir[col].apply(lambda v: fmt_br(v, 2) if pd.notna(v) else "—")
        nomes_col = {"data": "Data", "consumo": "Consumo (L)",
                     "energia_gerada": "Energia Gerada (MWh)", "consumo_especifico": "Cons. Específico (L/MWh)"}
        df_exibir.columns = [nomes_col.get(c, c) for c in cols_exib]
        st.dataframe(df_exibir, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────
# AUTONOMIA
# ─────────────────────────────────────────
def calcular_autonomia(estoque, estoque_geradores, media_energia, cons_esp, usar_seguranca=False):
    if not all([media_energia, cons_esp, media_energia > 0, cons_esp > 0]):
        return None, None
    gerador_dia = media_energia / 24
    horas = (estoque / cons_esp) / gerador_dia
    if usar_seguranca:
        horas = horas - estoque_geradores - 24
    horas = max(horas, 0)
    dias  = horas / 24
    return horas, dias


def card_autonomia(titulo, horas, dias, cor, data_limite=None, data_carregamento=None):
    if horas is None:
        return (
            "<div style='background:#1e1e2e; border:1px solid #2a2a4a; border-radius:14px; "
            f"padding:20px 24px; margin-bottom:12px;'>"
            f"<div style='color:#8888aa; font-size:12px; font-weight:600;'>{titulo}</div>"
            "<div style='color:#4a4a6a; font-size:16px; margin-top:8px;'>Dados insuficientes.</div>"
            "</div>"
        )

    data_lim_str  = data_limite.strftime("%d/%m/%Y")       if data_limite       else "—"
    data_carg_str = data_carregamento.strftime("%d/%m/%Y") if data_carregamento else "—"

    html = (
        f"<div style='background:{cor}12; border:1px solid {cor}33; border-radius:14px; "
        f"padding:20px 24px; margin-bottom:12px;'>"
        f"<div style='color:{cor}; font-size:12px; font-weight:700; "
        f"text-transform:uppercase; letter-spacing:0.5px;'>{titulo}</div>"
        f"<div style='display:flex; gap:28px; margin-top:14px; flex-wrap:wrap;'>"
        f"<div><div style='color:#8888aa; font-size:11px;'>Horas de Operação</div>"
        f"<div style='color:#e0e0f0; font-size:22px; font-weight:700;'>{fmt_br(horas, 1)} h</div></div>"
        f"<div><div style='color:#8888aa; font-size:11px;'>Dias de Operação</div>"
        f"<div style='color:#e0e0f0; font-size:22px; font-weight:700;'>{fmt_br(dias, 1)} dias</div></div>"
        f"<div><div style='color:#8888aa; font-size:11px;'>Autonomia até</div>"
        f"<div style='color:{cor}; font-size:22px; font-weight:700;'>{data_lim_str}</div></div>"
        f"<div><div style='color:#8888aa; font-size:11px;'>⚠️ Carregar até</div>"
        f"<div style='color:#f97316; font-size:22px; font-weight:700;'>{data_carg_str}</div></div>"
        f"</div></div>"
    )
    return html


def _render_resumo_html(resumo_data, title_prefix):
    itens = []
    for nome, info in resumo_data.items():
        cor   = UNIDADES[nome]["cor"]
        icone = UNIDADES[nome]["icone"]
        aut   = info["data_limite"].strftime("%d/%m/%Y") if info["data_limite"]      else "—"
        carg  = info["data_carga"].strftime("%d/%m/%Y")  if info["data_carga"]       else "—"
        dias  = fmt_br(info["dias"], 1)                  if info["dias"] is not None else "—"

        item = (
            f"<div style='flex:1; min-width:220px; background:{cor}12; border:1px solid {cor}33; "
            f"border-radius:14px; padding:18px 20px;'>"
            f"<div style='color:{cor}; font-size:13px; font-weight:700; margin-bottom:10px;'>"
            f"{icone} {nome}</div>"
            f"<div style='display:flex; flex-direction:column; gap:8px;'>"
            f"<div>"
            f"<div style='color:#8888aa; font-size:11px;'>Dias de operação</div>"
            f"<div style='color:#e0e0f0; font-size:20px; font-weight:700;'>{dias} dias</div>"
            f"</div>"
            f"<div style='display:flex; gap:20px;'>"
            f"<div>"
            f"<div style='color:#8888aa; font-size:11px;'>Autonomia até</div>"
            f"<div style='color:{cor}; font-size:16px; font-weight:700;'>{aut}</div>"
            f"</div>"
            f"<div>"
            f"<div style='color:#8888aa; font-size:11px;'>⚠️ Carregar até</div>"
            f"<div style='color:#f97316; font-size:16px; font-weight:700;'>{carg}</div>"
            f"</div>"
            f"</div>"
            f"</div>"
            f"</div>"
        )
        itens.append(item)

    itens_html = "".join(itens)

    html_completo = (
        "<div style='margin-bottom:8px;'>"
        f"<div style='color:#8888aa; font-size:12px; font-weight:600; "
        f"text-transform:uppercase; letter-spacing:0.5px; margin-bottom:10px;'>"
        f"📋 {title_prefix}"
        "</div>"
        "<div style='display:flex; gap:16px; flex-wrap:wrap;'>"
        + itens_html +
        "</div>"
        "</div>"
    )
    st.markdown(html_completo, unsafe_allow_html=True)
    st.markdown("<hr class='separador'>", unsafe_allow_html=True)


def aba_autonomia(dados, tipo_filtro, periodo_sel):
    st.markdown("## 🛢️ Autonomia de Combustível")
    st.markdown(
        f"<p style='color:#8888aa; font-size:13px; margin-top:-10px;'>"
        f"Baseado nas médias do período selecionado ({periodo_sel}).<br>"
        f"Gerador/hora = Média Energia / 24 &nbsp;|&nbsp; "
        f"Horas = (Estoque / Cons. Esp.) / Gerador/hora [− Estoque Geradores − 24h se segurança ativada]<br>"
        f"Data Carregamento = Autonomia − 2 dias (Amajari/Pacaraima) &nbsp;|&nbsp; − 3 dias (Uiramutã)"
        f"</p>",
        unsafe_allow_html=True
    )

    hoje   = date.today()
    resumo_atual = {}
    resumo_com_compra = {} # Novo dicionário para o cenário com compra

    st.markdown("<hr class='separador'>", unsafe_allow_html=True)

    for nome, cfg in CONFIG_PLANILHAS.items():
        cor               = UNIDADES[nome]["cor"]
        icone             = UNIDADES[nome]["icone"]
        dias_antecedencia = cfg["dias_antecedencia"]

        if nome not in dados:
            st.warning(f"Dados de {nome} não disponíveis.")
            continue

        df_f = filtrar(dados[nome], tipo_filtro, periodo_sel)
        if df_f.empty:
            st.warning(f"{nome} — sem dados para o período.")
            continue

        tem_energia = "energia_gerada"     in df_f.columns and df_f["energia_gerada"].notna().any()
        tem_cesp    = "consumo_especifico" in df_f.columns and df_f["consumo_especifico"].notna().any()
        media_energia = float(df_f["energia_gerada"].mean())     if tem_energia else None
        media_cesp    = float(df_f["consumo_especifico"].mean()) if tem_cesp    else None

        st.markdown(
            f"<span class='badge-unidade' style='background:{cor}22; color:{cor}; border:1px solid {cor}44;'>"
            f"{icone} {nome} "
            f"<small style='opacity:0.6; font-size:11px;'>— antecedência de {dias_antecedencia} dias</small>"
            f"</span>",
            unsafe_allow_html=True
        )

        mc1, mc2, mc3 = st.columns(3)
        with mc1:
            st.metric("⚡ Média Energia/dia",
                      f"{fmt_br(media_energia, 2)} MWh" if media_energia else "—")
        with mc2:
            gerador_hora = (media_energia / 24) if media_energia else None
            st.metric("🔧 Gerador/hora",
                      f"{fmt_br(gerador_hora, 4)} MWh/h" if gerador_hora else "—")
        with mc3:
            st.metric("🔢 Cons. Específico médio",
                      f"{fmt_br(media_cesp, 2)} L/MWh" if media_cesp else "—")

        st.markdown("<br>", unsafe_allow_html=True)

        ci1, ci2, ci3 = st.columns(3)
        with ci1:
            estoque = st.number_input(
                "🛢️ Estoque Atual (L)", min_value=0.0, step=100.0,
                format="%.0f", key=f"estoque_{nome}"
            )
        with ci2:
            usar_estoque_ger = st.checkbox(
                "Considerar estoque de segurança", value=False,
                key=f"usar_est_ger_{nome}"
            )
            estoque_geradores = st.number_input(
                "⚙️ Estoque Geradores (h)", min_value=0.0, step=0.5,
                format="%.1f", key=f"est_ger_{nome}",
                disabled=not usar_estoque_ger,
                help="Horas de combustível já nos geradores. Descontado apenas se a opção acima estiver ativada."
            )
        with ci3:
            vol_comprado = st.number_input(
                "📦 Volume Comprado (L)", min_value=0.0, step=100.0,
                format="%.0f", key=f"comprado_{nome}"
            )

        est_ger_efetivo = estoque_geradores if usar_estoque_ger else 0.0
        st.markdown("<br>", unsafe_allow_html=True)

        # Cenário 1 — estoque atual
        horas_atual, dias_atual = calcular_autonomia(
            estoque, est_ger_efetivo, media_energia, media_cesp,
            usar_seguranca=usar_estoque_ger
        )
        data_limite_atual       = (hoje + timedelta(days=dias_atual))                     if dias_atual is not None else None
        data_carregamento_atual = (data_limite_atual - timedelta(days=dias_antecedencia)) if data_limite_atual      else None

        # Cenário 2 — estoque + compra
        horas_total, dias_total = calcular_autonomia(
            estoque + vol_comprado, est_ger_efetivo, media_energia, media_cesp,
            usar_seguranca=usar_estoque_ger
        )
        data_limite_total       = (hoje + timedelta(days=dias_total))                     if dias_total is not None else None
        data_carregamento_total = (data_limite_total - timedelta(days=dias_antecedencia)) if data_limite_total      else None

        # Guarda para os resumos
        resumo_atual[nome] = {
            "dias":        dias_atual,
            "data_limite": data_limite_atual,
            "data_carga":  data_carregamento_atual,
        }
        resumo_com_compra[nome] = {
            "dias":        dias_total,
            "data_limite": data_limite_total,
            "data_carga":  data_carregamento_total,
        }

        st.markdown(
            card_autonomia("📊 Cenário atual — somente estoque",
                           horas_atual, dias_atual, cor,
                           data_limite_atual, data_carregamento_atual),
            unsafe_allow_html=True
        )
        st.markdown(
            card_autonomia("📦 Cenário com compra — estoque + volume comprado",
                           horas_total, dias_total, cor,
                           data_limite_total, data_carregamento_total),
            unsafe_allow_html=True
        )
        st.markdown("<hr class='separador'>", unsafe_allow_html=True)

    # ── Resumos ao final (sempre atualizado) ──
    if resumo_atual:
        _render_resumo_html(resumo_atual, "Resumo — Cenário Atual (somente estoque)")
    if resumo_com_compra:
        _render_resumo_html(resumo_com_compra, "Resumo — Cenário com Compra (estoque + volume comprado)")


# ─────────────────────────────────────────
# CALCULADORA
# ─────────────────────────────────────────
def calculadora():
    st.markdown("## 🧮 Calculadora de Compra de Combustível")
    st.markdown(
        f"<p style='color:#8888aa; font-size:13px; margin-top:-10px;'>"
        f"Bombeamento: R$ {fmt_br(BOMBEAMENTO, 3)} &nbsp;|&nbsp; Desconto: R$ {fmt_br(DESCONTO, 4)}<br>"
        f"FOB — Preço/Litro = Pm + Plog + Bombeamento − Desconto &nbsp;|&nbsp; "
        f"CIF — Preço/Litro = Pm + Plog + Bombeamento</p>",
        unsafe_allow_html=True
    )
    st.markdown("<hr class='separador'>", unsafe_allow_html=True)
    resultados = {}

    for uk in ["Amajari", "Pacaraima"]:
        cor   = UNIDADES[uk]["cor"]
        icone = UNIDADES[uk]["icone"]
        st.markdown(
            f"<span class='badge-unidade' style='background:{cor}22; color:{cor}; border:1px solid {cor}44;'>"
            f"{icone} {uk} &nbsp;<small style='opacity:0.7'>Plog: R$ {fmt_br(PLOG[uk], 4)}</small></span>",
            unsafe_allow_html=True
        )
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            pm = st.number_input("Pm (R$/L)", min_value=0.0, step=0.001, format="%.4f", key=f"pm_{uk}")
        with c2:
            st.markdown(
                f"<div style='background:#1e1e2e; border:1px solid #2a2a4a; border-radius:8px; "
                f"padding:10px 14px; margin-top:26px;'>"
                f"<div style='color:#8888aa; font-size:11px;'>Plog fixo</div>"
                f"<div style='color:#e0e0f0; font-size:18px; font-weight:bold;'>R$ {fmt_br(PLOG[uk], 4)}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        with c3:
            vol = st.number_input("Volume (L)", min_value=0.0, step=1.0, format="%.0f", key=f"vol_{uk}")
        with c4:
            preco = pm + PLOG[uk] + BOMBEAMENTO - DESCONTO
            total = preco * vol
            st.markdown(
                f"<div style='background:{cor}15; border:1px solid {cor}44; border-radius:10px; "
                f"padding:10px 14px; margin-top:26px;'>"
                f"<div style='color:{cor}; font-size:11px; font-weight:600;'>PREÇO / LITRO</div>"
                f"<div style='color:#e0e0f0; font-size:20px; font-weight:bold;'>R$ {fmt_br(preco, 4)}</div>"
                f"<div style='color:{cor}; font-size:11px; font-weight:600; margin-top:8px;'>VALOR TOTAL</div>"
                f"<div style='color:#e0e0f0; font-size:20px; font-weight:bold;'>R$ {fmt_br(total, 2)}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        resultados[uk] = {"preco_litro": preco, "volume": vol, "valor_total": total}
        st.markdown("<hr class='separador'>", unsafe_allow_html=True)

    cor   = UNIDADES["Uiramutã"]["cor"]
    icone = UNIDADES["Uiramutã"]["icone"]
    st.markdown(
        f"<span class='badge-unidade' style='background:{cor}22; color:{cor}; border:1px solid {cor}44;'>"
        f"{icone} Uiramutã</span>",
        unsafe_allow_html=True
    )
    pm_u = st.number_input("Pm (R$/L)", min_value=0.0, step=0.001, format="%.4f", key="pm_Uiramuta")

    col_fob, col_cif = st.columns(2)
    with col_fob:
        st.markdown(
            f"<div style='background:#22c55e10; border:1px solid #22c55e33; border-radius:10px; padding:14px; margin-top:8px;'>"
            f"<div style='color:#22c55e; font-size:12px; font-weight:700; margin-bottom:6px;'>"
            f"📦 FOB — Plog: R$ {fmt_br(PLOG['Uiramutã_FOB'], 4)}</div>"
            f"<div style='color:#8888aa; font-size:11px;'>Pm + Plog_FOB + Bombeamento − Desconto</div>"
            f"</div>",
            unsafe_allow_html=True
        )
        vol_fob   = st.number_input("Volume FOB (L)", min_value=0.0, step=1.0, format="%.0f", key="vol_Uiramuta_FOB")
        preco_fob = pm_u + PLOG["Uiramutã_FOB"] + BOMBEAMENTO - DESCONTO
        total_fob = preco_fob * vol_fob
        st.markdown(
            f"<div style='background:{cor}15; border:1px solid {cor}44; border-radius:10px; padding:10px 14px; margin-top:8px;'>"
            f"<div style='color:{cor}; font-size:11px; font-weight:600;'>PREÇO / LITRO</div>"
            f"<div style='color:#e0e0f0; font-size:20px; font-weight:bold;'>R$ {fmt_br(preco_fob, 4)}</div>"
            f"<div style='color:{cor}; font-size:11px; font-weight:600; margin-top:8px;'>VALOR TOTAL</div>"
            f"<div style='color:#e0e0f0; font-size:20px; font-weight:bold;'>R$ {fmt_br(total_fob, 2)}</div>"
            f"</div>",
            unsafe_allow_html=True
        )

    with col_cif:
        st.markdown(
            f"<div style='background:#22c55e10; border:1px solid #22c55e33; border-radius:10px; padding:14px; margin-top:8px;'>"
            f"<div style='color:#22c55e; font-size:12px; font-weight:700; margin-bottom:6px;'>"
            f"🚚 CIF — Plog: R$ {fmt_br(PLOG['Uiramutã_CIF'], 4)}</div>"
            f"<div style='color:#8888aa; font-size:11px;'>Pm + Plog_CIF + Bombeamento</div>"
            f"</div>",
            unsafe_allow_html=True
        )
        vol_cif   = st.number_input("Volume CIF (L)", min_value=0.0, step=1.0, format="%.0f", key="vol_Uiramuta_CIF")
        preco_cif = pm_u + PLOG["Uiramutã_CIF"] + BOMBEAMENTO
        total_cif = preco_cif * vol_cif
        st.markdown(
            f"<div style='background:{cor}15; border:1px solid {cor}44; border-radius:10px; padding:10px 14px; margin-top:8px;'>"
            f"<div style='color:{cor}; font-size:11px; font-weight:600;'>PREÇO / LITRO</div>"
            f"<div style='color:#e0e0f0; font-size:20px; font-weight:bold;'>R$ {fmt_br(preco_cif, 4)}</div>"
            f"<div style='color:{cor}; font-size:11px; font-weight:600; margin-top:8px;'>VALOR TOTAL</div>"
            f"<div style='color:#e0e0f0; font-size:20px; font-weight:bold;'>R$ {fmt_br(total_cif, 2)}</div>"
            f"</div>",
            unsafe_allow_html=True
        )

    resultados["Uiramutã_FOB"] = {"preco_litro": preco_fob, "volume": vol_fob, "valor_total": total_fob}
    resultados["Uiramutã_CIF"] = {"preco_litro": preco_cif, "volume": vol_cif, "valor_total": total_cif}
    st.markdown("<hr class='separador'>", unsafe_allow_html=True)

    total_geral = sum(r["valor_total"] for r in resultados.values())
    st.markdown(
        f"<div class='total-box'><p>Soma de todas as unidades</p>"
        f"<h2>💰 R$ {fmt_br(total_geral, 2)}</h2>"
        f"<p style='font-size:13px; margin-top:10px;'>"
        f"🔵 Amajari: R$ {fmt_br(resultados['Amajari']['valor_total'], 2)} &nbsp;|&nbsp; "
        f"🟠 Pacaraima: R$ {fmt_br(resultados['Pacaraima']['valor_total'], 2)} &nbsp;|&nbsp; "
        f"🟢 Uiramutã FOB: R$ {fmt_br(resultados['Uiramutã_FOB']['valor_total'], 2)} &nbsp;|&nbsp; "
        f"🟢 Uiramutã CIF: R$ {fmt_br(resultados['Uiramutã_CIF']['valor_total'], 2)}</p></div>",
        unsafe_allow_html=True
    )
    st.markdown("<br>", unsafe_allow_html=True)

    with st.expander("📋 Ver resumo detalhado"):
        rows = [
            {"Unidade": "Amajari",   "Tipo": "FOB", "Plog (R$)": fmt_br(PLOG['Amajari'], 4),
             "Preço/L (R$)": fmt_br(resultados['Amajari']['preco_litro'], 4),
             "Volume (L)": fmt_br(resultados['Amajari']['volume'], 0),
             "Total (R$)": fmt_br(resultados['Amajari']['valor_total'], 2)},
            {"Unidade": "Pacaraima", "Tipo": "FOB", "Plog (R$)": fmt_br(PLOG['Pacaraima'], 4),
             "Preço/L (R$)": fmt_br(resultados['Pacaraima']['preco_litro'], 4),
             "Volume (L)": fmt_br(resultados['Pacaraima']['volume'], 0),
             "Total (R$)": fmt_br(resultados['Pacaraima']['valor_total'], 2)},
            {"Unidade": "Uiramutã",  "Tipo": "FOB", "Plog (R$)": fmt_br(PLOG['Uiramutã_FOB'], 4),
             "Preço/L (R$)": fmt_br(resultados['Uiramutã_FOB']['preco_litro'], 4),
             "Volume (L)": fmt_br(resultados['Uiramutã_FOB']['volume'], 0),
             "Total (R$)": fmt_br(resultados['Uiramutã_FOB']['valor_total'], 2)},
            {"Unidade": "Uiramutã",  "Tipo": "CIF", "Plog (R$)": fmt_br(PLOG['Uiramutã_CIF'], 4),
             "Preço/L (R$)": fmt_br(resultados['Uiramutã_CIF']['preco_litro'], 4),
             "Volume (L)": fmt_br(resultados['Uiramutã_CIF']['volume'], 0),
             "Total (R$)": fmt_br(resultados['Uiramutã_CIF']['valor_total'], 2)},
            {"Unidade": "TOTAL", "Tipo": "—", "Plog (R$)": "—",
             "Preço/L (R$)": "—", "Volume (L)": "—", "Total (R$)": fmt_br(total_geral, 2)},
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
def main():
    with st.sidebar:
        st.markdown("## ⚡ Painel Energético")
        st.markdown("---")
        st.markdown("**Filtrar por:**")
        tipo_filtro = st.radio("", ["Ano", "Mês", "Semana"], index=1,
                               label_visibility="collapsed")
        if st.button("🔄 Recarregar dados"):
            st.cache_data.clear()
            st.rerun()
        st.markdown("---")
        st.markdown(
            "<small style='color:#8888bb'>📊 Dados atualizados a cada 5 min<br>automaticamente do OneDrive.</small>",
            unsafe_allow_html=True
        )

    st.markdown("# ⚡ Dashboard Energético — RR")
    st.markdown("Amajari &nbsp;|&nbsp; Pacaraima &nbsp;|&nbsp; Uiramutã", unsafe_allow_html=True)
    st.markdown("---")

    dados, erros = carregar_dados()

    if erros:
        with st.expander("⚠️ Avisos de carregamento"):
            for e in erros:
                st.warning(e)

    periodo_sel = None
    primeiro_df = next(iter(dados.values()), None)
    if primeiro_df is not None:
        periodos = gerar_periodos(primeiro_df, tipo_filtro)
        if periodos:
            with st.sidebar:
                st.markdown("---")
                periodo_sel = st.selectbox(f"Selecione o {tipo_filtro.lower()}:", periodos)

    tab_amajari, tab_pacaraima, tab_uiramuta, tab_autonomia, tab_calc = st.tabs([
        "🔵 Amajari", "🟠 Pacaraima", "🟢 Uiramutã", "🛢️ Autonomia", "🧮 Calculadora"
    ])

    with tab_calc:
        calculadora()

    if not dados:
        for tab in [tab_amajari, tab_pacaraima, tab_uiramuta, tab_autonomia]:
            with tab:
                st.markdown(
                    "<div style='text-align:center; padding:80px; color:#4a4a6a;'>"
                    "<div style='font-size:52px'>⚠️</div>"
                    "<h3 style='color:#4a4a6a !important'>Não foi possível carregar os dados.</h3>"
                    "</div>",
                    unsafe_allow_html=True
                )
    else:
        for nome, tab in zip(UNIDADES, [tab_amajari, tab_pacaraima, tab_uiramuta]):
            with tab:
                if nome in dados and periodo_sel:
                    secao_unidade(nome, dados[nome], tipo_filtro, periodo_sel)
                else:
                    st.error(f"Dados de {nome} não disponíveis.")

        with tab_autonomia:
            if periodo_sel:
                aba_autonomia(dados, tipo_filtro, periodo_sel)
            else:
                st.warning("Selecione um período na sidebar para calcular a autonomia.")


main()