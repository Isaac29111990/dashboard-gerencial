import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import io
import unicodedata
from datetime import date, timedelta, datetime

LINK_ENERGIA = "https://usinaxavantes-my.sharepoint.com/:x:/g/personal/jefferson_ferreira_usinaxavantes_onmicrosoft_com/IQDdqWDpJPZzS5sWsTULHWMPAaPbvF6rFiA99uybNJx7zh4?e=iDHkEG"
LINK_CONSUMO = "https://usinaxavantes-my.sharepoint.com/:x:/g/personal/jefferson_ferreira_usinaxavantes_onmicrosoft_com/IQDKVJdv3LvzQY4AjhJiPbiZAYzb7lg5BPZK9-O52ctFqq4?e=RboNX9"
LINK_PRECOS = LINK_CONSUMO # Mantém o mesmo link para preços

CONFIG_PLANILHAS = {
    "Amajari": {
        "aba_consumo": "Amajari", "aba_energia": "Energia_Amajari",
        "col_data_c": "DATA", "col_consumo": "Consumo Calculado",
        "col_data_e": "DATA", "col_energia": "ENERGIA GERADA TOTAL MWh",
        "dias_antecedencia": 2,
        "aba_preco_desconto": "Preço_Amajari", # Usar Preço_Amajari para Preço Desconto
    },
    "Pacaraima": {
        "aba_consumo": "Pacaraima", "aba_energia": "Energia_Pacaraima",
        "col_data_c": "DATA", "col_consumo": "Consumo Calculado",
        "col_data_e": "DATA", "col_energia": "ENERGIA GERADA TOTAL MWh",
        "dias_antecedencia": 2,
        "aba_preco_completa": "Preço_Pacaraima", # Nova aba para Carga Completa
        "aba_preco_parcial": "Preço_Pacaraima_Parcial", # Nova aba para Carga Parcial
    },
    "Uiramutã": {
        "aba_consumo": "Uiramutã", "aba_energia": "Energia_Uiramutã",
        "col_data_c": "DATA", "col_consumo": "Consumo Calculado",
        "col_data_e": "Data", "col_energia": "Energia Gerada MWh",
        "dias_antecedencia": 3,
        "aba_preco_fob": "Preço_Uiramutã_FOB", # Usar Preço_Uiramutã_FOB para Preço Final
        "aba_preco_cif": "Preço_Uiramutã_CIF", # Usar Preço_Uiramutã_CIF para Preço Desconto
    },
}

st.set_page_config(page_title="Acompanhamento Gerencial PIE Roraima", page_icon="⚡", layout="wide")

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
# PLOG fixo removido, será carregado dinamicamente

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

def ler_aba_preco_excel(xl_file, sheet_name):
    df_raw = pd.read_excel(xl_file, sheet_name=sheet_name, header=None, nrows=20)
    header_row = None
    cols_alvo = ["DATA", "PREÇO MÉDIO", "PREÇO FINAL", "PREÇO DESCONTO", "PLOG"] # Adicionado PLOG
    norm_cols_alvo = [norm(c) for c in cols_alvo]

    for i, row in df_raw.iterrows():
        valores = [norm(str(v)) for v in row.values]
        if all(c in valores for c in norm_cols_alvo):
            header_row = i
            break

    if header_row is None:
        return None, f"Cabeçalho de preços não encontrado na aba '{sheet_name}'. Colunas esperadas: {cols_alvo}"

    df = pd.read_excel(xl_file, sheet_name=sheet_name, header=header_row)

    col_data_found    = encontrar_coluna(df.columns, "DATA")
    col_pm_found      = encontrar_coluna(df.columns, "PREÇO MÉDIO")
    col_pf_found      = encontrar_coluna(df.columns, "PREÇO FINAL")
    col_desc_found    = encontrar_coluna(df.columns, "PREÇO DESCONTO")
    col_plog_found    = encontrar_coluna(df.columns, "PLOG") # Encontrar coluna PLOG

    if not all([col_data_found, col_pm_found, col_pf_found, col_desc_found, col_plog_found]):
        return None, f"Algumas colunas de preço não encontradas na aba '{sheet_name}'. Disponíveis: {list(df.columns)}"

    df = df[[col_data_found, col_pm_found, col_pf_found, col_desc_found, col_plog_found]].copy()
    df.columns = ["data", "preco_medio", "preco_final", "preco_desconto", "plog"] # Adicionado plog
    df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
    df["preco_medio"]    = pd.to_numeric(df["preco_medio"], errors="coerce")
    df["preco_final"]    = pd.to_numeric(df["preco_final"], errors="coerce")
    df["preco_desconto"] = pd.to_numeric(df["preco_desconto"], errors="coerce")
    df["plog"]           = pd.to_numeric(df["plog"], errors="coerce") # Converter PLOG
    df = df.dropna(subset=["data", "preco_medio", "preco_final", "preco_desconto", "plog"]).sort_values("data", ascending=False).reset_index(drop=True)

    if df.empty:
        return None, f"Nenhum dado válido encontrado na aba '{sheet_name}' após processamento."

    # Retorna apenas a linha mais recente
    return df.iloc[0], None


