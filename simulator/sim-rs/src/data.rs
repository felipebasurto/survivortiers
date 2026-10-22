//! Loads the pinned schema-4 game dataset into typed combat data. Missing optional numbers become NaN,
//! which is how `undefined` behaves in the JS arithmetic it replaces.

use serde_json::Value;
use std::collections::HashMap;

pub const TYPES: [&str; 18] = [
    "normal", "fire", "water", "electric", "grass", "ice", "fighting", "poison", "ground",
    "flying", "psychic", "bug", "rock", "ghost", "dragon", "dark", "steel", "fairy",
];
pub const T_NORMAL: u8 = 0;
pub const T_FIRE: u8 = 1;
pub const T_WATER: u8 = 2;
pub const T_ELECTRIC: u8 = 3;
pub const T_GRASS: u8 = 4;
pub const T_ICE: u8 = 5;
pub const T_FIGHTING: u8 = 6;
pub const T_POISON: u8 = 7;
pub const T_GROUND: u8 = 8;
pub const T_PSYCHIC: u8 = 10;
pub const T_BUG: u8 = 11;
pub const T_ROCK: u8 = 12;
pub const T_GHOST: u8 = 13;
pub const T_DRAGON: u8 = 14;
pub const T_STEEL: u8 = 16;
pub const T_FAIRY: u8 = 17;
pub const T_DARK: u8 = 15;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Kind {
    Melee,
    Beam,
    Orbit,
    Nova,
    Projectile,
    Boomerang,
    /// buff, dash, cone, aura, chain, trail, mine, meteor, turret, and the 5a23d49 kinds
    /// (homing, bounce, charge, spin, quake, vortex, shove, stun): never fired on the parity path.
    Effect,
}

impl Kind {
    fn parse(s: &str) -> Kind {
        match s {
            "melee" => Kind::Melee,
            "beam" => Kind::Beam,
            "orbit" => Kind::Orbit,
            "nova" => Kind::Nova,
            "projectile" => Kind::Projectile,
            "boomerang" => Kind::Boomerang,
            _ => Kind::Effect,
        }
    }

