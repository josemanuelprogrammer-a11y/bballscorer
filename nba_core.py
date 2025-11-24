import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional

import pandas as pd
from nba_api.stats.static import players as players_static, teams as teams_static
from nba_api.stats.endpoints import (
    PlayerGameLog,
    TeamGameLog,
    ScoreboardV2,
    BoxScoreTraditionalV2,
    PlayByPlayV2,
)


# ----------------- HELPERS GERAIS ----------------- #

STAT_COLS = {
    "pts": "PTS",
    "reb": "REB",
    "ast": "AST",
    "fg3m": "FG3M",
    "stl": "STL",
    "blk": "BLK",
}

# métricas onde "menos é melhor" para comparação Green/Red em equipas
LOWER_BETTER_METRICS = {
    "Turnovers por jogo",
}


def season_to_str(season_year: int) -> str:
    return f"{season_year}-{str(season_year + 1)[-2:]}"


def get_next_game(team_abbr: str, season: int):
    teams = teams_static.get_teams()
    team = next((t for t in teams if t["abbreviation"] == team_abbr), None)
    if not team:
        return "Sem próximo jogo"

    team_id = team["id"]
    today = datetime.today().date()

    for i in range(0, 30):
        date_to_check = today + timedelta(days=i)
        try:
            sb = ScoreboardV2(game_date=date_to_check.strftime("%m/%d/%Y"))
            df_games = sb.game_header.get_data_frame()
        except Exception:
            continue

        if df_games.empty:
            continue

        if not {"HOME_TEAM_ID", "VISITOR_TEAM_ID", "GAME_DATE_EST"}.issubset(
            df_games.columns
        ):
            continue

        for _, game in df_games.iterrows():
            if team_id in (game["HOME_TEAM_ID"], game["VISITOR_TEAM_ID"]):
                dt_est = pd.to_datetime(game["GAME_DATE_EST"])
                if dt_est.tzinfo is None:
                    dt_est = dt_est.replace(tzinfo=ZoneInfo("US/Eastern"))
                dt_local = dt_est.astimezone(ZoneInfo("Europe/Lisbon"))
                return dt_local.date().strftime("%d/%m/%Y")

    return "Sem próximo jogo"


# ----------------- FUNÇÕES PARA ANÁLISE DE EQUIPAS ----------------- #

def find_team_by_abbr(search_text: str):
    """
    Devolve o dicionário da equipa a partir de:
    - abreviação (ex.: BOS, LAL)
    - nome completo (ex.: Boston Celtics)
    - nome parcial (ex.: Boston, Celtics)
    - nickname (ex.: Celtics, Lakers)
    Mantido o nome da função por compatibilidade.
    """
    if not search_text:
        return None

    text = search_text.strip().lower()
    teams = teams_static.get_teams()

    for t in teams:
        abbr = t["abbreviation"].lower()
        full = t["full_name"].lower()
        nickname = t["nickname"].lower()
        city = t["city"].lower()

        if (
            text == abbr
            or text == full
            or text == nickname
            or text == city
            or text in full
            or text in nickname
        ):
            return t

    return None


def get_team_last_games(team_id: int, season_year: int, last_n: int = 10) -> pd.DataFrame:
    """Últimos N jogos de uma equipa numa época (TeamGameLog)."""
    season_str = season_to_str(season_year)

    logs = TeamGameLog(
        team_id=team_id,
        season=season_str,
        season_type_all_star="Regular Season",
        timeout=30,
    )
    df = logs.get_data_frames()[0].copy()

    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
    df = df.sort_values("GAME_DATE", ascending=False).head(last_n)
    return df


def get_team_season_games(team_id: int, season_year: int) -> pd.DataFrame:
    """Todos os jogos da época (ordenados da data mais recente para a mais antiga)."""
    season_str = season_to_str(season_year)

    logs = TeamGameLog(
        team_id=team_id,
        season=season_str,
        season_type_all_star="Regular Season",
        timeout=30,
    )
    df = logs.get_data_frames()[0].copy()

    # normalizar nome da coluna do ID do jogo
    if "Game_ID" in df.columns and "GAME_ID" not in df.columns:
        df = df.rename(columns={"Game_ID": "GAME_ID"})

    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
    df = df.sort_values("GAME_DATE", ascending=False)
    return df

