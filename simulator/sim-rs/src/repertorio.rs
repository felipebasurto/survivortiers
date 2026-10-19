//! Repertorio + Veto opening, as an expected value over the starter sweep.
//!
//! Game (JPTER78/pokesurvivor @ 5bbc3b2): upgrades.js:15 and :18, perks at :42 and :45,
//! the random second attack at game.js:120-128, slot switching at game.js:554 and
//! player.js:148, melee damage taken only while melee is active at player.js:238.
//!
//! The second attack is uniform over the non-buff pool. The player bans up to 3 moves
//! that pull that expectation down and then plays the better of the two. The value of a
//! draw is the better move's solo median from the starter sweep, not a fresh two-move sim.
//! One switch at the start is a single 35% cooldown clamp, so the rest of the run is that
//! move's solo survival.

use crate::data::Data;
use std::collections::HashMap;

pub const BANS: usize = 3;

#[derive(Clone, Debug)]
pub struct OpeningMove {
    pub id: String,
    pub kind: String,
    pub median: f64,
    pub lo: f64,
    pub hi: f64,
    /// Composite score from the sweep. Absent means compare `median` seconds.
    pub rank: Option<f64>,
    pub rank_lo: Option<f64>,
    pub rank_hi: Option<f64>,
}

fn value_of(m: &OpeningMove) -> f64 {
    m.rank.unwrap_or(m.median)
}

#[derive(Clone, Debug, PartialEq)]
pub struct Opening {
    pub median: f64,
    pub lo: f64,
    pub hi: f64,
    /// (rank, rank_lo, rank_hi) when the sweep carries a composite score.
    pub rank: Option<(f64, f64, f64)>,
    pub banned: Vec<String>,
    pub draws: usize,
    pub melee_locked: bool,
}

fn round3(x: f64) -> f64 {
    (x * 1000.0).round() / 1000.0
}

/// Mean over the draws of the band of whichever move is played, rounded, with the
/// interval clamped around the median.
fn expectation(starter: &OpeningMove, pool: &[&OpeningMove], band: impl Fn(&OpeningMove) -> (f64, f64, f64)) -> (f64, f64, f64) {
    let (mut sm, mut sl, mut sh) = (0.0, 0.0, 0.0);
    for c in pool {
        let (m, l, h) = if value_of(c) > value_of(starter) { band(c) } else { band(starter) };
        sm += m;
        sl += l;
        sh += h;
    }
    let n = pool.len() as f64;
    let (m, mut l, mut h) = (round3(sm / n), round3(sl / n), round3(sh / n));
    if l > m {
        l = m;
    }
    if h < m {
        h = m;
    }
    (m, l, h)
}

pub fn opening_value(starter: &OpeningMove, candidates: &[OpeningMove], bans: usize) -> Opening {
    let mut pool: Vec<&OpeningMove> = candidates.iter().filter(|c| c.id != starter.id).collect();
    pool.sort_by(|a, b| a.id.cmp(&b.id));
    let n_ban = bans.min(pool.len().saturating_sub(1));
    let mut banned: Vec<&OpeningMove> = Vec::new();
    for _ in 0..n_ban {
        let mut worst = 0;
        for i in 1..pool.len() {
            let vw = value_of(starter).max(value_of(pool[worst]));
            let vi = value_of(starter).max(value_of(pool[i]));
            if vi < vw || (vi == vw && pool[i].id < pool[worst].id) {
                worst = i;
            }
        }
        banned.push(pool.remove(worst));
    }
    banned.sort_by(|a, b| a.id.cmp(&b.id));
    pool.sort_by(|a, b| a.id.cmp(&b.id));

    let played = pool.iter().any(|c| value_of(c) > value_of(starter));
    let (median, lo, hi) = if played {
        expectation(starter, &pool, |m| (m.median, m.lo, m.hi))
    } else {
        (starter.median, starter.lo, starter.hi)
    };
    let rank = starter.rank.map(|r| {
        let starter_band = (r, starter.rank_lo.unwrap_or(f64::NAN), starter.rank_hi.unwrap_or(f64::NAN));
        if played {
            expectation(starter, &pool, |m| {
                (m.rank.unwrap_or(f64::NAN), m.rank_lo.unwrap_or(f64::NAN), m.rank_hi.unwrap_or(f64::NAN))
            })
        } else {
            starter_band
        }
    });

    // Stuck on melee when no remaining draw is a strictly better non-melee attack.
    let melee_locked = starter.kind == "melee"
        && pool.iter().all(|c| !(c.kind != "melee" && value_of(c) > value_of(starter)));

    Opening {
        median,
        lo,
        hi,
        rank,
        banned: banned.into_iter().map(|c| c.id.clone()).collect(),
        draws: pool.len(),
        melee_locked,
    }
}

