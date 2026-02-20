[🏠 Back to Main](../README.md)

# 🎵 1HALF - Sigma-Delta Audio Latch

> **1.5-bit latch for Class-D audio amplifiers - prevents transistor shoot-through**

🇫🇷 [Version française](1half_latch_FR.md)

## 🎯 What is Sigma-Delta?

Sigma-Delta modulation converts analog audio signals into high-frequency digital pulses. The "1.5-bit" means 3 possible output states instead of normal 2-bit (4 states).

## 🔌 Pins

### Selection: `ui_in[7:6] = 01`

```
┌─────────────────┬─────────┬─────────────────────┐
│      PIN        │   DIR   │      FUNCTION       │
├─────────────────┼─────────┼─────────────────────┤
│ ui_in[3:0]     │   IN    │ in_p[3:0]           │
│ uio_in[3:0]    │   IN    │ in_n[3:0]           │
│ uo_out[7:0]    │   OUT   │ 4x {out_p, out_n}   │
└─────────────────┴─────────┴─────────────────────┘
```

## ⚠️ Safety Logic

Prevents forbidden state `11` (both transistors ON = short circuit):
- `00` = Both OFF (no output) ✅
- `01` = N-transistor ON (+V output) ✅  
- `10` = P-transistor ON (-V output) ✅
- `11` = Both ON (SHORT CIRCUIT) ❌ **BLOCKED**

## 🎵 Real-World Example

**Class-D Audio Amplifier:**
```
Audio Signal → Sigma-Delta → 1.5bit Latch → Power Stage → Speaker
   ∿              101010        Safe PWM       High Power    🔊
```

1. **Input**: Audio from microphone/DAC
2. **Modulation**: Convert to high-freq pulses (MHz)
3. **Safety**: This latch prevents power transistor damage
4. **Output**: Safe PWM to drive speaker coils
5. **Filter**: Low-pass filter recovers audio

## 🔄 Operation

4 independent channels for:
- **Stereo audio** (2 channels)
- **Multi-channel** (4 mono channels)
- **Redundancy** (backup channels)

## 📂 Source
- File: `src/1half_latch.v:23-43`

---
[🏠 Back to Main](../README.md)