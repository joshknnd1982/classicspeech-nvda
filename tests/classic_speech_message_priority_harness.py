"""Give ClassicSpeech messages priority over NVDA speech (Misc page).

ClassicSpeech's own messages go through ``message_priority.speak_message``.
With the option off they are NVDA's ``ui.message``, unchanged. With it on they
are spoken at NVDA's highest priority, and NVDA's automatic "cancel speech"
calls are held off until the message has been spoken, unless the user presses
a key. These tests use fakes with the call shapes of NVDA 2026.2's speech,
braille and input modules; they do not start NVDA.
"""
from __future__ import annotations

import re
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
import config  # noqa: E402
import globalPluginHandler  # noqa: E402
import speech  # noqa: E402
import speech.priorities  # noqa: E402
import ui  # noqa: E402


class _Action:
	"""NVDA's extensionPoints.Action, as far as ClassicSpeech uses it."""

	def __init__(self):
		self.handlers = []

	def register(self, handler):
		self.handlers.append(handler)

	def unregister(self, handler):
		if handler in self.handlers:
			self.handlers.remove(handler)

	def notify(self, **kwargs):
		for handler in list(self.handlers):
			handler(**kwargs)


class _Decider(_Action):
	"""NVDA's extensionPoints.Decider: any false answer stops the gesture."""

	def decide(self, **kwargs):
		for handler in list(self.handlers):
			if not handler(**kwargs):
				return False
		return True


def _caller(module_name, function_name):
	"""Return a function named ``function_name`` in a module named ``module_name`` that cancels speech."""
	namespace = {"__name__": module_name, "speech": speech}
	exec(f"def {function_name}():\n\treturn speech.cancelSpeech()\n", namespace)
	return namespace[function_name]


#: An application event handler, which cancels speech on its own.
nvda_event = _caller("NVDAObjects", "event_foreground")


class MessagePriorityHarnessBase(unittest.TestCase):
	def setUp(self):
		nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
		self.canceled = []
		self.spoken = []
		self.brailled = []
		self._saved = {
			"cancelSpeech": getattr(speech, "cancelSpeech", None),
			"speechModule": getattr(speech, "speech", None),
			"speechCanceled": getattr(speech.extensions, "speechCanceled", None),
			"Spri": speech.priorities.Spri,
			"braille": sys.modules.get("braille"),
			"keyboardHandler": sys.modules.get("keyboardHandler"),
			"decider": getattr(sys.modules["inputCore"], "decide_executeGesture", None),
		}
		speech.cancelSpeech = self._nvda_cancel
		speech.speech = types.SimpleNamespace(speak=self._nvda_speak)
		speech.extensions.speechCanceled = _Action()
		speech.priorities.Spri = types.SimpleNamespace(NORMAL="normal", NEXT="next", NOW="now")
		braille = types.ModuleType("braille")
		braille.handler = types.SimpleNamespace(message=self.brailled.append)
		sys.modules["braille"] = braille
		self.keyboard = types.ModuleType("keyboardHandler")
		self.keyboard.keyCounter = 0
		sys.modules["keyboardHandler"] = self.keyboard
		self.decider = _Decider()
		sys.modules["inputCore"].decide_executeGesture = self.decider
		ui.messages.clear()
		speech.speak_calls.clear()
		self.section = config.conf.profiles[0].setdefault("classicSpeech", {})
		self.module = nvda_harness._import_classic_speech_like_nvda()
		from globalPlugins._speech_core import message_priority

		self.priority = message_priority
		self.plugin = self.module.GlobalPlugin()
		globalPluginHandler.runningPlugins.append(self.plugin)

	def tearDown(self):
		try:
			self.plugin.terminate()
		finally:
			globalPluginHandler.runningPlugins.clear()
			speech.extensions.filter_speechSequence.callbacks.clear()
			nvda_harness._reset_global_plugin_imports()
			for name in ("cancelSpeech",):
				if self._saved[name] is None:
					speech.__dict__.pop(name, None)
				else:
					setattr(speech, name, self._saved[name])
			if self._saved["speechModule"] is None:
				speech.__dict__.pop("speech", None)
			else:
				speech.speech = self._saved["speechModule"]
			if self._saved["speechCanceled"] is None:
				speech.extensions.__dict__.pop("speechCanceled", None)
			else:
				speech.extensions.speechCanceled = self._saved["speechCanceled"]
			speech.priorities.Spri = self._saved["Spri"]
			for name in ("braille", "keyboardHandler"):
				if self._saved[name] is None:
					sys.modules.pop(name, None)
				else:
					sys.modules[name] = self._saved[name]
			if self._saved["decider"] is None:
				sys.modules["inputCore"].__dict__.pop("decide_executeGesture", None)
			else:
				sys.modules["inputCore"].decide_executeGesture = self._saved["decider"]

	# -- NVDA fakes ---------------------------------------------------------
	def _nvda_cancel(self):
		self.canceled.append(True)
		speech.extensions.speechCanceled.notify()

	def _nvda_speak(self, sequence, symbolLevel=None, priority=None):
		self.spoken.append((list(sequence), priority))

	def priority_on(self, enabled=True):
		self.section["prioritizeMessages"] = enabled

	def reach_end(self, sequence):
		"""The synthesizer reached the end of a spoken message: NVDA runs its callback."""
		for item in sequence:
			if isinstance(item, self.priority.MessageSpoken):
				item.run()

	def press_key(self):
		self.keyboard.keyCounter += 1


