"""ClassicSpeech user guide: NVDA's Add-on Store Help and the user guide command.

The guide in doc/en/readme.html is what NVDA opens from the Add-on Store's Help
action. These tests keep it complete (every command, default gesture and
settings page) and screen-reader friendly, and check that the command opens the
same file NVDA's Add-on Store does.
"""
from __future__ import annotations

import ast
import re
import sys
import tempfile
import types
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "doc" / "en" / "readme.html"
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
	sys.path.insert(0, str(ROOT / "tests"))

import classic_speech_nvda_master_harness as nvda_harness  # noqa: E402
import globalPluginHandler  # noqa: E402
import speech  # noqa: E402


class _GuideParser(HTMLParser):
	"""Collect the guide's language, title, headings, ids, links and text."""

	def __init__(self):
		super().__init__()
		self.lang = None
		self.title = ""
		self.headings = []
		self.ids = set()
		self.links = []
		self._text = []
		self._inTitle = False
		self._heading = None

	def handle_starttag(self, tag, attrs):
		attrs = dict(attrs)
		if tag == "html":
			self.lang = attrs.get("lang")
		if attrs.get("id"):
			self.ids.add(attrs["id"])
		if tag == "title":
			self._inTitle = True
		if re.fullmatch(r"h[1-6]", tag):
			self._heading = [int(tag[1]), "", attrs.get("id")]
		if tag == "a" and attrs.get("href"):
			self.links.append(attrs["href"])

	def handle_endtag(self, tag):
		if tag == "title":
			self._inTitle = False
		if self._heading is not None and tag == f"h{self._heading[0]}":
			level, text, heading_id = self._heading
			self.headings.append((level, " ".join(text.split()), heading_id))
			self._heading = None

	def handle_data(self, data):
		if self._inTitle:
			self.title += data
		if self._heading is not None:
			self._heading[1] += data
		self._text.append(data)

	@property
	def text(self):
		return " ".join(" ".join(self._text).split())


def _parse_guide():
	parser = _GuideParser()
	parser.feed(GUIDE.read_text(encoding="utf-8"))
	parser.close()
	return parser


def _translated_literal(node):
	"""Return the string inside ``_("...")``, or None."""
	if (
		isinstance(node, ast.Call)
		and isinstance(node.func, ast.Name)
		and node.func.id == "_"
		and node.args
		and isinstance(node.args[0], ast.Constant)
		and isinstance(node.args[0].value, str)
	):
		return node.args[0].value
	return None


def _plugin_commands():
	"""Return {script name: description} and {gesture: script name} from classicSpeech.py."""
	tree = ast.parse((ROOT / "classicSpeech.py").read_text(encoding="utf-8"))
	descriptions = {}
	gestures = {}
	for node in ast.walk(tree):
		if isinstance(node, ast.FunctionDef) and node.name.startswith("script_"):
			for decorator in node.decorator_list:
				if not isinstance(decorator, ast.Call):
					continue
				for keyword in decorator.keywords:
					if keyword.arg == "description":
						descriptions[node.name[len("script_"):]] = _translated_literal(keyword.value)
		if isinstance(node, ast.Assign) and any(
			isinstance(target, ast.Name) and target.id == "__gestures" for target in node.targets
		):
			for key, value in zip(node.value.keys, node.value.values):
				gestures[key.value] = value.value
	return descriptions, gestures


def _category_names(relative_path):
	"""Return a settings dialog's CATEGORY_NAMES, as the user hears them."""
	tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
	for node in ast.walk(tree):
		if isinstance(node, ast.Assign) and any(
			isinstance(target, ast.Name) and target.id == "CATEGORY_NAMES" for target in node.targets
		):
			return [_translated_literal(item) for item in node.value.elts]
	raise AssertionError(f"No CATEGORY_NAMES in {relative_path}")


def _manifest_value(key):
	text = (ROOT / "manifest.ini").read_text(encoding="utf-8")
	match = re.search(rf'(?m)^\s*{key}\s*=\s*"?([^"\r\n]*?)"?\s*$', text)
	return match.group(1) if match else None


class UserGuideDocumentTests(unittest.TestCase):
	def test_manifest_names_the_guide_nvda_opens_from_the_addon_store(self):
		self.assertEqual(_manifest_value("docFileName"), "readme.html")
		self.assertTrue(GUIDE.is_file(), GUIDE)

	def test_guide_is_structured_for_screen_readers(self):
		guide = _parse_guide()
		self.assertEqual(guide.lang, "en")
		self.assertEqual(guide.title.strip(), "ClassicSpeech User Guide")
		levels = [level for level, _text, _id in guide.headings]
		self.assertEqual(levels.count(1), 1)
		self.assertEqual(levels[0], 1)
		for previous, current in zip(levels, levels[1:]):
			self.assertLessEqual(current, previous + 1, "a heading level is skipped")
		for level, text, heading_id in guide.headings:
			if level in (2, 3):
				self.assertTrue(heading_id, f"heading without an id: {text}")
		for link in guide.links:
			if link.startswith("#"):
				self.assertIn(link[1:], guide.ids, f"broken link {link}")

	def test_guide_lists_every_command_and_default_gesture(self):
		guide = _parse_guide().text
		descriptions, gestures = _plugin_commands()
		self.assertIn("openClassicSpeechUserGuide", descriptions)
		for name, description in descriptions.items():
			self.assertTrue(description, f"script_{name} has no description")
			self.assertIn(description, guide, f"the guide does not list {description!r}")
		for gesture in gestures:
			self.assertIn(gesture.split(":", 1)[1], guide, f"the guide does not name {gesture}")

	def test_guide_has_a_section_for_every_settings_page(self):
		headings = {text for level, text, _id in _parse_guide().headings if level == 3}
		for relative_path in ("_speech_core/settings/dialog.py", "_speech_core/settings/web/dialog.py"):
			for name in _category_names(relative_path):
				self.assertIn(name, headings, f"no guide section for the {name} page")

	def test_guide_names_the_supported_nvda_versions(self):
		expected = (
			f"NVDA {_manifest_value('minimumNVDAVersion')} through {_manifest_value('lastTestedNVDAVersion')}"
		)
		self.assertIn(expected, _parse_guide().text)


