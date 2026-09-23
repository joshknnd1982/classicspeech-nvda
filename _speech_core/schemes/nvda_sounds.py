"""Play the active speech and sound scheme's sounds instead of NVDA's own sounds.

NVDA plays the sounds in its waves folder (``browseMode.wav``, ``error.wav``,
the Remote Access cues...) through ``nvwave.playWaveFile``. While the scheme
switch is on and the active scheme gives an NVDA sound item a sound, that
function plays the scheme's sound instead; NVDA's own file is never changed.
Without such an item, or when its file is missing or outside the schemes
folder, NVDA's own sound plays, so with no NVDA sounds in the scheme NVDA
behaves as it always has. The sounds of a scheme live in its folder under
``ClassicSpeech/Schemes`` in NVDA's configuration folder (``store``).

NVDA plays its start sound before add-ons load, so a start sound can't be
replaced when it plays. While the active scheme has an NVDA start sound,
ClassicSpeech turns off NVDA's **Play sounds when starting or exiting NVDA**
(``general.playStartAndExitSounds``) and plays the start sound when it loads
and the exit sound when NVDA exits. It records the option's earlier value
(``nvda_settings_backup`` and ``STATE_KEY``) and puts it back when the scheme
no longer has a start sound, when ClassicSpeech is disabled or removed, and
on Reset All ClassicSpeech Settings.
"""
from __future__ import annotations

import functools
import json
import os

import logHandler

from . import store
from .catalog import NVDA_SOUND_PREFIX, nvda_waves_folder

log = logHandler.log

#: ClassicSpeech setting: NVDA's start and exit sound option as it was before
#: ClassicSpeech turned it off, as JSON; empty while NVDA plays them itself.
STATE_KEY = "nvdaStartExitSoundsState"
_OPTION_PATH = ("general",)
_OPTION_KEY = "playStartAndExitSounds"
START = "start"
EXIT = "exit"

_WRAPPED_MARK = "_classicSpeechNvdaSoundsWrapper"


def nvda_sound_name(file_name):
	"""Return the lower-case name of an NVDA sound (``browsemode``), or None for any other file.

	NVDA passes an absolute path, or one relative to its program folder for
	sounds inside speech (``waves\\textError.wav``).
	"""
	folder = nvda_waves_folder()
	if not folder or not file_name or not isinstance(file_name, str):
		return None
	path = file_name.replace("\\", "/")
	if not os.path.isabs(path):
		path = os.path.join(os.path.dirname(folder), path)
	path = os.path.normcase(os.path.normpath(path))
	if os.path.dirname(path) != os.path.normcase(os.path.normpath(folder)):
		return None
	name, extension = os.path.splitext(os.path.basename(path))
	if extension.lower() != ".wav" or not name:
		return None
	return name.lower()


def _inside_schemes_folder(path) -> bool:
	root = store.schemes_root()
	if not root:
		return False
	try:
		root = os.path.normcase(os.path.abspath(root))
		path = os.path.normcase(os.path.abspath(path))
		return os.path.commonpath([root, path]) == root
	except ValueError:
		return False


def replacement_for_name(name, sounds=None):
	"""The scheme's sound file for NVDA's sound ``name``, or None to play NVDA's own."""
	if not name:
		return None
	if sounds is None:
		sounds = store.active_nvda_sounds()
	path = sounds.get(str(name).lower())
	if not path or not _inside_schemes_folder(path) or not os.path.isfile(path):
		return None
	return path


def replacement_for(file_name, sounds=None):
	"""The scheme's sound file to play instead of ``file_name``, or None."""
	return replacement_for_name(nvda_sound_name(file_name), sounds)


def nvda_sound_path(name):
	"""NVDA's own file for NVDA's sound ``name`` (such as ``start``), or None outside NVDA."""
	folder = nvda_waves_folder()
	return os.path.join(folder, f"{name}.wav") if folder else None


def nvda_sound_path_for_item(item_id):
	"""NVDA's own file for an NVDA sound item, or None."""
	item_id = str(item_id or "")
	if not item_id.startswith(NVDA_SOUND_PREFIX):
		return None
	return nvda_sound_path(item_id[len(NVDA_SOUND_PREFIX):])


