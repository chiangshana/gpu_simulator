; ----------------------------------------------------------------
; full_factorial_gpu.asm — Tiny8 完整版範例
;
; 算 5! = 120,用 Tiny8 完整版才有的 MUL 指令做乘法。
; 每乘一次就送 GPU 一顆 vector_add kernel(代表 SIMD 平行做某些 element-wise 後處理),
; 最後 KWAIT,並把 5! 的結果當下一顆 kernel 的 hint 傳給 GPU。
;
; 輸入:R16 = 5
; 輸出:R0 = 5! 的低位元組 = 120;R1 = 已提交給 GPU 的 kernel 數 = 4
; ----------------------------------------------------------------

    ldi r16, 5          ; 算 5!
    ldi r0, 1           ; 累積 = 1
    ldi r1, 0           ; 提交 kernel 數
    ldi r3, 0           ; 0 = vector_add

factorial_loop:
    cpi r16, 1
    breq done           ; r16 == 1 → 結束(不需要再乘)
    mul r0, r16         ; r0 ← (r0 × r16) 的低位元組
    out 0x40, r3        ; KLAUNCH vector_add(代表這次 multiply 的後續工作)
    inc r1
    dec r16
    rjmp factorial_loop

done:
    out 0x41, r0        ; HINT = 結果(下一顆 kernel 會看到)
    ldi r4, 6           ; 6 = page_nav kernel
    out 0x40, r4        ; KLAUNCH page_nav(用 5! 結果當 hint)
    inc r1
    out 0xFF, r1        ; KWAIT

end:
    jmp end
