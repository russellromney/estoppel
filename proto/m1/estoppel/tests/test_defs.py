from estoppel.defs import TOPLEVEL

P = "proj/app/"


def test_comments_docstrings_and_layout_do_not_change_a_hash(tree):
    tree.write({"app/m.py": 'def f(x):\n    """Doc."""\n    return x + 1\n'})
    before = tree.index().defs[P + "m.py::f"].hash
    tree.write({"app/m.py": "# comment\ndef f(x):\n\n    return (x +\n            1)  # why\n"})
    assert tree.index().defs[P + "m.py::f"].hash == before
    tree.write({"app/m.py": "def f(x):\n    return x + 2\n"})
    assert tree.index().defs[P + "m.py::f"].hash != before


def test_each_statement_and_imported_name_is_a_definition(tree):
    tree.write({"app/m.py": """
        import os.path
        from typing import Any, Literal as L
        X = 1
        A, B = 2, 3
        Y: int = 4

        @staticmethod
        def f():
            pass

        class C:
            pass

        if X:
            Z = 5
        """})
    defs = tree.index().modules[P + "m.py"].defs
    assert {did.split("::")[1]: d.kind for did, d in defs.items()} == {
        "import os.path": "import", "from typing import Any": "import",
        "from typing import Literal as L": "import", "X": "value", "A,B": "value", "Y": "value",
        "f": "function", "C": "class", TOPLEVEL: "toplevel"}
    assert defs[P + "m.py::f"].spans == ((7, 9),)       # from the decorator


def test_references_follow_imports_and_re_exports(tree):
    tree.write({
        "app/core/__init__.py": "",
        "app/core/facts.py": "class Order:\n    pass\n",
        "app/core/api.py": "from app.core.facts import Order\n",
        "app/pricing/__init__.py": "",
        "app/pricing/rules.py": "from ..core.api import Order\nRULES = (Order,)\n",
        "app/use.py": "import app.pricing.rules as r\nfrom app.core import api\n"
                      "def f():\n    return r.RULES, api.Order\n",
    })
    index = tree.index()
    refs = set(index.defs[P + "use.py::f"].refs)
    assert P + "pricing/rules.py::RULES" in refs
    assert P + "core/facts.py::Order" in refs
    assert P + "core/api.py::from app.core.facts import Order" in refs
    assert P + "pricing/rules.py::from app.core.api import Order" in index.defs


def test_closure_includes_values_and_classes_but_not_functions_that_did_not_run(tree):
    tree.write({"app/m.py": """
        RATE = 3
        class Box:
            size = RATE
        def helper():
            return 1
        def f():
            return Box(), helper()
        """})
    index = tree.index()
    closure = index.closure([P + "m.py::f"])
    assert closure == {P + "m.py::f", P + "m.py::Box", P + "m.py::RATE"}


def test_code_lines_map_to_their_top_level_definition(tree):
    tree.write({"app/m.py": "class C:\n    def g(self):\n        return 1\n\ndef f():\n    pass\n"})
    index = tree.index()
    path = str(tree.path / "app/m.py")
    assert index.at(path, 2) == [P + "m.py::C"]
    assert index.at(path, 5) == [P + "m.py::f"]
    assert index.at(path, 4) == []
    assert index.at("/elsewhere.py", 1) == []
