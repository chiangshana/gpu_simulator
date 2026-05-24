; ----------------------------------------------------------------
; memory_copy.asm — copy six bytes from RAM[0x60..0x65] to
; RAM[0x70..0x75], then submit a vector_add kernel and KWAIT.
;
; This is the canonical example for the Heatmap and Debug tabs:
; the memory rows 0x60–0x7F light up step-by-step, exactly like
; the Tiny8 CLI animation screenshot.
; ----------------------------------------------------------------

start:
    ; ---- seed source bytes at 0x60..0x65
    ldi r20, 0x60
    ldi r21, 10
    st  r20, r21

    ldi r20, 0x61
    ldi r21, 20
    st  r20, r21

    ldi r20, 0x62
    ldi r21, 30
    st  r20, r21

    ldi r20, 0x63
    ldi r21, 40
    st  r20, r21

    ldi r20, 0x64
    ldi r21, 50
    st  r20, r21

    ldi r20, 0x65
    ldi r21, 60
    st  r20, r21

    ; ---- copy 6 bytes from src→dst
    ldi r16, 0x60     ; src pointer
    ldi r17, 0x70     ; dst pointer
    ldi r18, 6        ; remaining count

copy_loop:
    ld  r19, r16      ; load byte from src
    st  r17, r19      ; store byte to dst
    inc r16
    inc r17
    dec r18
    brne copy_loop

    ; ---- ask the GPU to vector_add the freshly-copied buffer
    ldi r0, 0         ; kernel id 0 = vector_add
    klaunch r0
    kwait
    halt
