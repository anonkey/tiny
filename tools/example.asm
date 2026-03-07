; Example program: compute (10 + 20) - 5 = 25

    LDI  r0, 10        ; r0 = 10
    LDI  r1, 20        ; r1 = 20
    ADD  r2, r0, r1    ; r2 = 30
    LDI  r3, 5         ; r3 = 5
    SUB  r4, r2, r3    ; r4 = 25

; Logic ops
    LDI  r5, 0xF0      ; r5 = 240
    LDI  r6, 0x0F      ; r6 = 15
    AND  r7, r5, r6    ; r7 = 0
    OR   r0, r5, r6    ; r0 = 255
    XOR  r1, r5, r6    ; r1 = 255

; ADDI
    LDI  r2, 10        ; r2 = 10
    ADDI r3, r2, 5     ; r3 = 15

; Jump
    JMP  done          ; skip to end

; This should be skipped
    LDI  r0, 0xFF

done:
    NOP
