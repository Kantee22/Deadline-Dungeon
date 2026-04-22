# Deadline Dungeon - Data Visualization

This document describes the data components of Deadline Dungeon. The game collects 8 features of gameplay data plus an aggregated leaderboard, and presents them in an interactive dashboard (`visualize.py`).

All data is stored as CSV files in the `stats_data/` folder, with one file per feature. Each row contains `session_id`, `player_name`, and `timestamp` so data from different sessions can be joined and compared.

## Dashboard Overview

![Dashboard overview](overview.png)

The interactive dashboard shows every feature on a single page, styled with a dark dungeon theme. On the right side is a control panel with a **Top-N slider** (controls how many rows appear in the leaderboard, death causes, and damage-received charts), a **Sessions slider** (controls how many recent sessions are drawn on the HP/EXP time-series charts; setting it to 0 shows all), a **Class filter** (restricts damage and skill data to one player class), a **Reset** button, and a **Save snapshot** button that exports the current view as a PNG. All charts refresh live when any control is moved.

## 1. Leaderboard

![Leaderboard](leaderboard.png)

The leaderboard is a horizontal bar chart showing the Top-N sessions ranked first by peak level reached, then by total kills, then by total damage dealt. Each bar is labeled with the player's name and level, and colored by the player's class for quick visual comparison. This component is used to compare performance across players and highlight the most successful runs. The number of bars shown adjusts with the Top-N slider.

## 2. Kills Per Level

![Kills per level](kills_per_level.png)

This stacked bar chart breaks down enemy kills by player level. Each bar represents one level band, with segments colored by enemy type (slime, skeleton, orc, and bosses). It reveals how enemy composition shifts as the player levels up: early levels are dominated by slimes, the mid-game by skeletons, and the late game by orcs and bosses. It also shows which levels the player spends the most time on.

## 3. Damage Dealt by Class

![Damage dealt by class](damage_dealt.png)

A histogram of individual damage hits, grouped by player class (Soldier, Knight, Wizard, Archer). Each class appears as its own colored distribution so the player can see the damage profile of each class: Wizard and Archer have higher peaks (big-hit projectiles), while Soldier and Knight have flatter distributions centered on lower values (consistent melee damage). The class filter on the control panel restricts this chart to a single class.

## 4. Damage Received

![Damage received](damage_received.png)

A horizontal bar chart of the top enemies by total damage dealt to the player, showing which monsters are the biggest threats. Each bar is labeled with the enemy type and colored by the same palette as the kills chart. The Top-N slider changes how many enemy types are displayed.

## 5. HP Over Time

![HP over time](hp_over_time.png)

A time-series line chart showing the player's HP ratio (current_hp / max_hp) across the 10-minute session, sampled every 2 seconds. Multiple sessions are overlaid as transparent lines so the shape of a typical run is visible, with the most recent sessions drawn more prominently. This chart is useful for spotting dangerous moments in the run (HP dips) and for comparing survival patterns between sessions. The Sessions slider controls how many sessions are drawn.

## 6. EXP Over Time

![EXP over time](exp_over_time.png)

A time-series line chart showing cumulative EXP gained over the session. Like the HP chart, multiple sessions are overlaid. Steep segments indicate fast leveling (usually during boss kills or dense spawns), while flat segments indicate idle or wandering time. The chart helps identify which strategies lead to the fastest progression.

## 7. Skill Usage (Hit Rate)

![Skill usage](skill_usage.png)

A grouped bar chart comparing the hit rate (percent of clicks that connect with an enemy) of basic attacks versus class skills, for each player class. It shows which classes land their attacks most reliably and whether the class skill is more or less accurate than the basic attack. Helpful for balancing class design and for spotting which abilities feel clumsy to aim.

## 8. Death Causes

![Death causes](death_cause.png)

A horizontal bar chart ranking the enemies that killed the player most often, across all recorded deaths. Each bar shows the count of deaths caused by that enemy type, and is colored by enemy. The Top-N slider changes the number of entries shown. Together with the damage-received chart, this reveals which enemies are truly dangerous (high damage) versus which ones merely chip at the player.

## 9. Session Outcomes (Win / Loss)

![Session outcomes](session_outcomes.png)

A pie chart summarizing win/loss ratio across all recorded sessions, split into categories: Victory (final boss defeated), Defeat (player died), and Timeout (10-minute deadline hit before final boss). It provides a high-level view of how often players successfully finish the run under the time pressure of the "deadline" theme.

## Data Source

All charts are generated from CSV files in `stats_data/`, produced automatically by `stats_collector.py` during gameplay. Stats are flushed to disk every 15 seconds (and at session end), so data is preserved even if the game crashes.

To regenerate the visualizations, run:

```
python visualize.py            # open interactive dashboard
python visualize.py --save     # export all charts as PNGs to screenshots/visualization/
python visualize.py --summary  # print a text summary to the console
```
