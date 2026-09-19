"""ClassicSpeech keeps its settings in its own file, not in nvda.ini.

The file is ``settings.ini`` in the ClassicSpeech folder of NVDA's user
configuration folder, usually ``%APPDATA%/nvda/ClassicSpeech/settings.ini``,
next to the Schemes folder. It has the same format as nvda.ini and holds what
ClassicSpeech 1.06 and earlier kept in the ``[classicSpeech]`` section of
nvda.ini. The first time this version starts, it moves that section into
settings.ini.

While NVDA runs, the settings stay in NVDA's base configuration as the
base-only ``classicSpeech`` section, where every ClassicSpeech module reads and
writes them. They are saved when NVDA saves its configuration: the base
configuration's ``write`` is wrapped so that it saves settings.ini and leaves
the section out of nvda.ini. The wrapper belongs to the base configuration
object, not to the plugin, because NVDA stops global plugins before it saves
its configuration on exit. If settings.ini can't be written, the section stays
in nvda.ini so nothing is lost, and the next start moves it again.

Reverting to the saved configuration reloads settings.ini. Resetting NVDA to
factory defaults starts ClassicSpeech from its defaults too; they replace
settings.ini the next time NVDA saves.
"""
from __future__ import annotations

import contextlib
import os
import re
import tempfile

from .nvda_settings_backup import CONFIG_SECTION, _may_write_files, data_folder

SETTINGS_FILE_NAME = "settings.ini"

# Set on NVDA's base configuration object once ClassicSpeech's settings are
# loaded into it. A new base configuration (after a reset) starts without it.
_LOADED_MARKER = "_classicSpeechSettingsLoaded"
_ORIGINAL_WRITE = "_classicSpeechOriginalWrite"


def _log():
	import logHandler

	return logHandler.log


def settings_path():
	folder = data_folder()
	return os.path.join(folder, SETTINGS_FILE_NAME) if folder else None


def _new_configobj(path=None):
	from configobj import ConfigObj

	if path is None:
		return ConfigObj(indent_type="\t", encoding="UTF-8")
	return ConfigObj(path, indent_type="\t", encoding="UTF-8", file_error=True)


def _stored_values(section):
	"""Return a section's stored values as plain data, as nvda.ini would hold them.

	Values are read without interpolation, and values that validation only
	filled in with defaults are left out, as ConfigObj does when it writes.
	"""
	defaults = set(getattr(section, "defaults", ()) or ())
	values = {}
	for key in list(section.keys()):
		if key in defaults:
			continue
		value = dict.__getitem__(section, key) if isinstance(section, dict) else section[key]
		if hasattr(value, "keys"):
			value = _stored_values(value)
		elif isinstance(value, (list, tuple)):
			value = list(value)
		values[key] = value
	return values


def load_settings_file(path=None):
	"""Return the settings in settings.ini as plain data, or None when there are none.

	An unreadable file is kept as ``settings.ini.corrupted.bak`` so nothing is
	lost, and ClassicSpeech starts from its defaults.
	"""
	path = path or settings_path()
	if not path or not os.path.isfile(path):
		return None
	try:
		return _stored_values(_new_configobj(path))
	except Exception:
		backup = path + ".corrupted.bak"
		_log().error(
			"ClassicSpeech: could not read %s; starting from default settings. "
			"The file is kept as %s.",
			path,
			backup,
			exc_info=True,
		)
		with contextlib.suppress(OSError):
			os.replace(path, backup)
		return None


def write_settings_file(section, path=None):
	"""Save a ClassicSpeech settings section to settings.ini. Returns True when saved."""
	path = path or settings_path()
	if not path or not _may_write_files():
		return False
	folder = os.path.dirname(path)
	os.makedirs(folder, exist_ok=True)
	output = _new_configobj()
	output.update(_stored_values(section))
	output.newlines = "\r\n"
	handle, temporary = tempfile.mkstemp(prefix="settings-", suffix=".tmp", dir=folder)
	os.close(handle)
	try:
		output.filename = temporary
		output.write()
		os.replace(temporary, path)
	except Exception:
		with contextlib.suppress(OSError):
			os.remove(temporary)
		raise
	return True


