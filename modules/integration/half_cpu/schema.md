# Half CPU — Detailed Architecture Schema

> **Multi-cycle CPU with external memory over SPI (nvSRAM-compatible)**

## Top-Level Block Diagram

```
                            i_clk ────────────────────────────────────────────────────────────┐
                            i_rst_n ──────────────────────────────────────────────────────────┤
                                                                                              │
  ┌───────────────────────────────────────────────────────────────────────────────────────────┤───────┐
  │ half_cpu                                                                                  │       │
  │                                                                                           │       │
  │  ┌──────────────────────────────────── DATAPATH ──────────────────────────────────────┐   │       │
  │  │                                                                                    │   │       │
  │  │                        w_read_data[15:0]                                           │   │       │
  │  │                   ┌───────────────────────────────────────────┐                     │   │       │
  │  │                   │                                           │                     │   │       │
  │  │                   ▼                                           │                     │   │       │
  │  │          ┌─────────────────┐                                  │                     │   │       │
  │  │          │   instr_reg     │                                  │                     │   │       │
  │  │          │  register #16   │ ◀── w_fsm_instr_en              │                     │   │       │
  │  │          └────────┬────────┘                                  │                     │   │       │
  │  │                   │ w_instr[15:0]                             │                     │   │       │
  │  │          ┌────────┴────────┐                                  │                     │   │       │
  │  │          │    w_opcode     │ = w_instr[15:12]                 │                     │   │       │
  │  │          │  ┌──┬──┬──┐    │                                   │                     │   │       │
  │  │          │  │LD│ST│BQ│    │ (opcode decode: 1101/1110/1100)   │                     │   │       │
  │  │          │  └──┴──┴──┘    │                                   │                     │   │       │
  │  │          └────────┬───────┘                                   │                     │   │       │
  │  │                   │                                           │                     │   │       │
  │  │                   ▼                                           │                     │   │       │
  │  │          ┌─────────────────┐                                  │                     │   │       │
  │  │          │    decoder      │                                  │                     │   │       │
  │  │          │   (combinat.)   │                                  │                     │   │       │
  │  │          └──┬──┬──┬──┬──┬─┘                                  │                     │   │       │
  │  │             │  │  │  │  │                                     │                     │   │       │
  │  │             │  │  │  │  └── w_alu_op[3:0]                    │                     │   │       │
  │  │             │  │  │  └───── w_alu_src                        │                     │   │       │
  │  │             │  │  └──────── w_dec_reg_we                     │                     │   │       │
  │  │             │  └─────────── w_pc_load                        │                     │   │       │
  │  │             └────────────── w_use_imm8                       │                     │   │       │
  │  │             │                                                │                     │   │       │
  │  │             ├── w_rd[2:0] ──────────────────┐                │                     │   │       │
  │  │             ├── w_rs1[2:0] ─────────────────┤ to regfile     │                     │   │       │
  │  │             ├── w_rs2[2:0] ─────────────────┘                │                     │   │       │
  │  │             ├── w_imm6[5:0] ─────────────────── to alu_op_mux│                     │   │       │
  │  │             ├── w_imm8[7:0] ─────── to writeback_mux + pc   │                     │   │       │
  │  │             │                                                │                     │   │       │
  │  │             ▼                                                │                     │   │       │
  │  │    ┌─────────────────────┐                                   │                     │   │       │
  │  │    │      regfile        │                                   │                     │   │       │
  │  │    │    8x8-bit          │                                   │                     │   │       │
  │  │    │  dual-read /        │ ◀── i_we = w_fsm_reg_we          │                     │   │       │
  │  │    │  single-write       │          & w_dec_reg_we           │                     │   │       │
  │  │    │                     │                                   │                     │   │       │
  │  │    │  raddr1 ← w_rs1    │                                   │                     │   │       │
  │  │    │  raddr2 ← w_rs2    │                                   │                     │   │       │
  │  │    │  waddr  ← w_rd     │                                   │                     │   │       │
  │  │    │  wd ◀── w_write_data│                                   │                     │   │       │
  │  │    └───┬───────────┬─────┘                                   │                     │   │       │
  │  │        │           │                                         │                     │   │       │
  │  │        │ w_rd1_data│ w_rd2_data                              │                     │   │       │
  │  │        │ (rs1)     │ (rs2)                                   │                     │   │       │
  │  │        │           │                                         │                     │   │       │
  │  │        │           ▼                                         │                     │   │       │
  │  │        │  ┌─────────────────┐                                │                     │   │       │
  │  │        │  │alu_operand_mux │                                 │                     │   │       │
  │  │        │  │                 │ ◀── i_sel = w_alu_src          │                     │   │       │
  │  │        │  │ 0: w_rd2_data  │     (0=reg, 1=imm)             │                     │   │       │
  │  │        │  │ 1: sext(imm6)  │                                 │                     │   │       │
  │  │        │  └───────┬────────┘                                 │                     │   │       │
  │  │        │          │ w_alu_b                                  │                     │   │       │
  │  │        │          │                                          │                     │   │       │
  │  │        ▼          ▼                                          │                     │   │       │
  │  │  ┌──────────────────────┐                                    │                     │   │       │
  │  │  │        alu           │                                    │                     │   │       │
  │  │  │  6 ops: ADD SUB AND  │                                    │                     │   │       │
  │  │  │  OR XOR NOT          │                                    │                     │   │       │
  │  │  │                      │                                    │                     │   │       │
  │  │  │  i_a ← w_rd1_data   │                                    │                     │   │       │
  │  │  │  i_b ← w_alu_b      │                                    │                     │   │       │
  │  │  │  i_opcode ← w_alu_op│                                    │                     │   │       │
  │  │  └──────┬───────────────┘                                    │                     │   │       │
  │  │         │ w_alu_result[7:0]                                  │                     │   │       │
  │  │         │ w_alu_carry                                        │                     │   │       │
  │  │         │                                                    │                     │   │       │
  │  │         ├──────────────────────────────────────────────── ──▶ o_alu[7:0]           │   │       │
  │  │         │                                                    │                     │   │       │
  │  │         ├──────────────┐                                     │                     │   │       │
  │  │         │              ▼                                     │                     │   │       │
  │  │         │    ┌──────────────┐                                │                     │   │       │
  │  │         │    │  zero_flag   │                                │                     │   │       │
  │  │         │    │   #(.N=8)    │                                │                     │   │       │
  │  │         │    └──────┬───────┘                                │                     │   │       │
  │  │         │           │ w_zero_flag                            │                     │   │       │
  │  │         │           │                                        │                     │   │       │
  │  │         │           ▼                                        │                     │   │       │
  │  │         │     w_do_jump = w_pc_load                          │                     │   │       │
  │  │         │                | (w_is_beq & w_zero_flag)          │                     │   │       │
  │  │         │                                                    │                     │   │       │
  │  │         ▼                ▼                                   │                     │   │       │
  │  │  ┌──────────────────────────────┐                            │                     │   │       │
  │  │  │      writeback_mux           │                            │                     │   │       │
  │  │  │                              │                            │                     │   │       │
  │  │  │  0: w_alu_result  (R-type)   │                            │                     │   │       │
  │  │  │  1: w_imm8        (LDI)      │ ◀── w_use_imm8            │                     │   │       │
  │  │  │  2: w_read_data[7:0] (LOAD)  │ ◀── w_fsm_load_data_sel   │                     │   │       │
  │  │  └──────────┬───────────────────┘                            │                     │   │       │
  │  │             │ w_write_data ──────────────────────────▶ regfile.i_wd               │   │       │
  │  │             │                                                │                     │   │       │
  │  │  ┌──────────┴──────────┐                                     │                     │   │       │
  │  │  │         pc          │                                     │                     │   │       │
  │  │  │  8-bit counter      │                                     │                     │   │       │
  │  │  │  +   adder          │                                     │                     │   │       │
  │  │  │                     │                                     │                     │   │       │
  │  │  │  i_load ← w_do_jump│                                     │                     │   │       │
  │  │  │  i_load_addr ← imm8│                                     │                     │   │       │
  │  │  │  i_en ← w_fsm_pc_en│                                     │                     │   │       │
  │  │  └──────────┬──────────┘                                     │                     │   │       │
  │  │             │                                                │                     │   │       │
  │  │             └─────────────────────────────────────────── ──▶ o_pc[7:0]             │   │       │
  │  │                                                              │                     │   │       │
  │  └──────────────────────────────────────────────────────────────┘                     │   │       │
  │                                                                                       │   │       │
  │  ┌──────────────────────────────────── CONTROL ────────────────────────────────────┐  │   │       │
  │  │                                                                                 │  │   │       │
  │  │  ┌──────────────────────────┐          ┌──────────────────────────────────┐      │  │   │       │
  │  │  │       cpu_fsm            │          │          mem_ctrl               │      │  │   │       │
  │  │  │                          │          │                                  │      │  │   │       │
  │  │  │  States (8):             │ mem bus  │  States (16):                    │      │  │   │       │
  │  │  │  FETCH ─▶ WAIT_FETCH    │◀────────▶│  IDLE                            │      │  │   │       │
  │  │  │  ─▶ DECODE              │          │  ─▶ FETCH_CMD / FETCH_ADDR       │      │  │   │       │
  │  │  │  ─▶ EXECUTE             │ mem_req  │  ─▶ FETCH_WAIT_HI / _LO         │      │  │   │       │
  │  │  │  ─▶ MEM_REQ            ─┼─────────▶│  ─▶ LOAD_CMD / LOAD_ADDR        │      │  │   │       │
  │  │  │  ─▶ WAIT_MEM           ◀┼──────────│─ ─▶ LOAD_DUMMY / LOAD_WAIT      │      │  │   │       │
  │  │  │  ─▶ WRITEBACK           │ mem_done │  ─▶ WREN_CMD / WREN_WAIT        │      │  │   │       │
  │  │  │  ─▶ PC_UPDATE           │          │  ─▶ STORE_CMD / STORE_ADDR      │      │  │   │       │
  │  │  │                          │ mem_op ──▶│  ─▶ STORE_DATA / STORE_WAIT    │      │  │   │       │
  │  │  │  Outputs:                │ mem_addr─▶│  ─▶ DONE                       │      │  │   │       │
  │  │  │  ─ w_fsm_instr_en       │ mem_wdata▶│                                  │      │  │   │       │
  │  │  │  ─ w_fsm_reg_we         │          │  Outputs:                        │      │  │   │       │
  │  │  │  ─ w_fsm_pc_en          │          │  ─ w_read_data[15:0]            │      │  │   │       │
  │  │  │  ─ w_fsm_load_data_sel  │          │  ─ w_cs_n                       │      │  │   │       │
  │  │  │                          │          │  ─ w_spi_tx_data / tx_load     │      │  │   │       │
  │  │  │  Inputs from datapath:   │          │                                  │      │  │   │       │
  │  │  │  ─ o_pc                  │          │                                  │      │  │   │       │
  │  │  │  ─ w_alu_result          │          │                                  │      │  │   │       │
  │  │  │  ─ w_rd2_data            │          │                                  │      │  │   │       │
  │  │  │  ─ w_is_load, w_is_store │          │                                  │      │  │   │       │
  │  │  └──────────┬───────────────┘          └────────────────┬─────────────────┘      │  │   │       │
  │  │             │ w_cpu_state[2:0]                          │ w_mem_state[3:0]       │  │   │       │
  │  │             └──────────────┬────────────────────────────┘                        │  │   │       │
  │  │                            ▼                                                     │  │   │       │
  │  │                 o_state = {w_mem_state, w_cpu_state} ──────────────────────── ──▶ o_state[6:0]  │
  │  │                                                                                 │  │   │       │
  │  └─────────────────────────────────────────────────────────────────────────────────┘  │   │       │
  │                                                                                       │   │       │
  │  ┌──────────────────────────────────── SPI ENGINE ─────────────────────────────────┐  │   │       │
  │  │                                                                                 │  │   │       │
  │  │  ┌─────────────────────────────────────────────────────────────────────┐         │  │   │       │
  │  │  │                      spi_phy                                     │         │  │   │       │
  │  │  │                                                                     │         │  │   │       │
  │  │  │  ┌──────────────┐    ┌──────────────┐    ┌───────────────────┐     │         │  │   │       │
  │  │  │  │  cdc_sync    │    │ spi_shift_tx │    │ spi_byte_counter  │     │         │  │   │       │
  │  │  │  │  (3-stage    │    │  MSB-first   │    │  4-bit counter    │     │         │  │   │       │
  │  │  │  │   SCLK sync  │    │  8-bit shift │    │  byte_done pulse  │     │         │  │   │       │
  │  │  │  │  + edge det)  │    │  register    │    │  every 8 bits     │     │         │  │   │       │
  │  │  │  │              │    └──────┬───────┘    └──────────┬────────┘     │         │  │   │       │
  │  │  │  │  cdc_sync    │           │                       │              │         │  │   │       │
  │  │  │  │  (2-stage    │    ┌──────┴───────┐               │              │         │  │   │       │
  │  │  │  │   MOSI sync) │    │ spi_shift_rx │               │              │         │  │   │       │
  │  │  │  └──────────────┘    │  MSB-first   │    w_spi_byte_done           │         │  │   │       │
  │  │  │                      │  8-bit shift │────────────────┘              │         │  │   │       │
  │  │  │                      │  register    │                              │         │  │   │       │
  │  │  │                      └──────────────┘                              │         │  │   │       │
  │  │  │                                                                     │         │  │   │       │
  │  │  │  i_tx_data ◀── w_spi_tx_data (from mem_ctrl)                       │         │  │   │       │
  │  │  │  i_tx_load ◀── w_spi_tx_load (from mem_ctrl)                       │         │  │   │       │
  │  │  │  o_rx_data ──▶ w_spi_rx_data (to mem_ctrl)                         │         │  │   │       │
  │  │  │  o_byte_done ─▶ w_spi_byte_done (to mem_ctrl)                      │         │  │   │       │
  │  │  │  i_cs_n ◀── w_cs_n (from mem_ctrl)                                │         │  │   │       │
  │  │  └─────────────────────────────────────────────────────────────────────┘         │  │   │       │
  │  │                                                                                 │  │   │       │
  │  │  Physical SPI bus wires:                                                        │  │   │       │
  │  │    o_mosi ◀── spi_phy.o_miso  (we are master: our TX = bus MOSI)              │  │   │       │
  │  │    i_miso ──▶ spi_phy.i_mosi  (bus MISO = our RX)                             │  │   │       │
  │  │    o_cs_n ◀── w_cs_n                                                            │  │   │       │
  │  │    i_sclk ──▶ spi_phy.i_sclk                                                 │  │   │       │
  │  │                                                                                 │  │   │       │
  │  └─────────────────────────────────────────────────────────────────────────────────┘  │   │       │
  │                                                                                       │   │       │
  └───────────────────────────────────────────────────────────────────────────────────────┘   │       │
        │           │          │                                                              │       │
     o_mosi      o_cs_n    o_state[6:0]                                        i_clk ────────┘       │
                                                                               i_rst_n ──────────────┘
        │           │                          o_pc[7:0]    o_alu[7:0]
        ▼           ▼                             │             │
  ┌─────────────────────┐                         │             │
  │    External nvSRAM  │                         ▼             ▼
  │    (SPI PHY)      │                    [debug ports]
  │                     │
  │  i_miso ────────────┤
  │  i_sclk ────────────┤
  └─────────────────────┘
```