def get_last_h2h_games(
    home_team: dict,
    away_team: dict,
    start_season: int,
    last_n_h2h: int = 6,
    max_seasons_back: int = 5,
) -> Optional[pd.DataFrame]:
    """
    Vai buscar os últimos N jogos H2H entre duas equipas,
    começando na época start_season e recuando até max_seasons_back épocas.

    Devolve DataFrame com colunas:
    - GAME_DATE
    - HOME_TEAM (abreviação)
    - AWAY_TEAM (abreviação)
    - PTS_HOME
    - PTS_AWAY
    """

    if not home_team or not away_team:
        return None

    home_id = home_team["id"]
    away_id = away_team["id"]
    home_abbr = home_team["abbreviation"]
    away_abbr = away_team["abbreviation"]

    all_rows = []

    for season_year in range(start_season, start_season - max_seasons_back, -1):
        if season_year < 2000:
            break

        try:
            df_home = get_team_season_games(home_id, season_year)
            df_away = get_team_season_games(away_id, season_year)
        except Exception:
            continue

        if df_home.empty or df_away.empty:
            continue

        # jogos em que se defrontam nessa época
        df_home_h2h = df_home[df_home["MATCHUP"].str.contains(away_abbr)]
        df_away_h2h = df_away[df_away["MATCHUP"].str.contains(home_abbr)]

        if df_home_h2h.empty or df_away_h2h.empty:
            continue

        merged = pd.merge(
            df_home_h2h[["GAME_ID", "GAME_DATE", "PTS", "MATCHUP"]],
            df_away_h2h[["GAME_ID", "GAME_DATE", "PTS"]],
            on=["GAME_ID", "GAME_DATE"],
            suffixes=("_A", "_B"),
        )

        if merged.empty:
            continue

        for _, row in merged.iterrows():
            matchup = str(row["MATCHUP"])
            game_date = row["GAME_DATE"]
            pts_a = float(row["PTS_A"])
            pts_b = float(row["PTS_B"])

            # linha A é vista da equipa "home_team"
            if "vs" in matchup:  # ex.: BOS vs LAL  -> home_team está em casa
                home_abbr_game = home_abbr
                away_abbr_game = away_abbr
                pts_home = pts_a
                pts_away = pts_b
            elif "@" in matchup:  # ex.: BOS @ LAL -> home_team está fora
                home_abbr_game = away_abbr
                away_abbr_game = home_abbr
                pts_home = pts_b
                pts_away = pts_a
            else:
                # fallback, se o formato for estranho
                home_abbr_game = home_abbr
                away_abbr_game = away_abbr
                pts_home = pts_a
                pts_away = pts_b

            all_rows.append(
                {
                    "GAME_DATE": game_date,
                    "HOME_TEAM": home_abbr_game,
                    "AWAY_TEAM": away_abbr_game,
                    "PTS_HOME": pts_home,
                    "PTS_AWAY": pts_away,
                }
            )

    if not all_rows:
        return None

    df_all = pd.DataFrame(all_rows)
    df_all = df_all.sort_values("GAME_DATE", ascending=False).head(last_n_h2h)
    return df_all

