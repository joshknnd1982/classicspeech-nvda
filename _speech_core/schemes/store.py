"""Persistence, runtime cache and transactional editing for Speech and Sound Schemes.

Each scheme is a folder under ``ClassicSpeech/Schemes`` in NVDA's user
configuration folder (usually ``%APPDATA%/nvda/ClassicSpeech/Schemes``)::

	Schemes/
		Default/
			scheme.json
			Sounds/
				link.wav

``scheme.json`` holds the scheme's name, its items, and the catalog entries
(fonts, sizes, styles and window classes) added to it::

	{
		"format": "ClassicSpeech scheme",
		"version": 1,
		"name": "Default",
		"items": {
			"role.LINK": {
				"sound": "Sounds/link.wav",
				"soundOnly": false,
				"voice": {
					"enabled": true,
					"engine": "",
					"bySynth": {"espeak": {"baseline": {...}, "overrides": {...}}}
				}
			}
		},
		"custom": {"fonts": [], "fontSizes": [], "styles": [], "classes": []}
	}

Saving a scheme copies sounds from outside its folder into its ``Sounds``
folder, so every scheme folder is complete and can be shared. In memory, sound
paths are always absolute. ``voice.engine`` is empty for "the active
synthesizer". Voice records use the same baseline/overrides shape as Voice
Profiles and are kept per synthesizer.

The ClassicSpeech config section keeps only the switches, as JSON in
``classicSpeech.schemeData``::

	{"version": 2, "enabled": true, "activeScheme": "Default"}

Version 1 of that JSON held every scheme, with catalog entries shared by all
schemes. ``prepare_scheme_folders`` moves such schemes into folders once.
Without an NVDA configuration folder, which happens only in tests, schemes stay
in the version 1 JSON.
"""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import tempfile

import logHandler

log = logHandler.log

SCHEME_DATA_KEY = "schemeData"
DEFAULT_SCHEME_NAME = "Default"
CUSTOM_KINDS = ("fonts", "fontSizes", "styles", "classes")
SCHEME_VERSION = 1
SWITCHES_VERSION = 2
SCHEME_FILE_NAME = "scheme.json"
SCHEME_FILE_FORMAT = "ClassicSpeech scheme"
SOUNDS_FOLDER_NAME = "Sounds"

# Tests point this at a temporary folder. NVDA uses its configuration folder.
_ROOT_OVERRIDE = None

_INVALID_NAME_CHARACTERS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"} | {f"{port}{number}" for port in ("COM", "LPT") for number in range(1, 10)}


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


def normalize_custom(custom):
	"""Return clean added catalog entries: unique, non-empty text per kind."""
	custom = _as_dict(custom)
	result = {}
	for kind in CUSTOM_KINDS:
		values = []
		for value in custom.get(kind, ()) or ():
			text = str(value or "").strip()
			if text and text not in values:
				values.append(text)
		result[kind] = values
	return result


def normalize_scheme_data(data):
	"""Return a complete, well-formed copy of version 1 ``data``."""
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
	result["custom"] = normalize_custom(data.get("custom"))
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


def _decode(raw) -> dict:
	if isinstance(raw, dict):
		return copy.deepcopy(raw)
	if isinstance(raw, str) and raw.strip():
		try:
			decoded = json.loads(raw)
		except (TypeError, ValueError):
			return {}
		return decoded if isinstance(decoded, dict) else {}
	return {}


def load_scheme_data(raw):
	"""Return version 1 data (every scheme inside the config) from ``raw``."""
	return normalize_scheme_data(_decode(raw))


def dump_scheme_data(data) -> str:
	return json.dumps(normalize_scheme_data(data), ensure_ascii=False, separators=(",", ":"))


def has_legacy_schemes(raw) -> bool:
	"""Return whether ``raw`` still holds version 1 schemes inside the config."""
	return "schemes" in _decode(raw)


