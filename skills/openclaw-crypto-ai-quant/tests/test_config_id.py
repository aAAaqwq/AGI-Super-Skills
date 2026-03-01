from __future__ import annotations

import re

import pytest

from tools.config_id import config_id_from_yaml_text


def test_config_id_is_order_independent_and_ignores_comments() -> None:
    a = """
global:
  trade:
    leverage: 3
    allocation_pct: 0.1
symbols:
  ETH:
    trade:
      leverage: 4
"""
    b = """
# leading comment
symbols:
  ETH:
    trade:
      leverage: 4
global:
  trade:
    allocation_pct: 0.1
    leverage: 3
"""

    ida = config_id_from_yaml_text(a)
    idb = config_id_from_yaml_text(b)

    assert ida == idb
    assert re.fullmatch(r"[0-9a-f]{64}", ida) is not None


def test_config_id_requires_mapping_root() -> None:
    with pytest.raises(ValueError, match="mapping"):
        config_id_from_yaml_text("- 1\n- 2\n")