## Module Hierarchy (Dependency Tree)

```
half_cpu
├── register #16 ...................... instruction register (16-bit latch)
│   └── dff .......................... D flip-flop (x16)
│
├── decoder .......................... 16-bit instruction field extraction (combinational)
│
├── regfile #(NREG=8, WIDTH=8) ...... 8 registers, 8-bit each
│   ├── mux .......................... read port 1 (8-way, 8-bit)
│   ├── mux .......................... read port 2 (8-way, 8-bit)
│   └── register #8 (x8) ............ storage
│       └── dff (x8 each)
│
├── alu_operand_mux .................. selects rs2 or sign-extended imm6
│   └── mux .......................... 2:1, 8-bit
│
├── alu .............................. 6-operation ALU (ADD SUB AND OR XOR NOT)
│   ├── kogge-stone #8 .............. parallel prefix adder (ADD)
│   ├── kogge-stone #8 .............. parallel prefix subtractor (SUB)
│   └── mux .......................... 16:1 result selector
│
├── zero_flag #8 ..................... OR-NOR reduction → zero detect
│
├── writeback_mux .................... 3-way: ALU | imm8 | load_data
│   └── mux .......................... 2-level select
│
├── pc ............................... 8-bit program counter
│   ├── kogge-stone #8 .............. PC+1 incrementer
│   ├── mux .......................... jump / increment select
│   └── register #8 ................. PC storage
│       └── dff (x8)
│
├── cpu_fsm .......................... pipeline controller (8 states)
│   ├── pipeline_reg ................. ALU result latch
│   ├── pipeline_reg ................. rs2_data latch
│   └── pipeline_reg ................. control flags latch
│
├── mem_ctrl ......................... nvSRAM SPI protocol translator (16 states)
│   └── read_data_accum .............. 16-bit RX word assembler
│       └── register #8 (x2) ........ hi/lo byte latches
│
└── spi_phy ........................ byte-oriented SPI engine
    ├── cdc_sync #3 .................. SCLK synchronizer (3-stage) + edge detect
    ├── cdc_sync #2 .................. MOSI synchronizer (2-stage)
    ├── spi_shift_tx ................. 8-bit TX shift register (MSB-first)
    ├── spi_shift_rx ................. 8-bit RX shift register (MSB-first)
    └── spi_byte_counter ............. 4-bit bit counter + byte_done pulse
```