class NvdaSoundReplacer:
	"""Wraps ``nvwave.playWaveFile`` to play the scheme's sounds instead of NVDA's."""

	def __init__(self):
		self._nvwave = None
		self._original = None
		self._wrapper = None
		#: The replacements to use while NVDA exits, after ClassicSpeech has stopped.
		self._frozen = None

	@property
	def installed(self) -> bool:
		return self._wrapper is not None

	def install(self):
		if self._wrapper is not None:
			return
		try:
			import nvwave
		except Exception:
			log.debug("ClassicSpeech: NVDA's sound player is unavailable", exc_info=True)
			return
		original = getattr(nvwave, "playWaveFile", None)
		if original is None:
			return
		replacer = self

		@functools.wraps(original)
		def playWaveFile(*args, **kwargs):
			# A later add-on may retain this closure after uninstall. Only the
			# current installation may replace sounds, even after reinstalling.
			if replacer._wrapper is not playWaveFile:
				return original(*args, **kwargs)
			try:
				swapped = replacer._swap(args, kwargs)
			except Exception:
				log.debug("ClassicSpeech: could not look up a scheme sound for NVDA", exc_info=True)
				swapped = None
			if swapped is None:
				return original(*args, **kwargs)
			try:
				return original(*swapped[0], **swapped[1])
			except Exception:
				# Such as a WAV file NVDA can't read: NVDA's own sound, rather than an error in NVDA.
				log.warning("ClassicSpeech: NVDA could not play a scheme sound; playing its own", exc_info=True)
				return original(*args, **kwargs)

		setattr(playWaveFile, _WRAPPED_MARK, True)
		nvwave.playWaveFile = playWaveFile
		self._nvwave = nvwave
		self._original = original
		self._wrapper = playWaveFile

	def _swap(self, args, kwargs):
		"""Return ``(args, kwargs)`` that play the scheme's sound instead, or None to play NVDA's."""
		if args:
			file_name, rest = args[0], args[1:]
		else:
			file_name, rest = kwargs.get("fileName"), ()
		replacement = replacement_for(file_name, self._frozen)
		if not replacement:
			return None
		log.debug(f"ClassicSpeech: playing {replacement} instead of NVDA's {file_name}")
		if args:
			return (replacement, *rest), kwargs
		kwargs = dict(kwargs)
		kwargs["fileName"] = replacement
		return args, kwargs

	def freeze(self):
		"""Keep replacing NVDA's sounds, such as its exit sound, after ClassicSpeech has stopped."""
		try:
			self._frozen = dict(store.active_nvda_sounds())
		except Exception:
			self._frozen = {}

	def uninstall(self):
		if self._wrapper is None:
			return
		try:
			if getattr(self._nvwave, "playWaveFile", None) is self._wrapper:
				self._nvwave.playWaveFile = self._original
		except Exception:
			log.debug("ClassicSpeech: could not restore NVDA's sound player", exc_info=True)
		self._nvwave = None
		self._original = None
		self._wrapper = None
		self._frozen = None

	def play_exactly(self, path, asynchronous=True):
		"""Play ``path`` itself, never a scheme's replacement for it."""
		play = self._original
		if play is None:
			import nvwave

			play = nvwave.playWaveFile
			if getattr(play, _WRAPPED_MARK, False):
				play = getattr(play, "__wrapped__", play)
		play(path, asynchronous=asynchronous)


_replacer = NvdaSoundReplacer()


def install():
	_replacer.install()


def uninstall(nvda_exiting=False):
	"""Stop replacing NVDA's sounds; while NVDA exits, keep replacing its exit sound."""
	if nvda_exiting:
		_replacer.freeze()
		return
	_replacer.uninstall()


def play_sound_file(path, asynchronous=True):
	"""Play exactly ``path``, as the schemes dialog's Play sound button does."""
	_replacer.play_exactly(path, asynchronous=asynchronous)


# -- NVDA's start and exit sounds -------------------------------------------------

def _section():
	from ..settings.config_core import _ensure_classic_speech_section

	return _ensure_classic_speech_section()


def _saved_option():
	"""NVDA's start and exit sound option before ClassicSpeech turned it off, or None."""
	try:
		raw = _section().get(STATE_KEY, "")
	except Exception:
		return None
	if not isinstance(raw, str) or not raw.strip():
		return None
	try:
		state = json.loads(raw)
	except ValueError:
		return None
	return state if isinstance(state, dict) else None


def _save_option(state):
	_section()[STATE_KEY] = json.dumps(state) if state is not None else ""


