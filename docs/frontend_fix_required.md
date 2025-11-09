# Frontend Fix Required - personal-site Repository

## Issue
The playoff probabilities table is displaying Vegas preseason win totals instead of model-projected wins.

## Data Structure Changes (COMPLETED in nfl-data-stack)

**Old structure:**
```json
{
  "ratings": [
    {"team": "Colts", "elo_rating": 1635, "win_total": 7.2}  // Vegas preseason
  ],
  "playoffs": [
    {"team": "Colts", "elo_rating": 1635, "avg_wins": 11.0}  // Model projection
  ]
}
```

**New structure:**
```json
{
  "ratings": [
    {"team": "Colts", "elo_rating": 1635, "vegas_preseason_total": 7.2}  // Renamed for clarity
  ],
  "playoffs": [
    {"team": "Colts", "elo_rating": 1635, "avg_wins": 11.0}  // Model projection
  ]
}
```

## Frontend Fix Needed

**Current (WRONG):**
```javascript
// Display is mixing data from both structures
<td>{team.conf}</td>
<td>{team.elo_rating}</td>
<td>{ratings[team].win_total}</td>        // ← WRONG: Vegas preseason
<td>{team.playoff_prob_pct}%</td>
```

**Fixed (CORRECT):**
```javascript
// All data should come from playoffs structure
<td>{playoffs[team].conf}</td>
<td>{playoffs[team].elo_rating}</td>
<td>{playoffs[team].avg_wins}</td>        // ← CORRECT: Model projection
<td>{playoffs[team].playoff_prob_pct}%</td>
```

## Files to Update in personal-site

Search for usages of:
- `ratings[...].win_total` → Replace with `playoffs[...].avg_wins`
- `vegas_preseason_total` → Do NOT use for display (reference only)

## Validation

After fix, the Colts/Texans rows should show:
```
Indianapolis Colts: AFC South, ELO 1635, 11.0 wins, 84.9% playoff odds  ✓
Houston Texans:     AFC South, ELO 1642, 8.1 wins, 19.1% playoff odds   ✓
```

NOT:
```
Indianapolis Colts: AFC South, ELO 1635, 7.2 wins, 84.9% playoff odds  ✗
Houston Texans:     AFC South, ELO 1642, 9.2 wins, 19.1% playoff odds  ✗
```
