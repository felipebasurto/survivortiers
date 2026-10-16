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
//! Options: --seeds N (200) --seconds S (900) --bot repulse|line --lvl1
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
mod math;
mod rng;
mod stats;
mod terrain;

use data::{Data, Mon};
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
    agi: bool,
    xkinds: bool,
    legacy: bool,
    item: String,
    fill: Vec<u8>,
    buffs: Option<u8>,
    comps: Option<Vec<String>>,
    rest: Vec<String>,
}

fn parse(args: &[String]) -> Cfg {
    let mut c = Cfg { seeds: 200, seconds: 900.0, bot: Bot::Repulse, cards: true, terrain: false, status: false, out: None, group: 0, dd: false, agi: false, xkinds: false, legacy: false, item: "none".into(), fill: vec![], buffs: None, comps: None, rest: vec![] };
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--seeds" => {
                i += 1;
                c.seeds = args[i].parse().expect("--seeds");
            }
            "--seconds" => {
                i += 1;
                c.seconds = args[i].parse().expect("--seconds");
            }
            "--bot" => {
                i += 1;
                c.bot = match args[i].as_str() {
                    "repulse" => Bot::Repulse,
                    "line" => Bot::Line,
                    b => panic!("unknown bot {b}"),
                };
            }
            "--lvl1" => c.cards = false,
            "--terrain" => c.terrain = true,
            "--status" => c.status = true,
            "--group" => {
                i += 1;
                c.group = match args[i].as_str() { "2+2" => 2, "3+1" => 3, "off" => 0, x => panic!("--group {x}") };
            }
            "--partners" => {
                i += 1;
                PARTNERS.set(read_partners(&args[i])).ok();
            }
            "--dd" => c.dd = true,
            "--agi" => c.agi = true,
            "--xkinds" => c.xkinds = true,
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

fn read_partners(path: &str) -> HashMap<u32, Vec<String>> {
    let text = std::fs::read_to_string(path).expect("partners");
    let mut rows: Vec<(u32, String, String, f64)> = Vec::new();
    for l in text.lines().filter(|l| !l.starts_with('#') && !l.starts_with("dex,")) {
        let c: Vec<&str> = l.split(',').collect();
        let n = c.len();
        // dex,name,start,kind,n,median_s,... (name may hold no commas in this data)
        rows.push((c[0].parse().unwrap(), c[2].to_string(), c[3].to_string(), c[5].parse().unwrap()));
        let _ = n;
    }
    rows.sort_by(|a, b| a.0.cmp(&b.0).then(b.3.partial_cmp(&a.3).unwrap()).then(a.1.cmp(&b.1)));
    let mut m: HashMap<u32, Vec<String>> = HashMap::new();
    for (d, mv, kind, _) in rows {
        if kind == "orbit" {
            continue;
        }
        m.entry(d).or_default().push(mv);
    }
    m
}

/// The fixed main group for this primary: the next best (old-mode) attacks of the pool, then buffs.
fn ext_for(data: &Data, mon: &Mon, start: usize, cfg: &Cfg) -> Ext {
    let mut companions = Vec::new();
    if let Some(list) = &cfg.comps {
        companions = list.iter().map(|id| data.move_ix[id.as_str()]).collect();
    } else if cfg.group >= 2 {
        let want = (cfg.group - 1) as usize;
        if let Some(list) = PARTNERS.get().and_then(|p| p.get(&mon.dex)) {
            for id in list {
                let ix = data.move_ix[id.as_str()];
                if ix != start && companions.len() < want {
                    companions.push(ix);
                }
            }
        }
    }
    Ext {
        companions,
        buffs: cfg.buffs.unwrap_or(match cfg.group { 2 => 3, 3 => 1, _ => 0 }),
        dd: cfg.dd,
        agi: cfg.agi,
        item: Item::by_id(&cfg.item),
        fill: cfg.fill.clone(),
        xkinds: cfg.xkinds || (cfg.group > 0 && !cfg.legacy),
        rift: cfg.group > 0 && !cfg.legacy,
        bosses: cfg.group > 0 && !cfg.legacy,
    }
}

fn group_label(cfg: &Cfg) -> &'static str {
    match (cfg.group, cfg.legacy) { (2, false) => "grupo fijo 2 ataques + Danza Espada y Fortaleza con vínculos de grieta, jefes y todos los tipos de ataque", (3, false) => "grupo fijo 3 ataques + Danza Espada con vínculos de grieta, jefes y todos los tipos de ataque", (2, true) => "grupo fijo 2 ataques + Danza Espada y Fortaleza desde t=0, sin grietas, sin jefes", (3, true) => "grupo fijo 3 ataques + Danza Espada desde t=0, sin grietas, sin jefes", _ => "un movimiento, sin grietas, sin jefes" }
}

