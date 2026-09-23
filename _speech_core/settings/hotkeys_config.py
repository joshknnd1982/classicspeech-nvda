"""Hotkeys panel settings helpers."""

from .config_core import _ensure_classic_speech_section, _read_classic_speech_section, _set_nvda_setting
from .constants import (
	HOTKEY_FORMAT_ABBREVIATED_NO_PLUS,
	HOTKEY_FORMAT_EXPANDED_NO_PLUS,
	HOTKEY_FORMAT_NATIVE,
	HOTKEY_MODE_BOTH,
	HOTKEY_MODE_CHOICES,
	HOTKEY_MODE_DIALOGS,
	HOTKEY_MODE_FLAGS,
	HOTKEY_MODE_MENUS,
	HOTKEY_MODE_OFF,
	HOTKEY_TYPES_ACCESS,
	HOTKEY_TYPES_BOTH,
	HOTKEY_TYPES_COMMAND,
	HOTKEY_TYPES_FLAGS,
	HOTKEY_TYPES_NONE,
)


def _get_hotkey_mode():
	conf = _read_classic_speech_section()
	try:
		mode = str(conf.get("hotkeyMode", HOTKEY_MODE_BOTH))
	except Exception:
		mode = HOTKEY_MODE_BOTH
	valid = {HOTKEY_MODE_OFF, HOTKEY_MODE_DIALOGS, HOTKEY_MODE_MENUS, HOTKEY_MODE_BOTH}
	if mode not in valid:
		mode = HOTKEY_MODE_BOTH
	return mode


def _set_hotkey_mode(mode: str):
	conf = _ensure_classic_speech_section()
	mode = str(mode or HOTKEY_MODE_BOTH)
	valid = {HOTKEY_MODE_OFF, HOTKEY_MODE_DIALOGS, HOTKEY_MODE_MENUS, HOTKEY_MODE_BOTH}
	if mode not in valid:
		mode = HOTKEY_MODE_BOTH
	conf["hotkeyMode"] = mode
	_set_nvda_setting(
		"presentation",
		"reportKeyboardShortcuts",
		mode != HOTKEY_MODE_OFF,
	)
	return mode


def _get_hotkey_mode_label(mode: str):
	mode = str(mode or HOTKEY_MODE_BOTH)
	for label, value in HOTKEY_MODE_CHOICES:
		if value == mode:
			return label
	return "Both"


def _get_hotkey_format():
	conf = _read_classic_speech_section()
	try:
		format_value = str(conf.get("hotkeyFormat", HOTKEY_FORMAT_NATIVE))
	except Exception:
		format_value = HOTKEY_FORMAT_NATIVE
	valid = {
		HOTKEY_FORMAT_NATIVE,
		HOTKEY_FORMAT_EXPANDED_NO_PLUS,
		HOTKEY_FORMAT_ABBREVIATED_NO_PLUS,
	}
	if format_value not in valid:
		format_value = HOTKEY_FORMAT_NATIVE
	return format_value


def _set_hotkey_format(format_value: str):
	conf = _ensure_classic_speech_section()
	format_value = str(format_value or HOTKEY_FORMAT_NATIVE)
	valid = {
		HOTKEY_FORMAT_NATIVE,
		HOTKEY_FORMAT_EXPANDED_NO_PLUS,
		HOTKEY_FORMAT_ABBREVIATED_NO_PLUS,
	}
	if format_value not in valid:
		format_value = HOTKEY_FORMAT_NATIVE
	conf["hotkeyFormat"] = format_value
	return format_value



def _get_hotkey_types():
	conf = _read_classic_speech_section()
	try:
		types_value = str(conf.get("hotkeyTypes", HOTKEY_TYPES_BOTH))
	except Exception:
		types_value = HOTKEY_TYPES_BOTH
	valid = {HOTKEY_TYPES_ACCESS, HOTKEY_TYPES_COMMAND, HOTKEY_TYPES_BOTH, HOTKEY_TYPES_NONE}
	if types_value not in valid:
		types_value = HOTKEY_TYPES_BOTH
	return types_value


def _set_hotkey_types(types_value: str):
	conf = _ensure_classic_speech_section()
	types_value = str(types_value or HOTKEY_TYPES_BOTH)
	valid = {HOTKEY_TYPES_ACCESS, HOTKEY_TYPES_COMMAND, HOTKEY_TYPES_BOTH, HOTKEY_TYPES_NONE}
	if types_value not in valid:
		types_value = HOTKEY_TYPES_BOTH
	conf["hotkeyTypes"] = types_value
	return types_value


# ---------------------------------------------------------------------------
# Check list conversion
#
# "Speak hotkeys" and "Which shortcuts to speak" are each really two
# independent choices, so they are presented as NVDA-style check lists (see
# ``check_lists``). The stored values stay the strings earlier versions wrote,
# so a settings file from any version keeps working.
# ---------------------------------------------------------------------------

def hotkey_mode_checked_rows(mode: str):
	"""Return the checked row numbers of the "Speak hotkeys" check list."""
	mode = str(mode or HOTKEY_MODE_BOTH)
	if mode == HOTKEY_MODE_BOTH:
		return list(range(len(HOTKEY_MODE_FLAGS)))
	if mode == HOTKEY_MODE_OFF:
		return []
	return [index for index, (_label, value) in enumerate(HOTKEY_MODE_FLAGS) if value == mode]


def hotkey_mode_from_checked_rows(rows) -> str:
	"""Return the stored "Speak hotkeys" value for those checked rows."""
	values = {
		value
		for index, (_label, value) in enumerate(HOTKEY_MODE_FLAGS)
		if index in set(int(row) for row in rows or [])
	}
	if not values:
		return HOTKEY_MODE_OFF
	if len(values) >= len(HOTKEY_MODE_FLAGS):
		return HOTKEY_MODE_BOTH
	return values.pop()


def hotkey_types_checked_rows(types_value: str):
	"""Return the checked row numbers of the "Which shortcuts to speak" list."""
	types_value = str(types_value or HOTKEY_TYPES_BOTH)
	if types_value == HOTKEY_TYPES_BOTH:
		return list(range(len(HOTKEY_TYPES_FLAGS)))
	if types_value == HOTKEY_TYPES_NONE:
		return []
	return [index for index, (_label, value) in enumerate(HOTKEY_TYPES_FLAGS) if value == types_value]


def hotkey_types_from_checked_rows(rows) -> str:
	"""Return the stored "Which shortcuts to speak" value for those rows."""
	values = {
		value
		for index, (_label, value) in enumerate(HOTKEY_TYPES_FLAGS)
		if index in set(int(row) for row in rows or [])
	}
	if not values:
		return HOTKEY_TYPES_NONE
	if len(values) >= len(HOTKEY_TYPES_FLAGS):
		return HOTKEY_TYPES_BOTH
	return values.pop()

def _get_hotkey_dialog_access_key_only():
	conf = _read_classic_speech_section()
	try:
		value = conf.get("hotkeyDialogAccessKeyOnly", False)
	except Exception:
		return False
	if isinstance(value, str):
		return value.strip().lower() in {"1", "true", "yes", "on"}
	return bool(value)


def _set_hotkey_dialog_access_key_only(enabled):
	conf = _ensure_classic_speech_section()
	conf["hotkeyDialogAccessKeyOnly"] = bool(enabled)
	return bool(enabled)