def load_switches(raw) -> dict:
	data = _decode(raw)
	return {
		"enabled": bool(data.get("enabled", True)),
		"activeScheme": str(data.get("activeScheme") or "").strip() or DEFAULT_SCHEME_NAME,
	}


def dump_switches(enabled, active_scheme) -> str:
	return json.dumps(
		{"version": SWITCHES_VERSION, "enabled": bool(enabled), "activeScheme": str(active_scheme)},
		ensure_ascii=False,
		separators=(",", ":"),
	)


# -- scheme folders -------------------------------------------------------------

def schemes_root():
	"""Return the folder that holds one folder per scheme, or None outside NVDA."""
	if _ROOT_OVERRIDE is not None:
		return _ROOT_OVERRIDE
	config_folder = None
	try:
		import NVDAState

		config_folder = NVDAState.WritePaths.configDir
	except Exception:
		try:
			import globalVars

			config_folder = globalVars.appArgs.configPath
		except Exception:
			config_folder = None
	if not config_folder:
		return None
	return os.path.join(os.path.abspath(config_folder), "ClassicSpeech", "Schemes")


def folder_name_for(name) -> str:
	"""Return a Windows-safe folder name for a scheme name."""
	text = _INVALID_NAME_CHARACTERS.sub("_", str(name or "")).strip().rstrip(". ")
	if not text:
		text = "Scheme"
	if text.split(".", 1)[0].upper() in _RESERVED_NAMES:
		text = f"_{text}"
	return text[:80].rstrip(". ") or "Scheme"


def _unique_folder(root, base) -> str:
	try:
		taken = {entry.lower() for entry in os.listdir(root)}
	except FileNotFoundError:
		taken = set()
	candidate = base
	counter = 2
	while candidate.lower() in taken:
		candidate = f"{base} {counter}"
		counter += 1
	return os.path.join(root, candidate)


def _is_within(folder, path) -> bool:
	folder = os.path.normcase(os.path.abspath(folder))
	path = os.path.normcase(os.path.abspath(path))
	try:
		return os.path.commonpath([folder, path]) == folder
	except ValueError:
		return False


def _absolute_sound_path(folder, sound) -> str:
	if os.path.isabs(sound):
		return os.path.normpath(sound)
	return os.path.normpath(os.path.join(folder, sound))


def _same_contents(first, second) -> bool:
	"""Return whether two files hold the same bytes.

	NVDA's bundled Python does not include ``filecmp``, so compare directly.
	"""
	try:
		if os.path.getsize(first) != os.path.getsize(second):
			return False
		with open(first, "rb") as left, open(second, "rb") as right:
			while True:
				chunk = left.read(64 * 1024)
				if chunk != right.read(64 * 1024):
					return False
				if not chunk:
					return True
	except OSError:
		return False


def _sound_target(sounds_folder, source) -> str:
	"""Return where ``source`` goes in a Sounds folder, reusing an identical copy."""
	base, extension = os.path.splitext(os.path.basename(source))
	candidate = os.path.join(sounds_folder, base + extension)
	counter = 2
	while os.path.exists(candidate):
		if _same_contents(candidate, source):
			return candidate
		candidate = os.path.join(sounds_folder, f"{base} {counter}{extension}")
		counter += 1
	return candidate


def _stored_sound(folder, sound) -> str:
	"""Return the scheme.json path for ``sound``, copying an outside file into Sounds."""
	absolute = _absolute_sound_path(folder, sound)
	if _is_within(folder, absolute):
		return os.path.relpath(absolute, folder).replace(os.sep, "/")
	if not os.path.isfile(absolute):
		# Keep a missing outside file as it is; the dialog reports it when played.
		return absolute
	sounds_folder = os.path.join(folder, SOUNDS_FOLDER_NAME)
	os.makedirs(sounds_folder, exist_ok=True)
	target = _sound_target(sounds_folder, absolute)
	if not os.path.exists(target):
		shutil.copy2(absolute, target)
	return os.path.relpath(target, folder).replace(os.sep, "/")