/// A blank cell reads as 0, a missing column as NaN.
fn num(cell: Option<&&str>) -> f64 {
    match cell {
        None => f64::NAN,
        Some(s) if s.trim().is_empty() => 0.0,
        Some(s) => s.trim().parse().unwrap_or(f64::NAN),
    }
}

/// dex -> move id -> row. A later row for the same move replaces an earlier one.
fn load_sweep(text: &str) -> HashMap<u32, HashMap<String, OpeningMove>> {
    let mut lines = text.lines().filter(|l| !l.is_empty() && !l.starts_with('#'));
    let header = lines.next().expect("sweep has no header");
    let ix: HashMap<&str, usize> = header.split(',').enumerate().map(|(i, c)| (c, i)).collect();
    let col = |name: &str| *ix.get(name).unwrap_or_else(|| panic!("sweep has no {name} column"));
    let (dex_c, start_c, kind_c) = (col("dex"), col("start"), col("kind"));
    let mut by_dex: HashMap<u32, HashMap<String, OpeningMove>> = HashMap::new();
    for line in lines.filter(|l| *l != header) {
        let p: Vec<&str> = line.split(',').collect();
        let at = |name: &str| ix.get(name).and_then(|&i| p.get(i));
        let score = at("median_score").filter(|s| !s.is_empty());
        let row = OpeningMove {
            id: p[start_c].to_string(),
            kind: p[kind_c].to_string(),
            median: num(at("median_s")),
            lo: num(at("boot_lo")),
            hi: num(at("boot_hi")),
            rank: score.map(|s| num(Some(s))),
            rank_lo: score.map(|_| num(at("score_lo"))),
            rank_hi: score.map(|_| num(at("score_hi"))),
        };
        let dex: u32 = p[dex_c].trim().parse().unwrap_or_else(|_| panic!("bad dex in {line}"));
        by_dex.entry(dex).or_default().insert(row.id.clone(), row);
    }
    by_dex
}

/// (dex, opening) for each (dex, game start move), in dex order. Panics when a species has
/// no starter row.
fn openings(starts: &[(u32, String)], sweep_text: &str) -> Vec<(u32, Opening)> {
    let sweep = load_sweep(sweep_text);
    let mut out: Vec<(u32, Opening)> = starts
        .iter()
        .map(|(dex, start)| {
            let rows = sweep.get(dex).filter(|r| r.contains_key(start));
            let rows = rows.unwrap_or_else(|| panic!("sweep has no starter for {dex} {start}"));
            let starter = rows[start].clone();
            let candidates: Vec<OpeningMove> = rows.values().filter(|r| r.id != *start && r.kind != "buff").cloned().collect();
            (*dex, opening_value(&starter, &candidates, BANS))
        })
        .collect();
    out.sort_by_key(|(dex, _)| *dex);
    out
}

pub fn openings_from_sweep(data: &Data, sweep_text: &str) -> Vec<(u32, Opening)> {
    let starts: Vec<(u32, String)> = data.dex.iter().map(|mon| (mon.dex, data.moves[mon.start].id.clone())).collect();
    openings(&starts, sweep_text)
}

