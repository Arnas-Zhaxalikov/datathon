"""
Qamqor AI — правила состава семьи / household composition rules.

RU: Одни и те же правила для введённой человеком семьи: в браузере (agent/web/validate.js),
    на сервере (agent/backend/core.py) и в инструментах ассистента (tools.py). К таблице
    обследования они не применяются: там семьи такие, какие есть в данных.
EN: The same rules for a household entered by a person: in the browser
    (agent/web/validate.js), on the server (agent/backend/core.py) and in the assistant's tools
    (tools.py). They are not applied to the survey table: its households are what the data holds.

    1. Размер семьи ≥ 1.                         Household size is at least 1.
    2. Хотя бы один взрослый: детей ≤ размер − 1. At least one adult: children ≤ size − 1.
    3. Детей + людей 63+ ≤ размер.               Children + people aged 63+ ≤ size.
    4. Детей до 7 лет ≤ детей.                   Children under 7 ≤ children.
    5. Работающих ≤ размер − детей.              Working members ≤ size − children (adults only, 63+ included).
    6. Работающих может быть 0.                  There may be no working members.
"""
from __future__ import annotations

CHILD_AGE = 18

# RU: код нарушения → (поле, текст). EN: violation code → (field, text).
MESSAGES = {
    "size": ("size", "The household must have at least one person."),
    "values": ("size", "Counts cannot be negative."),
    "no_adult": ("n_child", "The household must have at least one adult: children cannot be more than household size minus one."),
    "children_elderly": ("n_elderly", "Children and people aged 63+ together cannot outnumber the household."),
    "child_u7": ("n_child_u7", "Children under 7 cannot outnumber children."),
    "employed": ("n_employed", "Working members cannot outnumber adults (household size minus children)."),
}


class CompositionError(ValueError):
    """RU: невозможный состав семьи. EN: an impossible household composition."""

    def __init__(self, code: str):
        self.code = code
        self.field, self.message = MESSAGES[code]
        super().__init__(f"{self.message} Ask the person to clarify the household composition; do not compute.")


def violations(size: int, n_child: int = 0, n_child_u7: int = 0, n_elderly: int = 0, n_employed: int | None = None) -> list[str]:
    """RU: коды всех нарушенных правил, в порядке правил. EN: codes of every broken rule, in rule order."""
    if size < 1:
        return ["size"]
    if min(n_child, n_child_u7, n_elderly, n_employed or 0) < 0:
        return ["values"]
    out = []
    if n_child > size - 1:
        out.append("no_adult")
    if n_child + n_elderly > size:
        out.append("children_elderly")
    if n_child_u7 > n_child:
        out.append("child_u7")
    if n_employed is not None and n_employed > size - n_child:
        out.append("employed")
    return out


def check(size: int, n_child: int = 0, n_child_u7: int = 0, n_elderly: int = 0, n_employed: int | None = None) -> None:
    """RU: бросает CompositionError при первом нарушении. EN: raises CompositionError on the first violation."""
    bad = violations(int(size), int(n_child), int(n_child_u7), int(n_elderly), None if n_employed is None else int(n_employed))
    if bad:
        raise CompositionError(bad[0])


def check_members(members: list[dict]) -> None:
    """RU: то же для списка членов семьи (инструмент check_household): работают только взрослые.
       EN: the same for a list of members (the check_household tool): only adults work."""
    ages = [float(m.get("age", 0)) for m in members]
    children = [a < CHILD_AGE for a in ages]
    workers = [float(m.get("labor_month") or 0) > 0 for m in members]
    if any(c and w for c, w in zip(children, workers)):
        raise CompositionError("employed")
    check(len(members), sum(children), sum(a < 7 for a in ages), sum(a >= 63 for a in ages), sum(workers))
