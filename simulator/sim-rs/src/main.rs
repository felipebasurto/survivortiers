//! Fast headless PokéSurvivor sim. Run from the repo root.
//!
//!   cargo run --release --manifest-path sim-rs/Cargo.toml -- sweep
//!       every simulated pool move as start; writes sim/out/starter_sweep.csv
//!       and sim/out/rank_best_starter.csv (same format as sim/sweep_starters.js)
//!   ... -- rank [--out sim/out/rank_200.csv]
//!       game start move only (same format as sim/batch.js)
//!   ... -- run <dex> <move> <seed> [--out trace.csv]
//!   ... -- replay <trace.bin> <tables.bin> <dex> <move> <seed>
//!       parity check against a trace written by sim-rs/parity.js
//!   ... -- mathcheck <trace.bin>...
//!       how often libm's sin/cos/atan2/pow differ from V8's in recorded traces
//!   ... -- mapcheck <seed> [half]
//!       terrain digest; must match `node sim-rs/mapcheck.js <game repo> <seed> [half]`
//!
//! Options: --seeds N (200) --seconds S (900) --bot repulse|line|kite --lvl1 --dodge F
//!          --terrain  play on the real map (walls, props, liquids, pathing); not JS-parity
//!          --status   model slow, burn and poison with the game's values (enemy.js); moves the
//!                     sim never fires keep status_ignored=1. Not JS-parity.
//!
//! Parity with the JS engine (bit-exact, every transcendental replayed from V8):
//!   node sim-rs/parity.js [--random=N]
//! Any edit to sim/match.js or sim/rules.js must be mirrored in src/engine.rs and
//! re-checked with parity.js.

mod data;
mod engine;
mod radii;
mod math;
mod repertorio;
mod rng;
mod stats;
mod terrain;

use data::{Data, Kind, Mon};
use engine::{run_match, take_trace, Bot, Ext, Item, Opts, RunResult, Tables, DT};
use std::sync::OnceLock;

/// dex -> simulated pool attacks sorted by solo (old-mode) median, best first
static PARTNERS: OnceLock<HashMap<u32, Vec<String>>> = OnceLock::new();
use math::{Libm, MathFns, Replay};
use rayon::prelude::*;
use stats::{csv_escape, num, summarize, Summary};
use std::collections::HashMap;
use std::fmt::Write as _;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Instant;

struct Cfg {
    seeds: u32,
    seconds: f64,
    bot: Bot,
    cards: bool,
    terrain: bool,
    status: bool,
    out: Option<String>,
    group: u8,
    dd: bool,
    np: bool,
    agi: bool,
    xkinds: bool,
    legacy: bool,
    item: String,
    fill: Vec<u8>,
    buffs: Option<u8>,
    comps: Option<Vec<String>>,
    /// second slot: swap when the active cooldown is above 35% of its base (player.js:148)
    swap: bool,
    /// crit perk levels (upgrades.js). Chance is levels * 0.03. Published ranks pass 0.
    crit: f64,
    /// offer Aprendizaje and Baya Zidra (levelup.js). Off keeps the published card pool.
    full_cards: bool,
    /// fill priority stops once that stat reaches this count. 0 = no extra limit.
    stop: u32,
    /// take Baya Zidra only at or below this hp fraction. 0 = only when the fill list prefers it.
    heal_below: f64,
    /// fraction of combat damage ignored. 0 = the bot eats every hit.
    dodge: f64,
    /// `--bot` was passed. Otherwise a faithful run uses Play.
    bot_set: bool,
    /// stat index:count pairs. Start with that many and do not take more. 7 = Aprendizaje.
    locks: Vec<(u8, u32)>,
    /// Score status+Hex groups, not only the solo-sorted partner.
    synergy: bool,
    no_synergy: bool,
    /// First seed is `seed0 + 1`. The same block is used for every build (common random numbers).
    seed0: u32,
    /// Print the group-search size and exit.
    count: bool,
    rest: Vec<String>,
}

fn parse(args: &[String]) -> Cfg {
    let mut c = Cfg { seeds: 200, seconds: 900.0, bot: Bot::Repulse, cards: true, terrain: false, status: false, out: None, group: 0, dd: false, np: false, agi: false, xkinds: false, legacy: false, item: "none".into(), fill: vec![], buffs: None, comps: None, swap: false, crit: 0.0, full_cards: false, stop: 0, heal_below: 0.0, dodge: 0.0, locks: vec![], synergy: false, no_synergy: false, bot_set: false, seed0: 0, count: false, rest: vec![] };
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--seeds" => {
                i += 1;
                c.seeds = args[i].parse().expect("--seeds");
            }
            "--seed0" => {
                i += 1;
                c.seed0 = args[i].parse().expect("--seed0");
            }
            "--count" => c.count = true,
            "--seconds" => {
                i += 1;
                c.seconds = args[i].parse().expect("--seconds");
            }
            "--bot" => {
                i += 1;
                c.bot_set = true;
                c.bot = match args[i].as_str() {
                    "repulse" => Bot::Repulse,
                    "line" => Bot::Line,
                    "kite" => Bot::Kite,
                    "play" => Bot::Play,
                    b => panic!("unknown bot {b}"),
                };
            }
            "--lvl1" => c.cards = false,
            "--terrain" => c.terrain = true,
            "--status" => c.status = true,
            "--synergy" => c.synergy = true,
            "--no-synergy" => c.no_synergy = true,
            "--group" => {
                i += 1;
                c.group = match args[i].as_str() { "2+2" => 2, "3+1" => 3, "off" => 0, x => panic!("--group {x}") };
            }
            "--partners" => {
                i += 1;
                PARTNERS.set(read_partners(&args[i])).ok();
            }
            "--dd" => c.dd = true,
            "--np" => c.np = true,
            "--agi" => c.agi = true,
            "--xkinds" => c.xkinds = true,
            "--swap" => c.swap = true,
            "--crit" => {
                i += 1;
                c.crit = args[i].parse::<f64>().expect("--crit") * 0.03;
            }
            "--legacy-group" => c.legacy = true,
            "--buffs" => {
                i += 1;
                c.buffs = Some(args[i].parse().unwrap());
            }
            "--item" => {
                i += 1;
                c.item = args[i].clone();
            }
            "--fill" => {
                i += 1;
                c.fill = args[i].split(',').map(|x| x.parse().unwrap()).collect();
            }
            "--full-cards" => c.full_cards = true,
            "--stop" => {
                i += 1;
                c.stop = args[i].parse().expect("--stop");
            }
            "--heal-below" => {
                i += 1;
                c.heal_below = args[i].parse().expect("--heal-below");
            }
            "--dodge" => {
                i += 1;
                c.dodge = args[i].parse().expect("--dodge");
            }
            "--lock" => {
                i += 1;
                c.locks = parse_locks(&args[i]);
            }
            "--out" => {
                i += 1;
                c.out = Some(args[i].clone());
            }
            a => c.rest.push(a.to_string()),
        }
        i += 1;
    }
    c
}

fn parse_locks(s: &str) -> Vec<(u8, u32)> {
    if s.is_empty() {
        return vec![];
    }
    s.split(';')
        .filter(|p| !p.is_empty())
        .map(|p| {
            let (k, n) = p.split_once(':').unwrap_or_else(|| panic!("lock {p}"));
            (k.parse().unwrap(), n.parse().unwrap())
        })
        .collect()
}

