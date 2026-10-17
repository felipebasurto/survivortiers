"""Claim checker for the ficha summaries (data/summaries.json), in Spanish and English.

The texts are written by the pipeline in build/summary_pipeline.py (Grok subagents, prompt in
build/prompts/summary.md) from data/facts.parquet. This module only checks them; it uses the standard library so
build/catalog.py can run it on the hosting.

Every claim sits in a mark, `[key|text]`. `key` names the fact it states, for example `spd+` (fast), `hb-` (big
hitbox), `m.start:ember` (the start move) or `down:hitbox:S` (the hitbox is what keeps it out of S). The checker:

  1. checks that the fact behind each key holds (thresholds below);
  2. scans the plain text with a lexicon (fast, slow, HP, hitbox, damage, types, tier letters, every move, item and
     card name...). A word that states something must sit inside a mark whose key licenses it, so neither the
     writer nor a hand edit can add an unsupported claim;
  3. checks move, item and card names against the build the ficha shows now (start move, bonded group,
     alternatives, best item, priority cards), in that language;
  4. checks 2-3 sentences, the length, that Spanish and English carry the same keys, and that the facts hash
     stored with the text is the current one.

On a record without drivers (summary_facts.base_records(), what catalog.py has) the rank-driver keys are not
re-derived; everything else is, and the stored `bfp` must match.
"""
from __future__ import annotations

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
THRESHOLDS = {"high": HIGH, "low": LOW, "hugeRadius": HUGE_R, "driverMin": DRIVER_MIN, "maxLen": MAX_LEN}
DRIVER_HEADS = ("up", "down")

MARK = re.compile(r"\[([^\[\]|]+)\|([^\[\]]+)\]")
NAME_ROLES = ("m.start", "m.group", "m.alt", "i.best", "c.first")


def is_name(key: str) -> bool:
    """Marks whose text is a move, item or card name. The best move as a rank driver is said by its name too."""
    head, _, ref = key.partition(":")
    return head in NAME_ROLES or (head in ("up", "down") and ref.split(":")[0] == "best_move")


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
    head, _, ref = key.partition(":")
    if "drivers" not in f and (head in DRIVER_HEADS or key in ("calm", "nodown")):
        return None  # base record: drivers are checked where they are computed (summary_pipeline.py)
    simple = {
        "spd+": _stat(f, "spd") >= HIGH, "spd-": _stat(f, "spd") <= LOW,
        "hp+": _stat(f, "hp") >= HIGH, "hp-": _stat(f, "hp") <= LOW,
        "atk+": _stat(f, "atk") >= HIGH, "atk-": _stat(f, "atk") <= LOW,
        "hb+": _hb(f)[0] < _hb(f)[1], "hb-": _hb(f)[1] < _hb(f)[0] < HUGE_R, "hb--": _hb(f)[0] >= HUGE_R,
        "hb0": _hb(f)[0] == _hb(f)[1],
        "td+": f["pillars"]["typedef"] >= HIGH, "td-": f["pillars"]["typedef"] <= LOW,
        "avg": all(LOW < _stat(f, k) < HIGH for k in ("spd", "hp", "atk")),
    }
    if key in ("calm", "nodown"):
        ups, downs = ranked_drivers(f, True), ranked_drivers(f, False)
        return None if not downs and (key == "nodown" or not ups) else f"{key}: el dato no lo respalda"
    if key in simple:
        return None if simple[key] else f"{key}: el dato no lo respalda"
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
    if head in DRIVER_HEADS:
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
    out.setdefault(b["best"][lang], []).extend(
        f"{d}:best_move" for d in ("up", "down"))
    return out


def validate(dex: str, entry: dict, f: dict, all_names: dict[str, set[str]]) -> list[str]:
    errs = []
    full = "drivers" in f
    if entry.get("fp" if full else "bfp") != summary_facts.fingerprint(f):
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
                if key and is_name(key):
                    continue  # inside a move, item or card name; checked against the build below
                if key is None or not ok(key):
                    errs.append(f"{lang}: «{m.group(0)}» sin dato que lo respalde ({key or 'fuera de marca'})")
                elif re.fullmatch(r"[SABCD]", m.group(0)) and not key.endswith(":" + m.group(0)):
                    errs.append(f"{lang}: tier «{m.group(0)}» no coincide con {key}")
        build_names = names_in(f, lang)
        for nm in sorted(all_names[lang], key=len, reverse=True):
            for m in re.finditer(r"(?<!\w)" + re.escape(nm) + r"(?!\w)", flat):
                key = owner(m.start())
                if key and is_name(key):
                    continue  # part of a longer name in a name mark, checked whole below
                if key is None or key not in build_names.get(nm, []):
                    errs.append(f"{lang}: «{nm}» no coincide con la build ({key or 'fuera de marca'})")
        for s, e, key in spans:
            if is_name(key):
                if key not in build_names.get(flat[s:e], []):
                    errs.append(f"{lang}: el nombre de {key} debería ser el de la build, no «{flat[s:e]}»")
        p = plain(text)
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", p.strip()) if s]
        if not 2 <= len(sentences) <= 3:
            errs.append(f"{lang}: {len(sentences)} frases (2-3)")
        if len(p) > MAX_LEN:
            errs.append(f"{lang}: {len(p)} caracteres (máximo {MAX_LEN})")
    errs += coverage(keysets.get("es", []), f)
    if keysets.get("es") != keysets.get("en"):
        errs.append(f"español e inglés no dicen lo mismo: {keysets.get('es')} / {keysets.get('en')}")
    return [f"{dex} {f['name']}: {e}" for e in errs]