def build_team_h2h_table(
    home_abbr: str,
    away_abbr: str,
    start_season: int,
    last_n_h2h: int = 6,
    max_seasons_back: int = 5,
) -> Optional[pd.DataFrame]:
    """
    Cria a tabela de confrontos diretos (H2H) com:

    Data | Equipa da casa | PTS Casa | Casa Green | Equipa de fora | PTS Fora | Fora Green | Total pontos
    """

    home_team = find_team_by_abbr(home_abbr)
    away_team = find_team_by_abbr(away_abbr)

    if not home_team or not away_team:
        return None

    df_h2h = get_last_h2h_games(
        home_team=home_team,
        away_team=away_team,
        start_season=start_season,
        last_n_h2h=last_n_h2h,
        max_seasons_back=max_seasons_back,
    )

    if df_h2h is None or df_h2h.empty:
        return None

    rows = []
    for _, row in df_h2h.iterrows():
        date_str = pd.to_datetime(row["GAME_DATE"]).strftime("%d/%m/%Y")
        home_team_abbr = row["HOME_TEAM"]
        away_team_abbr = row["AWAY_TEAM"]
        pts_home = float(row["PTS_HOME"])
        pts_away = float(row["PTS_AWAY"])

        if pts_home > pts_away:
            home_flag, away_flag = "✅", "❌"
        elif pts_away > pts_home:
            home_flag, away_flag = "❌", "✅"
        else:
            home_flag = away_flag = ""

        rows.append(
            {
                "Data": date_str,
                "Equipa da casa": home_team_abbr,
                "PTS Casa": pts_home,
                "Casa ✓": home_flag,
                "Equipa de fora": away_team_abbr,
                "PTS Fora": pts_away,
                "Fora ✓": away_flag,
                "Total pontos": pts_home + pts_away,
            }
        )

    df_final = pd.DataFrame(rows)
    df_final.attrs["h2h_count"] = len(df_final)
    df_final.attrs["h2h_avg_total_points"] = float(df_final["Total pontos"].mean())

    return df_final

def split_home_away(df: pd.DataFrame):
    """Separa jogos em casa (vs) e fora (@) com base no campo MATCHUP."""
    if df.empty:
        return df, df

    df_home = df[df["MATCHUP"].str.contains(" vs")]
    df_away = df[df["MATCHUP"].str.contains("@")]
    return df_home, df_away


def summarize_team_stats(df: pd.DataFrame) -> dict:
    """Calcula médias simples de estatísticas de equipa."""
    if df is None or df.empty:
        return {}

    stats = {}
    stats["Jogos analisados"] = len(df)

    if "PTS" in df.columns:
        stats["Pontos por jogo"] = round(df["PTS"].mean(), 1)

    if "FG_PCT" in df.columns:
        stats["FG% (lançamentos)"] = round(df["FG_PCT"].mean() * 100, 1)

    if "FG3_PCT" in df.columns:
        stats["3PT% (triplos)"] = round(df["FG3_PCT"].mean() * 100, 1)

    if "REB" in df.columns:
        stats["Ressaltos por jogo"] = round(df["REB"].mean(), 1)

    if "AST" in df.columns:
        stats["Assistências por jogo"] = round(df["AST"].mean(), 1)

    if "TOV" in df.columns:
        stats["Turnovers por jogo"] = round(df["TOV"].mean(), 1)

    return stats


