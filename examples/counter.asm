; ----------------------------------------------------------------
; counter.asm — 倒數 9 → 0,每數一個就提交一顆 hash kernel,
; 並把當下的計數值寫進記憶體 0x70..0x79,留下漂亮的階梯軌跡。
;
; 觀察重點:Heatmap 分頁的記憶體列(0x70 一帶)會像 Tiny8 的
; bubble sort 動畫一樣,從上往下逐格亮起來。
; ----------------------------------------------------------------

    ldi r16, 9           ; 倒數計數器
    ldi r17, 0x70        ; 寫入記憶體的位址
    ldi r18, 2           ; hash 的 kernel id

count_loop:
    st  r17, r16         ; memory[r17] = r16(把當下計數值存進去)
    klaunch r18          ; 提交一顆 hash kernel
    inc r17              ; 下一格記憶體
    dec r16              ; 計數 -1
    brne count_loop      ; 還沒到 0 就繼續

    ; ---- 倒數結束,等 GPU 全部完成再 HALT
    kwait
    halt