fn bot_name(b: Bot) -> &'static str {
    match b {
        Bot::Repulse => "repulse",
        Bot::Line => "line",
    }
}

fn run_species(data: &Data, tables: &Tables, mon: &Mon, start: usize, cfg: &Cfg) -> Summary {
    let ext = ext_for(data, mon, start, cfg);
    let runs: Vec<RunResult> = (1..=cfg.seeds)
        .map(|seed| {
            let opts = Opts { seed, seconds: cfg.seconds, cards: cfg.cards, bot: cfg.bot, terrain: cfg.terrain, trace: false, status: cfg.status, ext: ext.clone() };
            run_match(&Libm, data, tables, mon, start, &opts)
        })
        .collect();
    summarize(&runs)
}

struct Row<'a> {
    mon: &'a Mon,
    start: usize,
    s: Summary,
}

fn run_tasks<'a>(data: &'a Data, tasks: Vec<(&'a Mon, usize)>, cfg: &Cfg) -> Vec<Row<'a>> {
    let tables = Tables::new();
    let done = AtomicUsize::new(0);
    let total = tasks.len();
    let t0 = Instant::now();
    tasks
        .into_par_iter()
        .map(|(mon, start)| {
            let s = run_species(data, &tables, mon, start, cfg);
            let d = done.fetch_add(1, Ordering::Relaxed) + 1;
            if d % 250 == 0 || d == total {
                eprintln!("  {d}/{total}  {:.1}s", t0.elapsed().as_secs_f64());
            }
            Row { mon, start, s }
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
    b.partial_cmp(&a).unwrap()
}

fn sweep(data: &Data, cfg: &Cfg) {
    let mut tasks = Vec::new();
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
                tasks.push((mon, id));
            }
        }
    }
    eprintln!("sweep: {} candidates x {} seeds, {} threads", tasks.len(), cfg.seeds, rayon::current_num_threads());
    let mut rows = run_tasks(data, tasks, cfg);
    let mv = |r: &Row| data.moves[r.start].id.as_str();
    rows.sort_by(|a, b| a.mon.dex.cmp(&b.mon.dex).then_with(|| mv(a).cmp(mv(b))));

    let out_dir = cfg.out.clone().unwrap_or_else(|| "sim/out".into());
    std::fs::create_dir_all(&out_dir).unwrap();
    let mut long = format!(
        "# barrido: todos los movimientos simulados del pool como inicial. seeds=1-{} seconds={} bot={}\n\
         dex,name,start,kind,n,median_s,mean_s,boot_lo,boot_hi,p10_s,p90_s,median_kills,median_lvl,status_ignored\n",
        cfg.seeds, cfg.seconds, bot_name(cfg.bot)
    );
    for r in &rows {
        let s = &r.s;
        writeln!(
            long,
            "{},{},{},{},{},{},{},{},{},{},{},{},{},{}",
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
            s.status_ignored as u8
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
            g.sort_by(|a, b| {
                cmp_desc(a.s.median_s, b.s.median_s)
                    .then(cmp_desc(a.s.mean_s, b.s.mean_s))
                    .then_with(|| mv(a).cmp(mv(b)))
            });
            (g[0], g.len(), g.get(1).copied())
        })
        .collect();
    best.sort_by(|a, b| {
        cmp_desc(a.0.s.median_s, b.0.s.median_s)
            .then(cmp_desc(a.0.s.mean_s, b.0.s.mean_s))
            .then(a.0.mon.dex.cmp(&b.0.mon.dex))
    });
    let old = read_old_rank("sim/out/rank_200.csv");
    let mut text = format!(
        "# mejor movimiento inicial por especie. seeds=1-{} seconds={} bot={}\n\
         rank,dex,name,best_start,best_kind,median_s,mean_s,boot_lo,boot_hi,p10_s,p90_s,median_kills,median_lvl,status_ignored,n_candidates,alt_start,alt_median_s,rank_old_200\n",
        cfg.seeds, cfg.seconds, bot_name(cfg.bot)
    );
    for (i, (r, n, alt)) in best.iter().enumerate() {
        let s = &r.s;
        writeln!(
            text,
            "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}",
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
            old.get(&r.mon.dex).map(|x| x.to_string()).unwrap_or_default()
        )
        .unwrap();
    }
    let best_path = format!("{out_dir}/rank_best_starter.csv");
    std::fs::write(&best_path, text).unwrap();
    eprintln!("wrote {long_path} ({} runs)\nwrote {best_path} ({} species)", rows.len(), best.len());
}