class MessageSpeakingTests(MessagePriorityHarnessBase):
	def test_off_by_default_and_spoken_exactly_like_ui_message(self):
		self.assertFalse(self.priority.messages_have_priority())
		self.priority.speak_message("Page ready")
		self.assertEqual(ui.messages, ["Page ready"])
		self.assertEqual(self.spoken, [])
		self.assertEqual(self.brailled, [])

	def test_on_speaks_first_and_shows_the_message_in_braille(self):
		self.priority_on()
		self.priority.speak_message("Page ready")
		self.assertEqual(ui.messages, [])
		self.assertEqual(len(self.spoken), 1)
		sequence, priority = self.spoken[0]
		self.assertEqual(priority, "now")
		self.assertEqual(sequence[0], "Page ready")
		self.assertIsInstance(sequence[-1], self.priority.MessageSpoken)
		self.assertEqual(self.brailled, ["Page ready"])

	def test_speech_history_replay_gets_priority_without_braille(self):
		self.priority_on()
		self.plugin.history.speak_text("Recycle Bin 1 of 17")
		sequence, priority = self.spoken[0]
		self.assertEqual(sequence[0], "Recycle Bin 1 of 17")
		self.assertEqual(priority, "now")
		self.assertEqual(self.brailled, [])
		self.priority_on(False)
		self.plugin.history.speak_text("Recycle Bin 1 of 17")
		self.assertEqual(speech.speak_calls[-1], ["Recycle Bin 1 of 17"])

	def test_nvda_speech_modes_that_may_not_speak_use_the_ordinary_way(self):
		self.priority_on()
		speech.getState = lambda: types.SimpleNamespace(speechMode="beeps")
		speech.SpeechMode = types.SimpleNamespace(talk="talk")
		self.addCleanup(lambda: [speech.__dict__.pop(name, None) for name in ("getState", "SpeechMode")])
		self.priority.speak_message("Page ready")
		self.assertEqual(ui.messages, ["Page ready"])
		self.assertEqual(self.spoken, [])

	def test_the_speech_hook_loaded_message_is_given_priority(self):
		self.plugin.terminate()
		globalPluginHandler.runningPlugins.clear()
		self.section.update({
			"speechHookEnabled": True,
			"announceSpeechHookLoaded": True,
			"speechHookLoadedMessage": "Hook ready",
			"prioritizeMessages": True,
		})
		self.plugin = self.module.GlobalPlugin()
		globalPluginHandler.runningPlugins.append(self.plugin)
		self.assertEqual(ui.messages, [])
		self.assertEqual(self.spoken[-1][0][0], "Hook ready")
		self.assertEqual(self.spoken[-1][1], "now")