def build_team_matchup_report(
    home_abbr: str,
    away_abbr: str,
    season: int,
    last_n_general: int = 10,
    last_n_home_away: int = 8,
    last_n_h2h: int = 6,
):
    """
    Monta uma tabela de comparação entre equipa da casa e equipa de fora.

    - Forma geral: últimos N jogos (last_n_general)
    - Casa/Fora: últimos N jogos em casa / fora (last_n_home_away)
    - H2H: últimos N confrontos diretos dentro da época escolhida (last_n_h2h)

    Colunas:
    - Métrica
    - [HOME]              -> valor da equipa da casa
    - [HOME] Green        -> ✅ se a equipa da casa está melhor nessa métrica, ❌ se pior
    - [AWAY]              -> valor da equipa de fora
    - [AWAY] Green        -> ✅ se a equipa de fora está melhor nessa métrica, ❌ se pior
    """

    home_team = find_team_by_abbr(home_abbr)
    away_team = find_team_by_abbr(away_abbr)

    if not home_team or not away_team:
        return None

    home_id = home_team["id"]
    away_id = away_team["id"]

    # ----- Forma geral (últimos N) -----
    df_home_all = get_team_last_games(home_id, season, last_n_general)
    df_away_all = get_team_last_games(away_id, season, last_n_general)

    home_general = summarize_team_stats(df_home_all)
    away_general = summarize_team_stats(df_away_all)

    # ----- Casa / Fora (últimos N casa/fora) -----
    home_home_df, _ = split_home_away(df_home_all)
    _, away_away_df = split_home_away(df_away_all)

    home_home = summarize_team_stats(home_home_df.head(last_n_home_away))
    away_away = summarize_team_stats(away_away_df.head(last_n_home_away))

    # ----- H2H (últimos N confrontos dentro da época) -----
    df_home_season = get_team_season_games(home_id, season)
    df_away_season = get_team_season_games(away_id, season)

    df_home_h2h = df_home_season[
        df_home_season["MATCHUP"].str.contains(away_team["abbreviation"])
    ]
    df_away_h2h = df_away_season[
        df_away_season["MATCHUP"].str.contains(home_team["abbreviation"])
    ]

    h2h_info = {}
    if not df_home_h2h.empty and not df_away_h2h.empty:
        merged = pd.merge(
            df_home_h2h[["GAME_ID", "GAME_DATE", "PTS"]],
            df_away_h2h[["GAME_ID", "GAME_DATE", "PTS"]],
            on=["GAME_ID", "GAME_DATE"],
            suffixes=("_HOME", "_AWAY"),
        )
        if not merged.empty:
            merged = merged.sort_values("GAME_DATE", ascending=False).head(last_n_h2h)
            h2h_info["Jogos H2H analisados"] = len(merged)
            h2h_info["Média total de pontos H2H"] = round(
                (merged["PTS_HOME"] + merged["PTS_AWAY"]).mean(), 1
            )

    # ----- Montar DataFrame final (Métrica x Equipa + colunas Green) -----
    linhas = []

    def calcular_flags(metric_name: str, home_val, away_val):
        """
        Devolve (flag_home, flag_away) com '✅'/'❌' ou '' (empate/sem comparação).
        """
        # não faz sentido comparar nº de jogos
        if "Jogos analisados" in metric_name:
            return "", ""

        try:
            hv = float(home_val)
            av = float(away_val)
        except (TypeError, ValueError):
            return "", ""

        # Turnovers: menos é melhor
        if metric_name in LOWER_BETTER_METRICS or "Turnovers por jogo" in metric_name:
            if hv < av:
                return "✅", "❌"
            elif av < hv:
                return "❌", "✅"
            else:
                return "", ""

        # Métricas "normais": mais é melhor
        if hv > av:
            return "✅", "❌"
        elif av > hv:
            return "❌", "✅"
        else:
            return "", ""

    def add_block(prefix: str, home_dict: dict, away_dict: dict):
        if not home_dict and not away_dict:
            return
        for metric in home_dict.keys():
            home_val = home_dict.get(metric, "")
            away_val = away_dict.get(metric, "")
            flag_home, flag_away = calcular_flags(metric, home_val, away_val)

            linhas.append(
                {
                    "Métrica": f"{prefix} - {metric}",
                    home_abbr: home_val,
                    f"{home_abbr} ✓": flag_home,
                    away_abbr: away_val,
                    f"{away_abbr} ✓": flag_away,
                }
            )

    # Bloco forma geral
    add_block("Geral", home_general, away_general)

    # Bloco casa/fora
    add_block("Casa/Fora", home_home, away_away)

    # H2H em linhas separadas (sem flags)


    if not linhas:
        return None

    df_result = pd.DataFrame(linhas)
    return df_result

# ----------------- FUNÇÕES BÁSICAS DE API ----------------- #

def get_all_players(max_pages: Optional[int] = None, active_only: bool = True):
    players = players_static.get_players()
    if active_only:
        players = [p for p in players if p.get("is_active")]
    if max_pages is not None:
        max_players = max_pages * 100
        players = players[:max_players]
    return players


def get_last_stats(player_id: int, season_year: int, last_n: int) -> pd.DataFrame:
    season_str = season_to_str(season_year)
    logs = PlayerGameLog(
        player_id=player_id,
        season=season_str,
        season_type_all_star="Regular Season",
        timeout=30,
    )
    df = logs.get_data_frames()[0]
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
    df = df.sort_values("GAME_DATE", ascending=False).head(last_n)
    return df


def find_player_by_name(name: str):
    players = players_static.get_players()
    matches = [p for p in players if name.lower() in p["full_name"].lower()]
    if not matches:
        return None
    return matches[0]