/// tasks <file>: each line "dex,move,item,fill" (fill = ';'-separated stat indices or empty).
/// Runs the group config of cfg with that item and card order; writes dex,move,item,fill,median,mean,lo,hi.
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
            sub.dd = cfg.dd;
            sub.agi = cfg.agi;
            if !explicit.is_empty() {
                sub.comps = Some(explicit);
            }
            // optional 5th column: buffs held in the group, ';'-separated (sd, dd, hd, agi); "-" = none
            if let Some(b) = c.get(4) {
                let mut mask = 0u8;
                for x in b.split(';').filter(|x| !x.is_empty() && *x != "-") {
                    match x {
                        "sd" => mask |= 1,
                        "dd" => { mask |= 1; sub.dd = true; }
                        "hd" => mask |= 2,
                        "agi" => { mask |= 2; sub.agi = true; }
                        _ => panic!("buff {x}"),
                    }
                }
                sub.buffs = Some(mask);
                if mask == 0 { sub.buffs = Some(0); }
            }
            let s = run_species(data, &tables, mon, start, &sub);
            let d = done.fetch_add(1, Ordering::Relaxed) + 1;
            if d % 500 == 0 { eprintln!("  {d}/{total}"); }
            format!("{},{},{},{},{},{},{},{},{}", c[0], c[1], c[2], c[3], c.get(4).map(String::as_str).unwrap_or(""), num(s.median_s), num(s.mean_s), num(s.boot_lo), num(s.boot_hi))
        })
        .collect();
    let path = cfg.out.clone().expect("--out");
    std::fs::write(&path, format!("dex,move,item,fill,buffs,median_s,mean_s,boot_lo,boot_hi\n{}\n", rows.join("\n"))).unwrap();
    eprintln!("wrote {path}");
}

fn cfg_clone(c: &Cfg) -> Box<Cfg> {
    Box::new(Cfg { seeds: c.seeds, seconds: c.seconds, bot: c.bot, cards: c.cards, terrain: c.terrain, status: c.status, out: None, group: c.group, dd: c.dd, agi: c.agi, xkinds: c.xkinds, legacy: c.legacy, item: c.item.clone(), fill: c.fill.clone(), buffs: c.buffs, comps: c.comps.clone(), rest: vec![] })
}

fn rank(data: &Data, cfg: &Cfg) {
    let tasks: Vec<(&Mon, usize)> = data.dex.iter().map(|m| (m, m.start)).collect();
    eprintln!("rank: {} species x {} seeds, {} threads", tasks.len(), cfg.seeds, rayon::current_num_threads());
    let mut rows = run_tasks(data, tasks, cfg);
    rows.sort_by(|a, b| {
        cmp_desc(a.s.median_s, b.s.median_s)
            .then(cmp_desc(a.s.mean_s, b.s.mean_s))
            .then(cmp_desc(a.s.mean_hp_frac.unwrap_or(0.0), b.s.mean_hp_frac.unwrap_or(0.0)))
            .then(a.mon.dex.cmp(&b.mon.dex))
    });
    let note = if cfg.status { ", ralentización, quemadura y veneno modelados" } else { "" };
    let mut text = format!(
        "# step={} seeds=1-{} seconds={} bot={} sin mejoras permanentes, {}, controlador compartido{}\n\
         dex,name,n,median_s,mean_s,boot_lo,boot_hi,p10_s,p90_s,median_kills,median_lvl,n_cap,mean_hp_frac,status_ignored\n",
        DT, cfg.seeds, cfg.seconds, bot_name(cfg.bot), group_label(cfg), note
    );
    for r in &rows {
        let s = &r.s;
        writeln!(
            text,
            "{},{},{},{},{},{},{},{},{},{},{},{},{},{}",
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
            s.status_ignored as u8
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
        "{{\"time\":{:?},\"kills\":{},\"level\":{},\"capped\":{},\"statusIgnored\":{},\"hp\":{:?},\"maxHp\":{:?},\"hpFrac\":{:?}}}",
        r.time, r.kills, r.level, r.capped, r.status_ignored, r.hp, r.max_hp, r.hp_frac
    );
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let cfg = parse(&args);
    let data = Data::load("v3/v3_data.json");
    let t0 = Instant::now();
    match cfg.rest.first().map(String::as_str) {
        Some("sweep") => sweep(&data, &cfg),
        Some("rank") => rank(&data, &cfg),
        Some("tasks") => tasks_cmd(&data, &cfg),
        Some("run") => {
            let (mon, start) = find(&data, &cfg.rest[1], &cfg.rest[2]);
            let opts = Opts { seed: cfg.rest[3].parse().unwrap(), seconds: cfg.seconds, cards: cfg.cards, bot: cfg.bot, terrain: cfg.terrain, trace: false, status: cfg.status, ext: Ext::default() };
            let opts = Opts { trace: cfg.out.is_some(), ..opts };
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
            eprintln!("usage: pokesim sweep|rank|run|replay [--seeds N] [--seconds S] [--bot repulse|line] [--lvl1] [--terrain] [--out P]");
            std::process::exit(2);
        }
    }
    eprintln!("total {:.1}s", t0.elapsed().as_secs_f64());
}
