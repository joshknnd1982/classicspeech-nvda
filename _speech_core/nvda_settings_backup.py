"""Put NVDA back the way it was before ClassicSpeech changed it.

ClassicSpeech keeps its own settings in two places in NVDA's user
configuration folder (usually ``%APPDATA%/nvda``):

- the ``[classicSpeech]`` section of ``nvda.ini``;
- the ``ClassicSpeech`` folder, which holds the speech and sound schemes and
  this module's backup file.

Some ClassicSpeech settings also change NVDA's own settings, such as the
verbosity profiles' effect on Report object descriptions, or the NVDA options
shown on the Document Reading / Proofing and Browse Mode pages. Before
ClassicSpeech changes one of NVDA's settings for the first time, it records in
``ClassicSpeech/nvda-settings-backup.json`` whether the setting was set, and
its value, in the configuration it changes: the base configuration or a named
configuration profile. After each change it records the value it wrote.

Resetting ClassicSpeech, or removing it, puts each recorded setting back to its
earlier value, but only while the setting still has the value ClassicSpeech
gave it. A setting changed afterwards in NVDA's own settings keeps the user's
value. Then the ``[classicSpeech]`` section and the ``ClassicSpeech`` folder are
deleted.

``installTasks.py`` loads this file on its own when NVDA removes ClassicSpeech,
before any add-on runs, so it must not import other ClassicSpeech modules.
"""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import sys
import tempfile

CONFIG_SECTION = "classicSpeech"
DATA_FOLDER_NAME = "ClassicSpeech"
BACKUP_FILE_NAME = "nvda-settings-backup.json"
BACKUP_FORMAT = "ClassicSpeech NVDA settings backup"
BACKUP_VERSION = 1

# Tests point this at a temporary folder that stands in for NVDA's user
# configuration folder. NVDA uses its real configuration folder.
_CONFIG_FOLDER_OVERRIDE = None


def _log():
	try:
		from logHandler import log

		return log
	except Exception:
		return None


def _debug(message, *args):
	log = _log()
	if log is not None:
		log.debug(
			"ClassicSpeech NVDA settings backup: " + message,
			*args,
			exc_info=sys.exc_info()[0] is not None,
		)


def _config():
	import config

	return config.conf


# -- folders --------------------------------------------------------------------

def config_folder():
	"""Return NVDA's user configuration folder, or None outside NVDA."""
	if _CONFIG_FOLDER_OVERRIDE is not None:
		return _CONFIG_FOLDER_OVERRIDE
	folder = None
	try:
		import NVDAState

		folder = NVDAState.WritePaths.configDir
	except Exception:
		try:
			import globalVars

			folder = globalVars.appArgs.configPath
		except Exception:
			folder = None
	return os.path.abspath(folder) if folder else None


def data_folder():
	"""Return the ClassicSpeech folder in NVDA's configuration folder, or None."""
	folder = config_folder()
	return os.path.join(folder, DATA_FOLDER_NAME) if folder else None


def backup_path():
	folder = data_folder()
	return os.path.join(folder, BACKUP_FILE_NAME) if folder else None


def _may_write_files():
	"""False when NVDA must not write to disk, such as on secure screens."""
	if _CONFIG_FOLDER_OVERRIDE is not None:
		return True
	try:
		import NVDAState

		return bool(NVDAState.shouldWriteToDisk())
	except Exception:
		try:
			import globalVars

			return not bool(getattr(globalVars.appArgs, "secure", False))
		except Exception:
			return True


# -- values ---------------------------------------------------------------------

def _plain(value):
	"""Return ``value`` as JSON data: a section becomes a dict, anything else its text."""
	if value is None or isinstance(value, (bool, int, float, str)):
		return value
	if isinstance(value, (list, tuple)):
		return [_plain(item) for item in value]
	if hasattr(value, "items"):
		return {str(key): _plain(item) for key, item in value.items()}
	# Such as NVDA's FeatureFlag, which nvda.ini stores as its name.
	return str(value)


def _text(value):
	"""Compare values the way NVDA does: by the text nvda.ini would hold."""
	if isinstance(value, (list, tuple)):
		return "[" + "\x1f".join(_text(item) for item in value) + "]"
	if isinstance(value, dict):
		return "{" + "\x1f".join(f"{key}={_text(item)}" for key, item in sorted(value.items())) + "}"
	return str(value)


def _same(first, second):
	first = first or {"set": False}
	second = second or {"set": False}
	if bool(first.get("set")) != bool(second.get("set")):
		return False
	return not first.get("set") or _text(first.get("value")) == _text(second.get("value"))


# -- NVDA configuration profiles ---------------------------------------------------

def _base_profile(conf):
	profiles = getattr(conf, "profiles", None)
	return profiles[0] if profiles else conf


