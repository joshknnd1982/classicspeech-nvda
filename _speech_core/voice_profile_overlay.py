"""Temporary, same-synth NVDA configuration overlays for Voice Profile routes."""
from __future__ import annotations

import copy


def _trace(message: str) -> None:
	"""Log runtime overlay evidence only when ClassicSpeech debugging is enabled."""
	try:
		import config
		import logHandler
		section = config.conf.profiles[0].get("classicSpeech", {})
		if not section.get("debugLogging", False):
			return
		logHandler.log.info("ClassicSpeech Voice Profile overlay: %s", message)
	except Exception:
		return


def _nvda_profile_factory():
	"""Create an in-memory ConfigObj profile with no filename to persist."""
	from configobj import ConfigObj

	return ConfigObj(indent_type="\t", encoding="UTF-8")


def _stored_values(section, path=()):
	"""Yield ``(section path, key, value)`` for every value stored in a profile."""
	for key in list(section.keys()):
		value = dict.__getitem__(section, key) if isinstance(section, dict) else section[key]
		if hasattr(value, "keys"):
			yield from _stored_values(value, path + (key,))
		else:
			yield path, key, value


def writes_to_carry(profile, belongs_to_overlay):
	"""Return the values NVDA stored in a temporary overlay profile that must outlive it.

	While an overlay is the newest profile, NVDA stores every setting that
	changes in it: a settings dialog's OK, a toggle command, or a new
	synthesizer. ``belongs_to_overlay(path, key, value)`` is True for the
	overlay's own values, such as the voice it speaks with, which must vanish
	with it.
	"""
	try:
		return [
			(path, key, value)
			for path, key, value in _stored_values(profile)
			if not belongs_to_overlay(path, key, value)
		]
	except Exception:
		_trace("could not read what was stored in the overlay")
		return []


def carry_writes(config_manager, writes):
	"""Store ``writes`` through NVDA's configuration, now that the overlay is gone.

	NVDA stores each one in the configuration profile it would have used without
	the overlay, and saves it with that profile.
	"""
	for path, key, value in writes:
		try:
			section = config_manager
			for part in path:
				if part not in section:
					section[part] = {}
				section = section[part]
			section[key] = value
			_trace(f"kept {'/'.join(path + (key,))} changed while the voice was speaking")
		except Exception:
			_trace(f"could not keep {'/'.join(path + (key,))}")


class VoiceProfileOverlay:
	"""Push one full resolved Voice Profile snapshot onto NVDA's config stack.

	The overlay intentionally does not call a synth driver. NVDA's speech manager
	will invoke the normal post-profile-switch loader at an utterance boundary.
	"""

	def __init__(self, config_manager, synth_name: str, snapshot: dict, profile_factory=None):
		if not synth_name:
			raise ValueError("A same-synth overlay requires an active synth name")
		if not isinstance(snapshot, dict) or not snapshot:
			raise ValueError("A Voice Profile overlay requires a resolved setting snapshot")
		self._config = config_manager
		self._synth_name = str(synth_name)
		self._snapshot = copy.deepcopy(snapshot)
		self._profile_factory = profile_factory or _nvda_profile_factory
		self._profile = None
		self.active = False

	def _build_profile(self):
		profile = self._profile_factory()
		# Do not include speech.synth: the current active synth must remain active.
		profile["speech"] = {self._synth_name: copy.deepcopy(self._snapshot)}
		try:
			profile.filename = None
		except Exception:
			pass
		return profile

	def _refresh_aggregate(self):
		refresh = getattr(self._config, "_handleProfileSwitch", None)
		if not callable(refresh):
			raise RuntimeError("NVDA config manager does not expose profile-stack refresh")
		refresh(shouldNotify=False)

	def _effective_value(self, setting_id: str):
		try:
			return self._config["speech"][self._synth_name].get(setting_id)
		except Exception:
			return None

	def enter(self):
		if self.active:
			return
		profile = self._build_profile()
		_trace(
			f"enter synth={self._synth_name} requestedVariant={self._snapshot.get('variant')!r} "
			f"effectiveVariantBefore={self._effective_value('variant')!r}"
		)
		self._config.profiles.append(profile)
		try:
			self._refresh_aggregate()
		except Exception:
			self._config.profiles.pop()
			raise
		self._profile = profile
		self.active = True
		_trace(f"entered synth={self._synth_name} effectiveVariantAfter={self._effective_value('variant')!r}")

	def synchronize_from_driver(self, driver):
		"""Replace the active profile with the driver's post-selector live values.

		This runs after the queue-bound Preview-style transaction and before
		SpeechManager's mandatory post-trigger config reload. It makes that reload
		replay the same native Voice/Variant defaults the driver just established.
		"""
		if not self.active:
			raise RuntimeError("Cannot synchronize an inactive Voice Profile overlay")
		snapshot = {}
		for setting in getattr(driver, "supportedSettings", ()):
			setting_id = getattr(setting, "id", "")
			if not setting_id:
				continue
			try:
				snapshot[setting_id] = copy.deepcopy(getattr(driver, setting_id))
			except Exception:
				continue
		if not snapshot:
			raise RuntimeError("Voice Profile overlay could not capture driver settings")
		self._snapshot = snapshot
		self._profile["speech"][self._synth_name] = copy.deepcopy(snapshot)
		self._refresh_aggregate()
		_trace(f"synchronized synth={self._synth_name} requestedVariant={snapshot.get('variant')!r}")

	def _belongs_to_overlay(self, path, key, value):
		"""The overlay's own values: the settings of the synthesizer it speaks with."""
		return path[:2] == ("speech", self._synth_name)

	def exit(self):
		if not self.active:
			return
		if not self._config.profiles or self._config.profiles[-1] is not self._profile:
			raise RuntimeError("ClassicSpeech Voice Profile overlays must exit in LIFO order")
		_trace(f"exit synth={self._synth_name} effectiveVariantBefore={self._effective_value('variant')!r}")
		writes = writes_to_carry(self._profile, self._belongs_to_overlay)
		self._config.profiles.pop()
		try:
			self._refresh_aggregate()
		except Exception:
			self._config.profiles.append(self._profile)
			raise
		self._profile = None
		self.active = False
		carry_writes(self._config, writes)
		_trace(f"exited synth={self._synth_name} effectiveVariantAfter={self._effective_value('variant')!r}")
