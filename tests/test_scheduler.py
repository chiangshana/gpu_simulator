"""Unit tests for gpu_simulator.scheduler."""

from gpu_simulator.kernel import KernelLibrary
from gpu_simulator.scheduler import PIPELINE_ORDER, PipelineStage, WarpScheduler, next_stage


def test_next_stage_cycles_back_to_fetch():
    assert next_stage(PipelineStage.WRITEBACK) is PipelineStage.FETCH


def test_pipeline_order_contains_all_stages():
    assert set(PIPELINE_ORDER) == set(PipelineStage)
    assert PIPELINE_ORDER[0] is PipelineStage.FETCH


def test_scheduler_expands_grid_into_blocks():
    scheduler = WarpScheduler()
    kernel = KernelLibrary.vector_add()
    scheduler.submit(kernel)
    assert scheduler.pending_blocks == kernel.grid_size


def test_scheduler_pop_fifo_order():
    scheduler = WarpScheduler()
    first = KernelLibrary.interpolation()
    second = KernelLibrary.vector_add()
    scheduler.submit(first)
    scheduler.submit(second)

    popped = scheduler.pop_ready()
    assert popped is not None
    assert popped.kernel.name == first.name


def test_scheduler_pop_empty_returns_none():
    assert WarpScheduler().pop_ready() is None
