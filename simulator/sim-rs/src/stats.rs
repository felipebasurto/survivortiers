//! Run summaries and the bootstrap median.

use crate::engine::{js_round, RunResult};
use crate::rng::Rng;

pub fn quantile(sorted: &[f64], p: f64) -> f64 {
    if sorted.is_empty() {
        return 0.0;
    }
    if sorted.len() == 1 {
        return sorted[0];
    }
    let x = (sorted.len() - 1) as f64 * p;
    let i = x.floor() as usize;
    let frac = x - i as f64;
    if i + 1 >= sorted.len() {
        return sorted[i];
    }
    sorted[i] * (1.0 - frac) + sorted[i + 1] * frac
}

fn sort(v: &mut [f64]) {
    v.sort_by(|a, b| a.partial_cmp(b).unwrap());
}

fn row_seed(values: &[f64]) -> u32 {
    let mut h = 0x9E37_79B9u32;
    for v in values {
        let bits = v.to_bits();
        h = h.wrapping_mul(0x0100_0193) ^ (bits as u32) ^ ((bits >> 32) as u32);
    }
    if h == 0 { 1 } else { h }
}

/// Bootstrap 5–95 % interval of the median, with a seed that belongs to this row.
/// Two builds that share a seed block stay paired; their intervals do not share one stream.
pub fn bootstrap_median_seeded(times: &[f64], reps: usize, seed: u32) -> (f64, f64) {
    let n = times.len();
    let mut roll = Rng::new(seed);
    let mut meds = Vec::with_capacity(reps);
    let mut sample = vec![0.0; n];
    for _ in 0..reps {
        for s in sample.iter_mut() {
            *s = times[(roll.next() * n as f64) as usize];
        }
        sort(&mut sample);
        meds.push(quantile(&sample, 0.5));
    }
    sort(&mut meds);
    (quantile(&meds, 0.05), quantile(&meds, 0.95))
}

#[derive(Clone, Debug)]
pub struct Summary {
    pub n: usize,
    pub median_s: f64,
    pub mean_s: f64,
    pub boot_lo: f64,
    pub boot_hi: f64,
    pub p10_s: f64,
    pub p75_s: f64,
    pub p90_s: f64,
    pub alive180: usize,
    pub alive300: usize,
    pub alive600: usize,
    pub median_kills: f64,
    pub p10_kills: f64,
    pub p90_kills: f64,
    pub median_bosses: f64,
    pub median_kpm: f64,
    pub median_coins: f64,
    pub p10_coins: f64,
    pub p90_coins: f64,
    pub median_dealt: f64,
    pub p10_dealt: f64,
    pub p90_dealt: f64,
    pub median_lvl: f64,
    pub n_cap: usize,
    pub mean_hp_frac: Option<f64>,
    pub status_ignored: bool,
    /// Median of time * dealt * (1 + kills). Zero damage scores 0.
    pub median_score: f64,
    pub mean_score: f64,
    pub score_lo: f64,
    pub score_hi: f64,
    /// Median score of the first and the second half of the seeds (seed order). Two
    /// independent blocks of the same run, for the stability check.
    pub score_a: f64,
    pub score_b: f64,
}

