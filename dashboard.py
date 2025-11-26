import streamlit as st
import pandas as pd

from nba_core import (
    build_player_multi_stats_report,
    build_team_matchup_report,
    build_team_h2h_table,
)

# IMPORTS DO PDF
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
import io

# ---------------------------------------------------------
# Mapa abreviaturas -> nomes completos
# ---------------------------------------------------------
TEAM_ABBR_TO_NAME = {
    "ATL": "Atlanta Hawks",
    "BOS": "Boston Celtics",
    "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets",
    "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets",
    "IND": "Indiana Pacers",
    "LAC": "Los Angeles Clippers",
    "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans",
    "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",
    "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings",
    "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz",
    "WAS": "Washington Wizards",
}

# Caminho do logo usado pelo programa
LOGO_PATH = "bball_logo.png"


def draw_header_footer(canvas, doc, title_text: str):
    """
    Cabeçalho com logo + nome do programa (BBall Scorer)
    Rodapé com página + data/hora
    """
    canvas.saveState()

    width, height = doc.pagesize

    # ---------- CABEÇALHO ----------
    try:
        logo_w = 2.0 * cm
        logo_h = 2.0 * cm
        canvas.drawImage(
            LOGO_PATH,
            20,
            height - logo_h - 20,
            width=logo_w,
            height=logo_h,
            preserveAspectRatio=True,
            mask="auto",
        )
    except Exception:
        pass

    canvas.setFont("Helvetica", 12)
    canvas.drawCentredString(
        width / 2,
        height - 28,
        "BBall Scorer Estatísticas NBA | Versão de teste https://app.bballscorer.com/",
    )

    canvas.setFont("Helvetica-Bold", 13)
    canvas.drawCentredString(width / 2, height - 50, title_text)

    canvas.setLineWidth(0.3)
    canvas.line(width * 0.15, height - 58, width * 0.85, height - 58)

    from datetime import datetime

    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(width - 20, 18, f"Página {doc.page}")
    canvas.drawString(
        20, 18, "Gerado em: " + datetime.now().strftime("%d/%m/%Y %H:%M")
    )

    canvas.restoreState()


# ---------------------------------------------------------
# Helpers de estilo para o dashboard
# ---------------------------------------------------------
def _strip_prefix_metric(df_block: pd.DataFrame) -> pd.DataFrame:
    """Remove 'Geral - ' e 'Casa/Fora - ' da coluna Métrica."""
    df_block = df_block.copy()
    if "Métrica" in df_block.columns:
        df_block["Métrica"] = (
            df_block["Métrica"]
            .str.replace("Geral - ", "", regex=False)
            .str.replace("Casa/Fora - ", "", regex=False)
        )
    return df_block


def style_team_block(df_block: pd.DataFrame, home_name: str, away_name: str):
    """
    Estilo para blocos de equipas (forma geral / casa-fora).
    """
    df_block = _strip_prefix_metric(df_block).reset_index(drop=True)

    home_col = home_name
    away_col = away_name
    home_flag_col = f"{home_name} ✓"
    away_flag_col = f"{away_name} ✓"

    flags = df_block[[home_flag_col, away_flag_col]].copy()
    df_show = df_block.drop(columns=[home_flag_col, away_flag_col])

    def color_from_flags(row):
        idx = row.name
        flag_home = flags.loc[idx, home_flag_col]
        flag_away = flags.loc[idx, away_flag_col]

        styles = []
        for col in df_show.columns:
            if col == home_col:
                if flag_home == "✅":
                    styles.append("background-color: #c6efce")
                elif flag_home == "❌":
                    styles.append("background-color: #ffc7ce")
                else:
                    styles.append("")
            elif col == away_col:
                if flag_away == "✅":
                    styles.append("background-color: #c6efce")
                elif flag_away == "❌":
                    styles.append("background-color: #ffc7ce")
                else:
                    styles.append("")
            else:
                styles.append("")
        return styles

    styler = df_show.style.apply(color_from_flags, axis=1).format(precision=0)
    return styler