# ----------------- STATS POR PERÍODO (CORRIGIDO) ----------------- #

def get_player_period_stats(player_id: int, game_id: str, period: int) -> dict:
    """
    VERSÃO CORRIGIDA: Busca estatísticas REAIS por período
    usando os parâmetros certos da API NBA
    """
    if period not in (1, 2, 3, 4):
        return {}

    try:
        bs = BoxScoreTraditionalV2(
            game_id=game_id,
            start_period=period,
            end_period=period,
            range_type=1,
        )
        df_bs = bs.player_stats.get_data_frame()
    except Exception as e:
        print(f"Erro ao buscar stats do período {period}: {e}")
        return {}

    if df_bs.empty:
        return {}

    df_player = df_bs[df_bs["PLAYER_ID"] == player_id]
    if df_player.empty:
        return {}

    row = df_player.iloc[0]

    stats = {
        "PTS": float(row.get("PTS", 0)),
        "REB": float(row.get("REB", 0)),
        "AST": float(row.get("AST", 0)),
        "FG3M": float(row.get("FG3M", 0)),
        "STL": float(row.get("STL", 0)),
        "BLK": float(row.get("BLK", 0)),
        "MIN": row.get("MIN", "0:00"),
    }

    return stats


# ----------------- PROCURAR TANCOS ----------------- #

def find_tanks(
    season: int,
    stat_field: str,
    line_value: float,
    last_n: int = 10,
    min_hit_rate: float = 0.7,
    min_games: int = 8,
    max_pages_players: Optional[int] = None,
    sleep_seconds: float = 0.5,
) -> pd.DataFrame:

    if stat_field not in STAT_COLS:
        raise ValueError("stat_field deve ser 'pts', 'reb', 'ast' ou 'fg3m'.")

    stat_col = STAT_COLS[stat_field]
    players = get_all_players(max_pages=max_pages_players, active_only=True)
    results = []

    for idx, p in enumerate(players, start=1):
        pid = p["id"]
        try:
            df_logs = get_last_stats(pid, season, last_n)
        except Exception:
            time.sleep(sleep_seconds)
            continue

        if df_logs.empty:
            time.sleep(sleep_seconds)
            continue

        total = len(df_logs)
        if total < min_games:
            time.sleep(sleep_seconds)
            continue

        if stat_col not in df_logs.columns:
            time.sleep(sleep_seconds)
            continue

        hits = int((df_logs[stat_col] >= line_value).sum())
        hit_rate = hits / total

        if hit_rate >= min_hit_rate:
            first_matchup = df_logs["MATCHUP"].iloc[0]
            team_abbr = first_matchup.split(" ")[0]
            next_game_date = get_next_game(team_abbr, season)

            results.append(
                {
                    "Jogador": p["full_name"],
                    "Equipa": team_abbr,
                    "Próximo Jogo": next_game_date,
                    "Hits": hits,
                    "Jogos": total,
                    "% Acerto": round(hit_rate * 100, 1),
                    "Stat": stat_field,
                    "Linha": f"{line_value}+",
                }
            )

        time.sleep(sleep_seconds)

    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(by="% Acerto", ascending=False)
    return df


# ----------------- RELATÓRIO GREEN SCORER ----------------- #

def _parse_matchup(matchup: str):
    if "vs." in matchup:
        parts = matchup.split("vs.")
        return "Casa", parts[1].strip()
    elif "vs" in matchup:
        parts = matchup.split("vs")
        return "Casa", parts[1].strip()
    elif "@" in matchup:
        parts = matchup.split("@")
        return "Fora", parts[1].strip()
    return "", ""