@st.cache_data(ttl=300)
def carregar_dados():
    dados = {}
    erros = []
    xl_consumo = None
    xl_energia = None
    xl_precos  = None

    try:
        r = requests.get(converter_link(LINK_CONSUMO), timeout=20)
        r.raise_for_status()
        xl_consumo = pd.ExcelFile(io.BytesIO(r.content))
        xl_precos = xl_consumo
    except Exception as e:
        erros.append(f"Erro ao baixar planilha de consumo/preços: {e}")

    try:
        r = requests.get(converter_link(LINK_ENERGIA), timeout=20)
        r.raise_for_status()
        xl_energia = pd.ExcelFile(io.BytesIO(r.content))
    except Exception as e:
        erros.append(f"Erro ao baixar planilha de energia: {e}")

    precos_carregados = {}

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

        if xl_precos is not None:
            if unidade == "Amajari":
                aba_preco = cfg.get("aba_preco_desconto")
                if aba_preco:
                    try:
                        preco_data, erro = ler_aba_preco_excel(xl_precos, aba_preco)
                        if erro:
                            erros.append(f"{unidade} — Preços: {erro}")
                        else:
                            precos_carregados[unidade] = preco_data
                    except Exception as e:
                        erros.append(f"{unidade} — Aba de preços '{aba_preco}': {e}")
            elif unidade == "Pacaraima":
                aba_preco_completa = cfg.get("aba_preco_completa")
                aba_preco_parcial  = cfg.get("aba_preco_parcial")
                if aba_preco_completa:
                    try:
                        preco_completa_data, erro = ler_aba_preco_excel(xl_precos, aba_preco_completa)
                        if erro:
                            erros.append(f"{unidade} — Preços Carga Completa: {erro}")
                        else:
                            precos_carregados["Pacaraima_Completa"] = preco_completa_data
                    except Exception as e:
                        erros.append(f"{unidade} — Aba de preços Carga Completa '{aba_preco_completa}': {e}")
                if aba_preco_parcial:
                    try:
                        preco_parcial_data, erro = ler_aba_preco_excel(xl_precos, aba_preco_parcial)
                        if erro:
                            erros.append(f"{unidade} — Preços Carga Parcial: {erro}")
                        else:
                            precos_carregados["Pacaraima_Parcial"] = preco_parcial_data
                    except Exception as e:
                        erros.append(f"{unidade} — Aba de preços Carga Parcial '{aba_preco_parcial}': {e}")
            elif unidade == "Uiramutã":
                aba_preco_fob = cfg.get("aba_preco_fob")
                aba_preco_cif = cfg.get("aba_preco_cif")
                if aba_preco_fob:
                    try:
                        preco_fob_data, erro = ler_aba_preco_excel(xl_precos, aba_preco_fob)
                        if erro:
                            erros.append(f"{unidade} — Preços FOB: {erro}")
                        else:
                            precos_carregados["Uiramutã_FOB"] = preco_fob_data
                    except Exception as e:
                        erros.append(f"{unidade} — Aba de preços FOB '{aba_preco_fob}': {e}")
                if aba_preco_cif:
                    try:
                        preco_cif_data, erro = ler_aba_preco_excel(xl_precos, aba_preco_cif)
                        if erro:
                            erros.append(f"{unidade} — Preços CIF: {erro}")
                        else:
                            precos_carregados["Uiramutã_CIF"] = preco_cif_data
                    except Exception as e:
                        erros.append(f"{unidade} — Aba de preços CIF '{aba_preco_cif}': {e}")

    return dados, erros, precos_carregados


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
    # Garante que media_energia e cons_esp sejam floats, mesmo que venham como None
    media_energia = float(media_energia) if media_energia is not None else 0.0
    cons_esp = float(cons_esp) if cons_esp is not None else 0.0

    if not all([media_energia > 0, cons_esp > 0]): # Verifica se são maiores que zero após a conversão
        return None, None, None

    gerador_dia = media_energia / 24

    if gerador_dia == 0:
        return 0.0, 0.0, datetime.now()

    horas_operacao = (estoque / cons_esp) / gerador_dia

    if usar_seguranca:
        horas_operacao = horas_operacao - estoque_geradores - 24

    horas_operacao = max(horas_operacao, 0)
    dias_operacao  = horas_operacao / 24

    if horas_operacao == 0:
        return 0.0, 0.0, datetime.now()

    data_hora_limite = datetime.now() + timedelta(hours=horas_operacao)

    return horas_operacao, dias_operacao, data_hora_limite


