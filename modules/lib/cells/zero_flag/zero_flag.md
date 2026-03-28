[Back to Main](../README.md)

# Zero Flag — All-Zero Detector

> **Parameterized zero detector: outputs 1 when all input bits are zero**

## Interface

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `zero` | out | 1 | High when all bits of `data` are zero |
| `data` | in | N | Input data |

| Parameter | Default | Description |
|-----------|---------|-------------|
| `N` | 8 | Input width |

## Usage

Used for BEZ (branch-if-zero) instruction: branch is taken when rs1 is zero.

Shared by both `cpu.v` and `half_cpu.v`.

## Dependencies

None (pure combinational).

---
[Back to Main](../README.md)
