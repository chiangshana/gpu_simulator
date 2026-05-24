; ----------------------------------------------------------------
; full_histogram_gpu.asm — Tiny8 完整版範例
;
; 在 RAM[0x60..0x6F] 種 16 個 byte 進去(值 0~3),
; 然後掃過去,把每個值當成「bucket index」,
; 在 RAM[0x70..0x73] 對應位置 +1(共 4 個 bucket)。
; 每 +1 一次就送 GPU 一顆 hash kernel,代表這個 bucket 累加結果。
;
; 輸出:RAM[0x70] = 出現 0 的次數
;       RAM[0x71] = 出現 1 的次數
;       RAM[0x72] = 出現 2 的次數
;       RAM[0x73] = 出現 3 的次數
;       16 個 sample 加總應該 = 16
;       (預設資料是 0,1,2,3 各 4 個)
; ----------------------------------------------------------------

    ; ---- 種樣本值 0,1,2,3,0,1,2,3,... 進 RAM[0x60..0x6F]
    ldi r16, 0x60
    ldi r17, 16         ; 還要寫 16 byte
    ldi r18, 0          ; 目前要寫的值

seed_loop:
    st  r16, r18
    inc r16
    inc r18
    cpi r18, 4
    brne seed_skip
    ldi r18, 0          ; 寫到 4 就回到 0
seed_skip:
    dec r17
    brne seed_loop

    ; ---- 清空 bucket(RAM[0x70..0x73] = 0)
    ldi r16, 0x70
    ldi r17, 4
    ldi r18, 0
clear_buckets:
    st  r16, r18
    inc r16
    dec r17
    brne clear_buckets

    ; ---- 掃 sample,把對應 bucket +1
    ldi r16, 0x60       ; sample 起始位址
    ldi r17, 16         ; 還剩幾個 sample
    ldi r3,  2          ; 2 = hash kernel id

scan:
    ld  r4, r16         ; 讀 sample
    mov r5, r4
    ldi r6, 0x70
    add r5, r6          ; bucket 位址 = 0x70 + sample
    ld  r7, r5          ; bucket 目前值
    inc r7
    st  r5, r7          ; 寫回去
    out 0x40, r3        ; KLAUNCH hash kernel
    inc r16
    dec r17
    brne scan

    ; ---- 等 GPU 跑完
    out 0xFF, r3

end:
    jmp end