## Signal Flow Summary

```
┌──────────────┐     w_instr[15:0]     ┌─────────┐
│  instr_reg   │──────────────────────▶│ decoder │
│  (16-bit)    │                       └────┬────┘
└──────┬───────┘                            │
       ▲                        ┌───────────┼──────────┐
       │                        │ rs1,rs2   │ alu_op   │ rd, imm8, imm6
  w_read_data[15:0]             │ control   │          │ alu_src, etc.
       │                        ▼           │          │
       │                   ┌─────────┐      │          │
       │                   │ regfile │      │          │
       │                   └──┬───┬──┘      │          │
       │              rd1_data│   │rd2_data  │          │
       │                      │   │         │          │
       │                      │   ▼         │          │
       │                      │ ┌─────────┐ │          │
       │                      │ │alu_op_  │ │          │
       │                      │ │  mux    │ │          │
       │                      │ └────┬────┘ │          │
       │                      │      │      │          │
       │                      ▼      ▼      ▼          │
       │                   ┌──────────────────┐        │
       │                   │       ALU        │        │
       │                   └────────┬─────────┘        │
       │                            │ alu_result       │
       │                   ┌────────┼──────────┐       │
       │                   │        │          │       │
       │                   ▼        ▼          ▼       ▼
       │             ┌──────┐ ┌──────────┐ ┌──────────────┐
       │             │ zero │ │writeback │ │    pc         │
       │             │ flag │ │  mux     │ │  (inc/jump)   │
       │             └──┬───┘ └────┬─────┘ └──────┬───────┘
       │                │          │               │
       │                │          └──▶ regfile    └──▶ o_pc ──▶ fsm
       │                │               .i_wd
       │                └──▶ w_do_jump ──▶ pc.i_load
       │
       │
  ┌────┴──────┐     mem bus      ┌──────────┐    spi bus    ┌───────────┐
  │ mem_ctrl  │◀────────────────▶│ cpu_fsm  │               │ spi_phy │
  │           │ req/done/op/addr │          │               │           │
  │           │                  │          │               │           │
  │   tx ─────┼──────────────────┼──────────┼──────────────▶│ shift_tx  │──▶ o_mosi
  │   rx ◀────┼──────────────────┼──────────┼──────────────◀│ shift_rx  │◀── i_miso
  │   cs_n ───┼──────────────────┼──────────┼──────────────▶│ i_cs_n    │
  │           │                  │          │               │           │◀── i_sclk
  └───────────┘                  └──────────┘               └───────────┘
                                                                  │
                                                            ┌─────┴─────┐
                                                            │  External │
                                                            │  nvSRAM   │
                                                            └───────────┘
```

