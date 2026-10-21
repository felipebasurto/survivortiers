//! Imports declarative literals from the pinned upstream source. Never evaluates JavaScript.
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{collections::BTreeSet, fs, path::Path, process::Command};
const PIN: &str = "ce5785313b0205af8b9477423f64b0a7b7039dcd";
fn literal(src: &str, marker: &str) -> Value {
    let tail = src
        .split_once(marker)
        .unwrap_or_else(|| panic!("missing literal {marker}"))
        .1;
    let start = tail.find(['[', '{']).expect("literal start");
    let bytes = tail.as_bytes();
    let mut stack = Vec::new();
    let mut quote = 0;
    let mut escape = false;
    let mut comment = 0;
    let mut i = start;
    while i < bytes.len() {
        let b = bytes[i];
        let next = bytes.get(i + 1).copied().unwrap_or(0);
        if comment == 1 {
            if b == b'\n' {
                comment = 0;
            }
        } else if comment == 2 {
            if b == b'*' && next == b'/' {
                comment = 0;
                i += 1;
            }
        } else if quote != 0 {
            if escape {
                escape = false;
            } else if b == b'\\' {
                escape = true;
            } else if b == quote {
                quote = 0;
            }
        } else if b == b'/' && next == b'/' {
            comment = 1;
            i += 1;
        } else if b == b'/' && next == b'*' {
            comment = 2;
            i += 1;
        } else if b == b'\'' || b == b'"' {
            quote = b;
        } else if b == b'[' || b == b'{' {
            stack.push(b);
        } else if b == b']' || b == b'}' {
            let open = stack.pop().expect("balanced literal");
            assert!((open == b'[' && b == b']') || (open == b'{' && b == b'}'));
            if stack.is_empty() {
                return json5::from_str(
                    &regex::Regex::new(r"([,{]\s*)([0-9]+)\s*:")
                        .unwrap()
                        .replace_all(&tail[start..=i], "$1\"$2\":"),
                )
                .unwrap_or_else(|e| panic!("{marker}: {e}"));
            }
        }
        i += 1;
    }
    panic!("unclosed literal {marker}")
}
fn mods(v: &mut Value, m: &Value) {
    const MULT: &[&str] = &[
        "dmg", "cd", "speed", "radius", "dur", "amount", "arc", "width", "spread", "life", "size",
        "rate", "pull", "knock", "stun", "charge",
    ];
    for (k, x) in m.as_object().unwrap() {
        let n = x.as_f64().unwrap();
        v[k] = if MULT.contains(&k.as_str()) && v[k].is_number() {
            json!(v[k].as_f64().unwrap() * n)
        } else if ["count", "pierce", "stacks", "bounce"].contains(&k.as_str()) {
            json!(v[k].as_f64().unwrap_or(0.) + n)
        } else {
            x.clone()
        };
    }
}
fn hash(x: u32, y: u32, seed: u32) -> f64 {
    // core/util.js hash: keep unsigned shifts and wrapping multiplication.
    let mut h =
        x.wrapping_mul(374761393) ^ y.wrapping_mul(668265263) ^ seed.wrapping_mul(2246822519);
    h = (h ^ (h >> 13)).wrapping_mul(1274126177);
    ((h ^ (h >> 16)) as f64) / 4294967296.
}
fn behavior(p: &Value, meta: &Value) -> &'static str {
    let d = p["dex"].as_u64().unwrap();
    let t = p["types"].as_array().unwrap();
    let has = |xs: &[&str]| xs.iter().any(|x| t.iter().any(|t| t == x));
    if [
        35, 36, 113, 173, 183, 184, 242, 301, 440, 531, 594, 700, 764, 858,
    ]
    .contains(&d)
    {
        return "healer";
    }
    if [
        95, 122, 208, 213, 227, 306, 375, 410, 411, 436, 437, 439, 476, 703,
    ]
    .contains(&d)
    {
        return "shielder";
    }
    if [74, 75, 76, 100, 101, 102, 109, 110, 337, 338, 343, 344].contains(&d) {
        return "bomber";
    }
    let summoners = [
        (15, 13),
        (18, 16),
        (24, 23),
        (28, 27),
        (31, 29),
        (34, 32),
        (42, 41),
        (51, 50),
        (53, 52),
        (57, 56),
        (59, 58),
        (62, 60),
        (68, 66),
        (73, 72),
        (78, 77),
        (82, 81),
        (85, 84),
        (91, 90),
        (117, 116),
        (130, 129),
        (168, 167),
        (169, 41),
        (199, 79),
        (230, 116),
        (262, 261),
        (334, 333),
        (405, 403),
        (416, 415),
        (462, 81),
        (466, 239),
        (553, 551),
        (637, 636),
    ];
    if summoners
        .iter()
        .any(|(a, b)| *a == d && !meta[b.to_string()].is_null())
    {
        return "summoner";
    }
    let h = hash(d as u32, 7, 11);
    if has(&["bug"]) && (0.6..0.78).contains(&h) {
        return "summoner";
    }
    if has(&["electric", "psychic", "dragon", "ice"]) && h < 0.18 {
        return "beamer";
    }
    if has(&["fire", "ground", "poison"]) && h < 0.18 {
        return "zoner";
    }
    if has(&["water", "grass", "bug", "fairy"]) && (0.18..0.32).contains(&h) {
        return "fan";
    }
    if has(&["fighting", "ground", "normal", "rock"]) && (0.42..0.56).contains(&h) {
        return "jumper";
    }
    if has(&["psychic", "electric", "ghost", "fairy"]) && h < 0.4
        || has(&["fire", "water", "poison", "ice"]) && h < 0.22
    {
        return "ranged";
    }
    if has(&[
        "fighting", "normal", "ground", "rock", "dragon", "steel", "dark",
    ]) && h < 0.4
    {
        return "charger";
    }
    if (p["hp"].as_f64().unwrap() - 70.) / 0.45 > 95.
        && (p["spd"].as_f64().unwrap() - 78.) / 0.42 < 50.
    {
        return "tank";
    }
    "chase"
}
fn main() {
    let args: Vec<String> = std::env::args().collect();
    assert_eq!(args.len(), 3, "import-game UPSTREAM_CHECKOUT OUTPUT_JSON");
    let repo = Path::new(&args[1]);
    let git = |a: &[&str]| {
        String::from_utf8(
            Command::new("git")
                .arg("-C")
                .arg(repo)
                .args(a)
                .output()
                .expect("git")
                .stdout,
        )
        .unwrap()
        .trim()
        .to_string()
    };
    assert_eq!(git(&["rev-parse", "HEAD"]), PIN, "checkout must be pinned");
    assert!(
        git(&["status", "--porcelain", "--untracked-files=no"]).is_empty(),
        "dirty upstream checkout"
    );
    let mut hashes = serde_json::Map::new();
    let mut read = |f: &str| {
        let bytes = fs::read(repo.join("js").join(f)).unwrap();
        hashes.insert(f.into(), json!(format!("{:x}", Sha256::digest(&bytes))));
        String::from_utf8(bytes).unwrap()
    };
    let moves_src = read("data/moves.js");
    let dex_src = read("data/pokedex.js");
    let meta = literal(&read("data/sprites-meta.js"), "G.SPRITE_META =");
    let starters = literal(&read("data/starters.js"), "G.STARTERS =");
    let natures = literal(&read("data/natures.js"), "G.NATURES =");
    let abilities = literal(&read("data/abilities.js"), "G.ABIL =");
    let slots = literal(&read("data/abilities.js"), "G.DEX_ABIL =");
    let tm_src = read("data/tms.js");
    let tms = literal(&tm_src, "G.TM_MOVES =");
    let prices = literal(&tm_src, "G.TM_PRICE =");
    let enemies = read("data/enemies.js");
    let tiers = literal(&enemies, "const TIERS =");
    let bosses = literal(&enemies, "const BOSS_SLOTS =");
    let chart = literal(&read("data/types.js"), "const CHART =");
    let upgrades = literal(&read("data/upgrades.js"), "const LIST =");
    for f in [
        "data/ability-fx.js",
        "systems/combat.js",
        "entities/player.js",
        "entities/enemy.js",
        "systems/levelup.js",
        "systems/spawner.js",
        "core/util.js",
        "systems/mons.js",
    ] {
        read(f);
    }
    let ladders = literal(&moves_src, "const LADDERS =");
    let raw = literal(&moves_src, "const RAW =");
    let phys = literal(&moves_src, "const PHYSICAL = new Set(");
    let evo = literal(&moves_src, "const EVO =");
    let evo_mods = literal(&moves_src, "const EVO_MODS =");
    let starts = literal(&moves_src, "const START =");
    let mut moves = serde_json::Map::new();
    let mut pool = serde_json::Map::<String, Value>::new();
    for mut m in raw.as_array().unwrap().clone() {
        let id = m["id"].as_str().unwrap().to_string();
        let k = m["kind"].as_str().unwrap().to_string();
        let ty = m["type"].as_str().unwrap().to_string();
        if k == "melee" {
            m["dmg"] = json!((m["dmg"].as_f64().unwrap() * 1.2).round());
            m["radius"] = json!((m["radius"].as_f64().unwrap() * 1.25).round());
            if let Some(a) = m["arc"].as_f64() {
                m["arc"] = json!(((a * 1.25 * 100.).round() / 100.).min(3.));
            }
        }
        if ["projectile", "homing", "bounce"].contains(&k.as_str()) {
            if m["count"].is_null() {
                m["count"] = json!(1)
            }
            if m["spread"].is_null() {
                m["spread"] = json!(0.12)
            }
        }
        m["baseDmg"] = m["dmg"].clone();
        m["cat"] = if k == "buff" {
            Value::Null
        } else {
            json!(if phys.as_array().unwrap().contains(&json!(&id)) {
                "physical"
            } else {
                "special"
            })
        };
        let ups = ladders[&k].as_array().expect("known move ladder");
        let max = ups.len() + 1;
        m["maxLvl"] = json!(max);
        let mut levels = vec![m.clone()];
        for u in ups {
            mods(&mut m, &u["m"]);
            levels.push(m.clone());
        }
        let evolved = if evo[&id].is_array() {
            mods(&mut m, &evo_mods[&k]["m"]);
            m["name"] = evo[&id][0].clone();
            m["evolved"] = json!(true);
            m.clone()
        } else {
            Value::Null
        };
        pool.entry(ty)
            .or_insert(json!([]))
            .as_array_mut()
            .unwrap()
            .push(json!(&id));
        moves.insert(id.clone(),json!({"id":id,"name":levels[0]["name"],"kind":k,"type":levels[0]["type"],"maxLvl":max,"levels":levels,"evo":evolved,"needs":evo[&id][1]}));
    }
    let mut dex = literal(&dex_src, "G.DEX =");
    for p in dex.as_array_mut().unwrap() {
        let d = p["dex"].as_u64().unwrap().to_string();
        let md = &meta[&d];
        let width = md["a"]["Idle"]["w"].as_f64().unwrap_or(32.);
        p["r"] = json!((width * 0.22).clamp(5., 26.) * 2.);
        p["fly"] = json!(md["hv"].as_i64() == Some(1));
        let mut ids = pool["normal"].as_array().unwrap().clone();
        for t in p["types"].as_array().unwrap() {
            for x in pool[t.as_str().unwrap()].as_array().unwrap() {
                if !ids.contains(x) {
                    ids.push(x.clone())
                }
            }
        }
        p["pool"] = json!(ids);
        p["start"] = starters
            .as_array()
            .unwrap()
            .iter()
            .find(|s| s["dex"] == p["dex"])
            .map(|s| s["start"].clone())
            .unwrap_or_else(|| starts[p["types"][0].as_str().unwrap()].clone());
        p["abilities"] = slots[&d].clone();
        p["tms"] = json!(tms
            .as_object()
            .unwrap()
            .iter()
            .filter(|(_, ds)| ds.as_array().unwrap().contains(&p["dex"]))
            .map(|(id, _)| id)
            .collect::<Vec<_>>());
    }
    let combos: BTreeSet<String> = dex
        .as_array()
        .unwrap()
        .iter()
        .map(|p| {
            p["types"]
                .as_array()
                .unwrap()
                .iter()
                .map(|x| x.as_str().unwrap())
                .collect::<Vec<_>>()
                .join("/")
        })
        .collect();
    let mut tmult = serde_json::Map::new();
    for (a, row) in chart.as_object().unwrap() {
        let mut out = serde_json::Map::new();
        for combo in &combos {
            let k = combo
                .split('/')
                .map(|t| match row[t].as_f64() {
                    Some(2.) => 1.6,
                    Some(0.5) => 0.6,
                    Some(0.) => 0.3,
                    _ => 1.,
                })
                .product::<f64>()
                .clamp(0.3, 2.4);
            out.insert(combo.clone(), json!(k));
        }
        tmult.insert(a.clone(), json!(out));
    }
    let tiers:Vec<Value>=tiers.as_array().unwrap().iter().enumerate().map(|(ti,t)|{let cands:Vec<Value>=dex.as_array().unwrap().iter().filter(|p|p["rarity"].as_u64().unwrap()<5 && p["bst"].as_f64().unwrap()>=t["bst"][0].as_f64().unwrap()&&p["bst"].as_f64().unwrap()<=t["bst"][1].as_f64().unwrap()&&!meta[p["dex"].to_string()].is_null()).map(|p|{
        let beh=behavior(p,&meta);let tank=beh=="tank";let basehp=(p["hp"].as_f64().unwrap()-70.)/0.45;let basespd=(p["spd"].as_f64().unwrap()-78.)/0.42;
        let mut def=json!({"behavior":beh,"hp":(t["hp"].as_f64().unwrap()*(basehp/65.).clamp(0.7,1.6)*if tank{1.5}else{1.}).round(),"spd":(t["spd"].as_f64().unwrap()*(0.75+basespd/260.).clamp(0.75,1.3)*if tank{0.7}else{1.}).round(),"dmg":(t["dmg"].as_f64().unwrap()*if tank{1.2}else{1.}).round(),"xp":(t["xp"].as_f64().unwrap()*if tank{1.3}else{1.}).round().max(3.)});
        let cd=match beh{"ranged"=>2.2-ti as f64*0.15,"fan"=>3.2-ti as f64*0.15,"beamer"=>4.4-ti as f64*0.2,"zoner"=>4.6-ti as f64*0.2,"healer"=>3.5,"summoner"=>7.,_=>0.};if cd>0.{def["shotDmg"]=json!((t["dmg"].as_f64().unwrap()*if beh=="fan"{0.7}else{0.8}).round());def["shotCd"]=json!((cd*100.).round()/100.);def["range"]=json!(match beh{"beamer"=>260,"healer"|"summoner"=>230,_=>190}+ti*6);}
        if beh=="fan"{def["fanN"]=json!(if ti<2{3}else{5})}if beh=="zoner"{def["zones"]=json!(if ti<2{1}else if ti<4{2}else{3})}if beh=="bomber"{def["spd"]=json!((def["spd"].as_f64().unwrap()*1.25).round());def["hp"]=json!((def["hp"].as_f64().unwrap()*0.8).round());}
        let mut c=p.clone();c["beh"]=json!(beh);c["def"]=def;c
    }).collect();let mut out=t.clone();out["cands"]=json!(cands);out}).collect();
    assert_eq!(dex.as_array().unwrap().len(), 966);
    assert_eq!(moves.len(), 103);
    assert_eq!(natures.as_array().unwrap().len(), 25);
    assert_eq!(tms.as_object().unwrap().len(), 58);
    let output = json!({"schema":4,"gameCommit":PIN,"sourceHashes":hashes,"moves":moves,"pool":pool,"dex":dex,"tiers":tiers,"bosses":bosses,"tmult":tmult,"chart":chart,"natures":natures,"abilities":abilities,"tmPrices":prices,"upgrades":upgrades});
    fs::write(&args[2], serde_json::to_vec(&output).unwrap()).expect("write game JSON");
    println!("Imported 966 species, 103 moves, 25 natures and 58 TMs @ {PIN}");
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn parses_literals_without_evaluating_source() {
        assert_eq!(
            literal(
                "const X = [{id:'x',n:.5}, // ]\n {id:'y'}]; bad()",
                "const X ="
            ),
            json!([{"id":"x","n":0.5},{"id":"y"}])
        );
    }
    #[test]
    fn additive_and_multiplicative_upgrades() {
        let mut x = json!({"dmg":10,"count":1,"spread":0.12});
        mods(&mut x, &json!({"dmg":1.5,"count":1,"spread":1.3}));
        assert_eq!(x, json!({"dmg":15.,"count":2.,"spread":0.156}));
    }
}
