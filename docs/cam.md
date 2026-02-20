[🏠 Back to Main](../README.md)

# 📋 CAM - Content-Addressable Memory

> **16x8 bit associative memory - search by content, not address**

🇫🇷 [Version française](cam_FR.md)

## 🎯 What is CAM?

Unlike normal RAM where you give an address to get data, CAM works backwards:  
you give it data and it tells you the address where it's stored.  
All 16 entries are searched simultaneously in 1 clock cycle.

## 🔌 Pins

### Selection: `ui_in[7:6] = 11`

```
┌─────────────────┬─────────┬─────────────────────┐
│      PIN        │   DIR   │      FUNCTION       │
├─────────────────┼─────────┼─────────────────────┤
│ ui_in[5]       │   IN    │ WRITE (1=write)     │
│ ui_in[4:0]     │   IN    │ ADDRESS[4:0]        │
│ uio_in[7:0]    │   IN    │ DATA[7:0]           │
│ uo_out[5]      │   OUT   │ FOUND               │
│ uo_out[4:0]    │   OUT   │ MATCH_ADDR[4:0]     │
│ uo_out[7:6]    │   OUT   │ Always 00           │
└─────────────────┴─────────┴─────────────────────┘
```

## 🔄 Operations

### Write Mode
```
ui_in[5] = 1 (WRITE)
ui_in[4:0] = address where to store
uio_in[7:0] = data to store
```

### Search Mode
```
ui_in[5] = 0 (SEARCH)
uio_in[7:0] = data to find
→ uo_out[5] = 1 if found
→ uo_out[4:0] = address where found
```

## 🏗️ Real-World Examples

### Network Router
```
Packet arrives → Extract MAC address → CAM lookup → Get output port
   📦              AA:BB:CC:DD:EE:FF      Found at 3        Port 3
```

### CPU Cache
```
CPU needs data → Check address tag → CAM lookup → Cache hit/miss
     🖥️              0x1000ABC         Found at 7      Cache HIT
```

### Translation Table
```
Virtual address → CAM search → Physical address
    0x4000           Found          0x2000ABC
```

## ⚡ Why CAM is Fast

**Normal RAM**: Address → Data (1 step)
**CAM**: Data → Address (1 step, but searches ALL entries in parallel)

Perfect for:
- **Routing tables** (network switches)
- **Cache tags** (CPU caches) 
- **Translation** (virtual to physical addresses)
- **Pattern matching** (security/firewall rules)

## 📂 Source
- File: `src/cam.v:1-75`

---
[🏠 Back to Main](../README.md)