def _write_json(path, payload) -> None:
	"""Write JSON through a temporary file so a failed write keeps the old file."""
	folder = os.path.dirname(path)
	handle, temporary = tempfile.mkstemp(prefix=".scheme-", suffix=".tmp", dir=folder)
	try:
		with os.fdopen(handle, "w", encoding="utf-8") as stream:
			json.dump(payload, stream, ensure_ascii=False, indent="\t")
		os.replace(temporary, path)
	except BaseException:
		try:
			os.remove(temporary)
		except OSError:
			pass
		raise


def read_scheme_folder(folder):
	"""Return ``(name, scheme)`` from a scheme folder, with absolute sound paths."""
	with open(os.path.join(folder, SCHEME_FILE_NAME), encoding="utf-8") as stream:
		raw = _as_dict(json.load(stream))
	name = str(raw.get("name") or "").strip() or os.path.basename(folder)
	items = {}
	for item_id, settings in _as_dict(raw.get("items")).items():
		clean = normalize_item_settings(settings)
		if clean.get("sound"):
			clean["sound"] = _absolute_sound_path(folder, clean["sound"])
		if clean:
			items[str(item_id)] = clean
	return name, {"items": items, "custom": normalize_custom(raw.get("custom"))}


def write_scheme_folder(folder, name, scheme) -> None:
	"""Write ``scheme`` to its folder, copying outside sounds into its Sounds folder."""
	os.makedirs(folder, exist_ok=True)
	items = {}
	for item_id, settings in _as_dict(scheme.get("items")).items():
		clean = normalize_item_settings(settings)
		if not clean:
			continue
		if clean.get("sound"):
			clean["sound"] = _stored_sound(folder, clean["sound"])
		items[str(item_id)] = clean
	_write_json(
		os.path.join(folder, SCHEME_FILE_NAME),
		{
			"format": SCHEME_FILE_FORMAT,
			"version": 1,
			"name": str(name),
			"items": items,
			"custom": normalize_custom(scheme.get("custom")),
		},
	)


def _unique_key(name, taken) -> str:
	lowered = {key.lower() for key in taken}
	if name.lower() not in lowered:
		return name
	counter = 2
	while f"{name} {counter}".lower() in lowered:
		counter += 1
	return f"{name} {counter}"


def load_scheme_folders(root):
	"""Return ``(schemes, folders)`` for every scheme folder under ``root``.

	Default comes first, then the other schemes by name. Folders without a
	scheme.json, and hidden folders, are skipped.
	"""
	found = []
	try:
		entries = os.listdir(root)
	except OSError:
		entries = []
	for entry in entries:
		folder = os.path.join(root, entry)
		if entry.startswith(".") or not os.path.isfile(os.path.join(folder, SCHEME_FILE_NAME)):
			continue
		try:
			name, scheme = read_scheme_folder(folder)
		except Exception:
			log.warning("ClassicSpeech: skipped unreadable scheme folder %s", folder, exc_info=True)
			continue
		found.append((name, scheme, folder))
	found.sort(key=lambda row: (row[0] != DEFAULT_SCHEME_NAME, row[0].lower(), row[2].lower()))
	schemes = {}
	folders = {}
	for name, scheme, folder in found:
		name = _unique_key(name, schemes)
		schemes[name] = scheme
		folders[name] = folder
	return schemes, folders


def _read_active_scheme(root, name):
	"""Return the named scheme from its folder, for the speech runtime."""
	folder = os.path.join(root, folder_name_for(name))
	try:
		if os.path.isfile(os.path.join(folder, SCHEME_FILE_NAME)):
			found, scheme = read_scheme_folder(folder)
			if found.lower() == name.lower():
				return scheme
	except Exception:
		log.debug("ClassicSpeech: scheme folder read failed: %s", folder, exc_info=True)
	schemes, _folders = load_scheme_folders(root)
	for key in (name, DEFAULT_SCHEME_NAME):
		if key in schemes:
			return schemes[key]
	return next(iter(schemes.values()), {"items": {}, "custom": normalize_custom({})})


