import os

import matplotlib.path as mpath
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import patches

from paths import DATA_DIR

HIT_COST = 4

# Spacing and sizing
BOX_HEIGHT = 0.9
BOX_WIDTH = 9
PLAYER_SPACING = 1.2
PLAYER_NAME_FONT_SIZE = 11
STATS_FONT_SIZE = 9
GAMEWEEK_SPACING = 14
POSITION_BORDER_WIDTH = 0.12
CAPTAIN_BORDER_WIDTH = 0.2
CHIP_BACKGROUND_ZORDERS = {
    "FH": -1.0,
    "WC": -5.0,
    "BB": -5.0,
    "TC": -5.0,
}

# color scheme
CAPTAIN_COLOR = "#ffd700"
VICE_CAPTAIN_COLOR = "#c0c0c0"
BG_COLOR = "#0f0f0f"
CELL_BG_COLOR = "#1e1e1e"
BENCH_BG_COLOR = "#2a2a2a"
TEXT_COLOR = "#ffffff"
STATS_COLOR = "#b0b0b0"
CHIP_BACKGROUND_COLOR = "#1a1a1a"

# Position constants
POSITIONS = ["GKP", "DEF", "MID", "FWD"]
POSITION_COLORS = {"GKP": "#8b5cf6", "DEF": "#3b82f6", "MID": "#f59e0b", "FWD": "#ef4444"}
BASE_Y = 16


def calculate_bezier(x_start, x_end, y_start, y_end):
    """
    Calculates a bezier curve using the 4 given points.
    These are used to draw the lines signifying transfers between gameweeks.
    """
    x_control1 = x_start + (x_end - x_start) * 0.3
    x_control2 = x_start + (x_end - x_start) * 0.7
    y_control1 = y_start + (y_end - y_start) * 0.02
    y_control2 = y_start + (y_end - y_start) * 0.98

    path_data = [
        ((x_start, y_start), mpath.Path.MOVETO),
        ((x_control1, y_control1), mpath.Path.CURVE4),
        ((x_control2, y_control2), mpath.Path.CURVE4),
        ((x_end, y_end), mpath.Path.CURVE4),
    ]

    return patches.PathPatch(
        mpath.Path(*zip(*path_data, strict=True)),
        facecolor="none",
        edgecolor="#60a5fa",
        alpha=0.8,
        linewidth=1.5,
        zorder=-3.0,
    )


def calculate_player_cells(gw_idx, player_idx, player):
    y_pos = BASE_Y - player_idx * PLAYER_SPACING
    data = []

    # base cell
    data.append(
        patches.Rectangle(
            (gw_idx * GAMEWEEK_SPACING - BOX_WIDTH / 2, y_pos - BOX_HEIGHT / 2),
            BOX_WIDTH,
            BOX_HEIGHT,
            facecolor=CELL_BG_COLOR if player["lineup"] else BENCH_BG_COLOR,
            edgecolor="none",
        )
    )

    # position border
    data.append(
        patches.Rectangle(
            (gw_idx * GAMEWEEK_SPACING - BOX_WIDTH / 2, y_pos - BOX_HEIGHT / 2 - POSITION_BORDER_WIDTH),
            BOX_WIDTH,
            POSITION_BORDER_WIDTH,
            facecolor=POSITION_COLORS[player["pos"]],
            edgecolor="none",
        )
    )

    # captain border
    if player["captain"] == 1 and gw_idx > 0:
        data.append(
            patches.Rectangle(
                (gw_idx * GAMEWEEK_SPACING - BOX_WIDTH / 2, y_pos - BOX_HEIGHT / 2),
                CAPTAIN_BORDER_WIDTH,
                BOX_HEIGHT,
                facecolor=CAPTAIN_COLOR,
                edgecolor="none",
            )
        )

    # vice captain border
    elif player["vicecaptain"] == 1 and gw_idx > 0:
        data.append(
            patches.Rectangle(
                (gw_idx * GAMEWEEK_SPACING - BOX_WIDTH / 2, y_pos - BOX_HEIGHT / 2),
                CAPTAIN_BORDER_WIDTH,
                BOX_HEIGHT,
                facecolor=VICE_CAPTAIN_COLOR,
                edgecolor="none",
            )
        )

    return data


def _setup_figure_and_data(picks, current_squad):
    """Setup the matplotlib figure and prepare data for visualization."""
    df = pd.DataFrame(picks)
    df_squad = df[df["squad"] == 1]
    df_base = df[df["week"] == min(df["week"])]
    gameweeks = sorted(df_squad["week"].unique())

    # Handle preseason scenario (earliest gameweek is 1)
    if min(gameweeks) == 1:
        base_week = None  # No base team in preseason
    else:
        base_week = min(gameweeks) - 1

    fh_week = df.loc[df["chip"] == "FH"].iloc[0]["week"] if len(df.loc[df["chip"] == "FH"]) > 0 else None

    fig, ax = plt.subplots(figsize=(26, 14))
    ax.set_facecolor(BG_COLOR)
    fig.patch.set_facecolor(BG_COLOR)

    return fig, ax, df, df_squad, df_base, gameweeks, base_week, fh_week


