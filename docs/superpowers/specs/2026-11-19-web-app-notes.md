# Application web privée : notes de cadrage (discussion en cours, rien de décidé)

Reprise de la discussion du 2026-11-19. Ce n'est pas encore une spec : il reste
une question ouverte, puis le choix d'une approche.

## Les trois situations décrites par le médecin

1. **Téléphone seul** : il enregistre la consultation et peut y joindre une photo
   ou un texte copié depuis le logiciel de l'hôpital (texte numérique, pas d'OCR).
2. **Ordinateur personnel** : la chaîne actuelle convient ; il manque un moyen
   simple de faire arriver la note sur le poste du travail (e-mail, ou mieux).
3. **Poste du travail seul** (téléphone déchargé) : une application web privée.
   Il dispose d'un domaine, d'un serveur à domicile et d'un nginx sur un VPS
   DigitalOcean qui renvoie les sous-domaines vers la maison par Tailscale.

## Proposition faite (pas encore validée)

Une seule application web privée pour les trois cas, hébergée sur le serveur à
domicile, avec ecrivez derrière :

- depuis le téléphone : envoi de l'audio, d'une photo ou d'un texte collé ;
- depuis le poste du travail : lecture de la note et bouton « copier », ce qui
  remplace l'e-mail du cas 2 ;
- sur Arch : la même page dans le navigateur ; le menu du terminal reste.

## Contraintes repérées

- Un navigateur de téléphone coupe souvent le micro quand l'écran se verrouille :
  pour 30 minutes, enregistrer avec le dictaphone du téléphone puis envoyer le
  fichier.
- Les données patients passent par le VPS : si nginx y déchiffre le trafic, elles
  y circulent en clair. À traiter dans la conception (chiffrement jusqu'à la
  maison, accès protégé).
- `claude -p` et la clé OpenRouter doivent être disponibles sur le serveur à
  domicile.
- Le dépôt est public : aucune donnée patient, aucun nom de domaine privé dedans.

## Question ouverte

Dans le cas 3, qu'est-ce qui capte le son de la consultation : le micro du poste
du travail par le navigateur (si l'hôpital l'autorise), le futur enregistreur
ESP32, ou pas d'audio du tout (seulement des notes tapées) ?

## À préciser ensuite

- Ce que « photo » recouvre (photo d'écran à lire, ou simple pièce jointe).
- Comment on s'identifie sur la page.
- Séparation des locuteurs : faite, voir `2026-11-17-speakers.md`.
