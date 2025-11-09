# Bug Report: Display Shows Vegas Win Totals Instead of Model Projections

## Issue

The playoff probabilities display is showing **Vegas preseason win totals** (from the "ratings" data structure) instead of **model-projected wins** (from the "playoffs" data structure).

## Current Display (INCORRECT)
```
Houston Texans:   AFC South, ELO 1642, 9.2 wins*, 19.1% playoff odds
Indianapolis Colts: AFC South, ELO 1635, 7.2 wins*, 84.9% playoff odds

*These are Vegas preseason totals, NOT model projections
```

This creates a nonsensical situation where:
- Team with MORE displayed "wins" (Texans 9.2) has LOWER playoff odds (19.1%)
- Team with FEWER displayed "wins" (Colts 7.2) has HIGHER playoff odds (84.9%)

## Actual Model Projections (CORRECT)
```
Houston Texans:   8.1 projected wins → 19.1% playoff odds ✓
Indianapolis Colts: 11.0 projected wins → 84.9% playoff odds ✓
```

## Root Cause

In `scripts/generate_full_webpage_data.py`:

**Line 67** creates a "ratings" structure:
```python
data["ratings"] = ratings_df[['team', 'conf', 'division', 'elo_rating', 'win_total']].to_dict('records')
```
- `win_total` = Vegas preseason over/under lines (static)

**Line 162** creates a "playoffs" structure:
```python
playoffs_records.append({
    ...
    'avg_wins': float(row['avg_wins']),  # Model projection
    ...
})
```
- `avg_wins` = Model's projected season-end wins (dynamic, updated weekly)

## The Bug

The frontend display is rendering:
- ELO from `playoffs.elo_rating` ✓
- **Win total from `ratings.win_total`** ✗ (Vegas preseason)
- Playoff % from `playoffs.playoff_prob_pct` ✓

It should be using `playoffs.avg_wins` instead of `ratings.win_total`.

## Fix Required

The display code needs to pull the wins column from the `playoffs` data structure:
```javascript
// WRONG
{team.conf} | {team.elo_rating} | {ratings[team].win_total} | {team.playoff_prob_pct}

// CORRECT
{team.conf} | {team.elo_rating} | {team.avg_wins} | {team.playoff_prob_pct}
```

## Data Validation

**Vegas Win Totals (preseason):**
- Colts: 7.2
- Texans: 9.2

**Model Projections (Week 10):**
- Colts: 11.0 (7-2 record + 3.3 expected future wins)
- Texans: 8.1 (3-5 record + 4.4 expected future wins)

**Playoff Odds:**
- Colts: 84.9% (makes sense with 11 wins)
- Texans: 19.1% (makes sense with 8 wins)

## Impact

High - Creates confusion about model accuracy and leads users to question basic model logic.