TRAIT_KEYS = ("spd+", "spd-", "hp+", "hp-", "atk+", "atk-", "hb+", "hb-", "hb--", "hb0", "td+", "td-", "avg")


def coverage(keys: list[str], f: dict) -> list[str]:
    """The three things a summary must say: what it is, how to build it, why that rank."""
    errs = []
    heads = {k.split(":")[0] for k in keys}
    if not set(keys) & set(TRAIT_KEYS) and any(holds(k, f) is None for k in TRAIT_KEYS):
        errs.append("falta el perfil: ningún rasgo marcado (spd+, hb-, td+...)")
    if "m.start" not in heads:
        errs.append("falta el ataque inicial (m.start)")
    if "i.best" not in heads:
        errs.append("falta el objeto (i.best)")
    if not heads & {"up", "down", "nodown", "calm"}:
        errs.append("falta el porqué del puesto (up:..., down:..., nodown o calm)")
    return errs


def all_build_names(facts: dict[str, dict]) -> dict[str, set[str]]:
    """Names of every move, item and card any build uses, so a name from another species is caught too."""
    out = {"es": set(), "en": set()}
    for f in facts.values():
        for lang in out:
            out[lang].update(names_in(f, lang))
            out[lang].update(c[lang] for c in f["build"]["cards"])
    return out


def check(facts: dict[str, dict], summaries: dict) -> tuple[list[str], dict]:
    """All errors of data/summaries.json against these records (dex -> record, full or base). A flagged species
    (the writer failed it after every retry) has no text and is not an error; it is counted."""
    names = all_build_names(facts)
    texts, flagged = summaries["species"], summaries.get("flagged", {})
    errs = [f"{d}: sin resumen" for d in sorted(set(facts) - set(texts) - set(flagged), key=int)]
    errs += [f"{d}: resumen de un Pokémon que no existe" for d in sorted(set(texts) - set(facts), key=int)]
    for d, entry in texts.items():
        if d in facts:
            errs += validate(d, entry, facts[d], names)
    stats = {"species": len(texts), "texts": 2 * len(texts), "flagged": len(flagged),
             "claims": sum(len(MARK.findall(e[lang])) for e in texts.values() for lang in ("es", "en")),
             "errors": len(errs)}
    return errs, stats


def crossing(f: dict, factor: str, up: bool) -> str | None:
    """The tier a factor alone decides: the one it keeps (up) or the one it blocks (down), if any."""
    cf = tier_of(f["rank"] - _places(f, factor))
    if up:
        return f["tier"] if TIERS.index(cf) > TIERS.index(f["tier"]) else None
    return cf if TIERS.index(cf) < TIERS.index(f["tier"]) and qualifies(f, cf, factor) else None


# ------------------------------------------------------------------ what a writer may claim

