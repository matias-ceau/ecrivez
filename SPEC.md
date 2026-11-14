# Ecrivez — la secrétaire (spec courte, v0)

## Intention

Dicter en vrac, ou enregistrer une consultation, et récupérer une observation
ou un compte rendu propre, dans le style et les trames du médecin, sans
formation répétée. Quand le résultat est faux, une phrase de correction suffit
et elle est retenue. Le but est de réduire la charge mentale (TDAH) : si
l'outil demande plus d'attention qu'il n'en économise, c'est un échec.

## Objectifs v0 (pour la consultation de mardi 17 novembre 2026)

- Trame « consultation TCA » remplie à partir d'un enregistrement ou d'une dictée.
- Observation courte à partir d'une phrase en vrac (exemple du diazépam).
- Correction en une commande, mémorisée pour la suite.
- Tout tourne sur l'abonnement Claude existant (Claude Code), sans clé API.

## Hors périmètre v0

- Appli téléphone, web app, interface plein écran, affichage en temps réel pendant la consultation.
- Étiquetage médecin/patient dans la transcription.
- Synchronisation entre desktop et laptop (dossier partagé ou repo privé, au choix plus tard).
- Intégration au logiciel de dossier patient : la sortie est du texte à coller.

## Anti-objectifs

- Inventer un fait clinique. Une rubrique non abordée est écrite « Non abordé ».
- Demander des réglages avant chaque usage.
- Stocker des textes de patients dans ce repo, qui est **public** sur GitHub.

## Utilisation

Une seule chose à retenir : taper `ecrivez`. Un menu à une touche s'affiche :

```
  Ecrivez — trame : TCA

  [c] enregistrer une consultation
  [d] dicter
  [f] fichier audio
  [t] taper du texte
  [m] changer de trame
  [q] quitter
```

Après chaque document, l'outil demande « Une remarque ? ». Une remarque en
français refait le document et est retenue dans le lexique ou les règles ;
Entrée seule valide et ramène au menu.

Les commandes directes (`ecrivez fichier <audio> [trame]`, `ecrivez texte "<phrase>"`)
existent pour les automatismes, sans qu'il faille les connaître.

## Sortie

Un fichier texte brut (`.txt`, sans balisage Markdown) dans `sorties/` du dossier
de données, donc synchronisé. Son chemin est affiché ; le texte est aussi affiché
dans le terminal et copié dans le presse-papiers.

## Le bureau de la secrétaire

Dossier de données privé et synchronisé entre machines, hors du repo public.
Son emplacement se règle par la variable `ECRIVEZ_DATA` (défaut : `~/.local/share/ecrivez/`).
Le repo reste l'espace de travail : code et idée générale.

```
trames/tca.md        trames de documents, une par fichier
exemples/*.md        2-3 documents rédigés par le médecin, servent de modèle de style
lexique.md           termes à reconnaître (craving, diazépam…), corrigés au fil de l'eau
regles.md            consignes de style retenues après un `ecrivez non`
sorties/             par date : document .txt + transcription brute .txt + audio .flac
```

Le repo ne contient que le code et une trame TCA d'exemple vide.

## Chaîne de traitement

1. Enregistrement : `pw-record` (PipeWire), fichier WAV temporaire.
2. Transcription, interchangeable : service en ligne si une clé API est fournie
   (meilleure qualité, découpage automatique des audios longs), sinon `whisper-cli`
   en local (whisper.cpp, `large-v3`). Le lexique sert d'amorce dans les deux cas.
3. Rédaction : `claude -p`, qui reçoit trame, exemples, lexique, règles et
   transcription, corrige les erreurs de transcription d'après le contexte, puis rédige.
4. Sortie : fichier `.txt` dans `sorties/`, terminal et presse-papiers (`wl-copy`).

L'audio est toujours conservé : une consultation ne se refait pas. Il est écrit
directement dans le dossier de données pendant l'enregistrement (rien n'est perdu
en cas de plantage), puis gardé en FLAC à côté du document. Aucune suppression
automatique ; le ménage est manuel.

## Règles de rédaction imposées

- Ne rien ajouter qui ne soit pas dans la source ; « Non abordé » sinon.
- Passage douteux de la transcription : signalé par `[?]` plutôt que deviné.
- Faux noms utilisés en consultation : repris tels quels.

## Approches écartées

- **Projet Claude dans l'appli** : pas de transcription locale ni d'audio long,
  corrections mal retenues. Reste le recours depuis le téléphone.
- **Web app locale** : plus confortable, mais plus longue ; à construire par-dessus v0 si elle sert.

## Choix techniques (les miens)

- Python stdlib, `uv`, branche `dev/secretary`. L'ancien code (REPL, Qt, Gradio,
  smolagents) est retiré ; il reste dans l'historique git.
- `uv.lock` régénéré (il contient des marqueurs de conflit).
- Tests : la chaîne est testée avec transcription et Claude simulés, sans réseau.

## Ce qu'il me faut du médecin

- La trame TCA telle qu'il la remplit (intitulés exacts des rubriques).
- Deux ou trois observations ou comptes rendus anonymisés, écrits par lui.
