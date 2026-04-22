"""
visualize.py - Data visualization for Deadline Dungeon

Reads all CSV files from stats_data/ and generates visualizations for
the 8 collected features plus the leaderboard.

Interactive controls (when running the dashboard GUI):
    * Top-N slider     - leaderboard / death-cause / damage-received
    * Sessions slider  - HP-over-time / EXP-over-time charts
    * Class radio      - filter damage histograms + skill usage by class
    * Reset button     - put everything back to defaults

Usage:
    python visualize.py                  # opens interactive dashboard
    python visualize.py --save           # saves all charts to screenshots/visualization/
    python visualize.py --save --nogui   # save only, no window
    python visualize.py --summary        # print a text summary

Requires: matplotlib, pandas
    pip install matplotlib pandas
"""
import os
import sys
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.widgets import Slider, RadioButtons, Button


# ---------- Resolve paths relative to this script ----------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------- Styling ----------
DATA_DIR = os.path.join(_SCRIPT_DIR, "stats_data")
OUT_DIR = os.path.join(_SCRIPT_DIR, "screenshots", "visualization")

# Dark dungeon-ish theme
BG          = "#1a1620"
PANEL_BG    = "#25202c"
FG          = "#e8e6e0"
MUTED       = "#9891a4"
GRID        = "#3a3342"

ACCENT_RED  = "#d44343"
ACCENT_GOLD = "#e8c14f"
ACCENT_BLUE = "#5e8ed6"
ACCENT_GREEN = "#7cb453"
ACCENT_PURPLE = "#9d7ad6"
ACCENT_ORANGE = "#e08845"

# Consistent colors for enemy types
ENEMY_COLORS = {
    "slime":              "#7cb453",
    "skeleton":           "#d0d0b8",
    "orc":                "#6aa146",
    "mini_boss_1":        "#d4a04a",
    "mini_boss_2":        "#b86a4a",
    "final_boss":         "#d44343",
    "Greatsword Skeleton":"#d4a04a",
    "Werewolf":           "#b86a4a",
    "Elite Orc":          "#d44343",
    "unknown":            "#888888",
}

# Consistent colors for player classes
CLASS_COLORS = {
    "Soldier": ACCENT_GOLD,
    "Knight":  ACCENT_RED,
    "Wizard":  ACCENT_BLUE,
    "Archer":  ACCENT_GREEN,
}


def apply_style():
    """Apply the dungeon dark theme to matplotlib."""
    plt.rcParams.update({
        "figure.facecolor":    BG,
        "axes.facecolor":      PANEL_BG,
        "axes.edgecolor":      GRID,
        "axes.labelcolor":     FG,
        "axes.titlecolor":     FG,
        "axes.titleweight":    "bold",
        "xtick.color":         MUTED,
        "ytick.color":         MUTED,
        "text.color":          FG,
        "grid.color":          GRID,
        "grid.linestyle":      "--",
        "grid.alpha":          0.5,
        "font.family":         "DejaVu Sans",
        "font.size":           10,
        "legend.facecolor":    PANEL_BG,
        "legend.edgecolor":    GRID,
        "legend.labelcolor":   FG,
    })


def load_csv(name):
    """Load a CSV from stats_data/ (returns empty DataFrame if missing or broken).

    Tolerates files where rows have varying column counts — common when the
    game was played with different versions of stats_collector.py. Bad rows
    are skipped, good rows kept.
    """
    path = os.path.join(DATA_DIR, f"{name}.csv")
    if not os.path.exists(path):
        print(f"  [!] Missing: {path}")
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.ParserError:
        try:
            df = pd.read_csv(path, on_bad_lines="skip", engine="python")
            print(f"  [i] {name}.csv had mixed schemas — loaded {len(df)} valid rows")
            return df
        except Exception as e:
            print(f"  [!] Failed to read {path}: {e}")
            return pd.DataFrame()
    except Exception as e:
        print(f"  [!] Failed to read {path}: {e}")
        return pd.DataFrame()


def style_axis(ax, title=None, xlabel=None, ylabel=None):
    """Apply consistent title/label formatting to an axis."""
    if title:
        ax.set_title(title, color=FG, fontsize=12, fontweight="bold", pad=10)
    if xlabel:
        ax.set_xlabel(xlabel, color=MUTED, fontsize=10)
    if ylabel:
        ax.set_ylabel(ylabel, color=MUTED, fontsize=10)
    ax.grid(True, alpha=0.3)
    for spine in ax.spines.values():
        spine.set_color(GRID)


