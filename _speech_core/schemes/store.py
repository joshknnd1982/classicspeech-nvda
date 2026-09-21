"""Persistence, runtime cache and transactional editing for Speech and Sound Schemes.

Scheme data is stored as one JSON string, ``classicSpeech.schemeData``, so
ConfigObj validation never discards nested voice records::

	{
		"version": 1,
		"enabled": true,
		"activeScheme": "Default",
		"schemes": {
			"Default": {
				"items": {
					"role.LINK": {
						"sound": "C:\\\\Sounds\\\\link.wav",
						"soundOnly": false,
						"voice": {
							"enabled": true,
							"engine": "",
							"bySynth": {"espeak": {"baseline": {...}, "overrides": {...}}}
						}
					}
				}
			}
		},
		"custom": {"fonts": [], "fontSizes": [], "styles": [], "classes": []}
	}

``voice.engine`` is empty for "the active synthesizer". Voice records use the
same baseline/overrides shape as Voice Profiles and are kept per synthesizer.
"""
from __future__ import annotations

import copy
import json
import os

SCHEME_DATA_KEY = "schemeData"
DEFAULT_SCHEME_NAME = "Default"
CUSTOM_KINDS = ("fonts", "fontSizes", "styles", "classes")
SCHEME_VERSION = 1


def empty_scheme_data():
	return {
		"version": SCHEME_VERSION,
		"enabled": True,
		"activeScheme": DEFAULT_SCHEME_NAME,
		"schemes": {DEFAULT_SCHEME_NAME: {"items": {}}},
		"custom": {kind: [] for kind in CUSTOM_KINDS},
	}


def _as_dict(value):
	return value if isinstance(value, dict) else {}


def normalize_scheme_data(data):
	"""Return a complete, well-formed copy of ``data``."""
	result = empty_scheme_data()
	data = _as_dict(data)
	result["enabled"] = bool(data.get("enabled", True))
	schemes = {}
	for name, scheme in _as_dict(data.get("schemes")).items():
		name = str(name or "").strip()
		if not name:
			continue
		items = {}
		for item_id, settings in _as_dict(_as_dict(scheme).get("items")).items():
			clean = normalize_item_settings(settings)
			if clean:
				items[str(item_id)] = clean
		schemes[name] = {"items": items}
	if schemes:
		result["schemes"] = schemes
	active = str(data.get("activeScheme") or "").strip()
	if active not in result["schemes"]:
		active = next(iter(result["schemes"]))
	result["activeScheme"] = active
	custom = _as_dict(data.get("custom"))
	for kind in CUSTOM_KINDS:
		values = []
		for value in custom.get(kind, ()) or ():
			text = str(value or "").strip()
			if text and text not in values:
				values.append(text)
		result["custom"][kind] = values
	return result


def normalize_item_settings(settings):
	"""Return clean item settings, or ``{}`` when nothing is configured."""
	settings = _as_dict(settings)
	clean = {}
	sound = str(settings.get("sound") or "").strip()
	if sound:
		clean["sound"] = sound
		clean["soundOnly"] = bool(settings.get("soundOnly", False))
	voice = _as_dict(settings.get("voice"))
	by_synth = {}
	for synth_name, record in _as_dict(voice.get("bySynth")).items():
		if isinstance(record, dict) and record:
			by_synth[str(synth_name)] = copy.deepcopy(record)
	if voice.get("enabled") and by_synth:
		clean["voice"] = {
			"enabled": True,
			"engine": str(voice.get("engine") or ""),
			"bySynth": by_synth,
		}
	elif by_synth:
		# Keep an edited but disabled voice so re-enabling it restores the values.
		clean["voice"] = {"enabled": False, "engine": str(voice.get("engine") or ""), "bySynth": by_synth}
	return clean


def item_is_configured(settings) -> bool:
	settings = _as_dict(settings)
	return bool(settings.get("sound")) or bool(_as_dict(settings.get("voice")).get("enabled"))


def load_scheme_data(raw):
	if isinstance(raw, dict):
		return normalize_scheme_data(copy.deepcopy(raw))
	if isinstance(raw, str) and raw.strip():
		try:
			return normalize_scheme_data(json.loads(raw))
		except (TypeError, ValueError):
			pass
	return empty_scheme_data()


def dump_scheme_data(data) -> str:
	return json.dumps(normalize_scheme_data(data), ensure_ascii=False, separators=(",", ":"))


def _read_raw():
	try:
		from ..settings.config_core import _read_classic_speech_section
		section = _read_classic_speech_section()
		return section.get(SCHEME_DATA_KEY, "{}")
	except Exception:
		return "{}"


class _RuntimeCache:
	raw = None
	data = None
	items = {}
	enabled = False


_runtime = _RuntimeCache()


def invalidate_runtime_cache():
	_runtime.raw = None


def runtime_data():
	"""Return the parsed scheme data, reparsing only when the stored JSON changes."""
	raw = _read_raw()
	if raw is _runtime.raw:
		return _runtime
	if _runtime.data is not None and raw == _runtime.raw:
		_runtime.raw = raw
		return _runtime
	data = load_scheme_data(raw)
	scheme = data["schemes"].get(data["activeScheme"], {"items": {}})
	_runtime.items = {
		item_id: settings
		for item_id, settings in scheme.get("items", {}).items()
		if item_is_configured(settings)
	}
	_runtime.enabled = bool(data.get("enabled")) and bool(_runtime.items)
	_runtime.data = data
	_runtime.raw = raw
	return _runtime


def active_items():
	"""Return ``{item_id: settings}`` for configured items, or ``{}`` when disabled."""
	runtime = runtime_data()
	return runtime.items if runtime.enabled else {}


def schemes_active() -> bool:
	return runtime_data().enabled


