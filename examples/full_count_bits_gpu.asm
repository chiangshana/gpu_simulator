; ----------------------------------------------------------------
; full_count_bits_gpu.asm — Tiny8 完整版範例
;
; 計算 R16 中有幾個 bit 是 1(popcount)。
; 每偵測到一個 1-bit,就送 GPU 一顆 interpolation kernel(視覺化每個 bit 的存在),
; 結束後讀回 GPU 完成數,確認跟我們算的 popcount 一致。
;
; 輸入:R16 = 0xB7(0b1011_0111,有 6 個 bit 是 1)
; 輸出:R0 = popcount = 6;R2 = GPU 完成的 kernel 數(也應該 = 6)
;
; 用了完整版才有的 LSR(右移)指令。
; ----------------------------------------------------------------

    ldi r16, 0xB7       ; 0b1011_0111 — 預期 popcount = 6
    ldi r17, 8          ; 還剩 8 個 bit 要檢查
    ldi r0,  0          ; popcount 累加器
    ldi r3,  1          ; 1 = interpolation kernel id

bit_loop:
    mov r4, r16
    andi r4, 1          ; 取最低位 bit
    breq skip_kernel    ; 如果是 0 → 不送 kernel
    ; 是 1 → 累加並送 GPU
    inc r0
    out 0x40, r3        ; KLAUNCH interpolation
skip_kernel:
    lsr r16             ; r16 >>= 1
    dec r17
    brne bit_loop

    ; ---- KWAIT 等所有 popcount kernel 跑完
    out 0xFF, r0
    in  r2, 0x41        ; 讀「已完成 kernel 數 mod 256」進 R2

done:
    jmp done