def empty_message(ax, message="No data available"):
    """Draw a 'no data' message in an axis."""
    ax.text(0.5, 0.5, message, transform=ax.transAxes,
            ha="center", va="center", color=MUTED, fontsize=11, style="italic")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


# ---------- Filter helpers ----------

def apply_class_filter(df, class_filter):
    """Return df filtered to the selected class (or the original df if 'All')."""
    if class_filter and class_filter != "All" and "player_class" in df.columns:
        return df[df["player_class"] == class_filter].copy()
    return df


# ---------- Visualization functions ----------
# Each takes (ax, filters_dict) and clears/redraws in-place so the interactive
# dashboard can re-run them when the user moves a slider or picks a filter.

def _clear_axis(ax):
    ax.clear()


def viz_damage_dealt(ax, filters):
    """Feature 1: Histogram of damage dealt, optionally grouped by class."""
    _clear_axis(ax)
    df = load_csv("damage_dealt")
    style_axis(ax, "1. Damage Dealt Per Attack",
                xlabel="Damage", ylabel="Frequency")
    if df.empty or "damage" not in df.columns:
        empty_message(ax); return

    df = apply_class_filter(df, filters.get("class"))
    if df.empty:
        empty_message(ax, "No data for this class"); return

    df = df.copy()
    df["damage"] = pd.to_numeric(df["damage"], errors="coerce")
    df = df.dropna(subset=["damage"])
    if df.empty:
        empty_message(ax); return

    p95 = df["damage"].quantile(0.95)
    clipped = df[df["damage"] <= p95]
    outliers = len(df) - len(clipped)

    if "player_class" in clipped.columns and clipped["player_class"].nunique() > 1:
        bins = 20
        classes = sorted(clipped["player_class"].dropna().unique())
        data_per_class = [clipped[clipped["player_class"] == c]["damage"].values
                           for c in classes]
        colors = [CLASS_COLORS.get(c, MUTED) for c in classes]
        ax.hist(data_per_class, bins=bins, color=colors, edgecolor=BG,
                 stacked=True, label=classes, alpha=0.95)
        ax.legend(title="Class", fontsize=8, title_fontsize=9,
                  loc="upper right", frameon=True, framealpha=0.85)
    else:
        cls = filters.get("class")
        single_color = CLASS_COLORS.get(cls, ACCENT_RED)
        ax.hist(clipped["damage"], bins=20, color=single_color,
                edgecolor=BG, alpha=0.9)

    mean = df["damage"].mean()
    ax.axvline(mean, color=ACCENT_GOLD, linestyle="--", linewidth=2)

    note = f"μ={mean:.1f}  ·  n={len(df)}"
    if outliers > 0:
        note += f"  ·  {outliers} outliers hidden"
    if filters.get("class") and filters["class"] != "All":
        note += f"  ·  {filters['class']} only"
    ax.text(0.02, 0.98, note, transform=ax.transAxes,
            ha="left", va="top", color=MUTED, fontsize=9,
            bbox={"facecolor": PANEL_BG, "edgecolor": GRID, "alpha": 0.85,
                   "pad": 4, "boxstyle": "round,pad=0.4"})


def viz_damage_received(ax, filters):
    """Feature 2: Horizontal bar of damage received per enemy type (top-N)."""
    _clear_axis(ax)
    df = load_csv("damage_received")
    title = "2. Damage Received Per Enemy Type"
    top_n = filters.get("top_n", 10)
    style_axis(ax, title, xlabel="Total damage received", ylabel="")
    if df.empty or "enemy_type" not in df.columns:
        empty_message(ax); return

    df = apply_class_filter(df, filters.get("class"))
    if df.empty:
        empty_message(ax, "No data for this class"); return

    totals = df.groupby("enemy_type")["actual_damage"].sum().sort_values(ascending=False)
    total_count = len(totals)
    if top_n and top_n < len(totals):
        totals = totals.head(top_n)
        subtitle = f"(Top {top_n} of {total_count})"
    else:
        subtitle = f"(All {total_count})"
    totals = totals.sort_values()  # horizontal bars read bottom-up

    colors = [ENEMY_COLORS.get(e, MUTED) for e in totals.index]
    bars = ax.barh(totals.index, totals.values, color=colors, edgecolor=BG)
    for bar, v in zip(bars, totals.values):
        ax.text(v, bar.get_y() + bar.get_height() / 2, f" {int(v)}",
                ha="left", va="center", color=FG, fontsize=10, fontweight="bold")
    ax.tick_params(axis="y", length=0, labelsize=10)
    xlim = ax.get_xlim()
    ax.set_xlim(0, xlim[1] * 1.15)
    ax.text(0.99, 0.02, subtitle, transform=ax.transAxes,
            ha="right", va="bottom", color=MUTED, fontsize=9,
            bbox={"facecolor": PANEL_BG, "edgecolor": GRID, "alpha": 0.85,
                   "pad": 3, "boxstyle": "round,pad=0.3"})