## Pipeline Stages (cpu_fsm)

```
  ┌───────┐    ┌────────────┐    ┌────────┐    ┌─────────┐    ┌─────────┐    ┌──────────┐    ┌───────────┐    ┌───────────┐
  │ FETCH │──▶│ WAIT_FETCH │──▶│ DECODE │──▶│ EXECUTE │──▶│ MEM_REQ │──▶│ WAIT_MEM │──▶│ WRITEBACK │──▶│ PC_UPDATE │──┐
  └───────┘    └────────────┘    └────────┘    └─────────┘    └─────────┘    └──────────┘    └───────────┘    └───────────┘  │
      ▲                                                                                                                     │
      └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

  FETCH:       Assert mem_req (FETCH op, addr = PC). Waits for mem_done.
  WAIT_FETCH:  Stall until mem_ctrl completes 4-byte SPI read.
  DECODE:      Pulse instr_en → latch 16-bit instruction. Decoder produces control signals.
  EXECUTE:     ALU computes result. Pipeline regs capture alu_result, rs2_data, flags.
  MEM_REQ:     If LOAD/STORE: assert mem_req with appropriate op. Else: skip to WRITEBACK.
  WAIT_MEM:    Stall until mem_ctrl finishes LOAD/STORE SPI sequence.
  WRITEBACK:   Pulse reg_we. Writeback mux selects source. Pulse load_data_sel if LOAD.
  PC_UPDATE:   Pulse pc_en. PC increments or jumps based on w_do_jump.
```