fn read_partners(path: &str) -> HashMap<u32, Vec<String>> {
    let text = std::fs::read_to_string(path).expect("partners");
    let mut rows: Vec<(u32, String, String, f64)> = Vec::new();
    for l in text.lines().filter(|l| !l.starts_with('#') && !l.starts_with("dex,")) {
        let c: Vec<&str> = l.split(',').collect();
        let n = c.len();
        // dex,name,start,kind,n,median_s,... (name may hold no commas in this data)
        let time: f64 = c[5].parse().unwrap();
        let score = c.get(16).and_then(|s| s.parse().ok()).unwrap_or(time);
        // A move that never lands is not a partner. Missing column (older sweeps) stays eligible.
        let dealt: f64 = c.get(15).and_then(|s| s.parse().ok()).unwrap_or(1.0);
        if dealt <= 0.0 || c[3] == "buff" {
            continue;
        }
        rows.push((c[0].parse().unwrap(), c[2].to_string(), c[3].to_string(), score));
        let _ = n;
    }
    rows.sort_by(|a, b| a.0.cmp(&b.0).then(b.3.partial_cmp(&a.3).unwrap()).then(a.1.cmp(&b.1)));
    let mut m: HashMap<u32, Vec<String>> = HashMap::new();
    for (d, mv, _kind, _) in rows {
        m.entry(d).or_default().push(mv);
    }
    m
}

/// Hex (moves.js chain, hex > 1) wants a partner that burns, poisons or slows, either way.
/// Two dashes also pair (combat.js dash invuln). Solo order is kept inside each group.
fn pairs_with(data: &Data, a: usize, b: usize) -> bool {
    let la = &data.moves[a].levels[0];
    let lb = &data.moves[b].levels[0];
    let statusy = |burn: f64, poison: f64, slow: f64| {
        (burn.is_finite() && burn > 0.0) || (poison.is_finite() && poison > 0.0) || (slow.is_finite() && slow > 0.0)
    };
    let hex = |h: f64| h.is_finite() && h > 1.0;
    (hex(la.hex) && statusy(lb.burn, lb.poison, lb.slow))
        || (hex(lb.hex) && statusy(la.burn, la.poison, la.slow))
        || (la.xk == 5 && lb.xk == 5)
}

/// Attacks the group can actually cast. Orbit stays out (a shared orb list). Buffs are the other slots.
/// Extra kinds count, so Hex and Flamethrower are eligible even when the old solo sweep skipped them.
fn partner_pool(data: &Data, mon: &Mon, start: usize) -> Vec<usize> {
    let solo: Vec<usize> = PARTNERS
        .get()
        .and_then(|p| p.get(&mon.dex))
        .map(|list| list.iter().filter_map(|id| data.move_ix.get(id.as_str()).copied()).collect())
        .unwrap_or_default();
    let mut ids: Vec<usize> = mon
        .pool
        .iter()
        .copied()
        .filter(|&ix| {
            if ix == start {
                return false;
            }
            let m = &data.moves[ix];
            // A second orbit uses its own orb list (step_side_orbs). Gengar's melee ban
            // is the publisher's rule (build/owner_rules.py), not a second copy here.
            if !publishable_attack(m) {
                return false;
            }
            m.kind.simulated() || m.levels[0].xk != 0
        })
        .collect();
    ids.sort_by(|&a, &b| {
        let syn = |ix| if pairs_with(data, start, ix) { 0u8 } else { 1 };
        let rank = |ix| solo.iter().position(|&p| p == ix).unwrap_or(10_000);
        syn(a).cmp(&syn(b)).then(rank(a).cmp(&rank(b))).then(data.moves[a].id.cmp(&data.moves[b].id))
    });
    ids
}

/// Buff ids from data/owner_rules.json. One file for the publisher and the sim.
fn owner_buffs() -> (&'static str, &'static str) {
    use std::sync::OnceLock;
    static IDS: OnceLock<(String, String)> = OnceLock::new();
    let (physical, special) = IDS.get_or_init(|| {
        let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../data/owner_rules.json");
        let text = std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("read {}: {e}", path.display()));
        let v: serde_json::Value = serde_json::from_str(&text).expect("owner_rules.json");
        (
            v["physical_buff"].as_str().unwrap().to_string(),
            v["special_buff"].as_str().unwrap().to_string(),
        )
    });
    (physical, special)
}

/// Maquinación when the lead attack is special. A physical lead, including a mixed pair,
/// bonds Danza Espada: Danza Espada does not raise special moves, and the lead is the move
/// that is up for most of the rift window. A lead with no category falls through to the
/// next attack, then to `sa > pa`. `--np` forces Maquinación. `--dd` is Dragon Dance and
/// only applies when this returns false.
fn use_nasty(data: &Data, mon: &Mon, start: usize, comps: &[usize], cfg: &Cfg) -> bool {
    if cfg.np {
        return true;
    }
    for ix in std::iter::once(start).chain(comps.iter().copied()) {
        match data.moves[ix].levels[0].cat {
            2 => return true,
            1 => return false,
            _ => {}
        }
    }
    mon.sa > mon.pa
}

/// The fixed main group for this primary: a synergistic partner first, then the next best solo attacks.
fn ext_for(data: &Data, mon: &Mon, start: usize, cfg: &Cfg) -> Ext {
    let pool = partner_pool(data, mon, start);
    let companions = if let Some(list) = &cfg.comps {
        list.iter().map(|id| data.move_ix[id.as_str()]).collect()
    } else if cfg.group >= 2 {
        let want = (cfg.group - 1) as usize;
        pool.iter().copied().take(want).collect()
    } else {
        Vec::new()
    };
    let item = Item::by_id(&cfg.item);
    // Slot 1 is the next leftover attack at level 1. Choice Band (player.js:141) cannot swap.
    let alt = if cfg.swap && !item.lock {
        pool.iter().copied().find(|&ix| !companions.contains(&ix))
    } else {
        None
    };
    let np = use_nasty(data, mon, start, &companions, cfg);
    Ext {
        companions,
        buffs: cfg.buffs.unwrap_or(match cfg.group { 2 => 3, 3 => 1, _ => 0 }),
        dd: cfg.dd && !np,
        np,
        agi: cfg.agi,
        item,
        fill: cfg.fill.clone(),
        xkinds: cfg.xkinds || (cfg.group > 0 && !cfg.legacy),
        rift: cfg.group > 0 && !cfg.legacy,
        bosses: cfg.group > 0 && !cfg.legacy,
        alt,
        crit: cfg.crit,
        full_cards: cfg.full_cards,
        stop: cfg.stop,
        heal_below: cfg.heal_below,
        dodge: cfg.dodge,
        locks: cfg.locks.clone(),
    }
}

fn group_label(cfg: &Cfg) -> &'static str {
    match (cfg.group, cfg.legacy) { (2, false) => "grupo fijo 2 ataques + Danza Espada o Maquinación y Fortaleza con vínculos de grieta, jefes y todos los tipos de ataque", (3, false) => "grupo fijo 3 ataques + Danza Espada o Maquinación con vínculos de grieta, jefes y todos los tipos de ataque", (2, true) => "grupo fijo 2 ataques + Danza Espada o Maquinación y Fortaleza desde t=0, sin grietas, sin jefes", (3, true) => "grupo fijo 3 ataques + Danza Espada o Maquinación desde t=0, sin grietas, sin jefes", _ => "un movimiento, sin grietas, sin jefes" }
}