def viz_kills_per_level(ax, filters):
    """Feature 3: Stacked bar of kills per level range."""
    _clear_axis(ax)
    df = load_csv("kills_per_level")
    style_axis(ax, "3. Enemies Defeated Per Level Range",
                xlabel="Level range", ylabel="Enemies killed")
    if df.empty or "player_level" not in df.columns:
        empty_message(ax); return

    df = apply_class_filter(df, filters.get("class"))
    if df.empty:
        empty_message(ax, "No data for this class"); return

    df = df.copy()
    df["player_level"] = pd.to_numeric(df["player_level"], errors="coerce")
    df = df.dropna(subset=["player_level"])

    def level_range(lv):
        lv = int(lv)
        if lv <= 5:   return "1-5"
        if lv <= 10:  return "6-10"
        if lv <= 15:  return "11-15"
        if lv <= 20:  return "16-20"
        if lv <= 25:  return "21-25"
        return "26-30"
    df["range"] = df["player_level"].apply(level_range)

    pivot = df.groupby(["range", "enemy_type"]).size().unstack(fill_value=0)

    range_order = ["1-5", "6-10", "11-15", "16-20", "21-25", "26-30"]
    pivot = pivot.reindex([r for r in range_order if r in pivot.index])

    order = ["slime", "skeleton", "orc",
             "mini_boss_1", "mini_boss_2", "final_boss"]
    cols = [c for c in order if c in pivot.columns] + \
           [c for c in pivot.columns if c not in order]
    pivot = pivot[cols]

    colors = [ENEMY_COLORS.get(c, MUTED) for c in pivot.columns]
    pivot.plot(kind="bar", stacked=True, ax=ax, color=colors,
               edgecolor=BG, width=0.75)
    ax.legend(loc="upper right", fontsize=8, title="Enemy", title_fontsize=9,
              frameon=True, framealpha=0.85)
    ax.tick_params(axis="x", rotation=0, labelsize=10)


def _time_series_sessions(df, filters, value_col):
    """Helper: pick which sessions to plot in a time-series chart based on
    the 'sessions_n' filter. 0 means 'show all', otherwise top-N longest."""
    session_lengths = df.groupby("session_id")["game_time"].max().sort_values(ascending=False)
    show_n = filters.get("sessions_n", 5)
    if show_n <= 0 or show_n >= len(session_lengths):
        return list(session_lengths.index), len(session_lengths), "all"
    return session_lengths.head(show_n).index.tolist(), len(session_lengths), f"top{show_n}"


def viz_hp_over_time(ax, filters):
    """Feature 4: Line chart of HP over time."""
    _clear_axis(ax)
    df = load_csv("hp_over_time")
    style_axis(ax, "4. Player HP Over Time",
                xlabel="Game time (s)", ylabel="HP ratio (0-1)")
    if df.empty or "game_time" not in df.columns:
        empty_message(ax); return

    df = apply_class_filter(df, filters.get("class"))
    if df.empty:
        empty_message(ax, "No data for this class"); return

    df = df.copy()
    df["game_time"] = pd.to_numeric(df["game_time"], errors="coerce")
    df["hp_ratio"] = pd.to_numeric(df["hp_ratio"], errors="coerce")
    df = df.dropna(subset=["game_time", "hp_ratio"])
    if df.empty:
        empty_message(ax); return

    sessions, total_sessions, mode = _time_series_sessions(df, filters, "hp_ratio")

    palette = [ACCENT_RED, ACCENT_BLUE, ACCENT_GREEN,
               ACCENT_PURPLE, ACCENT_ORANGE, ACCENT_GOLD]
    for i, sid in enumerate(sessions):
        sub = df[df["session_id"] == sid].sort_values("game_time")
        if "player_name" in sub.columns:
            names = sub["player_name"].dropna().unique()
            names = [n for n in names if n and str(n).strip()]
            label = str(names[0]) if names else f"Session {str(sid)[-4:]}"
        else:
            label = f"Session {str(sid)[-4:]}"

        # When showing all sessions, fade individual lines so the crowd
        # doesn't turn into a wall of color
        alpha = 0.9 if mode != "all" else max(0.15, min(0.6, 30.0 / len(sessions)))
        lw = 2 if mode != "all" else 1

        ax.plot(sub["game_time"], sub["hp_ratio"],
                color=palette[i % len(palette)], alpha=alpha,
                linewidth=lw, label=label if mode != "all" else None)

    ax.set_ylim(0, 1.05)
    if mode != "all":
        ax.legend(loc="lower left", fontsize=9,
                  title=f"Showing {len(sessions)} / {total_sessions} sessions",
                  title_fontsize=9, frameon=True, framealpha=0.85)
    else:
        ax.text(0.02, 0.02,
                f"Showing ALL {total_sessions} sessions",
                transform=ax.transAxes, color=MUTED, fontsize=9,
                bbox={"facecolor": PANEL_BG, "edgecolor": GRID, "alpha": 0.85,
                      "pad": 3, "boxstyle": "round,pad=0.3"})


