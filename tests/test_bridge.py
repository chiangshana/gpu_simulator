"""Unit tests for gpu_simulator.bridge — the CPU↔GPU coordination layer."""

from gpu_simulator.bridge import (
    GPU_PORT_KWAIT,
    KERNEL_BY_ID,
    CPUGPUBridge,
    TraceLog,
    TraceRow,
    kernel_name_for_id,
)
from gpu_simulator.core import GPU, GPUConfig
from gpu_simulator.cpu import CPU, assemble


# ---------------------------------------------------------------------------
# id table
# ---------------------------------------------------------------------------
def test_kernel_id_table_covers_all_factories():
    assert kernel_name_for_id(0) == "vector_add"
    assert kernel_name_for_id(2) == "hash"
    # wraps around so a stray byte never crashes
    assert kernel_name_for_id(len(KERNEL_BY_ID) + 3) == kernel_name_for_id(3)


# ---------------------------------------------------------------------------
# trace log
# ---------------------------------------------------------------------------
def test_trace_log_capacity_and_clear():
    log = TraceLog(capacity=3)
    for cycle in range(5):
        log.append(
            TraceRow(
                cycle=cycle,
                pc=0,
                instruction_text="nop",
                sreg_text="----",
                register_changes=(),
                gpu_summary="idle",
                cpu_halted=False,
                cpu_stalled=False,
                port_writes=(),
                port_reads=(),
            )
        )
    assert len(log) == 3
    cycles = [row.cycle for row in log]
    assert cycles == [2, 3, 4]
    log.clear()
    assert len(log) == 0


def test_trace_row_to_dict_is_json_friendly():
    row = TraceRow(
        cycle=1,
        pc=2,
        instruction_text="ldi r0, 5",
        sreg_text="----",
        register_changes=((0, 5),),
        gpu_summary="idle",
        cpu_halted=False,
        cpu_stalled=False,
        port_writes=((0x40, 1),),
        port_reads=(),
    )
    payload = row.to_dict()
    assert payload["register_changes"] == [[0, 5]]
    assert payload["port_writes"] == [[0x40, 1]]


# ---------------------------------------------------------------------------
# bridge end-to-end
# ---------------------------------------------------------------------------
def _small_bridge() -> CPUGPUBridge:
    gpu = GPU(GPUConfig(num_sms=2, warps_per_sm=2, threads_per_warp=8))
    return CPUGPUBridge(cpu=CPU(), gpu=gpu)


def test_klaunch_submits_kernel_with_correct_name():
    bridge = _small_bridge()
    bridge.load_program(assemble("""
        ldi r16, 0          ; vector_add id
        klaunch r16
        halt
    """))
    while not bridge.cpu.halted:
        bridge.step()
    assert bridge.gpu.kernels_submitted == 1
    last_event = bridge.gpu.snapshot()["event_log"][0]
    assert "vector_add" in last_event["message"]


def test_kwait_stalls_until_gpu_finishes():
    bridge = _small_bridge()
    bridge.load_program(assemble("""
        ldi r16, 0
        klaunch r16
        kwait
        halt
    """))
    cycles = 0
    stall_cycles = 0
    while not bridge.cpu.halted and cycles < 500:
        row = bridge.step()
        cycles += 1
        if row.cpu_stalled:
            stall_cycles += 1
    assert bridge.gpu.kernels_completed == 1
    # at least a few cycles must have been spent stalled in KWAIT
    assert stall_cycles >= 1


def test_in_port_returns_outstanding_kernel_count():
    bridge = _small_bridge()
    bridge.load_program(assemble("""
        ldi r16, 0
        klaunch r16
        klaunch r16
        kstat r0
        halt
    """))
    while not bridge.cpu.halted:
        bridge.step()
    # by the time we read 0x40, two kernels are outstanding
    assert bridge.cpu.registers[0] >= 1


def test_run_until_halt_stops_at_halt():
    bridge = _small_bridge()
    bridge.load_program(assemble("nop\nhalt\n"))
    cycles = bridge.run_until_halt(max_cycles=20)
    assert bridge.cpu.halted is True
    assert cycles <= 5


def test_loop_program_terminates_and_submits_three_kernels():
    bridge = _small_bridge()
    bridge.load_program(assemble("""
        ldi r16, 1          ; interpolation id
        ldi r17, 3          ; counter
    loop:
        klaunch r16
        dec r17
        brne loop
        kwait
        halt
    """))
    bridge.run_until_halt(max_cycles=2000)
    assert bridge.gpu.kernels_submitted == 3
    assert bridge.gpu.kernels_completed == 3


def test_kwait_port_id_is_ff():
    """Make sure the port assignment hasn't drifted from the spec."""
    assert GPU_PORT_KWAIT == 0xFF
