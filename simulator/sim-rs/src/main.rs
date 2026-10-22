//! Rust-only PokéSurvivor diagnostics. See simulator/README.md for current commands.
//! Historical ranking entrypoints are disabled until calibration and readiness review.

mod combat_runner;
mod cache_lock;
mod synergy_lab;
mod attack_lab;
mod batch;
mod data;
mod engine;
mod funnel;
mod math;
mod production;
mod radii;
mod ranking;
mod repertorio;
mod research;
mod rng;
mod selection;
mod selection_io;
mod stats;
mod terrain;

use data::{Data, Kind, Mon};
use engine::{run_match, take_trace, Bot, Ext, Item, Opts, RunResult, Tables, DT};
use std::sync::{Mutex, OnceLock};

/// dex -> simulated pool attacks sorted by solo (old-mode) median, best first
static PARTNERS: OnceLock<HashMap<u32, Vec<String>>> = OnceLock::new();
use math::Libm;
use rayon::prelude::*;
use stats::{csv_escape, num, summarize, Summary};
use std::collections::HashMap;
use std::fmt::Write as _;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Instant;

struct Cfg {
    ability: Option<String>,
    nature: String,
    tms: Vec<String>,
    second: Option<String>,
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
    /// group mode: the whole group is bonded from t=0 (no rift bonds); bosses and every kind stay on
    bonded: bool,
    item: String,
    fill: Vec<u8>,
    buffs: Option<u8>,
    /// The attack buff of a searched group. None picks it from the lead attack (`use_nasty`).
    atk_buff: Option<AtkBuff>,
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
    list: bool,
    /// Only these candidates (`dex|move` for sweep, `dex|group` for synergy), one per line in the file.
    only: Option<std::collections::HashSet<String>>,
    /// synergy: run the `dex|group` lines of `--only` as given, not the generated groups.
    explicit: bool,
    rest: Vec<String>,
}

fn parse(args: &[String]) -> Cfg {
    let mut c = Cfg {
        ability: None,
        nature: "hardy".into(),
        tms: Vec::new(),
        second: None,
        seeds: 200,
        seconds: 900.0,
        bot: Bot::Repulse,
        cards: true,
        terrain: false,
        status: true,
        out: None,
        group: 0,
        dd: false,
        np: false,
        agi: false,
        xkinds: true,
        legacy: false,
        bonded: false,
        item: "none".into(),
        fill: vec![],
        buffs: None,
        atk_buff: None,
        comps: None,
        swap: false,
        crit: 0.0,
        full_cards: false,
        stop: 0,
        heal_below: 0.0,
        dodge: 0.0,
        locks: vec![],
        synergy: false,
        no_synergy: false,
        bot_set: false,
        seed0: 0,
        count: false,
        list: false,
        only: None,
        explicit: false,
        rest: vec![],
    };
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--ability" => {
                i += 1;
                c.ability = Some(args[i].clone());
            }
            "--nature" => {
                i += 1;
                c.nature = args[i].clone();
            }
            "--tms" => {
                i += 1;
                c.tms = args[i].split(',').map(String::from).collect();
            }
            "--second" => {
                i += 1;
                c.second = Some(args[i].clone());
            }
            "--seeds" => {
                i += 1;
                c.seeds = args[i].parse().expect("--seeds");
            }
            "--seed0" => {
                i += 1;
                c.seed0 = args[i].parse().expect("--seed0");
            }
            "--count" => c.count = true,
            "--explicit" => c.explicit = true,
            "--list" => c.list = true,
            "--only" => {
                i += 1;
                let text = std::fs::read_to_string(&args[i]).expect("--only file");
                c.only = Some(
                    text.lines()
                        .map(str::trim)
                        .filter(|l| !l.is_empty() && !l.starts_with('#'))
                        .map(String::from)
                        .collect(),
                );
            }
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
                c.group = match args[i].as_str() {
                    "2+2" => 2,
                    "3+1" => 3,
                    "off" => 0,
                    x => panic!("--group {x}"),
                };
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
            "--legacy-group" => panic!("legacy rules were removed"),
            "--bonded" => c.bonded = true,
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
                panic!("--dodge was removed: use real movement and ability dodge rolls");
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
    for l in text
        .lines()
        .filter(|l| !l.starts_with('#') && !l.starts_with("dex,"))
    {
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
        rows.push((
            c[0].parse().unwrap(),
            c[2].to_string(),
            c[3].to_string(),
            score,
        ));
        let _ = n;
    }
    rows.sort_by(|a, b| {
        a.0.cmp(&b.0)
            .then(b.3.partial_cmp(&a.3).unwrap())
            .then(a.1.cmp(&b.1))
    });
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
        (burn.is_finite() && burn > 0.0)
            || (poison.is_finite() && poison > 0.0)
            || (slow.is_finite() && slow > 0.0)
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
        .map(|list| {
            list.iter()
                .filter_map(|id| data.move_ix.get(id.as_str()).copied())
                .collect()
        })
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
            // A second orbit uses its own orb list (step_side_orbs).
            if !m.is_attack() {
                return false;
            }
            m.kind.simulated() || m.levels[0].xk != 0
        })
        .collect();
    ids.sort_by(|&a, &b| {
        let syn = |ix| if pairs_with(data, start, ix) { 0u8 } else { 1 };
        let rank = |ix| solo.iter().position(|&p| p == ix).unwrap_or(10_000);
        syn(a)
            .cmp(&syn(b))
            .then(rank(a).cmp(&rank(b)))
            .then(data.moves[a].id.cmp(&data.moves[b].id))
    });
    ids
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
        // The buff is the start move's category buff, so a companion of the other category
        // would be left without one.
        let cat = cat_of(data, start);
        pool.iter()
            .copied()
            .filter(|&ix| cat_of(data, ix) == cat)
            .take(want)
            .collect()
    } else {
        Vec::new()
    };
    let item = Item::by_id(&cfg.item);
    // Slot 1 is the next leftover attack at level 1. Choice Band (player.js:141) cannot swap.
    let alt = if let Some(id) = &cfg.second {
        let ix = *data.move_ix.get(id).expect("unknown second move");
        assert!(
            ix != start && mon.start_choices(&data.moves).contains(&ix),
            "illegal second starting move"
        );
        Some(ix)
    } else if cfg.swap && !item.lock {
        pool.iter().copied().find(|&ix| !companions.contains(&ix))
    } else {
        None
    };
    let atk = cfg.atk_buff.unwrap_or_else(|| {
        if use_nasty(data, mon, start, &companions, cfg) {
            AtkBuff::Np
        } else if cfg.dd {
            AtkBuff::Dd
        } else {
            AtkBuff::Sd
        }
    });
    Ext {
        planned_buffs: None,
        initial_second: cfg.second.as_ref().map(|id| data.move_ix[id]),
        ability: cfg.ability.clone(),
        companions,
        buffs: cfg.buffs.unwrap_or(match cfg.group {
            2 => 3,
            3 => 1,
            _ => 0,
        }),
        dd: atk == AtkBuff::Dd,
        np: atk == AtkBuff::Np,
        agi: cfg.agi,
        item,
        fill: cfg.fill.clone(),
        rift: cfg.group > 0 && !cfg.legacy && !cfg.bonded,
        bonded: cfg.bonded,
        bosses: cfg.group > 0 && !cfg.legacy,
        alt,
        crit: cfg.crit,
        full_cards: cfg.full_cards,
        stop: cfg.stop,
        heal_below: cfg.heal_below,
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
    let configured = data
        .configure(mon, &cfg.nature, cfg.ability.as_deref(), &cfg.tms)
        .expect("run configuration");
    let mon = &configured;
    let ext = ext_for(data, mon, start, cfg);
    let runs: Vec<RunResult> = (1..=cfg.seeds)
        .map(|i| {
            let seed = cfg.seed0 + i;
            let opts = Opts {
                seed,
                seconds: cfg.seconds,
                cards: cfg.cards,
                bot: cfg.bot,
                terrain: cfg.terrain,
                trace: false,
                ext: ext.clone(),
            };
            run_match(&Libm, data, tables, mon, start, &opts)
        })
        .collect();
    if log_level() >= 2 {
        let label = run_label(data, mon, start, cfg);
        for (i, r) in runs.iter().enumerate() {
            eprintln!(
                "  run {label} seed {} t={:.1}s kills={} lvl={} capped={}",
                cfg.seed0 as usize + i + 1,
                r.time,
                r.kills,
                r.level,
                r.capped
            );
        }
    }
    summarize(&runs)
}

