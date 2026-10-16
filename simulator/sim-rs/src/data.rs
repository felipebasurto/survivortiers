//! Loads v3/v3_data.json into flat structs. Missing numeric fields become NaN,
//! which is how `undefined` behaves in the JS arithmetic it replaces.

use serde_json::Value;
use std::collections::HashMap;

pub const TYPES: [&str; 18] = [
    "normal", "fire", "water", "electric", "grass", "ice", "fighting", "poison", "ground",
    "flying", "psychic", "bug", "rock", "ghost", "dragon", "dark", "steel", "fairy",
];
pub const T_FIRE: u8 = 1;
pub const T_WATER: u8 = 2;
pub const T_ICE: u8 = 5;
pub const T_GROUND: u8 = 8;
pub const T_ROCK: u8 = 12;
pub const T_STEEL: u8 = 16;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Kind {
    Melee,
    Beam,
    Orbit,
    Nova,
    Projectile,
    Boomerang,
    /// buff, dash, cone, aura, chain, trail, mine, meteor, turret: never fired.
    Inert,
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
            _ => Kind::Inert,
        }
    }

    pub fn simulated(self) -> bool {
        self != Kind::Inert
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

pub const STATS: [Stat; 7] = [Stat::Pow, Stat::Run, Stat::Hp, Stat::Cor, Stat::Cd, Stat::Rgn, Stat::Mag];
pub const CAPS: [u32; 7] = [40, 8, 99, 12, 10, 10, 6];

#[derive(Clone, Debug)]
pub struct MoveLvl {
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
            Beh::Ranged | Beh::Fan | Beh::Beamer | Beh::Zoner | Beh::Healer | Beh::Summoner | Beh::Shielder
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
    pub start: usize,
    pub pool: Vec<usize>,
}

pub struct Data {
    pub moves: Vec<Move>,
    pub move_ix: HashMap<String, usize>,
    pub dex: Vec<Mon>,
    pub tiers: Vec<Tier>,
    /// tmult[attack type][defender combo]
    pub tmult: Vec<Vec<f64>>,
    pub swords_dance: usize,
    pub harden: usize,
}

fn num(v: &Value, k: &str) -> f64 {
    v.get(k).and_then(Value::as_f64).unwrap_or(f64::NAN)
}

fn type_ix(s: &str) -> u8 {
    TYPES.iter().position(|t| *t == s).unwrap_or_else(|| panic!("unknown type {s}")) as u8
}

fn move_lvl(v: &Value) -> MoveLvl {
    MoveLvl {
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
        status: ["burn", "poison", "slow"].iter().any(|k| v.get(*k).is_some_and(|x| !x.is_null())),
        burn: num(v, "burn"),
        poison: num(v, "poison"),
        slow: num(v, "slow"),
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
        let raw: Value = serde_json::from_str(&std::fs::read_to_string(path).expect("read v3_data.json"))
            .expect("parse v3_data.json");

        let tm = raw["tmult"].as_object().unwrap();
        let combo_names: Vec<String> = tm["normal"].as_object().unwrap().keys().cloned().collect();
        let combo_ix: HashMap<String, u16> =
            combo_names.iter().enumerate().map(|(i, c)| (c.clone(), i as u16)).collect();
        let tmult: Vec<Vec<f64>> = TYPES
            .iter()
            .map(|t| {
                let row = tm[*t].as_object().unwrap();
                combo_names.iter().map(|c| row[c].as_f64().unwrap()).collect()
            })
            .collect();
        let combo_of = |types: &Value| -> u16 {
            let key: Vec<&str> = types.as_array().unwrap().iter().map(|t| t.as_str().unwrap()).collect();
            let key = key.join("/");
            *combo_ix.get(&key).unwrap_or_else(|| panic!("missing type combo {key}"))
        };

        let mut moves = Vec::new();
        let mut move_ix = HashMap::new();
        let mut ids: Vec<&String> = raw["moves"].as_object().unwrap().keys().collect();
        ids.sort();
        for id in ids {
            let m = &raw["moves"][id];
            let levels: Vec<MoveLvl> = m["levels"].as_array().unwrap().iter().map(move_lvl).collect();
            let evo = if m["evo"].is_null() { None } else { Some(move_lvl(&m["evo"])) };
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
                types: p["types"].as_array().unwrap().iter().map(|t| type_ix(t.as_str().unwrap())).collect(),
                combo: combo_of(&p["types"]),
                hp: num(p, "hp"),
                spd: num(p, "spd"),
                atk: num(p, "atk"),
                r: num(p, "r"),
                start: move_ix[p["start"].as_str().unwrap()],
                pool: p["pool"].as_array().unwrap().iter().map(|x| move_ix[x.as_str().unwrap()]).collect(),
            })
            .collect();

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
                            water: c["types"].as_array().unwrap().iter().any(|t| t == "water"),
                            fire: c["types"].as_array().unwrap().iter().any(|t| t == "fire"),
                        }
                    })
                    .collect(),
            })
            .collect();

        let swords_dance = move_ix["swords-dance"];
        let harden = move_ix["harden"];
        Data { moves, move_ix, dex, tiers, tmult, swords_dance, harden }
    }
}