## SPI Protocol (mem_ctrl states)

```
  FETCH (read 16-bit instruction):
  ┌──────────┬──────────┬──────────┬──────────┬──────────┐
  │ CMD=0x03 │ ADDR=PC  │ DUMMY=00 │ RX hi    │ RX lo    │
  │ (READ)   │          │          │ byte     │ byte     │
  └──────────┴──────────┴──────────┴──────────┴──────────┘
      CS_n ▼ ─────────────────────────────────── CS_n ▲

  LOAD (read 8-bit data):
  ┌──────────┬──────────┬──────────┬──────────┐
  │ CMD=0x0B │ ADDR     │ DUMMY=00 │ RX data  │
  │(FAST_RD) │ =alu_res │          │ byte     │
  └──────────┴──────────┴──────────┴──────────┘
      CS_n ▼ ─────────────────────── CS_n ▲

  STORE (write 8-bit data):
  ┌──────────┐     ┌──────────┬──────────┬──────────┐
  │ CMD=0x06 │     │ CMD=0x02 │ ADDR     │ TX data  │
  │ (WREN)   │     │ (WRITE)  │ =alu_res │ =rs2     │
  └──────────┘     └──────────┴──────────┴──────────┘
  CS_n ▼───▲       CS_n ▼ ─────────────── CS_n ▲
```

## Instruction Format (16-bit)

```
  R-type:     [15:12 opcode] [11:9 rd] [8:6 rs1] [5:3 rs2] [2:0 unused]
  I-type:     [15:12 opcode] [11:9 rd] [8:6 rs1] [5:0 imm6]
  LDI:        [  1011      ] [11:9 rd] [8:1 imm8          ] [0 unused]
  LOAD:       [  1101      ] [11:9 rd] [8:6 rs1] [5:0 imm6]     addr = rs1 + sext(imm6)
  STORE:      [  1110      ] [11:9 rs2][8:6 rs1] [5:0 imm6]     addr = rs1 + sext(imm6)
  BEQ:        [  1100      ] [11:9 rs1][8:6 rs2] [5:0 unused]   branch if rs1 == rs2
  JMP:        [  1111      ] [  unused ] [8:1 imm8]              PC = imm8
```