def _write_target(conf, path):
	"""Return ``(profile, profile name, lasting)`` for a write through ``config.conf``.

	NVDA writes a setting into the most recently activated configuration
	profile, or into the base configuration for sections that only live there.
	The base configuration's name is None. ClassicSpeech's voice profiles push
	temporary unnamed profiles while they speak; a write into one of those does
	not last, so there is nothing to record.
	"""
	profiles = getattr(conf, "profiles", None)
	if not profiles:
		return conf, None, True
	if path and path[0] in getattr(conf, "BASE_ONLY_SECTIONS", ()):
		return profiles[0], None, True
	profile = profiles[-1]
	if profile is profiles[0]:
		return profile, None, True
	name = getattr(profile, "name", None)
	if isinstance(name, str) and name and getattr(profile, "filename", None):
		return profile, name, True
	return profile, None, False


def _profile_named(conf, name):
	"""Return the base configuration (None) or a named profile, loading it if needed."""
	if name is None:
		return _base_profile(conf)
	cache = getattr(conf, "_profileCache", None)
	if isinstance(cache, dict) and name in cache:
		return cache[name]
	load = getattr(conf, "_getProfile", None)
	if callable(load):
		try:
			return load(name)
		except Exception:
			# The user renamed or deleted the profile.
			_debug("profile %r is not available", name)
	return None


def _raw_state(profile, path, key):
	"""Return ``{"set": False}`` or ``{"set": True, "value": ...}`` for one profile."""
	section = profile
	try:
		for part in path:
			if not hasattr(section, "keys") or part not in section:
				return {"set": False}
			section = section[part]
		if not hasattr(section, "keys") or key not in section:
			return {"set": False}
		return {"set": True, "value": _plain(section[key])}
	except Exception:
		return {"set": False}


def _set_raw(profile, path, key, value):
	section = profile
	for part in path:
		if part not in section or not hasattr(section[part], "keys"):
			section[part] = {}
		section = section[part]
	section[key] = value


def _delete_raw(profile, path, key):
	section = profile
	for part in path:
		if not hasattr(section, "keys") or part not in section:
			return
		section = section[part]
	if hasattr(section, "keys") and key in section:
		del section[key]


def _mark_changed(conf, name):
	"""Make NVDA save a named profile; it always saves the base configuration."""
	dirty = getattr(conf, "_dirtyProfiles", None)
	if name is not None and isinstance(dirty, set):
		dirty.add(name)


def _refresh(conf):
	"""Make ``config.conf`` read the profiles again after they were edited directly."""
	refresh = getattr(conf, "_handleProfileSwitch", None)
	if callable(refresh):
		try:
			refresh(shouldNotify=False)
		except Exception:
			_debug("could not refresh NVDA's configuration")


# -- the backup file ------------------------------------------------------------

def _empty_backup():
	return {"format": BACKUP_FORMAT, "version": BACKUP_VERSION, "legacyChecked": False, "settings": []}


def load_backup():
	"""Return the backup file's contents, or an empty backup."""
	path = backup_path()
	backup = _empty_backup()
	if not path or not os.path.isfile(path):
		return backup
	try:
		with open(path, encoding="utf-8") as stream:
			data = json.load(stream)
	except Exception:
		_debug("could not read %s", path)
		return backup
	if isinstance(data, dict) and isinstance(data.get("settings"), list):
		backup["legacyChecked"] = bool(data.get("legacyChecked"))
		backup["settings"] = [entry for entry in data["settings"] if _valid_entry(entry)]
	return backup


def _valid_entry(entry):
	return (
		isinstance(entry, dict)
		and isinstance(entry.get("section"), list)
		and all(isinstance(part, str) for part in entry["section"])
		and isinstance(entry.get("key"), str)
		and (entry.get("profile") is None or isinstance(entry.get("profile"), str))
		and isinstance(entry.get("before"), dict)
		and isinstance(entry.get("after"), dict)
	)


def _save_backup(backup):
	path = backup_path()
	if not path or not _may_write_files():
		return
	folder = os.path.dirname(path)
	os.makedirs(folder, exist_ok=True)
	handle, temporary = tempfile.mkstemp(prefix="backup-", suffix=".tmp", dir=folder)
	try:
		with os.fdopen(handle, "w", encoding="utf-8") as stream:
			json.dump(backup, stream, ensure_ascii=False, indent="\t")
		os.replace(temporary, path)
	except Exception:
		with contextlib.suppress(OSError):
			os.remove(temporary)
		raise


def _find(backup, name, path, key):
	for entry in backup["settings"]:
		if entry.get("profile") == name and tuple(entry["section"]) == tuple(path) and entry["key"] == key:
			return entry
	return None


# -- recording changes ----------------------------------------------------------

@contextlib.contextmanager
def recording_nvda_change(path, key, conf=None):
	"""Record NVDA's setting ``path``/``key`` around a change made inside the block.

	The first change ClassicSpeech makes to a setting records the value it had
	before; every change records the value ClassicSpeech gave it. Recording
	never stops the change itself.
	"""
	path = tuple(path)
	pending = None
	try:
		conf = conf if conf is not None else _config()
		profile, name, lasting = _write_target(conf, path)
		if lasting:
			pending = (profile, name, _raw_state(profile, path, key))
	except Exception:
		_debug("could not read %s/%s before changing it", "/".join(path), key)
	yield
	if pending is None:
		return
	try:
		profile, name, before = pending
		after = _raw_state(profile, path, key)
		if _same(before, after):
			return
		backup = load_backup()
		entry = _find(backup, name, path, key)
		if entry is None:
			entry = {"profile": name, "section": list(path), "key": key, "before": before}
			backup["settings"].append(entry)
		entry["after"] = after
		_save_backup(backup)
	except Exception:
		_debug("could not record the change to %s/%s", "/".join(path), key)


