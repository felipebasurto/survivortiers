"""Render validated simulator JSON as semantic HTML for future page integration."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from build.sim_results import ResultContractError, validate_results


def render_cards(document: dict[str, Any], dex: int) -> str:
    """Return one species section containing controls, outcome cards, and unavailable notes."""
    validate_results(document)
    rows = [r for r in document["results"] if r["pokemon"]["dex"] == dex]
    unavailable = [r for r in document.get("unavailable_variants", []) if r["dex"] == dex]
    unavailable_cohorts = [r for r in document.get("unavailable_cohorts", []) if r["dex"] == dex]
    if not rows and not unavailable and not unavailable_cohorts:
        raise ResultContractError(f"dex {dex} is absent from the validated export")
    name = _e(rows[0]["pokemon"].get("name", rows[0]["pokemon"]["slug"]) if rows else f"Pokémon {dex}")
    chunks = [f'<section class="sim-results" data-dex="{dex}">',
              f"<h2>Builds simuladas: {name}</h2>",
              '<fieldset class="sim-controls"><legend>Comparar variantes</legend>',
              '<label>Aggro <select data-sim-aggro><option value="baseline">Normal</option><option value="subtle">Más agresiva</option></select></label>',
              '<label>Cobertura <select data-sim-coverage><option value="baseline">Normal</option><option value="subtle">Más cobertura</option></select></label></fieldset>']
    for row in rows:
        chunks.append(_card(row))
    for item in unavailable:
        v = item["variant"]
        chunks.append(f'<aside class="sim-unavailable" data-style="{_e(item["style"])}" data-availability="{_e(item["availability"])}" '
                      f'data-aggro="{_e(v["aggro"])}" data-coverage="{_e(v["coverage"])}">'
                      f'<strong>Build no disponible</strong><p>{_e(item["reason"])}</p></aside>')
    for item in unavailable_cohorts:
        chunks.append(f'<aside class="sim-unavailable" data-style="{_e(item["style"])}" data-availability="{_e(item["availability"])}">'
                      f'<strong>Build no disponible</strong><p>{_e(item["reason"])}</p></aside>')
    controls = [c for c in document.get("controls", []) if c.get("dex") == dex]
    if controls:
        chunks.append('<section class="sim-controls-reference"><h3>Control sin MT</h3>')
        for control in controls:
            chunks.append(f'<p>{_e(control.get("style", ""))}: {_metric_list(control.get("summary", {}))}</p>')
        chunks.append("</section>")
    if any(c.get("dex") == dex for c in document.get("unavailable_controls", [])):
        chunks.append('<p class="sim-control-unavailable">Control sin MT no disponible para alguna build.</p>')
    chunks.append("</section>")
    return "".join(chunks)


def _card(row: dict[str, Any]) -> str:
    dex = row["pokemon"]["dex"]
    build = row["build"]
    variant = row["variant"]
    outcome = row.get("selection", {}).get("outcome", "best_observed")
    status = "Mejores observados: empate; no se afirma superioridad." if outcome == "tied_best" else "Mejor observado; no se afirma superioridad estadística."
    attacks = "".join(f'<li value="{a["position"]}"><span>{_e(a.get("name", a["id"]))}</span> '
                       f'<small>{_e(a.get("type", ""))} · {_e(a.get("category", ""))}</small></li>' for a in build["attacks"])
    ability = build["ability"]
    nature = build["nature"]
    mint = nature.get("change_item", {})
    capsule = build.get("ability_capsule")
    capsule_text = f' · requiere {_e(capsule["name"])} ({capsule["price"]} monedas)' if capsule else ""
    stats = " · ".join(f'{_e(label)} {values["base"]} → {values["after_nature"]}'
                       for stat, label in (("pa", "Ataque"), ("sa", "At. especial"), ("df", "Defensa"),
                                           ("sd", "Def. especial"), ("spd", "Velocidad"))
                       if (values := nature.get("resulting_stats", {}).get(stat)))
    tms = "".join(f'<li>{_e(tm["name"])}: {_e(tm["price"])} monedas</li>' for tm in build["tm_requirements"]) or "<li>Sin MT</li>"
    start_items = []
    for item in build["initial_attack_details"]:
        unlock = item["unlock"]
        requires = " y ".join(_e(f"{req['upgrade_id']} ({req['price']} monedas)") for req in unlock.get("requires", []))
        suffix = f" + requiere {requires}" if requires else ""
        start_items.append(f'<li>{_e(item["name"])}: {unlock["price"]} monedas{suffix}</li>')
    starts = "".join(start_items)
    natural = " · ".join(_e(move.get("name", move["id"])) for move in build["natural_pool"])
    alt = build.get("no_tm_alternative")
    if isinstance(alt, dict) and alt.get("available") is False:
        no_tm = f'<p class="sim-no-tm-unavailable">Alternativa sin MT no disponible: {_e(alt["reason"])}</p>'
    else:
        no_tm = f'<p class="sim-no-tm">Alternativa sin MT evaluada: <a href="#{_e(alt["build_id"])}">ver build medida</a></p>' if alt else ""
    confidence = row.get("selection", {}).get("confidence") or {}
    uncertainty = "".join(f'<li>{_e(label)}: Δ {interval.get("meanDifference", "—")} '
                          f'(IC descriptivo {interval.get("lower", "—")} a {interval.get("upper", "—")})</li>'
                          for label, interval in confidence.items() if isinstance(interval, dict) and "meanDifference" in interval)
    metrics = _metric_list(row.get("score", {}).get("metrics", {}))
    return (
        f'<article class="sim-build-card" id="{_e(build["id"])}" data-dex="{dex}" data-style="{_e(build["style"])}" '
        f'data-availability="{_e(build["availability"])}" data-aggro="{_e(variant["aggro"])}" data-coverage="{_e(variant["coverage"])}">'
        f'<header><h3>{_e(build["style"].capitalize())} · {_e(build["availability"])}</h3><p>{_e(status)}</p></header>'
        f'<section><h4>Ataques</h4><ol>{attacks}</ol></section>'
        f'<section><h4>Aprendidos de forma natural</h4><p>{natural}</p></section>'
        f'<section><h4>Habilidad: {_e(ability["name"])} ({_e(build["ability_slot"])}){capsule_text}</h4><p>{_e(ability["effect"])}</p></section>'
        f'<p>Naturaleza: {_e(nature["name"])} · sube {_e(nature["up"]["name"])} · baja {_e(nature["down"]["name"])} · '
        f'cambio con {_e(mint.get("name", "Menta"))} ({mint.get("price", "—")} monedas)</p>'
        f'<p>Estadísticas con naturaleza: {stats}</p>'
        f'<section><h4>MT necesarias</h4><ul>{tms}</ul></section>'
        f'<section><h4>Movimientos iniciales</h4><ol>{starts}</ol></section>'
        f'{no_tm}<section><h4>Mediciones</h4><p>{metrics}</p>'
        + (f'<h4>Incertidumbre pareada</h4><ul>{uncertainty}</ul>' if uncertainty else "")
        + '</section></article>'
    )


def _metric_list(metrics: dict[str, Any]) -> str:
    return " · ".join(f"{_e(k)}: {_e(v)}" for k, v in metrics.items())


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("web_json", type=Path)
    parser.add_argument("dex", type=int)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    document = json.loads(args.web_json.read_text(encoding="utf8"))
    args.out.write_text(render_cards(document, args.dex) + "\n", encoding="utf8")
    print(f"rendered dex {args.dex} cards to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