def _get_week_players(week, base_week, df_base, df_squad, current_squad):
    """Get players for a specific gameweek."""
    if base_week is not None and week == base_week:
        gw_players = df_base[df_base["id"].isin(current_squad)]
        gw_players.loc[:, "lineup"] = 1
    else:
        gw_players = df_squad[df_squad["week"] == week]
    return gw_players


def _add_week_header(ax, gw_idx, week, base_week, gw_players):
    """Add gameweek header and chip information."""
    if base_week is not None and week == base_week:
        ax.text(gw_idx * GAMEWEEK_SPACING, BASE_Y + 1.2, "Base", color=TEXT_COLOR, fontsize=13, ha="center", weight="bold")
    else:
        ax.text(gw_idx * GAMEWEEK_SPACING, BASE_Y + 1.2, f"GW{week}", color=TEXT_COLOR, fontsize=13, ha="center", weight="bold")
        if "chip" in gw_players.columns and not gw_players["chip"].isna().all():
            try:
                chip = gw_players.loc[gw_players["chip"] != ""]["chip"].iloc[0]
            except Exception:
                chip = gw_players["chip"].iloc[0]
            if pd.notna(chip):
                ax.text(gw_idx * GAMEWEEK_SPACING, BASE_Y + 0.8, chip, color="#fbbf24", fontsize=11, ha="center", weight="bold")


def _add_player_cells(ax, gw_idx, gw_players, week, player_indexes):
    """Add player cells for starting XI and bench."""
    starting_xi = gw_players[gw_players["lineup"] == 1].sort_values(["type", "xP"], ascending=[True, False]).reset_index()
    bench = gw_players[gw_players["lineup"] == 0].sort_values(["type", "xP"], ascending=[True, False]).reset_index()
    bench.index = bench.index + 11

    player_indexes[week] = {}

    # Starting XI
    for player_idx, player in starting_xi.iterrows():
        y_pos = BASE_Y - player_idx * PLAYER_SPACING
        player_indexes[week][player["id"]] = (y_pos, player["pos"])

        cells = calculate_player_cells(gw_idx, player_idx, player)
        for cell in cells:
            ax.add_patch(cell)
        text_pos = (gw_idx * GAMEWEEK_SPACING, y_pos + 0.2)
        ax.text(*text_pos, player["name"], color=TEXT_COLOR, ha="center", va="center", fontsize=PLAYER_NAME_FONT_SIZE, weight="medium")

        # Check if this is not the base week by looking at the data structure
        if "xP" in player and "xMin" in player:
            stats_text = f"{player['xP']:.1f} xPts • {int(player['xMin'])} xMin"
            ax.text(gw_idx * GAMEWEEK_SPACING, y_pos - 0.25, stats_text, color=STATS_COLOR, ha="center", va="center", fontsize=STATS_FONT_SIZE)

    # Bench
    for player_idx, player in bench.iterrows():
        y_pos = BASE_Y - player_idx * PLAYER_SPACING
        player_indexes[week][player["id"]] = (BASE_Y - player_idx * PLAYER_SPACING, player["pos"])
        cells = calculate_player_cells(gw_idx, player_idx, player)
        for cell in cells:
            ax.add_patch(cell)
        text_pos = (gw_idx * GAMEWEEK_SPACING, y_pos + 0.2)
        ax.text(*text_pos, player["name"], color=TEXT_COLOR, ha="center", va="center", fontsize=PLAYER_NAME_FONT_SIZE, weight="medium")

        stats_text = f"{player['xP']:.1f} xPts • {int(player['xMin'])} xMin"
        ax.text(gw_idx * GAMEWEEK_SPACING, y_pos - 0.25, stats_text, color=STATS_COLOR, ha="center", va="center", fontsize=STATS_FONT_SIZE)


def _add_transfers(ax, gw_idx, week, picks, player_indexes):
    """Add transfer lines between gameweeks."""
    # Calculate fh_week from picks data
    fh_week = picks.loc[picks["chip"] == "FH"].iloc[0]["week"] if len(picks.loc[picks["chip"] == "FH"]) > 0 else None

    # Get previous week from player_indexes keys
    prev_weeks = [w for w in player_indexes.keys() if w < week]
    prev_week_int = max(prev_weeks) if prev_weeks else week - 1

    transfers_in = picks.loc[(picks["week"] == week) & (picks["transfer_in"] == 1)]
    transfers_out = picks.loc[(picks["week"] == week) & (picks["transfer_out"] == 1)]

    for pos in POSITIONS:
        players_out = transfers_out.loc[transfers_out["pos"] == pos].to_dict(orient="records")
        players_in = transfers_in.loc[transfers_in["pos"] == pos].to_dict(orient="records")

        if week == 1:
            # don't draw any lines
            continue

        for player_out, player_in in zip(players_out, players_in, strict=True):
            skip_fh = int(prev_week_int == fh_week) if fh_week else 0
            x_start = (gw_idx - 1 - skip_fh) * GAMEWEEK_SPACING + BOX_WIDTH / 2
            x_end = gw_idx * GAMEWEEK_SPACING - BOX_WIDTH / 2
            y_start = player_indexes[prev_week_int - skip_fh][player_out["id"]][0]
            y_end = player_indexes[week][player_in["id"]][0]
            ax.add_patch(calculate_bezier(x_start, x_end, y_start, y_end))


