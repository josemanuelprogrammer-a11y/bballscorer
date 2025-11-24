import streamlit as st

from nba_core import (
    build_player_multi_stats_report,
    build_team_matchup_report,
    build_team_h2h_table,
)

st.set_page_config(
    page_title="BBall Scorer",
    layout="wide"
)

# IMPORTS DO PDF
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
import io


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
    # Logo à esquerda
    try:
        logo_w = 2.0 * cm
        logo_h = 2.0 * cm
        canvas.drawImage(
            LOGO_PATH,
            20,                     # X
            height - logo_h - 20,   # Y
            width=logo_w,
            height=logo_h,
            preserveAspectRatio=True,
            mask="auto",
        )
    except Exception:
        pass  # Se o logo falhar, continua

    # Título principal (programa)
    canvas.setFont("Helvetica", 12)
    canvas.drawCentredString(
        width / 2,
        height - 28,       # ↓ antes era -20
        "BBall Scorer – estatísticas NBA | www.bballscorer.com"
    )

    canvas.setFont("Helvetica-Bold", 13)  # antes era 10 e sem bold
    canvas.drawCentredString(
        width / 2,
        height - 50,
        title_text
    )


    # Linha fina de separação
    canvas.setLineWidth(0.3)
    canvas.line(
        width * 0.15,         # início mais à direita
        height - 58,
        width * 0.85,         # fim mais cedo
        height - 58
    )


    # ---------- RODAPÉ ----------
    from datetime import datetime
    canvas.setFont("Helvetica", 8)

    # Página
    canvas.drawRightString(width - 20, 18, f"Página {doc.page}")

    # Data/hora
    canvas.drawString(20, 18, "Gerado em: " + datetime.now().strftime("%d/%m/%Y %H:%M"))

    canvas.restoreState()

st.set_page_config(
    page_title="NBA - Estatísticas",
    layout="wide"
)

col_logo, col_title = st.columns([0.4, 6])

with col_logo:
    # usa o caminho do logo no container
    st.image("bball_logo.png", width=90)

with col_title:
    st.title("Estatísticas NBA")

