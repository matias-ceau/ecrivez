# Ecrivez

Une secrétaire médicale dans le terminal : on dicte en vrac, ou on enregistre
une consultation, et on récupère une observation ou un compte rendu propre,
selon ses propres trames. Une remarque suffit pour corriger, et elle est retenue.

```
uv tool install -e .
ecrivez
```

Un menu à une touche s'affiche : enregistrer une consultation, dicter, partir
d'un fichier audio ou d'un texte tapé. Le document sort en fichier texte dans le
dossier de données, et dans le presse-papiers.

## Dossier de données

Privé, hors de ce repo : `$ECRIVEZ_DATA`, par défaut `~/.local/share/ecrivez/`.

| Élément | Rôle |
|---|---|
| `trames/*.md` | Trames de documents (une par fichier) |
| `exemples/*.md` | Documents déjà rédigés, modèles de style |
| `lexique.md` | Termes à reconnaître dans la transcription |
| `regles.md` | Consignes de style retenues |
| `sorties/` | Par date : `note.txt`, `source.txt`, `audio.flac` |

## Prérequis

`claude` (Claude Code, connecté à un abonnement), `whisper-cli` (whisper.cpp),
`ffmpeg`, `pw-record` (PipeWire), `wl-copy`.

Le modèle Whisper se règle par `ECRIVEZ_WHISPER_MODEL`.

Voir [SPEC.md](SPEC.md).
