//! Ability effects from ability-fx.js @ ce57853. Unknown effects use the official primary-type fallback.
use super::*;
const SPECIFIC: &[&str] = &[
    "overgrow",
    "blaze",
    "torrent",
    "swarm",
    "steelworker",
    "steely-spirit",
    "dragons-maw",
    "transistor",
    "water-bubble",
    "technician",
    "huge-power",
    "hustle",
    "guts",
    "adaptability",
    "protean",
    "sheer-force",
    "serene-grace",
    "tough-claws",
    "reckless",
    "iron-fist",
    "strong-jaw",
    "mega-launcher",
    "sharpness",
    "punk-rock",
    "tinted-lens",
    "scrappy",
    "sand-force",
    "solar-power",
    "sniper",
    "super-luck",
    "compound-eyes",
    "moxie",
    "chilling-neigh",
    "grim-neigh",
    "beast-boost",
    "speed-boost",
    "swift-swim",
    "chlorophyll",
    "sand-rush",
    "slush-rush",
    "run-away",
    "drought",
    "orichalcum-pulse",
    "drizzle",
    "sand-stream",
    "snow-warning",
    "rain-dish",
    "ice-body",
    "dry-skin",
    "levitate",
    "thick-fat",
    "heatproof",
    "water-absorb",
    "storm-drain",
    "volt-absorb",
    "lightning-rod",
    "motor-drive",
    "flash-fire",
    "well-baked-body",
    "sap-sipper",
    "earth-eater",
    "multiscale",
    "shadow-shield",
    "filter",
    "solid-rock",
    "prism-armor",
    "fur-coat",
    "fluffy",
    "ice-scales",
    "shell-armor",
    "battle-armor",
    "intimidate",
    "pressure",
    "sturdy",
    "regenerator",
    "magic-guard",
    "stamina",
    "limber",
    "own-tempo",
    "oblivious",
    "inner-focus",
    "clear-body",
    "white-smoke",
    "full-metal-body",
    "insomnia",
    "vital-spirit",
    "static",
    "flame-body",
    "poison-point",
    "cute-charm",
    "effect-spore",
    "rough-skin",
    "iron-barbs",
    "poison-touch",
    "pickup",
    "honey-gather",
    "truant",
    "slow-start",
    "defeatist",
    "wonder-guard",
    "schooling",
    "zen-mode",
    "stance-change",
    "imposter",
    "keen-eye",
    "frisk",
    "magnet-pull",
    "sticky-hold",
    "illuminate",
    "sand-veil",
    "snow-cloak",
    "gluttony",
    "harvest",
    "unnerve",
    "infiltrator",
    "telepathy",
    "anticipation",
    "forewarn",
    "weak-armor",
    "steadfast",
    "rattled",
    "hydration",
    "overcoat",
    "shed-skin",
    "natural-cure",
    "healer",
    "leaf-guard",
    "mold-breaker",
    "damp",
    "rivalry",
    "synchronize",
    "prankster",
    "early-bird",
    "shield-dust",
    "sweet-veil",
    "unburden",
    "unaware",
    "defiant",
    "competitive",
    "soundproof",
    "big-pecks",
    "water-veil",
    "pickpocket",
    "analytic",
    "klutz",
    "hyper-cutter",
    "contrary",
    "quick-feet",
    "bulletproof",
    "magic-bounce",
    "friend-guard",
    "stench",
    "anger-point",
    "justified",
    "cursed-body",
    "plus",
    "minus",
    "no-guard",
    "aftermath",
    "moody",
    "tangled-feet",
    "skill-link",
    "protosynthesis",
    "pure-power",
    "libero",
];
const PLUS: &[&str] = &[
    "zen-mode",
    "keen-eye",
    "frisk",
    "magnet-pull",
    "sticky-hold",
    "illuminate",
    "sand-veil",
    "snow-cloak",
    "gluttony",
    "harvest",
    "unnerve",
    "infiltrator",
    "telepathy",
    "anticipation",
    "forewarn",
    "weak-armor",
    "steadfast",
    "rattled",
    "hydration",
    "overcoat",
    "shed-skin",
    "natural-cure",
    "healer",
    "leaf-guard",
    "mold-breaker",
    "damp",
    "rivalry",
    "synchronize",
    "prankster",
    "early-bird",
    "shield-dust",
    "sweet-veil",
    "unburden",
    "unaware",
    "defiant",
    "competitive",
    "soundproof",
    "big-pecks",
    "water-veil",
    "pickpocket",
    "analytic",
    "klutz",
    "hyper-cutter",
    "contrary",
    "quick-feet",
    "bulletproof",
    "magic-bounce",
    "friend-guard",
    "stench",
    "justified",
    "aftermath",
    "moody",
    "tangled-feet",
    "skill-link",
    "protosynthesis",
];
#[derive(Clone, Copy, Debug)]
pub(super) struct Ability {
    pub id: &'static str,
}
impl Default for Ability {
    fn default() -> Self {
        Self { id: "none" }
    }
}
impl Ability {
    pub fn of(id: &str) -> Self {
        Self {
            id: SPECIFIC.iter().copied().find(|x| *x == id).unwrap_or(""),
        }
    }
    pub(super) fn generic(self) -> bool {
        self.id.is_empty() || PLUS.contains(&self.id)
    }
    pub(super) fn steady(self) -> bool {
        matches!(
            self.id,
            "limber"
                | "own-tempo"
                | "oblivious"
                | "inner-focus"
                | "clear-body"
                | "white-smoke"
                | "full-metal-body"
                | "insomnia"
                | "vital-spirit"
                | "early-bird"
                | "shield-dust"
                | "sweet-veil"
        )
    }
    pub(super) fn heal_mul(self) -> f64 {
        match self.id {
            "gluttony" => 1.4,
            "harvest" => 1.3,
            _ => 1.,
        }
    }
    pub(super) fn absorb(self) -> Option<u8> {
        Some(match self.id {
            "water-absorb" | "storm-drain" | "dry-skin" => T_WATER,
            "volt-absorb" | "lightning-rod" | "motor-drive" => T_ELECTRIC,
            "flash-fire" | "well-baked-body" => T_FIRE,
            "sap-sipper" => T_GRASS,
            "earth-eater" => T_GROUND,
            _ => return None,
        })
    }
    pub(super) fn summon(self) -> Option<Wx> {
        Some(match self.id {
            "drought" | "orichalcum-pulse" => Wx::Sun,
            "drizzle" => Wx::Rain,
            "sand-stream" => Wx::Sand,
            "snow-warning" => Wx::Snow,
            _ => return None,
        })
    }
    pub(super) fn crit(self) -> f64 {
        match self.id {
            "super-luck" => 0.1,
            "compound-eyes" => 0.06,
            "keen-eye" => 0.05,
            _ => 0.,
        }
    }
    pub(super) fn magnet(self) -> f64 {
        match self.id {
            "frisk" | "magnet-pull" | "sticky-hold" => 1.2,
            "illuminate" => 1.1,
            _ => 1.,
        }
    }
    pub(super) fn regen(self) -> f64 {
        match self.id {
            "regenerator" => 0.006,
            "natural-cure" | "healer" => 0.003,
            _ => 0.,
        }
    }
    pub(super) fn lava_proof(self) -> bool {
        matches!(self.id, "levitate" | "magic-guard" | "water-veil")
    }
    pub(super) fn trap_proof(self) -> bool {
        matches!(self.id, "levitate" | "magic-guard")
    }
}
#[derive(Clone, Copy, Default)]
pub(super) struct AbilityFrame {
    pub(super) ab: Ability,
    types: [u8; 2],
    ntypes: usize,
    hp: f64,
    time: f64,
    kills: u32,
    wx: Option<Wx>,
    item: bool,
    slow: bool,
    angry: bool,
    mood: u8,
    shield: bool,
}
impl AbilityFrame {
    pub(super) fn outgoing(
        self,
        st: Status,
        ty: u8,
        cat: u8,
        e: &Enemy,
        tm: &[Vec<f64>],
        rng: &mut Rng,
    ) -> f64 {
        let own = self.types[..self.ntypes].contains(&ty);
        let phys = cat == 1;
        let spec = cat == 2;
        let dash = st.kind == 5;
        let melee = st.kind == 100;
        let eff = type_mult(tm, ty, e.combo);
        let a = self.ab.id;
        let k = match a {
            "overgrow" if ty == T_GRASS && self.hp < 1. / 3. => 1.35,
            "blaze" if ty == T_FIRE && self.hp < 1. / 3. => 1.35,
            "torrent" if ty == T_WATER && self.hp < 1. / 3. => 1.35,
            "swarm" if ty == T_BUG && self.hp < 1. / 3. => 1.35,
            "steelworker" | "steely-spirit" if ty == T_STEEL => 1.2,
            "dragons-maw" if ty == T_DRAGON => 1.2,
            "transistor" if ty == T_ELECTRIC => 1.2,
            "water-bubble" if ty == T_WATER => 1.4,
            "technician" if st.base_dmg <= 12. => 1.35,
            "huge-power" | "pure-power" if phys => 1.5,
            "hustle" if phys => {
                if rng.next() < 1. / 6. {
                    0.3
                } else {
                    1.25
                }
            }
            "guts" if phys && self.hp < 0.5 => 1.3,
            "adaptability" if own => 1.25,
            "protean" | "libero" => 1.12,
            "sheer-force" if st.has_effect => 1.25,
            "tough-claws" if melee || dash => 1.25,
            "reckless" if dash => 1.25,
            "iron-fist" if st.tags & 1 != 0 => 1.25,
            "strong-jaw" if st.tags & 2 != 0 => 1.3,
            "mega-launcher" if st.tags & 4 != 0 => 1.3,
            "sharpness" if st.tags & 8 != 0 => 1.3,
            "punk-rock" if st.tags & 16 != 0 => 1.3,
            "tinted-lens" if eff < 1. && eff > 0. => 1. / eff,
            "scrappy"
                if (ty == T_NORMAL || ty == T_FIGHTING) && st.ghost_combos.contains(e.combo) =>
            {
                1. / eff.max(0.3)
            }
            "sand-force"
                if self.wx == Some(Wx::Sand) && [T_ROCK, T_GROUND, T_STEEL].contains(&ty) =>
            {
                1.3
            }
            "solar-power" if self.wx == Some(Wx::Sun) && spec => 1.4,
            "moxie" | "chilling-neigh" | "grim-neigh" | "beast-boost" => {
                1. + (self.kills as f64 * 0.005).min(0.15)
            }
            "truant" => 1.35,
            "slow-start" if self.time < 60. => 0.6,
            "defeatist" => {
                if self.hp < 0.5 {
                    0.75
                } else {
                    1.15
                }
            }
            "schooling" if self.hp > 0.25 => 1.5,
            "zen-mode" if self.hp < 0.5 && spec => 1.3,
            "stance-change" if !self.shield => 1.2,
            "mold-breaker" if e.boss => 1.12,
            "rivalry" if st.shared_combos.contains(e.combo) => 1.15,
            "defiant" if self.slow && phys => 1.2,
            "competitive" if self.slow && spec => 1.2,
            "analytic" if e.hp < e.max * 0.5 => 1.15,
            "klutz" if !self.item => 1.12,
            "hyper-cutter" if phys => 1.06,
            "anger-point" if self.angry => 1.25,
            "justified" if st.dark_combos.contains(e.combo) => 1.15,
            "plus" | "minus" if spec => 1.1,
            "no-guard" => 1.15,
            "moody" if self.mood == if spec { 1 } else { 0 } => 1.1,
            "skill-link" if st.count > 2. || st.bounce => 1.25,
            "protosynthesis" if self.wx == Some(Wx::Sun) => 1.2,
            _ => 1.,
        };
        k * if self.ab.generic() && ty == self.types[0] {
            1.08
        } else {
            1.
        }
    }
    pub(super) fn incoming(self, ty: u8, cat: u8, eff: f64) -> f64 {
        match self.ab.id {
            "dry-skin" if ty == T_FIRE => 1.25,
            "levitate" if ty == T_GROUND => 0.3,
            "thick-fat" if ty == T_FIRE || ty == T_ICE => 0.6,
            "heatproof" | "water-bubble" | "water-veil" if ty == T_FIRE => 0.5,
            "multiscale" | "shadow-shield" if self.hp >= 0.95 => 0.5,
            "filter" | "solid-rock" | "prism-armor" if eff > 1. => 0.75,
            "fur-coat" if cat == 1 => 0.6,
            "fluffy" if cat == 1 => 0.7,
            "ice-scales" if cat == 2 => 0.6,
            "shell-armor" | "battle-armor" | "pressure" | "unaware" => 0.92,
            "intimidate" if cat == 1 => 0.88,
            "wonder-guard" => {
                if eff > 1. {
                    1.5
                } else {
                    0.35
                }
            }
            "stance-change" if self.shield => 0.8,
            "unnerve" | "friend-guard" => 0.94,
            "overcoat" if cat == 2 => 0.95,
            "leaf-guard" if self.wx == Some(Wx::Sun) => 0.85,
            "soundproof" if cat == 2 => 0.9,
            "big-pecks" if cat == 1 => 0.92,
            "bulletproof" | "magic-bounce" if cat == 2 => 0.85,
            "no-guard" => 1.1,
            "moody" if self.mood == 3 => 0.9,
            _ => 1.,
        }
    }
    pub(super) fn dodge(self, cat: u8) -> f64 {
        match self.ab.id {
            "sand-veil" if self.wx == Some(Wx::Sand) => 0.15,
            "snow-cloak" if self.wx == Some(Wx::Snow) => 0.15,
            "telepathy" => 0.08,
            "anticipation" | "forewarn" => 0.06,
            "magic-bounce" if cat == 2 => 0.1,
            "tangled-feet" if self.slow => 0.2,
            _ => 0.,
        }
    }
    pub(super) fn speed(self) -> f64 {
        match self.ab.id {
            "speed-boost" => 1. + ((self.time / 10.).floor() * 0.015).min(0.3),
            "swift-swim" if self.wx == Some(Wx::Rain) => 1.5,
            "chlorophyll" if self.wx == Some(Wx::Sun) => 1.5,
            "sand-rush" if self.wx == Some(Wx::Sand) => 1.5,
            "slush-rush" if self.wx == Some(Wx::Snow) => 1.5,
            "run-away" => 1.08,
            "slow-start" if self.time < 60. => 0.8,
            "unburden" if !self.item => 1.15,
            "contrary" if self.slow => 2.4,
            "quick-feet" if self.slow => 2.5,
            "moody" if self.mood == 2 => 1.1,
            _ => 1.,
        }
    }
}
impl<'a, M: MathFns> Match<'a, M> {
    pub(super) fn ability_frame(&self) -> AbilityFrame {
        let mut types = [0; 2];
        for (i, &ty) in self.mon.types.iter().enumerate() {
            types[i] = ty;
        }
        AbilityFrame {
            ab: self.ability,
            types,
            ntypes: self.mon.types.len(),
            hp: self.pl.hp / self.st.max_hp,
            time: self.t,
            kills: self.kills,
            wx: self.weather.map(|w| w.kind),
            item: self.opts.ext.item.equipped(),
            slow: self.pl.slow_t > 0.,
            angry: self.angry,
            mood: self.mood,
            shield: ((self.t / 8.).floor() as u64) % 2 == 1,
        }
    }
    pub(super) fn heal(&mut self, amount: f64) {
        self.pl.hp = (self.pl.hp + amount * self.ability.heal_mul()).min(self.st.max_hp);
    }
    pub(super) fn ability_tick(&mut self) {
        let dt = self.dt;
        let a = self.ability;
        self.angry |= self.pl.hp < self.st.max_hp * 0.5;
        if self.t >= self.mood_at && a.id == "moody" {
            self.mood_at = self.t + 10.;
            self.mood = (self.fx.next() * 4.).floor() as u8;
        }
        if self.t >= self.summon_at {
            self.summon_at = self.t + 180.;
            if self.weather.is_none() {
                if let Some(kind) = a.summon() {
                    self.weather = Some(Weather {
                        kind,
                        elapsed: 0.,
                        dur: 60.,
                    });
                }
            }
        }
        let wx = self.weather.map(|w| w.kind);
        if a.id == "hydration" && wx == Some(Wx::Rain)
            || a.id == "leaf-guard" && wx == Some(Wx::Sun)
        {
            self.pl.slow_t = 0.;
        }
        let k = match a.id {
            "rain-dish" if wx == Some(Wx::Rain) => 0.015,
            "ice-body" if wx == Some(Wx::Snow) => 0.015,
            "dry-skin" if wx == Some(Wx::Rain) => 0.012,
            "hydration" if wx == Some(Wx::Rain) => 0.01,
            _ => 0.,
        };
        // The upstream fractional helper writes HP directly (it does not call Player.heal).
        self.pl.hp = (self.pl.hp + self.st.max_hp * k * dt).min(self.st.max_hp);
        if a.id == "solar-power" && wx == Some(Wx::Sun) && self.pl.hp > self.st.max_hp * 0.1 {
            self.pl.hp -= self.st.max_hp * 0.004 * dt;
        }
        if a.id == "shed-skin" && self.t >= self.shed_at {
            self.shed_at = self.t + 5.;
            self.pl.slow_t = 0.;
            self.pl.hp = (self.pl.hp + self.st.max_hp * 0.02).min(self.st.max_hp);
        }
        self.stamina.retain(|&t| t > self.t);
        self.speed_buffs.retain(|&(t, _)| t > self.t);
        if a.id == "aftermath"
            && !self.boomed
            && self.pl.hp > 0.
            && self.pl.hp < self.st.max_hp * 0.2
        {
            self.boomed = true;
            for e in &mut self.enemies {
                if e.hp > 0. && len(e.x - self.pl.x, e.y - self.pl.y) <= 140. {
                    raw_hurt(
                        e,
                        40. + self.level as f64 * 10.,
                        160.,
                        e.x - self.pl.x,
                        e.y - self.pl.y,
                    );
                }
            }
        }
        self.stat_dirty = true;
    }
    pub(super) fn ability_contact(&mut self, i: usize) {
        if self.pl.hp <= 0. || self.enemies[i].hp <= 0. {
            return;
        }
        let a = self.ability.id;
        let e = &mut self.enemies[i];
        let slow = match a {
            "static" => Some((0.5, 2.5)),
            "cute-charm" => Some((0.4, 2.5)),
            "effect-spore" if self.fx.next() < 0.5 => Some((0.45, 2.5)),
            "cursed-body" if self.fx.next() < 0.3 => Some((0.5, 2.)),
            _ => None,
        };
        if let Some((n, t)) = slow {
            e.slow = e.slow.max(n);
            e.slow_t = e.slow_t.max(t);
        }
        if a == "flame-body" {
            e.burn = (e.burn + 2.).min(8.);
            e.burn_t = 3.;
        }
        if a == "poison-point" || (a == "effect-spore" && slow.is_none()) {
            e.poison = (e.poison + 2.).min(8.);
            e.poison_t = 4.;
        }
        let back = match a {
            "rough-skin" | "iron-barbs" => 10. + self.level as f64 * 3.,
            "synchronize" => 6. + self.level as f64 * 2.,
            _ => 0.,
        };
        if back > 0. {
            raw_hurt(e, back, 0., 0., 0.);
        }
        if a == "stamina" {
            self.stamina.push(self.t + 6.);
            if self.stamina.len() > 5 {
                self.stamina.remove(0);
            }
        }
    }
}