def set_nvda_setting(path, key, value, conf=None):
	"""Set one of NVDA's own settings through ``config.conf``, recording it first."""
	conf = conf if conf is not None else _config()
	path = tuple(path)
	with recording_nvda_change(path, key, conf):
		section = conf
		for part in path:
			if part not in section:
				section[part] = {}
			section = section[part]
		section[key] = value


def legacy_checked():
	return bool(load_backup().get("legacyChecked"))


def record_legacy_changes(implied, conf=None):
	"""Record NVDA settings that an earlier ClassicSpeech changed without keeping a backup.

	``implied`` maps ``(section path, key)`` to the value ClassicSpeech's saved
	settings give that NVDA setting. A setting the base configuration holds with
	exactly that value is recorded as changed by ClassicSpeech from NVDA's
	default, because earlier versions did not record the value it had before.
	This runs once; later changes are recorded as they happen.
	"""
	backup = load_backup()
	if backup.get("legacyChecked"):
		return []
	conf = conf if conf is not None else _config()
	base = _base_profile(conf)
	recorded = []
	for (path, key), value in (implied or {}).items():
		path = tuple(path)
		if _find(backup, None, path, key) is not None:
			continue
		state = _raw_state(base, path, key)
		if state.get("set") and _text(state.get("value")) == _text(_plain(value)):
			backup["settings"].append({
				"profile": None,
				"section": list(path),
				"key": key,
				"before": {"set": False},
				"after": state,
				"assumed": True,
			})
			recorded.append((path, key))
	backup["legacyChecked"] = True
	_save_backup(backup)
	return recorded


def mark_legacy_checked():
	record_legacy_changes({})


def classic_speech_settings_exist(conf=None):
	"""True when NVDA's configuration already holds ClassicSpeech settings."""
	try:
		conf = conf if conf is not None else _config()
		section = _base_profile(conf).get(CONFIG_SECTION)
		return bool(section) and hasattr(section, "keys") and len(section) > 0
	except Exception:
		return False


# -- restoring ------------------------------------------------------------------

def _describe(entry):
	name = entry.get("profile")
	where = "base configuration" if name is None else f"profile {name}"
	return f"{'/'.join(entry['section'])}/{entry['key']} ({where})"


def restore_nvda_settings(conf=None):
	"""Put back NVDA's settings that ClassicSpeech changed.

	Returns ``{"restored": [...], "kept": [...]}``: settings put back to their
	earlier values, and settings kept because they changed after ClassicSpeech
	last set them, or because their profile no longer exists.
	"""
	conf = conf if conf is not None else _config()
	backup = load_backup()
	restored, kept = [], []
	changed_profiles = set()
	for entry in backup["settings"]:
		name = entry.get("profile")
		path = tuple(entry["section"])
		key = entry["key"]
		profile = _profile_named(conf, name)
		if profile is None:
			kept.append(_describe(entry))
			continue
		current = _raw_state(profile, path, key)
		if not _same(current, entry["after"]):
			kept.append(_describe(entry))
			continue
		before = entry["before"]
		try:
			if before.get("set"):
				_set_raw(profile, path, key, before.get("value"))
			elif current.get("set"):
				_delete_raw(profile, path, key)
		except Exception:
			_debug("could not restore %s", _describe(entry))
			kept.append(_describe(entry))
			continue
		restored.append(_describe(entry))
		changed_profiles.add(name)
	for name in changed_profiles:
		_mark_changed(conf, name)
	if changed_profiles:
		_refresh(conf)
	return {"restored": restored, "kept": kept}


def remove_classic_speech_data(conf=None):
	"""Delete the ``[classicSpeech]`` section and the ClassicSpeech folder.

	Returns the folder if some of it could not be deleted, otherwise None.
	"""
	conf = conf if conf is not None else _config()
	base = _base_profile(conf)
	if hasattr(base, "keys") and CONFIG_SECTION in base:
		del base[CONFIG_SECTION]
	_refresh(conf)
	folder = data_folder()
	if not folder or not os.path.isdir(folder) or not _may_write_files():
		return None
	shutil.rmtree(folder, ignore_errors=True)
	return folder if os.path.exists(folder) else None


def save_nvda_configuration(conf=None):
	conf = conf if conf is not None else _config()
	save = getattr(conf, "save", None)
	if callable(save):
		save()


def reset_all(conf=None, save=True):
	"""Restore NVDA's settings, delete every ClassicSpeech setting, then save NVDA's configuration.

	Returns the result of ``restore_nvda_settings`` plus ``"notDeleted"``: the
	ClassicSpeech folder if some of it could not be deleted, otherwise None.
	"""
	conf = conf if conf is not None else _config()
	result = restore_nvda_settings(conf)
	result["notDeleted"] = remove_classic_speech_data(conf)
	if save:
		save_nvda_configuration(conf)
	return result