struct Row<'a> {
    mon: &'a Mon,
    start: usize,
    /// Empty and `kit == None` means the heuristic partner from `ext_for`.
    comps: Vec<usize>,
    kit: Option<Kit>,
    s: Summary,
}

struct Job<'a> {
    mon: &'a Mon,
    start: usize,
    comps: Option<Vec<usize>>,
    kit: Option<Kit>,
}

fn run_tasks<'a>(data: &'a Data, tasks: Vec<(&'a Mon, usize)>, cfg: &Cfg) -> Vec<Row<'a>> {
    let jobs = tasks
        .into_iter()
        .map(|(mon, start)| Job {
            mon,
            start,
            comps: None,
            kit: None,
        })
        .collect();
    run_jobs(data, jobs, cfg)
}

/// `POKESIM_LOG=groups` logs every finished job and each species when its last job ends;
/// `POKESIM_LOG=runs` also logs every seed. Logs go to stderr only.
fn log_level() -> u8 {
    static LOG: OnceLock<u8> = OnceLock::new();
    *LOG.get_or_init(|| match std::env::var("POKESIM_LOG").as_deref() {
        Ok("runs") => 2,
        Ok("groups") => 1,
        _ => 0,
    })
}

fn hms(secs: f64) -> String {
    let s = secs.round() as u64;
    format!("{}:{:02}:{:02}", s / 3600, (s / 60) % 60, s % 60)
}

fn run_label(data: &Data, mon: &Mon, start: usize, cfg: &Cfg) -> String {
    let mut s = format!("{} {} {}", mon.dex, mon.name, data.moves[start].id);
    if let Some(c) = &cfg.comps {
        for id in c {
            s.push('+');
            s.push_str(id);
        }
    }
    if let Some(b) = cfg.buffs {
        let _ = write!(s, " buffs={b}");
    }
    s
}

fn run_jobs<'a>(data: &'a Data, jobs: Vec<Job<'a>>, cfg: &Cfg) -> Vec<Row<'a>> {
    let tables = Tables::new();
    let done = AtomicUsize::new(0);
    let total = jobs.len();
    if matches!(
        cfg.rest.first().map(String::as_str),
        Some("rank" | "sweep" | "synergy" | "tasks" | "repertorio")
    ) {
        panic!("historical ranking commands are retired; use candidates/evaluate. Current diagnostics do not validate a ranking");
    }
    if cfg.rest.first().map(String::as_str) == Some("run") {
        assert!(
            cfg.seconds > 0. && cfg.seconds <= 15.,
            "diagnostic runs are limited to 15 simulated seconds"
        );
    }
    let t0 = Instant::now();
    let left: Mutex<HashMap<u32, (usize, usize)>> = Mutex::new(HashMap::new());
    if log_level() > 0 {
        let mut l = left.lock().unwrap();
        for job in &jobs {
            l.entry(job.mon.dex).or_insert((0, 0)).1 += 1;
        }
        for v in l.values_mut() {
            v.0 = v.1;
        }
    }
    jobs
        .into_par_iter()
        .map(|job| {
            let t_job = Instant::now();
            let comps = job.comps.clone().unwrap_or_default();
            let explicit = job.comps.is_some() || job.kit.is_some();
            let s = if explicit {
                let mut sub = cfg_clone(cfg);
                if job.comps.is_some() {
                    sub.comps = Some(comps.iter().map(|&ix| data.moves[ix].id.clone()).collect());
                }
                if let Some(kit) = job.kit {
                    sub.buffs = Some(kit.buffs);
                    sub.atk_buff = Some(kit.atk);
                    sub.agi = kit.agi;
                }
                run_species(data, &tables, job.mon, job.start, &sub)
            } else {
                run_species(data, &tables, job.mon, job.start, cfg)
            };
            let d = done.fetch_add(1, Ordering::Relaxed) + 1;
            let row = Row { mon: job.mon, start: job.start, comps, kit: job.kit, s };
            let el = t0.elapsed().as_secs_f64();
            if log_level() == 0 {
                if d % 250 == 0 || d == total {
                    eprintln!("  {d}/{total}  {el:.1}s");
                }
                return row;
            }
            let eta = el / d as f64 * (total - d) as f64;
            eprintln!(
                "[{}] {d}/{total} {:5.1}%  #{} {}  {}  median_s {:.1}  kills {:.1}  job {:.2}s  eta {}",
                hms(el),
                100.0 * d as f64 / total as f64,
                row.mon.dex,
                row.mon.name,
                row_group(data, &row, cfg),
                row.s.median_s,
                row.s.median_kills,
                t_job.elapsed().as_secs_f64(),
                hms(eta),
            );
            let finished = {
                let mut l = left.lock().unwrap();
                let entry = l.get_mut(&row.mon.dex).expect("species counted");
                entry.0 -= 1;
                (entry.0 == 0).then_some(entry.1)
            };
            if let Some(groups) = finished {
                eprintln!("== #{} {} done: {} groups, at {}", row.mon.dex, row.mon.name, groups, hms(el));
            }
            row
        })
        .collect()
}

fn read_old_rank(path: &str) -> HashMap<u32, usize> {
    let mut m = HashMap::new();
    let Ok(text) = std::fs::read_to_string(path) else {
        return m;
    };
    let lines = text
        .lines()
        .filter(|l| !l.is_empty() && !l.starts_with('#') && !l.starts_with("dex,"));
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
    m.is_attack() && (m.kind.simulated() || m.levels[0].xk != 0 || m.kind == Kind::Orbit)
}

fn level_dps(l: &data::MoveLvl) -> f64 {
    let cd = if l.cd.is_finite() && l.cd > 0.0 {
        l.cd
    } else {
        1.0
    };
    let n = if l.count.is_finite() && l.count > 0.0 {
        l.count
    } else {
        1.0
    };
    let dmg = if l.dmg.is_finite() { l.dmg } else { 0.0 };
    dmg * n / cd
}

/// The attack buff a group bonds. Danza Espada and Danza Dragón raise `patk`, Maquinación
/// raises `satk` (moves.js).
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
enum AtkBuff {
    Sd,
    Np,
    Dd,
}

impl AtkBuff {
    fn id(self) -> &'static str {
        match self {
            AtkBuff::Sd => "swords-dance",
            AtkBuff::Np => "nasty-plot",
            AtkBuff::Dd => "dragon-dance",
        }
    }
}