def _add_gameweek_statistics(ax, gw_idx, week, statistics, player_idx):
    """Add gameweek statistics below the squad."""
    # Determine base week from statistics keys
    base_week = min(statistics.keys()) if statistics else week

    if week == base_week:
        return

    stats_y = BASE_Y - (player_idx + 0.5) * PLAYER_SPACING
    ax.text(
        gw_idx * GAMEWEEK_SPACING,
        stats_y - 0.5,
        f"{statistics[int(week)]['xP']:.2f} xPts",
        color=TEXT_COLOR,
        fontsize=11,
        ha="center",
        weight="medium",
    )

    if week > 1:
        itb_text = f"{statistics[week - 1]['itb']:.1f} → {statistics[week]['itb']:.1f}"
    else:
        itb_text = f"{statistics[week]['itb']:.1f}"
    ax.text(
        gw_idx * GAMEWEEK_SPACING,
        stats_y - 0.9,
        f"ITB: {itb_text}",
        color=STATS_COLOR,
        fontsize=9,
        ha="center",
    )

    if week > 1 and statistics[week]["chip"] not in ["FH", "WC"]:
        fts_available = round(statistics[week]["ft"])
        transfer_str = f"FTs: {round(statistics[week]['nt'])}/{fts_available}"
        if statistics[week]["pt"] > 0:
            transfer_str += f" (-{statistics[week]['pt'] * HIT_COST})"
        ax.text(gw_idx * GAMEWEEK_SPACING, stats_y - 1.3, transfer_str, color=STATS_COLOR, fontsize=9, ha="center")


def _add_chip_backgrounds(ax, df, base_week, bottom_limit, top_limit):
    """Add background rectangles for chip gameweeks."""
    chip_weeks = dict(df.loc[df["chip"] != ""][["week", "chip"]].drop_duplicates().values)

    for gw, chip in chip_weeks.items():
        # Handle preseason scenario (no base week)
        if base_week is not None:
            x_center = (gw - base_week) * GAMEWEEK_SPACING
        else:
            x_center = (gw - 1) * GAMEWEEK_SPACING  # Use GW1 as reference in preseason

        rect = patches.FancyBboxPatch(
            (x_center - GAMEWEEK_SPACING / 2, bottom_limit),
            GAMEWEEK_SPACING,
            top_limit - bottom_limit,
            edgecolor="none",
            facecolor=CHIP_BACKGROUND_COLOR,
            zorder=CHIP_BACKGROUND_ZORDERS[chip],
            boxstyle=patches.BoxStyle("Round", pad=-0.3, rounding_size=2),
            alpha=0.85,
        )
        ax.add_patch(rect)


def create_squad_timeline(current_squad, statistics, picks, filename):
    """Create a timeline visualization of squad changes across gameweeks."""
    fig, ax, df, df_squad, df_base, gameweeks, base_week, fh_week = _setup_figure_and_data(picks, current_squad)

    player_indexes = {}
    # Handle preseason scenario (no base week)
    if base_week is not None:
        display_weeks = [base_week, *gameweeks]
    else:
        display_weeks = gameweeks

    for gw_idx, week in enumerate(display_weeks):
        gw_players = _get_week_players(week, base_week, df_base, df_squad, current_squad)
        _add_week_header(ax, gw_idx, week, base_week, gw_players)
        _add_player_cells(ax, gw_idx, gw_players, week, player_indexes)
        _add_transfers(ax, gw_idx, week, picks, player_indexes)
        _add_gameweek_statistics(ax, gw_idx, week, statistics, len(gw_players) - 1)

    # Set plot limits and styling
    total_width = (len(display_weeks) - 1) * GAMEWEEK_SPACING + BOX_WIDTH
    ax.set_xlim(-6, total_width + 2)
    bottom_limit = BASE_Y - (len(gw_players) + 1.5) * PLAYER_SPACING
    top_limit = BASE_Y + 2.8
    ax.set_ylim(bottom_limit, top_limit)
    ax.axis("off")

    plt.title(filename, color=TEXT_COLOR, fontsize=14, weight="bold", pad=20)
    _add_chip_backgrounds(ax, df, base_week, bottom_limit, top_limit)

    # Ensure the images directory exists
    os.makedirs(DATA_DIR / "images", exist_ok=True)
    plt.savefig(DATA_DIR / "images" / f"{filename}.png", bbox_inches="tight", facecolor=BG_COLOR)
    plt.close()
