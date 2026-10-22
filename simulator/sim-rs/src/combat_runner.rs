//! Build and execute an assembled combat configuration, independent of search and reporting.
use crate::{
    data::{Data, Mon},
    engine::{run_match, Bot, Ext, Opts, Tables},
    math::Libm,
    selection::Configuration,
};
use serde_json::{json, Value};

fn build_opts(
    data: &Data,
    config: &Configuration,
    seed: u32,
    seconds: f64,
) -> Result<(Mon, usize, Opts), String> {
    let base = data
        .dex
        .iter()
        .find(|m| m.dex == config.dex)
        .ok_or("unknown configuration dex")?;
    let mon = data.configure(base, &config.nature, config.ability.as_deref(), &config.tms)?;
    let ids = config
        .moves
        .iter()
        .map(|id| {
            data.move_ix
                .get(id)
                .copied()
                .ok_or_else(|| format!("unknown move {id}"))
        })
        .collect::<Result<Vec<_>, _>>()?;
    if ids.is_empty() || !mon.start_choices(&data.moves).contains(&ids[0]) {
        return Err("configuration lead became illegal".into());
    }
    let buff_ids = ids
        .iter()
        .copied()
        .filter(|&i| data.moves[i].kind_name == "buff")
        .collect::<Vec<_>>();
    let second = config
        .second
        .as_ref()
        .map(|s| {
            data.move_ix
                .get(s)
                .copied()
                .ok_or_else(|| format!("unknown second start {s}"))
        })
        .transpose()?;
    let companions = ids
        .iter()
        .copied()
        .filter(|&i| data.moves[i].is_attack() && i != ids[0] && Some(i) != second)
        .collect::<Vec<_>>();
    let mut ext = Ext::with_planned_buffs(data, buff_ids)?;
    ext.companions = companions;
    ext.initial_second = second;
    ext.bonded = true;
    ext.bosses = true;
    ext.ability = config.ability.clone();
    let opts = Opts {
        seed,
        seconds,
        cards: true,
        bot: Bot::Play,
        terrain: true,
        trace: false,
        ext,
    };
    Ok((mon, ids[0], opts))
}

pub(crate) fn run_configuration(
    data: &Data,
    tables: &Tables,
    config: &Configuration,
    seed: u32,
    seconds: f64,
) -> Result<Value, String> {
    let (mon, start, opts) = build_opts(data, config, seed, seconds)?;
    let r = run_match(&Libm, data, tables, &mon, start, &opts);
    Ok(
        json!({"seed":seed,"metrics":{"damage":r.dealt,"contactDamage":r.risk.damage,"contactSeconds":r.risk.contact_seconds,"trappedSeconds":r.risk.surrounded_seconds,"kills":r.kills,"bosses":r.bosses,"survivalSeconds":r.time}}),
    )
}