def _delete_scheme_folder(folder) -> None:
	"""Remove a deleted scheme. scheme.json goes first, so a locked sound cannot bring it back."""
	try:
		os.remove(os.path.join(folder, SCHEME_FILE_NAME))
	except FileNotFoundError:
		pass
	shutil.rmtree(folder, ignore_errors=True)


def _rename_scheme_folder(root, folder, base) -> str:
	"""Give a scheme folder its scheme's name; keep the old name if Windows refuses."""
	current = os.path.basename(folder)
	if current == base:
		return folder
	if current.lower() == base.lower():
		target = os.path.join(root, base)
	elif re.fullmatch(re.escape(base) + r" \d+", current, re.IGNORECASE) and os.path.exists(os.path.join(root, base)):
		# Already numbered because another folder has the plain name.
		return folder
	else:
		target = _unique_folder(root, base)
	try:
		os.rename(folder, target)
		return target
	except OSError:
		log.warning("ClassicSpeech: could not rename scheme folder %s to %s", folder, target, exc_info=True)
		return folder


def prepare_scheme_folders(section=None, root=None):
	"""Create the schemes folder with a Default scheme, moving version 1 schemes into folders.

	Returns the schemes folder, or None outside NVDA. Moving is safe to repeat:
	a scheme that already has a folder keeps it.
	"""
	root = root if root is not None else schemes_root()
	if root is None:
		return None
	if section is None:
		from ..settings.config_core import _ensure_classic_speech_section

		section = _ensure_classic_speech_section()
	os.makedirs(root, exist_ok=True)
	raw = section.get(SCHEME_DATA_KEY, "{}")
	if has_legacy_schemes(raw):
		legacy = load_scheme_data(raw)
		existing, _folders = load_scheme_folders(root)
		existing_names = {name.lower() for name in existing}
		for name, scheme in legacy["schemes"].items():
			if name.lower() in existing_names:
				continue
			scheme = {"items": scheme["items"], "custom": legacy["custom"]}
			write_scheme_folder(_unique_folder(root, folder_name_for(name)), name, scheme)
		section[SCHEME_DATA_KEY] = dump_switches(legacy["enabled"], legacy["activeScheme"])
		log.info("ClassicSpeech: moved Speech and Sound Schemes into %s", root)
		invalidate_runtime_cache()
	schemes, _folders = load_scheme_folders(root)
	if not schemes:
		write_scheme_folder(_unique_folder(root, DEFAULT_SCHEME_NAME), DEFAULT_SCHEME_NAME, {"items": {}})
		invalidate_runtime_cache()
	return root


# -- speech runtime -------------------------------------------------------------

def _read_raw():
	try:
		from ..settings.config_core import _read_classic_speech_section
		section = _read_classic_speech_section()
		return section.get(SCHEME_DATA_KEY, "{}")
	except Exception:
		return "{}"


class _RuntimeCache:
	raw = None
	generation = -1
	data = None
	items = {}
	enabled = False


_runtime = _RuntimeCache()
_generation = 0


def invalidate_runtime_cache():
	"""Make the next speech lookup reread the switches and the active scheme."""
	global _generation
	_generation += 1


