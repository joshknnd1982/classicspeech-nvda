"""Outlook's message list says "unread" in the focus announcement again (1.17).

NVDA's Outlook app module asks Outlook's object model whether the selected
message is unread while it builds the message's name, and leaves "unread" out
when Outlook doesn't answer. A tester's NVDA 2026.2 log, with ClassicSpeech,
shows that for every message: "From <sender>, Subject <subject>, row <n>" as
the focus arrived, and "unread From <sender>, ..." about 80 ms
later, when Outlook reported a name change. ClassicSpeech now waits for Outlook
before NVDA builds the focused message's name.

These tests load NVDA master's own ``baseObject.py``, so an object's name is
kept for a core cycle exactly as NVDA keeps it, and give the row NVDA 2026.2's
way of asking Outlook, with a fake Outlook that turns calls away for a while,
as Outlook did in the log. They do not start NVDA or Outlook.
"""
from __future__ import annotations

import importlib.util
import sys
import threading
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
import core  # noqa: E402
import globalPluginHandler  # noqa: E402
import logHandler  # noqa: E402
import speech  # noqa: E402

#: RPC_E_CALL_REJECTED: "Call was rejected by callee.", Outlook's answer while it is busy.
CALL_REJECTED = -2147418111
#: RPC_E_WRONG_THREAD: a COM object used on a thread other than the one it belongs to.
WRONG_THREAD = -2147417842
#: The columns of the logged message, as NVDA's Outlook app module reads them.
COLUMNS = "From Contoso News, Subject Morning headlines, Received Thu 9/24/2026 6:31 AM, Size 97 KB,"


def _load_nvda_base_object():
	"""NVDA master's baseObject, which keeps an NVDAObject's properties for a core cycle."""
	if "garbageHandler" not in sys.modules:
		garbage = types.ModuleType("garbageHandler")
		garbage.TrackedObject = type("TrackedObject", (), {})
		sys.modules["garbageHandler"] = garbage
	spec = importlib.util.spec_from_file_location("nvdaMasterBaseObject", nvda_harness.NVDA_SOURCE / "baseObject.py")
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


baseObject = _load_nvda_base_object()


class NVDAObject(baseObject.AutoPropertyObject):
	"""NVDA's NVDAObject as far as its properties go: they are kept until the core cycle ends."""

	cachePropertiesByDefault = True

	def _get_name(self):
		return ""


class _Clock:
	"""time.monotonic and time.sleep for the module: sleeping moves the clock on."""

	def __init__(self):
		self.now = 1000.0
		self.sleeps = []

	def monotonic(self):
		return self.now

	def sleep(self, seconds):
		self.sleeps.append(seconds)
		self.now += seconds

	@property
	def slept(self):
		return sum(self.sleeps)


class _Selection:
	def __init__(self, messages, error):
		self._messages = messages
		self._error = error

	def item(self, index):
		if not self._messages:
			raise self._error(-2147352567, "Array index out of bounds.", None)
		return self._messages[index - 1]


class _Outlook:
	"""Outlook's object model (Outlook.Application), as NVDA's Outlook app module reaches it.

	It turns every call away until ``busyUntil``. When ``thread`` is set, it belongs
	to that thread, as the object model NVDA gets belongs to NVDA's main thread.
	"""

	def __init__(self, clock, error, unread=True, busyFor=0.0, selected=True, explorer=True):
		self.clock = clock
		self.error = error
		self.message = types.SimpleNamespace(unread=unread)
		self.busyUntil = clock.now + busyFor
		self.selected = selected
		self.explorer = explorer
		self.thread = None
		self.calls = 0

	def activeExplorer(self):
		self.calls += 1
		if self.thread is not None and threading.get_ident() != self.thread:
			raise self.error(WRONG_THREAD, "The application called an interface that was marshalled for a different thread.", None)
		if self.clock.now < self.busyUntil:
			raise self.error(CALL_REJECTED, "Call was rejected by callee.", None)
		if not self.explorer:
			return None
		return types.SimpleNamespace(selection=_Selection([self.message] if self.selected else [], self.error))


