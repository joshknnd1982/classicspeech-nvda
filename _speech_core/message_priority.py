"""ClassicSpeech's own messages, and the option to give them priority over NVDA's speech.

Every message ClassicSpeech speaks itself goes through ``speak_message`` (or
``speak_sequence`` for speech history): the speech hook loaded message, Page
ready and page summaries, speech history, default button, speech and sound
scheme, update and user guide messages, and the custom browse mode, focus mode
and Microsoft Edge notification messages.

With **Give ClassicSpeech messages priority over NVDA speech** off (the
``prioritizeMessages`` setting, the default), a message is spoken exactly as
before: ``speak_message`` is NVDA's ``ui.message``.

With it on:

* A message is spoken at NVDA's highest speech priority, ``Spri.NOW``, as
  NVDA's own ``ui.delayedMessage`` is. It starts at once. Speech it
  interrupts resumes after it, and speech NVDA queues while it plays, even at
  the same priority, waits until it has been spoken.
* Until NVDA reports that the message has been spoken, ClassicSpeech holds off
  NVDA's automatic requests to cancel speech: a new foreground window or menu,
  the mouse, an application's event or another program. Those are what cut
  messages off, such as the hook loaded message when NVDA reports the first
  focus after it starts. The speech NVDA queues next is spoken after the
  message instead.
* The user can still stop it, as any speech: once a key is pressed on the
  keyboard or a braille display, or a touch gesture is made, NVDA's
  cancellation goes through. So do NVDA's exit and a configuration profile
  that loads another synthesizer.

NVDA runs the ``MessageSpoken`` callback at the end of a message's sequence
when the synthesizer reaches it. ClassicSpeech's speech filter keeps it right
after the message's text (``split_message_ends`` and ``join_message_ends``).
If it never runs, for example because another add-on removed it, the hold ends
after a generous estimate of how long the message takes to speak.
"""
from __future__ import annotations

import functools
import sys
import time

import logHandler

log = logHandler.log

#: The ClassicSpeech setting: give ClassicSpeech's messages priority.
SETTING_KEY = "prioritizeMessages"

#: ClassicSpeech's own modules, whose wrappers may sit between NVDA and this one.
_OWN_MODULE_PREFIXES = (__name__.rpartition(".")[0] + ".", "globalPlugins.classicSpeech")

#: NVDA's own cancellations that always go through, by the calling module and function.
_ALWAYS_CANCEL = {
	# NVDA is exiting.
	("core", "main"),
	# Windows is signing out or shutting down.
	("core", "onEndSession"),
	# A configuration profile loads another synthesizer; NVDA resets speech first.
	("synthDriverHandler", "handlePostConfigProfileSwitch"),
}

try:
	from speech.commands import CallbackCommand as _CallbackBase
except Exception:  # Outside NVDA (test harnesses).
	_CallbackBase = object


class MessageSpoken(_CallbackBase):
	"""The end of one ClassicSpeech message. NVDA runs it once the message has been spoken."""

	def __init__(self, on_spoken, token):
		self.token = token
		callback = functools.partial(on_spoken, token)
		if _CallbackBase is object:
			self._callback = callback
		else:
			super().__init__(callback, name="ClassicSpeech message spoken")

	def run(self, *args, **kwargs):
		return self._callback()

	def __repr__(self):
		return "MessageSpoken()"


def split_message_ends(sequence):
	"""Return ``(sequence, ends)``: the sequence without its ``MessageSpoken`` callbacks, and those callbacks."""
	ends = [item for item in sequence if isinstance(item, MessageSpoken)]
	if not ends:
		return sequence, []
	return [item for item in sequence if not isinstance(item, MessageSpoken)], ends


def join_message_ends(sequence, ends):
	"""Put ``MessageSpoken`` callbacks back right after the last text of ``sequence``.

	Right after the text, the callback's index belongs to the utterance that
	speaks it, even when a voice profile's trigger follows.
	"""
	if not ends:
		return sequence
	output = list(sequence)
	for index in range(len(output) - 1, -1, -1):
		if isinstance(output[index], str) and output[index].strip():
			return output[: index + 1] + list(ends) + output[index + 1:]
	return output + list(ends)


