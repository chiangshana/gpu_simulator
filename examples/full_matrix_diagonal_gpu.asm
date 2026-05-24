; ----------------------------------------------------------------
; full_matrix_diagonal_gpu.asm — Tiny8 完整版範例
;
; 把 RAM[0x60..0x9F] 視為 8x8 byte 矩陣(每列 8 byte,共 64 byte)。
; 在主對角線位置寫入 1(其他位置維持 0),然後對每一列送一顆
; texture_load kernel — 模擬對每一列做 GPU 處理。
;
; 矩陣的 (i,j) 位址 = 0x60 + i*8 + j。
; 主對角線 = i == j。
; 結果可以在 Heatmap / Memory Map 分頁直接看到漂亮的對角線。
; ----------------------------------------------------------------

    ldi r16, 0          ; row index (i)
    ldi r3,  3          ; 3 = texture_load kernel id

row_loop:
    cpi r16, 8
    breq done           ; 8 列做完

    ; ---- 計算 row 起始位址 = 0x60 + i*8
    mov r17, r16
    lsl r17             ; r17 *= 2
    lsl r17             ; r17 *= 2
    lsl r17             ; r17 *= 2 → 共 *8
    ldi r18, 0x60
    add r17, r18        ; r17 = 0x60 + i*8

    ; ---- (i, i) 位址 = row_start + i
    mov r19, r17
    add r19, r16

    ; ---- 寫 1 到對角線上
    ldi r20, 1
    st  r19, r20

    ; ---- 對這一列送一顆 GPU kernel
    out 0x40, r3        ; KLAUNCH texture_load

    inc r16
    rjmp row_loop

done:
    out 0xFF, r3        ; KWAIT

end:
    jmp end
