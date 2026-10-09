import builtins
import importlib.util
import sys
from pathlib import Path


def _load_basic_agent_demo():
    path = Path(__file__).resolve().parents[2] / "demos" / "basic-agent.py"
    spec = importlib.util.spec_from_file_location("basic_agent_demo", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_calculator_preserves_arithmetic_precedence():
    module = _load_basic_agent_demo()

    assert module.calculator_tool("2 + 3 * 4") == "🧮 计算结果: 2 + 3 * 4 = 14"


def test_calculator_rejects_code_execution_syntax(monkeypatch):
    module = _load_basic_agent_demo()
    imports = []
    original_import = builtins.__import__

    def record_import(*args, **kwargs):
        imports.append(args[0])
        return original_import(*args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", record_import)

    result = module.calculator_tool("__import__('os').getcwd()")

    assert result.startswith("❌ 计算失败:")
    assert "os" not in imports


def test_calculator_bounds_expression_complexity_and_arithmetic():
    module = _load_basic_agent_demo()

    too_complex = module.calculator_tool(" + ".join(["1"] * 40))
    division_by_zero = module.calculator_tool("1 / 0")
    excessive_power = module.calculator_tool("2 ** 101")

    assert too_complex.startswith("❌ 计算失败:")
    assert division_by_zero.startswith("❌ 计算失败:")
    assert excessive_power.startswith("❌ 计算失败:")
