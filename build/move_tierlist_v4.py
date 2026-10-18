"""Tier list de movimientos v4 (estimación propia), modo noregen, con textos.

Sustituye a move_tierlist_v3.py del análisis: usa score_v4 en modo noregen en vez de
`exec` de score_v3, no depende de /tmp y toma los nombres de js/data/moves.js.

Se ejecuta a mano, no en Vercel, porque necesita el análisis (score_v4.py, v3/v3_data.json y
las rejillas v3/grid_*.jsonl). Su resultado, data/move_tierlist_v4.csv, se commitea.

    python3 build/move_tierlist_v4.py --analysis ~/Downloads/pokesurvivor --game /ruta/al/juego
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import re
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _early_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--analysis", type=Path, default=Path.home() / "Downloads" / "pokesurvivor",
                    help="carpeta del análisis (score_v4.py, v3/)")
    ap.add_argument("--game", type=Path, required=False, default=None,
                    help="copia local del repositorio del juego (solo lectura), para js/data/moves.js")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "move_tierlist_v4.csv")
    return ap.parse_known_args()[0]


ARGS = _early_args()
# score_v4 lee MODE de sys.argv[1] y abre v3/ y v4/ con rutas relativas: se prepara antes de importarlo.
os.chdir(ARGS.analysis)
sys.path.insert(0, str(ARGS.analysis))
sys.argv = ["score_v4", "noregen"]
import score_v4 as S  # noqa: E402  (ver comentario de arriba)

CLOSE_KINDS = {"melee", "aura", "dash", "trail", "orbit"}
CAT_CLOSE, CAT_RANGED, CAT_STAT = "cuerpo a cuerpo", "distancia", "estadística"
TIER_SHARE = (("S", 0.15), ("A", 0.40), ("B", 0.70))   # corte acumulado como en move_tierlist_v3

KIND_ES = {
    "melee": "golpe en arco", "aura": "aura continua", "dash": "carga que atraviesa", "trail": "estela de charcos",
    "orbit": "orbes que giran", "projectile": "proyectiles", "nova": "ráfaga radial", "beam": "rayo recto",
    "boomerang": "bumerán", "chain": "cadena de saltos", "mine": "minas", "meteor": "meteoros", "turret": "torreta",
    "cone": "abanico de disparos", "buff": "potenciador",
}
STAT_ES = {"atk": "ataque", "patk": "ataque físico", "satk": "ataque especial", "spd": "velocidad", "def": "defensa",
           "regen": "regeneración", "hp": "vida"}
TYPE_ES = {
    "normal": "Normal", "fire": "Fuego", "water": "Agua", "grass": "Planta", "electric": "Eléctrico", "ice": "Hielo",
    "fighting": "Lucha", "poison": "Veneno", "ground": "Tierra", "flying": "Volador", "psychic": "Psíquico",
    "bug": "Bicho", "rock": "Roca", "ghost": "Fantasma", "dragon": "Dragón", "dark": "Siniestro", "steel": "Acero",
    "fairy": "Hada",
}


def game_names(game_dir: Path) -> dict:
    """Nombres españoles de js/data/moves.js: id -> nombre; y EVO: id -> (nombre evolucionado, carta)."""
    text = (game_dir / "js" / "data" / "moves.js").read_text(encoding="utf8")
    names = dict(re.findall(r"\{ id: '([^']+)', name: '([^']+)'", text))
    need = dict(re.findall(r"(\w+): '([^']+)'", text[text.index("const NEED_NAME"):text.index("const EVO")]))
    evo = {mid: (nm, nd) for mid, nm, nd in re.findall(r"'([^']+)': \['([^']+)', '(\w+)'\]", text)}
    return {"names": names, "need": need, "evo": evo}


def build_rows(names: dict) -> tuple[list, list]:
    missing = [m for m in S.MOVES if m not in names["names"]]
    if missing:
        raise SystemExit(f"movimientos sin nombre en moves.js: {missing}")
    GB = S.load_grid("base", "baseR170")
    GB["ranged_grid"] = S.load_grid("ranged")
    LV = S.level_curve(GB)
    P = S.BASEP
    ref = dict(dex=0, name="ref", types=["normal"], hp=st.median(p["hp"] for p in S.DEX),
               spd=st.median(p["spd"] for p in S.DEX), atk=st.median(p["atk"] for p in S.DEX), r=14.1,
               start="tackle", pool=list(S.MOVES))
    rows = []
    for mid in S.ATTACK:
        ev = [S.evaluate(ref, (mid,), ("swords-dance", "harden"), t, LV[t], GB, P) for t in S.CHECK]
        kind = S.MOVES[mid]["kind"]
        rows.append(dict(id=mid, kind=kind, type=S.MOVES[mid]["type"], ev=ev,
                         cat=CAT_CLOSE if kind in CLOSE_KINDS else CAT_RANGED))
    for ti in range(3):
        for key in ("dps", "ttd"):
            m_ = st.median(r["ev"][ti][key] for r in rows)
            for r in rows:
                r.setdefault("rel", {})[(ti, key)] = r["ev"][ti][key] / m_
    for r in rows:
        r["score"] = math.exp(sum(w * (P["wK"] * math.log(r["rel"][(i, "dps")]) + P["wS"] * math.log(r["rel"][(i, "ttd")]))
                                  for i, w in enumerate(P["wt"])))
    best_single = max(rows, key=lambda r: r["score"])["id"]
    top3 = [r["id"] for r in sorted(rows, key=lambda r: -r["score"])[:3]]
    buffrows = []
    for b in S.BUFFS:
        gains = []
        for t in S.CHECK:
            n = S.group_size(t, P)
            base_e = S.evaluate(ref, tuple(top3[:n - 1] or top3[:1]), (), t, LV[t], GB, P)
            with_e = S.evaluate(ref, tuple(top3[:max(1, n - 1)]) + (b,), (), t, LV[t], GB, P)
            weave_e = S.evaluate(ref, (best_single,), (b,), t, LV[t], GB, P)
            b0 = S.evaluate(ref, (best_single,), (), t, LV[t], GB, P)
            gains.append((math.exp(S.objective(with_e, P) - S.objective(base_e, P)),
                          math.exp(S.objective(weave_e, P) - S.objective(b0, P))))
        s5 = S.inst(b, 5, False)
        buffrows.append(dict(id=b, kind="buff", type=S.MOVES[b]["type"], cat=CAT_STAT, gains=gains,
                             score=math.exp(sum(w * math.log(g[0]) for w, g in zip(P["wt"], gains))),
                             stat=s5["stat"], total=s5["amount"] * s5["stacks"], dur=s5["dur"], cd=s5["cd"]))
    return rows, buffrows


def assign_tiers(lst: list) -> list:
    lst = sorted(lst, key=lambda r: -r["score"])
    n = len(lst)
    for i, r in enumerate(lst):
        r["tier"] = ("S" if i < max(1, round(0.15 * n)) else "A" if i < round(0.40 * n)
                     else "B" if i < round(0.70 * n) else "C")
    return lst


def _fx(x: float, d: int = 1) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def _rel(x: float) -> str:
    return "menos de 0,05" if x < 0.05 else _fx(x)


def attack_blurb(r: dict, med: dict, evo: tuple | None, need_name: dict) -> str:
    e5, e15 = r["ev"][0], r["ev"][2]
    dps_rel = e15["dps"] / med["dps15"]
    ttd_rel = e15["ttd"] / med["ttd15"]
    dps_txt = ("daño muy superior" if dps_rel >= 1.6 else "daño superior" if dps_rel >= 1.15 else
               "daño en la media" if dps_rel >= 0.85 else "daño inferior" if dps_rel >= 0.55 else "daño muy inferior")
    ttd_txt = ("te mantiene vivo mucho más" if ttd_rel >= 1.5 else "te mantiene vivo más" if ttd_rel >= 1.15 else
               "aguante en la media" if ttd_rel >= 0.85 else "te expone más" if ttd_rel >= 0.55 else "te expone mucho")
    kind = KIND_ES[r["kind"]]
    if r["cat"] == CAT_CLOSE:
        why = "Obliga a pelear dentro del enjambre, por eso el aguante pesa tanto."
    else:
        why = "Golpea desde lejos, así que el daño recibido depende menos del movimiento."
    early = (f"Ya funciona pronto (min 5: {_fx(e5['dps'] / med['dps5'])}× la mediana)." if e5["dps"] / med["dps5"] >= 1.3
             else "Rinde sobre todo cuando subes de nivel." if e5["dps"] / med["dps5"] < 0.7 else "")
    evo_txt = (f" Evoluciona a {evo[0]} con la carta {need_name[evo[1]]}." if evo else "")
    return (f"{TYPE_ES[r['type']]}, {kind}: {dps_txt} ({_rel(dps_rel)}× la mediana al minuto 15) y {ttd_txt} "
            f"({_rel(ttd_rel)}×). {why} {early}{evo_txt}").replace("  ", " ").strip()


def buff_blurb(r: dict) -> str:
    g = r["gains"]
    stat = STAT_ES.get(r["stat"], r["stat"])
    total = r["total"]
    amount = f"hasta +{_fx(total * 100, 0)} % de {stat}" if r["stat"] in ("atk", "patk", "satk", "spd", "def") else f"hasta +{_fx(total, 1)} de {stat}"
    uptime = min(1.0, r["dur"] / r["cd"]) if r["cd"] else 1.0
    return (f"{TYPE_ES[r['type']]}, potenciador: {amount} con todas las acumulaciones a nivel máximo, dura {_fx(r['dur'], 0)} s con recarga de "
            f"{_fx(r['cd'], 2)} s (cobertura {_fx(uptime * 100, 0)} %). Fusionado con tus ataques multiplica su valor "
            f"×{_fx(g[0][0], 2)} / ×{_fx(g[1][0], 2)} / ×{_fx(g[2][0], 2)} a los minutos 5 / 10 / 15; "
            f"alternándolo en otro hueco, ×{_fx(g[2][1], 2)} al minuto 15.")


def main() -> None:
    names = game_names(ARGS.game) if ARGS.game else None
    if names is None:
        raise SystemExit("falta --game (ruta al repositorio del juego, solo lectura)")
    rows, buffrows = build_rows(names)
    med = dict(dps5=st.median(r["ev"][0]["dps"] for r in rows), dps15=st.median(r["ev"][2]["dps"] for r in rows),
               ttd15=st.median(r["ev"][2]["ttd"] for r in rows))
    melee = assign_tiers([r for r in rows if r["cat"] == CAT_CLOSE])
    ranged = assign_tiers([r for r in rows if r["cat"] == CAT_RANGED])
    stat = assign_tiers(buffrows)
    ARGS.out.parent.mkdir(parents=True, exist_ok=True)
    with ARGS.out.open("w", newline="", encoding="utf8") as f:
        w = csv.writer(f)
        w.writerow(["category", "tier", "rank", "move_id", "name", "type", "kind", "score_rel",
                    "dps_m5", "dps_m15", "ttd_s_m5", "ttd_s_m15", "evolves_to", "needs_card", "blurb"])
        for lst in (melee, ranged, stat):
            for i, r in enumerate(lst, 1):
                evo = names["evo"].get(r["id"])
                if r["kind"] == "buff":
                    w.writerow([r["cat"], r["tier"], i, r["id"], names["names"][r["id"]], r["type"], "buff",
                                round(r["score"], 3), "", "", "", "", "", "", buff_blurb(r)])
                else:
                    e5, e15 = r["ev"][0], r["ev"][2]
                    w.writerow([r["cat"], r["tier"], i, r["id"], names["names"][r["id"]], r["type"], r["kind"],
                                round(r["score"], 3), round(e5["dps"]), round(e15["dps"]), round(e5["ttd"], 1),
                                round(e15["ttd"], 1), evo[0] if evo else "", names["need"][evo[1]] if evo else "",
                                attack_blurb(r, med, evo, names["need"])])
    total = len(melee) + len(ranged) + len(stat)
    print(f"{ARGS.out}: {total} movimientos ({len(melee)} cuerpo a cuerpo, {len(ranged)} distancia, {len(stat)} estadística)")
    for lst in (melee, ranged, stat):
        print([(r["tier"], names["names"][r["id"]]) for r in lst[:6]])


if __name__ == "__main__":
    main()