/// The buffs of a group. `buffs` bit 1 bonds `atk`, bit 2 bonds Agility (`agi`) or Harden.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
struct Kit {
    buffs: u8,
    atk: AtkBuff,
    agi: bool,
}

struct Spec {
    start: usize,
    comps: Vec<usize>,
    kit: Kit,
}

/// How many of a species' best attacks are crossed as pairs and trios, either category.
/// Solo-sweep order and the move-tier list (`data/move_tierlist_v4.csv`) both count;
/// a move takes the better of the two ranks.
const TOP_ALL: usize = 6;

fn attack_list(data: &Data, mon: &Mon) -> Vec<usize> {
    mon.start_choices(&data.moves)
        .into_iter()
        .filter(|&ix| castable(&data.moves[ix]))
        .collect()
}

fn ensure_partners() {
    if PARTNERS.get().is_some() {
        return;
    }
    for p in [
        "results/fixed_group/solo_sweep.csv",
        "simulator/results/fixed_group/solo_sweep.csv",
    ] {
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
            let Ok(text) = std::fs::read_to_string(p) else {
                continue;
            };
            for line in text
                .lines()
                .filter(|l| !l.is_empty() && !l.starts_with("category,"))
            {
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

/// Every attack of the species, best first. Rank is the better of the species' solo
/// sweep order and the global move-tier order,
/// so a kind the solo sweep skipped (Hex) still enters when its tier is high.
fn ranked_attacks(data: &Data, mon: &Mon, atk: &[usize]) -> Vec<usize> {
    ensure_partners();
    let solo: Vec<usize> = PARTNERS
        .get()
        .and_then(|p| p.get(&mon.dex))
        .map(|list| {
            list.iter()
                .filter_map(|id| data.move_ix.get(id.as_str()).copied())
                .collect()
        })
        .unwrap_or_default();
    let scores = tier_scores();
    let mut by_tier = atk.to_vec();
    by_tier.sort_by(|&a, &b| {
        let sa = scores
            .get(&data.moves[a].id)
            .copied()
            .unwrap_or(f64::NEG_INFINITY);
        let sb = scores
            .get(&data.moves[b].id)
            .copied()
            .unwrap_or(f64::NEG_INFINITY);
        sb.partial_cmp(&sa)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(data.moves[a].id.cmp(&data.moves[b].id))
    });
    let solo_pos = |ix: usize| solo.iter().position(|&p| p == ix).unwrap_or(10_000);
    let tier_pos = |ix: usize| by_tier.iter().position(|&p| p == ix).unwrap_or(10_000);
    let mut ranked = atk.to_vec();
    ranked.sort_by(|&a, &b| {
        solo_pos(a)
            .min(tier_pos(a))
            .cmp(&solo_pos(b).min(tier_pos(b)))
            .then(data.moves[a].id.cmp(&data.moves[b].id))
    });
    ranked
}

fn cat_of(data: &Data, ix: usize) -> u8 {
    data.moves[ix].levels[0].cat
}

/// Every buff fill of these attacks inside the four bond slots (start included).
/// Two attacks: an attack buff plus Harden or Agility. Three attacks: an attack buff, or
/// Harden or Agility. An attack buff that raises no attack of the group is left out
/// (Danza Espada and Danza Dragón only raise physical moves, Maquinación only special
/// ones), and Danza Dragón needs a species that learns it.
fn kits(data: &Data, mon: &Mon, attacks: &[usize]) -> Vec<Kit> {
    let has = |cat: u8| attacks.iter().any(|&ix| cat_of(data, ix) == cat);
    let mut atk = Vec::new();
    if has(1) {
        atk.push(AtkBuff::Sd);
        if mon.pool.contains(&data.dragon_dance) {
            atk.push(AtkBuff::Dd);
        }
    }
    if has(2) {
        atk.push(AtkBuff::Np);
    }
    let mut out = Vec::new();
    match attacks.len() {
        2 => {
            for &a in &atk {
                for agi in [false, true] {
                    out.push(Kit {
                        buffs: 3,
                        atk: a,
                        agi,
                    });
                }
            }
        }
        3 => {
            for &a in &atk {
                out.push(Kit {
                    buffs: 1,
                    atk: a,
                    agi: false,
                });
            }
            for agi in [false, true] {
                out.push(Kit {
                    buffs: 2,
                    atk: AtkBuff::Sd,
                    agi,
                });
            }
        }
        _ => {}
    }
    out
}

fn dedup_specs(specs: Vec<Spec>) -> Vec<Spec> {
    let mut seen = std::collections::HashSet::new();
    let mut out = Vec::new();
    for s in specs {
        if seen.insert((s.start, s.comps.clone(), s.kit)) {
            out.push(s);
        }
    }
    out
}

/// Every species gets a real group search. The attack sets are pruned: every ordered
/// pair and trio of the species' best `TOP_ALL` attacks (either category), Hex with its
/// best appliers, and dash pairs. Each attack set is then simulated with every buff fill
/// from `kits`. Nothing prefers one fill, category or shape over another; the score picks.
/// A species with fewer than two attacks has nothing to bond.
fn synergy_specs(data: &Data, mon: &Mon) -> Vec<Spec> {
    let atk = attack_list(data, mon);
    if atk.len() < 2 {
        return vec![];
    }
    let pay: Vec<usize> = atk
        .iter()
        .copied()
        .filter(|&ix| is_payoff(&data.moves[ix].levels[0]))
        .collect();
    let mut app: Vec<usize> = atk
        .iter()
        .copied()
        .filter(|&ix| is_applier(&data.moves[ix].levels[0]))
        .collect();
    app.sort_by(|&a, &b| {
        level_dps(&data.moves[b].levels[0])
            .partial_cmp(&level_dps(&data.moves[a].levels[0]))
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(data.moves[a].id.cmp(&data.moves[b].id))
    });
    let pay: Vec<usize> = pay.into_iter().take(2).collect();
    app.truncate(3);
    // (start, companions) attack sets; the buff fills come after.
    let mut sets: Vec<(usize, Vec<usize>)> = Vec::new();
    for &p in &pay {
        for &a in &app {
            if p != a {
                sets.push((p, vec![a]));
                sets.push((a, vec![p]));
            }
        }
    }
    let trio = 3.min(app.len());
    for i in 0..trio {
        for j in (i + 1)..trio {
            let (a, b) = (app[i], app[j]);
            for &p in &pay {
                if p != a && p != b {
                    sets.push((p, vec![a, b]));
                    sets.push((a, vec![p, b]));
                }
            }
        }
    }
    // Plain groups, both leads. The bond waits on the rift, so the lead is most of the
    // median and the partner is the tie-break. Both orders are scored.
    let ranked = ranked_attacks(data, mon, &atk);
    let pool = &ranked[..TOP_ALL.min(ranked.len())];
    for &a in pool {
        for &b in pool {
            if a == b {
                continue;
            }
            sets.push((a, vec![b]));
            push_thirds(data, pool, &atk, a, b, &mut sets);
        }
    }
    // Dash invuln is its own relation. Score every ordered dash pair, not only the
    // ones that also land in the top list (Jumpluff, Honchkrow, Rowlet, Dartrix).
    let dashes: Vec<usize> = atk
        .iter()
        .copied()
        .filter(|&ix| data.moves[ix].levels[0].xk == 5)
        .collect();
    for &a in &dashes {
        for &b in &dashes {
            if a != b {
                sets.push((a, vec![b]));
            }
        }
    }
    let mut out = Vec::new();
    for (start, comps) in sets {
        let members: Vec<usize> = std::iter::once(start)
            .chain(comps.iter().copied())
            .collect();
        for kit in kits(data, mon, &members) {
            out.push(Spec {
                start,
                comps: comps.clone(),
                kit,
            });
        }
    }
    dedup_specs(out)
}

/// The fourth slot as a third attack. Every other member of the top list takes it
/// (companions in rank order), and so does the strongest status partner of either
/// member (Sludge + Hex).
fn push_thirds(
    data: &Data,
    pool: &[usize],
    atk: &[usize],
    a: usize,
    b: usize,
    out: &mut Vec<(usize, Vec<usize>)>,
) {
    let rank = |ix: usize| pool.iter().position(|&p| p == ix).unwrap_or(usize::MAX);
    let mut thirds: Vec<usize> = pool.iter().copied().filter(|&c| c != a && c != b).collect();
    // The same trio is reached from every order of its companions; keep the rank order.
    thirds.retain(|&c| rank(b) < rank(c));
    let mut syn: Vec<usize> = atk
        .iter()
        .copied()
        .filter(|&c| c != a && c != b && (pairs_with(data, a, c) || pairs_with(data, b, c)))
        .collect();
    syn.sort_by(|&x, &y| {
        level_dps(&data.moves[y].levels[0])
            .partial_cmp(&level_dps(&data.moves[x].levels[0]))
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(data.moves[x].id.cmp(&data.moves[y].id))
    });
    if let Some(c) = syn.first().copied() {
        if !thirds.contains(&c) && !pool.contains(&c) {
            thirds.push(c);
        }
    }
    for c in thirds {
        out.push((a, vec![b, c]));
    }
}

fn group_name(data: &Data, start: usize, comps: &[usize], kit: Kit) -> String {
    let mut parts = vec![data.moves[start].id.clone()];
    for &c in comps {
        parts.push(data.moves[c].id.clone());
    }
    if kit.buffs & 1 != 0 {
        parts.push(kit.atk.id().to_string());
    }
    if kit.buffs & 2 != 0 {
        parts.push((if kit.agi { "agility" } else { "harden" }).to_string());
    }
    parts.join("+")
}

fn ext_kit(ext: &Ext) -> Kit {
    let atk = if ext.np {
        AtkBuff::Np
    } else if ext.dd {
        AtkBuff::Dd
    } else {
        AtkBuff::Sd
    };
    Kit {
        buffs: ext.buffs,
        atk,
        agi: ext.agi,
    }
}

fn row_group(data: &Data, row: &Row, cfg: &Cfg) -> String {
    if let Some(kit) = row.kit {
        return group_name(data, row.start, &row.comps, kit);
    }
    if cfg.group == 0 {
        return data.moves[row.start].id.clone();
    }
    let ext = ext_for(data, row.mon, row.start, cfg);
    group_name(data, row.start, &ext.companions, ext_kit(&ext))
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
            let extra =
                (cfg.xkinds || (cfg.group > 0 && !cfg.legacy)) && data.moves[id].levels[0].xk != 0;
            if let Some(only) = &cfg.only {
                if !only.contains(&format!("{}|{}", mon.dex, data.moves[id].id)) {
                    continue;
                }
            }
            if data.moves[id].kind.simulated() || extra {
                if cfg.group > 0 {
                    let ext = ext_for(data, mon, id, cfg);
                    seen.insert((mon.dex, id, ext.companions.clone(), ext_kit(&ext)));
                }
                jobs.push(Job {
                    mon,
                    start: id,
                    comps: None,
                    kit: None,
                });
            }
        }
        if cfg.synergy && cfg.group > 0 {
            for spec in synergy_specs(data, mon) {
                let key = (mon.dex, spec.start, spec.comps.clone(), spec.kit);
                if let Some(only) = &cfg.only {
                    if !only.contains(&format!(
                        "{}|{}",
                        mon.dex,
                        group_name(data, spec.start, &spec.comps, spec.kit)
                    )) {
                        continue;
                    }
                }
                if seen.insert(key) {
                    jobs.push(Job {
                        mon,
                        start: spec.start,
                        comps: Some(spec.comps),
                        kit: Some(spec.kit),
                    });
                }
            }
        }
    }
    eprintln!(
        "sweep: {} candidates x {} seeds, {} threads",
        jobs.len(),
        cfg.seeds,
        rayon::current_num_threads()
    );
    let mut rows = run_jobs(data, jobs, cfg);
    let mv = |r: &Row| data.moves[r.start].id.as_str();
    rows.sort_by(|a, b| a.mon.dex.cmp(&b.mon.dex).then_with(|| mv(a).cmp(mv(b))));

    let out_dir = cfg.out.clone().unwrap_or_else(|| "out".into());
    std::fs::create_dir_all(&out_dir).unwrap();
    let mut long = format!(
        "# barrido: todos los movimientos simulados del pool como inicial. seeds=1-{} seconds={} bot={}\n\
         dex,name,start,kind,n,median_s,mean_s,boot_lo,boot_hi,p10_s,p90_s,median_kills,median_lvl,status_ignored,group,median_dealt,median_score,mean_score,score_lo,score_hi,score_a,score_b\n",
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
            // Best move is an attack that dealt damage.
            let mut picked: Vec<&Row> = g
                .iter()
                .copied()
                .filter(|&r| data.moves[r.start].is_attack() && r.s.median_dealt > 0.0)
                .collect();
            if picked.is_empty() {
                picked = g
                    .iter()
                    .copied()
                    .filter(|&r| data.moves[r.start].is_attack())
                    .collect();
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
    let old = read_old_rank("out/rank_200.csv");
    let mut text = format!(
        "# mejor movimiento inicial por especie. seeds=1-{} seconds={} bot={}\n\
         rank,dex,name,best_start,best_kind,median_s,mean_s,boot_lo,boot_hi,p10_s,p90_s,median_kills,median_lvl,status_ignored,n_candidates,alt_start,alt_median_s,rank_old_200,group,median_dealt,median_score,mean_score,score_lo,score_hi,score_a,score_b\n",
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
            old.get(&r.mon.dex)
                .map(|x| x.to_string())
                .unwrap_or_default(),
            row_group(data, r, cfg),
            score_tail(&s)
        )
        .unwrap();
    }
    let best_path = format!("{out_dir}/rank_best_starter.csv");
    std::fs::write(&best_path, text).unwrap();
    eprintln!(
        "wrote {long_path} ({} runs)\nwrote {best_path} ({} species)",
        rows.len(),
        best.len()
    );
}

/// tasks <file>: each line "dex,move,item,fill[,buffs][,stop][,heal_below][,lock][,mods]".
/// fill is ';'-separated stat indices (0 atk … 6 mag, 7 xp, 8 heal) or empty.
/// lock is "index:count;..." (start with that many, and do not take more).
/// Writes the input columns plus median, mean, bootstrap, p75, p90 and how many runs reached 3/5/10 min.
fn tasks_cmd(data: &Data, cfg: &Cfg) {
    let text = std::fs::read_to_string(&cfg.rest[1]).expect("tasks file");
    let lines: Vec<Vec<String>> = text
        .lines()
        .filter(|l| !l.is_empty())
        .map(|l| l.split(',').map(String::from).collect())
        .collect();
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
    std::fs::write(&path, format!("dex,move,item,fill,buffs,stop,heal_below,lock,mods,median_s,mean_s,boot_lo,boot_hi,p75_s,p90_s,median_lvl,alive180,alive300,alive600,median_kills,p10_kills,p90_kills,median_bosses,median_kpm,median_coins,p10_coins,p90_coins,p10_dealt,p90_dealt,median_dealt,median_score,mean_score,score_lo,score_hi,score_a,score_b\n{}\n", rows.join("\n"))).unwrap();
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
    Box::new(Cfg {
        ability: c.ability.clone(),
        nature: c.nature.clone(),
        tms: c.tms.clone(),
        second: c.second.clone(),
        seeds: c.seeds,
        seconds: c.seconds,
        bot: c.bot,
        cards: c.cards,
        terrain: c.terrain,
        status: c.status,
        out: None,
        group: c.group,
        dd: c.dd,
        np: c.np,
        agi: c.agi,
        xkinds: c.xkinds,
        legacy: c.legacy,
        bonded: c.bonded,
        item: c.item.clone(),
        fill: c.fill.clone(),
        buffs: c.buffs,
        atk_buff: c.atk_buff,
        comps: c.comps.clone(),
        swap: c.swap,
        crit: c.crit,
        full_cards: c.full_cards,
        stop: c.stop,
        heal_below: c.heal_below,
        dodge: c.dodge,
        locks: c.locks.clone(),
        synergy: c.synergy,
        no_synergy: c.no_synergy,
        bot_set: c.bot_set,
        seed0: c.seed0,
        count: c.count,
        list: c.list,
        only: c.only.clone(),
        explicit: c.explicit,
        rest: vec![],
    })
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
    format!(
        "{},{},{},{},{},{},{}",
        num(s.median_dealt),
        num(s.median_score),
        num(s.mean_score),
        num(s.score_lo),
        num(s.score_hi),
        num(s.score_a),
        num(s.score_b)
    )
}

/// A group name as `group_name` writes it: attacks (start first), then the attack buff, then Harden or Agility.
fn parse_group(data: &Data, group: &str) -> Option<(usize, Vec<usize>, Kit)> {
    let mut atoms = Vec::new();
    let mut atk = None;
    let mut buffs = 0u8;
    let mut agi = false;
    for part in group.split('+') {
        match part {
            "swords-dance" => {
                atk = Some(AtkBuff::Sd);
                buffs |= 1;
            }
            "nasty-plot" => {
                atk = Some(AtkBuff::Np);
                buffs |= 1;
            }
            "dragon-dance" => {
                atk = Some(AtkBuff::Dd);
                buffs |= 1;
            }
            "harden" | "agility" => {
                if buffs & 2 != 0 {
                    return None;
                }
                buffs |= 2;
                agi = part == "agility";
            }
            id => {
                let ix = *data.move_ix.get(id)?;
                if data.moves[ix].kind_name == "buff" {
                    return None;
                }
                atoms.push(ix);
            }
        }
    }
    let start = *atoms.first()?;
    let kit = Kit {
        buffs,
        atk: atk.unwrap_or(AtkBuff::Sd),
        agi,
    };
    Some((start, atoms[1..].to_vec(), kit))
}

fn explicit_jobs<'a>(data: &'a Data, cfg: &Cfg) -> Vec<Job<'a>> {
    let only = cfg.only.as_ref().expect("--explicit needs --only");
    let mut lines: Vec<&String> = only.iter().collect();
    lines.sort();
    lines
        .into_iter()
        .map(|line| {
            let (dex, group) = line
                .split_once('|')
                .unwrap_or_else(|| panic!("--explicit line {line}"));
            let dex: u32 = dex.parse().expect("dex");
            let mon = data
                .dex
                .iter()
                .find(|m| m.dex == dex)
                .unwrap_or_else(|| panic!("no dex {dex}"));
            let (start, comps, kit) =
                parse_group(data, group).unwrap_or_else(|| panic!("bad group {line}"));
            Job {
                mon,
                start,
                comps: Some(comps),
                kit: Some(kit),
            }
        })
        .collect()
}

