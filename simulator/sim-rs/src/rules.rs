//! The owner's build rules, read from `data/owner_rules.json`.
//!
//! The publisher (`build/owner_rules.py`) reads the same file. This module is the engine
//! side: which moves count as attacks, which buff goes with which category, the melee
//! penalty and Gengar's melee ban. Nothing here is a game number; the game's own numbers
//! live in `v3_data.json` (extracted from `moves.js`, `player.js`, ...).

use crate::data::{Kind, Mon, Move};
use std::sync::OnceLock;

pub struct OwnerRules {
    pub gengar_dex: u32,
    pub physical_buff: String,
    pub special_buff: String,
    /// Moves that are never an attack, whatever damage their entity deals (Sustituto).
    pub never_attack: Vec<String>,
    /// Multiplier on the score of any run that bonds a melee attack. The sim overrates melee.
    pub melee_score_factor: f64,
}

pub fn rules() -> &'static OwnerRules {
    static RULES: OnceLock<OwnerRules> = OnceLock::new();
    RULES.get_or_init(|| {
        let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../data/owner_rules.json");
        let text = std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("read {}: {e}", path.display()));
        parse(&text)
    })
}

fn parse(text: &str) -> OwnerRules {
    let v: serde_json::Value = serde_json::from_str(text).expect("owner_rules.json");
    OwnerRules {
        gengar_dex: v["gengar_dex"].as_u64().expect("gengar_dex") as u32,
        physical_buff: v["physical_buff"].as_str().expect("physical_buff").to_string(),
        special_buff: v["special_buff"].as_str().expect("special_buff").to_string(),
        never_attack: v["never_attack"]
            .as_array()
            .expect("never_attack")
            .iter()
            .map(|x| x.as_str().expect("never_attack id").to_string())
            .collect(),
        melee_score_factor: v["melee_score_factor"].as_f64().expect("melee_score_factor"),
    }
}

/// An attacking move: it deals damage, it is not a buff and the owner does not exclude it.
/// Turret, orbit and melee qualify when they deal damage. Sustituto never does.
pub fn publishable_attack(m: &Move) -> bool {
    if m.kind_name == "buff" || rules().never_attack.iter().any(|id| *id == m.id) {
        return false;
    }
    let l = &m.levels[0];
    let dmg = if l.dmg.is_finite() { l.dmg } else { 0.0 };
    dmg > 0.0 && l.buff == 0
}

/// `publishable_attack`, and not a melee move on Gengar.
pub fn usable_attack(mon: &Mon, m: &Move) -> bool {
    publishable_attack(m) && !(mon.dex == rules().gengar_dex && m.kind == Kind::Melee)
}

/// Score as the publisher ranks it: a bonded melee attack takes the owner's penalty.
pub fn adjusted_score(score: f64, has_melee: bool) -> f64 {
    if has_melee {
        score * rules().melee_score_factor
    } else {
        score
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn owner_file_parses() {
        let r = rules();
        assert_eq!(r.gengar_dex, 94);
        assert_eq!(r.physical_buff, "swords-dance");
        assert_eq!(r.special_buff, "nasty-plot");
        assert!(r.never_attack.iter().any(|id| id == "substitute"));
        assert!(r.melee_score_factor > 0.0 && r.melee_score_factor < 1.0);
    }

    #[test]
    fn melee_takes_the_penalty() {
        let f = rules().melee_score_factor;
        assert_eq!(adjusted_score(100.0, false), 100.0);
        assert!((adjusted_score(100.0, true) - 100.0 * f).abs() < 1e-12);
    }
}
