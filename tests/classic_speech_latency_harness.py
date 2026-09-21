"""Regression harness for ClassicSpeech 1.02 speech-filter latency.

The Explorer/file-dialog lag came from cross-process work on every speech
sequence: parent walks for focus context and a dialog default-button scan that
ran for every focused object. These tests count accessibility property reads on
fake objects so the expensive paths cannot silently return.
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
import config  # noqa: E402
import controlTypes  # noqa: E402
import globalPluginHandler  # noqa: E402
import speech  # noqa: E402


class CountingObject:
	"""An accessibility object double that counts expensive property reads."""

	def __init__(self, role_name, name="", parent=None, children=(), states=()):
		self._role = getattr(controlTypes.Role, role_name, None) or types.SimpleNamespace(name=role_name)
		self._name = name
		self._parent = parent
		self._children = list(children)
		self.states = set(states)
		self.windowHandle = id(self) % 100000
		self.IAccessibleChildID = 0
		self.treeInterceptor = None
		self.value = ""
		self.reads = {"parent": 0, "role": 0, "children": 0}

	@property
	def role(self):
		self.reads["role"] += 1
		return self._role

	@property
	def name(self):
		return self._name

	@property
	def parent(self):
		self.reads["parent"] += 1
		return self._parent

	@property
	def children(self):
		self.reads["children"] += 1
		return list(self._children)


def _chain(*objects):
	"""Link objects so each one's parent is the next; return them nearest-first."""
	for child, parent in zip(objects, objects[1:]):
		child._parent = parent
	return objects


class LatencyTestBase(unittest.TestCase):
	def setUp(self):
		nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
		self.module = nvda_harness._import_classic_speech_like_nvda()
		from globalPlugins._speech_core import dialog_helpers, focus_ancestry

		self.dialog_helpers = dialog_helpers
		self.focus_ancestry = focus_ancestry
		focus_ancestry.reset_cache()
		dialog_helpers.reset_default_button_cache()
		self._original_get_focus = api.getFocusObject
		self._original_get_ancestors = getattr(api, "getFocusAncestors", None)

	def tearDown(self):
		api.getFocusObject = self._original_get_focus
		if self._original_get_ancestors is None:
			try:
				del api.getFocusAncestors
			except AttributeError:
				pass
		else:
			api.getFocusAncestors = self._original_get_ancestors
		self.focus_ancestry.reset_cache()
		globalPluginHandler.runningPlugins.clear()
		speech.extensions.filter_speechSequence.callbacks.clear()
		nvda_harness._reset_global_plugin_imports()

	def _focus(self, focus, *ancestors_nearest_first):
		ancestors = list(reversed(ancestors_nearest_first))
		api.getFocusObject = lambda: focus
		api.getFocusAncestors = lambda: ancestors


class FocusAncestryTests(LatencyTestBase):
	def test_focus_context_reads_cached_ancestors_without_parent_walk(self):
		desktop = CountingObject("PANE", "Desktop")
		window = CountingObject("WINDOW", "File Explorer")
		items = CountingObject("LIST", "Items View")
		item = CountingObject("LISTITEM", "Documents")
		_chain(item, items, window, desktop)
		self._focus(item, items, window, desktop)
		from globalPlugins._speech_core.base_processor import BaseSpeechProcessor

		processor = BaseSpeechProcessor()
		for _ in range(5):
			self.assertEqual(processor._get_focus_context(), "dialog")
			processor.should_bypass_literal_review(["Documents", "3 of 12"])

		for obj in (item, items, window, desktop):
			self.assertEqual(obj.reads["parent"], 0, obj.name)
		# Ancestor roles are remembered until focus moves.
		self.assertEqual(items.reads["role"], 1)
		self.assertEqual(window.reads["role"], 1)

	def test_focus_change_rebuilds_the_lineage(self):
		menu = CountingObject("POPUPMENU", "Context")
		menu_item = CountingObject("MENUITEM", "Open")
		list_obj = CountingObject("LIST", "Items View")
		list_item = CountingObject("LISTITEM", "Documents")
		from globalPlugins._speech_core.base_processor import BaseSpeechProcessor

		processor = BaseSpeechProcessor()
		self._focus(list_item, list_obj)
		self.assertEqual(processor._get_focus_context(), "dialog")
		self._focus(menu_item, menu)
		self.assertEqual(processor._get_focus_context(), "menu")

	def test_moving_between_items_reuses_container_roles_and_signature(self):
		window = CountingObject("WINDOW", "File Explorer")
		items = CountingObject("LIST", "Items View")
		first = CountingObject("LISTITEM", "Documents")
		second = CountingObject("LISTITEM", "Downloads")
		_chain(first, items, window)
		_chain(second, items, window)
		from globalPlugins._speech_core.base_processor import BaseSpeechProcessor

		processor = BaseSpeechProcessor()
		self._focus(first, items, window)
		signature = processor._get_position_container_signature(first)
		processor._get_focus_context()
		reads_after_first_item = (items.reads["role"], window.reads["role"])
		self._focus(second, items, window)
		self.assertEqual(processor._get_position_container_signature(second), signature)
		processor._get_focus_context()
		# Moving to the next item reads nothing new from the list or window.
		self.assertEqual((items.reads["role"], window.reads["role"]), reads_after_first_item)
		self.assertEqual(second.reads["parent"] + items.reads["parent"], 0)

	def test_dialog_ancestor_is_found_from_cached_ancestry(self):
		dialog = CountingObject("DIALOG", "Browse")
		pane = CountingObject("PANE", "Shell view")
		items = CountingObject("LIST", "Items View")
		item = CountingObject("LISTITEM", "readme.txt")
		_chain(item, items, pane, dialog)
		self._focus(item, items, pane, dialog)

		for _ in range(3):
			self.assertIs(self.dialog_helpers.get_dialog_ancestor(item), dialog)
		self.assertEqual(sum(obj.reads["parent"] for obj in (item, items, pane, dialog)), 0)
		self.assertEqual(dialog.reads["role"], 1)


