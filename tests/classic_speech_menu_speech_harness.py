"""Menus that stay audible.

NVDA cancels speech as focus enters a popup menu and attaches a focus-scoped
cancellation marker to every announcement it builds for a focus event. Its
speech manager throws away an utterance whose marker has expired *together with
everything still queued behind it*. So anything ClassicSpeech holds back and
speaks again later, or merges into another object's announcement, must travel
without that marker and must be abandoned once the focus has moved on.
Otherwise the item a menu opens on is silenced by ClassicSpeech's own delayed
speech, which is what happened to the keyboard layout menu NVDA opens while
adding an input gesture.

Whatever else happens, menu speech that ClassicSpeech leaves with no words at
all falls back to NVDA's own text: a menu you cannot hear is a dead end.
"""
from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
	sys.path.insert(0, str(ROOT / "tests"))

import classic_speech_nvda_master_harness as nvda_harness  # noqa: E402
import api  # noqa: E402
import controlTypes  # noqa: E402
import globalPluginHandler  # noqa: E402
import speech  # noqa: E402
from speech.commands import _CancellableSpeechCommand  # noqa: E402


class FakeObject:
	"""An accessible object, as the speech hook reads one."""

	def __init__(self, role_name, name, parent=None, window=1):
		self.role = getattr(controlTypes.Role, role_name, None) or types.SimpleNamespace(name=role_name)
		self.name = name
		self.parent = parent
		self.states = set()
		self.value = ""
		self.windowHandle = window
		self.processID = 100
		self.IAccessibleChildID = 0
		self.treeInterceptor = None


class SpeechTestBase(unittest.TestCase):
	def setUp(self):
		nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
		self.module = nvda_harness._import_classic_speech_like_nvda()
		from globalPlugins._speech_core import focus_ancestry

		self.focus_ancestry = focus_ancestry
		self._original_get_focus = api.getFocusObject
		self._original_get_ancestors = getattr(api, "getFocusAncestors", None)

	def tearDown(self):
		api.getFocusObject = self._original_get_focus
		if self._original_get_ancestors is not None:
			api.getFocusAncestors = self._original_get_ancestors
		self.focus_ancestry.reset_cache()
		globalPluginHandler.runningPlugins.clear()
		speech.extensions.filter_speechSequence.callbacks.clear()
		nvda_harness._reset_global_plugin_imports()

	def plugin(self):
		plugin = self.module.GlobalPlugin()
		globalPluginHandler.runningPlugins.append(plugin)
		self.addCleanup(plugin.terminate)
		plugin.processor._safe_selected_text = lambda _focus: ""
		return plugin

	def focus(self, obj, *ancestors_nearest_first):
		api.getFocusObject = lambda: obj
		api.getFocusAncestors = lambda: list(reversed(ancestors_nearest_first))
		self.focus_ancestry.reset_cache()

	def words(self, sequence):
		return [entry for entry in sequence if isinstance(entry, str) and entry.strip()]