def runtime_data():
	"""Return the switches and the active scheme's configured items.

	Speech calls this for every sequence, so it rereads the scheme folder only
	after ``invalidate_runtime_cache`` or a change to the stored switches.
	"""
	raw = _read_raw()
	if _runtime.generation == _generation and _runtime.data is not None:
		if raw is _runtime.raw or raw == _runtime.raw:
			_runtime.raw = raw
			return _runtime
	root = schemes_root()
	if root is None or has_legacy_schemes(raw):
		legacy = load_scheme_data(raw)
		switches = {"enabled": legacy["enabled"], "activeScheme": legacy["activeScheme"]}
		scheme = legacy["schemes"].get(legacy["activeScheme"], {"items": {}})
	else:
		switches = load_switches(raw)
		try:
			scheme = _read_active_scheme(root, switches["activeScheme"])
		except Exception:
			log.debugWarning("ClassicSpeech: active scheme could not be read", exc_info=True)
			scheme = {"items": {}}
	_runtime.items = {
		item_id: settings
		for item_id, settings in _as_dict(scheme.get("items")).items()
		if item_is_configured(settings)
	}
	_runtime.enabled = bool(switches["enabled"]) and bool(_runtime.items)
	_runtime.data = switches
	_runtime.raw = raw
	_runtime.generation = _generation
	return _runtime


def active_items():
	"""Return ``{item_id: settings}`` for configured items, or ``{}`` when disabled."""
	runtime = runtime_data()
	return runtime.items if runtime.enabled else {}


def schemes_active() -> bool:
	return runtime_data().enabled


# -- editing --------------------------------------------------------------------

