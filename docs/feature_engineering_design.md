# Feature Engineering Design

## Overview

Enhance the ELO-based prediction model by incorporating contextual factors that impact game outcomes: rest days, weather conditions, and injury status.

## Data Sources

### nflreadpy Package
Using `nflreadpy` v0.1.4+ for all feature data:

1. **`load_schedules(years)`**:
   - Rest days: `away_rest`, `home_rest`
   - Weather: `temp`, `wind`, `roof`, `surface`
   - Stadium: `stadium_id`, `stadium`

2. **`load_injuries(years)`**:
   - Player-level injury reports by week
   - Practice status, game status
   - Injury types and severity

## Feature Design

### 1. Rest Days Adjustment

**Rationale**: Teams with more rest have better performance (fewer injuries, better preparation).

**Features**:
- `rest_diff`: Difference in rest days (home_rest - away_rest)
- Short week penalty: Games with <7 days rest (Thursday games)
- Long rest bonus: Games with >7 days rest (bye week, TNF after bye)

**ELO Adjustment**:
```python
rest_adjustment = rest_diff * 5.0  # 5 ELO points per day of rest advantage
# Cap at ±20 points to avoid over-weighting
rest_adjustment = max(-20, min(20, rest_adjustment))
```

**Expected Impact**:
- Team with 3 extra rest days → +15 ELO points
- Thursday game (3 days rest) vs Sunday (7 days) → -20 ELO points

### 2. Weather Adjustment (Outdoor Stadiums Only)

**Rationale**: Extreme weather conditions favor certain team styles and penalize passing/finesse teams.

**Applicability**:
- **Apply**: `roof == 'outdoors'` or `roof == 'open'`
- **Skip**: `roof == 'dome'` or `roof == 'closed'`

**Features**:

#### Temperature
- **Extreme cold**: temp < 32°F (freezing)
- **Moderate cold**: 32°F ≤ temp < 50°F
- **Ideal**: 50°F ≤ temp ≤ 75°F (no adjustment)
- **Hot**: temp > 75°F

**Formula**:
```python
if temp is None or roof in ('dome', 'closed'):
    temp_adjustment = 0
elif temp < 32:
    temp_adjustment = -10  # Extreme cold hurts both teams
elif temp < 50:
    temp_adjustment = -5   # Moderate cold
elif temp > 75:
    temp_adjustment = -3   # Heat
else:
    temp_adjustment = 0    # Ideal conditions
```

#### Wind
- **High wind**: wind ≥ 20 mph (impacts passing)
- **Moderate wind**: 10 ≤ wind < 20 mph
- **Low wind**: wind < 10 mph (no adjustment)

**Formula**:
```python
if wind is None or roof in ('dome', 'closed'):
    wind_adjustment = 0
elif wind >= 20:
    wind_adjustment = -15  # Severe wind
elif wind >= 10:
    wind_adjustment = -5   # Moderate wind
else:
    wind_adjustment = 0    # Calm
```

**Combined Weather Adjustment**:
```python
weather_adjustment = temp_adjustment + wind_adjustment
# Applied symmetrically to both teams (reduces overall scoring/passing)
```

### 3. Injury Adjustment

**Rationale**: Key player injuries significantly impact team strength, especially QB, star skill players.

**Aggregation**: Team-level injury impact score by position group

**Position Weights** (out of 100 total impact points):
- **QB**: 40 points
- **RB/WR/TE**: 5 points each (max 15 for skill positions)
- **OL**: 3 points each (max 15)
- **DL/LB**: 3 points each (max 15)
- **DB**: 2 points each (max 10)
- **K/P/LS**: 1 point each (max 5)

**Injury Status Multipliers**:
- **Out**: 1.0 (full weight)
- **Doubtful**: 0.75
- **Questionable**: 0.5
- **Did Not Participate**: 0.75
- **Limited Participation**: 0.4
- **Full Participation**: 0.0 (no impact)

