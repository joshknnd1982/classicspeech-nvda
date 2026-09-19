"""Native NVDA web and browse-mode settings helpers for ClassicSpeech v3.

These helpers wrap native NVDA ``virtualBuffers`` settings plus the
web-oriented ``documentFormatting`` settings that were intentionally excluded
from the Document Reading / Proofing panel. They do not add web speech
processing or browse-mode rewriting.
"""
from __future__ import annotations

import copy

import config
import logHandler

from ...nvda_settings_backup import nvda_setting_state, restore_nvda_setting, set_nvda_setting

log = logHandler.log

VIRTUAL_BUFFER_KEYS = (
	"maxLineLength",
	"linesPerPage",
	"useScreenLayout",
	"enableOnPageLoad",
	"autoSayAllOnPageLoad",
	"autoPassThroughOnFocusChange",
	"autoPassThroughOnCaretMove",
	"passThroughAudioIndication",
	"trapNonCommandGestures",
	"loadChromiumVBufOnBusyState",
	"browseModeTouchNavigationElements",
)

ANNOTATION_KEYS = (
	"reportDetails",
	"reportAriaDescription",
)

BRAILLE_WEB_KEYS = (
	"reportLiveRegions",
)

WEB_DOCUMENT_FORMATTING_KEYS = (
	"includeLayoutTables",
	"reportHeadings",
	"reportLinks",
	"reportLinkType",
	"reportGraphics",
	"reportLists",
	"reportBlockQuotes",
	"reportGroupings",
	"reportLandmarks",
	"reportArticles",
	"reportFrames",
	"reportFigures",
	"reportClickable",
)

VIRTUAL_BUFFER_DEFAULTS = {
	"maxLineLength": 100,
	"linesPerPage": 25,
	"useScreenLayout": True,
	"enableOnPageLoad": True,
	"autoSayAllOnPageLoad": True,
	"autoPassThroughOnFocusChange": True,
	"autoPassThroughOnCaretMove": False,
	"passThroughAudioIndication": True,
	"trapNonCommandGestures": True,
	"loadChromiumVBufOnBusyState": "DEFAULT",
	"browseModeTouchNavigationElements": ["heading", "link", "formField", "list", "table"],
}

ANNOTATION_DEFAULTS = {
	"reportDetails": True,
	"reportAriaDescription": True,
}

FEATURE_FLAG_DEFAULTS = {
	"loadChromiumVBufOnBusyState": "DEFAULT",
	"reportLiveRegions": "DEFAULT",
}

WEB_DOCUMENT_FORMATTING_DEFAULTS = {
	"includeLayoutTables": False,
	"reportHeadings": True,
	"reportLinks": True,
	"reportLinkType": True,
	"reportGraphics": True,
	"reportLists": True,
	"reportBlockQuotes": True,
	"reportGroupings": True,
	"reportLandmarks": True,
	"reportArticles": False,
	"reportFrames": True,
	"reportFigures": True,
	"reportClickable": True,
}

_INTEGER_VIRTUAL_BUFFER_KEYS = {"maxLineLength", "linesPerPage"}
_LIST_VIRTUAL_BUFFER_KEYS = {"browseModeTouchNavigationElements"}
_FEATURE_FLAG_VIRTUAL_BUFFER_KEYS = {"loadChromiumVBufOnBusyState"}


def _coerce_virtual_buffer_value(key: str, value):
	if key in _INTEGER_VIRTUAL_BUFFER_KEYS:
		try:
			return int(value)
		except Exception:
			return int(VIRTUAL_BUFFER_DEFAULTS[key])
	if key in _LIST_VIRTUAL_BUFFER_KEYS:
		if isinstance(value, (list, tuple, set)):
			return [str(item) for item in value]
		return list(VIRTUAL_BUFFER_DEFAULTS[key])
	if key in _FEATURE_FLAG_VIRTUAL_BUFFER_KEYS:
		return copy.deepcopy(value)
	return bool(value)


def _coerce_document_formatting_value(key: str, value):
	return bool(value)


def _get_section(section_name: str):
	"""Read a config section without materializing a default section."""
	try:
		section = config.conf.get(section_name)
	except Exception:
		return None
	return section if hasattr(section, "get") else None


def get_virtual_buffer_setting(key: str):
	if key not in VIRTUAL_BUFFER_KEYS:
		raise KeyError(key)
	section = _get_section("virtualBuffers")
	value = section.get(key, copy.deepcopy(VIRTUAL_BUFFER_DEFAULTS[key])) if section is not None else copy.deepcopy(VIRTUAL_BUFFER_DEFAULTS[key])
	return _coerce_virtual_buffer_value(key, value)


def set_virtual_buffer_setting(key: str, value) -> None:
	if key not in VIRTUAL_BUFFER_KEYS:
		raise KeyError(key)
	set_nvda_setting(("virtualBuffers",), key, _coerce_virtual_buffer_value(key, value))


def get_web_document_formatting_setting(key: str):
	if key not in WEB_DOCUMENT_FORMATTING_KEYS:
		raise KeyError(key)
	section = _get_section("documentFormatting")
	value = section.get(key, WEB_DOCUMENT_FORMATTING_DEFAULTS[key]) if section is not None else WEB_DOCUMENT_FORMATTING_DEFAULTS[key]
	return _coerce_document_formatting_value(key, value)


def set_web_document_formatting_setting(key: str, value) -> None:
	if key not in WEB_DOCUMENT_FORMATTING_KEYS:
		raise KeyError(key)
	set_nvda_setting(("documentFormatting",), key, _coerce_document_formatting_value(key, value))


def get_annotation_setting(key: str):
	if key not in ANNOTATION_KEYS:
		raise KeyError(key)
	section = _get_section("annotations")
	return bool(section.get(key, ANNOTATION_DEFAULTS[key])) if section is not None else ANNOTATION_DEFAULTS[key]


def set_annotation_setting(key: str, value) -> None:
	if key not in ANNOTATION_KEYS:
		raise KeyError(key)
	set_nvda_setting(("annotations",), key, bool(value))


# The NVDA settings the Web / Browse Mode dialog changes, by section.
_DIALOG_KEYS = (
	("virtualBuffers", VIRTUAL_BUFFER_KEYS),
	("documentFormatting", WEB_DOCUMENT_FORMATTING_KEYS),
	("annotations", ANNOTATION_KEYS),
	("braille", BRAILLE_WEB_KEYS),
)


def capture_web_browse_state() -> dict:
	"""Capture how each NVDA setting this dialog changes is stored, for Cancel.

	Each setting keeps its exact stored state in the configuration NVDA changes:
	whether it is set there, and its raw value, even a malformed legacy one.
	Settings the dialog doesn't change are never touched.
	"""
	state = {}
	for section_name, keys in _DIALOG_KEYS:
		state[section_name] = {}
		for key in keys:
			try:
				state[section_name][key] = nvda_setting_state((section_name,), key)
			except Exception:
				log.debug("ClassicSpeech: could not read %s/%s", section_name, key, exc_info=True)
	return state


def restore_web_browse_state(state: dict) -> None:
	"""Put every captured NVDA setting back exactly as it was stored."""
	if not hasattr(state, "get"):
		return
	for section_name, keys in _DIALOG_KEYS:
		saved = state.get(section_name)
		if not hasattr(saved, "get"):
			continue
		for key in keys:
			stored = saved.get(key)
			if not hasattr(stored, "get") or "set" not in stored:
				continue
			try:
				restore_nvda_setting((section_name,), key, stored)
			except Exception:
				log.debug("ClassicSpeech: could not restore %s/%s", section_name, key, exc_info=True)