class OutlookMessageRowTestBase(unittest.TestCase):
	def setUp(self):
		nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
		self.plugin_module = nvda_harness._import_classic_speech_like_nvda()
		from globalPlugins._speech_core import outlook_message_rows

		self.module = outlook_message_rows
		self.clock = _Clock()
		self._saved = {
			"sleep": outlook_message_rows._sleep,
			"monotonic": outlook_message_rows._monotonic,
			"overlay": outlook_message_rows._overlay_class,
			"getFocusObject": api.getFocusObject,
			"mainThreadId": getattr(core, "mainThreadId", None),
		}
		outlook_message_rows._sleep = self.clock.sleep
		outlook_message_rows._monotonic = self.clock.monotonic
		# NVDA's NVDAObject class, which the module takes from NVDAObjects inside NVDA.
		outlook_message_rows._overlay_class = outlook_message_rows.make_overlay_class(NVDAObject)
		outlook_message_rows.reset()
		core.mainThreadId = threading.get_ident()

	def tearDown(self):
		self.module._sleep = self._saved["sleep"]
		self.module._monotonic = self._saved["monotonic"]
		self.module._overlay_class = self._saved["overlay"]
		self.module.reset()
		api.getFocusObject = self._saved["getFocusObject"]
		if self._saved["mainThreadId"] is None:
			try:
				del core.mainThreadId
			except AttributeError:
				pass
		else:
			core.mainThreadId = self._saved["mainThreadId"]
		globalPluginHandler.runningPlugins.clear()
		speech.extensions.filter_speechSequence.callbacks.clear()
		nvda_harness._reset_global_plugin_imports()

	# -- NVDA's Outlook app module, as far as a message's name goes -------------------------------

	def _nvda_row_class(self, module_name="appModules.outlook"):
		COMError = self.module.COMError

		def _get_name(row):
			"""NVDA 2026.2's UIAGridRow._get_name, as far as Outlook's object model goes."""
			row.nameBuilds.append(threading.get_ident())
			textList = []
			selection = None
			if row.appModule.nativeOm:
				try:
					selection = row.appModule.nativeOm.activeExplorer().selection.item(1)
				except COMError:
					pass
			if selection:
				try:
					unread = selection.unread
				except COMError:
					unread = False
				# Translators: when an email is unread
				if unread:
					textList.append("unread")
			textList.append(COLUMNS)
			return " ".join(textList)

		return type(NVDAObject)("UIAGridRow", (NVDAObject,), {"__module__": module_name, "_get_name": _get_name})

	def _build(self, clsList):
		"""Build the object's class from ``clsList`` as NVDA's DynamicNVDAObjectType does."""
		bases = []
		for index, cls in enumerate(clsList):
			if index == 0 or not issubclass(clsList[index - 1], cls):
				bases.append(cls)
		if len(bases) == 1:
			return bases[0]
		name = "Dynamic_" + "".join(cls.__name__ for cls in clsList)
		return type(NVDAObject)(name, tuple(bases), {"__module__": __name__})

	def _row(self, outlook, focused=True, module_name="appModules.outlook"):
		clsList = [self._nvda_row_class(module_name), NVDAObject]
		self.module.choose_overlay_classes(None, clsList)
		row = self._build(clsList)()
		row.appModule = types.SimpleNamespace(nativeOm=outlook)
		row.nameBuilds = []
		if focused:
			api.getFocusObject = lambda: row
		return row

	def _outlook(self, **kwargs):
		return _Outlook(self.clock, self.module.COMError, **kwargs)