fn synergy_cmd(data: &Data, cfg: &Cfg) {
    let mut jobs = Vec::new();
    let mut covered = 0usize;
    if cfg.explicit {
        jobs = explicit_jobs(data, cfg);
    } else {
        for mon in &data.dex {
            let specs = synergy_specs(data, mon);
            if !specs.is_empty() {
                covered += 1;
            }
            for spec in specs {
                let name = group_name(data, spec.start, &spec.comps, spec.kit);
                if let Some(only) = &cfg.only {
                    if !only.contains(&format!("{}|{}", mon.dex, name)) {
                        continue;
                    }
                }
                if cfg.list {
                    println!("{}|{}", mon.dex, name);
                    continue;
                }
                jobs.push(Job {
                    mon,
                    start: spec.start,
                    comps: Some(spec.comps),
                    kit: Some(spec.kit),
                });
            }
        }
    }
    if cfg.list {
        return;
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
        "dex,name,group,median_s,mean_s,boot_lo,boot_hi,p10_s,p90_s,median_kills,median_lvl,status_ignored,median_dealt,median_score,mean_score,score_lo,score_hi,score_a,score_b\n",
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
    eprintln!(
        "rank: {} species x {} seeds, {} threads",
        tasks.len(),
        cfg.seeds,
        rayon::current_num_threads()
    );
    let mut rows = run_tasks(data, tasks, cfg);
    rows.sort_by(|a, b| {
        cmp_run(&a.s, &b.s)
            .then(cmp_desc(
                a.s.mean_hp_frac.unwrap_or(0.0),
                b.s.mean_hp_frac.unwrap_or(0.0),
            ))
            .then(a.mon.dex.cmp(&b.mon.dex))
    });
    let note = if cfg.status {
        ", ralentización, quemadura y veneno modelados"
    } else {
        ""
    };
    let note = if cfg.swap {
        format!("{note}, cambio de hueco al 35% de la recarga")
    } else {
        note.to_string()
    };
    let mut text = format!(
        "# step={} seeds=1-{} seconds={} bot={} sin mejoras permanentes, {}, controlador compartido{}\n\
         dex,name,n,median_s,mean_s,boot_lo,boot_hi,p10_s,p90_s,median_kills,median_lvl,n_cap,mean_hp_frac,status_ignored,median_dealt,median_score,mean_score,score_lo,score_hi,score_a,score_b\n",
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
    let path = cfg
        .out
        .clone()
        .unwrap_or_else(|| "out/rank_fresh.csv".into());
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
        (
            "ghost",
            &["psychic"][..],
            40.0,
            1.2,
            80.0,
            40.0,
            30.0,
            10.0,
            2u8,
        ),
        (
            "fire",
            &["grass", "steel"][..],
            55.0,
            1.0,
            75.0,
            75.0,
            20.0,
            0.0,
            1u8,
        ),
        (
            "water",
            &["fire"][..],
            12.0,
            2.5,
            200.0,
            40.0,
            100.0,
            50.0,
            2u8,
        ),
        (
            "normal",
            &["ghost"][..],
            80.0,
            1.0,
            50.0,
            50.0,
            5.0,
            0.0,
            1u8,
        ),
        (
            "dragon",
            &["fairy"][..],
            90.0,
            0.8,
            10.0,
            120.0,
            8.0,
            4.0,
            1u8,
        ),
    ];
    for (atk, defs, dmg, atk_mul, df, sd, hp, shield, cat) in cases {
        let def = if cat == 2 { sd } else { df };
        let taken = engine::defense_guard(def);
        let combo = combo_for(data, defs);
        let dealt = engine::faithful_hit_dealt(
            hp,
            shield,
            dmg,
            atk_mul,
            ty(atk),
            combo,
            &data.tmult,
            taken,
            cat,
        );
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
        .map(|d| {
            format!(
                "{{\"def\":{},\"v\":{}}}",
                num(d),
                num(engine::defense_guard(d))
            )
        })
        .collect();
    let spawns: Vec<String> = [0.0, 32.0, 60.0, 105.0, 180.0, 600.0]
        .into_iter()
        .map(|t| {
            format!(
                "{{\"t\":{},\"rate\":{}}}",
                num(t),
                num(engine::spawn_per_second(t))
            )
        })
        .collect();
    let caps: Vec<String> = [100.0, 130.0, 180.0, 260.0]
        .into_iter()
        .map(|s| format!("{{\"spd\":{},\"v\":{}}}", num(s), num(engine::cap_spd(s))))
        .collect();
    let touch: Vec<String> = [0.0, 420.0, 600.0, 900.0]
        .into_iter()
        .map(|t| {
            format!(
                "{{\"arena\":{},\"v\":{}}}",
                num(t),
                num(engine::judgment_touch_pct(t))
            )
        })
        .collect();
    let chase: Vec<String> = [0.0, 100.0, 300.0, 600.0]
        .into_iter()
        .map(|t| {
            format!(
                "{{\"arena\":{},\"v\":{}}}",
                num(t),
                num(engine::judgment_chase_k(t))
            )
        })
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
        format!(
            "{{\"own\":\"{}\",\"atk\":\"{atk}\",\"v\":{}}}",
            own.join("/"),
            num(engine::mono_factor(&types, ty(atk)))
        )
    })
    .collect();
    let damps: Vec<String> = [
        (0.0, 100.0, 6.0, 0.05),
        (10.0, -4.0, 3.5, 0.2),
        (1.0, 1.0, 5.0, 1.0),
    ]
    .into_iter()
    .map(|(a, b, r, dt)| {
        format!(
            "{{\"a\":{},\"b\":{},\"rate\":{},\"dt\":{},\"v\":{}}}",
            num(a),
            num(b),
            num(r),
            num(dt),
            num(engine::damp(a, b, r, dt))
        )
    })
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
    let mon = data
        .dex
        .iter()
        .find(|m| m.dex == dex)
        .expect("dex not found");
    (mon, *data.move_ix.get(mv).expect("move not found"))
}

