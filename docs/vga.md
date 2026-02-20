[🏠 Back to Main](../README.md)

# 📺 VGA - Video Signal Generator

> **640x480 VGA with animated pattern - generates classic analog video signals**

🇫🇷 [Version française](vga_FR.md)

## 🎯 What is VGA?

VGA (Video Graphics Array) is an analog video standard that uses separate sync signals  
to tell monitors when to start new lines (HSYNC) and new frames (VSYNC).  
This implementation generates a 640x480 @ 60Hz signal with animated colored patterns.

## 🔌 Pins

### Selection: `ui_in[7:6] = 10`

```
┌─────────────────┬─────────┬─────────────────────┐
│      PIN        │   DIR   │      FUNCTION       │
├─────────────────┼─────────┼─────────────────────┤
│ uo_out[7]      │   OUT   │ HSYNC               │
│ uo_out[6]      │   OUT   │ BLUE[1]             │
│ uo_out[5]      │   OUT   │ GREEN[1]            │
│ uo_out[4]      │   OUT   │ RED[1]              │
│ uo_out[3]      │   OUT   │ VSYNC               │
│ uo_out[2]      │   OUT   │ BLUE[0]             │
│ uo_out[1]      │   OUT   │ GREEN[0]            │
│ uo_out[0]      │   OUT   │ RED[0]              │
└─────────────────┴─────────┴─────────────────────┘
```

## 🖼️ VGA Timing

![VGA Timing Diagram](vga.png)

### Signal Generation
- **HSYNC**: Horizontal sync (line start signal)
- **VSYNC**: Vertical sync (frame start signal)  
- **RGB**: 2-bit per color (4 levels each = 64 total colors)

### Timing Parameters
```
Horizontal: 640 pixels + 16 front + 96 sync + 48 back = 800 total
Vertical:   480 lines  + 10 front + 2 sync  + 33 back = 525 total  
Frequency:  25.175 MHz pixel clock → 60Hz refresh rate
```

## 🎨 Pattern Generation

**Moving Colored Bars:**
- Horizontal bars that shift right each frame
- Colors based on pixel position and frame counter
- Pattern: `moving_x = pix_x + frame_counter`

**Color Logic:**
```
R = {moving_x[5], pix_y[2]}  // Red varies horizontally + vertically
G = {moving_x[6], pix_y[2]}  // Green different horizontal pattern  
B = {moving_x[7], pix_y[5]}  // Blue slower horizontal + vertical
```

## 📱 Output

- **Resolution**: 640x480 @ 60Hz
- **Colors**: 2-bit RGB (64 colors)
- **Pattern**: Animated horizontal bars
- **Autonomous**: No input required

## 📂 Source
- File: `src/vga.v:8-126`

---
[🏠 Back to Main](../README.md)