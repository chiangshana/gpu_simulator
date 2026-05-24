"""Plugin 系統 — 從 ``~/.gpu_simulator/plugins/`` 自動載入使用者外掛。

每個 plugin 是一個 .py 檔,可以選擇性提供以下 hook(都不是必填):

- ``def register_kernels() -> dict[str, callable]``
  回傳 ``{kernel_name: factory_function}`` 字典,工廠拿一個 ``trigger`` 參數,
  回傳 :class:`gpu_simulator.kernel.Kernel` 物件。

- ``def register_examples() -> dict[str, str]``
  回傳 ``{filename: asm_source}`` 字典,讓使用者的 .asm 範例自動顯示在 Input 分頁。

- ``def register_themes() -> list[gpu_simulator.themes.Theme]``
  回傳新主題列表,加進主題下拉選單。

整個 plugin loader 是純 Python,沒有 Qt 相依,可以單獨測試。
**任何 plugin 載入失敗(語法錯、import 錯、API 不對)都不會影響 widget 啟動**,
頂多在 :class:`PluginRegistry.load_errors` 留下記錄。
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from gpu_simulator.kernel import Kernel
from gpu_simulator.themes import Theme

PLUGIN_DIR_ENV = "GPU_SIMULATOR_PLUGIN_DIR"


@dataclass
class PluginLoadError:
    plugin_path: Path
    message: str


@dataclass
class LoadedPlugin:
    name: str
    path: Path
    kernel_factories: dict[str, Callable[[str], Kernel]] = field(default_factory=dict)
    examples: dict[str, str] = field(default_factory=dict)
    themes: list[Theme] = field(default_factory=list)


@dataclass
class PluginRegistry:
    """匯整所有成功載入的 plugin 提供的東西。"""

    plugins: list[LoadedPlugin] = field(default_factory=list)
    load_errors: list[PluginLoadError] = field(default_factory=list)

    def all_kernel_factories(self) -> dict[str, Callable[[str], Kernel]]:
        merged: dict[str, Callable[[str], Kernel]] = {}
        for plugin in self.plugins:
            merged.update(plugin.kernel_factories)
        return merged

    def all_examples(self) -> dict[str, str]:
        merged: dict[str, str] = {}
        for plugin in self.plugins:
            merged.update(plugin.examples)
        return merged

    def all_themes(self) -> list[Theme]:
        themes: list[Theme] = []
        for plugin in self.plugins:
            themes.extend(plugin.themes)
        return themes


# ---------------------------------------------------------------------------
# 公用 API
# ---------------------------------------------------------------------------
def default_plugin_dir() -> Path:
    """``~/.gpu_simulator/plugins`` 或環境變數 ``GPU_SIMULATOR_PLUGIN_DIR``。"""
    import os

    override = os.environ.get(PLUGIN_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".gpu_simulator" / "plugins"


def load_plugins(directory: Path | str | None = None) -> PluginRegistry:
    """掃描 ``directory`` 下所有 .py 檔並嘗試載入。

    永遠回一個 :class:`PluginRegistry`(失敗的記在 ``load_errors``)。
    """
    directory = Path(directory) if directory is not None else default_plugin_dir()
    registry = PluginRegistry()
    if not directory.exists() or not directory.is_dir():
        return registry

    for plugin_path in sorted(directory.glob("*.py")):
        try:
            module = _load_module(plugin_path)
            loaded = _extract_plugin_data(module, plugin_path)
            registry.plugins.append(loaded)
        except Exception as exc:
            registry.load_errors.append(
                PluginLoadError(plugin_path=plugin_path, message=str(exc))
            )
    return registry


# ---------------------------------------------------------------------------
# 內部實作
# ---------------------------------------------------------------------------
def _load_module(plugin_path: Path):
    module_name = f"_gpu_simulator_plugin_{plugin_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, plugin_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"無法從 {plugin_path} 建立 module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _extract_plugin_data(module, plugin_path: Path) -> LoadedPlugin:
    plugin = LoadedPlugin(
        name=plugin_path.stem,
        path=plugin_path,
    )

    register_kernels = getattr(module, "register_kernels", None)
    if callable(register_kernels):
        result = register_kernels()
        if isinstance(result, dict):
            for name, factory in result.items():
                if isinstance(name, str) and callable(factory):
                    plugin.kernel_factories[name] = factory

    register_examples = getattr(module, "register_examples", None)
    if callable(register_examples):
        result = register_examples()
        if isinstance(result, dict):
            for filename, source in result.items():
                if isinstance(filename, str) and isinstance(source, str):
                    plugin.examples[filename] = source

    register_themes = getattr(module, "register_themes", None)
    if callable(register_themes):
        result = register_themes()
        if isinstance(result, list):
            for theme in result:
                if isinstance(theme, Theme):
                    plugin.themes.append(theme)

    return plugin