class OverlayChoiceTests(OutlookMessageRowTestBase):
	def test_a_row_of_outlooks_message_list_gets_the_overlay_first(self):
		for module_name in ("appModules.outlook", "nvdaBuiltin.appModules.outlook"):
			with self.subTest(module_name):
				row_class = self._nvda_row_class(module_name)
				clsList = [row_class, NVDAObject]
				self.module.choose_overlay_classes(None, clsList)
				self.assertIs(clsList[0], self.module._overlay_class)
				self.assertEqual(clsList[1:], [row_class, NVDAObject])

	def test_outlook_extended_rows_get_it_too(self):
		# Outlook Extended 3.4 puts its own row class, built on NVDA's, in front of NVDA's.
		nvda_row = self._nvda_row_class("nvdaBuiltin.appModules.outlook")
		extended_row = type(NVDAObject)("UIAGridRowWithReadStatus", (nvda_row,), {"__module__": "appModules.outlook"})
		clsList = [extended_row, nvda_row, NVDAObject]
		self.module.choose_overlay_classes(None, clsList)
		self.assertEqual(clsList, [self.module._overlay_class, extended_row, nvda_row, NVDAObject])
		row = self._build(clsList)()
		row.appModule = types.SimpleNamespace(nativeOm=self._outlook(busyFor=0.08))
		row.nameBuilds = []
		api.getFocusObject = lambda: row
		self.assertEqual(row.name, "unread " + COLUMNS)

	def test_other_objects_are_left_alone(self):
		other_grid_row = type(NVDAObject)("UIAGridRow", (NVDAObject,), {"__module__": "appModules.thunderbird"})
		list_item = type(NVDAObject)("ListItem", (NVDAObject,), {"__module__": "NVDAObjects.UIA"})
		for clsList in ([other_grid_row, NVDAObject], [list_item, NVDAObject], [NVDAObject], []):
			with self.subTest([cls.__name__ for cls in clsList]):
				before = list(clsList)
				self.module.choose_overlay_classes(None, clsList)
				self.assertEqual(clsList, before)

	def test_the_overlay_is_added_once(self):
		clsList = [self._nvda_row_class(), NVDAObject]
		self.module.choose_overlay_classes(None, clsList)
		self.module.choose_overlay_classes(None, clsList)
		self.assertEqual(clsList.count(self.module._overlay_class), 1)

	def test_choosing_never_raises(self):
		# NVDA calls this for every object it creates; an error would lose the object.
		self.module.choose_overlay_classes(None, None)
		self.module.choose_overlay_classes(None, [object(), 3, None])

	def test_the_plugin_passes_every_object_to_the_module(self):
		plugin_class = self.plugin_module.GlobalPlugin
		# NVDA only calls a plugin's chooseNVDAObjectOverlayClasses when its class defines one.
		self.assertIn("chooseNVDAObjectOverlayClasses", plugin_class.__dict__)
		plugin = plugin_class()
		globalPluginHandler.runningPlugins.append(plugin)
		self.addCleanup(plugin.terminate)
		row_class = self._nvda_row_class("nvdaBuiltin.appModules.outlook")
		clsList = [row_class, NVDAObject]
		plugin.chooseNVDAObjectOverlayClasses(None, clsList)
		self.assertEqual(clsList, [self.module._overlay_class, row_class, NVDAObject])


class FocusAnnouncementTests(OutlookMessageRowTestBase):
	def test_logged_message_is_announced_as_unread_when_outlook_answers_late(self):
		# The tester's log: Outlook answered about 80 ms after NVDA asked.
		outlook = self._outlook(busyFor=0.08)
		row = self._row(outlook)
		logHandler.log.messages.clear()
		self.assertEqual(row.name, "unread " + COLUMNS)
		self.assertGreaterEqual(self.clock.slept, 0.08)
		self.assertLess(self.clock.slept, 0.08 + self.module.WAIT_STEP + 1e-9)
		# NVDA built the name once, after Outlook answered.
		self.assertEqual(len(row.nameBuilds), 1)
		# The debug log says how long Outlook took, for the next report.
		self.assertTrue(
			any(level == "debug" and "Outlook answered after" in text for level, text in logHandler.log.messages),
			logHandler.log.messages,
		)

	def test_nvda_alone_leaves_unread_out_while_outlook_is_busy(self):
		# What the log shows: NVDA's own name for the row, without ClassicSpeech's class.
		clsList = [self._nvda_row_class(), NVDAObject]
		row = self._build(clsList)()
		row.appModule = types.SimpleNamespace(nativeOm=self._outlook(busyFor=0.08))
		row.nameBuilds = []
		api.getFocusObject = lambda: row
		self.assertEqual(row.name, COLUMNS)

	def test_the_name_change_that_follows_says_nothing_new(self):
		# In the log, Outlook's name change 80 ms later made NVDA read the whole message again, now with "unread".
		# NVDA only speaks a changed name, and it is the same name now.
		outlook = self._outlook(busyFor=0.08)
		row = self._row(outlook)
		focus_name = row.name
		row.invalidateCache()  # NVDA's core cycle ends.
		self.clock.now += 0.08
		self.assertEqual(row.name, focus_name)

	def test_no_wait_when_outlook_answers_at_once(self):
		row = self._row(self._outlook())
		self.assertEqual(row.name, "unread " + COLUMNS)
		self.assertEqual(self.clock.sleeps, [])

	def test_a_read_message_is_announced_without_unread(self):
		row = self._row(self._outlook(unread=False, busyFor=0.05))
		self.assertEqual(row.name, COLUMNS)

	def test_the_name_is_kept_for_the_core_cycle(self):
		outlook = self._outlook(busyFor=0.04)
		row = self._row(outlook)
		for _ in range(3):
			self.assertEqual(row.name, "unread " + COLUMNS)
		self.assertEqual(len(row.nameBuilds), 1)
		waited = self.clock.slept
		row.invalidateCache()
		self.assertEqual(row.name, "unread " + COLUMNS)
		self.assertEqual(len(row.nameBuilds), 2)
		self.assertEqual(self.clock.slept, waited)

	def test_only_the_focus_waits(self):
		# Object navigation and braille can ask for other rows; Outlook's selection isn't theirs.
		row = self._row(self._outlook(busyFor=0.08), focused=False)
		api.getFocusObject = lambda: None
		self.assertEqual(row.name, COLUMNS)
		self.assertEqual(self.clock.sleeps, [])

	def test_no_wait_before_nvda_has_outlooks_object_model(self):
		# NVDA gets it itself the first time, and may show its "Waiting for Outlook..." dialog.
		row = self._row(None)
		self.assertEqual(row.name, COLUMNS)
		self.assertEqual(self.clock.sleeps, [])

	def test_no_wait_without_a_message_list_window(self):
		# Outlook's activeExplorer() is None when no Outlook window with a message list is active.
		outlook = self._outlook(explorer=False)
		answer, error = self.module.ask_outlook(outlook)
		self.assertIsNone(answer)
		self.assertIsInstance(error, AttributeError)
		self.module.wait_for_object_model(types.SimpleNamespace(nativeOm=outlook))
		self.assertEqual(self.clock.sleeps, [])

	def test_a_selection_that_is_still_empty_is_waited_for(self):
		outlook = self._outlook(selected=False)
		row = self._row(outlook)

		def select_later(seconds, sleep=self.clock.sleep):
			sleep(seconds)
			if self.clock.slept >= 0.05:
				outlook.selected = True

		self.module._sleep = select_later
		self.assertEqual(row.name, "unread " + COLUMNS)


