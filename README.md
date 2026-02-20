![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# 🔀 Multiplexed Digital Processing Unit

> **A multiplexed digital system with 4 specialized processing units**

🇫🇷 [Version française](README_FR.md)

```mermaid
flowchart TB
    subgraph TT ["TinyTapeout Interface"]
        CTRL["ui_in[7:6]<br/>CTRL"]
        DATA["ui_in[5:0] + uio_in[7:0]<br/>DATA"]
    end
    
    CTRL --> MUX_CTRL["MUX CONTROL"]
    DATA --> DEMUX["DEMULTIPLEXER<br/>4-WAY"]
    
    subgraph MODULES ["4 MODULES"]
        BRENT["➕<br/>BRENT-K<br/>00"]
        HALF["🎵<br/>1.5bit<br/>01"]
        VGA["📺<br/>VGA<br/>10"]
        CAM["📋<br/>CAM<br/>11"]
    end
    
    MUX_CTRL --> DEMUX
    DEMUX --> BRENT
    DEMUX --> HALF
    DEMUX --> VGA
    DEMUX --> CAM
    
    BRENT --> MUX["MULTIPLEXER<br/>4-TO-1"]
    HALF --> MUX
    VGA --> MUX
    CAM --> MUX
    
    MUX --> OUTPUT["uo_out[7:0]"]
```

## 📋 Module Documentation

| Module | Description | Documentation |
|--------|-------------|---------------|
| 🔀 **TOP** | Main controller and multiplexing | [📖 top.md](docs/top.md) |
| ➕ **BRENT-KUNG** | Optimized parallel adder | [📖 brent-kung.md](docs/brent-kung.md) |
| 📺 **VGA** | Video signal generator | [📖 vga.md](docs/vga.md) |
| 🎵 **1HALF** | Sigma-delta audio latch | [📖 1half_latch.md](docs/1half_latch.md) |
| 📋 **CAM** | Content-addressable memory | [📖 cam.md](docs/cam.md) |

## 🎛️ Multiplexing Usage

### Module Selection
```
ui_in[7:6] = CTRL[1:0]
┌─────┬─────────────┬─────────────────────┐
│CTRL │   MODULE    │     FUNCTION        │
├─────┼─────────────┼─────────────────────┤
│ 00  │ ➕ BRENT-K  │ Adder               │
│ 01  │ 🎵 1HALF    │ Audio latch         │
│ 10  │ 📺 VGA      │ Video generator     │
│ 11  │ 📋 CAM      │ Associative memory  │
└─────┴─────────────┴─────────────────────┘
```

### Data Routing
```mermaid
flowchart LR
    subgraph INPUTS
        UI["ui_in[5:0]"]
        UIO["uio_in[7:0]"]
        CLK["clk, rst_n"]
    end
    
    subgraph MULTIPLEXING
        DEMUX_BLOCK["DEMUX 4:1"]
        ACTIVE["ACTIVE MODULE"]
        MUX_BLOCK["MUX 4:1"]
    end
    
    subgraph OUTPUTS
        OUT["uo_out[7:0]"]
    end
    
    UI --> DEMUX_BLOCK
    UIO --> DEMUX_BLOCK
    CLK --> ACTIVE
    DEMUX_BLOCK --> ACTIVE
    ACTIVE --> MUX_BLOCK
    MUX_BLOCK --> OUT
```

## 🔌 Pin Usage

- **`ui_in[7:6]`** : Module selection  
  (00=BRENT, 01=1HALF, 10=VGA, 11=CAM)
- **`ui_in[5:0]` + `uio_in[7:0]`** : Data inputs  
  (14 bits available for modules)
- **`uo_out[7:0]`** : Results from active module

See individual module documentation for specific pin assignments.


## 🏗️ Project Architecture

```
📁 src/
├── 🔧 config.json      # TinyTapeout configuration
├── 🔀 top.v           # Main module + MUX/DEMUX
├── 🔄 mux.v           # Multiplexing utilities
├── ➕ brent-kung.v    # Brent-Kung adder
├── 🎵 1half_latch.v   # Sigma-delta 1.5bit latch
├── 📺 vga.v           # VGA generator + H/V sync
└── 📋 cam.v           # Content-Addressable Memory

📁 docs/
├── 📖 top.md          # Main module documentation
├── 📖 brent-kung.md   # Adder documentation
├── 📖 vga.md          # VGA documentation
├── 📖 1half_latch.md  # Audio latch documentation
└── 📖 cam.md          # CAM memory documentation
```

## 🎯 Applications

- **🎵 Audio** : Class D amplifier with sigma-delta modulator
- **📺 Video** : VGA pattern generator for testing and display  
- **🧮 Computing** : Fast arithmetic for signal processing
- **💾 Memory** : Associative cache and lookup tables