def card_autonomia(titulo, horas, dias, cor, data_hora_limite=None, data_hora_carregamento=None):
    if horas is None:
        return (
            "<div style='background:#1e1e2e; border:1px solid #2a2a4a; border-radius:14px; "
            f"padding:20px 24px; margin-bottom:12px;'>"
            f"<div style='color:#8888aa; font-size:12px; font-weight:600;'>{titulo}</div>"
            "<div style='color:#4a4a6a; font-size:16px; margin-top:8px;'>Dados insuficientes.</div>"
            "</div>"
        )

    data_lim_str  = data_hora_limite.strftime("%d/%m/%Y")       if data_hora_limite       else "—"
    hora_lim_str  = data_hora_limite.strftime("%H:%M")          if data_hora_limite       else "—"
    data_carg_str = data_hora_carregamento.strftime("%d/%m/%Y") if data_hora_carregamento else "—"
    hora_carg_str = data_hora_carregamento.strftime("%H:%M")    if data_hora_carregamento else "—"

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
        f"<div style='color:{cor}; font-size:22px; font-weight:700;'>{data_lim_str} {hora_lim_str}</div></div>"
        f"<div><div style='color:#8888aa; font-size:11px;'>⚠️ Carregar até</div>"
        f"<div style='color:#f97316; font-size:22px; font-weight:700;'>{data_carg_str} {hora_carg_str}</div></div>"
        f"</div></div>"
    )
    return html


def _render_resumo_html(resumo_data, title_prefix):
    rows = []
    for nome, info in resumo_data.items():
        data_aut_str  = info["data_limite"].strftime("%d/%m/%Y") if info["data_limite"]      else "—"
        hora_aut_str  = info["data_limite"].strftime("%H:%M")    if info["data_limite"]      else "—"
        data_carg_str = info["data_carga"].strftime("%d/%m/%Y")  if info["data_carga"]       else "—"
        hora_carg_str = info["data_carga"].strftime("%H:%M")     if info["data_carga"]       else "—"
        dias  = fmt_br(info["dias"], 1)                  if info["dias"] is not None else "—"
        horas = fmt_br(info["horas"], 1)                 if info["horas"] is not None else "—"
        estoque = fmt_br(info["estoque"], 0)             if info["estoque"] is not None else "—"

        rows.append({
            "Unidade": nome,
            "Volume Estoque (L)": estoque,
            "Horas de Operação": horas,
            "Dias de Operação": dias,
            "Data Autonomia": data_aut_str,
            "Hora Autonomia": hora_aut_str,
            "Data Carregar": data_carg_str,
            "Hora Carregar": hora_carg_str,
        })

    if rows:
        df_resumo = pd.DataFrame(rows)
        with st.expander(f"📋 {title_prefix}"):
            st.dataframe(df_resumo, use_container_width=True, hide_index=True)
    st.markdown("<hr class='separador'>", unsafe_allow_html=True)