def build_player_line_report(
    player_name: str,
    season: int,
    stat_field: str,
    line_value: float,
    last_n: int = 10,
) -> Optional[pd.DataFrame]:
    if stat_field not in STAT_COLS:
        raise ValueError("stat_field deve ser 'pts', 'reb', 'ast' ou 'fg3m'.")

    stat_col = STAT_COLS[stat_field]
    player = find_player_by_name(player_name)
    if not player:
        return None

    player_id = player["id"]
    try:
        df_logs = get_last_stats(player_id, season, last_n)
    except Exception:
        return None

    if df_logs.empty:
        return None

    rows = []
    hits = 0

    for _, row in df_logs.iterrows():
        date_obj = pd.to_datetime(row["GAME_DATE"]).date()
        date_str = date_obj.strftime("%d/%m/%Y")

        matchup = row.get("MATCHUP", "")
        casa_fora, adversario = _parse_matchup(matchup)

        if "TEAM_ABBREVIATION" in df_logs.columns:
            team_abbr = row["TEAM_ABBREVIATION"]
        else:
            team_abbr = (
                matchup.split(" ")[0] if isinstance(matchup, str) and matchup else ""
            )

        value = float(row.get(stat_col, 0))
        green = value >= line_value
        if green:
            hits += 1

        rows.append(
            {
                "Data": date_str,
                "Equipa": team_abbr,
                "Adversário": adversario,
                "Casa/Fora": casa_fora,
                stat_col: value,
                "Linha": f"{line_value}+",
                "Green": "✅" if green else "❌",
            }
        )

    df = pd.DataFrame(rows)
    df["Data"] = pd.to_datetime(df["Data"], format="%d/%m/%Y")
    df = df.sort_values("Data", ascending=False)
    df["Data"] = df["Data"].dt.strftime("%d/%m/%Y")

    df.attrs["player_full_name"] = player["full_name"]
    df.attrs["hits"] = hits
    df.attrs["total"] = len(rows)

    return df