fn bot_name(b: Bot) -> &'static str {
    match b {
        Bot::Repulse => "repulse",
        Bot::Line => "line",
        Bot::Kite => "kite",
        Bot::Play => "play",
    }
}

fn run_species(data: &Data, tables: &Tables, mon: &Mon, start: usize, cfg: &Cfg) -> Summary {
    let ext = ext_for(data, mon, start, cfg);
    let runs: Vec<RunResult> = (1..=cfg.seeds)
        .map(|i| {
            let seed = cfg.seed0 + i;
            let opts = Opts { seed, seconds: cfg.seconds, cards: cfg.cards, bot: cfg.bot, terrain: cfg.terrain, trace: false, status: cfg.status, ext: ext.clone() };
            run_match(&Libm, data, tables, mon, start, &opts)
        })
        .collect();
    summarize(&runs)
}

struct Row<'a> {
    mon: &'a Mon,
    start: usize,
    /// Empty and `buffs == None` means the heuristic partner from `ext_for`.
    comps: Vec<usize>,
    buffs: Option<u8>,
    s: Summary,
}

struct Job<'a> {
    mon: &'a Mon,
    start: usize,
    comps: Option<Vec<usize>>,
    buffs: Option<u8>,
}

fn run_tasks<'a>(data: &'a Data, tasks: Vec<(&'a Mon, usize)>, cfg: &Cfg) -> Vec<Row<'a>> {
    let jobs = tasks
        .into_iter()
        .map(|(mon, start)| Job { mon, start, comps: None, buffs: None })
        .collect();
    run_jobs(data, jobs, cfg)
}

fn run_jobs<'a>(data: &'a Data, jobs: Vec<Job<'a>>, cfg: &Cfg) -> Vec<Row<'a>> {
    let tables = Tables::new();
    let done = AtomicUsize::new(0);
    let total = jobs.len();
    let t0 = Instant::now();
    jobs
        .into_par_iter()
        .map(|job| {
            let comps = job.comps.clone().unwrap_or_default();
            let explicit = job.comps.is_some() || job.buffs.is_some();
            let s = if explicit {
                let mut sub = cfg_clone(cfg);
                if job.comps.is_some() {
                    sub.comps = Some(comps.iter().map(|&ix| data.moves[ix].id.clone()).collect());
                }
                if let Some(b) = job.buffs {
                    sub.buffs = Some(b);
                }
                run_species(data, &tables, job.mon, job.start, &sub)
            } else {
                run_species(data, &tables, job.mon, job.start, cfg)
            };
            let d = done.fetch_add(1, Ordering::Relaxed) + 1;
            if d % 250 == 0 || d == total {
                eprintln!("  {d}/{total}  {:.1}s", t0.elapsed().as_secs_f64());
            }
            Row { mon: job.mon, start: job.start, comps, buffs: job.buffs, s }
        })
        .collect()
}

fn read_old_rank(path: &str) -> HashMap<u32, usize> {
    let mut m = HashMap::new();
    let Ok(text) = std::fs::read_to_string(path) else { return m };
    let lines = text.lines().filter(|l| !l.is_empty() && !l.starts_with('#') && !l.starts_with("dex,"));
    for (i, l) in lines.enumerate() {
        m.insert(l.split(',').next().unwrap().parse().unwrap(), i + 1);
    }
    m
}

fn cmp_desc(a: f64, b: f64) -> std::cmp::Ordering {
    b.total_cmp(&a)
}

fn finite_pos(x: f64) -> bool {
    x.is_finite() && x > 0.0
}

fn is_payoff(l: &data::MoveLvl) -> bool {
    l.hex.is_finite() && l.hex > 1.0
}

fn is_applier(l: &data::MoveLvl) -> bool {
    finite_pos(l.burn) || finite_pos(l.poison) || finite_pos(l.slow)
}

/// Attacks the bonded group can cast, orbit included. A buff is not an attack.
fn castable(m: &data::Move) -> bool {
    publishable_attack(m) && (m.kind.simulated() || m.levels[0].xk != 0 || m.kind == Kind::Orbit)
}

/// An attacking move: it deals damage and it is not a buff. Turret, orbit and melee
/// qualify. A move that deals nothing cannot be "best" because its run score is 0.
fn publishable_attack(m: &data::Move) -> bool {
    if m.kind_name == "buff" {
        return false;
    }
    let l = &m.levels[0];
    let dmg = if l.dmg.is_finite() { l.dmg } else { 0.0 };
    dmg > 0.0 && l.buff == 0
}

fn level_dps(l: &data::MoveLvl) -> f64 {
    let cd = if l.cd.is_finite() && l.cd > 0.0 { l.cd } else { 1.0 };
    let n = if l.count.is_finite() && l.count > 0.0 { l.count } else { 1.0 };
    let dmg = if l.dmg.is_finite() { l.dmg } else { 0.0 };
    dmg * n / cd
}

struct Spec {
    start: usize,
    comps: Vec<usize>,
    buffs: u8,
}

/// How many of a species' best attacks are crossed as plain pairs.
/// Solo-sweep order and the move-tier list (`data/move_tierlist_v4.csv`) both count;
/// a move takes the better of the two ranks. Six is enough to cover the attacks
/// that actually win a fixed group (Shadow Ball and Aura Sphere sit here for Marshadow)
/// without the full pool cross product.
const PAIR_TOP: usize = 4;

fn attack_list(data: &Data, mon: &Mon) -> Vec<usize> {
    mon.start_choices(&data.moves)
        .into_iter()
        .filter(|&ix| {
            let m = &data.moves[ix];
            castable(m) && (ix == mon.start || publishable_attack(m))
        })
        .collect()
}

fn ensure_partners() {
    if PARTNERS.get().is_some() {
        return;
    }
    for p in ["results/fixed_group/solo_sweep.csv", "simulator/results/fixed_group/solo_sweep.csv"] {
        if std::path::Path::new(p).exists() {
            let _ = PARTNERS.set(read_partners(p));
            return;
        }
    }
}

/// move id -> score_rel from the v4 move tier list. Empty if the file is not next to the sim.
fn tier_scores() -> &'static HashMap<String, f64> {
    static SCORES: OnceLock<HashMap<String, f64>> = OnceLock::new();
    SCORES.get_or_init(|| {
        let mut m = HashMap::new();
        for p in ["../data/move_tierlist_v4.csv", "data/move_tierlist_v4.csv"] {
            let Ok(text) = std::fs::read_to_string(p) else { continue };
            for line in text.lines().filter(|l| !l.is_empty() && !l.starts_with("category,")) {
                let cols = csv_fields(line);
                // category,tier,rank,move_id,name,type,kind,score_rel,...
                if cols.len() > 7 {
                    if let Ok(score) = cols[7].parse::<f64>() {
                        m.insert(cols[3].clone(), score);
                    }
                }
            }
            break;
        }
        m
    })
}

fn csv_fields(line: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut cur = String::new();
    let mut in_quotes = false;
    for c in line.chars() {
        match c {
            '"' => in_quotes = !in_quotes,
            ',' if !in_quotes => out.push(std::mem::take(&mut cur)),
            _ => cur.push(c),
        }
    }
    out.push(cur);
    out
}