def style_player_table(df_multi: pd.DataFrame):
    """
    Remove colunas '... ✓' e pinta as colunas de valor associadas
    (ex.: 'PTS', 'REB', 'PRA', etc.) com base nessas flags.
    """
    df_block = df_multi.reset_index(drop=True)

    flag_cols = [c for c in df_block.columns if "✓" in c]
    flags = {}
    for fc in flag_cols:
        base = fc.replace("✓", "").strip()
        flags[base] = df_block[fc]

    df_show = df_block.drop(columns=flag_cols)

    def color_row(row):
        idx = row.name
        styles = []
        for col in df_show.columns:
            base = col
            if base in flags:
                flag_val = flags[base].iloc[idx]
                if flag_val == "✅":
                    styles.append("background-color: #c6efce")
                elif flag_val == "❌":
                    styles.append("background-color: #ffc7ce")
                else:
                    styles.append("")
            else:
                styles.append("")
        return styles

    styler = df_show.style.apply(color_row, axis=1).format(precision=0)
    return styler


def style_h2h_table(df_h2h: pd.DataFrame):
    """
    Remove colunas '... ✓' e pinta PTS Casa / PTS Fora com base nas flags.
    """
    df = df_h2h.copy().reset_index(drop=True)

    flag_cols = [c for c in df.columns if "✓" in c]
    if len(flag_cols) != 2:
        num_cols = df.select_dtypes(include="number").columns
        return df.style.format(precision=0, subset=num_cols)

    home_flag_col, away_flag_col = flag_cols
    pts_home_col = "PTS Casa"
    pts_away_col = "PTS Fora"

    flags_home = df[home_flag_col]
    flags_away = df[away_flag_col]

    df_show = df.drop(columns=flag_cols)

    def color_row(row):
        idx = row.name
        styles = []
        for col in df_show.columns:
            if col == pts_home_col:
                flag = str(flags_home.iloc[idx]).strip()
                if flag == "✅":
                    styles.append("background-color: #c6efce")
                elif flag == "❌":
                    styles.append("background-color: #ffc7ce")
                else:
                    styles.append("")
            elif col == pts_away_col:
                flag = str(flags_away.iloc[idx]).strip()
                if flag == "✅":
                    styles.append("background-color: #c6efce")
                elif flag == "❌":
                    styles.append("background-color: #ffc7ce")
                else:
                    styles.append("")
            else:
                styles.append("")
        return styles

    num_cols = df_show.select_dtypes(include="number").columns

    styler = (
        df_show.style
        .apply(color_row, axis=1)
        .format(precision=0, subset=num_cols)
    )
    return styler


# ---------------------------------------------------------
# Configuração da página
# ---------------------------------------------------------
st.set_page_config(
    page_title="BBall Scorer Estatísticas NBA",
    layout="wide",
)

col_logo, col_title = st.columns([0.4, 6])

with col_logo:
    st.image("bball_logo.png", width=140)

with col_title:
    st.title("BBall Scorer")

st.markdown(
    "Ferramenta para analisar **equipas e jogadores da NBA** com base em estatísticas diversas. "
    "Teste gratuitamente por tempo limitado\n\n"
)

# ------------------- TABS PRINCIPAIS ------------------- #
tab_teams, tab_player = st.tabs(["🏀 Analisar equipas", "📋 Analisar jogador"])