def _nvda_option_on() -> bool:
	try:
		import config

		value = config.conf["general"]["playStartAndExitSounds"]
	except Exception:
		return True
	if isinstance(value, str):
		return value.strip().lower() in {"1", "true", "yes", "on"}
	return bool(value)


def _may_change_nvda():
	"""False on secure screens, where NVDA must not write its configuration."""
	try:
		import globalVars

		if getattr(globalVars.appArgs, "secure", False):
			return False
	except Exception:
		pass
	try:
		import NVDAState

		return bool(NVDAState.shouldWriteToDisk())
	except Exception:
		return True


def classicspeech_plays_start_and_exit_sounds() -> bool:
	"""True while ClassicSpeech has turned off NVDA's start and exit sounds to play them itself."""
	return _saved_option() is not None


def sync_start_and_exit_sounds(release=False) -> bool:
	"""Turn NVDA's start and exit sounds over to ClassicSpeech while the scheme has a start sound.

	``release`` gives them back to NVDA whatever the scheme has, as when
	ClassicSpeech is disabled or removed. Returns whether ClassicSpeech now
	plays them.
	"""
	if not _may_change_nvda():
		return classicspeech_plays_start_and_exit_sounds()
	from .. import nvda_settings_backup

	saved = _saved_option()
	nvda_on = _nvda_option_on()
	wanted = not release and replacement_for_name(START) is not None
	try:
		if wanted:
			if saved is None:
				if not nvda_on:
					# NVDA plays no start or exit sound; neither does the scheme.
					return False
				_save_option(nvda_settings_backup.nvda_setting_state(_OPTION_PATH, _OPTION_KEY))
			if nvda_on:
				nvda_settings_backup.set_nvda_setting(_OPTION_PATH, _OPTION_KEY, False)
			return True
		if saved is not None:
			# Put the option back, unless it was changed in NVDA's settings since.
			if not nvda_on:
				nvda_settings_backup.restore_nvda_setting(_OPTION_PATH, _OPTION_KEY, saved)
			_save_option(None)
	except Exception:
		log.exception("ClassicSpeech: could not change NVDA's start and exit sound option")
	return classicspeech_plays_start_and_exit_sounds()


def _play_start_or_exit(name, asynchronous):
	native_path = nvda_sound_path(name)
	replacement = replacement_for_name(name)
	# Try the scheme first, then NVDA's own sound once. play_exactly bypasses
	# replacement so the fallback cannot select the same broken scheme again.
	paths = [replacement] if replacement and replacement != native_path else []
	paths.append(native_path)
	for path in paths:
		if not path or not os.path.isfile(path):
			continue
		try:
			_replacer.play_exactly(path, asynchronous=asynchronous)
			return
		except Exception:
			log.debug("ClassicSpeech: could not play the %s sound from %s", name, path, exc_info=True)


def _minimal_start():
	try:
		import globalVars

		return bool(getattr(globalVars.appArgs, "minimal", False))
	except Exception:
		return False


def _nvda_starting() -> bool:
	"""True while NVDA starts, rather than when its plugins are reloaded."""
	try:
		import NVDAState

		return not NVDAState._TrackNVDAInitialization.isInitializationComplete()
	except Exception:
		return True


def handle_nvda_start():
	"""When ClassicSpeech loads: play the start sound NVDA left to it, then keep the option in step."""
	if (
		_nvda_starting()
		and classicspeech_plays_start_and_exit_sounds()
		and not _nvda_option_on()
		and not _minimal_start()
	):
		_play_start_or_exit(START, asynchronous=True)
	sync_start_and_exit_sounds()


def handle_nvda_exit(addon_leaving=False):
	"""While NVDA exits: play the exit sound NVDA left to ClassicSpeech, or give the sounds back.

	NVDA itself plays its exit sound after ClassicSpeech has stopped; the
	frozen replacement (``uninstall(nvda_exiting=True)``) still applies then.
	"""
	if sync_start_and_exit_sounds(release=addon_leaving):
		if not _minimal_start():
			_play_start_or_exit(EXIT, asynchronous=False)


def handle_windows_session_end():
	"""Windows is signing out or shutting down: NVDA won't play the exit sound ClassicSpeech took over."""
	if classicspeech_plays_start_and_exit_sounds() and not _nvda_option_on() and not _minimal_start():
		_play_start_or_exit(EXIT, asynchronous=False)
