; ----------------------------------------------------------------
; full_bubble_sort.asm — Tiny8 完整版範例
;
; 把 RAM[0x60..0x67] 的 8 個 byte 用 bubble sort 由小到大排好,
; 排完後對著 GPU 提交 vector_add + texture_load 兩種 kernel,
; 並 KWAIT 等它們做完。
;
; 用了完整版才有的指令:LSL / RJMP / BRGE 等。
; ----------------------------------------------------------------

start:
    ; ---- 種 8 個 byte 進去
    ldi r20, 0x60
    ldi r21, 30
    st  r20, r21
    ldi r20, 0x61
    ldi r21, 12
    st  r20, r21
    ldi r20, 0x62
    ldi r21, 7
    st  r20, r21
    ldi r20, 0x63
    ldi r21, 99
    st  r20, r21
    ldi r20, 0x64
    ldi r21, 18
    st  r20, r21
    ldi r20, 0x65
    ldi r21, 5
    st  r20, r21
    ldi r20, 0x66
    ldi r21, 64
    st  r20, r21
    ldi r20, 0x67
    ldi r21, 21
    st  r20, r21

    ; ---- bubble sort outer loop counter
    ldi r24, 8              ; 跑 8 趟,絕對夠把 8 個元素排好

outer:
    dec r24
    breq sorted             ; r24 = 0 代表排好了

    ldi r25, 0x60           ; 內層起始位址(每趟都從頭掃)
    ldi r26, 0x67           ; 內層終止位址(掃到第 7 對為止)

inner:
    ld  r0, r25
    mov r27, r25
    inc r27
    ld  r1, r27
    cp  r0, r1
    brcs no_swap            ; r0 < r1 不換
    st  r25, r1             ; 互換
    st  r27, r0
no_swap:
    inc r25
    cp  r25, r26
    brcs inner
    rjmp outer

sorted:
    ; ---- 排序完成,提交兩顆 kernel 給 GPU
    ldi r0, 0
    out 0x40, r0            ; KLAUNCH vector_add
    ldi r0, 3
    out 0x40, r0            ; KLAUNCH texture_load
    out 0xFF, r0            ; KWAIT

end:
    jmp end
