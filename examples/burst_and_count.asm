; ----------------------------------------------------------------
; burst_and_count.asm — submit a burst of three different kernels,
; wait for them all to finish, then read back the completed count.
; ----------------------------------------------------------------

    ldi r16, 0          ; vector_add id
    ldi r17, 2          ; hash id
    ldi r18, 3          ; texture_load id

    klaunch r16
    klaunch r17
    klaunch r18

    kwait               ; wait for all three to finish

    in   r0, 0x41       ; r0 = number of kernels completed (mod 256)
    halt
