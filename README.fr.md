# clientsim

**Testez votre assistant IA contre des centaines de faux clients — avant que les vrais ne le fassent.**

[English](README.md) · licence MIT · créé par [JustiLoi](https://www.justiloi.com)

Vous avez écrit les consignes de votre assistant WhatsApp, Messenger ou du chat de votre site, vous l'avez essayé
trois fois, tout semblait bien, vous l'avez mis en service. Puis un vrai client a écrit… et rien n'est revenu.
Ou l'assistant a inventé un prix. Ou il a promis un rappel sans prévenir personne.

`clientsim` invente des clients réalistes (pressés, méfiants, bavards, avec des fautes, en créole ou en anglais, qui
négocient, qui veulent parler à quelqu'un, qui répondent STOP), les fait discuter avec votre assistant, puis un
correcteur note chaque conversation selon **vos** règles et dit précisément quoi corriger.

## L'histoire

Nous utilisons un assistant WhatsApp pour notre petite société en Guadeloupe. Le jour du lancement, le premier vrai
prospect venu d'une publicité a écrit *« Bonjour, je veux essayer l'assistant »*… et n'a **rien reçu**. Aucune erreur
nulle part.

Nous avons écrit `clientsim` l'après-midi même. Sur les 5 premiers faux clients, l'assistant est resté muet
**3 fois**. La cause : la « réflexion » du modèle compte dans la limite `max_tokens` ; avec 400, elle consommait
parfois tout avant d'écrire un seul mot. Corrigé en une ligne. Puis 120 conversations simulées ont montré la suite :
annoncer « la gérante vous rappelle » sans la prévenir, poser trois questions à la fois, répondre en français à des
clients qui écrivent en créole.

Mêmes 8 clients, même assistant, avant et après la correction :

| Réglage | Note moyenne | Clients restés sans réponse |
|---|---|---|
| `max_tokens: 400` | **3,0 / 10** | **4 sur 8** |
| `max_tokens: 4000`, `effort: low` | **7,6 / 10** | 0 |

## Démarrer

```bash
pip install git+https://github.com/MarieA-911/clientsim
export ANTHROPIC_API_KEY=sk-ant-...
clientsim init          # crée clientsim.yaml et bot_prompt.md
# décrivez votre commerce dans clientsim.yaml, collez les consignes de votre assistant dans bot_prompt.md
clientsim run -n 30 --budget 3
```

Ouvrez `runs/<date>/report.html` : note moyenne, répartition, fautes les plus fréquentes, règles à ajouter à votre
assistant, et les pires conversations en entier avec, pour chacune, la réponse qu'il aurait fallu donner.

Commencez par l'exemple [`examples/bakery-fr`](examples/bakery-fr) : une boulangerie (fictive) du Gosier, avec des
clients qui écrivent en créole.

## Brancher votre assistant

Trois façons (`target` dans `clientsim.yaml`) : des consignes Claude (`kind: anthropic`), une adresse web
(`kind: http`, qui reçoit `{"messages": [...]}` et renvoie `{"reply": "...", "handoff": false}`), ou une fonction
Python (`kind: python`). Voir le [README anglais](README.md#plug-in-your-bot) pour le détail.

## Commandes

| Commande | Effet |
|---|---|
| `clientsim run` | invente les clients, fait les conversations, les note, écrit le rapport |
| `clientsim run -o runs/x` | reprend une série interrompue (rien n'est refait) |
| `clientsim replay runs/x --worst 10` | après une correction, rejoue les 10 pires clients et compare |
| `clientsim rejudge runs/x` | renote les conversations (après avoir changé les règles) |
| `clientsim report runs/x` | refait le rapport |

## Coût

Chaque série a un plafond de dépense (`budget_usd` ou `--budget`). Compter 3 à 10 centimes de dollar par
conversation ; 50 conversations ≈ 3 $.

## Créé par JustiLoi

`clientsim` est développé par [JustiLoi](https://www.justiloi.com), petite société de Guadeloupe qui installe des
assistants WhatsApp pour les commerces, artisans et indépendants des Outre-mer et de toute la France — testés avec
cet outil avant de parler au moindre vrai client.
Un assistant pour votre commerce ? → [justiloi.com/assistant-whatsapp](https://www.justiloi.com/assistant-whatsapp)