class DefaultButtonScanTests(LatencyTestBase):
	def _file_dialog(self, default_button=False):
		files = [CountingObject("LISTITEM", f"file {index}") for index in range(300)]
		items = CountingObject("LIST", "Items View", children=files)
		ok_states = {controlTypes.State.DEFAULT} if default_button and hasattr(controlTypes.State, "DEFAULT") else set()
		open_button = CountingObject("BUTTON", "Open", states=ok_states)
		cancel_button = CountingObject("BUTTON", "Cancel")
		pane = CountingObject("PANE", "Shell view", children=[items])
		dialog = CountingObject("DIALOG", "Browse", children=[pane, open_button, cancel_button])
		for child in (pane, open_button, cancel_button):
			child._parent = dialog
		items._parent = pane
		for file_item in files:
			file_item._parent = items
		return dialog, pane, items, files, open_button, cancel_button

	def test_list_item_focus_never_scans_for_the_default_button(self):
		dialog, pane, items, files, _open, _cancel = self._file_dialog()
		focus = files[0]
		self._focus(focus, items, pane, dialog)
		from globalPlugins._speech_core.base_processor import BaseSpeechProcessor
		from globalPlugins._speech_core.tokens import TOKEN_NAME, TOKEN_POSITION, token

		processor = BaseSpeechProcessor()
		processor.verbosity.announce_default_button = True
		tokens = [token(TOKEN_NAME, raw=["file 0"], spoken="file 0"), token(TOKEN_POSITION, raw="1 of 300", spoken="1 of 300")]
		for _ in range(5):
			processor._insert_focused_default_button_token(tokens, focus)

		self.assertEqual(dialog.reads["children"], 0)
		self.assertEqual(items.reads["children"], 0)

	def test_empty_default_button_scan_is_remembered_for_the_dialog(self):
		dialog, pane, items, _files, _open, cancel_button = self._file_dialog()
		self._focus(cancel_button, dialog)
		first = self.dialog_helpers.focused_button_default_status(cancel_button)
		reads_after_first = dialog.reads["children"]
		second = self.dialog_helpers.focused_button_default_status(cancel_button)

		self.assertEqual(first, (True, False, ""))
		self.assertEqual(second, (True, False, ""))
		self.assertGreater(reads_after_first, 0)
		self.assertEqual(dialog.reads["children"], reads_after_first)
		# The file list's contents are never enumerated while scanning.
		self.assertEqual(items.reads["children"], 0)

	def test_explicit_query_rescans_despite_a_recent_empty_scan(self):
		dialog, _pane, _items, _files, _open, cancel_button = self._file_dialog()
		self._focus(cancel_button, dialog)
		self.dialog_helpers.focused_button_default_status(cancel_button)
		before = dialog.reads["children"]
		self.dialog_helpers.get_default_button_name(cancel_button, use_negative_cache=False)
		self.assertGreater(dialog.reads["children"], before)


if __name__ == "__main__":
	unittest.main(verbosity=2)
