"""Drafting and revising notes through Claude Code (`claude -p`)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass

from ecrivez.desk import Desk, SavedNote

MEMORY_MARK = "===MEMOIRE==="

Run = Callable[[list[str], str | None], str]


class ToolError(Exception):
    def __init__(self, program: str, detail: str) -> None:
        super().__init__(f"{program} : {detail}")
        self.program = program
        self.detail = detail


@dataclass(frozen=True)
class Revision:
    note: str
    lexicon: list[str]
    rules: list[str]


def run_tool(argv: list[str], stdin: str | None = None) -> str:
    try:
        done = subprocess.run(argv, input=stdin, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise ToolError(argv[0], "programme introuvable") from None
    if done.returncode != 0:
        lines = (done.stderr or done.stdout).strip().splitlines()
        raise ToolError(argv[0], lines[-1] if lines else f"échec (code {done.returncode})")
    return done.stdout


BASE = """\
Tu es la secrétaire médicale d'un psychiatre hospitalier. Il te confie une source \
(dictée en vrac, notes tapées, ou transcription automatique brute d'une consultation) \
et tu rends le document médical propre qu'il collera dans le dossier du patient.

Règles impératives :
- La source peut contenir des erreurs de reconnaissance vocale. Corrige-les d'après le \
contexte médical et le lexique (exemple : « craie vin » pour « craving »).
- N'ajoute aucun fait, aucune interprétation clinique, aucune posologie absents de la source.
- Une rubrique de la trame que la source n'aborde pas reçoit exactement : Non abordé
- Si aucune rubrique d'une section de la trame n'est abordée, écris Non abordé une seule fois \
sous l'intitulé de la section, sans détailler ses rubriques.
- Les parenthèses de la trame sont un aide-mémoire de ce qu'il faut y chercher : ne les \
recopie pas et ne signale pas un par un les éléments absents.
- Un passage douteux ou inaudible que le contexte ne permet pas de trancher est signalé par [?] \
plutôt que deviné.
- Les noms de personnes sont repris tels que prononcés.
- Dans une transcription, les lettres en début de ligne (A, B, C…) désignent les voix de \
l'enregistrement. Déduis du contenu qui est le médecin. Une autre lettre peut être un tiers \
(appel téléphonique, accompagnant). Ce qui concerne un autre patient est ignoré.
- Les propos familiers du médecin sont reformulés en langage médical ; ses raisonnements \
cliniques sont conservés.
- Texte brut uniquement : pas de Markdown, pas de dièses, pas d'astérisques, pas de tableaux.
- Réponds uniquement par le document, sans introduction ni commentaire.
"""

WITH_TEMPLATE = (
    "Remplis la trame ci-dessous en conservant ses intitulés, dans l'ordre.\n\n=== TRAME ===\n{}\n"
)
FREE = "Aucune trame : rédige une observation courte, datée implicitement du jour (« Vue ce jour. »).\n"

REVISION = f"""\
Le médecin a relu ton document et te fait une remarque. Rends le document corrigé en entier.
Puis, sur une ligne seule, écris {MEMORY_MARK} et, en dessous, ce qu'il faut retenir pour \
toutes les fois suivantes, une entrée par ligne :
lexique: <terme correctement orthographié>   (mot mal transcrit)
regle: <consigne en une phrase>   (préférence de style ou de contenu durable)
N'écris aucune entrée si la remarque ne vaut que pour ce document.
"""


def _system(desk: Desk, template: str | None, revising: bool = False) -> str:
    parts = [BASE]
    parts.append(WITH_TEMPLATE.format(desk.template(template).strip()) if template else FREE)
    if rules := desk.rules().strip():
        parts.append(f"=== CONSIGNES DU MÉDECIN ===\n{rules}\n")
    if lexicon := desk.lexicon().strip():
        parts.append(f"=== LEXIQUE ===\n{lexicon}\n")
    for i, example in enumerate(desk.examples(), 1):
        parts.append(f"=== EXEMPLE DE SON STYLE {i} ===\n{example.strip()}\n")
    if revising:
        parts.append(REVISION)
    return "\n".join(parts)


def _claude(system: str, content: str, run: Run) -> str:
    argv = ["claude", "-p", "--safe-mode", "--no-session-persistence"]
    argv += ["--tools", "", "--system-prompt", system]
    return run(argv, content)


def draft(desk: Desk, source: str, template: str | None, run: Run = run_tool) -> str:
    return _claude(_system(desk, template), source, run).strip()


def parse_revision(text: str) -> Revision:
    note, _, memory = text.partition(MEMORY_MARK)
    lexicon: list[str] = []
    rules: list[str] = []
    for line in memory.splitlines():
        key, _, value = line.partition(":")
        value = value.strip()
        if not value:
            continue
        if key.strip().lower() == "lexique":
            lexicon.append(value)
        elif key.strip().lower() in ("regle", "règle"):
            rules.append(value)
    return Revision(note.strip(), lexicon, rules)


def revise(desk: Desk, last: SavedNote, remark: str, run: Run = run_tool) -> Revision:
    content = (
        f"=== SOURCE ===\n{last.source}\n\n=== TON DOCUMENT ===\n{last.note}\n\n"
        f"=== REMARQUE DU MÉDECIN ===\n{remark}\n"
    )
    return parse_revision(_claude(_system(desk, last.template, revising=True), content, run))