def viz_skill_usage(ax, filters):
    """Feature 5: Stacked bar of skill usage per class."""
    _clear_axis(ax)
    df = load_csv("skill_usage")
    style_axis(ax, "5. Skill Usage Frequency (by class)",
                xlabel="Class", ylabel="Uses")
    if df.empty or "player_class" not in df.columns:
        empty_message(ax); return

    df = apply_class_filter(df, filters.get("class"))
    if df.empty:
        empty_message(ax, "No data for this class"); return

    pivot = df.groupby(["player_class", "skill_name"]).size().unstack(fill_value=0)
    cols = [c for c in ["attack", "skill"] if c in pivot.columns]
    cols += [c for c in pivot.columns if c not in cols]
    pivot = pivot[cols]
    skill_palette = {"attack": ACCENT_BLUE, "skill": ACCENT_GOLD}
    colors = [skill_palette.get(c, MUTED) for c in pivot.columns]
    pivot.plot(kind="bar", stacked=True, ax=ax, color=colors,
               edgecolor=BG, width=0.65)
    ax.legend(title="Click type", fontsize=9, title_fontsize=9)
    ax.tick_params(axis="x", rotation=0)


def viz_session_outcomes(ax, filters):
    """Feature 6: Donut chart showing win rate + summary."""
    _clear_axis(ax)
    df = load_csv("session_outcomes")
    style_axis(ax, "6. Session Outcomes")
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    if df.empty or "won" not in df.columns:
        empty_message(ax); return

    df = apply_class_filter(df, filters.get("class"))
    if df.empty:
        empty_message(ax, "No data for this class"); return

    df = df.copy()
    df["won_str"] = df["won"].astype(str).str.lower().map(
        {"true": "Victory", "false": "Defeat"})

    counts = df["won_str"].value_counts()
    if counts.empty:
        empty_message(ax); return
    colors_map = {"Victory": ACCENT_GOLD, "Defeat": ACCENT_RED}
    colors = [colors_map.get(k, MUTED) for k in counts.index]

    wedges, texts, autotexts = ax.pie(
        counts.values, labels=counts.index, colors=colors,
        autopct="%1.0f%%", startangle=90,
        textprops={"color": FG, "fontsize": 11, "fontweight": "bold"},
        wedgeprops={"edgecolor": BG, "linewidth": 2, "width": 0.38},
        pctdistance=0.82,
    )
    for t in autotexts:
        t.set_color(BG)
        t.set_fontweight("bold")

    n = len(df)
    wins = int((df["won_str"] == "Victory").sum())
    win_rate = wins / n * 100 if n > 0 else 0
    ax.text(0, 0.08, f"{win_rate:.0f}%", ha="center", va="center",
            color=ACCENT_GOLD, fontsize=22, fontweight="bold")
    ax.text(0, -0.13, "win rate", ha="center", va="center",
            color=MUTED, fontsize=9)

    df["time_survived"] = pd.to_numeric(df.get("time_survived"), errors="coerce")
    df["final_level"] = pd.to_numeric(df.get("final_level"), errors="coerce")
    avg_level = df["final_level"].mean()
    avg_time = df["time_survived"].mean()
    class_note = ""
    if filters.get("class") and filters["class"] != "All":
        class_note = f" · {filters['class']} only"
    stats_text = (f"{n} sessions · {wins} wins{class_note}\n"
                   f"avg Lv.{avg_level:.1f} · {avg_time:.0f}s survived")
    ax.text(0.5, -0.17, stats_text, transform=ax.transAxes,
            ha="center", va="top", color=MUTED, fontsize=9)


