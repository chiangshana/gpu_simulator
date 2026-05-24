; ----------------------------------------------------------------
; hello_gpu.asm — the simplest CPU↔GPU interaction
; Submits one vector_add kernel, waits for it, then halts.
;
; Kernel id table:
;   0 = vector_add        4 = idle_compression
;   1 = interpolation     5 = app_launch
;   2 = hash              6 = page_nav
;   3 = texture_load
; ----------------------------------------------------------------

    ldi r16, 0          ; r16 = vector_add id
    klaunch r16         ; submit one vector_add kernel
    kwait               ; CPU stalls until the GPU finishes
    halt
