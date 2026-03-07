[Back to Main](../README.md)

# Kogge-Stone - Parallel Prefix Adder

> **O(log N) carry propagation adder with ADD/SUB support**

## Modules

### `ks_black`

Parallel prefix operator (black cell): combines two (P, G) pairs.

```
P = Pi & Pj
G = Gi | (Pi & Gj)
```

### `ks_green`

Final carry computation (green cell): resolves carry from prefix result + carry-in.

```
C_out = Gi | (Pi & C_in)
```

### `kogge_stone`

Parameterized N-bit adder/subtractor.

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `output_S` | out | N+1 | Sum with carry out |
| `input_A` | in | N | Operand A |
| `input_B` | in | N | Operand B |
| `sub` | in | 1 | 0=add, 1=subtract |

| Parameter | Default | Description |
|-----------|---------|-------------|
| `N` | 8 | Bit width |

## Algorithm

1. **Stage 0**: Generate initial P (`A ^ B`) and G (`A & B`)
2. **Stages 1..log2(N)**: Parallel prefix tree — each stage doubles the span using black cells
3. **Carry**: Green cells compute final carries from prefix tree + carry-in
4. **Sum**: `S[i] = P0[i] ^ C[i]`

Subtraction: `B` is XORed with `sub` (one's complement) and `sub` is used as carry-in (two's complement).

## Dependencies

None (leaf cells).

---
[Back to Main](../README.md)
