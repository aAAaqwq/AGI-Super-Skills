from pathlib import Path

from tools.deploy_validate import validate_yaml_text


def test_strategy_module_template_is_deploy_validatable():
    root = Path(__file__).resolve().parents[1]
    cfg = root / "research" / "strategy_modules" / "template" / "strategy.yaml"
    errs = validate_yaml_text(cfg.read_text(encoding="utf-8"))
    assert errs == []