/// The JSON array `make_definitive.py` reads: dex, median, lo, hi, banned, draws, meleeLocked,
/// and rank, rankLo, rankHi when the sweep carries a composite score.
pub fn to_json(openings: &[(u32, Opening)]) -> String {
    let rows: Vec<serde_json::Value> = openings
        .iter()
        .map(|(dex, o)| {
            let mut v = serde_json::json!({
                "dex": dex, "median": o.median, "lo": o.lo, "hi": o.hi,
                "banned": o.banned, "draws": o.draws, "meleeLocked": o.melee_locked,
            });
            if let Some((r, rl, rh)) = o.rank {
                v["rank"] = r.into();
                v["rankLo"] = rl.into();
                v["rankHi"] = rh.into();
            }
            v
        })
        .collect();
    serde_json::Value::Array(rows).to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn mov(v: &serde_json::Value) -> OpeningMove {
        OpeningMove {
            id: v["id"].as_str().unwrap().to_string(),
            kind: v["kind"].as_str().unwrap().to_string(),
            median: v["median"].as_f64().unwrap(),
            lo: v["lo"].as_f64().unwrap(),
            hi: v["hi"].as_f64().unwrap(),
            rank: v.get("rank").and_then(|x| x.as_f64()),
            rank_lo: v.get("rankLo").and_then(|x| x.as_f64()),
            rank_hi: v.get("rankHi").and_then(|x| x.as_f64()),
        }
    }

    fn row(id: &str, kind: &str, rank: f64) -> OpeningMove {
        OpeningMove {
            id: id.into(), kind: kind.into(), median: 100.0, lo: 90.0, hi: 110.0,
            rank: Some(rank), rank_lo: Some(rank - 10.0), rank_hi: Some(rank + 10.0),
        }
    }

    #[test]
    fn matches_the_shared_cases() {
        let raw = include_str!("repertorio_cases.json");
        let cases: Vec<serde_json::Value> = serde_json::from_str(raw).unwrap();
        assert!(!cases.is_empty());
        for case in cases {
            let starter = mov(&case["starter"]);
            let candidates: Vec<OpeningMove> = case["candidates"].as_array().unwrap().iter().map(mov).collect();
            let got = opening_value(&starter, &candidates, case["bans"].as_u64().unwrap() as usize);
            let expect = &case["expect"];
            assert_eq!(got.median, expect["median"].as_f64().unwrap(), "{}", case["name"]);
            assert_eq!(got.lo, expect["lo"].as_f64().unwrap(), "{}", case["name"]);
            assert_eq!(got.hi, expect["hi"].as_f64().unwrap(), "{}", case["name"]);
            let banned: Vec<String> = expect["banned"].as_array().unwrap().iter().map(|v| v.as_str().unwrap().to_string()).collect();
            assert_eq!(got.banned, banned, "{}", case["name"]);
            assert_eq!(got.draws, expect["draws"].as_u64().unwrap() as usize, "{}", case["name"]);
            assert_eq!(got.melee_locked, expect["meleeLocked"].as_bool().unwrap(), "{}", case["name"]);
        }
    }

    // By hand, on the sweep's own scores: seven of the nine draws score under the Karate Chop
    // starter (72.799), so each is worth the starter and the three bans go by id (Esfera Aural,
    // Golpe Cuerpo, Vozarrón). The six draws left are worth
    // (105.936 + 145.938 + 4 * 72.799) / 6 = 90.512.
    #[test]
    fn marshadow_bans_the_three_worst_and_expects_the_mean_of_the_rest() {
        let got = openings(&[(802, "karate-chop".into())], include_str!("repertorio_marshadow.csv"));
        let (dex, o) = &got[0];
        assert_eq!(*dex, 802);
        assert_eq!(o.banned, ["aura-sphere", "body-slam", "hyper-voice"]);
        assert_eq!(o.draws, 6);
        assert_eq!(o.rank.unwrap().0, 90.512);
        assert!(!o.melee_locked);
    }

    #[test]
    fn rank_follows_the_played_move() {
        let starter = row("tackle", "melee", 50.0);
        let got = opening_value(&starter, &[row("ember", "projectile", 80.0), row("growl", "projectile", 10.0)], 0);
        assert_eq!(got.rank, Some((65.0, 55.0, 75.0)));
        assert!(!got.melee_locked);
    }
}
