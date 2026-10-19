//! Repertorio + Veto opening. Same rule as `simulator/sim/repertorio.js`.
//!
//! Game (JPTER78/pokesurvivor @ 5bbc3b2): upgrades.js:15 and :18, perks at :42 and :45,
//! the random second attack at game.js:120-128, slot switching at game.js:554 and
//! player.js:148, melee damage taken only while melee is active at player.js:238.
//!
//! The second attack is uniform over the non-buff pool. The player bans up to 3 moves
//! that pull that expectation down and then plays the better of the two. The value of a
//! draw is the better move's solo median from the starter sweep.

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
    pub banned: Vec<String>,
    pub draws: usize,
    pub melee_locked: bool,
}

fn round3(x: f64) -> f64 {
    (x * 1000.0).round() / 1000.0
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

    let mut median = starter.median;
    let mut lo = starter.lo;
    let mut hi = starter.hi;
    if pool.iter().any(|c| value_of(c) > value_of(starter)) {
        let mut sm = 0.0;
        let mut sl = 0.0;
        let mut sh = 0.0;
        for c in &pool {
            if value_of(c) > value_of(starter) {
                sm += c.median;
                sl += c.lo;
                sh += c.hi;
            } else {
                sm += starter.median;
                sl += starter.lo;
                sh += starter.hi;
            }
        }
        let n = pool.len() as f64;
        median = round3(sm / n);
        lo = round3(sl / n);
        hi = round3(sh / n);
        if lo > median {
            lo = median;
        }
        if hi < median {
            hi = median;
        }
    }

    let melee_locked = starter.kind == "melee"
        && pool.iter().all(|c| !(c.kind != "melee" && value_of(c) > value_of(starter)));

    Opening {
        median,
        lo,
        hi,
        banned: banned.into_iter().map(|c| c.id.clone()).collect(),
        draws: pool.len(),
        melee_locked,
    }
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

    #[test]
    fn matches_javascript_cases() {
        let raw = include_str!("../../sim/test/repertorio_cases.json");
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
}