def aba_autonomia(dados, tipo_filtro, periodo_sel):
    st.markdown("## 🛢️ Autonomia de Combustível")
    st.markdown(
        f"<p style='color:#8888aa; font-size:13px; margin-top:-10px;'>"
        f"Baseado nas médias do período selecionado ({periodo_sel}).<br>"
        f"Gerador/hora = Média Energia / 24 &nbsp;|&nbsp; "
        f"Horas = (Estoque / Cons. Esp.) / Gerador/hora [− Estoque Geradores − 24h se segurança ativada]<br>"
        f"Data Carregamento = Autonomia − dias de antecedência configurados por unidade."
        f"</p>",
        unsafe_allow_html=True
    )

    agora = datetime.now()
    resumo_atual = {}
    resumo_com_compra = {}

    if 'autonomia_data_for_calc' not in st.session_state:
        st.session_state['autonomia_data_for_calc'] = {}

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
            # Continuar para a próxima unidade se não houver dados para esta
            # Mas ainda precisamos inicializar os dados para o resumo para evitar KeyError
            resumo_atual[nome] = {
                "estoque":     0.0,
                "horas":       None,
                "dias":        None,
                "data_limite": None,
                "data_carga":  None,
            }
            resumo_com_compra[nome] = {
                "estoque":     0.0,
                "horas":       None,
                "dias":        None,
                "data_limite": None,
                "data_carga":  None,
            }
            st.session_state['autonomia_data_for_calc'][nome] = {
                "data_limite_total": None,
                "vol_comprado": 0.0,
                "estoque_atual_input": 0.0
            }
            continue # Pula para a próxima unidade no loop

        tem_energia = "energia_gerada"     in df_f.columns and df_f["energia_gerada"].notna().any()
        tem_cesp    = "consumo_especifico" in df_f.columns and df_f["consumo_especifico"].notna().any()

        # Garante que media_energia e media_cesp sejam 0.0 se não houver dados
        media_energia = float(df_f["energia_gerada"].mean())     if tem_energia else 0.0
        media_cesp    = float(df_f["consumo_especifico"].mean()) if tem_cesp    else 0.0

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
            estoque_atual_input = st.number_input(
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
        horas_atual, dias_atual, data_hora_limite_atual = calcular_autonomia(
            estoque_atual_input, est_ger_efetivo, media_energia, media_cesp,
            usar_seguranca=usar_estoque_ger
        )
        data_hora_carregamento_atual = (data_hora_limite_atual - timedelta(days=dias_antecedencia)) if data_hora_limite_atual else None

        # Cenário 2 — estoque + compra
        horas_total, dias_total, data_hora_limite_total = calcular_autonomia(
            estoque_atual_input + vol_comprado, est_ger_efetivo, media_energia, media_cesp,
            usar_seguranca=usar_estoque_ger
        )
        data_hora_carregamento_total = (data_hora_limite_total - timedelta(days=dias_antecedencia)) if data_hora_limite_total else None

        # Guarda para os resumos
        resumo_atual[nome] = {
            "estoque":     estoque_atual_input,
            "horas":       horas_atual,
            "dias":        dias_atual,
            "data_limite": data_hora_limite_atual,
            "data_carga":  data_hora_carregamento_atual,
        }
        resumo_com_compra[nome] = {
            "estoque":     estoque_atual_input + vol_comprado,
            "horas":       horas_total,
            "dias":        dias_total,
            "data_limite": data_hora_limite_total,
            "data_carga":  data_hora_carregamento_total,
        }

        # Armazena dados relevantes para a calculadora no session_state
        st.session_state['autonomia_data_for_calc'][nome] = {
            "data_limite_total": data_hora_limite_total,
            "vol_comprado": vol_comprado,
            "estoque_atual_input": estoque_atual_input
        }

        st.markdown(
            card_autonomia("📊 Cenário atual — somente estoque",
                           horas_atual, dias_atual, cor,
                           data_hora_limite_atual, data_hora_carregamento_atual),
            unsafe_allow_html=True
        )
        st.markdown(
            card_autonomia("📦 Cenário com compra — estoque + volume comprado",
                           horas_total, dias_total, cor,
                           data_hora_limite_total, data_hora_carregamento_total),
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
def calculadora(precos_carregados):
    st.markdown("## 🧮 Calculadora de Compra de Combustível")
    st.markdown(
        f"<p style='color:#8888aa; font-size:13px; margin-top:-10px;'>"
        f"Bombeamento: R$ {fmt_br(BOMBEAMENTO, 3)} &nbsp;|&nbsp; Desconto: R$ {fmt_br(DESCONTO, 4)}<br>"
        f"FOB — Preço/Litro = Pm + Plog + Bombeamento − Desconto &nbsp;|&nbsp; "
        f"CIF — Preço/Litro = Pm + Plog + Bombeamento</p>", # Descrição antiga, o cálculo agora usa as colunas diretas
        unsafe_allow_html=True
    )
    st.markdown("<hr class='separador'>", unsafe_allow_html=True)
    resultados = {}
    observacoes = {}

    autonomia_data = st.session_state.get('autonomia_data_for_calc', {})

    todas_datas_compra = []

    # Amajari
    uk = "Amajari"
    cor   = UNIDADES[uk]["cor"]
    icone = UNIDADES[uk]["icone"]

    preco_info = precos_carregados.get(uk, {})
    pm_planilha = preco_info.get("preco_medio", 0.0)
    pf_planilha = preco_info.get("preco_final", 0.0)
    pd_planilha = preco_info.get("preco_desconto", 0.0)
    plog_planilha = preco_info.get("plog", 0.0) # Plog dinâmico
    data_preco_planilha = preco_info.get("data")

    st.markdown(
        f"<span class='badge-unidade' style='background:{cor}22; color:{cor}; border:1px solid {cor}44;'>"
        f"{icone} {uk} &nbsp;<small style='opacity:0.7'>Plog: R$ {fmt_br(plog_planilha, 4)}</small></span>",
        unsafe_allow_html=True
    )

    if data_preco_planilha:
        st.markdown(f"<p style='color:#8888aa; font-size:12px; margin-top:-8px;'>Último preço carregado em: {data_preco_planilha.strftime('%d/%m/%Y')}</p>", unsafe_allow_html=True)
    else:
        st.warning(f"Não foi possível carregar os preços mais recentes para {uk}.")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f"<div style='background:#1e1e2e; border:1px solid #2a2a4a; border-radius:8px; "
            f"padding:10px 14px; margin-top:26px;'>"
            f"<div style='color:#8888aa; font-size:11px;'>Preço Médio (Pm)</div>"
            f"<div style='color:#e0e0f0; font-size:18px; font-weight:bold;'>R$ {fmt_br(pm_planilha, 4)}</div>"
            f"</div>",
            unsafe_allow_html=True
        )
    with c2:
        st.markdown(
            f"<div style='background:#1e1e2e; border:1px solid #2a2a4a; border-radius:8px; "
            f"padding:10px 14px; margin-top:26px;'>"
            f"<div style='color:#8888aa; font-size:11px;'>Plog</div>"
            f"<div style='color:#e0e0f0; font-size:18px; font-weight:bold;'>R$ {fmt_br(plog_planilha, 4)}</div>"
            f"</div>",
            unsafe_allow_html=True
        )
    with c3:
        vol_default = autonomia_data.get(uk, {}).get("vol_comprado", 0.0)
        vol = st.number_input("Volume (L)", min_value=0.0, step=1.0, format="%.0f", key=f"vol_{uk}", value=vol_default)
    with c4:
        preco = pd_planilha # Amajari usa Preço Desconto
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
    resultados[uk] = {"preco_litro": preco, "volume": vol, "valor_total": total,
                      "preco_medio_planilha": pm_planilha, "preco_final_planilha": pf_planilha,
                      "preco_desconto_planilha": pd_planilha, "plog_planilha": plog_planilha}

    observacoes[uk] = st.text_area(f"Observação para {uk}", key=f"obs_{uk}", height=50)

    if uk in autonomia_data:
        data_limite_total = autonomia_data[uk].get("data_limite_total")
        if data_limite_total:
            data_da_compra = data_limite_total - timedelta(days=4) # Exemplo de 4 dias de antecedência
            todas_datas_compra.append(data_da_compra)

    st.markdown("<hr class='separador'>", unsafe_allow_html=True)

    # Pacaraima
    uk = "Pacaraima"
    cor   = UNIDADES[uk]["cor"]
    icone = UNIDADES[uk]["icone"]
    st.markdown(
        f"<span class='badge-unidade' style='background:{cor}22; color:{cor}; border:1px solid {cor}44;'>"
        f"{icone} {uk}</span>",
        unsafe_allow_html=True
    )

    tipo_pacaraima = st.radio("Selecione o tipo de carga para Pacaraima:", ["Carga Completa", "Carga Parcial"], key="tipo_pacaraima_calc")

    pm_p_planilha = 0.0
    pf_p_planilha = 0.0
    pd_p_planilha = 0.0
    plog_p_planilha = 0.0
    data_preco_p_planilha = None

    if tipo_pacaraima == "Carga Completa":
        preco_info_p = precos_carregados.get("Pacaraima_Completa", {})
        pm_p_planilha = preco_info_p.get("preco_medio", 0.0)
        pf_p_planilha = preco_info_p.get("preco_final", 0.0)
        pd_p_planilha = preco_info_p.get("preco_desconto", 0.0)
        plog_p_planilha = preco_info_p.get("plog", 0.0)
        data_preco_p_planilha = preco_info_p.get("data")
    elif tipo_pacaraima == "Carga Parcial":
        preco_info_p = precos_carregados.get("Pacaraima_Parcial", {})
        pm_p_planilha = preco_info_p.get("preco_medio", 0.0)
        pf_p_planilha = preco_info_p.get("preco_final", 0.0)
        pd_p_planilha = preco_info_p.get("preco_desconto", 0.0)
        plog_p_planilha = preco_info_p.get("plog", 0.0)
        data_preco_p_planilha = preco_info_p.get("data")

    if data_preco_p_planilha:
        st.markdown(f"<p style='color:#8888aa; font-size:12px; margin-top:-8px;'>Último preço carregado em: {data_preco_p_planilha.strftime('%d/%m/%Y')}</p>", unsafe_allow_html=True)
    else:
        st.warning(f"Não foi possível carregar os preços mais recentes para Pacaraima ({tipo_pacaraima}).")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f"<div style='background:#1e1e2e; border:1px solid #2a2a4a; border-radius:8px; "
            f"padding:10px 14px; margin-top:26px;'>"
            f"<div style='color:#8888aa; font-size:11px;'>Preço Médio (Pm)</div>"
            f"<div style='color:#e0e0f0; font-size:18px; font-weight:bold;'>R$ {fmt_br(pm_p_planilha, 4)}</div>"
            f"</div>",
            unsafe_allow_html=True
        )
    with c2:
        st.markdown(
            f"<div style='background:#1e1e2e; border:1px solid #2a2a4a; border-radius:8px; "
            f"padding:10px 14px; margin-top:26px;'>"
            f"<div style='color:#8888aa; font-size:11px;'>Plog</div>"
            f"<div style='color:#e0e0f0; font-size:18px; font-weight:bold;'>R$ {fmt_br(plog_p_planilha, 4)}</div>"
            f"</div>",
            unsafe_allow_html=True
        )
    with c3:
        vol_default = autonomia_data.get(uk, {}).get("vol_comprado", 0.0)
        volume_pacaraima = st.number_input(f"Volume {tipo_pacaraima} (L)", min_value=0.0, step=1.0, format="%.0f", key=f"vol_{uk}_{tipo_pacaraima}", value=vol_default)
    with c4:
        preco_pacaraima = pd_p_planilha # Pacaraima (ambos) usam Preço Desconto
        total_pacaraima = preco_pacaraima * volume_pacaraima
        st.markdown(
            f"<div style='background:{cor}15; border:1px solid {cor}44; border-radius:10px; "
            f"padding:10px 14px; margin-top:26px;'>"
            f"<div style='color:{cor}; font-size:11px; font-weight:600;'>PREÇO / LITRO</div>"
            f"<div style='color:#e0e0f0; font-size:20px; font-weight:bold;'>R$ {fmt_br(preco_pacaraima, 4)}</div>"
            f"<div style='color:{cor}; font-size:11px; font-weight:600; margin-top:8px;'>VALOR TOTAL</div>"
            f"<div style='color:#e0e0f0; font-size:20px; font-weight:bold;'>R$ {fmt_br(total_pacaraima, 2)}</div>"
            f"</div>",
            unsafe_allow_html=True
        )
    resultados[f"{uk}_{tipo_pacaraima.replace(' ', '_')}"] = {
        "preco_litro": preco_pacaraima, "volume": volume_pacaraima, "valor_total": total_pacaraima,
        "preco_medio_planilha": pm_p_planilha, "preco_final_planilha": pf_p_planilha,
        "preco_desconto_planilha": pd_p_planilha, "plog_planilha": plog_p_planilha
    }
    # Zera o outro tipo para o total geral
    if tipo_pacaraima == "Carga Completa":
        resultados["Pacaraima_Parcial"] = {"preco_litro": 0.0, "volume": 0.0, "valor_total": 0.0, "preco_medio_planilha": 0.0, "preco_final_planilha": 0.0, "preco_desconto_planilha": 0.0, "plog_planilha": 0.0}
    else:
        resultados["Pacaraima_Completa"] = {"preco_litro": 0.0, "volume": 0.0, "valor_total": 0.0, "preco_medio_planilha": 0.0, "preco_final_planilha": 0.0, "preco_desconto_planilha": 0.0, "plog_planilha": 0.0}


    observacoes[uk] = st.text_area(f"Observação para {uk} ({tipo_pacaraima})", key=f"obs_{uk}_{tipo_pacaraima}", height=50)

    if uk in autonomia_data:
        data_limite_total = autonomia_data[uk].get("data_limite_total")
        if data_limite_total:
            data_da_compra = data_limite_total - timedelta(days=4)
            todas_datas_compra.append(data_da_compra)

    st.markdown("<hr class='separador'>", unsafe_allow_html=True)

    # Uiramutã
    uk = "Uiramutã"
    cor   = UNIDADES[uk]["cor"]
    icone = UNIDADES[uk]["icone"]
    st.markdown(
        f"<span class='badge-unidade' style='background:{cor}22; color:{cor}; border:1px solid {cor}44;'>"
        f"{icone} {uk}</span>",
        unsafe_allow_html=True
    )

    tipo_uiramuta = st.radio("Selecione o tipo para Uiramutã:", ["FOB", "CIF"], key="tipo_uiramuta_calc")

    pm_u_planilha = 0.0
    pf_u_planilha = 0.0
    pd_u_planilha = 0.0
    plog_u_planilha = 0.0
    data_preco_u_planilha = None

    if tipo_uiramuta == "FOB":
        preco_info_u = precos_carregados.get("Uiramutã_FOB", {})
        pm_u_planilha = preco_info_u.get("preco_medio", 0.0)
        pf_u_planilha = preco_info_u.get("preco_final", 0.0)
        pd_u_planilha = preco_info_u.get("preco_desconto", 0.0)
        plog_u_planilha = preco_info_u.get("plog", 0.0)
        data_preco_u_planilha = preco_info_u.get("data")
    elif tipo_uiramuta == "CIF":
        preco_info_u = precos_carregados.get("Uiramutã_CIF", {})
        pm_u_planilha = preco_info_u.get("preco_medio", 0.0)
        pf_u_planilha = preco_info_u.get("preco_final", 0.0)
        pd_u_planilha = preco_info_u.get("preco_desconto", 0.0)
        plog_u_planilha = preco_info_u.get("plog", 0.0)
        data_preco_u_planilha = preco_info_u.get("data")

    if data_preco_u_planilha:
        st.markdown(f"<p style='color:#8888aa; font-size:12px; margin-top:-8px;'>Último preço carregado em: {data_preco_u_planilha.strftime('%d/%m/%Y')}</p>", unsafe_allow_html=True)
    else:
        st.warning(f"Não foi possível carregar os preços mais recentes para Uiramutã ({tipo_uiramuta}).")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f"<div style='background:#1e1e2e; border:1px solid #2a2a4a; border-radius:8px; "
            f"padding:10px 14px; margin-top:26px;'>"
            f"<div style='color:#8888aa; font-size:11px;'>Preço Médio (Pm)</div>"
            f"<div style='color:#e0e0f0; font-size:18px; font-weight:bold;'>R$ {fmt_br(pm_u_planilha, 4)}</div>"
            f"</div>",
            unsafe_allow_html=True
        )
    with c2:
        st.markdown(
            f"<div style='background:#1e1e2e; border:1px solid #2a2a4a; border-radius:8px; "
            f"padding:10px 14px; margin-top:26px;'>"
            f"<div style='color:#8888aa; font-size:11px;'>Plog</div>"
            f"<div style='color:#e0e0f0; font-size:18px; font-weight:bold;'>R$ {fmt_br(plog_u_planilha, 4)}</div>"
            f"</div>",
            unsafe_allow_html=True
        )
    with c3:
        vol_default = autonomia_data.get(uk, {}).get("vol_comprado", 0.0)
        volume_uiramuta = st.number_input(f"Volume {tipo_uiramuta} (L)", min_value=0.0, step=1.0, format="%.0f", key=f"vol_{uk}_{tipo_uiramuta}", value=vol_default)
    with c4:
        preco_uiramuta = pf_u_planilha if tipo_uiramuta == "FOB" else pd_u_planilha # Uiramutã FOB usa Preço Final, CIF usa Preço Desconto
        total_uiramuta = preco_uiramuta * volume_uiramuta
        st.markdown(
            f"<div style='background:{cor}15; border:1px solid {cor}44; border-radius:10px; "
            f"padding:10px 14px; margin-top:26px;'>"
            f"<div style='color:{cor}; font-size:11px; font-weight:600;'>PREÇO / LITRO</div>"
            f"<div style='color:#e0e0f0; font-size:20px; font-weight:bold;'>R$ {fmt_br(preco_uiramuta, 4)}</div>"
            f"<div style='color:{cor}; font-size:11px; font-weight:600; margin-top:8px;'>VALOR TOTAL</div>"
            f"<div style='color:#e0e0f0; font-size:20px; font-weight:bold;'>R$ {fmt_br(total_uiramuta, 2)}</div>"
            f"</div>",
            unsafe_allow_html=True
        )
    resultados[f"{uk}_{tipo_uiramuta}"] = {
        "preco_litro": preco_uiramuta, "volume": volume_uiramuta, "valor_total": total_uiramuta,
        "preco_medio_planilha": pm_u_planilha, "preco_final_planilha": pf_u_planilha,
        "preco_desconto_planilha": pd_u_planilha, "plog_planilha": plog_u_planilha
    }
    # Zera o outro tipo para o total geral
    if tipo_uiramuta == "FOB":
        resultados["Uiramutã_CIF"] = {"preco_litro": 0.0, "volume": 0.0, "valor_total": 0.0, "preco_medio_planilha": 0.0, "preco_final_planilha": 0.0, "preco_desconto_planilha": 0.0, "plog_planilha": 0.0}
    else:
        resultados["Uiramutã_FOB"] = {"preco_litro": 0.0, "volume": 0.0, "valor_total": 0.0, "preco_medio_planilha": 0.0, "preco_final_planilha": 0.0, "preco_desconto_planilha": 0.0, "plog_planilha": 0.0}

    observacoes[uk] = st.text_area(f"Observação para {uk} ({tipo_uiramuta})", key=f"obs_{uk}_{tipo_uiramuta}", height=50)

    if uk in autonomia_data:
        data_limite_total = autonomia_data[uk].get("data_limite_total")
        if data_limite_total:
            data_da_compra = data_limite_total - timedelta(days=4)
            todas_datas_compra.append(data_da_compra)

    st.markdown("<hr class='separador'>", unsafe_allow_html=True)

    total_geral = sum(r["valor_total"] for r in resultados.values())
    st.markdown(
        f"<div class='total-box'><p>Soma de todas as unidades</p>"
        f"<h2>💰 R$ {fmt_br(total_geral, 2)}</h2>"
        f"<p style='font-size:13px; margin-top:10px;'>"
        f"🔵 Amajari: R$ {fmt_br(resultados['Amajari']['valor_total'], 2)} &nbsp;|&nbsp; "
        f"🟠 Pacaraima {tipo_pacaraima}: R$ {fmt_br(total_pacaraima, 2) if total_pacaraima is not None else '—'} &nbsp;|&nbsp; "
        f"🟢 Uiramutã {tipo_uiramuta}: R$ {fmt_br(total_uiramuta, 2) if total_uiramuta is not None else '—'}</p></div>",
        unsafe_allow_html=True
    )
    st.markdown("<br>", unsafe_allow_html=True)

    with st.expander("📋 Ver resumo detalhado"):
        rows = []

        menor_data_compra_str = "—"
        if todas_datas_compra:
            menor_data_compra = min(todas_datas_compra)
            menor_data_compra_str = menor_data_compra.strftime("%d/%m/%Y")

        # Amajari
        unit_name = "Amajari"
        volume = resultados[unit_name]['volume']
        valor_total = resultados[unit_name]['valor_total']
        obs = observacoes.get(unit_name, "—")
        preco_litro_calc = resultados[unit_name]['preco_litro'] # Preço Desconto

        rows.append({
            "Unidade": unit_name,
            "Tipo": "Padrão",
            "Preço/Litro (R$)": fmt_br(preco_litro_calc, 4),
            "Volume (L)": fmt_br(volume, 0),
            "Total (R$)": fmt_br(valor_total, 2),
            "Data da Compra": menor_data_compra_str,
            "Observação": obs
        })

        # Pacaraima
        unit_name = "Pacaraima"
        # Pega os dados do tipo de carga selecionado
        key_pacaraima = f"{unit_name}_{tipo_pacaraima.replace(' ', '_')}"
        volume = resultados[key_pacaraima]['volume']
        valor_total = resultados[key_pacaraima]['valor_total']
        obs = observacoes.get(unit_name, "—") # Observação é geral para Pacaraima
        preco_litro_calc = resultados[key_pacaraima]['preco_litro'] # Preço Desconto

        rows.append({
            "Unidade": unit_name,
            "Tipo": tipo_pacaraima,
            "Preço/Litro (R$)": fmt_br(preco_litro_calc, 4),
            "Volume (L)": fmt_br(volume, 0),
            "Total (R$)": fmt_br(valor_total, 2),
            "Data da Compra": menor_data_compra_str,
            "Observação": obs
        })

        # Uiramutã
        unit_name = "Uiramutã"
        volume = resultados[f"{unit_name}_{tipo_uiramuta}"]['volume']
        valor_total = resultados[f"{unit_name}_{tipo_uiramuta}"]['valor_total']
        obs = observacoes.get(unit_name, "—")
        preco_litro_calc = resultados[f"{unit_name}_{tipo_uiramuta}"]['preco_litro'] # Preço Final ou Preço Desconto

        rows.append({
            "Unidade": unit_name,
            "Tipo": tipo_uiramuta,
            "Preço/Litro (R$)": fmt_br(preco_litro_calc, 4),
            "Volume (L)": fmt_br(volume, 0),
            "Total (R$)": fmt_br(valor_total, 2),
            "Data da Compra": menor_data_compra_str,
            "Observação": obs
        })

        rows.append({
            "Unidade": "TOTAL", "Tipo": "—",
            "Preço/Litro (R$)": "—",
            "Volume (L)": "—", "Total (R$)": fmt_br(total_geral, 2),
            "Data da Compra": menor_data_compra_str if menor_data_compra_str != "—" else "—",
            "Observação": "—"
        })

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

    st.markdown("# ⚡ Acompanhamento Gerencial PIE Roraima")
    st.markdown("Amajari &nbsp;|&nbsp; Pacaraima &nbsp;|&nbsp; Uiramutã", unsafe_allow_html=True)
    st.markdown("---")

    dados, erros, precos_carregados = carregar_dados()

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
        calculadora(precos_carregados)

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