TRAIT_WORDS = {
    "spd+": ("rápido", "fast"), "spd-": ("lento", "slow"),
    "hp+": ("mucha vida", "lots of HP"), "hp-": ("poca vida", "low HP"),
    "atk+": ("pega fuerte", "hits hard"), "atk-": ("pega poco", "hits soft"),
    "hb+": ("hitbox pequeño", "small hitbox"), "hb-": ("hitbox grande", "big hitbox"),
    "hb--": ("hitbox enorme", "huge hitbox"), "hb0": ("hitbox normal", "normal hitbox"),
    "td+": ("aguanta bien los tipos rivales", "shrugs off enemy types"),
    "td-": ("sufre contra los tipos rivales", "suffers against enemy types"),
    "avg": ("del montón en velocidad, vida y daño", "average speed, HP and damage"),
}
TRAIT_MEANS = {
    "spd+": "speed in the top quarter", "spd-": "speed in the bottom quarter",
    "hp+": "HP in the top quarter", "hp-": "HP in the bottom quarter",
    "atk+": "attack in the top quarter", "atk-": "attack in the bottom quarter",
    "hb+": "body radius below the median (harder to hit)", "hb-": "body radius above the median (easier to hit)",
    "hb--": "body radius in the huge range", "hb0": "body radius exactly the median",
    "td+": "its types take little damage from the enemy pool", "td-": "its types take a lot from the enemy pool",
    "avg": "speed, HP and attack all in the middle half",
}
FACTOR = {
    "speed": ("su velocidad", "its speed"), "hp": ("su vida", "its HP"), "attack": ("su daño", "its damage"),
    "start_move": ("su ataque inicial", "its start move"),
    "stats": ("sus estadísticas", "its stats"), "moves": ("los ataques que aprende", "the moves it learns"),
    "typedef": ("sus tipos", "its types"),
    "gate_stats": ("el tope por estadísticas", "the stats cap"),
    "gate_types": ("tener un solo tipo de ataque", "having a single attack type"),
    "gate_melee": ("empezar cuerpo a cuerpo", "its melee start"),
}
FACTOR_MEANS = {
    "hitbox": "its hitbox size", "speed": "its speed", "hp": "its HP", "attack": "its attack",
    "start_move": "its game start move compared with the other starts it can learn",
    "best_move": "its best move compared with its second best", "stats": "its stats overall",
    "moves": "the moves it can learn", "typedef": "how its types take enemy hits", "late": "how it does in long runs",
    "gate_stats": "a tier cap for low stats", "gate_types": "a tier cap for a single attack type",
    "gate_melee": "a tier cap for a melee start",
}


def factor_words(f: dict, factor: str, up: bool) -> tuple[str, str]:
    if factor == "hitbox":
        return ("su hitbox pequeño", "its small hitbox") if up else ("su hitbox grande", "its big hitbox")
    if factor == "late":
        return (("cómo aguanta las partidas largas", "how it holds up in long runs") if up
                else ("cómo flojea en partidas largas", "how it fades in long runs"))
    if factor == "best_move":
        return f["build"]["best"]["es"], f["build"]["best"]["en"]
    return FACTOR[factor]


def claims(f: dict) -> list[dict]:
    """Every key that holds for this full facts record, what it means and plain wording. A writer may use these
    and nothing else."""
    out = []
    for k, (es, en) in TRAIT_WORDS.items():
        if holds(k, f) is None:
            out.append({"key": k, "means": TRAIT_MEANS[k], "es": es, "en": en})
    b = f["build"]
    named = [("m.start", b["start"], "game start move")] + [("m.group", m, "bonded group move") for m in b["group"]]
    named += [("m.alt", m, "alternative move") for m in b["alts"]]
    named.append(("i.best", b["item"], "best item"))
    if b["cards"]:
        named.append(("c.first", b["cards"][0], "first card to pick"))
    for role, m, means in named:
        out.append({"key": f"{role}:{m['id']}", "means": means, "es": m["es"], "en": m["en"]})
    for head, up in (("up", True), ("down", False)):
        for factor in ranked_drivers(f, up)[:2]:
            es, en = factor_words(f, factor, up)
            places = abs(_places(f, factor))
            verb = "lifts it" if up else "holds it back"
            out.append({"key": f"{head}:{factor}", "means": f"{FACTOR_MEANS[factor]} {verb} (about {places} places)",
                        "es": es, "en": en})
            t = crossing(f, factor, up) if factor != "best_move" else None
            if t:
                means = (f"without it, it would drop out of tier {t}" if up
                         else f"it is what keeps it out of tier {t}")
                es_t = f"sin {es} no estaría en el {t}" if up else f"{es} lo deja fuera del {t}"
                en_t = f"without {en} it would drop out of {t}" if up else f"{en} keeps it out of {t}"
                out.append({"key": f"{head}:{factor}:{t}", "means": means, "es": es_t, "en": en_t})
    for k, es, en, means in (("nodown", "nada lo frena", "nothing holds it back", "no factor holds it back"),
                             ("calm", "ningún factor", "no single factor", "no factor moves it much either way")):
        if holds(k, f) is None:
            out.append({"key": k, "means": means, "es": es, "en": en})
    return out


# ------------------------------------------------------------------ files

def load() -> dict:
    if not PATH.exists():
        return {"species": {}, "flagged": {}}
    doc = json.loads(PATH.read_text(encoding="utf8"))
    doc.setdefault("flagged", {})
    return doc


def public(summaries: dict, lang: str) -> dict:
    """What the ficha loads: dex -> marked text in that language."""
    return {d: e[lang] for d, e in summaries["species"].items()}
