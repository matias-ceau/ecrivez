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

## Fenêtre (`ecrivez-gui`)

Un bouton pour enregistrer une consultation. L'audio est écrit par tranches de deux
minutes, chacune transcrite dès qu'elle est close : le texte apparaît pendant la
consultation. Si l'ordinateur s'arrête, on perd au plus quelques secondes ; la séance
interrompue est reprise (transcription puis assemblage) au lancement suivant. Une panne
de réseau ne coupe pas l'enregistrement, la transcription réessaie seule.

## Dossier de données

Privé, hors de ce repo : `$ECRIVEZ_DATA`, par défaut `~/.local/share/ecrivez/`.

| Élément | Rôle |
|---|---|
| `trames/*.md` | Trames de documents (une par fichier) ; `tca` et `psy` fournies |
| `exemples/*.md` | Documents déjà rédigés, modèles de style |
| `lexique.md` | Termes à reconnaître dans la transcription |
| `regles.md` | Consignes de style retenues |
| `sorties/` | Par date : `note.txt`, `source.txt`, `audio.flac`, `transcription.txt` (fenêtre) |

## Prérequis

`claude` (Claude Code, connecté à un abonnement), `ffmpeg`, `pw-record` (PipeWire), `wl-copy`.

## Transcription

- En ligne dès que `OPENROUTER_API_KEY` est définie (à défaut, `OPENAI_API_KEY` avec
  `OPENAI_BASE_URL`) : l'audio est envoyé par tranches de 10 minutes, modèle
  `ECRIVEZ_AUDIO_MODEL` (défaut `google/gemini-4-hydrogen`).
- Sinon, ou avec `ECRIVEZ_TRANSCRIBER=local` : commande `whisper` (openai-whisper),
  modèle `ECRIVEZ_WHISPER_MODEL` (défaut `large-v3-turbo`).

Voir [SPEC.md](SPEC.md).