**Formula**:
```python
def calculate_injury_impact(injuries_df, team, week):
    """
    Calculate team injury impact score for a specific week.

    Returns:
        injury_score: 0-100 (0 = healthy, 100 = decimated)
    """
    team_injuries = injuries_df.filter(
        (injuries_df['team'] == team) &
        (injuries_df['week'] == week)
    )

    impact = 0.0
    position_totals = {
        'QB': 0, 'RB': 0, 'WR': 0, 'TE': 0,
        'OL': 0, 'DL': 0, 'LB': 0, 'DB': 0,
        'ST': 0  # Special teams
    }

    for injury in team_injuries:
        status = injury['report_status']
        position_group = map_position(injury['position'])

        # Get status multiplier
        multiplier = STATUS_MULTIPLIERS.get(status, 0.5)

        # Get position weight (capped per group)
        weight = POSITION_WEIGHTS[position_group]

        # Add weighted impact (capped by position group max)
        if position_totals[position_group] < POSITION_CAPS[position_group]:
            impact += weight * multiplier
            position_totals[position_group] += weight * multiplier

    return min(100, impact)  # Cap at 100
```

**ELO Adjustment**:
```python
# Injury differential (positive = opponent more injured)
injury_diff = opponent_injury_score - team_injury_score

# Scale: 10 injury points = ~15 ELO points
injury_adjustment = injury_diff * 1.5

# Cap at ±60 ELO points
injury_adjustment = max(-60, min(60, injury_adjustment))
```

**Expected Impact**:
- QB out (40 points) → -60 ELO points
- Multiple starters out (60 points) → -90 ELO points (capped at -60)
- Healthy team vs injured opponent (+30 diff) → +45 ELO points

## Implementation Architecture

### Data Collection Layer

**Script**: `scripts/collect_enhanced_features.py`

```python
def collect_enhanced_features(seasons: list[int]) -> None:
    """Collect and merge rest, weather, and injury data."""

    # Load nflreadpy data
    schedules = nfl.load_schedules(seasons)
    injuries = nfl.load_injuries(seasons)

    # Process features
    enhanced = schedules.select([
        'game_id', 'season', 'week',
        'home_team', 'away_team',
        'home_rest', 'away_rest',
        'roof', 'temp', 'wind',
        'stadium_id', 'stadium'
    ])

    # Calculate injury scores per team-week
    injury_scores = calculate_team_injury_scores(injuries)

    # Join injury data
    enhanced = enhanced.join(
        injury_scores,
        left_on=['home_team', 'week'],
        right_on=['team', 'week'],
        how='left'
    ).rename({'injury_score': 'home_injury_score'})

    enhanced = enhanced.join(
        injury_scores,
        left_on=['away_team', 'week'],
        right_on=['team', 'week'],
        how='left'
    ).rename({'injury_score': 'away_injury_score'})

    # Export to CSV for dbt ingestion
    enhanced.write_csv('data/nfl/nfl_enhanced_features.csv')
```

### Transformation Layer (dbt)

**Model**: `models/nfl/prep/nfl_enhanced_features.sql`

```sql
-- Load enhanced features from CSV
{{ config(materialized='table') }}

select
    game_id,
    season,
    week,
    home_team,
    away_team,
    home_rest,
    away_rest,
    home_rest - away_rest as rest_diff,
    roof,
    temp,
    wind,
    home_injury_score,
    away_injury_score,
    away_injury_score - home_injury_score as injury_diff
from {{ source('nfl', 'enhanced_features') }}
```

**Model**: `models/nfl/prep/nfl_elo_adjustments.sql`

```sql
-- Calculate ELO adjustments from features
{{ config(materialized='table') }}

with features as (
    select * from {{ ref('nfl_enhanced_features') }}
),

adjustments as (
    select
        game_id,

        -- Rest adjustment (±20 cap)
        greatest(-20, least(20, rest_diff * 5.0)) as rest_adjustment,

        -- Weather adjustments (outdoor only)
        case
            when roof in ('dome', 'closed') then 0
            when temp is null then 0
            when temp < 32 then -10
            when temp < 50 then -5
            when temp > 75 then -3
            else 0
        end as temp_adjustment,

        case
            when roof in ('dome', 'closed') then 0
            when wind is null then 0
            when wind >= 20 then -15
            when wind >= 10 then -5
            else 0
        end as wind_adjustment,

        -- Injury adjustment (±60 cap)
        greatest(-60, least(60, injury_diff * 1.5)) as injury_adjustment

    from features
)

select
    game_id,
    rest_adjustment,
    temp_adjustment,
    wind_adjustment,
    temp_adjustment + wind_adjustment as weather_adjustment,
    injury_adjustment,
    rest_adjustment + temp_adjustment + wind_adjustment + injury_adjustment as total_adjustment
from adjustments
```

