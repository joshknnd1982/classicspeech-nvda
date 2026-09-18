"""ClassicSpeech runtime code may import only modules NVDA ships.

NVDA runs add-ons on its own bundled Python. That bundle holds NVDA's modules
and the standard library modules NVDA's source imports, not the whole standard
library. ClassicSpeech 1.05 imported ``filecmp``, which NVDA does not ship, so
the plugin failed to load: no ClassicSpeech menu, no Input Gestures category,
and no speech processing. The other harnesses run on a full Python and cannot
notice that, so this test checks every runtime import against NVDA's source.
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tests") not in sys.path:
	sys.path.insert(0, str(ROOT / "tests"))

import classic_speech_nvda_master_harness as nvda_harness  # noqa: E402

# Standard library modules that NVDA's build bundles although NVDA's source does
# not import them directly; they come in with modules it does import. Each was
# checked in NVDA 2026.2's library.zip. Add a module only after the same check.
_SHIPPED_INDIRECTLY = {"calendar", "contextvars"}


def _imports(path):
	"""Yield ``(top-level module, line)`` for every absolute import in ``path``.

	Imports inside functions and try blocks count too: they fail the same way
	when they run.
	"""
	tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
	for node in ast.walk(tree):
		if isinstance(node, ast.Import):
			for alias in node.names:
				yield alias.name.split(".", 1)[0], node.lineno
		elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
			yield node.module.split(".", 1)[0], node.lineno


def _modules_nvda_ships(source):
	"""Return NVDA's own modules plus every module its source imports, which its build bundles."""
	own = {path.stem for path in source.glob("*.py")}
	own |= {path.name for path in source.iterdir() if path.is_dir()}
	imported = set()
	for path in source.rglob("*.py"):
		try:
			imported |= {name for name, _line in _imports(path)}
		except SyntaxError:
			continue
	return own | imported | set(sys.builtin_module_names) | _SHIPPED_INDIRECTLY


def _runtime_files():
	files = [ROOT / "classicSpeech.py"]
	files += sorted((ROOT / "_speech_core").rglob("*.py"))
	files += sorted((ROOT / "appModules").rglob("*.py"))
	return files


class RuntimeImportTests(unittest.TestCase):
	def test_runtime_code_imports_only_modules_nvda_ships(self):
		available = _modules_nvda_ships(nvda_harness.NVDA_SOURCE)
		missing = []
		for path in _runtime_files():
			for name, line in _imports(path):
				if name != "__future__" and name not in available:
					missing.append(f"{path.relative_to(ROOT).as_posix()}:{line} imports {name}")
		self.assertEqual(missing, [], "NVDA does not ship these modules, so ClassicSpeech would fail to load")

	def test_the_check_sees_imports_inside_functions(self):
		source = ROOT / "tests" / "classic_speech_runtime_imports_harness.py"
		names = {name for name, _line in _imports(source)}
		self.assertTrue({"ast", "sys", "unittest", "pathlib"} <= names)
		self.assertIn("classicSpeech.py", [path.name for path in _runtime_files()])


if __name__ == "__main__":
	unittest.main()