/// Best attacks for the plain-pair search. Rank is the better of the species' solo
/// sweep order and the global move-tier order, so a kind the solo sweep skipped (Hex)
/// still enters when its tier is high.
fn top_attacks(data: &Data, mon: &Mon, atk: &[usize]) -> Vec<usize> {
    ensure_partners();
    let solo: Vec<usize> = PARTNERS
        .get()
        .and_then(|p| p.get(&mon.dex))
        .map(|list| list.iter().filter_map(|id| data.move_ix.get(id.as_str()).copied()).collect())
        .unwrap_or_default();
    let scores = tier_scores();
    let mut by_tier = atk.to_vec();
    by_tier.sort_by(|&a, &b| {
        let sa = scores.get(&data.moves[a].id).copied().unwrap_or(f64::NEG_INFINITY);
        let sb = scores.get(&data.moves[b].id).copied().unwrap_or(f64::NEG_INFINITY);
        sb.partial_cmp(&sa).unwrap_or(std::cmp::Ordering::Equal).then(data.moves[a].id.cmp(&data.moves[b].id))
    });
    let solo_pos = |ix: usize| solo.iter().position(|&p| p == ix).unwrap_or(10_000);
    let tier_pos = |ix: usize| by_tier.iter().position(|&p| p == ix).unwrap_or(10_000);
    let mut ranked = atk.to_vec();
    ranked.sort_by(|&a, &b| {
        solo_pos(a).min(tier_pos(a)).cmp(&solo_pos(b).min(tier_pos(b))).then(data.moves[a].id.cmp(&data.moves[b].id))
    });
    ranked.truncate(PAIR_TOP);
    if !ranked.contains(&mon.start) && atk.contains(&mon.start) {
        if ranked.len() == PAIR_TOP {
            ranked.pop();
        }
        ranked.push(mon.start);
    }
    ranked
}

fn dedup_specs(specs: Vec<Spec>) -> Vec<Spec> {
    let mut seen = std::collections::HashSet::new();
    let mut out = Vec::new();
    for s in specs {
        if seen.insert((s.start, s.comps.clone(), s.buffs)) {
            out.push(s);
        }
    }
    out
}

/// Every species gets a real group search. The cross is pruned: the top attacks
/// (solo sweep or the move-tier list, whichever ranks the move higher), both
/// leads, Harden against one third attack, Hex with its best appliers, and dash
/// pairs. A species with fewer than two attacks has nothing to bond.
///
/// Every group holds an attack buff (bit 1). The move is Maquinación when the lead
/// attack is special, otherwise Danza Espada. A mixed pair follows that lead. The
/// fourth slot is Harden (`buffs` 3) or a third attack (`buffs` 1). Gengar may be
/// searched with a melee move. The publisher drops that build (`owner_rules`).
fn synergy_specs(data: &Data, mon: &Mon) -> Vec<Spec> {
    let atk = attack_list(data, mon);
    if atk.len() < 2 {
        return vec![];
    }
    let pay: Vec<usize> = atk.iter().copied().filter(|&ix| is_payoff(&data.moves[ix].levels[0])).collect();
    let mut app: Vec<usize> = atk.iter().copied().filter(|&ix| is_applier(&data.moves[ix].levels[0])).collect();
    app.sort_by(|&a, &b| {
        level_dps(&data.moves[b].levels[0])
            .partial_cmp(&level_dps(&data.moves[a].levels[0]))
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(data.moves[a].id.cmp(&data.moves[b].id))
    });
    // Two payoffs and three appliers. The full cross is the same shape and a lot of seeds.
    let pay: Vec<usize> = pay.into_iter().take(2).collect();
    app.truncate(3);
    let mut out = Vec::new();
    if !pay.is_empty() && !app.is_empty() {
        for &p in &pay {
            for &a in &app {
                if p == a {
                    continue;
                }
                out.push(Spec { start: p, comps: vec![a], buffs: 3 });
                out.push(Spec { start: a, comps: vec![p], buffs: 3 });
            }
        }
        let trio = 3.min(app.len());
        for i in 0..trio {
            for j in (i + 1)..trio {
                let (a, b) = (app[i], app[j]);
                for &p in &pay {
                    out.push(Spec { start: p, comps: vec![a, b], buffs: 1 });
                    out.push(Spec { start: a, comps: vec![p, b], buffs: 1 });
                }
            }
        }
    }
    // Plain pairs, both leads. The bond waits on the rift, so the lead is most of the
    // median and the partner is the tie-break. Both orders are scored.
    let top = top_attacks(data, mon, &atk);
    for &a in &top {
        for &b in &top {
            if a == b {
                continue;
            }
            // 2 attacks + Swords Dance + Harden.
            out.push(Spec { start: a, comps: vec![b], buffs: 3 });
            // Same pair, fourth slot a third attack instead of Harden.
            push_third(data, &top, &atk, a, b, &mut out);
        }
    }
    // Dash invuln is its own relation. Score every ordered dash pair, not only the
    // ones that also land in the top six (Jumpluff, Honchkrow, Rowlet, Dartrix).
    let dashes: Vec<usize> = atk.iter().copied().filter(|&ix| data.moves[ix].levels[0].xk == 5).collect();
    for &a in &dashes {
        for &b in &dashes {
            if a != b {
                out.push(Spec { start: a, comps: vec![b], buffs: 3 });
            }
        }
    }
    dedup_specs(out)
}

/// One or two thirds for a pair: the next non-melee attack in the top list, and the
/// strongest status partner of either member when that is a different move (Sludge + Hex).
fn push_third(data: &Data, top: &[usize], atk: &[usize], a: usize, b: usize, out: &mut Vec<Spec>) {
    let ranged = |ix: usize| data.moves[ix].kind != Kind::Melee;
    let mut thirds = Vec::new();
    if let Some(c) = top.iter().copied().find(|&c| c != a && c != b && ranged(c)) {
        thirds.push(c);
    }
    let mut syn: Vec<usize> = atk
        .iter()
        .copied()
        .filter(|&c| c != a && c != b && ranged(c) && (pairs_with(data, a, c) || pairs_with(data, b, c)))
        .collect();
    syn.sort_by(|&x, &y| {
        level_dps(&data.moves[y].levels[0])
            .partial_cmp(&level_dps(&data.moves[x].levels[0]))
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(data.moves[x].id.cmp(&data.moves[y].id))
    });
    if let Some(c) = syn.first().copied() {
        if !thirds.contains(&c) {
            thirds.push(c);
        }
    }
    for c in thirds {
        out.push(Spec { start: a, comps: vec![b, c], buffs: 1 });
    }
}

fn group_name(data: &Data, mon: &Mon, start: usize, comps: &[usize], buffs: u8, cfg: &Cfg) -> String {
    let mut parts = vec![data.moves[start].id.clone()];
    for &c in comps {
        parts.push(data.moves[c].id.clone());
    }
    if buffs & 1 != 0 {
        let (physical, special) = owner_buffs();
        let buff = if use_nasty(data, mon, start, comps, cfg) {
            special
        } else if cfg.dd {
            "dragon-dance"
        } else {
            physical
        };
        parts.push(buff.to_string());
    }
    if buffs & 2 != 0 {
        parts.push((if cfg.agi { "agility" } else { "harden" }).to_string());
    }
    parts.join("+")
}

fn row_group(data: &Data, row: &Row, cfg: &Cfg) -> String {
    if row.buffs.is_none() && row.comps.is_empty() {
        if cfg.group == 0 {
            return data.moves[row.start].id.clone();
        }
        let ext = ext_for(data, row.mon, row.start, cfg);
        return group_name(data, row.mon, row.start, &ext.companions, ext.buffs, cfg);
    }
    group_name(data, row.mon, row.start, &row.comps, row.buffs.unwrap_or(0), cfg)
}

