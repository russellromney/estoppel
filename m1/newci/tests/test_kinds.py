from newci import kinds

BASE = {
    "app/registry.py": "from app.rules import a\nACTIVE = (a,)\n",
    "app/rules.py": "def a():\n    return 1\n",
    "tests/test_rules.py": "def test_a():\n    assert True\n",
}


def verdict(tree, declared, files):
    tree.write(BASE)
    before = tree.index()
    tree.write(files)
    return kinds.check(declared, before, tree.index(), [])


def test_publish_adds_definitions_only(tree):
    v = verdict(tree, "publish", {"app/rules.py": BASE["app/rules.py"] + "def b():\n    return 2\n",
                                  "tests/test_b.py": "def test_b():\n    pass\n"})
    assert v.ok and v.smallest == "publish" and v.added == 2


def test_publish_may_not_change_a_definition(tree):
    v = verdict(tree, "publish", {"app/rules.py": "def a():\n    return 9\n"})
    assert not v.ok and v.problems == ["changes app/rules.py::a"]


def test_activate_changes_only_bindings(tree):
    v = verdict(tree, "activate", {
        "app/rules.py": BASE["app/rules.py"] + "def b():\n    return 2\n",
        "app/registry.py": "from app.rules import a, b\nACTIVE = (a, b)\n",
        "tests/test_rules.py": "def test_a():\n    assert 1\n"})
    assert v.ok and v.smallest == "activate"
    assert [kinds.short(b, "proj") for b in v.bindings] == [
        "app/registry.py::ACTIVE", "app/registry.py::from app.rules import b"]


def test_activate_may_not_change_other_code(tree):
    v = verdict(tree, "activate", {"app/registry.py": "ACTIVE = ()\n",
                                   "app/rules.py": "def a():\n    return 9\n"})
    assert not v.ok and "changes app/rules.py::a, which is not a binding" in v.problems


def test_activate_must_change_a_binding(tree):
    v = verdict(tree, "activate", {"app/rules.py": BASE["app/rules.py"] + "B = 1\n"})
    assert not v.ok and v.smallest == "publish"


def test_modify_is_anything_and_reports_the_narrowest_kind(tree):
    v = verdict(tree, "modify", {"app/registry.py": "ACTIVE = ()\n"})
    assert v.ok and v.smallest == "activate"
    assert "also qualifies as activate" in kinds.describe(v)