class UserGuideCommandTests(unittest.TestCase):
	def setUp(self):
		nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
		self.module = nvda_harness._import_classic_speech_like_nvda()
		from globalPlugins._speech_core import user_guide

		self.user_guide = user_guide
		self.messages = []
		self._saved = {name: sys.modules.get(name) for name in ("addonHandler", "languageHandler", "ui")}
		ui = types.ModuleType("ui")
		ui.message = self.messages.append
		sys.modules["ui"] = ui
		language = types.ModuleType("languageHandler")
		language.getLanguage = lambda: "en"
		sys.modules["languageHandler"] = language

	def tearDown(self):
		for name, module in self._saved.items():
			if module is None:
				sys.modules.pop(name, None)
			else:
				sys.modules[name] = module
		globalPluginHandler.runningPlugins.clear()
		speech.extensions.filter_speechSequence.callbacks.clear()
		nvda_harness._reset_global_plugin_imports()

	def _install_addon(self, doc_path):
		addon_handler = types.ModuleType("addonHandler")
		addon_handler.getCodeAddon = lambda *args, **kwargs: types.SimpleNamespace(getDocFilePath=lambda: doc_path)
		sys.modules["addonHandler"] = addon_handler

	def test_command_opens_the_file_the_addon_store_help_opens(self):
		self._install_addon(r"C:\addons\ClassicSpeech\doc\en\readme.html")
		opened = []
		self.assertTrue(self.user_guide.open_user_guide(startfile=opened.append))
		self.assertEqual(opened, [r"C:\addons\ClassicSpeech\doc\en\readme.html"])
		self.assertEqual(self.messages, [])

	def test_missing_guide_is_reported_instead_of_opened(self):
		addon_handler = types.ModuleType("addonHandler")

		def not_an_addon(*args, **kwargs):
			raise RuntimeError("Code does not belong to an addon package.")

		addon_handler.getCodeAddon = not_an_addon
		sys.modules["addonHandler"] = addon_handler
		opened = []
		with tempfile.TemporaryDirectory() as empty_root:
			original_root = self.user_guide._ADDON_ROOT
			self.user_guide._ADDON_ROOT = empty_root
			try:
				self.assertFalse(self.user_guide.open_user_guide(startfile=opened.append))
			finally:
				self.user_guide._ADDON_ROOT = original_root
		self.assertEqual(opened, [])
		self.assertEqual(self.messages, ["The ClassicSpeech user guide could not be found."])

	def test_windows_failure_to_open_the_guide_is_spoken(self):
		self._install_addon(r"C:\addons\ClassicSpeech\doc\en\readme.html")

		def refuse(path):
			raise OSError("no program is associated")

		self.assertFalse(self.user_guide.open_user_guide(startfile=refuse))
		self.assertEqual(self.messages, ["The ClassicSpeech user guide could not be opened."])

	def test_language_fallback_matches_nvda(self):
		self.assertEqual(self.user_guide.guide_languages("es_MX"), ["es_MX", "es", "en"])
		self.assertEqual(self.user_guide.guide_languages("fr"), ["fr", "en"])
		self.assertEqual(self.user_guide.guide_languages("en"), ["en"])
		with tempfile.TemporaryDirectory() as root:
			english = Path(root) / "doc" / "en" / "readme.html"
			english.parent.mkdir(parents=True)
			english.write_text("guide", encoding="utf-8")
			self.assertEqual(self.user_guide.find_user_guide_in(root, "fr_CA"), str(english))
			spanish = Path(root) / "doc" / "es" / "readme.html"
			spanish.parent.mkdir(parents=True)
			spanish.write_text("guía", encoding="utf-8")
			self.assertEqual(self.user_guide.find_user_guide_in(root, "es_MX"), str(spanish))
		self.assertIsNone(self.user_guide.find_user_guide_in(str(ROOT / "tests"), "en"))

	def test_plugin_command_has_no_default_gesture_and_opens_the_guide(self):
		descriptions, gestures = _plugin_commands()
		self.assertEqual(descriptions["openClassicSpeechUserGuide"], "Opens the ClassicSpeech user guide")
		self.assertNotIn("openClassicSpeechUserGuide", gestures.values())
		calls = []
		original = self.module.open_user_guide
		self.module.open_user_guide = lambda: calls.append("opened")
		try:
			self.module.GlobalPlugin.script_openClassicSpeechUserGuide(None, None)
		finally:
			self.module.open_user_guide = original
		self.assertEqual(calls, ["opened"])


if __name__ == "__main__":
	unittest.main()
