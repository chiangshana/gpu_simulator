"""Light tests for the pieces of gpu_simulator.event_listener that don't need a display."""

from gpu_simulator.event_listener import KernelQueue
from gpu_simulator.kernel import KernelLibrary


def test_kernel_queue_drain_returns_in_submission_order():
    queue = KernelQueue(max_size=16)
    first = KernelLibrary.vector_add()
    second = KernelLibrary.interpolation()
    queue.push(first)
    queue.push(second)

    drained = queue.drain(limit=16)
    assert [kernel.name for kernel in drained] == [first.name, second.name]


def test_kernel_queue_drain_respects_limit():
    queue = KernelQueue()
    for _ in range(5):
        queue.push(KernelLibrary.interpolation())
    first_batch = queue.drain(limit=2)
    second_batch = queue.drain(limit=10)
    assert len(first_batch) == 2
    assert len(second_batch) == 3


def test_kernel_queue_silently_drops_when_full():
    queue = KernelQueue(max_size=2)
    for _ in range(10):
        queue.push(KernelLibrary.interpolation())
    drained = queue.drain(limit=100)
    assert len(drained) == 2