st.markdown(
    "Ferramenta para analisar **equipas e jogadores da NBA** com base em estatísticas de "
    "pontos, ressaltos, assistências, triplos convertidos, roubos de bola, desarmes de lançamento, etc.\n\n"
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
            "Equipa da casa (nome ou abreviatura)",
            value="BOS"
        ).strip()
    with col_away:
        away_abbr = st.text_input(
            "Equipa de fora (nome ou abreviatura)",
            value="LAL"
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

                st.markdown(
                    "Ao lado de cada equipa existe uma coluna de **Green**:\n"
                    "- **✅** significa que essa equipa está melhor nessa métrica;\n"
                    "- **❌** significa que está pior;\n"
                    "- Em métricas de ataque (PTS, FG%, 3PT%, REB, AST) → mais alto é melhor;\n"
                    "- Em **Turnovers por jogo** → mais baixo é melhor."
                )

                st.dataframe(df_teams, use_container_width=True)

                # botão para descarregar CSV
                csv_teams = df_teams.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="💾 Descarregar tabela em CSV",
                    data=csv_teams,
                    file_name=f"teams_{home_abbr.replace(' ', '_')}_vs_{away_abbr.replace(' ', '_')}.csv",
                    mime="text/csv",
                )

                # ---------- TABELA H2H DETALHADA ----------
                h2h_table = build_team_h2h_table(
                    home_abbr=home_abbr,
                    away_abbr=away_abbr,
                    start_season=season_team,
                    last_n_h2h=last_n_h2h,
                    max_seasons_back=5,
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

                    st.dataframe(h2h_table, use_container_width=True)

                    csv_h2h = h2h_table.to_csv(index=False).encode("utf-8-sig")
                    st.download_button(
                        label="💾 Descarregar H2H em CSV",
                        data=csv_h2h,
                        file_name=f"h2h_{home_abbr.replace(' ', '_')}_vs_{away_abbr.replace(' ', '_')}.csv",
                        mime="text/csv",
                    )
                else:
                    st.info(
                        "Não foram encontrados confrontos diretos recentes entre estas equipas nas últimas épocas."
                    )


                # ---------- BOTÃO PDF (Relatório completo de equipas) ----------
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

                # Título
                title_text = f"Relatório de equipas - {home_abbr} vs {away_abbr}"
                title = Paragraph(title_text, styles["Title"])

                # Subtítulo com parâmetros usados
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

                # -------- Tabela 1: comparação geral / casa-fora --------
                elements_teams.append(
                    Paragraph("Comparação estatística das equipas", styles["Heading3"])
                )
                elements_teams.append(Spacer(1, 6))

                df_pdf_teams = df_teams.copy().astype(str)

                # trocar símbolos nas colunas com ✓
                for col in df_pdf_teams.columns:
                    if "✓" in col:
                        df_pdf_teams[col] = df_pdf_teams[col].replace(
                            {"✅": "✔", "❌": "✘", "🟩": "✔", "🟥": "✘"}
                        )

                # cabeçalho: esconde texto nas colunas ✓
                headers_teams = []
                for col in df_pdf_teams.columns:
                    if "✓" in col:
                        headers_teams.append("")
                    else:
                        headers_teams.append(col)

                table_data_teams = [headers_teams] + df_pdf_teams.values.tolist()
                table_teams = Table(table_data_teams, repeatRows=1)

                style_cmds_teams = [
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

                # pintar células das colunas ✓
                for row_idx in range(1, len(table_data_teams)):  # ignora header
                    for col_idx, col_name in enumerate(df_pdf_teams.columns):
                        if "✓" not in col_name:
                            continue

                        cell_value = str(table_data_teams[row_idx][col_idx]).strip()
                        if cell_value == "✔":
                            style_cmds_teams.append(
                                ("BACKGROUND", (col_idx, row_idx), (col_idx, row_idx), green_color)
                            )
                            style_cmds_teams.append(
                                ("TEXTCOLOR", (col_idx, row_idx), (col_idx, row_idx), colors.black)
                            )
                        elif cell_value == "✘":
                            style_cmds_teams.append(
                                ("BACKGROUND", (col_idx, row_idx), (col_idx, row_idx), red_color)
                            )
                            style_cmds_teams.append(
                                ("TEXTCOLOR", (col_idx, row_idx), (col_idx, row_idx), colors.black)
                            )

                table_teams.setStyle(TableStyle(style_cmds_teams))
                elements_teams.append(table_teams)

                # -------- Tabela 2: H2H, se existir --------
                if h2h_table is not None and not h2h_table.empty:
                    elements_teams.append(Spacer(1, 16))
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

                    df_pdf_h2h = h2h_table.copy().astype(str)
                    for col in df_pdf_h2h.columns:
                        if "✓" in col:
                            df_pdf_h2h[col] = df_pdf_h2h[col].replace(
                                {"✅": "✔", "❌": "✘"}
                            )

                    headers_h2h = []
                    for col in df_pdf_h2h.columns:
                        if "✓" in col:
                            headers_h2h.append("")
                        else:
                            headers_h2h.append(col)

                    table_data_h2h = [headers_h2h] + df_pdf_h2h.values.tolist()
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

                    for row_idx in range(1, len(table_data_h2h)):
                        for col_idx, col_name in enumerate(df_pdf_h2h.columns):
                            if "✓" not in col_name:
                                continue
                            cell_value = str(table_data_h2h[row_idx][col_idx]).strip()
                            if cell_value == "✔":
                                style_cmds_h2h.append(
                                    ("BACKGROUND", (col_idx, row_idx), (col_idx, row_idx), green_color)
                                )
                            elif cell_value == "✘":
                                style_cmds_h2h.append(
                                    ("BACKGROUND", (col_idx, row_idx), (col_idx, row_idx), red_color)
                                )

                    table_h2h.setStyle(TableStyle(style_cmds_h2h))
                    elements_teams.append(table_h2h)

                # Função de cabeçalho/rodapé específica para este relatório (equipas)
                def header_footer_teams(canvas, doc):
                    draw_header_footer(
                        canvas,
                        doc,
                        title_text=f"Relatório de Equipas – {home_abbr} vs {away_abbr}",
                    )

                # gerar o PDF com cabeçalho + rodapé
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
            "Nome do jogador (ex.: 'Jayson Tatum', 'LeBron James')",
            value=""
        )

    with colB:
        season_player = st.number_input(
            "Época (ex.: 2025)",
            min_value=2000,
            max_value=2100,
            value=2025,
            step=1
        )

    # Mapa de labels -> códigos internos
    stat_label_map = {
        "Pontos (PTS)": "pts",
        "Ressaltos (REB)": "reb",
        "Assistências (AST)": "ast",
        "Triplos convertidos (FG3M)": "fg3m",
        "Roubos de Bola (STL)": "stl",
        "Desarmes de Lançamento (BLK)": "blk",

        "Pontos + Ressaltos + Assistências (PRA)": "pra",
        "Ressaltos + Assistências (RA)": "ra",

        # NOVOS MERCADOS
        "Pontos + Ressaltos (P+R)": "pr",
        "Pontos + Assistências (P+A)": "pa",
        "Roubos + Desarmes (S+B)": "sb",
        "Pontos + Desarmes (P+B)": "pb",
        "Duplo-Duplo (DD)": "dd",
        "Triplo-Duplo (TD)": "td",
    }

    # --- Tipo de mercado: jogo inteiro ou período ---
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

    # ------ SELECIONAR ESTATÍSTICAS ------ #
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

    # --- Dicionário de linhas escolhidas ---
    stats_lines: dict[str, float] = {}

    if stats_escolhidas:
        st.markdown("#### Linhas por estatística")
        cols = st.columns(len(stats_escolhidas))

        for i, label in enumerate(stats_escolhidas):
            sf = stat_label_map[label]

            # defaults por tipo de mercado
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
            elif sf == "pr":   # Pontos + Ressaltos
                default_line = 24.5
            elif sf == "pa":   # Pontos + Assistências
                default_line = 21.5
            elif sf == "sb":   # Roubos + Desarmes
                default_line = 1.5
            elif sf == "pb":   # Pontos + Desarmes
                default_line = 18.5
            elif sf in ("dd", "td"):  # Duplo / Triplo Duplo (Sim/Não)
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
                full_name = df_multi.attrs.get("player_full_name", player_name)
                stats_summary = df_multi.attrs.get("stats_summary", {})
                avg_minutes = df_multi.attrs.get("avg_minutes", 0.0)
                period_attr = df_multi.attrs.get("period", None)

                # descrição do período para mostrar no texto
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

                # Resumo por mercado (no dashboard)
                st.markdown("#### Resumo por mercado")
                linhas_resumo = []
                for sf, cfg in stats_summary.items():
                    # voltar do código interno ('pts', 'reb', ...) para o label bonito
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

                st.dataframe(df_multi, use_container_width=True)

                # ---------- BOTÃO CSV ----------
                csv_multi = df_multi.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="💾 Descarregar relatório em CSV",
                    data=csv_multi,
                    file_name=f"report_{full_name.replace(' ', '_')}_multi.csv",
                    mime="text/csv",
                )

                # ---------- BOTÃO PDF (tabela igual ao dashboard) ----------
                pdf_buffer = io.BytesIO()

                # documento em A4 na horizontal (mais espaço para colunas)
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

                # Título e resumo
                title_style = ParagraphStyle(
                    name="TitleBig",
                    fontName="Helvetica-Bold",
                    fontSize=20,
                    leading=26,
                    alignment=1,  # 1 = centrado
                )

                title = Paragraph(f"Relatório de Jogador – {full_name}", title_style)

                # texto do subtítulo com jogos + período
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

                # Resumo por mercado (no PDF)
                if stats_summary:
                    elements.append(Paragraph("Resumo por mercado:", styles["Heading3"]))
                    resumo_linhas_pdf = []
                    for sf, cfg in stats_summary.items():
                        nome = [k for k, v in stat_label_map.items() if v == sf][0]
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

                # -------- Tabela com os mesmos dados do df_multi --------
                # criar cópia só para o PDF (para trocar os símbolos)
                df_pdf = df_multi.copy().astype(str)

                # trocar símbolos nas colunas "Green" para ✔ / ✘
                for col in df_pdf.columns:
                    if "✓" in col:
                        df_pdf[col] = df_pdf[col].replace(
                            {"✅": "✔", "❌": "✘", "🟩": "✔", "🟥": "✘"}
                        )

                # cabeçalho personalizado + linhas
                headers = []
                for col in df_pdf.columns:
                    if "✓" in col:
                        # não mostrar texto no cabeçalho das colunas de Green/Red
                        headers.append("")
                    else:
                        headers.append(col)

                table_data = [headers] + df_pdf.values.tolist()

                table = Table(table_data, repeatRows=1)

                # estilos base
                style_cmds = [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),  # header
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ]

                # cores para green / red
                green_color = colors.HexColor("#c6efce")   # verde claro
                red_color = colors.HexColor("#ffc7ce")     # vermelho claro

                # pintar células das colunas Green
                for row_idx in range(1, len(table_data)):  # ignora header
                    for col_idx, col_name in enumerate(df_pdf.columns):
                        if "✓" not in col_name:
                            continue

                        cell_value = str(table_data[row_idx][col_idx]).strip()

                        if cell_value == "✔":
                            style_cmds.append(
                                ("BACKGROUND", (col_idx, row_idx), (col_idx, row_idx), green_color)
                            )
                            style_cmds.append(
                                ("TEXTCOLOR", (col_idx, row_idx), (col_idx, row_idx), colors.black)
                            )
                        elif cell_value == "✘":
                            style_cmds.append(
                                ("BACKGROUND", (col_idx, row_idx), (col_idx, row_idx), red_color)
                            )
                            style_cmds.append(
                                ("TEXTCOLOR", (col_idx, row_idx), (col_idx, row_idx), colors.black)
                            )

                table.setStyle(TableStyle(style_cmds))

                elements.append(table)

                def header_footer_player(canvas, doc):
                    draw_header_footer(
                        canvas,
                        doc,
                        title_text=f"Relatório de Jogador – {full_name}",
                    )

                # gerar o PDF com cabeçalho + rodapé
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