class SchemeStore:
	"""Transactional editor for the scheme data in the ClassicSpeech config section."""

	def __init__(self, section=None):
		if section is None:
			from ..settings.config_core import _ensure_classic_speech_section
			section = _ensure_classic_speech_section()
		self._section = section
		self._opening_raw = section.get(SCHEME_DATA_KEY, "{}")
		self.data = load_scheme_data(self._opening_raw)

	# -- schemes ---------------------------------------------------------
	@property
	def enabled(self) -> bool:
		return bool(self.data.get("enabled", True))

	@enabled.setter
	def enabled(self, value):
		self.data["enabled"] = bool(value)

	@property
	def scheme_names(self):
		return list(self.data["schemes"].keys())

	@property
	def active_scheme(self) -> str:
		return self.data["activeScheme"]

	def set_active_scheme(self, name):
		if name not in self.data["schemes"]:
			raise KeyError(name)
		self.data["activeScheme"] = name

	def _unique_name(self, base):
		base = str(base or "").strip() or DEFAULT_SCHEME_NAME
		if base not in self.data["schemes"]:
			return base
		counter = 2
		while f"{base} {counter}" in self.data["schemes"]:
			counter += 1
		return f"{base} {counter}"

	def add_scheme(self, name, copy_from=None):
		name = self._unique_name(name)
		source = self.data["schemes"].get(copy_from) if copy_from else None
		self.data["schemes"][name] = copy.deepcopy(source) if source else {"items": {}}
		self.data["activeScheme"] = name
		return name

	def rename_scheme(self, old, new):
		new = str(new or "").strip()
		if not new or old not in self.data["schemes"]:
			return old
		if new == old:
			return old
		new = self._unique_name(new)
		renamed = {}
		for name, scheme in self.data["schemes"].items():
			renamed[new if name == old else name] = scheme
		self.data["schemes"] = renamed
		if self.data["activeScheme"] == old:
			self.data["activeScheme"] = new
		return new

	def delete_scheme(self, name):
		if name not in self.data["schemes"] or len(self.data["schemes"]) <= 1:
			return False
		del self.data["schemes"][name]
		if self.data["activeScheme"] == name:
			self.data["activeScheme"] = next(iter(self.data["schemes"]))
		return True

	# -- items -----------------------------------------------------------
	def _items(self):
		return self.data["schemes"][self.data["activeScheme"]].setdefault("items", {})

	def get_item(self, item_id) -> dict:
		return copy.deepcopy(self._items().get(item_id, {}))

	def set_item(self, item_id, settings):
		clean = normalize_item_settings(settings)
		if clean:
			self._items()[item_id] = clean
		else:
			self._items().pop(item_id, None)

	def clear_item(self, item_id):
		self._items().pop(item_id, None)

	def configured_item_ids(self):
		return {item_id for item_id, settings in self._items().items() if item_is_configured(settings)}

	def item_summary(self, item_id) -> dict:
		settings = self._items().get(item_id, {})
		voice = _as_dict(settings.get("voice"))
		return {
			"sound": bool(settings.get("sound")),
			"soundOnly": bool(settings.get("sound")) and bool(settings.get("soundOnly")),
			"voice": bool(voice.get("enabled")),
			"engine": str(voice.get("engine") or ""),
		}

	# -- custom catalog entries -------------------------------------------
	def custom_entries(self):
		return copy.deepcopy(self.data["custom"])

	def add_custom_entry(self, kind, value):
		if kind not in CUSTOM_KINDS:
			raise KeyError(kind)
		value = str(value or "").strip()
		if not value:
			return False
		values = self.data["custom"].setdefault(kind, [])
		if value in values:
			return False
		values.append(value)
		return True

	def remove_custom_entry(self, kind, value):
		values = self.data["custom"].get(kind, [])
		if value in values:
			values.remove(value)
			return True
		return False

	# -- transaction -----------------------------------------------------
	def apply(self):
		self._section[SCHEME_DATA_KEY] = dump_scheme_data(self.data)
		invalidate_runtime_cache()
		try:
			import config
			save = getattr(config.conf, "save", None)
			if callable(save):
				save()
		except Exception:
			raise

	def mark_applied(self):
		self._opening_raw = self._section.get(SCHEME_DATA_KEY, "{}")

	def cancel(self):
		self._section[SCHEME_DATA_KEY] = self._opening_raw
		invalidate_runtime_cache()
		self.data = load_scheme_data(self._opening_raw)

	def is_dirty(self) -> bool:
		return dump_scheme_data(self.data) != dump_scheme_data(load_scheme_data(self._opening_raw))


def sound_file_exists(path) -> bool:
	try:
		return bool(path) and os.path.isfile(path)
	except Exception:
		return False


def set_schemes_enabled(enabled: bool) -> bool:
	"""Persist the master switch without opening the dialog (used by a gesture)."""
	from ..settings.config_core import _ensure_classic_speech_section

	section = _ensure_classic_speech_section()
	data = load_scheme_data(section.get(SCHEME_DATA_KEY, "{}"))
	data["enabled"] = bool(enabled)
	section[SCHEME_DATA_KEY] = dump_scheme_data(data)
	invalidate_runtime_cache()
	return bool(enabled)


def cycle_active_scheme():
	"""Switch to the next named scheme and return its name."""
	from ..settings.config_core import _ensure_classic_speech_section

	section = _ensure_classic_speech_section()
	data = load_scheme_data(section.get(SCHEME_DATA_KEY, "{}"))
	names = list(data["schemes"].keys())
	index = names.index(data["activeScheme"]) if data["activeScheme"] in names else -1
	data["activeScheme"] = names[(index + 1) % len(names)]
	section[SCHEME_DATA_KEY] = dump_scheme_data(data)
	invalidate_runtime_cache()
	return data["activeScheme"]
