; ----------------------------------------------------------------
; full_gcd_gpu.asm — Tiny8 完整版範例
;
; Euclidean GCD(輾轉相除法)。
; 每跑完一次相減/比較迭代,送 GPU 一顆 hash kernel(代表 checkpoint),
; 最後 KWAIT 等所有 checkpoint kernel 跑完。
;
; 輸入:R16 = a (24)、R17 = b (18)
; 輸出:R0 = gcd(a, b) = 6;R1 = 過程裡送出的 kernel 數
; ----------------------------------------------------------------

    ldi r16, 24
    ldi r17, 18
    ldi r1,  0          ; 計算送出的 kernel 數

gcd_loop:
    cp  r16, r17
    breq done           ; a == b → 收工
    brcs swap_then_sub  ; a < b → 先 swap 再做 a -= b
    sub r16, r17        ; a > b → a -= b
    rjmp checkpoint
swap_then_sub:
    mov r2,  r16
    mov r16, r17
    mov r17, r2
    sub r16, r17

checkpoint:
    ; ---- 把這次 iteration 提交給 GPU 當 checkpoint
    ldi r3, 2           ; 2 = hash kernel
    out 0x40, r3
    inc r1
    rjmp gcd_loop

done:
    mov r0, r16         ; gcd 留在 R0
    out 0xFF, r0        ; KWAIT 等 GPU 把所有 checkpoint 跑完

end:
    jmp end