fn sweep(data: &Data, cfg: &Cfg) {
    let mut jobs = Vec::new();
    let mut seen = std::collections::HashSet::new();
    for mon in &data.dex {
        let mut ids = vec![mon.start];
        for &p in &mon.pool {
            if !ids.contains(&p) {
                ids.push(p);
            }
        }
        for id in ids {
            let extra = (cfg.xkinds || (cfg.group > 0 && !cfg.legacy)) && data.moves[id].levels[0].xk != 0;
            if data.moves[id].kind.simulated() || extra {
                if cfg.group > 0 {
                    let ext = ext_for(data, mon, id, cfg);
                    seen.insert((mon.dex, id, ext.companions.clone(), ext.buffs));
                }
                jobs.push(Job { mon, start: id, comps: None, buffs: None });
            }
        }
        if cfg.synergy && cfg.group > 0 {
            for spec in synergy_specs(data, mon) {
                let key = (mon.dex, spec.start, spec.comps.clone(), spec.buffs);
                if seen.insert(key) {
                    jobs.push(Job { mon, start: spec.start, comps: Some(spec.comps), buffs: Some(spec.buffs) });
                }
            }
        }
    }
    eprintln!("sweep: {} candidates x {} seeds, {} threads", jobs.len(), cfg.seeds, rayon::current_num_threads());
    let mut rows = run_jobs(data, jobs, cfg);
    let mv = |r: &Row| data.moves[r.start].id.as_str();
    rows.sort_by(|a, b| a.mon.dex.cmp(&b.mon.dex).then_with(|| mv(a).cmp(mv(b))));

    let out_dir = cfg.out.clone().unwrap_or_else(|| "sim/out".into());
    std::fs::create_dir_all(&out_dir).unwrap();
    let mut long = format!(
        "# barrido: todos los movimientos simulados del pool como inicial. seeds=1-{} seconds={} bot={}\n\
         dex,name,start,kind,n,median_s,mean_s,boot_lo,boot_hi,p10_s,p90_s,median_kills,median_lvl,status_ignored,group,median_dealt,median_score,mean_score,score_lo,score_hi\n",
        cfg.seeds, cfg.seconds, bot_name(cfg.bot)
    );
    for r in &rows {
        let s = &r.s;
        writeln!(
            long,
            "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}",
            r.mon.dex,
            csv_escape(&r.mon.name),
            mv(r),
            data.moves[r.start].kind_name,
            s.n,
            num(s.median_s),
            num(s.mean_s),
            num(s.boot_lo),
            num(s.boot_hi),
            num(s.p10_s),
            num(s.p90_s),
            num(s.median_kills),
            num(s.median_lvl),
            s.status_ignored as u8,
            row_group(data, r, cfg),
            score_tail(s)
        )
        .unwrap();
    }
    let long_path = format!("{out_dir}/starter_sweep.csv");
    std::fs::write(&long_path, long).unwrap();

    let mut groups: Vec<Vec<&Row>> = Vec::new();
    for r in &rows {
        match groups.last_mut() {
            Some(g) if g[0].mon.dex == r.mon.dex => g.push(r),
            _ => groups.push(vec![r]),
        }
    }
    let mut best: Vec<(&Row, usize, Option<&Row>)> = groups
        .iter_mut()
        .map(|g| {
            // Best move is an attack. Sustituto stays in the long CSV (its turret shots
            // are real damage) and is dropped here, along with any row that dealt nothing.
            let mut picked: Vec<&Row> = g
                .iter()
                .copied()
                .filter(|&r| {
                    let m = &data.moves[r.start];
                    publishable_attack(m) && r.s.median_dealt > 0.0
                })
                .collect();
            if picked.is_empty() {
                picked = g.iter().copied().filter(|&r| publishable_attack(&data.moves[r.start])).collect();
            }
            if picked.is_empty() {
                picked = g.clone();
            }
            picked.sort_by(|a, b| cmp_run(&a.s, &b.s).then_with(|| mv(a).cmp(mv(b))));
            let n = picked.len();
            let alt = picked.get(1).copied();
            (picked[0], n, alt)
        })
        .collect();
    best.sort_by(|a, b| cmp_run(&a.0.s, &b.0.s).then(a.0.mon.dex.cmp(&b.0.mon.dex)));
    let old = read_old_rank("sim/out/rank_200.csv");
    let mut text = format!(
        "# mejor movimiento inicial por especie. seeds=1-{} seconds={} bot={}\n\
         rank,dex,name,best_start,best_kind,median_s,mean_s,boot_lo,boot_hi,p10_s,p90_s,median_kills,median_lvl,status_ignored,n_candidates,alt_start,alt_median_s,rank_old_200,group,median_dealt,median_score,mean_score,score_lo,score_hi\n",
        cfg.seeds, cfg.seconds, bot_name(cfg.bot)
    );
    for (i, (r, n, alt)) in best.iter().enumerate() {
        let s = &r.s;
        writeln!(
            text,
            "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}",
            i + 1,
            r.mon.dex,
            csv_escape(&r.mon.name),
            mv(r),
            data.moves[r.start].kind_name,
            num(s.median_s),
            num(s.mean_s),
            num(s.boot_lo),
            num(s.boot_hi),
            num(s.p10_s),
            num(s.p90_s),
            num(s.median_kills),
            num(s.median_lvl),
            s.status_ignored as u8,
            n,
            alt.map(mv).unwrap_or(""),
            alt.map(|a| num(a.s.median_s)).unwrap_or_default(),
            old.get(&r.mon.dex).map(|x| x.to_string()).unwrap_or_default(),
            row_group(data, r, cfg),
            score_tail(&s)
        )
        .unwrap();
    }
    let best_path = format!("{out_dir}/rank_best_starter.csv");
    std::fs::write(&best_path, text).unwrap();
    eprintln!("wrote {long_path} ({} runs)\nwrote {best_path} ({} species)", rows.len(), best.len());
}

