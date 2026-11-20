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

« Envoyer par mail » passe la note à la commande `ECRIVEZ_MAIL_COMMAND` (défaut
`send_email.py`), appelée avec `-s <objet> -c <note>` ; l'objet ne contient que la date.

Le Python fourni par `uv` a un Tk sans polices modernes : installer avec celui du système,
`uv tool install --python /usr/bin/python3 -e .` (paquet `tk`).

## Téléphone (`ecrivez-web`)

Une page web privée, installable sur l'écran d'accueil du téléphone : enregistrer (l'audio
part à la maison toutes les cinq secondes et reste dans le téléphone tant qu'il n'est pas
confirmé), ou envoyer un fichier du dictaphone ; puis transcription, note, copie, mail.
Le serveur n'écoute que sur `127.0.0.1` et exige un code d'accès (créé au premier
lancement dans `$ECRIVEZ_DATA/web-code`, saisi une fois par appareil). On l'expose par un
relais HTTPS qui ne déchiffre pas en route :

```
ecrivez-web --port 8377
tailscale serve  --bg --https=8443 http://127.0.0.1:8377   # réseau Tailscale seulement
tailscale funnel --bg --https=8443 http://127.0.0.1:8377   # ou : adresse publique
```

Avec `ecrivez-web --auto`, la note est rédigée puis envoyée par mail dès que la séance
est finie, sans rien toucher (adresse : celle de la commande de mail, ou
`ECRIVEZ_MAIL_TO`). La page se rouvre et enregistre même quand la maison est injoignable :
l'audio reste dans le téléphone et part à la prochaine ouverture de la page avec du réseau.

Détails et cas limites : [spec](docs/superpowers/specs/2026-11-19-mobile.md).

## Dossier de données

Privé, hors de ce repo : `$ECRIVEZ_DATA`, par défaut `~/.local/share/ecrivez/`.

| Élément | Rôle |
|---|---|
| `trames/*.md` | Trames de documents (une par fichier) ; `tca` et `psy` fournies |
| `exemples/*.md` | Documents déjà rédigés, modèles de style |
| `lexique.md` | Termes à reconnaître dans la transcription |
| `regles.md` | Consignes de style retenues |
| `sorties/` | Par date : `note.txt`, `source.txt`, `audio.flac` (`audio.webm` depuis un navigateur), `transcription.txt` |

## Prérequis

`claude` (Claude Code, connecté à un abonnement), `ffmpeg`, `pw-record` (PipeWire), `wl-copy`.

## Transcription

- En ligne dès que `OPENROUTER_API_KEY` est définie (à défaut, `OPENAI_API_KEY` avec
  `OPENAI_BASE_URL`) : l'audio est envoyé par tranches de 10 minutes, modèle
  `ECRIVEZ_AUDIO_MODEL` (défaut `google/gemini-4-hydrogen`).
- Sinon, ou avec `ECRIVEZ_TRANSCRIBER=local` : commande `whisper` (openai-whisper),
  modèle `ECRIVEZ_WHISPER_MODEL` (défaut `large-v3-turbo`).

## Rédaction

Par `claude -p` (abonnement). Si `ECRIVEZ_DRAFT_MODEL` est définie (par exemple
`anthropic/claude-opus-5.5`), la note est rédigée par ce modèle via le même compte en
ligne que la transcription : utile là où `claude` ne s'installe pas.

Voir [SPEC.md](SPEC.md).