fn print_result(r: &RunResult) {
    assert!(
        [r.time, r.hp, r.max_hp, r.dealt, r.risk.damage]
            .iter()
            .all(|x| x.is_finite()),
        "non-finite run result"
    );
    println!(
        "{}",
        serde_json::json!({"time":r.time,"kills":r.kills,"bosses":r.bosses,"coins":r.coins,"level":r.level,"capped":r.capped,"hp":r.hp,"maxHp":r.max_hp,"dealt":r.dealt,
      "risk":{"contactAttempts":r.risk.contact_attempts,"hits":r.risk.hits,"damage":r.risk.damage,"contactSeconds":r.risk.contact_seconds,"surroundedSeconds":r.risk.surrounded_seconds,"maxSurrounded":r.risk.max_surrounded,"invulnerableSeconds":r.risk.invulnerable_seconds,"dashCasts":r.risk.dash_casts,"dashHitsAfter":r.risk.dash_hits_after}})
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
    if matches!(cfg.rest.first().map(String::as_str), Some("attack-lab" | "synergy-lab" | "ranking" | "fingerprint")) {
        let runtime_game = std::fs::read("data/game.json").expect("read current game data");
        if runtime_game.as_slice() != include_bytes!("../../data/game.json") {
            eprintln!("Game data changed since this binary was built. Rebuild before laboratory or ranking commands so provenance and cache dependencies match the actual simulation.");
            std::process::exit(2);
        }
    }
    let data = Data::load("data/game.json");
    eprintln!(
        "game={} engine=4 nature={} ability={} tms={} second={}",
        data.commit,
        cfg.nature,
        cfg.ability.as_deref().unwrap_or("slot-1"),
        cfg.tms.join(","),
        cfg.second.as_deref().unwrap_or("none")
    );
    if matches!(
        cfg.rest.first().map(String::as_str),
        Some("rank" | "sweep" | "synergy" | "tasks" | "repertorio")
    ) {
        panic!("historical ranking commands are retired; use candidates/evaluate. Current diagnostics do not validate a ranking");
    }
    if cfg.rest.first().map(String::as_str) == Some("run") {
        assert!(
            cfg.seconds > 0. && cfg.seconds <= 15.,
            "diagnostic runs are limited to 15 simulated seconds"
        );
    }
    let t0 = Instant::now();
    match cfg.rest.first().map(String::as_str) {
        Some("production") => production::command(&data, &cfg.rest[1..]),
        Some("attack-lab") => {
            if let Err(error) = attack_lab::command(&data, &cfg.rest[1..]) {
                eprintln!("{error}");
                std::process::exit(2);
            }
        },
        Some("synergy-lab") => {
            if let Err(error) = synergy_lab::command(&data, &cfg.rest[1..]) {
                eprintln!("{error}");
                std::process::exit(2);
            }
        },
        Some("ranking") => {
            if let Err(error) = ranking::command(&data, &cfg.rest[1..]) {
                eprintln!("{error}");
                std::process::exit(2);
            }
        },
        Some("funnel") => {
            eprintln!("The exhaustive funnel is archived. Use attack-lab and ranking; see docs/simulator/laboratory-runner.md. Historical diagnostics require legacy-funnel explicitly.");
            std::process::exit(2);
        },
        Some("legacy-funnel") => funnel::command(&data, &cfg.rest[1..]),
        Some("fingerprint") => println!("{}", research::fingerprint()),
        Some("candidates") => {
            research::candidates(&data, cfg.rest[1].parse().expect("dex"), cfg.list, false)
        }
        Some("configurations") => {
            research::candidates(&data, cfg.rest[1].parse().expect("dex"), cfg.list, true)
        }
        Some("select") => selection_io::command(&cfg.rest[1]),
        Some("evaluate") => research::evaluate(&data, &cfg.rest[1]),
        Some("plan") | Some("resume") => batch::command(&data, &cfg.rest),
        Some("sweep") => sweep(&data, &cfg),
        Some("formulas") => formulas_cmd(&data),
        Some("rank") => rank(&data, &cfg),
        Some("synergy") => synergy_cmd(&data, &cfg),
        Some("tasks") => tasks_cmd(&data, &cfg),
        Some("repertorio") => {
            let path = cfg
                .rest
                .get(1)
                .expect("usage: pokesim repertorio <starter_sweep.csv>");
            let text = std::fs::read_to_string(path).unwrap_or_else(|e| panic!("read {path}: {e}"));
            println!(
                "{}",
                repertorio::to_json(&repertorio::openings_from_sweep(&data, &text))
            );
        }
        Some("run") => {
            let (mon, start) = find(&data, &cfg.rest[1], &cfg.rest[2]);
            let configured = data
                .configure(mon, &cfg.nature, cfg.ability.as_deref(), &cfg.tms)
                .expect("run configuration");
            let mon = &configured;
            assert!(
                mon.start_choices(&data.moves).contains(&start),
                "illegal starting attack; teach the required TM first"
            );
            let ext = ext_for(&data, mon, start, &cfg);
            let opts = Opts {
                seed: cfg.rest[3].parse().unwrap(),
                seconds: cfg.seconds,
                cards: cfg.cards,
                bot: cfg.bot,
                terrain: cfg.terrain,
                trace: cfg.out.is_some(),
                ext,
            };
            print_result(&run_match(&Libm, &data, &Tables::new(), mon, start, &opts));
            if let Some(path) = cfg.out.as_ref().filter(|p| p.ends_with(".json")) {
                // Compact trace for a browser replay: [t, hp, x, y, enemies, shots, enemy shots],
                // enemies as id,dex,x,y,fly; shots as x,y,vx,vy; enemy shots as x,y,vx,vy,type.
                let r = |v: f64| v.round() as i64;
                let frames: Vec<String> = take_trace()
                    .iter()
                    .map(|f| {
                        let es: Vec<String> = f
                            .enemies
                            .iter()
                            .zip(&f.ids)
                            .map(|(e, id)| {
                                format!("{},{},{},{},{}", id.0, id.1, r(e.0), r(e.1), e.3 as u8)
                            })
                            .collect();
                        let ss: Vec<String> = f
                            .shots
                            .iter()
                            .map(|s| format!("{},{},{},{}", r(s.0), r(s.1), r(s.2), r(s.3)))
                            .collect();
                        let xs: Vec<String> = f
                            .e_shots
                            .iter()
                            .map(|s| {
                                format!(
                                    "{},{},{},{},\"{}\"",
                                    r(s.0),
                                    r(s.1),
                                    r(s.2),
                                    r(s.3),
                                    data::TYPES[s.4 as usize]
                                )
                            })
                            .collect();
                        format!(
                            "[{:.2},{:.1},{},{},[{}],[{}],[{}]]",
                            f.t,
                            f.hp,
                            r(f.x),
                            r(f.y),
                            es.join(","),
                            ss.join(","),
                            xs.join(",")
                        )
                    })
                    .collect();
                std::fs::write(
                    path,
                    format!("{{\"frames\":[\n{}\n]}}\n", frames.join(",\n")),
                )
                .expect("write trace");
            } else if let Some(path) = &cfg.out {
                let mut csv = String::from("t,x,y,hp,enemies\n");
                for f in take_trace() {
                    let es: Vec<String> = f
                        .enemies
                        .iter()
                        .map(|e| format!("{:.0}:{:.0}:{:.0}:{}", e.0, e.1, e.2, e.3 as u8))
                        .collect();
                    csv += &format!(
                        "{:.2},{:.1},{:.1},{:.1},{}\n",
                        f.t,
                        f.x,
                        f.y,
                        f.hp,
                        es.join(" ")
                    );
                }
                std::fs::write(path, csv).expect("write trace");
            }
        }
        Some("mapdump") => {
            print!(
                "{}",
                terrain::dump(
                    cfg.rest[1].parse().unwrap(),
                    cfg.rest.get(2).map_or(80, |h| h.parse().unwrap())
                )
            );
        }
        Some("mapcheck") => {
            println!(
                "{}",
                terrain::digest(
                    cfg.rest[1].parse().unwrap(),
                    cfg.rest.get(2).map_or(80, |h| h.parse().unwrap())
                )
            );
        }
        _ => {
            eprintln!("usage: pokesim production plan|run|resume|benchmark ... | sweep|rank|synergy|tasks|repertorio|run [--seeds N] [--seconds S] [--bot repulse|line] [--lvl1] [--terrain] [--status] [--group 2+2] [--no-synergy] [--out P]");
            std::process::exit(2);
        }
    }
    eprintln!("total {:.1}s", t0.elapsed().as_secs_f64());
}