def viz_exp_over_time(ax, filters):
    """Feature 7: Cumulative EXP over time per session."""
    _clear_axis(ax)
    df = load_csv("exp_over_time")
    style_axis(ax, "7. EXP Earned Over Time",
                xlabel="Game time (s)", ylabel="Cumulative EXP")
    if df.empty or "game_time" not in df.columns:
        empty_message(ax); return

    df = apply_class_filter(df, filters.get("class"))
    if df.empty:
        empty_message(ax, "No data for this class"); return

    df = df.copy()
    df["game_time"] = pd.to_numeric(df["game_time"], errors="coerce")
    df = df.dropna(subset=["game_time"])

    if "event_type" in df.columns:
        gains = df[df["event_type"] == "gain"].copy()
    elif "exp_gained" in df.columns:
        gains = df.copy()
        gains["exp_gained"] = pd.to_numeric(gains["exp_gained"], errors="coerce").fillna(0)
        gains = gains[gains["exp_gained"] > 0]
    else:
        gains = df.copy()

    if gains.empty or "exp_gained" not in gains.columns:
        empty_message(ax, "No EXP data available"); return

    gains["exp_gained"] = pd.to_numeric(gains["exp_gained"], errors="coerce").fillna(0)

    sessions, total_sessions, mode = _time_series_sessions(gains, filters, "exp_gained")

    palette = [ACCENT_RED, ACCENT_BLUE, ACCENT_GREEN,
               ACCENT_PURPLE, ACCENT_ORANGE, ACCENT_GOLD]
    for i, sid in enumerate(sessions):
        sub = gains[gains["session_id"] == sid].sort_values("game_time").copy()
        sub["cumulative"] = sub["exp_gained"].cumsum()

        if "player_name" in sub.columns:
            names = sub["player_name"].dropna().unique()
            names = [n for n in names if n and str(n).strip()]
            label = str(names[0]) if names else f"Session {str(sid)[-4:]}"
        else:
            label = f"Session {str(sid)[-4:]}"

        alpha = 0.9 if mode != "all" else max(0.15, min(0.6, 30.0 / len(sessions)))
        lw = 2 if mode != "all" else 1

        ax.plot(sub["game_time"], sub["cumulative"],
                color=palette[i % len(palette)], alpha=alpha,
                linewidth=lw, label=label if mode != "all" else None)
        if mode != "all":
            ax.scatter(sub["game_time"], sub["cumulative"],
                       color=palette[i % len(palette)], s=15, alpha=0.5,
                       edgecolor="none")

    if mode != "all":
        title = (f"Showing {len(sessions)} / {total_sessions} sessions"
                 if total_sessions > len(sessions) else None)
        ax.legend(loc="upper left", fontsize=9, title=title, title_fontsize=9,
                  frameon=True, framealpha=0.85)
    else:
        ax.text(0.02, 0.98,
                f"Showing ALL {total_sessions} sessions",
                transform=ax.transAxes, color=MUTED, fontsize=9,
                va="top",
                bbox={"facecolor": PANEL_BG, "edgecolor": GRID, "alpha": 0.85,
                      "pad": 3, "boxstyle": "round,pad=0.3"})


def viz_death_cause(ax, filters):
    """Feature 8: Donut chart of what killed the player (top-N killers)."""
    _clear_axis(ax)
    df = load_csv("death_cause")
    style_axis(ax, "8. Player Death Causes")
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    if df.empty or "killer_type" not in df.columns:
        empty_message(ax, "No deaths recorded"); return

    df = apply_class_filter(df, filters.get("class"))
    if df.empty:
        empty_message(ax, "No deaths for this class"); return

    counts = df["killer_type"].value_counts()
    top_n = filters.get("top_n", 10)
    if top_n and top_n < len(counts):
        top = counts.head(top_n)
        other_sum = counts.iloc[top_n:].sum()
        if other_sum > 0:
            top = pd.concat([top, pd.Series({"other": int(other_sum)})])
        counts = top

    colors = [ENEMY_COLORS.get(k, MUTED) for k in counts.index]
    wedges, texts, autotexts = ax.pie(
        counts.values, labels=counts.index, colors=colors,
        autopct="%1.0f%%", startangle=90,
        textprops={"color": FG, "fontsize": 10, "fontweight": "bold"},
        wedgeprops={"edgecolor": BG, "linewidth": 2, "width": 0.38},
        pctdistance=0.82,
    )
    for t in autotexts:
        t.set_color(BG)
        t.set_fontweight("bold")

    ax.text(0, 0.05, f"{len(df)}", ha="center", va="center",
            color=ACCENT_RED, fontsize=22, fontweight="bold")
    ax.text(0, -0.12, "deaths", ha="center", va="center",
            color=MUTED, fontsize=9)

    top_killer = counts.index[0]
    top_pct = counts.values[0] / counts.sum() * 100
    ax.text(0.5, -0.15, f"Most deadly: {top_killer} ({top_pct:.0f}%)",
            transform=ax.transAxes, ha="center", va="top",
            color=MUTED, fontsize=9)


