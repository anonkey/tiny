[🏠 Retour à l'Accueil](../README_FR.md)

# 🎵 1HALF - Latch Audio Sigma-Delta

> **Latch 1.5-bit pour amplificateurs audio classe-D - évite les court-circuits**

🇺🇸 [English version](1half_latch.md)

## 🎯 Qu'est-ce que Sigma-Delta ?

La modulation Sigma-Delta convertit les signaux audio analogiques en impulsions numériques haute fréquence. Le "1.5-bit" signifie 3 états de sortie possibles au lieu de 4 états normaux (2-bit).

## 🔌 Broches

### Sélection: `ui_in[7:6] = 01`

```
┌─────────────────┬─────────┬─────────────────────┐
│     BROCHE      │   DIR   │      FONCTION       │
├─────────────────┼─────────┼─────────────────────┤
│ ui_in[3:0]     │   IN    │ in_p[3:0]           │
│ uio_in[3:0]    │   IN    │ in_n[3:0]           │
│ uo_out[7:0]    │   OUT   │ 4x {out_p, out_n}   │
└─────────────────┴─────────┴─────────────────────┘
```

## ⚠️ Logique de Sécurité

Empêche l'état interdit `11` (les deux transistors ON = court-circuit):
- `00` = Les deux OFF (pas de sortie) ✅
- `01` = Transistor N ON (sortie +V) ✅  
- `10` = Transistor P ON (sortie -V) ✅
- `11` = Les deux ON (COURT-CIRCUIT) ❌ **BLOQUÉ**

## 🎵 Exemple Concret

**Amplificateur Audio Classe-D :**
```
Signal Audio → Sigma-Delta → Latch 1.5bit → Étage Puissance → Haut-parleur
     ∿             101010        PWM Sûr       Haute Puissance      🔊
```

1. **Entrée** : Audio du microphone/DAC
2. **Modulation** : Conversion en impulsions haute fréq (MHz)
3. **Sécurité** : Ce latch évite d'endommager les transistors de puissance
4. **Sortie** : PWM sûr pour commander les bobines du haut-parleur
5. **Filtrage** : Filtre passe-bas récupère l'audio

## 🔄 Fonctionnement

4 canaux indépendants pour :
- **Audio stéréo** (2 canaux)
- **Multi-canal** (4 canaux mono)
- **Redondance** (canaux de sauvegarde)

## 📂 Source
- Fichier: `src/1half_latch.v:23-43`

---
[🏠 Retour à l'Accueil](../README_FR.md)