# =================== TAB 1: ANÁLISE DE EQUIPAS =================== #
with tab_teams:
    st.subheader("🏀 Análise de equipas")

    st.markdown(
        "Compare estatísticas da **equipa da casa** vs **equipa de fora** "
        "com base nos últimos jogos e confrontos diretos (H2H). "
        "Podes escrever a abreviatura (BOS, LAL), o nome completo (Boston Celtics) ou o nickname (Celtics, Lakers)."
    )

    col_home, col_away, col_season = st.columns(3)
    with col_home:
        home_abbr = st.text_input(
            "Equipa da casa (nome ou abreviatura)", value="BOS"
        ).strip()
    with col_away:
        away_abbr = st.text_input(
            "Equipa de fora (nome ou abreviatura)", value="LAL"
        ).strip()
    with col_season:
        season_team = st.number_input(
            "Época (ano inicial, ex.: 2025 para 2025-26)",
            min_value=2000,
            max_value=2100,
            value=2025,
            step=1,
        )

    col_g1, col_g2, col_g3 = st.columns(3)
    with col_g1:
        last_n_general = st.slider("Últimos jogos (geral)", 5, 30, 10)
    with col_g2:
        last_n_home_away = st.slider("Últimos jogos casa/fora", 3, 20, 8)
    with col_g3:
        last_n_h2h = st.slider("Últimos jogos H2H", 2, 10, 6)

    mostrar_h2h = st.checkbox(
        "Mostrar confrontos diretos (H2H)",
        value=True,
        help="Desmarca os confrontos diretos caso não pretendas visualizar os mesmos.",
    )

    if st.button("📊 Gerar análise de equipas"):
        if not home_abbr or not away_abbr:
            st.error("Preenche as duas equipas (casa e fora).")
        else:
            with st.spinner("A carregar dados das equipas..."):
                df_teams = build_team_matchup_report(
                    home_abbr=home_abbr,
                    away_abbr=away_abbr,
                    season=season_team,
                    last_n_general=last_n_general,
                    last_n_home_away=last_n_home_away,
                    last_n_h2h=last_n_h2h,
                )

            if df_teams is None or df_teams.empty:
                st.error(
                    "Não foi possível obter dados para estas equipas/época. "
                    "Verifica se os nomes/abreviaturas estão corretos e se a época já tem jogos."
                )
            else:
                st.success(f"Comparação gerada para {home_abbr} vs {away_abbr}.")

                # ---- Nomes completos das equipas (para dashboard + PDF) ----
                home_full = (
                    df_teams.attrs.get("home_team_full_name")
                    or TEAM_ABBR_TO_NAME.get(home_abbr.upper(), home_abbr)
                )
                away_full = (
                    df_teams.attrs.get("away_team_full_name")
                    or TEAM_ABBR_TO_NAME.get(away_abbr.upper(), away_abbr)
                )

                # renomear colunas BOS -> Boston Celtics, LAL -> Los Angeles Lakers
                rename_cols = {}
                for short, full in [(home_abbr, home_full), (away_abbr, away_full)]:
                    for suffix in ["", " ✓"]:
                        old = f"{short}{suffix}"
                        new = f"{full}{suffix}"
                        if old in df_teams.columns:
                            rename_cols[old] = new

                df_teams = df_teams.rename(columns=rename_cols)

                home_col = home_full
                away_col = away_full

                st.markdown(
                    "As células em **verde** indicam vantagem nessa métrica; "
                    "as em **vermelho**, desvantagem. "
                    "Em **Turnovers por jogo** e **Pontos concedidos por jogo**, menos é melhor."
                )

                # separar em blocos: Geral e Casa/Fora
                mask_geral = df_teams["Métrica"].str.startswith("Geral -")
                mask_casafora = df_teams["Métrica"].str.startswith("Casa/Fora -")

                df_geral = df_teams[mask_geral]
                df_casafora = df_teams[mask_casafora]

                if not df_geral.empty:
                    st.markdown("#### Forma geral (últimos jogos)")
                    styled_geral = style_team_block(df_geral, home_col, away_col)
                    st.table(styled_geral)

                if not df_casafora.empty:
                    st.markdown("#### Casa vs Fora (últimos jogos em casa/fora)")
                    styled_casa = style_team_block(df_casafora, home_col, away_col)
                    st.table(styled_casa)

                # ---------- CSV ----------
                csv_teams = df_teams.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="💾 Descarregar tabela em CSV",
                    data=csv_teams,
                    file_name=f"teams_{home_abbr.replace(' ', '_')}_vs_{away_abbr.replace(' ', '_')}.csv",
                    mime="text/csv",
                )

                # ---------- Excel ----------
                excel_buffer_teams = io.BytesIO()
                with pd.ExcelWriter(excel_buffer_teams, engine="xlsxwriter") as writer:
                    df_teams.to_excel(writer, index=False, sheet_name="Comparação")

                excel_buffer_teams.seek(0)

                st.download_button(
                    label="📊 Descarregar tabela em Excel",
                    data=excel_buffer_teams,
                    file_name=f"teams_{home_abbr.replace(' ', '_')}_vs_{away_abbr.replace(' ', '_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

                # ---------- TABELA H2H DETALHADA ----------
                h2h_table = None

                if mostrar_h2h:
                    h2h_table = build_team_h2h_table(
                        home_abbr=home_abbr,
                        away_abbr=away_abbr,
                        start_season=season_team,
                        last_n_h2h=last_n_h2h,
                        max_seasons_back=3,  # menos épocas para ficar mais rápido
                    )

                    if h2h_table is not None and not h2h_table.empty:
                        h2h_count = h2h_table.attrs.get("h2h_count", len(h2h_table))
                        h2h_avg_total = h2h_table.attrs.get(
                            "h2h_avg_total_points",
                            float(h2h_table["Total pontos"].mean()),
                        )

                        st.markdown("---")
                        st.markdown(f"#### Últimos {h2h_count} confrontos diretos (H2H)")
                        st.markdown(
                            f"Média de **total de pontos** nesses jogos: **{h2h_avg_total:.1f}**."
                        )

                        team_name_map = {home_abbr: home_full, away_abbr: away_full}
                        h2h_display = h2h_table.replace(team_name_map)

                        styled_h2h = style_h2h_table(h2h_display)
                        st.table(styled_h2h)

                        # ---------- CSV ----------
                        csv_h2h = h2h_display.to_csv(index=False).encode("utf-8-sig")
                        st.download_button(
                            label="💾 Descarregar H2H em CSV",
                            data=csv_h2h,
                            file_name=f"h2h_{home_abbr.replace(' ', '_')}_vs_{away_abbr.replace(' ', '_')}.csv",
                            mime="text/csv",
                        )

                        # ---------- Excel ----------
                        excel_buffer_h2h = io.BytesIO()
                        with pd.ExcelWriter(excel_buffer_h2h, engine="xlsxwriter") as writer:
                            h2h_display.to_excel(writer, index=False, sheet_name="H2H")

                        excel_buffer_h2h.seek(0)

                        st.download_button(
                            label="📊 Descarregar H2H em Excel",
                            data=excel_buffer_h2h,
                            file_name=f"h2h_{home_abbr.replace(' ', '_')}_vs_{away_abbr.replace(' ', '_')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )

                    else:
                        st.info(
                            "Não foram encontrados confrontos diretos recentes entre estas equipas nas últimas épocas."
                        )

                # ---------- BOTÃO PDF (Relatório de equipas) ----------
                pdf_buffer_teams = io.BytesIO()

                doc_teams = SimpleDocTemplate(
                    pdf_buffer_teams,
                    pagesize=A4,
                    leftMargin=20,
                    rightMargin=20,
                    topMargin=90,
                    bottomMargin=20,
                )

                elements_teams = []
                styles = getSampleStyleSheet()

                title_text = f"Relatório de equipas - {home_full} vs {away_full}"
                title = Paragraph(title_text, styles["Title"])

                season_str = f"{season_team}-{str(season_team + 1)[-2:]}"
                subtitle_text = (
                    f"Época: {season_str} | "
                    f"Últimos {last_n_general} jogos (geral) | "
                    f"Últimos {last_n_home_away} jogos (casa/fora) | "
                    f"Últimos {last_n_h2h} jogos H2H"
                )
                subtitle = Paragraph(subtitle_text, styles["Normal"])

                elements_teams.append(title)
                elements_teams.append(Spacer(1, 8))
                elements_teams.append(subtitle)
                elements_teams.append(Spacer(1, 12))

                elements_teams.append(
                    Paragraph(
                        "Comparação estatística das equipas", styles["Heading3"]
                    )
                )

                home_flag_col = f"{home_col} ✓"
                away_flag_col = f"{away_col} ✓"

                mask_geral = df_teams["Métrica"].str.startswith("Geral -")
                mask_casafora = df_teams["Métrica"].str.startswith("Casa/Fora -")

                df_geral_raw = df_teams[mask_geral]
                df_casafora_raw = df_teams[mask_casafora]

                green_color = colors.HexColor("#c6efce")
                red_color = colors.HexColor("#ffc7ce")

                def build_team_block_table(df_block_raw, titulo):
                    if df_block_raw is None or df_block_raw.empty:
                        return

                    elements_teams.append(Paragraph(titulo, styles["Heading3"]))
                    elements_teams.append(Spacer(1, 6))

                    df_block_raw = _strip_prefix_metric(df_block_raw)

                    flags_block = df_block_raw[[home_flag_col, away_flag_col]].reset_index(drop=True)

                    df_block = df_block_raw.drop(columns=[home_flag_col, away_flag_col]).copy()
                    num_cols_block = df_block.select_dtypes(include="number").columns
                    df_block[num_cols_block] = df_block[num_cols_block].round(1)
                    df_block = df_block.astype(str)

                    headers = list(df_block.columns)
                    table_data = [headers] + df_block.values.tolist()
                    table = Table(table_data, repeatRows=1)

                    style_cmds = [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 0), (-1, -1), 7),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ]

                    home_idx = df_block.columns.get_loc(home_col)
                    away_idx = df_block.columns.get_loc(away_col)

                    for row_idx in range(1, len(table_data)):
                        flag_home = str(flags_block.loc[row_idx - 1, home_flag_col]).strip()
                        flag_away = str(flags_block.loc[row_idx - 1, away_flag_col]).strip()

                        if flag_home == "✅":
                            style_cmds.append(
                                ("BACKGROUND", (home_idx, row_idx), (home_idx, row_idx), green_color)
                            )
                        elif flag_home == "❌":
                            style_cmds.append(
                                ("BACKGROUND", (home_idx, row_idx), (home_idx, row_idx), red_color)
                            )

                        if flag_away == "✅":
                            style_cmds.append(
                                ("BACKGROUND", (away_idx, row_idx), (away_idx, row_idx), green_color)
                            )
                        elif flag_away == "❌":
                            style_cmds.append(
                                ("BACKGROUND", (away_idx, row_idx), (away_idx, row_idx), red_color)
                            )

                    table.setStyle(TableStyle(style_cmds))
                    elements_teams.append(table)
                    elements_teams.append(Spacer(1, 10))

                build_team_block_table(df_geral_raw, "Forma geral (últimos jogos)")
                build_team_block_table(
                    df_casafora_raw, "Casa vs Fora (últimos jogos em casa/fora)"
                )

                # ------- H2H no PDF (se existir e se foi calculado) -------
                if mostrar_h2h and h2h_table is not None and not h2h_table.empty:
                    elements_teams.append(PageBreak())
                    elements_teams.append(Spacer(1, 30))

                    h2h_count = h2h_table.attrs.get("h2h_count", len(h2h_table))
                    h2h_avg_total = h2h_table.attrs.get(
                        "h2h_avg_total_points",
                        float(h2h_table["Total pontos"].mean()),
                    )

                    elements_teams.append(
                        Paragraph(
                            f"Últimos {h2h_count} confrontos diretos (H2H)",
                            styles["Heading3"],
                        )
                    )
                    elements_teams.append(
                        Paragraph(
                            f"Média de total de pontos: {h2h_avg_total:.1f}",
                            styles["Normal"],
                        )
                    )
                    elements_teams.append(Spacer(1, 6))

                    team_name_map = {home_abbr: home_full, away_abbr: away_full}
                    df_h2h_raw = h2h_table.replace(team_name_map).reset_index(drop=True)

                    flag_cols = [c for c in df_h2h_raw.columns if "✓" in c]
                    if len(flag_cols) == 2:
                        home_flag_col_h2h, away_flag_col_h2h = flag_cols
                        flags_home = df_h2h_raw[home_flag_col_h2h]
                        flags_away = df_h2h_raw[away_flag_col_h2h]
                        df_h2h = df_h2h_raw.drop(columns=flag_cols)
                    else:
                        flags_home = flags_away = None
                        df_h2h = df_h2h_raw

                    num_cols_h2h = df_h2h.select_dtypes(include="number").columns
                    df_h2h[num_cols_h2h] = df_h2h[num_cols_h2h].round(0)
                    df_h2h = df_h2h.astype(str)

                    headers_h2h = list(df_h2h.columns)
                    table_data_h2h = [headers_h2h] + df_h2h.values.tolist()
                    table_h2h = Table(table_data_h2h, repeatRows=1)

                    style_cmds_h2h = [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 0), (-1, -1), 7),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ]

                    green_color = colors.HexColor("#c6efce")
                    red_color = colors.HexColor("#ffc7ce")

                    try:
                        pts_home_idx = df_h2h.columns.get_loc("PTS Casa")
                        pts_away_idx = df_h2h.columns.get_loc("PTS Fora")
                    except KeyError:
                        pts_home_idx = pts_away_idx = None

                    if pts_home_idx is not None and flags_home is not None:
                        for row_idx in range(1, len(table_data_h2h)):
                            flag_h = str(flags_home.iloc[row_idx - 1]).strip()
                            flag_a = str(flags_away.iloc[row_idx - 1]).strip()

                            if flag_h == "✅":
                                style_cmds_h2h.append(
                                    ("BACKGROUND", (pts_home_idx, row_idx), (pts_home_idx, row_idx), green_color)
                                )
                            elif flag_h == "❌":
                                style_cmds_h2h.append(
                                    ("BACKGROUND", (pts_home_idx, row_idx), (pts_home_idx, row_idx), red_color)
                                )

                            if flag_a == "✅":
                                style_cmds_h2h.append(
                                    ("BACKGROUND", (pts_away_idx, row_idx), (pts_away_idx, row_idx), green_color)
                                )
                            elif flag_a == "❌":
                                style_cmds_h2h.append(
                                    ("BACKGROUND", (pts_away_idx, row_idx), (pts_away_idx, row_idx), red_color)
                                )

                    table_h2h.setStyle(TableStyle(style_cmds_h2h))
                    elements_teams.append(table_h2h)

                def header_footer_teams(canvas, doc):
                    draw_header_footer(
                        canvas,
                        doc,
                        title_text=f"Relatório de Equipas – {home_full} vs {away_full}",
                    )

                doc_teams.build(
                    elements_teams,
                    onFirstPage=header_footer_teams,
                    onLaterPages=header_footer_teams,
                )
                pdf_buffer_teams.seek(0)

                st.download_button(
                    label="📄 Descarregar relatório de equipas em PDF",
                    data=pdf_buffer_teams,
                    file_name=f"teams_{home_abbr.replace(' ', '_')}_vs_{away_abbr.replace(' ', '_')}.pdf",
                    mime="application/pdf",
                )