class HeldContainerSpeechTests(SpeechTestBase):
	def _dialog_with_tree(self):
		dialog = FakeObject("DIALOG", "Input Gestures")
		tree = FakeObject("TREEVIEW", "Gestures")
		tree.parent = dialog
		return dialog, tree

	def test_a_held_container_is_dropped_once_the_focus_has_moved(self):
		"""The first item of a menu that has just opened must still be heard."""
		plugin = self.plugin()
		dialog, tree = self._dialog_with_tree()
		row = FakeObject("TREEVIEWITEM", "Enter input gesture:", tree)
		self.focus(row, tree, dialog)

		self.assertEqual(plugin._filterSpeechSequence(["Gestures", "tree view"]), [])
		self.assertIsNotNone(plugin._pendingContainerSequence)

		# The keystroke is captured and the keyboard layout menu opens.
		menu = FakeObject("POPUPMENU", "", dialog, window=2)
		item = FakeObject("MENUITEM", "control+f (desktop keyboard)", menu, window=2)
		self.focus(item, menu, dialog)

		speech.speak_calls.clear()
		plugin._flush_pending_container_sequence()
		self.assertEqual(speech.speak_calls, [])

	def test_a_held_container_is_still_spoken_while_the_focus_stays_put(self):
		plugin = self.plugin()
		dialog, tree = self._dialog_with_tree()
		row = FakeObject("TREEVIEWITEM", "Enter input gesture:", tree)
		self.focus(row, tree, dialog)

		self.assertEqual(plugin._filterSpeechSequence(["Gestures", "tree view"]), [])
		speech.speak_calls.clear()
		plugin._flush_pending_container_sequence()

		self.assertTrue(speech.speak_calls)
		self.assertIn("tree view", speech.speak_calls[-1])

	def test_a_held_container_never_carries_nvdas_cancellation_marker(self):
		plugin = self.plugin()
		dialog, tree = self._dialog_with_tree()
		row = FakeObject("TREEVIEWITEM", "Enter input gesture:", tree)
		self.focus(row, tree, dialog)

		marker = _CancellableSpeechCommand(tree)
		self.assertEqual(plugin._filterSpeechSequence(["Gestures", "tree view", marker]), [])
		held = plugin._pendingContainerSequence
		for key in ("raw", "core"):
			self.assertNotIn(marker, held[key], key)

	def test_a_container_from_an_earlier_focus_is_not_merged_into_this_one(self):
		plugin = self.plugin()
		dialog, tree = self._dialog_with_tree()
		row = FakeObject("TREEVIEWITEM", "Enter input gesture:", tree)
		self.focus(row, tree, dialog)
		self.assertEqual(plugin._filterSpeechSequence(["Gestures", "tree view"]), [])

		menu = FakeObject("POPUPMENU", "", dialog, window=2)
		item = FakeObject("MENUITEM", "control+f (desktop keyboard)", menu, window=2)
		self.focus(item, menu, dialog)

		output = plugin._filterSpeechSequence(["control+f (desktop keyboard)", "1 of 2"])
		self.assertIn("control+f (desktop keyboard)", self.words(output))
		self.assertNotIn("tree view", self.words(output))
		self.assertIsNone(plugin._pendingContainerSequence)

	def test_every_item_of_the_keyboard_layout_menu_is_read(self):
		plugin = self.plugin()
		dialog = FakeObject("DIALOG", "Input Gestures")
		menu = FakeObject("POPUPMENU", "", dialog, window=2)
		for position, name in (
			("1 of 2", "control+f (desktop keyboard)"),
			("2 of 2", "control+f (keyboard, all layouts)"),
		):
			item = FakeObject("MENUITEM", name, menu, window=2)
			self.focus(item, menu, dialog)
			output = plugin._filterSpeechSequence([name, position])
			self.assertIn(name, self.words(output), name)


class MenuIsNeverSilentTests(SpeechTestBase):
	def test_menu_speech_falls_back_to_nvdas_own_words(self):
		from globalPlugins._speech_core.base_processor import BaseSpeechProcessor

		dialog = FakeObject("DIALOG", "Input Gestures")
		menu = FakeObject("POPUPMENU", "", dialog)
		item = FakeObject("MENUITEM", "control+f (desktop keyboard)", menu)
		self.focus(item, menu, dialog)

		processor = BaseSpeechProcessor()
		native = ["control+f (desktop keyboard)", "1 of 2"]
		rescued = processor._ensure_menu_context_not_silent([], [], "menu", native)
		self.assertEqual(rescued, native)

	def test_a_root_popup_menu_keeps_its_short_marker(self):
		from globalPlugins._speech_core.base_processor import BaseSpeechProcessor

		dialog = FakeObject("DIALOG", "Input Gestures")
		menu = FakeObject("POPUPMENU", "", dialog)
		self.focus(menu, dialog)

		processor = BaseSpeechProcessor()
		self.assertEqual(processor._ensure_menu_context_not_silent([], [], "menu", ["menu"]), ["menu"])

	def test_speech_outside_a_menu_is_left_alone(self):
		from globalPlugins._speech_core.base_processor import BaseSpeechProcessor

		dialog = FakeObject("DIALOG", "Settings")
		box = FakeObject("CHECKBOX", "Report page numbers", dialog)
		self.focus(box, dialog)

		processor = BaseSpeechProcessor()
		self.assertEqual(processor._ensure_menu_context_not_silent([], [], "dialog", ["anything"]), [])


if __name__ == "__main__":
	unittest.main(verbosity=2)
