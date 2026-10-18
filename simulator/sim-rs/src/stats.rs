//! summarize() and bootstrapMedian() from sim/rank.js.

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

pub fn bootstrap_median(times: &[f64], reps: usize) -> (f64, f64) {
    let n = times.len();
    let mut roll = Rng::new(0xB007);
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
    pub median_bosses: f64,
    pub median_kpm: f64,
    pub median_coins: f64,
    pub median_lvl: f64,
    pub n_cap: usize,
    pub mean_hp_frac: Option<f64>,
    pub status_ignored: bool,
}

/// `runs` must be in seed order (1..N), as runSpecies produces them.
pub fn summarize(runs: &[RunResult]) -> Summary {
    let mut times: Vec<f64> = runs.iter().map(|r| r.time).collect();
    let mut kills: Vec<f64> = runs.iter().map(|r| r.kills as f64).collect();
    let mut bosses: Vec<f64> = runs.iter().map(|r| r.bosses as f64).collect();
    let mut coins: Vec<f64> = runs.iter().map(|r| r.coins).collect();
    let mut kpm: Vec<f64> = runs.iter().map(|r| if r.time > 0.0 { r.kills as f64 * 60.0 / r.time } else { 0.0 }).collect();
    let mut levels: Vec<f64> = runs.iter().map(|r| r.level as f64).collect();
    sort(&mut times);
    sort(&mut kills);
    sort(&mut bosses);
    sort(&mut coins);
    sort(&mut kpm);
    sort(&mut levels);
    let (boot_lo, boot_hi) = bootstrap_median(&times, 400);
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
        median_bosses: quantile(&bosses, 0.5),
        median_kpm: quantile(&kpm, 0.5),
        median_coins: quantile(&coins, 0.5),
        median_lvl: quantile(&levels, 0.5),
        n_cap: capped.len(),
        mean_hp_frac,
        status_ignored: runs.iter().any(|r| r.status_ignored),
    }
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
