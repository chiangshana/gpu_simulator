; ----------------------------------------------------------------
; sort_three.asm — 比較三個數字,把「相等的標記」記下來
;
; 我們的 Tiny8 子集 ISA 只有 BRNE / BREQ(看 Z 旗標),沒有 BRGE / BRLT,
; 所以本範例聚焦在「示範 CP 怎麼影響 SREG 旗標」的教學重點。
;
; 結果說明:
;   R0 = 1  代表 R16 == R17
;   R1 = 1  代表 R16 == R18
;   R2 = 1  代表 R17 == R18
;
; 觀察重點:Trace / Debug / Heatmap 三個分頁看 SREG 的 Z 欄位
; 在 CP 指令前後是怎麼變動的。
; ----------------------------------------------------------------

    ldi r16, 42
    ldi r17, 17
    ldi r18, 42      ; 故意讓 R16 跟 R18 相等

    ; ---- 比較 R16 跟 R17
    cp  r16, r17
    breq mark_16_eq_17
    jmp  next1
mark_16_eq_17:
    ldi r0, 1
next1:

    ; ---- 比較 R16 跟 R18(預期相等,Z 旗標會被設起)
    cp  r16, r18
    breq mark_16_eq_18
    jmp  next2
mark_16_eq_18:
    ldi r1, 1
next2:

    ; ---- 比較 R17 跟 R18
    cp  r17, r18
    breq mark_17_eq_18
    jmp  fire_kernel
mark_17_eq_18:
    ldi r2, 1

fire_kernel:
    ; ---- 比完之後,把 r0 / r1 / r2 三個記號丟給 GPU 觀察
    klaunch r0
    klaunch r1
    klaunch r2
    kwait
    halt