class GivingUpTests(OutlookMessageRowTestBase):
	def test_waiting_stops_at_the_limit(self):
		outlook = self._outlook(busyFor=10.0)
		row = self._row(outlook)
		logHandler.log.messages.clear()
		self.assertEqual(row.name, COLUMNS)
		self.assertGreaterEqual(self.clock.slept, self.module.WAIT_LIMIT - 1e-9)
		self.assertLess(self.clock.slept, self.module.WAIT_LIMIT + self.module.WAIT_STEP + 1e-9)
		# The debug log names Outlook's answer, such as "Call was rejected by callee."
		self.assertTrue(
			any(
				level == "debugWarning" and "Call was rejected by callee." in text
				for level, text in logHandler.log.messages
			),
			logHandler.log.messages,
		)

	def test_after_giving_up_nothing_waits_until_outlook_answers_again(self):
		outlook = self._outlook(busyFor=10.0)
		first = self._row(outlook)
		self.assertEqual(first.name, COLUMNS)
		waited = self.clock.slept

		second = self._row(outlook)
		self.assertEqual(second.name, COLUMNS)
		self.assertEqual(self.clock.slept, waited)

		# Outlook answers again: the next message waits once more when Outlook is busy.
		self.clock.now = outlook.busyUntil
		self.assertEqual(self._row(outlook).name, "unread " + COLUMNS)
		outlook.busyUntil = self.clock.now + 0.06
		self.assertEqual(self._row(outlook).name, "unread " + COLUMNS)
		self.assertGreater(self.clock.slept, waited)


class ThreadTests(OutlookMessageRowTestBase):
	def test_a_name_built_on_another_thread_is_not_kept(self):
		# The object model belongs to NVDA's main thread; elsewhere NVDA's name lacks "unread".
		outlook = self._outlook()
		outlook.thread = threading.get_ident()
		row = self._row(outlook)
		names = []
		worker = threading.Thread(target=lambda: names.append(row.name))
		worker.start()
		worker.join()
		self.assertEqual(names, [COLUMNS])
		# Still in the same core cycle, NVDA's main thread gets the full name, not the other thread's.
		self.assertEqual(row.name, "unread " + COLUMNS)
		self.assertEqual(len(row.nameBuilds), 2)
		self.assertEqual(self.clock.sleeps, [])


if __name__ == "__main__":
	unittest.main()