/// tasks <file>: each line "dex,move,item,fill[,buffs][,stop][,heal_below][,lock][,mods]".
/// fill is ';'-separated stat indices (0 atk … 6 mag, 7 xp, 8 heal) or empty.
/// lock is "index:count;..." (start with that many, and do not take more).
/// Writes the input columns plus median, mean, bootstrap, p75, p90 and how many runs reached 3/5/10 min.
fn tasks_cmd(data: &Data, cfg: &Cfg) {
    let text = std::fs::read_to_string(&cfg.rest[1]).expect("tasks file");
    let lines: Vec<Vec<String>> = text.lines().filter(|l| !l.is_empty()).map(|l| l.split(',').map(String::from).collect()).collect();
    let tables = Tables::new();
    let done = AtomicUsize::new(0);
    let total = lines.len();
    let rows: Vec<String> = lines
        .par_iter()
        .map(|c| {
            // move: "primary" or "primary+companion+..." (explicit group)
            let mut parts = c[1].split('+');
            let (mon, start) = find(data, &c[0], parts.next().unwrap());
            let explicit: Vec<String> = parts.map(String::from).collect();
            let mut sub = Cfg { item: c[2].clone(), fill: if c[3].is_empty() { vec![] } else { c[3].split(';').map(|x| x.parse().unwrap()).collect() }, rest: vec![], out: None, ..*cfg_clone(cfg) };
            if let Some(s) = c.get(5) {
                if !s.is_empty() {
                    sub.stop = s.parse().unwrap();
                }
            }
            if let Some(h) = c.get(6) {
                if !h.is_empty() {
                    sub.heal_below = h.parse().unwrap();
                }
            }
            if let Some(lock) = c.get(7) {
                if !lock.is_empty() {
                    sub.locks = parse_locks(lock);
                }
            }
            sub.dd = cfg.dd;
            sub.agi = cfg.agi;
            if !explicit.is_empty() {
                sub.comps = Some(explicit);
            }
            // optional 5th column: buffs held in the group, ';'-separated (sd, dd, hd, agi); "-" = none.
            // An empty column keeps the group default (2+2 is Swords Dance and Harden).
            if let Some(b) = c.get(4) {
                if !b.is_empty() {
                    let mut mask = 0u8;
                    for x in b.split(';').filter(|x| !x.is_empty() && *x != "-") {
                        match x {
                            "sd" => mask |= 1,
                            "dd" => { mask |= 1; sub.dd = true; }
                            "np" => { mask |= 1; sub.np = true; }
                            "hd" => mask |= 2,
                            "agi" => { mask |= 2; sub.agi = true; }
                            _ => panic!("buff {x}"),
                        }
                    }
                    sub.buffs = Some(mask);
                }
            }
            // optional 9th column: species overrides for counterfactuals, "r=14.08;spd=105;hp=99;atk=1.17".
            let modded = c.get(8).filter(|m| !m.is_empty()).map(|m| with_mods(mon, m));
            let s = run_species(data, &tables, modded.as_ref().unwrap_or(mon), start, &sub);
            let d = done.fetch_add(1, Ordering::Relaxed) + 1;
            if d % 500 == 0 { eprintln!("  {d}/{total}"); }
            format!(
                "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}",
                c[0],
                c[1],
                c[2],
                c[3],
                c.get(4).map(String::as_str).unwrap_or(""),
                c.get(5).map(String::as_str).unwrap_or(""),
                c.get(6).map(String::as_str).unwrap_or(""),
                c.get(7).map(String::as_str).unwrap_or(""),
                c.get(8).map(String::as_str).unwrap_or(""),
                num(s.median_s),
                num(s.mean_s),
                num(s.boot_lo),
                num(s.boot_hi),
                num(s.p75_s),
                num(s.p90_s),
                num(s.median_lvl),
                s.alive180,
                s.alive300,
                s.alive600,
                num(s.median_kills),
                num(s.p10_kills),
                num(s.p90_kills),
                num(s.median_bosses),
                num(s.median_kpm),
                num(s.median_coins),
                num(s.p10_coins),
                num(s.p90_coins),
                num(s.p10_dealt),
                num(s.p90_dealt),
                score_tail(&s)
            )
        })
        .collect();
    let path = cfg.out.clone().expect("--out");
    std::fs::write(&path, format!("dex,move,item,fill,buffs,stop,heal_below,lock,mods,median_s,mean_s,boot_lo,boot_hi,p75_s,p90_s,median_lvl,alive180,alive300,alive600,median_kills,p10_kills,p90_kills,median_bosses,median_kpm,median_coins,p10_coins,p90_coins,p10_dealt,p90_dealt,median_dealt,median_score,mean_score,score_lo,score_hi\n{}\n", rows.join("\n"))).unwrap();
    eprintln!("wrote {path}");
}

fn with_mods(mon: &Mon, mods: &str) -> Mon {
    let mut m = mon.clone();
    for kv in mods.split(';').filter(|p| !p.is_empty()) {
        let (k, v) = kv.split_once('=').unwrap_or_else(|| panic!("mod {kv}"));
        let v: f64 = v.parse().unwrap_or_else(|_| panic!("mod {kv}"));
        match k {
            "r" => m.r = v,
            "spd" => m.spd = v,
            "hp" => m.hp = v,
            "atk" => m.atk = v,
            _ => panic!("mod {k}"),
        }
    }
    m
}

fn cfg_clone(c: &Cfg) -> Box<Cfg> {
    Box::new(Cfg { seeds: c.seeds, seconds: c.seconds, bot: c.bot, cards: c.cards, terrain: c.terrain, status: c.status, out: None, group: c.group, dd: c.dd, np: c.np, agi: c.agi, xkinds: c.xkinds, legacy: c.legacy, item: c.item.clone(), fill: c.fill.clone(), buffs: c.buffs, comps: c.comps.clone(), swap: c.swap, crit: c.crit, full_cards: c.full_cards, stop: c.stop, heal_below: c.heal_below, dodge: c.dodge, locks: c.locks.clone(), synergy: c.synergy, no_synergy: c.no_synergy, bot_set: c.bot_set, seed0: c.seed0, count: c.count, rest: vec![] })
}

fn cmp_run(a: &Summary, b: &Summary) -> std::cmp::Ordering {
    // A total order. Overlapping score intervals are still a tie on the page
    // (build/combos.py); folding that test into the sort is not transitive.
    cmp_desc(a.median_score, b.median_score)
        .then(cmp_desc(a.mean_score, b.mean_score))
        .then(cmp_desc(a.median_s, b.median_s))
        .then(cmp_desc(a.median_kills, b.median_kills))
}

fn score_tail(s: &Summary) -> String {
    format!("{},{},{},{},{}", num(s.median_dealt), num(s.median_score), num(s.mean_score), num(s.score_lo), num(s.score_hi))
}

fn synergy_cmd(data: &Data, cfg: &Cfg) {
    let mut jobs = Vec::new();
    let mut covered = 0usize;
    for mon in &data.dex {
        let specs = synergy_specs(data, mon);
        if !specs.is_empty() {
            covered += 1;
        }
        for spec in specs {
            jobs.push(Job { mon, start: spec.start, comps: Some(spec.comps), buffs: Some(spec.buffs) });
        }
    }
    if cfg.count {
        println!("species {covered} groups {}", jobs.len());
        return;
    }
    eprintln!(
        "synergy: {} groups x {} seeds, {} threads (terrain, status, group {})",
        jobs.len(),
        cfg.seeds,
        rayon::current_num_threads(),
        cfg.group
    );
    let mut rows = run_jobs(data, jobs, cfg);
    rows.sort_by(|a, b| a.mon.dex.cmp(&b.mon.dex).then(cmp_run(&a.s, &b.s)));
    let path = cfg.out.clone().expect("--out");
    if let Some(dir) = std::path::Path::new(&path).parent() {
        if !dir.as_os_str().is_empty() {
            std::fs::create_dir_all(dir).unwrap();
        }
    }
    let mut text = String::from(
        "dex,name,group,median_s,mean_s,boot_lo,boot_hi,p10_s,p90_s,median_kills,median_lvl,status_ignored,median_dealt,median_score,mean_score,score_lo,score_hi\n",
    );
    for r in &rows {
        let s = &r.s;
        writeln!(
            text,
            "{},{},{},{},{},{},{},{},{},{},{},{},{}",
            r.mon.dex,
            csv_escape(&r.mon.name),
            row_group(data, r, cfg),
            num(s.median_s),
            num(s.mean_s),
            num(s.boot_lo),
            num(s.boot_hi),
            num(s.p10_s),
            num(s.p90_s),
            num(s.median_kills),
            num(s.median_lvl),
            s.status_ignored as u8,
            score_tail(s)
        )
        .unwrap();
    }
    std::fs::write(&path, text).unwrap();
    eprintln!("wrote {path}");
}