    pub fn simulated(self) -> bool {
        self != Kind::Effect
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Stat {
    Pow = 0,
    Run = 1,
    Hp = 2,
    Cor = 3,
    Cd = 4,
    Rgn = 5,
    Mag = 6,
}

pub const STATS: [Stat; 7] = [
    Stat::Pow,
    Stat::Run,
    Stat::Hp,
    Stat::Cor,
    Stat::Cd,
    Stat::Rgn,
    Stat::Mag,
];
pub const CAPS: [u32; 7] = [40, 8, 99, 12, 10, 10, 6];

#[derive(Clone, Debug)]
pub struct MoveLvl {
    pub tags: u16,
    pub base_dmg: f64,
    pub kind: Kind,
    pub ty: u8,
    pub cd: f64,
    pub dmg: f64,
    pub radius: f64,
    pub arc: f64,
    pub width: f64,
    pub speed: f64,
    pub count: f64,
    pub spread: f64,
    pub pierce: f64,
    pub life: f64,
    pub size: f64,
    pub homing: f64,
    pub amount: f64,
    pub dur: f64,
    pub stacks: f64,
    /// burn, poison or slow present (none of them is applied unless `Opts::status`).
    pub status: bool,
    /// burn stacks per hit (NaN when absent), applied with `Opts::status`.
    pub burn: f64,
    /// poison stacks per hit (NaN when absent), applied with `Opts::status`.
    pub poison: f64,
    /// slow factor of the move (NaN when absent): enemy speed x (1 - slow) for 1.2 s after a hit.
    pub slow: f64,
    /// game kind the parity engine never fires (Kind::Effect), for the fixed-group mode:
    /// 0 none/buff, 1 cone, 2 meteor, 3 chain, 4 aura, 5 dash, 6 mine, 7 trail, 8 turret,
    /// 9 homing, 10 bounce, 11 charge, 12 spin, 13 quake, 14 vortex, 15 shove, 16 stun
    pub xk: u8,
    pub hex: f64,
    pub drain: f64,
    pub rate: f64,
    pub range: f64,
    /// impulse on a non-boss (enemy.js hurt knock). NaN when the move has none.
    pub knock: f64,
    /// rebounds a projectile makes (moves.js bounce, combat.js rebound). NaN when absent.
    pub bounce: f64,
    /// seconds a charge move glows before the beam leaves (moves.js charge). NaN when absent.
    pub charge: f64,
    /// px/s a vortex drags enemies toward its centre (moves.js pull). NaN when absent.
    pub pull: f64,
    /// seconds a stun zone freezes what it catches (moves.js stun). NaN when absent.
    pub stun: f64,
    /// buff stat: 0 none, 1 atk, 2 spd, 3 def, 4 regen (moves.js aqua-ring),
    /// 5 patk (Swords Dance / Dragon Dance), 6 satk (Nasty Plot). moves.js at e868b5e.
    pub buff: u8,
    /// 0 none (buffs), 1 physical, 2 special. moves.js PHYSICAL set.
    pub cat: u8,
}

#[derive(Clone, Debug)]
pub struct Move {
    pub id: String,
    pub kind_name: String,
    pub kind: Kind,
    pub max_lvl: usize,
    pub levels: Vec<MoveLvl>,
    pub evo: Option<MoveLvl>,
    pub needs: Option<Stat>,
}

impl Move {
    /// Deals damage and is not a buff (moves.js `kind: 'buff'` carries no `dmg`).
    pub fn is_attack(&self) -> bool {
        let l = &self.levels[0];
        self.kind_name != "buff" && l.buff == 0 && l.dmg.is_finite() && l.dmg > 0.0
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Beh {
    Chase,
    Tank,
    Charger,
    Runner,
    Bomber,
    Jumper,
    Ranged,
    Fan,
    Beamer,
    Zoner,
    Healer,
    Summoner,
    Shielder,
}

impl Beh {
    fn parse(s: &str) -> Beh {
        match s {
            "chase" => Beh::Chase,
            "tank" => Beh::Tank,
            "charger" => Beh::Charger,
            "runner" => Beh::Runner,
            "bomber" => Beh::Bomber,
            "jumper" => Beh::Jumper,
            "ranged" => Beh::Ranged,
            "fan" => Beh::Fan,
            "beamer" => Beh::Beamer,
            "zoner" => Beh::Zoner,
            "healer" => Beh::Healer,
            "summoner" => Beh::Summoner,
            "shielder" => Beh::Shielder,
            other => panic!("unknown enemy behavior {other}"),
        }
    }

    /// KEEPS in match.js: hold range and shoot.
    pub fn keeps(self) -> bool {
        matches!(
            self,
            Beh::Ranged
                | Beh::Fan
                | Beh::Beamer
                | Beh::Zoner
                | Beh::Healer
                | Beh::Summoner
                | Beh::Shielder
        )
    }

    pub fn no_touch(self) -> bool {
        matches!(self, Beh::Healer | Beh::Summoner)
    }
}

#[derive(Clone, Debug)]
pub struct Def {
    pub beh: Beh,
    pub hp: f64,
    pub spd: f64,
    pub dmg: f64,
    pub xp: f64,
    pub shot_dmg: f64,
    pub shot_cd: f64,
    pub range: f64,
    pub zones: f64,
    pub fan_n: f64,
}

#[derive(Clone, Debug)]
pub struct Cand {
    pub def: Def,
    /// national dex number, only used by traces
    pub dex: u16,
    /// index into `Data::combos`
    pub combo: u16,
    /// first type, used as the attack type of everything this enemy does
    pub ty0: u8,
    pub r: f64,
    /// hovers over terrain (G.Sprites.hovers)
    pub fly: bool,
    pub water: bool,
    pub fire: bool,
    /// weather.js sand safe types (rock, ground, steel): chip skips them
    pub sand_safe: bool,
    /// weather.js snow safe type (ice)
    pub snow_safe: bool,
    /// Attack multipliers and base defenses (stats.js / fetch_stats.py at e868b5e).
    pub pa: f64,
    pub sa: f64,
    pub df: f64,
    pub sd: f64,
}

#[derive(Clone, Debug)]
pub struct Tier {
    pub from: f64,
    pub cands: Vec<Cand>,
}

#[derive(Clone, Debug)]
pub struct Mon {
    pub dex: u32,
    pub name: String,
    pub types: Vec<u8>,
    pub combo: u16,
    pub hp: f64,
    pub spd: f64,
    pub atk: f64,
    pub r: f64,
    /// Attack multipliers and base defenses. atk stays max(pa, sa).
    pub pa: f64,
    pub sa: f64,
    pub df: f64,
    pub sd: f64,
    pub start: usize,
    pub pool: Vec<usize>,
    pub tms: Vec<usize>,
    pub abilities: Vec<Option<String>>,
    /// legendary or mythical (rift.js only spawns these in arenas)
    pub leg: bool,
    /// base stat total (enemies.js boss bands)
    pub bst: f64,
}

impl Mon {
    /// starters.js startChoices at ce57853. poolFor minus buffs, plus the stock start.
    /// The exported pool is poolFor(natural): the species' own type pools plus every Normal move.
    /// configure() adds taught TMs, which is poolFor without the natural flag. The stock start
    /// stays even when it is off-type (Confusion on Psyduck).
    pub fn start_choices(&self, moves: &[Move]) -> Vec<usize> {
        let mut ids: Vec<usize> = self
            .pool
            .iter()
            .copied()
            .filter(|&ix| moves[ix].kind_name != "buff")
            .collect();
        if !ids.contains(&self.start) {
            ids.push(self.start);
        }
        ids
    }
}

pub struct Data {
    pub commit: String,
    pub natures: Value,
    pub combos: Vec<Vec<u8>>,
    pub moves: Vec<Move>,
    pub move_ix: HashMap<String, usize>,
    pub dex: Vec<Mon>,
    pub tiers: Vec<Tier>,
    /// tmult[attack type][defender combo]
    pub tmult: Vec<Vec<f64>>,
    pub swords_dance: usize,
    pub harden: usize,
    pub dragon_dance: usize,
    pub agility: usize,
    pub nasty_plot: usize,
    /// Shop price of each TM id. A move already in the natural pool costs nothing.
    pub tm_prices: HashMap<String, u32>,
}

fn num(v: &Value, k: &str) -> f64 {
    v.get(k).and_then(Value::as_f64).unwrap_or(f64::NAN)
}

fn type_ix(s: &str) -> u8 {
    TYPES
        .iter()
        .position(|t| *t == s)
        .unwrap_or_else(|| panic!("unknown type {s}")) as u8
}

fn move_lvl(v: &Value) -> MoveLvl {
    let id = v["id"].as_str().unwrap_or("");
    let groups: &[&[&str]] = &[
        &["punch"],
        &["bite", "fang", "crunch", "jaw"],
        &["pulse", "aura-sphere"],
        &["cut", "slash", "blade", "razor", "scissor", "sword"],
        &[
            "voice", "buzz", "boom", "noise", "sing", "echo", "uproar", "snarl",
        ],
    ];
    let tags = groups.iter().enumerate().fold(0, |n, (i, g)| {
        n | if g.iter().any(|s| id.contains(s)) {
            1 << i
        } else {
            0
        }
    });
    MoveLvl {
        tags,
        base_dmg: v["baseDmg"].as_f64().unwrap_or_else(|| num(v, "dmg")),
        kind: Kind::parse(v["kind"].as_str().unwrap()),
        ty: type_ix(v["type"].as_str().unwrap()),
        cd: num(v, "cd"),
        dmg: num(v, "dmg"),
        radius: num(v, "radius"),
        arc: num(v, "arc"),
        width: num(v, "width"),
        speed: num(v, "speed"),
        count: num(v, "count"),
        spread: num(v, "spread"),
        pierce: num(v, "pierce"),
        life: num(v, "life"),
        size: num(v, "size"),
        homing: num(v, "homing"),
        amount: num(v, "amount"),
        dur: num(v, "dur"),
        stacks: num(v, "stacks"),
        status: ["burn", "poison", "slow"]
            .iter()
            .any(|k| v.get(*k).is_some_and(|x| !x.is_null())),
        burn: num(v, "burn"),
        poison: num(v, "poison"),
        slow: num(v, "slow"),
        xk: match v["kind"].as_str().unwrap() {
            "cone" => 1,
            "meteor" => 2,
            "chain" => 3,
            "aura" => 4,
            "dash" => 5,
            "mine" => 6,
            "trail" => 7,
            "turret" => 8,
            "homing" => 9,
            "bounce" => 10,
            "charge" => 11,
            "spin" => 12,
            "quake" => 13,
            "vortex" => 14,
            "shove" => 15,
            "stun" => 16,
            _ => 0,
        },
        hex: num(v, "hex"),
        drain: num(v, "drain"),
        rate: num(v, "rate"),
        range: num(v, "range"),
        knock: num(v, "knock"),
        bounce: num(v, "bounce"),
        charge: num(v, "charge"),
        pull: num(v, "pull"),
        stun: num(v, "stun"),
        buff: match v.get("stat").and_then(Value::as_str) {
            Some("atk") => 1,
            Some("spd") => 2,
            Some("def") => 3,
            Some("regen") => 4,
            Some("patk") => 5,
            Some("satk") => 6,
            _ => 0,
        },
        cat: match v.get("cat").and_then(Value::as_str) {
            Some("physical") => 1,
            Some("special") => 2,
            _ => 0,
        },
    }
}

fn stat_of(s: &str) -> Option<Stat> {
    match s {
        "atk" => Some(Stat::Pow),
        "spd" => Some(Stat::Run),
        "def" => Some(Stat::Cor),
        "hp" => Some(Stat::Hp),
        "cd" => Some(Stat::Cd),
        "rgn" => Some(Stat::Rgn),
        "mag" => Some(Stat::Mag),
        _ => None,
    }
}

impl Data {
    pub fn load(path: &str) -> Data {
        let raw: Value =
            serde_json::from_str(&std::fs::read_to_string(path).expect("read v3_data.json"))
                .expect("parse v3_data.json");

        assert_eq!(
            raw["schema"], 4,
            "engine requires the current schema-4 dataset"
        );
        assert_eq!(
            raw["gameCommit"],
            crate::research::GAME_COMMIT,
            "unexpected game version"
        );
        let tm = raw["tmult"].as_object().unwrap();
        let combo_names: Vec<String> = tm["normal"].as_object().unwrap().keys().cloned().collect();
        assert!(
            combo_names.len() <= 256,
            "combo bitsets require <=256 combinations"
        );
        let combo_ix: HashMap<String, u16> = combo_names
            .iter()
            .enumerate()
            .map(|(i, c)| (c.clone(), i as u16))
            .collect();
        let tmult: Vec<Vec<f64>> = TYPES
            .iter()
            .map(|t| {
                let row = tm[*t].as_object().unwrap();
                combo_names
                    .iter()
                    .map(|c| row[c].as_f64().unwrap())
                    .collect()
            })
            .collect();
        let combo_of = |types: &Value| -> u16 {
            let key: Vec<&str> = types
                .as_array()
                .unwrap()
                .iter()
                .map(|t| t.as_str().unwrap())
                .collect();
            let key = key.join("/");
            *combo_ix
                .get(&key)
                .unwrap_or_else(|| panic!("missing type combo {key}"))
        };

        let mut moves = Vec::new();
        let mut move_ix = HashMap::new();
        let mut ids: Vec<&String> = raw["moves"].as_object().unwrap().keys().collect();
        ids.sort();
        for id in ids {
            let m = &raw["moves"][id];
            let levels: Vec<MoveLvl> = m["levels"]
                .as_array()
                .unwrap()
                .iter()
                .map(move_lvl)
                .collect();
            let evo = if m["evo"].is_null() {
                None
            } else {
                Some(move_lvl(&m["evo"]))
            };
            move_ix.insert(id.clone(), moves.len());
            let kind_name = m["kind"].as_str().unwrap().to_string();
            moves.push(Move {
                id: id.clone(),
                kind: Kind::parse(&kind_name),
                kind_name,
                max_lvl: m["maxLvl"].as_u64().unwrap() as usize,
                levels,
                evo,
                needs: m["needs"].as_str().and_then(stat_of),
            });
        }

        let dex = raw["dex"]
            .as_array()
            .unwrap()
            .iter()
            .map(|p| Mon {
                dex: p["dex"].as_u64().unwrap() as u32,
                name: p["name"].as_str().unwrap().to_string(),
                types: p["types"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .map(|t| type_ix(t.as_str().unwrap()))
                    .collect(),
                combo: combo_of(&p["types"]),
                hp: num(p, "hp"),
                spd: num(p, "spd"),
                atk: num(p, "atk"),
                r: num(p, "r"),
                pa: num(p, "pa"),
                sa: num(p, "sa"),
                df: num(p, "df"),
                sd: num(p, "sd"),
                start: move_ix[p["start"].as_str().unwrap()],
                abilities: p["abilities"]
                    .as_array()
                    .map(|a| a.iter().map(|x| x.as_str().map(String::from)).collect())
                    .unwrap_or_default(),
                tms: p["tms"]
                    .as_array()
                    .map(|a| a.iter().map(|x| move_ix[x.as_str().unwrap()]).collect())
                    .unwrap_or_default(),
                pool: p["pool"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .map(|x| move_ix[x.as_str().unwrap()])
                    .collect(),
                leg: p["leg"].as_bool().unwrap_or(false),
                bst: num(p, "bst"),
            })
            .collect::<Vec<Mon>>();
        // nasty-plot is in each pool in v3_data.json. moves.js poolFor puts every
        // normal move in every pool, and the export now includes Maquinación there.

        let tiers = raw["tiers"]
            .as_array()
            .unwrap()
            .iter()
            .map(|t| Tier {
                from: num(t, "from"),
                cands: t["cands"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .map(|c| {
                        let d = &c["def"];
                        let types = c["types"].as_array().unwrap();
                        let has = |n: &str| types.iter().any(|t| t == n);
                        Cand {
                            def: Def {
                                beh: Beh::parse(d["behavior"].as_str().unwrap()),
                                hp: num(d, "hp"),
                                spd: num(d, "spd"),
                                dmg: num(d, "dmg"),
                                xp: num(d, "xp"),
                                shot_dmg: num(d, "shotDmg"),
                                shot_cd: num(d, "shotCd"),
                                range: num(d, "range"),
                                zones: num(d, "zones"),
                                fan_n: num(d, "fanN"),
                            },
                            dex: c["dex"].as_u64().unwrap_or(0) as u16,
                            combo: combo_of(&c["types"]),
                            ty0: type_ix(c["types"][0].as_str().unwrap()),
                            r: num(c, "r"),
                            fly: c["fly"].as_bool().unwrap_or(false),
                            water: has("water"),
                            fire: has("fire"),
                            sand_safe: has("rock") || has("ground") || has("steel"),
                            snow_safe: has("ice"),
                            pa: num(c, "pa"),
                            sa: num(c, "sa"),
                            df: num(c, "df"),
                            sd: num(c, "sd"),
                        }
                    })
                    .collect(),
            })
            .collect();

        let swords_dance = move_ix["swords-dance"];
        let harden = move_ix["harden"];
        let dragon_dance = move_ix["dragon-dance"];
        let agility = move_ix["agility"];
        let nasty_plot = move_ix["nasty-plot"];
        let tm_prices = raw["tmPrices"]
            .as_object()
            .unwrap_or_else(|| panic!("tmPrices missing"))
            .iter()
            .map(|(id, price)| {
                (
                    id.clone(),
                    price
                        .as_u64()
                        .unwrap_or_else(|| panic!("tm price {id}")) as u32,
                )
            })
            .collect();
        Data {
            commit: raw["gameCommit"].as_str().unwrap_or("5a23d49").into(),
            natures: raw["natures"].clone(),
            combos: combo_names
                .iter()
                .map(|s| s.split('/').map(type_ix).collect())
                .collect(),
            moves,
            move_ix,
            dex,
            tiers,
            tmult,
            swords_dance,
            harden,
            dragon_dance,
            agility,
            nasty_plot,
            tm_prices,
        }
    }
}

impl Data {
    pub fn configure(
        &self,
        base: &Mon,
        nature: &str,
        ability: Option<&str>,
        tms: &[String],
    ) -> Result<Mon, String> {
        let mut mon = base.clone();
        if let Some(id) = ability {
            if !mon.abilities.iter().flatten().any(|s| s == id) {
                return Err(format!("{} cannot have ability {id}", mon.name));
            }
        }
        let n = self
            .natures
            .as_array()
            .and_then(|a| a.iter().find(|n| n["id"] == nature))
            .ok_or_else(|| format!("unknown nature {nature}"))?;
        for (key, k) in [("up", 1.1), ("down", 0.9)] {
            match n[key].as_str().unwrap() {
                "pa" => mon.pa *= k,
                "sa" => mon.sa *= k,
                "df" => mon.df *= k,
                "sd" => mon.sd *= k,
                "spd" => mon.spd *= k,
                "" => {}
                x => return Err(format!("unknown nature stat {x}")),
            }
        }
        mon.atk = mon.pa.max(mon.sa);
        for id in tms {
            let ix = *self
                .move_ix
                .get(id)
                .ok_or_else(|| format!("unknown TM {id}"))?;
            if !mon.tms.contains(&ix) {
                return Err(format!("{} cannot learn TM {id}", mon.name));
            }
            if !mon.pool.contains(&ix) {
                mon.pool.push(ix);
            }
        }
        if ability == Some("imposter")
            || ability.is_none()
                && mon.abilities.first().and_then(|s| s.as_deref()) == Some("imposter")
        {
            let atk = mon.atk.max(1.12);
            mon.pa = atk;
            mon.sa = atk;
            mon.atk = atk;
            mon.df = mon.df.max(72.);
            mon.sd = mon.sd.max(72.);
        }
        Ok(mon)
    }
}
