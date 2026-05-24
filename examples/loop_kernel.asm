; ----------------------------------------------------------------
; loop_kernel.asm — submit interpolation kernel three times in a loop,
; counting down with a register, then wait once at the end.
; ----------------------------------------------------------------

    ldi r16, 1          ; interpolation id
    ldi r17, 3          ; loop counter

submit_loop:
    klaunch r16
    dec r17
    brne submit_loop    ; branch if r17 != 0 (Z flag clear)

    kwait
    halt