fn rank(data: &Data, cfg: &Cfg) {
    let tasks: Vec<(&Mon, usize)> = data.dex.iter().map(|m| (m, m.start)).collect();
    eprintln!("rank: {} species x {} seeds, {} threads", tasks.len(), cfg.seeds, rayon::current_num_threads());
    let mut rows = run_tasks(data, tasks, cfg);
    rows.sort_by(|a, b| {
        cmp_run(&a.s, &b.s)
            .then(cmp_desc(a.s.mean_hp_frac.unwrap_or(0.0), b.s.mean_hp_frac.unwrap_or(0.0)))
            .then(a.mon.dex.cmp(&b.mon.dex))
    });
    let note = if cfg.status { ", ralentización, quemadura y veneno modelados" } else { "" };
    let note = if cfg.swap { format!("{note}, cambio de hueco al 35% de la recarga") } else { note.to_string() };
    let mut text = format!(
        "# step={} seeds=1-{} seconds={} bot={} sin mejoras permanentes, {}, controlador compartido{}\n\
         dex,name,n,median_s,mean_s,boot_lo,boot_hi,p10_s,p90_s,median_kills,median_lvl,n_cap,mean_hp_frac,status_ignored,median_dealt,median_score,mean_score,score_lo,score_hi\n",
        DT, cfg.seeds, cfg.seconds, bot_name(cfg.bot), group_label(cfg), note
    );
    for r in &rows {
        let s = &r.s;
        writeln!(
            text,
            "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}",
            r.mon.dex,
            csv_escape(&r.mon.name),
            s.n,
            num(s.median_s),
            num(s.mean_s),
            num(s.boot_lo),
            num(s.boot_hi),
            num(s.p10_s),
            num(s.p90_s),
            num(s.median_kills),
            num(s.median_lvl),
            s.n_cap,
            s.mean_hp_frac.map(num).unwrap_or_default(),
            s.status_ignored as u8,
            score_tail(s)
        )
        .unwrap();
    }
    let path = cfg.out.clone().unwrap_or_else(|| "sim/out/rank_fresh.csv".into());
    if let Some(dir) = std::path::Path::new(&path).parent() {
        std::fs::create_dir_all(dir).unwrap();
    }
    std::fs::write(&path, text).unwrap();
    eprintln!("wrote {path}");
}

fn formulas_cmd(data: &Data) {
    fn ty(name: &str) -> u8 {
        data::TYPES.iter().position(|t| *t == name).unwrap() as u8
    }
    fn combo_for(data: &Data, names: &[&str]) -> u16 {
        let want: Vec<u8> = names.iter().copied().map(ty).collect();
        if let Some(mon) = data.dex.iter().find(|m| m.types == want) {
            return mon.combo;
        }
        data.dex
            .iter()
            .find(|m| {
                let mut a = m.types.clone();
                let mut b = want.clone();
                a.sort();
                b.sort();
                a == b
            })
            .unwrap_or_else(|| panic!("no species with types {names:?}"))
            .combo
    }
    let num = |v: f64| format!("{:.10}", v);
    let mut hits = Vec::new();
    let cases = [
        ("ghost", &["psychic"][..], 40.0, 1.2, 80.0, 40.0, 30.0, 10.0, 2u8),
        ("fire", &["grass", "steel"][..], 55.0, 1.0, 75.0, 75.0, 20.0, 0.0, 1u8),
        ("water", &["fire"][..], 12.0, 2.5, 200.0, 40.0, 100.0, 50.0, 2u8),
        ("normal", &["ghost"][..], 80.0, 1.0, 50.0, 50.0, 5.0, 0.0, 1u8),
        ("dragon", &["fairy"][..], 90.0, 0.8, 10.0, 120.0, 8.0, 4.0, 1u8),
    ];
    for (atk, defs, dmg, atk_mul, df, sd, hp, shield, cat) in cases {
        let def = if cat == 2 { sd } else { df };
        let taken = engine::defense_guard(def);
        let combo = combo_for(data, defs);
        let dealt = engine::faithful_hit_dealt(hp, shield, dmg, atk_mul, ty(atk), combo, &data.tmult, taken, cat);
        let mult = data.tmult[ty(atk) as usize][combo as usize];
        hits.push(format!(
            "{{\"atk\":\"{atk}\",\"def\":\"{}\",\"mult\":{},\"taken\":{},\"dealt\":{}}}",
            defs.join("/"),
            num(mult),
            num(taken),
            num(dealt)
        ));
    }
    let guards: Vec<String> = [0.0, 5.0, 75.0, 150.0, 400.0]
        .into_iter()
        .map(|d| format!("{{\"def\":{},\"v\":{}}}", num(d), num(engine::defense_guard(d))))
        .collect();
    let spawns: Vec<String> = [0.0, 32.0, 60.0, 105.0, 180.0, 600.0]
        .into_iter()
        .map(|t| format!("{{\"t\":{},\"rate\":{}}}", num(t), num(engine::spawn_per_second(t))))
        .collect();
    let caps: Vec<String> = [100.0, 130.0, 180.0, 260.0]
        .into_iter()
        .map(|s| format!("{{\"spd\":{},\"v\":{}}}", num(s), num(engine::cap_spd(s))))
        .collect();
    let touch: Vec<String> = [0.0, 420.0, 600.0, 900.0]
        .into_iter()
        .map(|t| format!("{{\"arena\":{},\"v\":{}}}", num(t), num(engine::judgment_touch_pct(t))))
        .collect();
    let chase: Vec<String> = [0.0, 100.0, 300.0, 600.0]
        .into_iter()
        .map(|t| format!("{{\"arena\":{},\"v\":{}}}", num(t), num(engine::judgment_chase_k(t))))
        .collect();
    let mono: Vec<String> = [
        (&["psychic"][..], "psychic"),
        (&["psychic"][..], "ghost"),
        (&["grass", "poison"][..], "grass"),
        (&["fire"][..], "fire"),
    ]
    .into_iter()
    .map(|(own, atk)| {
        let types: Vec<u8> = own.iter().map(|n| ty(n)).collect();
        format!("{{\"own\":\"{}\",\"atk\":\"{atk}\",\"v\":{}}}", own.join("/"), num(engine::mono_factor(&types, ty(atk))))
    })
    .collect();
    let damps: Vec<String> = [(0.0, 100.0, 6.0, 0.05), (10.0, -4.0, 3.5, 0.2), (1.0, 1.0, 5.0, 1.0)]
        .into_iter()
        .map(|(a, b, r, dt)| format!("{{\"a\":{},\"b\":{},\"rate\":{},\"dt\":{},\"v\":{}}}", num(a), num(b), num(r), num(dt), num(engine::damp(a, b, r, dt))))
        .collect();
    println!(
        "{{\"guard\":[{}],\"spawn\":[{}],\"capSpd\":[{}],\"touch\":[{}],\"chase\":[{}],\"hit\":[{}],\"mono\":[{}],\"damp\":[{}]}}",
        guards.join(","),
        spawns.join(","),
        caps.join(","),
        touch.join(","),
        chase.join(","),
        hits.join(","),
        mono.join(","),
        damps.join(",")
    );
}

fn find<'a>(data: &'a Data, dex: &str, mv: &str) -> (&'a Mon, usize) {
    let dex: u32 = dex.parse().expect("dex");
    let mon = data.dex.iter().find(|m| m.dex == dex).expect("dex not found");
    (mon, *data.move_ix.get(mv).expect("move not found"))
}