class SchemeStore:
	"""Transactional editor for Speech and Sound Schemes.

	Changes stay in memory until ``apply``, which writes each changed scheme to
	its folder, renames and deletes folders, and saves the switches. Imported
	packages wait in a temporary folder until then. Without a schemes folder
	(only in tests), ``apply`` writes the version 1 JSON instead.
	"""

	def __init__(self, section=None, root=None):
		if section is None:
			from ..settings.config_core import _ensure_classic_speech_section
			section = _ensure_classic_speech_section()
		self._section = section
		self._root = root if root is not None else schemes_root()
		self._staging = []
		if self._root is not None:
			prepare_scheme_folders(section, self._root)
		self._load()

	def _load(self):
		self._opening_raw = self._section.get(SCHEME_DATA_KEY, "{}")
		if self._root is None:
			legacy = load_scheme_data(self._opening_raw)
			schemes = {
				name: {"items": scheme["items"], "custom": copy.deepcopy(legacy["custom"])}
				for name, scheme in legacy["schemes"].items()
			}
			enabled, active = legacy["enabled"], legacy["activeScheme"]
			self._folders = {}
		else:
			switches = load_switches(self._opening_raw)
			schemes, self._folders = load_scheme_folders(self._root)
			if not schemes:
				schemes = {DEFAULT_SCHEME_NAME: {"items": {}, "custom": normalize_custom({})}}
			enabled, active = switches["enabled"], switches["activeScheme"]
		if active not in schemes:
			active = DEFAULT_SCHEME_NAME if DEFAULT_SCHEME_NAME in schemes else next(iter(schemes))
		self.data = {"enabled": bool(enabled), "activeScheme": active, "schemes": schemes}
		self._remember_opening()

	def _remember_opening(self):
		self._opening = copy.deepcopy(self.data)
		self._opening_folders = dict(self._folders)
		self._opening_by_folder = {
			os.path.normcase(folder): (name, copy.deepcopy(self.data["schemes"][name]))
			for name, folder in self._folders.items()
		}
		self._deleted_folders = []

	# -- schemes ---------------------------------------------------------
	@property
	def root(self):
		"""The schemes folder, or None when schemes are kept in the config."""
		return self._root

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

	def _unique_name(self, base, ignore=None):
		base = str(base or "").strip() or DEFAULT_SCHEME_NAME
		taken = [name for name in self.data["schemes"] if name != ignore]
		return _unique_key(base, taken)

	def add_scheme(self, name, copy_from=None):
		"""Add a scheme, empty or copied from ``copy_from``, and make it active.

		A new empty scheme keeps the active scheme's added fonts, sizes, styles
		and window classes, so the item list does not change.
		"""
		name = self._unique_name(name)
		active = self.data["schemes"].get(self.data["activeScheme"], {})
		source = self.data["schemes"].get(copy_from) if copy_from else None
		if source:
			scheme = copy.deepcopy(source)
		else:
			scheme = {"items": {}, "custom": copy.deepcopy(active.get("custom", normalize_custom({})))}
		self.data["schemes"][name] = scheme
		self.data["activeScheme"] = name
		return name

	def rename_scheme(self, old, new):
		new = str(new or "").strip()
		if not new or old not in self.data["schemes"]:
			return old
		if new == old:
			return old
		new = self._unique_name(new, ignore=old)
		renamed = {}
		for name, scheme in self.data["schemes"].items():
			renamed[new if name == old else name] = scheme
		self.data["schemes"] = renamed
		if old in self._folders:
			self._folders[new] = self._folders.pop(old)
		if self.data["activeScheme"] == old:
			self.data["activeScheme"] = new
		return new

	def delete_scheme(self, name):
		if name not in self.data["schemes"] or len(self.data["schemes"]) <= 1:
			return False
		del self.data["schemes"][name]
		folder = self._folders.pop(name, None)
		if folder:
			self._deleted_folders.append(folder)
		if self.data["activeScheme"] == name:
			self.data["activeScheme"] = next(iter(self.data["schemes"]))
		return True

	# -- items -----------------------------------------------------------
	def _scheme(self):
		return self.data["schemes"][self.data["activeScheme"]]

	def _items(self):
		return self._scheme().setdefault("items", {})

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
	def _custom_lists(self):
		"""The added entry lists to change: the active scheme's, or every scheme's in the config."""
		schemes = self.data["schemes"].values() if self._root is None else [self._scheme()]
		return [scheme.setdefault("custom", normalize_custom({})) for scheme in schemes]

	def custom_entries(self):
		return normalize_custom(self._scheme().get("custom"))

	def add_custom_entry(self, kind, value):
		if kind not in CUSTOM_KINDS:
			raise KeyError(kind)
		value = str(value or "").strip()
		if not value or value in self.custom_entries()[kind]:
			return False
		for custom in self._custom_lists():
			values = custom.setdefault(kind, [])
			if value not in values:
				values.append(value)
		return True

	def remove_custom_entry(self, kind, value):
		if value not in self.custom_entries().get(kind, []):
			return False
		for custom in self._custom_lists():
			values = custom.get(kind, [])
			if value in values:
				values.remove(value)
		return True

	# -- sharing ---------------------------------------------------------
	def export_scheme(self, name, path):
		"""Write scheme ``name``, with its sounds, to a package; return missing sounds."""
		from . import packages

		return packages.write_scheme_package(path, name, self.data["schemes"][name])

	def import_package(self, path):
		"""Add the scheme in package ``path`` as a new, active scheme; return its name.

		The package's sounds wait in a temporary folder until ``apply`` copies
		them into the new scheme's folder, so Cancel leaves no trace.
		"""
		from . import packages

		staging = tempfile.mkdtemp(prefix="ClassicSpeech-import-")
		try:
			name, scheme = packages.read_scheme_package(path, staging)
		except BaseException:
			shutil.rmtree(staging, ignore_errors=True)
			raise
		self._staging.append(staging)
		name = self._unique_name(name)
		self.data["schemes"][name] = scheme
		self.data["activeScheme"] = name
		return name

	def cleanup(self):
		"""Remove temporary folders left by imports."""
		for staging in self._staging:
			shutil.rmtree(staging, ignore_errors=True)
		self._staging = []

	# -- transaction -----------------------------------------------------
	def apply(self):
		if self._root is None:
			self._apply_to_config()
		else:
			self._apply_to_folders()
		invalidate_runtime_cache()
		self.cleanup()
		try:
			import config
			save = getattr(config.conf, "save", None)
			if callable(save):
				save()
		except Exception:
			raise

	def _apply_to_config(self):
		schemes = self.data["schemes"]
		self._section[SCHEME_DATA_KEY] = dump_scheme_data({
			"enabled": self.data["enabled"],
			"activeScheme": self.data["activeScheme"],
			"schemes": {name: {"items": scheme.get("items", {})} for name, scheme in schemes.items()},
			"custom": self._scheme().get("custom", {}),
		})

	def _apply_to_folders(self):
		"""Write changed schemes, then delete and rename folders.

		Deleting comes after writing, so a scheme copied from a deleted one in
		the same session still gets its sounds.
		"""
		root = self._root
		os.makedirs(root, exist_ok=True)
		folders = {}
		for name, scheme in self.data["schemes"].items():
			folder = self._folders.get(name)
			if not folder or not os.path.isdir(folder):
				folder = _unique_folder(root, folder_name_for(name))
				write_scheme_folder(folder, name, scheme)
			else:
				opening = self._opening_by_folder.get(os.path.normcase(folder))
				if opening is None or opening != (name, scheme):
					write_scheme_folder(folder, name, scheme)
			folders[name] = folder
		for folder in self._deleted_folders:
			_delete_scheme_folder(folder)
		for name, folder in folders.items():
			folders[name] = _rename_scheme_folder(root, folder, folder_name_for(name))
		self._section[SCHEME_DATA_KEY] = dump_switches(self.data["enabled"], self.data["activeScheme"])
		schemes, self._folders = load_scheme_folders(root)
		active = self.data["activeScheme"]
		self.data["schemes"] = schemes or {DEFAULT_SCHEME_NAME: {"items": {}, "custom": normalize_custom({})}}
		if active not in self.data["schemes"]:
			self.data["activeScheme"] = next(iter(self.data["schemes"]))

	def mark_applied(self):
		self._opening_raw = self._section.get(SCHEME_DATA_KEY, "{}")
		self._remember_opening()

	def cancel(self):
		self._section[SCHEME_DATA_KEY] = self._opening_raw
		invalidate_runtime_cache()
		self.data = copy.deepcopy(self._opening)
		self._folders = dict(self._opening_folders)
		self._deleted_folders = []
		self.cleanup()

	def is_dirty(self) -> bool:
		return self.data != self._opening or bool(self._deleted_folders)