def messages_have_priority() -> bool:
	"""Return whether ClassicSpeech's messages are given priority over NVDA's speech."""
	try:
		import config

		try:
			section = config.conf.profiles[0]["classicSpeech"]
		except Exception:
			section = config.conf["classicSpeech"]
		value = section.get(SETTING_KEY, False)
	except Exception:
		return False
	if isinstance(value, str):
		return value.strip().lower() in {"1", "true", "yes", "on"}
	return bool(value)


def _longest_speaking_time(text) -> float:
	"""A generous upper bound, in seconds, on how long ``text`` takes to speak."""
	return min(60.0, 5.0 + len(text) / 8.0)


def _speech_is_on() -> bool:
	"""False in NVDA's Speech mode off, beeps and on demand, where a message may never be spoken."""
	try:
		import speech

		return speech.getState().speechMode == speech.SpeechMode.talk
	except Exception:
		return True


def _must_cancel(frame) -> bool:
	"""Return whether the code that asked NVDA to cancel speech must always be obeyed.

	``frame`` is the caller of ``speech.cancelSpeech``. ClassicSpeech's own
	wrappers around it are looked past.
	"""
	depth = 0
	while frame is not None and depth < 8:
		module = str(frame.f_globals.get("__name__", ""))
		if not module.startswith(_OWN_MODULE_PREFIXES):
			return (module, frame.f_code.co_name) in _ALWAYS_CANCEL
		frame = frame.f_back
		depth += 1
	return False


class MessageGuard:
	"""Keeps NVDA's automatic speech cancellation from cutting ClassicSpeech's messages off."""

	def __init__(self):
		#: Messages being spoken: token -> (user input count when it began, latest end time).
		self._messages = {}
		self._nextToken = 0
		self._gestures = 0
		self._installed = False
		self._originalCancel = None
		self._wrapper = None
		self._gestureDecider = None
		self._canceledAction = None

	@property
	def installed(self) -> bool:
		return self._installed

	# -- the user's input ------------------------------------------------------------
	def _note_input_gesture(self, gesture=None):
		"""``inputCore.decide_executeGesture`` handler: count the user's input.

		It must return True. A decider that returns anything false stops NVDA
		from running the gesture, and so from reacting to the keyboard at all.
		"""
		try:
			self._gestures += 1
		except Exception:
			pass
		return True

	def _input_count(self) -> int:
		"""Increases with every key press on the keyboard, braille display key and touch gesture."""
		count = self._gestures
		try:
			import keyboardHandler

			count += int(getattr(keyboardHandler, "keyCounter", 0) or 0)
		except Exception:
			pass
		return count

	# -- messages ----------------------------------------------------------------------
	def begin(self, text) -> int:
		"""Start holding NVDA's automatic cancellations for a message; return its token."""
		self._nextToken += 1
		token = self._nextToken
		self._messages[token] = (self._input_count(), time.monotonic() + _longest_speaking_time(text))
		return token

	def spoken(self, token):
		"""The message has been spoken (or will never be)."""
		self._messages.pop(token, None)

	def clear(self, *args, **kwargs):
		"""Speech was cancelled: no message is being spoken any more."""
		self._messages.clear()

	def holding(self) -> bool:
		"""Return whether a message is being spoken that nothing has interrupted yet."""
		if not self._messages:
			return False
		now = time.monotonic()
		inputs = self._input_count()
		for token, (mark, deadline) in list(self._messages.items()):
			# A key press ends the hold: the user is taking over.
			if deadline <= now or mark != inputs:
				del self._messages[token]
		return bool(self._messages)

	def should_hold_cancel(self, caller) -> bool:
		if not self.holding():
			return False
		if not messages_have_priority():
			self.clear()
			return False
		return not _must_cancel(caller)

	# -- installation --------------------------------------------------------------------
	def install(self):
		if self._installed:
			return
		try:
			import speech

			original = speech.cancelSpeech
		except Exception:
			log.debug("ClassicSpeech: speech cancellation unavailable for message priority", exc_info=True)
			return
		guard = self

		@functools.wraps(original)
		def cancelSpeech(*args, **kwargs):
			try:
				if guard._installed and guard.should_hold_cancel(sys._getframe(1)):
					log.debug("ClassicSpeech: kept NVDA from cutting off a ClassicSpeech message")
					return None
			except Exception:
				log.debug("ClassicSpeech: message priority check failed", exc_info=True)
			return original(*args, **kwargs)

		speech.cancelSpeech = cancelSpeech
		self._originalCancel = original
		self._wrapper = cancelSpeech
		self._installed = True
		try:
			import inputCore

			decider = getattr(inputCore, "decide_executeGesture", None)
			if decider is not None:
				decider.register(self._note_input_gesture)
				self._gestureDecider = decider
		except Exception:
			log.debug("ClassicSpeech: input gestures unavailable for message priority", exc_info=True)
		try:
			canceled = getattr(getattr(speech, "extensions", None), "speechCanceled", None)
			if canceled is not None:
				canceled.register(self.clear)
				self._canceledAction = canceled
		except Exception:
			log.debug("ClassicSpeech: speech cancel notification unavailable for message priority", exc_info=True)

	def uninstall(self):
		if not self._installed:
			return
		self._installed = False
		self._messages.clear()
		try:
			import speech

			if speech.cancelSpeech is self._wrapper:
				speech.cancelSpeech = self._originalCancel
			# Otherwise another wrapper holds this one; it now passes every call through.
		except Exception:
			log.debug("ClassicSpeech: could not restore speech cancellation", exc_info=True)
		for action, handler in (
			(self._gestureDecider, self._note_input_gesture),
			(self._canceledAction, self.clear),
		):
			if action is None:
				continue
			try:
				action.unregister(handler)
			except Exception:
				pass
		self._gestureDecider = None
		self._canceledAction = None
		self._originalCancel = None
		self._wrapper = None


