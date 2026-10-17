"""Short summaries for every ficha, in Spanish and English, written from data/summary_facts.json.

    python3 build/summaries.py --write    # (re)writes data/summaries.json where the facts changed or a text fails
    python3 build/summaries.py            # validates data/summaries.json against the current facts

The texts are composed by this script from phrase banks written by hand below, picked by the facts of each species.
Nothing runs at page load and there is no AI service: the ficha only reads the JSON.

Every claim sits in a mark, `[key|text]`. `key` names the fact it states, for example `spd+` (fast), `hb-` (big
hitbox), `m.start:ember` (the start move) or `down:hitbox:S` (the hitbox is what keeps it out of S). The validator:

  1. checks that the fact behind each key holds (thresholds below);
  2. scans the plain text with a lexicon (fast, slow, HP, hitbox, damage, types, tier letters, every move, item and
     card name...). A word that states something must sit inside a mark whose key licenses it, so a hand edit cannot
     add an unsupported claim;
  3. checks move, item and card names against the build the ficha shows now (start move, bonded group,
     alternatives, best item, priority cards), in that language;
  4. checks 2-3 sentences, the length, that Spanish and English carry the same keys, and that the stored facts
     fingerprint is the current one.

Any failure makes build/catalog.py stop.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import summary_facts  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "data" / "summaries.json"

HIGH, LOW = 0.75, 0.25      # stat percentile for "fast" / "slow", "lots of HP" / "low HP", "hits hard" / "hits soft"
HUGE_R = 24.6               # body radius from which a hitbox is "huge" (median 14.1; game sizes 10.6 ... 52)
DRIVER_MIN = 10             # places a factor must move the species to be named as a reason for its rank
MAX_LEN = 240               # characters of plain text per language
TIERS = "SABCD"
TIER_BANDS = {"S": (1, 30), "A": (31, 120), "B": (121, 320), "C": (321, 620), "D": (621, 966)}

MARK = re.compile(r"\[([^\[\]|]+)\|([^\[\]]+)\]")
NAME_ROLES = ("m.start", "m.group", "m.alt", "i.best", "c.first")


def tier_of(rank: int) -> str:
    rank = max(1, min(966, rank))
    return next(t for t, (lo, hi) in TIER_BANDS.items() if lo <= rank <= hi)


def plain(text: str) -> str:
    return MARK.sub(lambda m: m.group(2), text)


# ------------------------------------------------------------------ facts behind each key

def _stat(f: dict, k: str) -> float:
    return f["stats"][k]["pct"]


def _hb(f: dict) -> tuple[float, float]:
    return f["hitbox"]["r"], f["hitbox"]["median"]


def _places(f: dict, factor: str) -> int:
    return f["drivers"]["gate" if factor.startswith("gate") else factor]["places"]


# A driver can only be named in the direction its fact points: a hitbox lifts only if it is smaller than the median.
DIRECTION = {
    "hitbox": lambda f, up: (_hb(f)[0] < _hb(f)[1]) if up else (_hb(f)[0] > _hb(f)[1]),
    "speed": lambda f, up: (_stat(f, "spd") > 0.5) == up,
    "hp": lambda f, up: (_stat(f, "hp") > 0.5) == up,
    "attack": lambda f, up: (_stat(f, "atk") > 0.5) == up,
    "start_move": lambda f, up: True,
    "best_move": lambda f, up: True,
    "stats": lambda f, up: (f["pillars"]["stats"] > 0.5) == up,
    "moves": lambda f, up: (f["pillars"]["moves"] > 0.5) == up,
    "typedef": lambda f, up: (f["pillars"]["typedef"] > 0.5) == up,
    "late": lambda f, up: True,
    "gate_stats": lambda f, up: not up and f["flags"]["statsCapped"],
    "gate_types": lambda f, up: not up and f["flags"]["typesCapped"],
    "gate_melee": lambda f, up: not up and f["flags"]["melee"],
}


def ranked_drivers(f: dict, up: bool) -> list[str]:
    """Factors that move the species at least DRIVER_MIN places in that direction, strongest first."""
    out = []
    for factor, ok in DIRECTION.items():
        if factor.startswith("gate") and not ok(f, up):
            continue
        p = _places(f, factor)
        if (p >= DRIVER_MIN if up else p <= -DRIVER_MIN) and ok(f, up):
            out.append((abs(p), factor))
    return [k for _, k in sorted(out, reverse=True)]


def qualifies(f: dict, tier: str, factor: str) -> bool:
    """make_definitive.qualifies for the tier the species would reach without that factor."""
    if tier in "CD" or factor.startswith("gate"):
        return True
    stats = 0.5 if factor == "stats" else f["pillars"]["stats"]
    if stats < {"S": 0.6, "A": 0.4, "B": 0.2}[tier]:
        return False
    return not (tier == "S" and (f["matchup"]["attackTypes"] < 3 or f["flags"]["melee"]))


def holds(key: str, f: dict) -> str | None:
    """None if the fact behind `key` holds for species f, else why not."""
    b = f["build"]
    simple = {
        "spd+": _stat(f, "spd") >= HIGH, "spd-": _stat(f, "spd") <= LOW,
        "hp+": _stat(f, "hp") >= HIGH, "hp-": _stat(f, "hp") <= LOW,
        "atk+": _stat(f, "atk") >= HIGH, "atk-": _stat(f, "atk") <= LOW,
        "hb+": _hb(f)[0] < _hb(f)[1], "hb-": _hb(f)[1] < _hb(f)[0] < HUGE_R, "hb--": _hb(f)[0] >= HUGE_R,
        "hb0": _hb(f)[0] == _hb(f)[1],
        "td+": f["pillars"]["typedef"] >= HIGH, "td-": f["pillars"]["typedef"] <= LOW,
        "avg": all(LOW < _stat(f, k) < HIGH for k in ("spd", "hp", "atk")),
        "calm": not ranked_drivers(f, True) and not ranked_drivers(f, False),
        "nodown": not ranked_drivers(f, False),
    }
    if key in simple:
        return None if simple[key] else f"{key}: el dato no lo respalda"
    head, _, ref = key.partition(":")
    if head == "m.start":
        return None if ref == b["start"]["id"] else f"{key}: el ataque inicial es {b['start']['id']}"
    if head == "m.group":
        return None if ref in [m["id"] for m in b["group"]] else f"{key}: no está en el grupo vinculado"
    if head == "m.alt":
        return None if ref in [m["id"] for m in b["alts"]] else f"{key}: no es un ataque opcional"
    if head == "i.best":
        return None if ref == b["item"]["id"] else f"{key}: el mejor objeto es {b['item']['id']}"
    if head == "c.first":
        return None if b["cards"] and ref == b["cards"][0]["id"] else f"{key}: no es la primera carta"
    if head in ("up", "down"):
        factor, _, tier = ref.partition(":")
        if factor not in DIRECTION:
            return f"{key}: factor desconocido"
        up = head == "up"
        top = ranked_drivers(f, up)[:2]
        if factor not in top:
            return f"{key}: no es de los dos factores que más lo {'suben' if up else 'bajan'} ({top})"
        if tier:
            cf = tier_of(f["rank"] - _places(f, factor))
            if up:
                if not (tier == f["tier"] and TIERS.index(cf) > TIERS.index(tier)):
                    return f"{key}: sin ese factor seguiría en {cf}"
            elif not (tier == cf and TIERS.index(cf) < TIERS.index(f["tier"]) and qualifies(f, cf, factor)):
                return f"{key}: sin ese factor no llegaría a {tier}"
        return None
    return f"{key}: clave desconocida"


# ------------------------------------------------------------------ lexicon: words that state a fact

def _keys(*ks: str):
    return lambda key: any(key == k or key.startswith(k + ":") for k in ks)


SPEED = ("spd+", "spd-", "avg", "up:speed", "down:speed")
HP = ("hp+", "hp-", "avg", "up:hp", "down:hp")
DMG = ("atk+", "atk-", "avg", "up:attack", "down:attack")
LEXICON = [
    # (regex, Spanish?, English?, which keys may say it)
    (r"\brápid[oa]s?\b", True, False, _keys("spd+")), (r"\bfast\b", False, True, _keys("spd+")),
    (r"\blent[oa]s?\b", True, False, _keys("spd-")), (r"\bslow\b", False, True, _keys("spd-")),
    (r"\bvelocidad\b", True, False, _keys(*SPEED)), (r"\bspeed\b", False, True, _keys(*SPEED)),
    (r"\bmucha vida\b", True, False, _keys("hp+")), (r"\blots of HP\b", False, True, _keys("hp+")),
    (r"\bpoca vida\b", True, False, _keys("hp-")), (r"\blow HP\b", False, True, _keys("hp-")),
    (r"\bvida\b", True, False, _keys(*HP)), (r"\bHP\b", False, True, _keys(*HP)),
    (r"\bpega fuerte\b", True, False, _keys("atk+")), (r"\bhits hard\b", False, True, _keys("atk+")),
    (r"\bpega poco\b", True, False, _keys("atk-")), (r"\bhits soft\b", False, True, _keys("atk-")),
    (r"\bpega\b", True, False, _keys("atk+", "atk-")), (r"\bhits\b", False, True, _keys("atk+", "atk-")),
    (r"\bdaño\b", True, False, _keys(*DMG)), (r"\bdamage\b", False, True, _keys(*DMG)),
    (r"\bhitbox\b", True, True, _keys("hb+", "hb-", "hb--", "hb0", "up:hitbox", "down:hitbox")),
    (r"\bpequeñ[oa]\b", True, False, _keys("hb+", "up:hitbox")), (r"\bsmall\b", False, True, _keys("hb+", "up:hitbox")),
    (r"\bgrande\b", True, False, _keys("hb-", "down:hitbox")), (r"\bbig\b", False, True, _keys("hb-", "down:hitbox")),
    (r"\benorme\b", True, False, _keys("hb--")), (r"\bhuge\b", False, True, _keys("hb--")),
    (r"\bnormal\b", True, True, _keys("hb0")),
    (r"\btipos?\b", True, False, _keys("td+", "td-", "up:typedef", "down:typedef", "down:gate_types")),
    (r"\btypes?\b", False, True, _keys("td+", "td-", "up:typedef", "down:typedef", "down:gate_types")),
    (r"\bataque inicial\b", True, False, _keys("up:start_move", "down:start_move")),
    (r"\bstart move\b", False, True, _keys("up:start_move", "down:start_move")),
    (r"\bmejor ataque\b", True, False, _keys("up:best_move", "down:best_move")),
    (r"\bbest move\b", False, True, _keys("up:best_move", "down:best_move")),
    (r"\bataques que aprende\b", True, False, _keys("up:moves", "down:moves")),
    (r"\bmoves it learns\b", False, True, _keys("up:moves", "down:moves")),
    (r"\bestadísticas\b", True, False, _keys("up:stats", "down:stats", "down:gate_stats")),
    (r"\bstats\b", False, True, _keys("up:stats", "down:stats", "down:gate_stats")),
    (r"\bfinal de partida\b|\bpartidas largas\b", True, False, _keys("up:late", "down:late")),
    (r"\blate game\b|\blong runs\b", False, True, _keys("up:late", "down:late")),
    (r"\btope\b", True, False, _keys("down:gate_stats")), (r"\bcap\b", False, True, _keys("down:gate_stats")),
    (r"\bcuerpo a cuerpo\b", True, False, _keys("down:gate_melee")), (r"\bmelee\b", False, True, _keys("down:gate_melee")),
    (r"\bdel montón\b|\bnormalito\b", True, False, _keys("avg")), (r"\baverage\b", False, True, _keys("avg")),
    (r"\bnada lo (frena|baja)\b", True, False, _keys("nodown", "calm")),
    (r"\bnothing holds it back\b", False, True, _keys("nodown", "calm")),
    (r"\bningún factor\b", True, False, _keys("calm")), (r"\bno single factor\b", False, True, _keys("calm")),
    (r"\b[SABCD]\b", True, True, lambda key: bool(re.search(r":[SABCD]$", key))),
    (r"\d", True, True, lambda key: False),
]


def names_in(f: dict, lang: str) -> dict[str, list[str]]:
    """Every name the build can show, mapped to the keys that may carry it."""
    b = f["build"]
    out: dict[str, list[str]] = {}
    out.setdefault(b["start"][lang], []).append("m.start:" + b["start"]["id"])
    for m in b["group"]:
        out.setdefault(m[lang], []).append("m.group:" + m["id"])
    for m in b["alts"]:
        out.setdefault(m[lang], []).append("m.alt:" + m["id"])
    out.setdefault(b["item"][lang], []).append("i.best:" + b["item"]["id"])
    if b["cards"]:
        out.setdefault(b["cards"][0][lang], []).append("c.first:" + b["cards"][0]["id"])
    return out


def validate(dex: str, entry: dict, f: dict, all_names: dict[str, set[str]]) -> list[str]:
    errs = []
    if entry.get("fp") != summary_facts.fingerprint(f):
        errs.append("los datos han cambiado desde que se escribió (huella distinta)")
    keysets = {}
    for lang in ("es", "en"):
        text = entry.get(lang, "")
        if MARK.sub("", text).count("[") or MARK.sub("", text).count("]") or MARK.sub("", text).count("|"):
            errs.append(f"{lang}: marca mal cerrada")
        marks = [(m.start(), m.end(), m.group(1), m.group(2)) for m in MARK.finditer(text)]
        keysets[lang] = sorted(k for _, _, k, _ in marks)
        for _, _, key, _ in marks:
            why = holds(key, f)
            if why:
                errs.append(f"{lang}: {why}")
        # Each lexicon hit and each known name must sit inside a mark that licenses it.
        spans = []
        pos = 0
        flat = ""
        for s, e, key, inner in marks:
            flat += text[pos:s]
            spans.append((len(flat), len(flat) + len(inner), key))
            flat += inner
            pos = e
        flat += text[pos:]
        owner = lambda i: next((k for a, z, k in spans if a <= i < z), None)  # noqa: E731
        for rx, es, en, ok in LEXICON:
            if not (es if lang == "es" else en):
                continue
            flags = 0 if any(c.isupper() for c in rx) else re.IGNORECASE
            for m in re.finditer(rx, flat, flags):
                key = owner(m.start())
                if key and key.split(":")[0] in NAME_ROLES:
                    continue  # inside a move, item or card name; checked against the build below
                if key is None or not ok(key):
                    errs.append(f"{lang}: «{m.group(0)}» sin dato que lo respalde ({key or 'fuera de marca'})")
                elif re.fullmatch(r"[SABCD]", m.group(0)) and not key.endswith(":" + m.group(0)):
                    errs.append(f"{lang}: tier «{m.group(0)}» no coincide con {key}")
        build_names = names_in(f, lang)
        for nm in sorted(all_names[lang], key=len, reverse=True):
            for m in re.finditer(r"(?<!\w)" + re.escape(nm) + r"(?!\w)", flat):
                key = owner(m.start())
                if key and key.split(":")[0] in NAME_ROLES:
                    continue  # part of a longer name in a name mark, checked whole below
                if key is None or key not in build_names.get(nm, []):
                    errs.append(f"{lang}: «{nm}» no coincide con la build ({key or 'fuera de marca'})")
        for s, e, key in spans:
            if key.split(":")[0] in NAME_ROLES:
                if key not in build_names.get(flat[s:e], []):
                    errs.append(f"{lang}: el nombre de {key} debería ser el de la build, no «{flat[s:e]}»")
        p = plain(text)
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", p.strip()) if s]
        if not 2 <= len(sentences) <= 3:
            errs.append(f"{lang}: {len(sentences)} frases (2-3)")
        if len(p) > MAX_LEN:
            errs.append(f"{lang}: {len(p)} caracteres (máximo {MAX_LEN})")
    if keysets.get("es") != keysets.get("en"):
        errs.append(f"español e inglés no dicen lo mismo: {keysets.get('es')} / {keysets.get('en')}")
    return [f"{dex} {f['name']}: {e}" for e in errs]


def all_build_names(facts: dict) -> dict[str, set[str]]:
    """Names of every move, item and card any build uses, so a name from another species is caught too."""
    out = {"es": set(), "en": set()}
    for f in facts["species"].values():
        for lang in out:
            out[lang].update(names_in(f, lang))
            out[lang].update(c[lang] for c in f["build"]["cards"])
    return out


def check(facts: dict, summaries: dict) -> tuple[list[str], dict]:
    names = all_build_names(facts)
    errs = []
    missing = sorted(set(facts["species"]) - set(summaries["species"]), key=int)
    errs += [f"{d}: sin resumen" for d in missing]
    errs += [f"{d}: resumen de un Pokémon que no existe" for d in set(summaries["species"]) - set(facts["species"])]
    for d, entry in summaries["species"].items():
        if d in facts["species"]:
            errs += validate(d, entry, facts["species"][d], names)
    stats = {"species": len(summaries["species"]), "texts": 2 * len(summaries["species"]),
             "claims": sum(len(MARK.findall(e[lang])) for e in summaries["species"].values() for lang in ("es", "en")),
             "errors": len(errs)}
    return errs, stats


# ------------------------------------------------------------------ the phrase banks

def pick(dex: int, options: list, salt: str = ""):
    h = int(hashlib.sha1(f"{dex}{salt}".encode()).hexdigest(), 16)
    return options[h % len(options)]


def cap(s: str) -> str:
    return s[0].upper() + s[1:]


# trait key: (form, Spanish, English). Forms: "adj" (rápido / fast), "verb" (pega fuerte / hits hard) and "noun"
# (mucha vida / lots of HP), which share one «con» (or «tiene» after a verb or «pero») and one "has".
TRAITS = {
    "spd+": ("adj", "rápido", "fast"),
    "spd-": ("adj", "lento", "slow"),
    "atk+": ("verb", "pega fuerte", "hits hard"),
    "atk-": ("verb", "pega poco", "hits soft"),
    "td+": ("verb", "aguanta bien los tipos rivales", "shrugs off enemy types"),
    "td-": ("verb", "sufre contra los tipos rivales", "suffers against enemy types"),
    "hp+": ("noun", "mucha vida", "lots of HP"),
    "hp-": ("noun", "poca vida", "low HP"),
    "hb+": ("noun", "hitbox pequeño", "a small hitbox"),
    "hb-": ("noun", "hitbox grande", "a big hitbox"),
    "hb--": ("noun", "hitbox enorme", "a huge hitbox"),
}
GOOD = {"spd+", "hp+", "atk+", "hb+", "td+"}
ORDER = ["spd", "atk", "td", "hp", "hb"]  # adjectives, then verbs, then the nouns that share «con»


def traits(f: dict) -> list[str]:
    """Up to three of the clearest traits, strongest first."""
    cands = []
    for k, stat in (("spd", "spd"), ("hp", "hp"), ("atk", "atk")):
        p = _stat(f, stat)
        if p >= HIGH:
            cands.append((p - 0.5, k + "+"))
        elif p <= LOW:
            cands.append((0.5 - p, k + "-"))
    r, med = _hb(f)
    if r < med:
        cands.append((0.4, "hb+"))
    elif r >= HUGE_R:
        cands.append((0.45, "hb--"))
    elif r > med:
        cands.append((0.3, "hb-"))
    td = f["pillars"]["typedef"]
    if td >= 0.85:
        cands.append((td - 0.5 - 0.1, "td+"))
    elif td <= 0.15:
        cands.append((0.5 - td - 0.1, "td-"))
    return [k for _, k in sorted(cands, reverse=True)[:3]]


def _join(parts: list[str], sep_last: str) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + sep_last + parts[-1]


def profile(f: dict) -> tuple[str, str]:
    ks = traits(f)
    if not ks:
        hb = "hb0" if _hb(f)[0] == _hb(f)[1] else None
        es = "[avg|Del montón en velocidad, vida y daño]"
        en = "[avg|Average speed, HP and damage]"
        if hb:
            es += ", con [hb0|hitbox normal]"
            en += ", [hb0|normal hitbox]"
        return es + ".", en + "."
    ks = sorted(ks, key=lambda k: ORDER.index(k.rstrip("+-")))
    good = [k for k in ks if k in GOOD]
    bad = [k for k in ks if k not in GOOD]
    lead, rest = (good, bad) if good else (bad, [])
    es, en = cap_text(trait_list(lead, "es", True)), cap_text(trait_list(lead, "en", True))
    if rest:
        es += ", pero " + trait_list(rest, "es", False)
        en += ", but " + trait_list(rest, "en", False)
    return es + ".", en + "."


def trait_list(keys: list[str], lang: str, leading: bool) -> str:
    """«rápido, pega fuerte, con mucha vida y hitbox pequeño» / «es lento y tiene hitbox grande»."""
    col = 1 if lang == "es" else 2
    and_ = " y " if lang == "es" else " and "
    parts = []
    for k in keys:
        form, text = TRAITS[k][0], TRAITS[k][col]
        if form == "adj" and not leading:
            text = ("es " if lang == "es" else "is ") + text
        parts.append((form, f"[{k}|{text}]"))
    nouns = [p for f, p in parts if f == "noun"]
    others = [p for f, p in parts if f != "noun"]
    if nouns:
        after_verb = any(f == "verb" for f, _ in parts)
        with_ = "con " if lang == "es" and leading and not after_verb else ("tiene " if lang == "es" else "has ")
        others.append(with_ + _join(nouns, and_))
        if len(nouns) > 1:
            return ", ".join(others)
    return _join(others, and_)


def mv(role: str, m: dict, lang: str) -> str:
    return f"[{role}:{m['id']}|{m[lang]}]"


def build_lines(f: dict) -> list[tuple[str, str]]:
    """The build sentence, longest first: with the attack buff and an alternative, then without them."""
    b = f["build"]
    start = b["start"]
    attacks = [m for m in b["group"][:b["attacks"]] if m["id"] != start["id"]]
    boosts = b["group"][b["attacks"]:]
    used = {start["id"]} | {m["id"] for m in b["group"]}
    alt = next((m for m in b["alts"] if m["id"] not in used), None)
    item = b["item"]
    out = []
    for with_boost, with_alt in ((True, True), (False, True), (True, False), (False, False)):
        pair = []
        for lang in ("es", "en"):
            parts = [mv("m.group", m, lang) for m in attacks]
            if with_alt and alt and parts:
                parts[-1] += f" ({'o' if lang == 'es' else 'or'} {mv('m.alt', alt, lang)})"
            if with_boost and boosts:
                parts.append(mv("m.group", boosts[0], lang))
            group = _join(parts, " y " if lang == "es" else " and ") if parts else None
            it = f"[i.best:{item['id']}|{item[lang]}]"
            if lang == "es":
                verb = pick(f["dex"], ["vincula", "súmale", "vincúlale"], "es-bond")
                bond = f" y {verb} {group}" if group else ""
                pair.append(f"Empieza con {mv('m.start', start, lang)}{bond}; lleva {it}.")
            else:
                verb = pick(f["dex"], ["bond", "add", "link"], "en-bond")
                bond = f", {verb} {group}" if group else ""
                pair.append(f"Start with {mv('m.start', start, lang)}{bond}; carry {it}.")
        out.append(tuple(pair))
    return out


# factor: (Spanish noun phrase, English noun phrase). The hitbox says small or big, as its direction requires.
FACTOR = {
    "speed": ("su velocidad", "its speed"), "hp": ("su vida", "its HP"), "attack": ("su daño", "its damage"),
    "start_move": ("su ataque inicial", "its start move"), "best_move": ("su mejor ataque", "its best move"),
    "stats": ("sus estadísticas", "its stats"), "moves": ("los ataques que aprende", "the moves it learns"),
    "typedef": ("sus tipos", "its types"), "late": ("su final de partida", "its late game"),
    "gate_stats": ("el tope por estadísticas", "the stats cap"),
    "gate_types": ("tener un solo tipo de ataque", "having a single attack type"),
    "gate_melee": ("empezar cuerpo a cuerpo", "its melee start"),
}


def noun(factor: str, up: bool) -> tuple[str, str]:
    if factor == "hitbox":
        return ("su hitbox pequeño", "its small hitbox") if up else ("su hitbox grande", "its big hitbox")
    return FACTOR[factor]


def gate_factor(f: dict) -> str | None:
    if f["drivers"]["gate"]["places"] > -DRIVER_MIN:
        return None
    for flag, key in (("statsCapped", "gate_stats"), ("typesCapped", "gate_types"), ("melee", "gate_melee")):
        if f["flags"][flag]:
            return key
    return None


def crossing(f: dict, factor: str, up: bool) -> str | None:
    """The tier named when that factor alone decides it: the one it keeps (up) or the one it blocks (down)."""
    cf = tier_of(f["rank"] - _places(f, factor))
    if up:
        return f["tier"] if TIERS.index(cf) > TIERS.index(f["tier"]) else None
    return cf if TIERS.index(cf) < TIERS.index(f["tier"]) and qualifies(f, cf, factor) else None


PLURAL = {"stats", "moves", "typedef"}


def why_line(f: dict) -> tuple[str, str]:
    ups = ranked_drivers(f, True)
    downs = ranked_drivers(f, False)
    up = ups[0] if ups else None
    down = downs[0] if downs else None
    d = f["dex"]
    # Spanish and English verb endings for a singular or plural subject
    n_ = lambda k: "n" if k in PLURAL else ""  # noqa: E731
    es_ = lambda k: "son" if k in PLURAL else "es"  # noqa: E731
    s_ = lambda k: "" if k in PLURAL else "s"  # noqa: E731
    is_ = lambda k: "are" if k in PLURAL else "is"  # noqa: E731
    t_up = t_dn = None
    if up:
        n_es, n_en = noun(up, True)
        t_up = crossing(f, up, True)
        up_es = f"[up:{up}:{t_up}|sin {n_es} no estaría en el {t_up}]" if t_up else f"[up:{up}|{n_es}]"
        up_en = f"[up:{up}:{t_up}|without {n_en} it would drop out of {t_up}]" if t_up else f"[up:{up}|{n_en}]"
    if down:
        n_es, n_en = noun(down, False)
        t_dn = crossing(f, down, False)
        dn_es = (f"[down:{down}:{t_dn}|{n_es} {es_(down)} lo que lo deja fuera del {t_dn}]" if t_dn
                 else f"[down:{down}|{n_es}]")
        dn_en = (f"[down:{down}:{t_dn}|{n_en} {is_(down)} what keeps it out of {t_dn}]" if t_dn
                 else f"[down:{down}|{n_en}]")

    if up and down:
        if t_up and t_dn:
            return f"{cap_mark(up_es)}, y {dn_es}.", f"{cap_mark(up_en)}, and {dn_en}."
        if t_dn:
            return (f"{cap_mark(dn_es)}; lo sube{n_(up)} {up_es}.", f"{cap_mark(dn_en)}; {up_en} lift{s_(up)} it.")
        if t_up:
            return (f"{cap_mark(up_es)}; lo frena{n_(down)} {dn_es}.",
                    f"{cap_mark(up_en)}; {dn_en} hold{s_(down)} it back.")
        es = pick(d, [f"Lo sube{n_(up)} {up_es}; lo frena{n_(down)} {dn_es}.",
                      f"Tira{n_(up)} de él {up_es}; lo lastra{n_(down)} {dn_es}.",
                      f"Lo que más le ayuda {es_(up)} {up_es}; lo que más le pesa, {dn_es}."], "why")
        en = pick(d, [f"{cap_mark(up_en)} lift{s_(up)} it; {dn_en} hold{s_(down)} it back.",
                      f"{cap_mark(up_en)} carr{'y' if up in PLURAL else 'ies'} it; {dn_en} drag{s_(down)} it down.",
                      f"What helps most {is_(up)} {up_en}; what hurts most, {dn_en}."], "why")
        return es, en
    if up:
        if t_up:
            return (f"{cap_mark(up_es)}, y [nodown|nada lo frena] de verdad.",
                    f"{cap_mark(up_en)}, and [nodown|nothing holds it back] much.")
        return (f"Lo que más lo sube {es_(up)} {up_es}, y [nodown|nada lo frena] de verdad.",
                f"What lifts it most {is_(up)} {up_en}, and [nodown|nothing holds it back] much.")
    if down:
        if t_dn:
            return f"{cap_mark(dn_es)}.", f"{cap_mark(dn_en)}."
        return (f"Lo que más lo frena {es_(down)} {dn_es}.", f"What holds it back most {is_(down)} {dn_en}.")
    return ("[calm|Ningún factor] lo mueve mucho: está donde lo ponen todas las medidas juntas.",
            "[calm|No single factor] moves it much: it sits where all the measures put it together.")


def cap_mark(s: str) -> str:
    """Capitalise the visible text of a mark that starts a sentence."""
    i = s.index("|") + 1
    return s[:i] + s[i].upper() + s[i + 1:]


def cap_text(s: str) -> str:
    return cap_mark(s) if s.startswith("[") else cap(s)


def compose(f: dict) -> dict:
    p_es, p_en = profile(f)
    w_es, w_en = why_line(f)
    for b_es, b_en in build_lines(f):
        es, en = " ".join([p_es, b_es, w_es]), " ".join([p_en, b_en, w_en])
        if max(len(plain(es)), len(plain(en))) <= MAX_LEN:
            break
    return {"fp": summary_facts.fingerprint(f), "es": es, "en": en}


# ------------------------------------------------------------------ files

def load_facts() -> dict:
    return json.loads(summary_facts.OUT.read_text(encoding="utf8"))


def load() -> dict:
    if not PATH.exists():
        return {"species": {}}
    return json.loads(PATH.read_text(encoding="utf8"))


def write(facts: dict) -> dict:
    """Recompose the entries whose facts changed, that fail validation or that are missing. Keeps the rest."""
    old = load()
    names = all_build_names(facts)
    out, counts = {}, {"regenerated": 0, "kept": 0, "new": 0}
    for d, f in facts["species"].items():
        prev = old["species"].get(d)
        if prev and not validate(d, prev, f, names):
            out[d] = prev
            counts["kept"] += 1
            continue
        out[d] = compose(f)
        counts["regenerated" if prev else "new"] += 1
    doc = {"note": "Escrito por build/summaries.py a partir de data/summary_facts.json. Las marcas [clave|texto] "
                   "dicen qué dato respalda cada afirmación; la ficha las convierte en iconos.",
           "thresholds": {"high": HIGH, "low": LOW, "hugeRadius": HUGE_R, "driverMin": DRIVER_MIN, "maxLen": MAX_LEN},
           "species": out}
    PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf8")
    return counts


def public(summaries: dict, lang: str) -> dict:
    """What the ficha loads: dex -> marked text in that language."""
    return {d: e[lang] for d, e in summaries["species"].items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    facts = load_facts()
    if args.write:
        counts = write(facts)
        print(f"resúmenes: {counts['regenerated']} reescritos, {counts['new']} nuevos, {counts['kept']} sin cambios")
    errs, stats = check(facts, load())
    for e in errs[:40]:
        print("  " + e, file=sys.stderr)
    print(f"validación: {stats['species']} Pokémon, {stats['texts']} textos, {stats['claims']} afirmaciones marcadas, "
          f"{stats['errors']} errores")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