fn read_f64s(path: &str) -> Vec<f64> {
    let b = std::fs::read(path).expect("read trace");
    b.chunks_exact(8).map(|c| f64::from_le_bytes(c.try_into().unwrap())).collect()
}

fn print_result(r: &RunResult) {
    println!(
        "{{\"time\":{:?},\"kills\":{},\"bosses\":{},\"coins\":{:?},\"level\":{},\"capped\":{},\"statusIgnored\":{},\"hp\":{:?},\"maxHp\":{:?},\"hpFrac\":{:?}}}",
        r.time, r.kills, r.bosses, r.coins, r.level, r.capped, r.status_ignored, r.hp, r.max_hp, r.hp_frac
    );
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let mut cfg = parse(&args);
    let synergy_cmd_on = cfg.rest.first().map(String::as_str) == Some("synergy");
    if cfg.no_synergy {
        cfg.synergy = false;
    } else if cfg.group > 0 || synergy_cmd_on {
        cfg.synergy = true;
    }
    // The published tier path. Hex does nothing useful without status, and the
    // site's medians are played on the real map.
    if synergy_cmd_on {
        if cfg.group == 0 {
            cfg.group = 2;
        }
        cfg.status = true;
        cfg.terrain = true;
    }
    // Faithful runs (status, extra kinds, or a fixed group) play with the kite bot.
    // `--bot repulse` keeps the old policy for a before/after check. Parity never sets these.
    if !cfg.bot_set && (cfg.status || cfg.xkinds || cfg.group > 0) {
        cfg.bot = Bot::Play;
    }
    let data = Data::load("v3/v3_data.json");
    let t0 = Instant::now();
    match cfg.rest.first().map(String::as_str) {
        Some("sweep") => sweep(&data, &cfg),
        Some("formulas") => formulas_cmd(&data),
        Some("rank") => rank(&data, &cfg),
        Some("synergy") => synergy_cmd(&data, &cfg),
        Some("tasks") => tasks_cmd(&data, &cfg),
        Some("run") => {
            let (mon, start) = find(&data, &cfg.rest[1], &cfg.rest[2]);
            let ext = ext_for(&data, mon, start, &cfg);
            let opts = Opts { seed: cfg.rest[3].parse().unwrap(), seconds: cfg.seconds, cards: cfg.cards, bot: cfg.bot, terrain: cfg.terrain, trace: cfg.out.is_some(), status: cfg.status, ext };
            print_result(&run_match(&Libm, &data, &Tables::new(), mon, start, &opts));
            if let Some(path) = cfg.out.as_ref().filter(|p| p.ends_with(".json")) {
                // Compact trace for a browser replay: [t, hp, x, y, enemies, shots, enemy shots],
                // enemies as id,dex,x,y,fly; shots as x,y,vx,vy; enemy shots as x,y,vx,vy,type.
                let r = |v: f64| v.round() as i64;
                let frames: Vec<String> = take_trace()
                    .iter()
                    .map(|f| {
                        let es: Vec<String> = f.enemies.iter().zip(&f.ids).map(|(e, id)| format!("{},{},{},{},{}", id.0, id.1, r(e.0), r(e.1), e.3 as u8)).collect();
                        let ss: Vec<String> = f.shots.iter().map(|s| format!("{},{},{},{}", r(s.0), r(s.1), r(s.2), r(s.3))).collect();
                        let xs: Vec<String> = f.e_shots.iter().map(|s| format!("{},{},{},{},\"{}\"", r(s.0), r(s.1), r(s.2), r(s.3), data::TYPES[s.4 as usize])).collect();
                        format!("[{:.2},{:.1},{},{},[{}],[{}],[{}]]", f.t, f.hp, r(f.x), r(f.y), es.join(","), ss.join(","), xs.join(","))
                    })
                    .collect();
                std::fs::write(path, format!("{{\"frames\":[\n{}\n]}}\n", frames.join(",\n"))).expect("write trace");
            } else if let Some(path) = &cfg.out {
                let mut csv = String::from("t,x,y,hp,enemies\n");
                for f in take_trace() {
                    let es: Vec<String> = f.enemies.iter().map(|e| format!("{:.0}:{:.0}:{:.0}:{}", e.0, e.1, e.2, e.3 as u8)).collect();
                    csv += &format!("{:.2},{:.1},{:.1},{:.1},{}\n", f.t, f.x, f.y, f.hp, es.join(" "));
                }
                std::fs::write(path, csv).expect("write trace");
            }
        }
        Some("mapdump") => {
            print!("{}", terrain::dump(cfg.rest[1].parse().unwrap(), cfg.rest.get(2).map_or(80, |h| h.parse().unwrap())));
        }
        Some("mapcheck") => {
            println!("{}", terrain::digest(cfg.rest[1].parse().unwrap(), cfg.rest.get(2).map_or(80, |h| h.parse().unwrap())));
        }
        Some("mathcheck") => {
            let names = ["sin", "cos", "atan2", "pow"];
            let mut bad = [0usize; 4];
            let mut all = [0usize; 4];
            let mut shown = [0usize; 4];
            for path in &cfg.rest[1..] {
                for rec in read_f64s(path).chunks_exact(4) {
                    let (f, a, b, out) = (rec[0] as usize - 1, rec[1], rec[2], rec[3]);
                    let mine = match f {
                        0 => Libm.sin(a),
                        1 => Libm.cos(a),
                        2 => Libm.atan2(a, b),
                        _ => Libm.pow(a, b),
                    };
                    all[f] += 1;
                    if mine.to_bits() != out.to_bits() {
                        bad[f] += 1;
                        if shown[f] < 3 {
                            shown[f] += 1;
                            println!("  {}({a:?}, {b:?}) v8 {out:?} libm {mine:?}", names[f]);
                        }
                    }
                }
            }
            for f in 0..4 {
                println!("{}: {}/{} differ", names[f], bad[f], all[f]);
            }
        }
        Some("replay") => {
            let replay = Replay::new(read_f64s(&cfg.rest[1]));
            let js_tables = read_f64s(&cfg.rest[2]);
            let tables = Tables::new();
            let mine: Vec<f64> = tables.flat();
            assert_eq!(mine.len(), js_tables.len(), "table length");
            for (i, (a, b)) in mine.iter().zip(&js_tables).enumerate() {
                assert_eq!(a.to_bits(), b.to_bits(), "pow table entry {i}: rust {a} js {b}");
            }
            let (mon, start) = find(&data, &cfg.rest[3], &cfg.rest[4]);
            let opts = Opts { seed: cfg.rest[5].parse().unwrap(), seconds: cfg.seconds, cards: cfg.cards, bot: cfg.bot, terrain: cfg.terrain, trace: false, status: cfg.status, ext: Ext::default() };
            let r = run_match(&replay, &data, &tables, mon, start, &opts);
            assert!(replay.consumed_all(), "rust made fewer math calls ({}) than js", replay.calls());
            print_result(&r);
        }
        _ => {
            eprintln!("usage: pokesim sweep|rank|synergy|tasks|run|replay [--seeds N] [--seconds S] [--bot repulse|line] [--lvl1] [--terrain] [--status] [--group 2+2] [--no-synergy] [--out P]");
            std::process::exit(2);
        }
    }
    eprintln!("total {:.1}s", t0.elapsed().as_secs_f64());
}