# =================== TAB 2: ANÁLISE DE JOGADOR =================== #
with tab_player:
    st.subheader("📋 Analisar jogador")

    st.write(
        "Escolhe um jogador, época e estatísticas para veres jogo a jogo se "
        "ele bateu ou não as linhas nos últimos N jogos (jogo inteiro ou por período)."
    )

    colA, colB = st.columns([2, 1])

    with colA:
        player_name = st.text_input(
            "Nome do jogador (ex.: 'Jayson Tatum', 'LeBron James')", value=""
        )

    with colB:
        season_player = st.number_input(
            "Época (ex.: 2025)",
            min_value=2000,
            max_value=2100,
            value=2025,
            step=1,
        )

    stat_label_map = {
        "Pontos (PTS)": "pts",
        "Ressaltos (REB)": "reb",
        "Assistências (AST)": "ast",
        "Triplos convertidos (FG3M)": "fg3m",
        "Roubos de Bola (STL)": "stl",
        "Desarmes de Lançamento (BLK)": "blk",
        "Pontos + Ressaltos + Assistências (PRA)": "pra",
        "Ressaltos + Assistências (RA)": "ra",
        "Pontos + Ressaltos (P+R)": "pr",
        "Pontos + Assistências (P+A)": "pa",
        "Roubos + Desarmes (S+B)": "sb",
        "Pontos + Desarmes (P+B)": "pb",
        "Duplo-Duplo (DD)": "dd",
        "Triplo-Duplo (TD)": "td",
    }

    period_label_map = {
        "Jogo inteiro": None,
        "1.º período": 1,
        "2.º período": 2,
        "3.º período": 3,
        "4.º período": 4,
    }

    period_label = st.selectbox(
        "Tipo de mercado (período):",
        list(period_label_map.keys()),
        index=0,
    )
    period_value = period_label_map[period_label]

    st.markdown("### 🎯 Selecionar estatísticas")

    colC, colD = st.columns([2, 1])

    with colC:
        stats_escolhidas = st.multiselect(
            "Selecionar estatísticas",
            list(stat_label_map.keys()),
            default=["Pontos (PTS)", "Ressaltos (REB)"],
            key="multi_stats_select",
        )

    with colD:
        last_n_multi = st.slider(
            "Nº de últimos jogos a ver",
            min_value=3,
            max_value=20,
            value=10,
            key="last_n_multi",
        )

    stats_lines: dict[str, float] = {}

    if stats_escolhidas:
        st.markdown("#### Linhas por estatística")
        cols = st.columns(len(stats_escolhidas))

        for i, label in enumerate(stats_escolhidas):
            sf = stat_label_map[label]

            if sf == "pts":
                default_line = 26.0
            elif sf == "reb":
                default_line = 7.5
            elif sf == "ast":
                default_line = 5.5
            elif sf == "fg3m":
                default_line = 2.5
            elif sf == "pra":
                default_line = 32.5
            elif sf == "ra":
                default_line = 11.5
            elif sf in ("stl", "blk"):
                default_line = 1.5
            elif sf == "pr":
                default_line = 24.5
            elif sf == "pa":
                default_line = 21.5
            elif sf == "sb":
                default_line = 1.5
            elif sf == "pb":
                default_line = 18.5
            elif sf in ("dd", "td"):
                default_line = 0.5
            else:
                default_line = 1.0

            with cols[i]:
                linha = st.number_input(
                    f"Linha {label}",
                    value=default_line,
                    step=0.5,
                    key=f"multi_line_{sf}",
                )

                if sf in ("dd", "td"):
                    st.caption("Colocar 1 (ou 0,5) para saber número de acertos")

                stats_lines[sf] = linha

    run_multi = st.button("📊 Gerar relatório", key="btn_multi_player")

    if run_multi:
        if not player_name.strip():
            st.warning("Escreve o nome do jogador primeiro.")
        elif not stats_lines:
            st.warning("Escolhe pelo menos uma estatística.")
        else:
            with st.spinner("A carregar dados do jogador..."):
                df_multi = build_player_multi_stats_report(
                    player_name=player_name.strip(),
                    season=season_player,
                    stats_lines=stats_lines,
                    last_n=last_n_multi,
                    period=period_value,
                )

            if df_multi is None or df_multi.empty:
                st.error("Não foi possível obter dados para esse jogador/época.")
            else:
                # --- Converter abreviaturas para nomes completos (equipa e adversário) ---
                for col in ["Equipa", "Adversário"]:
                    if col in df_multi.columns:
                        df_multi[col] = df_multi[col].apply(
                            lambda x: TEAM_ABBR_TO_NAME.get(str(x).upper(), x)
                        )

                full_name = df_multi.attrs.get("player_full_name", player_name)
                stats_summary = df_multi.attrs.get("stats_summary", {})
                avg_minutes = df_multi.attrs.get("avg_minutes", 0.0)
                period_attr = df_multi.attrs.get("period", None)

                if period_attr is None:
                    period_desc = "Jogo inteiro"
                    period_suffix = ""
                else:
                    period_desc = f"{period_attr}.º período"
                    period_suffix = f" no {period_attr}.º período"

                st.markdown(f"### {full_name}")
                st.markdown(f"- Jogos analisados: **{len(df_multi)}**")
                st.markdown(
                    f"- Minutos médios (últimos {last_n_multi} jogos): **{avg_minutes:.1f} min**"
                )
                st.markdown(f"- Período analisado: **{period_desc}**")

                st.markdown("#### Resumo por mercado")
                linhas_resumo = []
                for sf, cfg in stats_summary.items():
                    nome = [k for k, v in stat_label_map.items() if v == sf][0]
                    linha = cfg["line"]
                    hits = cfg["hits"]
                    total = cfg["total"]
                    hit_rate = cfg["hit_rate"]
                    linhas_resumo.append(
                        f"- **{nome} {linha}+{period_suffix}** → {hits}/{total} "
                        f"({hit_rate:.1f}%)"
                    )
                st.markdown("\n".join(linhas_resumo))

                st.markdown(
                    "As células em **verde** indicam jogos em que o jogador "
                    "bateu a linha nessa estatística; em **vermelho**, falhou."
                )

                styled_multi = style_player_table(df_multi)
                st.table(styled_multi)

                # ---------- CSV ----------
                csv_multi = df_multi.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="💾 Descarregar relatório em CSV",
                    data=csv_multi,
                    file_name=f"report_{full_name.replace(' ', '_')}_multi.csv",
                    mime="text/csv",
                )

                # ---------- Excel ----------
                excel_buffer_multi = io.BytesIO()
                with pd.ExcelWriter(excel_buffer_multi, engine="xlsxwriter") as writer:
                    df_multi.to_excel(writer, index=False, sheet_name="Jogador")

                excel_buffer_multi.seek(0)

                st.download_button(
                    label="📊 Descarregar relatório em Excel",
                    data=excel_buffer_multi,
                    file_name=f"report_{full_name.replace(' ', '_')}_multi.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

                # ---------- PDF jogador ----------
                pdf_buffer = io.BytesIO()

                doc = SimpleDocTemplate(
                    pdf_buffer,
                    pagesize=landscape(A4),
                    leftMargin=20,
                    rightMargin=20,
                    topMargin=90,
                    bottomMargin=20,
                )

                elements = []
                styles = getSampleStyleSheet()

                title_style = ParagraphStyle(
                    name="TitleBig",
                    fontName="Helvetica-Bold",
                    fontSize=20,
                    leading=26,
                    alignment=1,
                )

                title = Paragraph(
                    f"Relatório de Jogador – {full_name}", title_style
                )

                if period_attr is None:
                    period_text_pdf = "Período analisado: Jogo inteiro"
                else:
                    period_text_pdf = f"Período analisado: {period_attr}.º período"

                subtitle_text = (
                    f"Jogos analisados: {len(df_multi)} | {period_text_pdf}"
                )
                subtitle = Paragraph(subtitle_text, styles["Normal"])

                elements.append(subtitle)
                elements.append(Spacer(1, 12))

                if stats_summary:
                    elements.append(
                        Paragraph("Resumo por mercado:", styles["Heading3"])
                    )
                    resumo_linhas_pdf = []
                    for sf, cfg in stats_summary.items():
                        nome = [
                            k for k, v in stat_label_map.items() if v == sf
                        ][0]
                        linha = cfg["line"]
                        hits = cfg["hits"]
                        total = cfg["total"]
                        hit_rate = cfg["hit_rate"]
                        resumo_linhas_pdf.append(
                            f"{nome} {linha}+{period_suffix} → {hits}/{total} ({hit_rate:.1f}%)"
                        )

                    resumo_html = "<br/>".join(resumo_linhas_pdf)
                    elements.append(Paragraph(resumo_html, styles["Normal"]))
                    elements.append(Spacer(1, 12))

                df_pdf_raw = df_multi.copy()
                flag_cols = [c for c in df_pdf_raw.columns if "✓" in c]
                flags_pdf = {}
                for fc in flag_cols:
                    base = fc.replace("✓", "").strip()
                    flags_pdf[base] = df_pdf_raw[fc].reset_index(drop=True)

                df_pdf = (
                    df_pdf_raw.drop(columns=flag_cols)
                    .copy()
                    .round(1)
                    .astype(str)
                )

                headers = list(df_pdf.columns)
                table_data = [headers] + df_pdf.values.tolist()
                table = Table(table_data, repeatRows=1)

                style_cmds = [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ]

                green_color = colors.HexColor("#c6efce")
                red_color = colors.HexColor("#ffc7ce")

                value_col_idx = {
                    col: df_pdf.columns.get_loc(col) for col in df_pdf.columns
                }

                for row_idx in range(1, len(table_data)):
                    flag_row = row_idx - 1
                    for base, series_flags in flags_pdf.items():
                        if base not in value_col_idx:
                            continue
                        flag_val = str(series_flags.iloc[flag_row])
                        col_idx = value_col_idx[base]

                        if flag_val == "✅":
                            style_cmds.append(
                                (
                                    "BACKGROUND",
                                    (col_idx, row_idx),
                                    (col_idx, row_idx),
                                    green_color,
                                )
                            )
                        elif flag_val == "❌":
                            style_cmds.append(
                                (
                                    "BACKGROUND",
                                    (col_idx, row_idx),
                                    (col_idx, row_idx),
                                    red_color,
                                )
                            )

                table.setStyle(TableStyle(style_cmds))
                elements.append(table)

                def header_footer_player(canvas, doc):
                    draw_header_footer(
                        canvas,
                        doc,
                        title_text=f"Relatório de Jogador – {full_name}",
                    )

                doc.build(
                    elements,
                    onFirstPage=header_footer_player,
                    onLaterPages=header_footer_player,
                )
                pdf_buffer.seek(0)

                st.download_button(
                    label="📄 Descarregar relatório em PDF",
                    data=pdf_buffer,
                    file_name=f"report_{full_name.replace(' ', '_')}_multi.pdf",
                    mime="application/pdf",
                )