/// `runs` must be in seed order (1..N), as runSpecies produces them.
pub fn summarize(runs: &[RunResult]) -> Summary {
    let mut times: Vec<f64> = runs.iter().map(|r| r.time).collect();
    let mut kills: Vec<f64> = runs.iter().map(|r| r.kills as f64).collect();
    let mut bosses: Vec<f64> = runs.iter().map(|r| r.bosses as f64).collect();
    let mut coins: Vec<f64> = runs.iter().map(|r| r.coins).collect();
    let mut dealt: Vec<f64> = runs.iter().map(|r| r.dealt).collect();
    let mut kpm: Vec<f64> = runs.iter().map(|r| if r.time > 0.0 { r.kills as f64 * 60.0 / r.time } else { 0.0 }).collect();
    let mut levels: Vec<f64> = runs.iter().map(|r| r.level as f64).collect();
    sort(&mut times);
    sort(&mut kills);
    sort(&mut bosses);
    sort(&mut coins);
    sort(&mut dealt);
    sort(&mut kpm);
    sort(&mut levels);
    let (boot_lo, boot_hi) = bootstrap_median_seeded(&times, 2000, row_seed(&times));
    let mut scores: Vec<f64> = runs.iter().map(run_score).collect();
    let (score_a, score_b) = half_medians(&scores);
    let score_seed = row_seed(&scores);
    sort(&mut scores);
    let (score_lo, score_hi) = bootstrap_median_seeded(&scores, 2000, score_seed);
    let mut score_sum = 0.0;
    for s in &scores {
        score_sum += s;
    }
    let capped: Vec<&RunResult> = runs.iter().filter(|r| r.capped).collect();
    let mut sum = 0.0;
    for t in &times {
        sum += t;
    }
    let mean_hp_frac = if capped.is_empty() {
        None
    } else {
        let mut s = 0.0;
        for r in &capped {
            s += r.hp_frac;
        }
        Some(s / capped.len() as f64)
    };
    Summary {
        n: runs.len(),
        median_s: quantile(&times, 0.5),
        mean_s: sum / times.len() as f64,
        boot_lo,
        boot_hi,
        p10_s: quantile(&times, 0.1),
        p75_s: quantile(&times, 0.75),
        p90_s: quantile(&times, 0.9),
        alive180: runs.iter().filter(|r| r.time >= 180.0).count(),
        alive300: runs.iter().filter(|r| r.time >= 300.0).count(),
        alive600: runs.iter().filter(|r| r.time >= 600.0).count(),
        median_kills: quantile(&kills, 0.5),
        p10_kills: quantile(&kills, 0.1),
        p90_kills: quantile(&kills, 0.9),
        median_bosses: quantile(&bosses, 0.5),
        median_kpm: quantile(&kpm, 0.5),
        median_coins: quantile(&coins, 0.5),
        p10_coins: quantile(&coins, 0.1),
        p90_coins: quantile(&coins, 0.9),
        median_dealt: quantile(&dealt, 0.5),
        p10_dealt: quantile(&dealt, 0.1),
        p90_dealt: quantile(&dealt, 0.9),
        median_lvl: quantile(&levels, 0.5),
        n_cap: capped.len(),
        mean_hp_frac,
        status_ignored: runs.iter().any(|r| r.status_ignored),
        median_score: quantile(&scores, 0.5),
        mean_score: score_sum / scores.len() as f64,
        score_lo,
        score_hi,
        score_a,
        score_b,
    }
}

/// Medians of the first half and the second half of `scores` in seed order.
fn half_medians(scores: &[f64]) -> (f64, f64) {
    let mid = scores.len() / 2;
    let median = |part: &[f64]| {
        let mut v = part.to_vec();
        sort(&mut v);
        quantile(&v, 0.5)
    };
    if mid == 0 {
        let m = median(scores);
        return (m, m);
    }
    (median(&scores[..mid]), median(&scores[mid..]))
}

/// Total damage dealt in the run (HP and shield removed). A run that deals nothing scores 0.
///
/// Damage first: a hard hitter that dies sooner beats a tank that lives longer and hits less,
/// because the damage is the output the run is judged on. Survival counts only through the
/// damage it lets the mon deal, so no constant is needed to weigh the two. The score is not
/// dps (damage per second): dps would reward a burst that ends the run in a few seconds.
pub fn run_score(r: &RunResult) -> f64 {
    if r.dealt <= 0.0 || r.time <= 0.0 {
        return 0.0;
    }
    r.dealt
}

/// `num()` from the JS writers: round to 3 decimals, shortest round-trip text.
pub fn num(v: f64) -> String {
    if v.is_nan() {
        return String::new();
    }
    let r = js_round(v * 1000.0) / 1000.0;
    if r == 0.0 {
        return "0".into();
    }
    format!("{r}")
}

pub fn csv_escape(text: &str) -> String {
    if text.contains([',', '"', '\n']) {
        format!("\"{}\"", text.replace('"', "\"\""))
    } else {
        text.to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn run(time: f64, dealt: f64, kills: u32) -> RunResult {
        RunResult {
            time,
            kills,
            bosses: 0,
            coins: 0.0,
            level: 1,
            capped: false,
            status_ignored: false,
            hp: 0.0,
            max_hp: 1.0,
            hp_frac: 0.0,
            dealt,
        }
    }

    #[test]
    fn halves_are_taken_in_seed_order() {
        let (a, b) = half_medians(&[1.0, 2.0, 3.0, 10.0, 20.0, 30.0]);
        assert_eq!((a, b), (2.0, 20.0));
    }

    #[test]
    fn no_damage_scores_zero() {
        assert_eq!(run_score(&run(120.0, 0.0, 40)), 0.0);
    }

    #[test]
    fn score_is_the_damage_dealt() {
        assert_eq!(run_score(&run(120.0, 9600.0, 80)), 9600.0);
        // A hard hitter that dies sooner beats a tank that lives longer and hits less.
        assert!(run_score(&run(100.0, 8000.0, 70)) > run_score(&run(180.0, 1800.0, 36)));
    }
}
