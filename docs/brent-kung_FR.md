[🏠 Retour à l'Accueil](../README_FR.md)

# ➕ BRENT-KUNG - Additionneur 4-bit

> **Additionneur parallèle ultra-rapide**

🇺🇸 [English version](brent-kung.md)

## 🔌 Connexions

### Sélection: `ui_in[7:6] = 00`

```
┌─────────────────┬─────────┬─────────────────────┐
│      PIN        │   DIR   │      FONCTION       │
├─────────────────┼─────────┼─────────────────────┤
│ ui_in[3:0]     │   IN    │ 🅰️ Nombre A (4-bit) │
│ uio_in[3:0]    │   IN    │ 🅱️ Nombre B (4-bit) │
│ uio_in[7]      │   IN    │ ➕ Retenue entrée   │
│ uo_out[4:0]    │   OUT   │ 📊 Somme (5-bit)    │
│ uo_out[7:5]    │   OUT   │ 🚫 Toujours 000     │
└─────────────────┴─────────┴─────────────────────┘
```

## 📊 Exemples

### Addition simple
```
🅰️ = 1010 (10)  →  ui_in[3:0]  = 1010
🅱️ = 0110 (6)   →  uio_in[3:0] = 0110  
➕ = 0         →  uio_in[7]   = 0
                 uo_out[4:0] = 10000 (16)
```

### Avec retenue
```
🅰️ = 1111 (15) →  ui_in[3:0]  = 1111
🅱️ = 0001 (1)  →  uio_in[3:0] = 0001
➕ = 1         →  uio_in[7]   = 1
                 uo_out[4:0] = 10001 (17)
```


## 🏗️ Fonctionnement

### Implémentation Complète 4-bit
Circuit complet montrant tous les composants et étapes :

![Implémentation 4-bit](brent4.png)

*Circuit complet de l'additionneur Brent-Kung 4-bit avec toutes les étapes et interconnexions*

### Structure Arborescente de l'Algorithme
Détail du composant step0_4 utilisé dans le circuit ci-dessus :

![Étapes Algorithme Brent-Kung](step0_4.png)

*Structure arborescente à 4 étapes montrant la logique centrale de l'algorithme*

## 📂 Source
- Fichier: `src/brent-kung.v:38-85`

---
[🏠 Retour à l'Accueil](../README_FR.md)