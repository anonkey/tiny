[🏠 Retour à l'Accueil](../README_FR.md)

# 📋 CAM - Mémoire Associative

> **Mémoire associative 16x8 bit - recherche par contenu, pas par adresse**

🇺🇸 [English version](cam.md)

## 🎯 Qu'est-ce qu'une CAM ?

Contrairement à la RAM normale où on donne une adresse pour obtenir des données, la CAM fonctionne à l'inverse : on lui donne des données et elle nous dit l'adresse où elles sont stockées. Les 16 entrées sont recherchées simultanément en 1 cycle d'horloge.

## 🔌 Broches

### Sélection: `ui_in[7:6] = 11`

```
┌─────────────────┬─────────┬─────────────────────┐
│     BROCHE      │   DIR   │      FONCTION       │
├─────────────────┼─────────┼─────────────────────┤
│ ui_in[5]       │   IN    │ WRITE (1=écriture)  │
│ ui_in[4:0]     │   IN    │ ADRESSE[4:0]        │
│ uio_in[7:0]    │   IN    │ DONNÉES[7:0]        │
│ uo_out[5]      │   OUT   │ TROUVÉ              │
│ uo_out[4:0]    │   OUT   │ ADDR_TROUVÉE[4:0]   │
│ uo_out[7:6]    │   OUT   │ Toujours 00         │
└─────────────────┴─────────┴─────────────────────┘
```

## 🔄 Opérations

### Mode Écriture
```
ui_in[5] = 1 (ÉCRITURE)
ui_in[4:0] = adresse où stocker
uio_in[7:0] = données à stocker
```

### Mode Recherche
```
ui_in[5] = 0 (RECHERCHE)
uio_in[7:0] = données à chercher
→ uo_out[5] = 1 si trouvé
→ uo_out[4:0] = adresse où trouvé
```

## 🏗️ Exemples Concrets

### Routeur Réseau
```
Paquet arrive → Extrait adresse MAC → Recherche CAM → Obtient port sortie
     📦            AA:BB:CC:DD:EE:FF       Trouvé en 3          Port 3
```

### Cache CPU
```
CPU veut données → Vérifie tag adresse → Recherche CAM → Cache hit/miss
       🖥️               0x1000ABC          Trouvé en 7       Cache HIT
```

### Table de Traduction
```
Adresse virtuelle → Recherche CAM → Adresse physique
     0x4000             Trouvé         0x2000ABC
```

## ⚡ Pourquoi la CAM est Rapide

**RAM normale** : Adresse → Données (1 étape)
**CAM** : Données → Adresse (1 étape, mais recherche TOUTES les entrées en parallèle)

Parfait pour :
- **Tables de routage** (commutateurs réseau)
- **Tags de cache** (caches CPU)
- **Traduction** (adresses virtuelles vers physiques)
- **Correspondance de motifs** (règles sécurité/firewall)

## 📂 Source
- Fichier: `src/cam.v:1-75`

---
[🏠 Retour à l'Accueil](../README_FR.md)