def viz_leaderboard(ax, filters):
    """Bonus: Top-N leaderboard — best session per player."""
    _clear_axis(ax)
    df = load_csv("leaderboard")
    top_n = filters.get("top_n", 10)
    style_axis(ax, f"Leaderboard — Top {top_n} Players")
    if df.empty or "player_name" not in df.columns:
        empty_message(ax); return

    df_sorted = df.copy()
    df_sorted = apply_class_filter(df_sorted, filters.get("class"))
    if df_sorted.empty:
        empty_message(ax, "No data for this class"); return

    df_sorted["peak_level"] = df_sorted["peak_level"].astype(int)
    df_sorted["total_kills"] = df_sorted["total_kills"].astype(int)
    df_sorted["total_damage_dealt"] = df_sorted["total_damage_dealt"].astype(int)

    session_counts = df_sorted["player_name"].value_counts().to_dict()

    df_sorted = df_sorted.sort_values(
        ["peak_level", "total_kills", "total_damage_dealt"],
        ascending=[False, False, False])
    df_sorted = df_sorted.drop_duplicates(subset=["player_name"], keep="first")
    df_sorted = df_sorted.head(top_n)

    ax.axis("off")
    headers = ["#", "Player", "Lv.", "Kills", "Dmg", "Bosses", "Games"]
    rows = []
    for i, (_, r) in enumerate(df_sorted.iterrows(), 1):
        name = str(r.get("player_name", "?"))
        rows.append([
            f"{i}",
            name[:12],
            f"{int(r['peak_level'])}",
            f"{int(r['total_kills'])}",
            f"{int(r['total_damage_dealt'])}",
            f"{int(r.get('boss_kills', 0))}",
            f"{session_counts.get(name, 1)}",
        ])

    if not rows:
        empty_message(ax); return

    table = ax.table(cellText=rows, colLabels=headers,
                     loc="center", cellLoc="center", colLoc="center")
    table.auto_set_font_size(False)
    # Shrink font slightly when showing a lot of rows so the table still fits
    if top_n <= 10:
        fontsize, scale_y = 10, 1.6
    elif top_n <= 20:
        fontsize, scale_y = 9, 1.25
    else:
        fontsize, scale_y = 8, 1.0
    table.set_fontsize(fontsize)
    table.scale(1, scale_y)

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor(GRID)
        if row == 0:
            cell.set_facecolor(ACCENT_GOLD)
            cell.set_text_props(color=BG, fontweight="bold")
        else:
            cell.set_facecolor(PANEL_BG if row % 2 else "#2a2531")
            cell.set_text_props(color=FG)
            if col == 0 and row <= 3:
                medal_colors = ["#FFD700", "#C0C0C0", "#CD7F32"]
                cell.set_text_props(color=medal_colors[row - 1],
                                     fontweight="bold")


# ---------- Main dashboard ----------

VIZ_CONFIGS = [
    ("damage_dealt",      viz_damage_dealt),
    ("damage_received",   viz_damage_received),
    ("kills_per_level",   viz_kills_per_level),
    ("hp_over_time",      viz_hp_over_time),
    ("skill_usage",       viz_skill_usage),
    ("session_outcomes",  viz_session_outcomes),
    ("exp_over_time",     viz_exp_over_time),
    ("death_cause",       viz_death_cause),
    ("leaderboard",       viz_leaderboard),
]


def _default_filters():
    return {"top_n": 10, "sessions_n": 5, "class": "All"}


def build_static_dashboard(filters=None):
    """Build a non-interactive dashboard (used by --save and --nogui)."""
    if filters is None:
        filters = _default_filters()

    fig = plt.figure(figsize=(18, 12))
    fig.suptitle("DEADLINE DUNGEON — Data Dashboard",
                 fontsize=18, color=ACCENT_GOLD, fontweight="bold", y=0.995)

    for i, (name, func) in enumerate(VIZ_CONFIGS):
        ax = fig.add_subplot(3, 3, i + 1)
        try:
            func(ax, filters)
        except Exception as e:
            print(f"  [!] Error rendering {name}: {e}")
            empty_message(ax, f"Error: {e}")

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    return fig


