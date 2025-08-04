import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import patches


def create_squad_timeline(current_squad, statistics, picks, filename):
    df = pd.DataFrame(picks)

    bg_color = "#1a1a1a"
    cell_bg_color = "#2d2d2d"
    bench_bg_color = "#404040"
    text_color = "#ffffff"
    stats_color = "#a0a0a0"
    position_colors = {"GKP": "#4a1b7a", "DEF": "#0d4a6b", "MID": "#6b5c0d", "FWD": "#6b1d1d", "AMN": "#2d5a1d"}

    # where squad = 1 or the player pos is AMN
    df_squad = df[(df["squad"] == 1) | (df["pos"] == "AMN")]

    df_base = df[df["week"] == min(df["week"])]

    gameweeks = sorted(df_squad["week"].unique())
    base_week = min(gameweeks) - 1

    am_used = any(
        not df_squad[df_squad["week"] == week]["chip"].isna().all() and df_squad[df_squad["week"] == week]["chip"].iloc[0] == "AM"
        for week in gameweeks
    )

    fig, ax = plt.subplots(figsize=(20, 10))

    ax.set_facecolor(bg_color)
    fig.patch.set_facecolor(bg_color)

    captain_color = "#ffd700"
    vice_captain_color = "#c0c0c0"

    box_height = 0.8
    box_width = 8
    player_spacing = 1
    gameweek_spacing = 12
    position_border_width = 0.08
    captain_border_width = 0.15

    # Set consistent base position
    base_y = 15
    am_y_position = base_y  # AM cell goes at the top position

    # Adjust spacing if AM is used to maintain proper distribution
    player_spacing = 0.85 if am_used else 1

    player_positions = {}
    display_weeks = [base_week] + gameweeks

    for gw_idx, week in enumerate(display_weeks):
        if week == base_week:
            gw_players = df_base[df_base["id"].isin(current_squad)]
            gw_players.loc[:, "lineup"] = 1
            ax.text(gw_idx * gameweek_spacing, base_y + 1, "Base", color=text_color, fontsize=10, ha="center")
        else:
            gw_players = df_squad[df_squad["week"] == week]
            ax.text(gw_idx * gameweek_spacing, base_y + 1, f"GW{week}", color=text_color, fontsize=10, ha="center")
            if "chip" in gw_players.columns and not gw_players["chip"].isna().all():
                try:
                    chip = gw_players.loc[gw_players["chip"] != ""]["chip"].iloc[0]
                except Exception:
                    chip = gw_players["chip"].iloc[0]
                if pd.notna(chip):
                    ax.text(gw_idx * gameweek_spacing, base_y + 0.7, chip, color=text_color, fontsize=8, ha="center")
                if chip == "AM":
                    amn_players = gw_players[gw_players["pos"] == "AMN"]

                    if not amn_players.empty:
                        manager = (
                            amn_players[amn_players["transfer_in"] == 1].iloc[0] if any(amn_players["transfer_in"] == 1) else amn_players.iloc[0]
                        )

                        cell = patches.Rectangle(
                            (gw_idx * gameweek_spacing - box_width / 2, am_y_position - box_height / 2),
                            box_width,
                            box_height,
                            facecolor=cell_bg_color,
                            edgecolor="none",
                        )
                        ax.add_patch(cell)

                        bottom_border = patches.Rectangle(
                            (gw_idx * gameweek_spacing - box_width / 2, am_y_position - box_height / 2),
                            box_width,
                            position_border_width,
                            facecolor=position_colors["AMN"],
                            edgecolor="none",
                        )
                        ax.add_patch(bottom_border)

                        ax.text(
                            gw_idx * gameweek_spacing,
                            am_y_position + 0.15,
                            manager["name"],
                            color=text_color,
                            ha="center",
                            va="center",
                            fontsize=8,
                        )

                        stats_text = f"{manager['xP']:.1f} xPts"
                        ax.text(
                            gw_idx * gameweek_spacing,
                            am_y_position - 0.15,
                            stats_text,
                            color=stats_color,
                            ha="center",
                            va="center",
                            fontsize=6,
                        )

                        week_int = int(week)
                        if week_int not in player_positions:
                            player_positions[week_int] = {}

                        player_positions[week_int]["AM_MANAGER"] = (am_y_position, "AMN")

                        if week != base_week:
                            prev_week_int = int(display_weeks[gw_idx - 1])
                            if prev_week_int in player_positions and "AM_MANAGER" in player_positions[prev_week_int] and manager["transfer_in"] == 1:
                                ax.plot(
                                    [
                                        (gw_idx - 1) * gameweek_spacing + box_width / 2,
                                        gw_idx * gameweek_spacing - box_width / 2,
                                    ],
                                    [player_positions[prev_week_int]["AM_MANAGER"][0], am_y_position],
                                    color=text_color,
                                    alpha=0.5,
                                    linewidth=1,
                                )

        starting_xi = gw_players[gw_players["lineup"] == 1].sort_values(["type", "name"])
        bench = gw_players[gw_players["lineup"] == 0]
        bench_gk = bench[bench["pos"] == "GKP"]
        bench_outfield = bench[bench["pos"] != "GKP"].sort_values("xP", ascending=False)
        bench = pd.concat([bench_gk, bench_outfield])

        # Initialize or reset player positions for this week
        week_int = int(week)
        if week_int not in player_positions:
            player_positions[week_int] = {}

        player_idx = 1 if am_used else 0

        for _, player in starting_xi.iterrows():
            y_pos = base_y - player_idx * player_spacing
            player_positions[week_int][player["name"]] = (y_pos, player["pos"])

            cell = patches.Rectangle(
                (gw_idx * gameweek_spacing - box_width / 2, y_pos - box_height / 2),
                box_width,
                box_height,
                facecolor=cell_bg_color,
                edgecolor="none",
            )
            ax.add_patch(cell)

            bottom_border = patches.Rectangle(
                (gw_idx * gameweek_spacing - box_width / 2, y_pos - box_height / 2),
                box_width,
                position_border_width,
                facecolor=position_colors[player["pos"]],
                edgecolor="none",
            )
            ax.add_patch(bottom_border)

            if player["captain"] == 1:
                left_border = patches.Rectangle(
                    (gw_idx * gameweek_spacing - box_width / 2, y_pos - box_height / 2),
                    captain_border_width,
                    box_height,
                    facecolor=captain_color,
                    edgecolor="none",
                )
                ax.add_patch(left_border)
            elif player["vicecaptain"] == 1:
                left_border = patches.Rectangle(
                    (gw_idx * gameweek_spacing - box_width / 2, y_pos - box_height / 2),
                    captain_border_width,
                    box_height,
                    facecolor=vice_captain_color,
                    edgecolor="none",
                )
                ax.add_patch(left_border)

            ax.text(
                gw_idx * gameweek_spacing,
                y_pos + 0.15,
                player["name"],
                color=text_color,
                ha="center",
                va="center",
                fontsize=8,
            )

            stats_text = f"{player['xP']:.1f} xPts : {int(player['xMin'])} xMin"
            ax.text(
                gw_idx * gameweek_spacing,
                y_pos - 0.15,
                stats_text,
                color=stats_color,
                ha="center",
                va="center",
                fontsize=6,
            )

            player_idx += 1

        for _, player in bench.iterrows():
            y_pos = base_y - player_idx * player_spacing
            player_positions[week_int][player["name"]] = (y_pos, player["pos"])

            cell = patches.Rectangle(
                (gw_idx * gameweek_spacing - box_width / 2, y_pos - box_height / 2),
                box_width,
                box_height,
                facecolor=bench_bg_color,
                edgecolor="none",
            )
            ax.add_patch(cell)

            bottom_border = patches.Rectangle(
                (gw_idx * gameweek_spacing - box_width / 2, y_pos - box_height / 2),
                box_width,
                position_border_width,
                facecolor=position_colors[player["pos"]],
                edgecolor="none",
            )
            ax.add_patch(bottom_border)

            if player["captain"] == 1:
                left_border = patches.Rectangle(
                    (gw_idx * gameweek_spacing - box_width / 2, y_pos - box_height / 2),
                    captain_border_width,
                    box_height,
                    facecolor=captain_color,
                    edgecolor="none",
                )
                ax.add_patch(left_border)
            elif player["vicecaptain"] == 1:
                left_border = patches.Rectangle(
                    (gw_idx * gameweek_spacing - box_width / 2, y_pos - box_height / 2),
                    captain_border_width,
                    box_height,
                    facecolor=vice_captain_color,
                    edgecolor="none",
                )
                ax.add_patch(left_border)

            ax.text(
                gw_idx * gameweek_spacing,
                y_pos + 0.15,
                player["name"],
                color=text_color,
                ha="center",
                va="center",
                fontsize=8,
            )

            stats_text = f"{player['xP']:.1f} xPts : {int(player['xMin'])} xMin"
            ax.text(
                gw_idx * gameweek_spacing,
                y_pos - 0.15,
                stats_text,
                color=stats_color,
                ha="center",
                va="center",
                fontsize=6,
            )

            player_idx += 1

        if week != base_week:
            prev_week_int = int(display_weeks[gw_idx - 1])
            prev_players = set(player_positions[prev_week_int].keys())
            curr_players = set(player_positions[week_int].keys())

            transfers_out = prev_players - curr_players
            transfers_in = curr_players - prev_players

            for pos in ["GKP", "DEF", "MID", "FWD"]:
                out_players = [p for p in transfers_out if player_positions[prev_week_int][p][1] == pos]
                in_players = [p for p in transfers_in if player_positions[week_int][p][1] == pos]

                for out_p, in_p in zip(out_players, in_players, strict=False):
                    ax.plot(
                        [(gw_idx - 1) * gameweek_spacing + box_width / 2, gw_idx * gameweek_spacing - box_width / 2],
                        [player_positions[prev_week_int][out_p][0], player_positions[week_int][in_p][0]],
                        color=text_color,
                        alpha=0.5,
                        linewidth=1,
                    )

        if week != base_week and week in statistics:
            gw_statistics = statistics[week]

            # Position summary stats relative to last player
            stats_y = base_y - (player_idx + 1) * player_spacing

            ax.text(
                gw_idx * gameweek_spacing,
                stats_y,
                f"Lineup {gw_statistics['xP']:.2f} xPts",
                color=text_color,
                fontsize=10,
                ha="center",
            )

            ax.text(
                gw_idx * gameweek_spacing,
                stats_y - 0.4,
                f"Obj {gw_statistics['obj']:.2f} xPts",
                color=text_color,
                fontsize=10,
                ha="center",
            )

            ax.text(
                gw_idx * gameweek_spacing,
                stats_y - 0.8,
                f"ITB: {gw_statistics['itb']:.1f}",
                color=text_color,
                fontsize=8,
                ha="center",
            )

            transfer_str = ""
            for key in ["ft", "pt", "nt"]:
                if key in gw_statistics:
                    transfer_str += f"{key.upper()}: {gw_statistics[key]}  "

            ax.text(gw_idx * gameweek_spacing, stats_y - 1.15, transfer_str, color=text_color, fontsize=8, ha="center")

    total_width = (len(display_weeks) - 1) * gameweek_spacing + box_width
    ax.set_xlim(-5, total_width)
    # Calculate limits based on content
    bottom_limit = base_y - (player_idx + 2) * player_spacing  # Extra space for summary stats
    top_limit = base_y + 2  # Space for headers
    ax.set_ylim(bottom_limit, top_limit)
    ax.axis("off")

    plt.title(filename, color=text_color)
    plt.savefig("../data/results/" + filename + ".png", bbox_inches="tight", facecolor=bg_color)
    plt.close()