class CancellationTests(MessagePriorityHarnessBase):
	def test_nvda_cannot_cut_off_a_message_until_it_is_spoken(self):
		self.priority_on()
		self.priority.speak_message("ClassicSpeech hook loaded")
		nvda_event()
		self.assertEqual(self.canceled, [], "an automatic cancellation cut the message off")
		self.reach_end(self.spoken[-1][0])
		nvda_event()
		self.assertEqual(self.canceled, [True])

	def test_without_priority_nvda_cancels_as_usual(self):
		self.priority.speak_message("ClassicSpeech hook loaded")
		nvda_event()
		self.assertEqual(self.canceled, [True])

	def test_a_key_press_still_interrupts_the_message(self):
		self.priority_on()
		self.priority.speak_message("Checking for ClassicSpeech updates")
		self.press_key()
		nvda_event()
		self.assertEqual(self.canceled, [True])

	def test_a_braille_display_key_or_touch_gesture_also_interrupts(self):
		self.priority_on()
		self.priority.speak_message("Checking for ClassicSpeech updates")
		self.assertTrue(self.decider.decide(gesture=object()))
		nvda_event()
		self.assertEqual(self.canceled, [True])

	def test_counting_gestures_never_blocks_one(self):
		self.assertEqual(len(self.decider.handlers), 1)
		handler = self.decider.handlers[0]
		self.assertIs(handler(gesture=None), True)
		guard = self.priority._guard
		guard._gestures = None  # Even a broken count must not block the keyboard.
		self.assertIs(handler(gesture=None), True)

	def test_a_key_pressed_before_the_message_does_not_interrupt_it(self):
		self.priority_on()
		self.press_key()
		self.priority.speak_message("1 heading, 2 links.")
		nvda_event()
		self.assertEqual(self.canceled, [])

	def test_nvda_exit_and_a_new_synthesizer_always_cancel(self):
		self.priority_on()
		for module_name, function_name in (
			("core", "main"),
			("core", "onEndSession"),
			("synthDriverHandler", "handlePostConfigProfileSwitch"),
		):
			self.canceled.clear()
			self.priority.speak_message("Page ready")
			_caller(module_name, function_name)()
			self.assertEqual(self.canceled, [True], (module_name, function_name))

	def test_the_hold_ends_when_the_message_should_long_have_been_spoken(self):
		self.priority_on()
		now = [1000.0]
		original = self.priority.time.monotonic
		self.priority.time.monotonic = lambda: now[0]
		self.addCleanup(setattr, self.priority.time, "monotonic", original)
		self.priority.speak_message("Page ready")
		nvda_event()
		self.assertEqual(self.canceled, [])
		now[0] += 61
		nvda_event()
		self.assertEqual(self.canceled, [True])

	def test_a_cancellation_nvda_carried_out_ends_every_hold(self):
		self.priority_on()
		self.priority.speak_message("Page ready")
		speech.extensions.speechCanceled.notify()
		nvda_event()
		self.assertEqual(self.canceled, [True])

	def test_turning_the_option_off_releases_a_message(self):
		self.priority_on()
		self.priority.speak_message("Page ready")
		self.priority_on(False)
		nvda_event()
		self.assertEqual(self.canceled, [True])

	def test_two_messages_are_both_protected(self):
		self.priority_on()
		self.priority.speak_message("Page ready")
		self.priority.speak_message("1 heading.")
		self.reach_end(self.spoken[0][0])
		nvda_event()
		self.assertEqual(self.canceled, [], "the second message was cut off")
		self.reach_end(self.spoken[1][0])
		nvda_event()
		self.assertEqual(self.canceled, [True])

	def test_removing_classicspeech_restores_nvdas_cancellation(self):
		self.plugin.terminate()
		globalPluginHandler.runningPlugins.clear()
		self.assertEqual(speech.cancelSpeech, self._nvda_cancel)
		self.assertEqual(self.decider.handlers, [])
		self.assertEqual(speech.extensions.speechCanceled.handlers, [])
		self.plugin = self.module.GlobalPlugin()

	def test_a_guard_wrapped_by_another_add_on_passes_everything_through_once_removed(self):
		before = speech.cancelSpeech
		self.addCleanup(setattr, speech, "cancelSpeech", before)
		guard = self.priority.MessageGuard()
		guard.install()
		self.addCleanup(guard.uninstall)
		ours = speech.cancelSpeech

		def other_add_on(*args, **kwargs):
			return ours(*args, **kwargs)

		speech.cancelSpeech = other_add_on
		self.priority_on()
		guard.begin("Page ready")
		guard.uninstall()
		self.assertIs(speech.cancelSpeech, other_add_on)
		nvda_event()
		self.assertEqual(self.canceled, [True])


class SpeechFilterTests(MessagePriorityHarnessBase):
	def test_the_end_callback_follows_the_message_through_classicspeech_processing(self):
		end = self.priority.MessageSpoken(lambda token: None, 1)
		plain = self.plugin._filterSpeechSequence(["Speech and sound schemes on"])
		marked = self.plugin._filterSpeechSequence(["Speech and sound schemes on", end])
		self.assertIn(end, marked)
		self.assertEqual([repr(item) for item in marked if item is not end], [repr(item) for item in plain])
		last_text = max(index for index, item in enumerate(marked) if isinstance(item, str) and item.strip())
		self.assertIs(marked[last_text + 1], end)

	def test_the_end_callback_stays_with_the_text_before_a_voice_trigger(self):
		end = self.priority.MessageSpoken(lambda token: None, 1)
		trigger_exit = object()
		self.assertEqual(
			self.priority.join_message_ends(["enter", "Page ready", trigger_exit], [end]),
			["enter", "Page ready", end, trigger_exit],
		)
		self.assertEqual(self.priority.join_message_ends([trigger_exit], [end]), [trigger_exit, end])
		sequence = ["Page ready"]
		self.assertIs(self.priority.join_message_ends(sequence, []), sequence)


class MessageSourcesTests(unittest.TestCase):
	"""Every message ClassicSpeech speaks itself can be given priority."""

	def test_classicspeech_speaks_no_message_around_the_priority_option(self):
		offenders = []
		paths = [ROOT / "classicSpeech.py", *sorted((ROOT / "_speech_core").rglob("*.py")), *sorted((ROOT / "appModules").glob("*.py"))]
		for path in paths:
			if path.name == "message_priority.py":
				continue
			text = path.read_text(encoding="utf-8")
			for number, line in enumerate(text.splitlines(), 1):
				if re.search(r"(?<![\w.])ui\.message\(", line):
					offenders.append(f"{path.relative_to(ROOT)}:{number}")
		self.assertEqual(offenders, [], "use message_priority.speak_message for ClassicSpeech messages")

	def test_custom_browse_and_focus_mode_messages_use_the_priority_option(self):
		source = (ROOT / "classicSpeech.py").read_text(encoding="utf-8")
		install = source.split("install_mode_indication(\n", 1)[1].split(")", 1)[0]
		self.assertIn("speak_message=speak_message", install)


if __name__ == "__main__":
	unittest.main(verbosity=2)