def build_interactive_dashboard():
    """Build an interactive dashboard with sliders / radio buttons / reset
    for filtering the views on the fly."""
    filters = _default_filters()

    # Figure is wider to make room for a control column on the right
    fig = plt.figure(figsize=(20, 12))
    fig.suptitle("DEADLINE DUNGEON — Data Dashboard",
                 fontsize=18, color=ACCENT_GOLD, fontweight="bold", y=0.995)

    # Leave right 14% for controls
    gs_left = fig.add_gridspec(3, 3, left=0.04, right=0.78,
                                top=0.94, bottom=0.07, hspace=0.45, wspace=0.30)
    chart_axes = []
    for i, (name, func) in enumerate(VIZ_CONFIGS):
        r, c = divmod(i, 3)
        ax = fig.add_subplot(gs_left[r, c])
        chart_axes.append((name, func, ax))

    def redraw():
        for name, func, ax in chart_axes:
            try:
                func(ax, filters)
            except Exception as e:
                print(f"  [!] Error rendering {name}: {e}")
                empty_message(ax, f"Error: {e}")
        fig.canvas.draw_idle()

    # ── Controls panel on the right ─────────────────────────────────────
    ctrl_left = 0.82
    ctrl_width = 0.15

    # Helper to build a consistently-styled axes for a widget
    def make_ctrl_ax(y, height, label_above=None):
        ax = fig.add_axes([ctrl_left, y, ctrl_width, height])
        ax.set_facecolor(PANEL_BG)
        for spine in ax.spines.values():
            spine.set_color(GRID)
        if label_above:
            fig.text(ctrl_left, y + height + 0.012, label_above,
                     color=ACCENT_GOLD, fontsize=11, fontweight="bold")
        return ax

    # Panel title
    fig.text(ctrl_left + ctrl_width / 2, 0.965, "CONTROLS",
             color=ACCENT_GOLD, fontsize=13, fontweight="bold",
             ha="center")

    # ── Top-N slider (leaderboard / death cause / damage received) ──────
    slider_top_ax = make_ctrl_ax(0.88, 0.03,
                                  label_above="Top-N (board / deaths / dmg)")
    slider_top = Slider(slider_top_ax, "", 3, 30,
                         valinit=filters["top_n"], valstep=1,
                         color=ACCENT_GOLD, initcolor="none",
                         track_color=GRID)
    slider_top.label.set_color(FG)
    slider_top.valtext.set_color(FG)

    def _on_top_n(val):
        filters["top_n"] = int(val)
        redraw()
    slider_top.on_changed(_on_top_n)

    # ── Sessions slider (HP / EXP time series). 0 means "All" ──────────
    # For usability, we use valmax = 20 and label specially.
    slider_sess_ax = make_ctrl_ax(0.78, 0.03,
                                   label_above="Time-series sessions (0 = All)")
    slider_sess = Slider(slider_sess_ax, "", 0, 20,
                          valinit=filters["sessions_n"], valstep=1,
                          color=ACCENT_BLUE, initcolor="none",
                          track_color=GRID)
    slider_sess.label.set_color(FG)
    slider_sess.valtext.set_color(FG)

    def _on_sessions(val):
        filters["sessions_n"] = int(val)
        redraw()
    slider_sess.on_changed(_on_sessions)

    # ── Class filter radio buttons ──────────────────────────────────────
    radio_ax = make_ctrl_ax(0.55, 0.18, label_above="Filter by class")
    radio_ax.set_facecolor(PANEL_BG)
    labels = ("All", "Soldier", "Knight", "Wizard", "Archer")
    radio = RadioButtons(radio_ax, labels,
                          active=0, activecolor=ACCENT_GOLD)
    for circle in radio.circles if hasattr(radio, "circles") else []:
        circle.set_edgecolor(FG)
    for lbl in radio.labels:
        lbl.set_color(FG)
        lbl.set_fontsize(10)

    def _on_class(cls):
        filters["class"] = cls
        redraw()
    radio.on_clicked(_on_class)

    # ── Reset button ────────────────────────────────────────────────────
    reset_ax = make_ctrl_ax(0.45, 0.045)
    reset_btn = Button(reset_ax, "Reset filters",
                        color=PANEL_BG, hovercolor="#3a3342")
    reset_btn.label.set_color(ACCENT_GOLD)
    reset_btn.label.set_fontweight("bold")

    def _on_reset(event):
        defaults = _default_filters()
        filters.update(defaults)
        slider_top.set_val(defaults["top_n"])
        slider_sess.set_val(defaults["sessions_n"])
        radio.set_active(0)
        redraw()
    reset_btn.on_clicked(_on_reset)

    # ── Save current view button ────────────────────────────────────────
    save_ax = make_ctrl_ax(0.38, 0.045)
    save_btn = Button(save_ax, "Save snapshot PNG",
                       color=PANEL_BG, hovercolor="#3a3342")
    save_btn.label.set_color(ACCENT_BLUE)
    save_btn.label.set_fontweight("bold")

    def _on_save(event):
        os.makedirs(OUT_DIR, exist_ok=True)
        path = os.path.join(OUT_DIR, "dashboard_snapshot.png")
        fig.savefig(path, dpi=110, facecolor=BG)
        print(f"  Saved snapshot: {path}")
    save_btn.on_clicked(_on_save)

    # ── Quick tips text ─────────────────────────────────────────────────
    tips = (
        "Tips:\n"
        " • Drag sliders to adjust\n"
        " • Click a class to filter\n"
        "   all relevant charts\n"
        " • Sessions = 0 → show ALL\n"
        "   sessions on time charts\n"
        " • Matplotlib toolbar (bottom\n"
        "   left) for zoom & pan"
    )
    fig.text(ctrl_left, 0.10, tips, color=MUTED, fontsize=9,
             va="bottom", ha="left",
             bbox={"facecolor": PANEL_BG, "edgecolor": GRID,
                   "pad": 6, "boxstyle": "round,pad=0.4"})

    # Keep references on the figure so widgets aren't garbage collected
    fig._dd_widgets = (slider_top, slider_sess, radio, reset_btn, save_btn)

    # Initial render
    redraw()
    return fig


