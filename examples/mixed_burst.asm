; ----------------------------------------------------------------
; mixed_burst.asm — 一口氣把 7 種 kernel 全提交一遍,觀察混合工作
; 負載的 GPU 反應。
;
; Kernel id 對應:
;   0=vector_add  1=interpolation  2=hash  3=texture_load
;   4=idle_compression  5=app_launch  6=page_nav
;
; 觀察重點:
;   • Live 分頁:8 顆 SM 會輪番亮起,VRAM bar 會大起大落
;   • Heatmap 分頁:暫存器 R0 會一路從 0 累加到 6,SREG 旗標
;     每次比較完都會跳動
; ----------------------------------------------------------------

    ldi r0, 0            ; 從 vector_add 開始
    ldi r1, 7            ; 共 7 種 kernel

burst_loop:
    klaunch r0           ; 提交目前這種 kernel
    inc r0               ; 下一種
    dec r1               ; 還剩幾種
    brne burst_loop

    ; ---- 七種 kernel 全提交完,等它們跑完
    kwait
    halt
