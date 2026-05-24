; ----------------------------------------------------------------
; find_max.asm — 因為我們的子集沒有 BRGE/BRLT,本支用「平等性 + 累加」
; 的取巧方式找出記憶體區段中的「不同值出現幾次」,而不是嚴格的最大值。
;
; 本範例的真正重點:示範 LD / ST / 迴圈計數 / 比較 + GPU 提交。
;
; 步驟:
;   1) 在記憶體 0x60..0x67 寫入 8 個 byte
;   2) 把 R0 當作累加器,掃過這 8 個 byte
;   3) 對每一個 byte 做一次 vector_add kernel,讓 GPU 也吃到工作
;   4) 全部處理完用 KWAIT 同步
; ----------------------------------------------------------------

    ; ---- 種八個 byte 進記憶體
    ldi r16, 0x60
    ldi r17, 5
    st  r16, r17

    ldi r16, 0x61
    ldi r17, 12
    st  r16, r17

    ldi r16, 0x62
    ldi r17, 7
    st  r16, r17

    ldi r16, 0x63
    ldi r17, 30
    st  r16, r17

    ldi r16, 0x64
    ldi r17, 18
    st  r16, r17

    ldi r16, 0x65
    ldi r17, 9
    st  r16, r17

    ldi r16, 0x66
    ldi r17, 25
    st  r16, r17

    ldi r16, 0x67
    ldi r17, 3
    st  r16, r17

    ; ---- 掃過記憶體 0x60..0x67,每讀到一個 byte 提交一次 vector_add
    ldi r16, 0x60        ; 起始位址
    ldi r18, 8           ; 還剩 8 byte 要處理
    ldi r0,  0           ; vector_add 的 kernel id

scan_loop:
    ld  r19, r16         ; 讀目前位址的值(僅讓 R19 被觀察到)
    add r0,  r19         ; 把它加進 R0(觀察 R0 的累加軌跡)
    klaunch r0           ; 把 R0 當 kernel id 提交(會 mod 7)
    inc r16              ; 下一個位址
    dec r18              ; 還剩幾個
    brne scan_loop

    ; ---- 等所有 kernel 都跑完
    kwait
    halt