def build_player_multi_stats_report(
    player_name: str,
    season: int,
    stats_lines: dict,
    last_n: int = 10,
    period: Optional[int] = None,
) -> Optional[pd.DataFrame]:
    if not stats_lines:
        return None

    for sf in stats_lines.keys():
        if sf not in STAT_COLS and sf not in (
            "pra", "ra",
            "pr",   # Pontos + Ressaltos
            "pa",   # Pontos + Assistências
            "sb",   # Roubos + Desarmes
            "pb",   # Pontos + Desarmes
            "dd",   # Duplo Duplo
            "td",   # Triplo Duplo
        ):
            raise ValueError(
                "stat_field deve ser 'pts', 'reb', 'ast', 'fg3m', 'stl', 'blk', "
                "'pra' (PRA), 'ra' (Ressaltos+Assistências), "
                "'pr' (Pontos+Ressaltos), 'pa' (Pontos+Assistências), "
                "'sb' (Roubos+Desarmes), 'pb' (Pontos+Desarmes), "
                "'dd' (Duplo-Duplo) ou 'td' (Triplo-Duplo)."
            )

    player = find_player_by_name(player_name)
    if not player:
        return None

    player_id = player["id"]
    try:
        df_logs = get_last_stats(player_id, season, last_n)
    except Exception:
        return None

    if df_logs.empty:
        return None

    rows = []
    hits_por_stat = {sf: 0 for sf in stats_lines.keys()}
    total_min_float = 0.0
    count_min = 0

    for _, row in df_logs.iterrows():
        date_obj = pd.to_datetime(row["GAME_DATE"]).date()
        date_str = date_obj.strftime("%d/%m/%Y")

        matchup = row.get("MATCHUP", "")
        casa_fora, adversario = _parse_matchup(matchup)

        if "TEAM_ABBREVIATION" in df_logs.columns:
            team_abbr = row["TEAM_ABBREVIATION"]
        else:
            team_abbr = (
                matchup.split(" ")[0] if isinstance(matchup, str) and matchup else ""
            )

        per_stats = None
        if period is not None:
            game_id = row.get("Game_ID") or row.get("GAME_ID")
            if pd.notna(game_id):
                per_stats = get_player_period_stats(player_id, str(game_id), period)

        if per_stats:
            base_pts = per_stats.get("PTS", 0.0)
            base_reb = per_stats.get("REB", 0.0)
            base_ast = per_stats.get("AST", 0.0)
            base_fg3m = per_stats.get("FG3M", 0.0)
            base_stl = per_stats.get("STL", 0.0)
            base_blk = per_stats.get("BLK", 0.0)
            min_str = per_stats.get("MIN", "")
        else:
            base_pts = float(row.get("PTS", 0))
            base_reb = float(row.get("REB", 0))
            base_ast = float(row.get("AST", 0))
            base_fg3m = float(row.get("FG3M", 0))
            base_stl = float(row.get("STL", 0))
            base_blk = float(row.get("BLK", 0))
            min_str = row.get("MIN", "")

        if period is not None and per_stats:
            min_float = 10.0 + (period % 2)
            total_min_float += min_float
            count_min += 1
        elif pd.notna(min_str) and min_str:
            try:
                parts = str(min_str).split(":")
                m_ = int(parts[0])
                s_ = int(parts[1]) if len(parts) > 1 else 0
                min_float = m_ + s_ / 60.0
                total_min_float += min_float
                count_min += 1
            except Exception:
                pass

        linha_base = {
            "Data": date_str,
            "Equipa": team_abbr,
            "Adversário": adversario,
            "Casa/Fora": casa_fora,
            "MIN": min_str,
        }

        for sf, line_value in stats_lines.items():
            # --- Combos especiais ---
            if sf == "pra":
                value = base_pts + base_reb + base_ast
                label = "PRA"

            elif sf == "ra":
                value = base_reb + base_ast
                label = "RA"

            elif sf == "pr":  # Pontos + Ressaltos
                value = base_pts + base_reb
                label = "P+R"

            elif sf == "pa":  # Pontos + Assistências
                value = base_pts + base_ast
                label = "P+A"

            elif sf == "sb":  # Roubos + Desarmes
                value = base_stl + base_blk
                label = "S+B"

            elif sf == "pb":  # Pontos + Desarmes
                value = base_pts + base_blk
                label = "P+B"

            elif sf == "dd":  # Duplo-Duplo
                categorias = [
                    base_pts,
                    base_reb,
                    base_ast,
                    base_stl,
                    base_blk,
                ]
                count_10 = sum(1 for v in categorias if v >= 10)
                # 1 = fez duplo-duplo; 0 = não fez
                value = 1 if count_10 >= 2 else 0
                label = "DD"

            elif sf == "td":  # Triplo-Duplo
                categorias = [
                    base_pts,
                    base_reb,
                    base_ast,
                    base_stl,
                    base_blk,
                ]
                count_10 = sum(1 for v in categorias if v >= 10)
                value = 1 if count_10 >= 3 else 0
                label = "TD"

            # --- Estatísticas "simples" ---
            else:
                if sf == "pts":
                    value = base_pts
                elif sf == "reb":
                    value = base_reb
                elif sf == "ast":
                    value = base_ast
                elif sf == "fg3m":
                    value = base_fg3m
                elif sf == "stl":
                    value = base_stl
                elif sf == "blk":
                    value = base_blk
                else:
                    stat_col = STAT_COLS.get(sf, "")
                    value = float(row.get(stat_col, 0))
                label = STAT_COLS.get(sf, sf.upper())

            # resto da lógica mantém-se
            green = value >= line_value
            if green:
                hits_por_stat[sf] += 1

            linha_base[label] = value
            linha_base[f"{label} Linha"] = f"{line_value}+"
            linha_base[f"{label} ✓"] = "✅" if green else "❌"

        rows.append(linha_base)

    df = pd.DataFrame(rows)
    df["Data"] = pd.to_datetime(df["Data"], format="%d/%m/%Y")
    df = df.sort_values("Data", ascending=False)
    df["Data"] = df["Data"].dt.strftime("%d/%m/%Y")

    df.attrs["player_full_name"] = player["full_name"]

    stats_summary = {}
    total = len(df)
    for sf, line_value in stats_lines.items():
        stats_summary[sf] = {
            "line": line_value,
            "hits": hits_por_stat[sf],
            "total": total,
            "hit_rate": (hits_por_stat[sf] / total * 100) if total else 0.0,
        }

    df.attrs["stats_summary"] = stats_summary

    if count_min > 0:
        df.attrs["avg_minutes"] = total_min_float / count_min
    else:
        df.attrs["avg_minutes"] = 0.0

    df.attrs["period"] = period

    return df
