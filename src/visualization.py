import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches


def create_squad_timeline(current_squad, picks, filename):
    df = pd.DataFrame(picks)

    bg_color = '#1a1a1a'
    cell_bg_color = '#2d2d2d'
    bench_bg_color = '#404040'
    text_color = '#ffffff'
    stats_color = '#a0a0a0'
    position_colors = {
        'GKP': '#4a1b7a',
        'DEF': '#0d4a6b',
        'MID': '#6b5c0d',
        'FWD': '#6b1d1d'
    }

    fig, ax = plt.subplots(figsize=(20, 10))
    ax.set_facecolor(bg_color)
    fig.patch.set_facecolor(bg_color)

    captain_color = '#ffd700'
    vice_captain_color = '#c0c0c0'

    box_height = 0.8
    box_width = 8
    player_spacing = 1
    gameweek_spacing = 12
    position_border_width = 0.08
    captain_border_width = 0.15

    df_squad = df[df['squad'] == 1]

    df_base = df[df['week'] == min(df['week'])]

    gameweeks = sorted(df_squad['week'].unique())
    base_week = min(gameweeks) - 1

    player_positions = {}
    display_weeks = [base_week] + gameweeks

    for gw_idx, week in enumerate(display_weeks):
        if week == base_week:
            gw_players = df_base[df_base['id'].isin(current_squad)]
            gw_players['lineup'] = 1
            ax.text(gw_idx * gameweek_spacing, 16, 'Base',
                    color=text_color, fontsize=10, ha='center')
        else:
            gw_players = df_squad[df_squad['week'] == week]
            ax.text(gw_idx * gameweek_spacing, 16, f'GW{week}',
                    color=text_color, fontsize=10, ha='center')
            if 'chip' in gw_players.columns and not gw_players['chip'].isna().all():
                chip = gw_players['chip'].iloc[0]
                if pd.notna(chip):
                    ax.text(gw_idx * gameweek_spacing, 15.7, chip,
                            color=text_color, fontsize=8, ha='center')

        starting_xi = gw_players[gw_players['lineup'] == 1].sort_values(['type', 'name'])

        bench = gw_players[gw_players['lineup'] == 0]
        bench_gk = bench[bench['pos'] == 'GKP']
        bench_outfield = bench[bench['pos'] != 'GKP'].sort_values('xP', ascending=False)
        bench = pd.concat([bench_gk, bench_outfield])

        player_positions[week] = {}

        player_idx = 0

        for _, player in starting_xi.iterrows():
            y_pos = 15 - player_idx * player_spacing
            player_positions[week][player['name']] = (y_pos, player['pos'])

            cell = patches.Rectangle(
                (gw_idx * gameweek_spacing - box_width / 2,
                 y_pos - box_height / 2),
                box_width, box_height,
                facecolor=cell_bg_color,
                edgecolor='none'
            )
            ax.add_patch(cell)

            bottom_border = patches.Rectangle(
                (gw_idx * gameweek_spacing - box_width / 2,
                 y_pos - box_height / 2),
                box_width, position_border_width,
                facecolor=position_colors[player['pos']],
                edgecolor='none'
            )
            ax.add_patch(bottom_border)

            if player['captain'] == 1:
                left_border = patches.Rectangle(
                    (gw_idx * gameweek_spacing - box_width / 2,
                     y_pos - box_height / 2),
                    captain_border_width, box_height,
                    facecolor=captain_color,
                    edgecolor='none'
                )
                ax.add_patch(left_border)
            elif player['vicecaptain'] == 1:
                left_border = patches.Rectangle(
                    (gw_idx * gameweek_spacing - box_width / 2,
                     y_pos - box_height / 2),
                    captain_border_width, box_height,
                    facecolor=vice_captain_color,
                    edgecolor='none'
                )
                ax.add_patch(left_border)

            ax.text(gw_idx * gameweek_spacing,
                    y_pos + 0.15,
                    player['name'],
                    color=text_color,
                    ha='center',
                    va='center',
                    fontsize=8)

            stats_text = f"{player['xP']:.1f} xPts, {int(player['xMin'])} xMin"
            ax.text(gw_idx * gameweek_spacing,
                    y_pos - 0.15,
                    stats_text,
                    color=stats_color,
                    ha='center',
                    va='center',
                    fontsize=6)

            player_idx += 1

        for _, player in bench.iterrows():
            y_pos = 15 - player_idx * player_spacing
            player_positions[week][player['name']] = (y_pos, player['pos'])

            cell = patches.Rectangle(
                (gw_idx * gameweek_spacing - box_width / 2,
                 y_pos - box_height / 2),
                box_width, box_height,
                facecolor=bench_bg_color,
                edgecolor='none'
            )
            ax.add_patch(cell)

            bottom_border = patches.Rectangle(
                (gw_idx * gameweek_spacing - box_width / 2,
                 y_pos - box_height / 2),
                box_width, position_border_width,
                facecolor=position_colors[player['pos']],
                edgecolor='none'
            )
            ax.add_patch(bottom_border)

            if player['captain'] == 1:
                left_border = patches.Rectangle(
                    (gw_idx * gameweek_spacing - box_width / 2,
                     y_pos - box_height / 2),
                    captain_border_width, box_height,
                    facecolor=captain_color,
                    edgecolor='none'
                )
                ax.add_patch(left_border)
            elif player['vicecaptain'] == 1:
                left_border = patches.Rectangle(
                    (gw_idx * gameweek_spacing - box_width / 2,
                     y_pos - box_height / 2),
                    captain_border_width, box_height,
                    facecolor=vice_captain_color,
                    edgecolor='none'
                )
                ax.add_patch(left_border)

            ax.text(gw_idx * gameweek_spacing,
                    y_pos + 0.15,
                    player['name'],
                    color=text_color,
                    ha='center',
                    va='center',
                    fontsize=8)

            stats_text = f"{player['xP']:.1f} xPts : {int(player['xMin'])} xMin"
            ax.text(gw_idx * gameweek_spacing,
                    y_pos - 0.15,
                    stats_text,
                    color=stats_color,
                    ha='center',
                    va='center',
                    fontsize=6)

            player_idx += 1

        if week != base_week:
            prev_week = display_weeks[gw_idx - 1]
            prev_players = set(player_positions[prev_week].keys())
            curr_players = set(player_positions[week].keys())

            transfers_out = prev_players - curr_players
            transfers_in = curr_players - prev_players

            for pos in ['GKP', 'DEF', 'MID', 'FWD']:
                out_players = [p for p in transfers_out
                               if player_positions[prev_week][p][1] == pos]
                in_players = [p for p in transfers_in
                              if player_positions[week][p][1] == pos]

                for out_p, in_p in zip(out_players, in_players):
                    ax.plot([
                        (gw_idx - 1) * gameweek_spacing + box_width / 2,
                        gw_idx * gameweek_spacing - box_width / 2
                    ], [
                        player_positions[prev_week][out_p][0],
                        player_positions[week][in_p][0]
                    ], color=text_color, alpha=0.5, linewidth=1)

        if week != base_week:
            weekly_xp = gw_players['xP'].sum()
            ax.text(gw_idx * gameweek_spacing, -1, f'{weekly_xp:.1f} xPts',
                    color=text_color, fontsize=10, ha='center')

    total_width = (len(display_weeks) - 1) * gameweek_spacing + box_width
    ax.set_xlim(-5, total_width)
    ax.set_ylim(-2, 18)
    ax.axis('off')

    plt.title(filename, color=text_color)
    plt.savefig('../data/results/' + filename + '.png', bbox_inches='tight', facecolor=bg_color)
    plt.close()