def sound_file_exists(path) -> bool:
	try:
		return bool(path) and os.path.isfile(path)
	except Exception:
		return False


def set_schemes_enabled(enabled: bool) -> bool:
	"""Persist the master switch without opening the dialog (used by a gesture)."""
	from ..settings.config_core import _ensure_classic_speech_section

	section = _ensure_classic_speech_section()
	raw = section.get(SCHEME_DATA_KEY, "{}")
	if schemes_root() is None or has_legacy_schemes(raw):
		data = load_scheme_data(raw)
		data["enabled"] = bool(enabled)
		section[SCHEME_DATA_KEY] = dump_scheme_data(data)
	else:
		switches = load_switches(raw)
		section[SCHEME_DATA_KEY] = dump_switches(enabled, switches["activeScheme"])
	invalidate_runtime_cache()
	return bool(enabled)


def cycle_active_scheme():
	"""Switch to the next named scheme and return its name."""
	from ..settings.config_core import _ensure_classic_speech_section

	section = _ensure_classic_speech_section()
	raw = section.get(SCHEME_DATA_KEY, "{}")
	root = schemes_root()
	if root is None or has_legacy_schemes(raw):
		data = load_scheme_data(raw)
		names = list(data["schemes"].keys())
		index = names.index(data["activeScheme"]) if data["activeScheme"] in names else -1
		data["activeScheme"] = names[(index + 1) % len(names)]
		section[SCHEME_DATA_KEY] = dump_scheme_data(data)
		active = data["activeScheme"]
	else:
		switches = load_switches(raw)
		names = list(load_scheme_folders(root)[0]) or [DEFAULT_SCHEME_NAME]
		index = names.index(switches["activeScheme"]) if switches["activeScheme"] in names else -1
		active = names[(index + 1) % len(names)]
		section[SCHEME_DATA_KEY] = dump_switches(switches["enabled"], active)
	invalidate_runtime_cache()
	return active