def _base_configuration(conf):
	profiles = getattr(conf, "profiles", None)
	return profiles[0] if profiles else conf


def _nvda_ini_has_section(base, path):
	"""True when nvda.ini on disk still has a ``[classicSpeech]`` section newer than settings.ini.

	ClassicSpeech 1.06 and earlier saved the section there. A section NVDA
	creates in memory for a base-only section is not in the file, so it doesn't
	count. A section older than settings.ini is a leftover that NVDA didn't save
	over yet.
	"""
	nvda_ini = getattr(base, "filename", None)
	if not isinstance(nvda_ini, str) or not os.path.isfile(nvda_ini):
		return False
	try:
		with open(nvda_ini, encoding="utf-8", errors="replace") as stream:
			found = any(re.match(r"\s*\[\s*classicSpeech\s*\]\s*$", line) for line in stream)
	except OSError:
		return False
	if not found:
		return False
	if path and os.path.isfile(path):
		return os.path.getmtime(nvda_ini) >= os.path.getmtime(path)
	return True


def load_into_nvda(conf=None, *, factory_defaults=False):
	"""Load ClassicSpeech's settings into NVDA's base configuration.

	Does nothing when they are already loaded into this base configuration,
	which is the case when NVDA reloads its plugins. Returns True when the
	settings came from nvda.ini, so they were moved into settings.ini.
	"""
	if conf is None:
		import config

		conf = config.conf
	base = _base_configuration(conf)
	moved = False
	if not getattr(base, _LOADED_MARKER, False):
		path = settings_path()
		if not factory_defaults and path:
			current = base.get(CONFIG_SECTION) if hasattr(base, "get") else None
			if (
				hasattr(current, "keys")
				and _has_values(_stored_values(current))
				and _nvda_ini_has_section(base, path)
			):
				# An earlier ClassicSpeech kept its settings in nvda.ini: move them.
				moved = True
				try:
					write_settings_file(current, path)
					_log().info("ClassicSpeech: moved its settings from nvda.ini to %s", path)
				except Exception:
					_log().error("ClassicSpeech: could not write %s", path, exc_info=True)
			else:
				values = load_settings_file(path)
				if values is not None:
					base[CONFIG_SECTION] = values
		with contextlib.suppress(Exception):
			setattr(base, _LOADED_MARKER, True)
	_wrap_nvda_ini_write(base)
	return moved


def _has_values(values):
	"""True when settings hold at least one value, not only empty sections."""
	return any(_has_values(value) if isinstance(value, dict) else True for value in values.values())


def _wrap_nvda_ini_write(base):
	"""Save settings.ini whenever NVDA writes nvda.ini, and keep the section out of nvda.ini."""
	if not isinstance(getattr(base, "sections", None), list) or not callable(getattr(base, "write", None)):
		return
	original = getattr(base, _ORIGINAL_WRITE, None)
	if original is None:
		original = base.write
		setattr(base, _ORIGINAL_WRITE, original)

	def write(outfile=None, section=None):
		if section is not None:
			# ConfigObj writing one of the sections that go into nvda.ini.
			return original(outfile, section)
		hidden = False
		settings = dict.get(base, CONFIG_SECTION)
		if hasattr(settings, "keys"):
			try:
				hidden = write_settings_file(settings) and _hide_section(base)
			except Exception:
				_log().error(
					"ClassicSpeech: could not save settings.ini; keeping ClassicSpeech settings in nvda.ini",
					exc_info=True,
				)
		try:
			return original(outfile)
		finally:
			if hidden:
				_show_section(base)

	base.write = write


def _hide_section(base):
	"""Leave the section out of the next nvda.ini write; it stays readable meanwhile."""
	sections = base.sections
	if CONFIG_SECTION in sections:
		sections.remove(CONFIG_SECTION)
		return True
	return False


def _show_section(base):
	if dict.__contains__(base, CONFIG_SECTION) and CONFIG_SECTION not in base.sections:
		base.sections.append(CONFIG_SECTION)