_guard = None


def install() -> MessageGuard:
	"""Start protecting ClassicSpeech's messages; the running plugin calls this once."""
	global _guard
	if _guard is None:
		_guard = MessageGuard()
	_guard.install()
	return _guard


def uninstall():
	global _guard
	guard, _guard = _guard, None
	if guard is not None:
		guard.uninstall()


def _priority_speak(sequence, text_for_hold) -> bool:
	"""Speak ``sequence`` at priority now and hold cancellations until it is spoken.

	Returns False when the message should be spoken the ordinary way instead.
	"""
	guard = _guard
	if guard is None or not guard.installed or not messages_have_priority() or not _speech_is_on():
		return False
	try:
		import speech
		from speech.priorities import Spri

		now = Spri.NOW
		# The function ui.message speaks with, rather than any wrapper of speech.speak.
		speak = getattr(getattr(speech, "speech", None), "speak", None) or speech.speak
	except Exception:
		log.debug("ClassicSpeech: speech priority unavailable", exc_info=True)
		return False
	token = guard.begin(text_for_hold)
	try:
		speak(list(sequence) + [MessageSpoken(guard.spoken, token)], symbolLevel=None, priority=now)
	except Exception:
		guard.spoken(token)
		log.debug("ClassicSpeech: could not give a message priority", exc_info=True)
		return False
	return True


def speak_message(text):
	"""Speak one of ClassicSpeech's own messages and show it in braille, as ``ui.message`` does."""
	import ui

	message = text if isinstance(text, str) else ""
	if not message.strip() or not _priority_speak([message], message):
		ui.message(text)
		return
	try:
		import braille

		braille.handler.message(message)
	except Exception:
		log.debug("ClassicSpeech: could not show a message in braille", exc_info=True)


def speak_sequence(sequence):
	"""Speak ClassicSpeech's own ``sequence``, such as a speech history item, as ``speech.speak`` does."""
	import speech

	sequence = list(sequence or [])
	text = " ".join(item for item in sequence if isinstance(item, str))
	if not text.strip() or not _priority_speak(sequence, text):
		speech.speak(sequence)
