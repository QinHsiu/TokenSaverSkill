import json
from pathlib import Path

import _common as common


def test_ensure_runtime_creates_config(ts_home):
    root = common.ensure_runtime()
    assert root == ts_home / ".agent" / "token-saver"
    cfg = root / "config.json"
    assert cfg.is_file()
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data["observationPack"]["tokenThreshold"] == 2000


def test_approx_tokens_heuristic():
    # "a b c" -> 3 words * 1.3 -> ceil 3.9 -> 4
    assert common.approx_tokens("a b c") == 4
