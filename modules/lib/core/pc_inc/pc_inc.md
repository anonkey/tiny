> **8-bit half-adder chain incrementer** — replaces Kogge-Stone for fixed +1 PC increment.

Ripple chain of N half-adders. Carry-in is tied to 1, so each stage computes `sum = pc[k] ^ carry[k]` and `carry[k+1] = pc[k] & carry[k]`. Minimal area for a constant-increment use case.
