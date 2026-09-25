"""Outlook's message list: "unread" and the rest of a message's status in its announcement.

NVDA's Outlook support (``UIAGridRow`` in NVDA's Outlook app module) builds a
message's name from the columns of the message list, and asks Outlook's object
model about the selected message for the rest: unread, replied or forwarded,
has attachment, importance, meeting request. When Outlook doesn't answer at
that moment, NVDA leaves all of that out without a word.

Right after the selection moves, Outlook doesn't always answer. A tester's
NVDA 2026.2 log, with ClassicSpeech and the JAWS Migration Assistant, shows
NVDA asking at that moment for every message in the Inbox: it announced "From
<sender>, Subject <subject>, row <n>", and only about 80 ms later, when
Outlook reported a name change, "unread From <sender>, ...". The
tester had moved on by then, so "unread" was never heard. Without the add-ons,
NVDA asked a little earlier and Outlook answered, but its own log misses
"unread" now and then too: how soon NVDA builds the announcement decides it.

So for the message that has the focus, ClassicSpeech waits until Outlook
answers, for up to ``WAIT_LIMIT`` seconds, before NVDA builds its name, and
the announcement starts with "unread" again. When Outlook doesn't answer in
time, NVDA's own name is used and ClassicSpeech stops waiting until Outlook
answers again, so a busy Outlook never slows every message down.

Outlook's object model belongs to NVDA's main thread. A name built on any
other thread lacks the message's status, so it is never kept for the rest of
NVDA's core cycle, where NVDA's next announcement would use it.
"""
from __future__ import annotations

import threading
import time

import api
import logHandler

try:
	from comtypes import COMError
except ImportError:  # Outside NVDA, in the test harnesses.
	class COMError(Exception):
		"""Stands in for comtypes' COMError where comtypes isn't installed."""

log = logHandler.log

#: The longest wait for Outlook's object model before the focused message is announced without it, in seconds.
WAIT_LIMIT = 0.3
#: The pause before asking Outlook again, in seconds.
WAIT_STEP = 0.02
#: NVDA's class for a row of Outlook's message list, in NVDA's Outlook app module. Add-ons that extend it,
#: such as Outlook Extended, import NVDA's own module as ``nvdaBuiltin.appModules.outlook``.
ROW_CLASS_NAME = "UIAGridRow"
ROW_MODULE_SUFFIX = "appModules.outlook"

# The tests replace these.
_sleep = time.sleep
_monotonic = time.monotonic

#: True once Outlook didn't answer within WAIT_LIMIT: no more waiting until it answers again.
_waiting_paused = False
_overlay_class = None


def reset() -> None:
	"""Forget that Outlook once didn't answer in time."""
	global _waiting_paused
	_waiting_paused = False


def is_outlook_row_class(cls) -> bool:
	"""True for NVDA's class for a row of Outlook's message list."""
	return (
		getattr(cls, "__name__", "") == ROW_CLASS_NAME
		and str(getattr(cls, "__module__", "")).endswith(ROW_MODULE_SUFFIX)
	)


def choose_overlay_classes(obj, clsList) -> None:
	"""Put ClassicSpeech's row class first for a row of Outlook's message list.

	NVDA calls this for every object it creates, on whatever thread creates it,
	so it only looks at the class names NVDA's Outlook app module chose, and
	never raises.
	"""
	try:
		if not any(is_outlook_row_class(cls) for cls in clsList):
			return
		overlay = _get_overlay_class()
		if overlay is not None and overlay not in clsList:
			clsList.insert(0, overlay)
	except Exception:
		log.debugWarning("ClassicSpeech: could not add its Outlook message row class", exc_info=True)


def _get_overlay_class():
	global _overlay_class
	if _overlay_class is None:
		from NVDAObjects import NVDAObject

		_overlay_class = make_overlay_class(NVDAObject)
	return _overlay_class


def make_overlay_class(base):
	"""The overlay class for a row of Outlook's message list, built on NVDA's ``NVDAObject``."""

	class OutlookMessageRow(base):
		"""A row of Outlook's message list whose name waits for Outlook's object model."""

		# NVDA keeps an object's name for the rest of its core cycle. This class keeps
		# only a name built on NVDA's main thread, where Outlook can answer.
		_cache_name = False

		def _get_name(self):
			if not on_main_thread():
				return super()._get_name()
			cached = getattr(self, "_getPropertyViaCache", None)
			if cached is None:
				return self._classicSpeechMainThreadName()
			return cached(OutlookMessageRow._classicSpeechMainThreadName)

		def _classicSpeechMainThreadName(self):
			try:
				if self is api.getFocusObject():
					wait_for_object_model(self.appModule)
			except Exception:
				log.debugWarning("ClassicSpeech: could not wait for Outlook's object model", exc_info=True)
			return super()._get_name()

	return OutlookMessageRow


def on_main_thread() -> bool:
	"""True on NVDA's main thread, and outside NVDA."""
	try:
		import core

		main = getattr(core, "mainThreadId", None)
	except Exception:
		main = None
	return main is None or threading.get_ident() == main


def object_model(appModule):
	"""Outlook's object model once NVDA has it, or None.

	NVDA's Outlook app module keeps the object model it got as ``nativeOm``. Until
	then, asking for it can open NVDA's "Waiting for Outlook..." dialog, which NVDA
	does itself when it builds the name.
	"""
	try:
		return vars(appModule).get("nativeOm")
	except TypeError:
		return None


def ask_outlook(nativeOm):
	"""Ask Outlook about the selected message, as NVDA does: ``(answer, error)``.

	``answer`` is True when Outlook answers, False when it doesn't answer yet (it
	rejects the call, or nothing is selected yet), and None when there's nothing
	to wait for, such as when no Outlook window with a message list is active.
	"""
	try:
		nativeOm.activeExplorer().selection.item(1).unread
	except COMError as error:
		return False, error
	except Exception as error:
		return None, error
	return True, None


def wait_for_object_model(appModule) -> None:
	"""Return once Outlook's object model answers about the selected message, or after WAIT_LIMIT."""
	global _waiting_paused
	nativeOm = object_model(appModule)
	if nativeOm is None:
		return
	answer, error = ask_outlook(nativeOm)
	if answer is not False:
		if answer:
			_waiting_paused = False
		return
	if _waiting_paused:
		return
	start = _monotonic()
	while _monotonic() - start < WAIT_LIMIT:
		_sleep(WAIT_STEP)
		answer, error = ask_outlook(nativeOm)
		if answer is not False:
			if answer:
				_waiting_paused = False
				log.debug(
					f"ClassicSpeech: Outlook answered after {(_monotonic() - start) * 1000:.0f} ms, "
					"so NVDA announces the message with its status, such as unread"
				)
			return
	_waiting_paused = True
	log.debugWarning(
		f"ClassicSpeech: Outlook didn't answer within {WAIT_LIMIT * 1000:.0f} ms ({error!r}); the message is "
		"announced without its status, and ClassicSpeech waits again once Outlook answers"
	)