def save_individual_charts():
    """Save each chart as its own PNG in the screenshots/visualization/ folder."""
    os.makedirs(OUT_DIR, exist_ok=True)
    filters = _default_filters()
    saved = []
    for name, func in VIZ_CONFIGS:
        fig, ax = plt.subplots(figsize=(8, 6))
        try:
            func(ax, filters)
            path = os.path.join(OUT_DIR, f"{name}.png")
            fig.tight_layout()
            fig.savefig(path, dpi=110, facecolor=BG)
            saved.append(path)
            print(f"  Saved: {path}")
        except Exception as e:
            print(f"  [!] Failed {name}: {e}")
        plt.close(fig)
    return saved


def save_dashboard():
    """Save the full dashboard as one PNG."""
    os.makedirs(OUT_DIR, exist_ok=True)
    fig = build_static_dashboard()
    path = os.path.join(OUT_DIR, "dashboard.png")
    fig.savefig(path, dpi=110, facecolor=BG)
    plt.close(fig)
    print(f"  Saved: {path}")
    return path


def print_summary():
    """Print a quick text summary of the data."""
    print()
    print("=" * 60)
    print("DATA SUMMARY")
    print("=" * 60)
    for name, _ in VIZ_CONFIGS:
        df = load_csv(name)
        if df.empty:
            print(f"  {name:22s}: (no data)")
        else:
            print(f"  {name:22s}: {len(df):5d} rows")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Generate data visualizations from Deadline Dungeon CSVs")
    parser.add_argument("--save", action="store_true",
                        help="Save charts to " + OUT_DIR + "/")
    parser.add_argument("--nogui", action="store_true",
                        help="Don't open interactive window (use with --save)")
    parser.add_argument("--summary", action="store_true",
                        help="Print data summary only")
    args = parser.parse_args()

    apply_style()

    if not os.path.isdir(DATA_DIR):
        print(f"Error: '{DATA_DIR}/' not found.")
        print("Run the game first to generate statistics, or check working dir.")
        sys.exit(1)

    print(f"Reading data from '{DATA_DIR}/'...")
    print_summary()

    if args.summary:
        return

    if args.save:
        print("\nSaving individual charts...")
        save_individual_charts()
        print("\nSaving dashboard...")
        save_dashboard()

    if not args.nogui:
        print("\nOpening interactive dashboard...")
        print("  ↳ Use the sliders on the right to filter the data.")
        build_interactive_dashboard()
        plt.show()


if __name__ == "__main__":
    main()
