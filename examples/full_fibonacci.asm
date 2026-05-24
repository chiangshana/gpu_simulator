; ----------------------------------------------------------------
; full_fibonacci.asm — Tiny8 完整版範例
;
; 改寫自 Tiny8 經典 fibonacci.asm,算到 F(10) = 55,
; 然後把結果當 hint 提交給 GPU 跑一顆 hash kernel。
;
; 注意:這支「只能」在 Tiny8 完整版分頁跑;
; 因為一般 Trace 分頁的子集 ISA 不支援這份程式所有指令。
; ----------------------------------------------------------------

    ldi r16, 0          ; F(0) = 0
    ldi r17, 1          ; F(1) = 1
    ldi r18, 9          ; 倒數計數,要再算 9 次

loop:
    add r16, r17        ; F(n) = F(n-1) + F(n-2)
    mov r19, r16
    mov r16, r17
    mov r17, r19
    dec r18
    brne loop

    ; ---- R17 現在是 F(10) = 55,把它當作 GPU 的 hint
    out 0x41, r17       ; HINT
    ldi r0, 2           ; 2 = hash kernel
    out 0x40, r0        ; KLAUNCH
    out 0xFF, r0        ; KWAIT
done:
    jmp done