### ELO Integration

**Modify**: `models/nfl/prep/nfl_elo_rollforward.py`

```python
def calc_elo_diff_with_features(
    game_result: float,
    home_elo: float,
    visiting_elo: float,
    home_adv: float,
    scoring_margin: float,
    total_adjustment: float = 0.0,  # NEW
    k_factor: float = 20.0
) -> float:
    """
    Calculate ELO rating change with features.

    Parameters:
    - total_adjustment: Combined adjustment from rest/weather/injuries
                       (positive = favors home team)
    """
    # Apply feature adjustments to home advantage
    adjusted_home_adv = home_adv + total_adjustment

    # Rest of calculation stays the same
    adj_home_elo = home_elo + adjusted_home_adv
    winner_elo_diff = visiting_elo - adj_home_elo if game_result == 1 else adj_home_elo - visiting_elo

    margin_of_victory_multiplier = math.log(abs(scoring_margin) + 1) * (2.2 / (winner_elo_diff * 0.001 + 2.2))
    expected_visiting_win = 1.0 / (10.0 ** (-(visiting_elo - home_elo - adjusted_home_adv) / 400.0) + 1.0)
    elo_change = k_factor * (game_result - expected_visiting_win) * margin_of_victory_multiplier

    return elo_change
```

## Validation Strategy

### Temporal Cross-Validation

Run modified temporal CV to compare:
1. **Baseline**: Current ELO-only model (Brier 0.2261, Accuracy 64.4%)
2. **+Rest**: ELO + rest days
3. **+Weather**: ELO + rest + weather
4. **+Injuries**: ELO + rest + weather + injuries (full model)

**Success Criteria**:
- Brier score improvement > 0.01 (e.g., 0.2261 → 0.2161)
- Accuracy improvement > 2% (64.4% → 66.4%+)
- Log loss reduction
- Calibration slope closer to 1.0

### A/B Testing

Compare predictions for Week 10 2024:
- Baseline ELO predictions
- Feature-enhanced predictions
- Analyze differences in high-leverage games (close matchups)

### Feature Importance

Track individual feature contributions:
```python
# Per game, log feature adjustments
game_adjustments = {
    'rest': rest_adjustment,
    'weather': weather_adjustment,
    'injuries': injury_adjustment,
    'total': total_adjustment
}

# Aggregate statistics
- Mean absolute adjustment by feature
- Games where features changed prediction
- Correlation between features and prediction error
```

## Expected Results

### Predictions

**Conservative Estimate**:
- Brier score: 0.2261 → 0.215 (6% improvement)
- Accuracy: 64.4% → 66.0% (+1.6%)

**Optimistic Estimate**:
- Brier score: 0.2261 → 0.205 (9% improvement)
- Accuracy: 64.4% → 68.0% (+3.6%)

### Feature Impact Rankings

Based on research literature:
1. **Injuries** (highest impact): QB injuries alone swing games 7-10 points
2. **Rest Days**: Thursday games historically underperform by 2-3 points
3. **Weather**: Extreme conditions (wind 20+ mph) impact spreads by 3-5 points

## Rollout Plan

1. **Phase 1** (Current): Design and data collection setup
2. **Phase 2**: Implement rest days only → validate improvement
3. **Phase 3**: Add weather features → incremental validation
4. **Phase 4**: Add injury features → full model validation
5. **Phase 5**: Temporal CV comparison and documentation
6. **Phase 6**: Deploy to production predictions

## Open Questions

1. Should injury adjustment be symmetric (hurt both teams) or asymmetric (relative advantage)?
   - **Proposal**: Asymmetric - injury differential impacts expected win probability

2. Weather adjustment: Should it reduce both teams' effective ELO or create relative advantage?
   - **Proposal**: Symmetric reduction (both teams impacted by wind/cold)

3. How to handle missing weather data (12% of outdoor games)?
   - **Proposal**: Impute using historical stadium averages for that week/month

4. Position mapping: How to categorize hybrid positions (FB, slot WR, etc.)?
   - **Proposal**: Use broad categories (RB includes FB, WR includes slot)

## References

- FiveThirtyEight: "How Our NFL Predictions Work"
- Sharp Football Analysis: Weather impact studies
- Pro Football Reference: Injury reports and rest day analysis
- nflreadpy documentation: https://nflreadpy.nflverse.com/
