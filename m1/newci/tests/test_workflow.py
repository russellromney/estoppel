"""The workflow end to end, in a temporary git repository."""

import json

import pytest

BASE = {
    "app/prices.py": """
        TAX = 0
        def price(x):
            return x * 2 + TAX
        def unused():
            return 0
        """,
    "app/window.py": "def window():\n    return 30\n",
    "app/registry.py": "ACTIVE = ()\n",
    "tests/test_prices.py": "from app.prices import price\ndef test_price():\n    assert price(2) == 4\n",
    "tests/test_window.py": "from app.window import window\ndef test_window():\n    assert window() >= 30\n",
    "tests/test_registry.py": "from app.registry import ACTIVE\ndef test_active():\n    assert len(ACTIVE) <= 1\n",
}


def gate(tree, *args):
    result = tree.newci("gate", "--report", str(tree.root / "report.json"), *args)
    assert result.returncode in (0, 1, 2), result.stderr
    report = json.loads((tree.root / "report.json").read_text()) if result.returncode != 2 else None
    return result, report


def commit(tree, message, kind):
    tree.git("add", "-A")
    tree.git("commit", "-q", "-m", f"{message}\n\nNewci-Kind: {kind}")


@pytest.fixture
def repo(tree):
    tree.write(BASE)
    tree.git("init", "-q", "-b", "main")
    for key, value in (("user.name", "t"), ("user.email", "t@example.com")):
        tree.git("config", key, value)
    result, report = gate(tree)
    assert result.returncode == 0 and len(report["ran"]) == 3, result.stdout
    tree.git("add", "-A")
    tree.git("commit", "-q", "-m", "base")
    return tree


def test_unchanged_code_reruns_nothing(repo):
    _, report = gate(repo)
    assert report["ran"] == {} and len(report["kept"]) == 3


def test_a_value_that_a_check_used_reruns_it_and_an_unused_function_does_not(repo):
    repo.write({"app/prices.py": BASE["app/prices.py"].replace("return 0", "return 1")})
    assert gate(repo)[1]["ran"] == {}
    repo.write({"app/prices.py": BASE["app/prices.py"].replace("TAX = 0", "TAX = 0 * 1")})
    assert list(gate(repo)[1]["ran"]) == ["tests/test_prices.py::test_price"]


def test_a_failing_check_gets_no_claim(repo):
    repo.write({"app/window.py": "def window():\n    return 1\n"})
    result, report = gate(repo)
    assert result.returncode == 1 and report["failed"] == ["tests/test_window.py::test_window"]
    assert list(gate(repo)[1]["ran"]) == ["tests/test_window.py::test_window"]


def test_the_gate_checks_the_declared_kind(repo):
    repo.write({"app/window.py": "def window():\n    return 31\n"})
    result, _ = gate(repo, "--kind", "publish")
    assert result.returncode == 2 and "changes app/window.py::window" in result.stdout


def test_combine_keeps_each_sides_claims_and_stops_at_a_shared_binding(repo):
    repo.git("checkout", "-q", "-b", "x")
    repo.write({"app/promo.py": "def promo():\n    return 1\n",
                "tests/test_promo.py": "from app.promo import promo\ndef test_promo():\n    assert promo() == 1\n"})
    assert list(gate(repo, "--kind", "publish")[1]["ran"]) == ["tests/test_promo.py::test_promo"]
    commit(repo, "publish promo", "publish")
    repo.write({"app/registry.py": "from app.promo import promo\nACTIVE = (promo,)\n"})
    assert list(gate(repo, "--kind", "activate")[1]["ran"]) == ["tests/test_registry.py::test_active"]
    commit(repo, "activate promo", "activate")

    repo.git("checkout", "-q", "-b", "y", "main")
    repo.write({"app/window.py": "def window():\n    return 31\n"})
    assert list(gate(repo, "--kind", "modify")[1]["ran"]) == ["tests/test_window.py::test_window"]
    commit(repo, "longer window", "modify")

    repo.git("checkout", "-q", "-b", "z", "main")
    repo.write({"app/registry.py": "ACTIVE = (len,)\n"})
    gate(repo, "--kind", "activate")
    commit(repo, "activate len", "activate")

    repo.git("checkout", "-q", "-b", "int", "main")
    result = repo.newci("combine", "x", "y", "--report", str(repo.root / "combine.json"))
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((repo.root / "combine.json").read_text())
    assert report["recheck"] == {} and report["result"]["ran"] == {}
    assert report["kept"] == {"base": 1, "x": 2, "y": 1}
    assert "Newci-Kind: combine" in repo.git("log", "-1", "--format=%B")

    result = repo.newci("combine", "z")
    assert result.returncode == 3
    assert "app/registry.py::ACTIVE (binding): int, z" in result.stdout


def test_combine_rechecks_a_claim_whose_footprint_the_other_side_changed(repo):
    repo.git("checkout", "-q", "-b", "x")
    repo.write({"app/promo.py": "from app.prices import price\ndef promo():\n    return price(1)\n",
                "tests/test_promo.py": "from app.promo import promo\ndef test_promo():\n    assert promo() == 2\n"})
    gate(repo, "--kind", "publish")
    commit(repo, "publish promo", "publish")

    repo.git("checkout", "-q", "-b", "y", "main")
    repo.write({"app/prices.py": BASE["app/prices.py"].replace("TAX = 0", "TAX = 0 * 1")})
    gate(repo, "--kind", "modify")
    commit(repo, "restate tax", "modify")

    repo.git("checkout", "-q", "-b", "int", "main")
    result = repo.newci("combine", "x", "y", "--report", str(repo.root / "combine.json"))
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((repo.root / "combine.json").read_text())
    assert report["recheck"] == {"tests/test_promo.py::test_promo": ["proj/app/prices.py::TAX"]}
    assert list(report["result"]["ran"]) == ["tests/test_promo.py::test_promo"]
    assert report["kept"] == {"base": 2, "y": 1}
    assert "1 use app/prices.py::TAX, changed by y" in result.stdout


def test_combine_refuses_a_change_that_is_not_its_declared_kind(repo):
    repo.git("checkout", "-q", "-b", "x")
    repo.write({"app/window.py": "def window():\n    return 31\n"})
    commit(repo, "claims to publish", "publish")
    repo.git("checkout", "-q", "main")
    result = repo.newci("combine", "x")
    assert result.returncode == 2 and "not the kind it declares" in result.stdout
