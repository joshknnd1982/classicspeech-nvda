"""Wrap NVDA's speech builders so scheme items are marked in speech output.

Markers are added only while speech is being generated *for output*:

* text speech: inside ``getTextInfoSpeech`` (caret, review cursor, say all,
  browse mode, quick navigation, mouse text);
* object speech: inside ``speakObject`` / ``speakObjectProperties`` (focus,
  object navigation, mouse objects, state changes).

Callers that build text for other purposes (NVDA+F formatting reports, the
spelled and copied result of NVDA+Tab pressed twice) run outside those scopes
and receive NVDA's output unchanged. Every wrapper returns NVDA's original
result whenever schemes are disabled or nothing relevant is configured.
"""
from __future__ import annotations

import functools
from contextvars import ContextVar

import logHandler

from . import labels as schemeLabels
from . import store
from .markers import (
	ElementEndMarker,
	ElementStartMarker,
	FormatMarker,
	LabelMarker,
	ObjectMarker,
	TextStartMarker,
)

log = logHandler.log

#: True while NVDA speaks an object (speakObject / speakObjectProperties).
_object_output = ContextVar("classicSpeechSchemeObjectOutput", default=False)
#: The object whose properties NVDA is currently describing.
_object_context = ContextVar("classicSpeechSchemeObject", default=None)
#: A list collecting container elements while getTextInfoSpeech runs.
_text_collector = ContextVar("classicSpeechSchemeTextCollector", default=None)
#: True while NVDA builds control field (element) speech.
_in_control_field = ContextVar("classicSpeechSchemeControlField", default=False)

_WRAPPED_MARK = "_classicSpeechSchemeWrapper"


def _configured_items():
	try:
		return store.active_items()
	except Exception:
		return {}


#: Item id prefixes that can match each kind of NVDA speech. Label tables are
#: only built when a configured item could appear in that speech.
_PROPERTY_PREFIXES = ("role.", "state.", "object.", "class.", "fmt.tableCellCoords", "fmt.tableHeaders")
_CONTROL_FIELD_PREFIXES = ("role.", "state.", "landmark.", "object.", "fmt.tableCellCoords", "fmt.tableHeaders")
_FORMAT_FIELD_PREFIXES = ("fmt.", "role.HEADING", "role.LINK", "role.TABLE", "state.COLLAPSED")


def _interested(items_cfg, prefixes) -> bool:
	return any(item_id.startswith(prefixes) for item_id in items_cfg)


def _reason_name(reason) -> str:
	return str(getattr(reason, "name", "") or "")


def _voice_items(items_cfg):
	return {
		item_id
		for item_id, settings in items_cfg.items()
		if isinstance(settings.get("voice"), dict) and settings["voice"].get("enabled")
	}


def _insert_label_markers(sequence, table, items_cfg, start=0):
	"""Return ``sequence`` with a LabelMarker before each configured label string."""
	if not table:
		return sequence
	result = []
	for index, entry in enumerate(sequence):
		if index >= start and isinstance(entry, str):
			items = table.get(entry)
			if items:
				configured = [item_id for item_id in items if item_id in items_cfg]
				if configured:
					result.append(LabelMarker(configured))
		result.append(entry)
	return result


def _argument(args, kwargs, index, name, default=None):
	if name in kwargs:
		return kwargs[name]
	if len(args) > index:
		return args[index]
	return default


class SchemeTagger:
	"""Installs and removes the speech-builder wrappers."""

	def __init__(self, is_active=None):
		self._is_active = is_active or (lambda: True)
		self._patches = []

	# -- helpers -----------------------------------------------------------
	def _enabled_items(self):
		try:
			if not self._is_active():
				return {}
		except Exception:
			return {}
		return _configured_items()

	def _patch(self, owner, attribute, wrapper_factory, originals):
		original = getattr(owner, attribute, None)
		if original is None or getattr(original, _WRAPPED_MARK, False):
			return None
		key = id(original)
		wrapper = originals.get(key)
		if wrapper is None:
			wrapper = wrapper_factory(original)
			setattr(wrapper, _WRAPPED_MARK, True)
			originals[key] = wrapper
		setattr(owner, attribute, wrapper)
		self._patches.append((owner, attribute, original, wrapper))
		return wrapper

	def install(self):
		if self._patches:
			return
		try:
			import speech
			from speech import speech as speechModule
		except Exception:
			log.debug("ClassicSpeech schemes: speech module unavailable", exc_info=True)
			return
		originals = {}
		targets = (
			("getPropertiesSpeech", self._wrap_get_properties_speech),
			("getObjectPropertiesSpeech", self._wrap_get_object_properties_speech),
			("getControlFieldSpeech", self._wrap_get_control_field_speech),
			("getFormatFieldSpeech", self._wrap_get_format_field_speech),
			("getIndentationSpeech", self._wrap_get_indentation_speech),
			("getTextInfoSpeech", self._wrap_get_text_info_speech),
			("speakObject", self._wrap_object_output),
			("speakObjectProperties", self._wrap_object_output),
		)
		for attribute, factory in targets:
			for owner in (speechModule, speech):
				try:
					self._patch(owner, attribute, factory, originals)
				except Exception:
					log.debug("ClassicSpeech schemes: could not wrap %s", attribute, exc_info=True)
		# Say all keeps its own references to these functions.
		try:
			from speech import sayAll
			handler = getattr(sayAll, "SayAllHandler", None)
			if handler is not None:
				for attribute, factory in (
					("_getTextInfoSpeech", self._wrap_get_text_info_speech),
					("_speakObject", self._wrap_object_output),
				):
					self._patch(handler, attribute, factory, originals)
		except Exception:
			log.debug("ClassicSpeech schemes: say all references unavailable", exc_info=True)

	def uninstall(self):
		for owner, attribute, original, wrapper in reversed(self._patches):
			try:
				if getattr(owner, attribute, None) is wrapper:
					setattr(owner, attribute, original)
			except Exception:
				log.debug("ClassicSpeech schemes: could not restore %s", attribute, exc_info=True)
		self._patches = []

	@property
	def installed(self):
		return bool(self._patches)

	# -- object speech -------------------------------------------------------
	def _wrap_object_output(self, original):
		@functools.wraps(original)
		def wrapped(*args, **kwargs):
			token = _object_output.set(True)
			try:
				return original(*args, **kwargs)
			finally:
				_object_output.reset(token)

		return wrapped

	def _wrap_get_object_properties_speech(self, original):
		tagger = self

		@functools.wraps(original)
		def wrapped(obj, *args, **kwargs):
			if not _object_output.get():
				return original(obj, *args, **kwargs)
			items_cfg = tagger._enabled_items()
			if not items_cfg or not _interested(items_cfg, _PROPERTY_PREFIXES):
				return original(obj, *args, **kwargs)
			token = _object_context.set(obj)
			try:
				result = original(obj, *args, **kwargs)
			finally:
				_object_context.reset(token)
			# A state or name change of the same object reports only what changed;
			# its state labels are marked, but the object's own sound is not replayed.
			if _reason_name(_argument(args, kwargs, 0, "reason")) == "CHANGE":
				return result
			try:
				return tagger._add_object_marker(result, obj, items_cfg)
			except Exception:
				log.debug("ClassicSpeech schemes: object marker failed", exc_info=True)
				return result

		return wrapped

	def _add_object_marker(self, result, obj, items_cfg):
		if not result:
			return result
		items = []
		if any(item_id.startswith("class.") for item_id in items_cfg):
			try:
				class_name = str(getattr(obj, "windowClassName", "") or "")
			except Exception:
				class_name = ""
			if class_name and f"class.{class_name}" in items_cfg:
				items.append(f"class.{class_name}")
		try:
			role = getattr(obj, "role", None)
		except Exception:
			role = None
		if role is not None:
			name = None
			if getattr(role, "name", "") == "GRAPHIC":
				try:
					name = getattr(obj, "name", None)
				except Exception:
					name = None
			for item_id in schemeLabels.role_items(role, name=name):
				if item_id in items_cfg and item_id not in items:
					items.append(item_id)
		if not items:
			return result
		result = list(result)
		result.insert(0, ObjectMarker(items))
		return result

	def _wrap_get_properties_speech(self, original):
		tagger = self

		@functools.wraps(original)
		def wrapped(*args, **kwargs):
			result = original(*args, **kwargs)
			if _object_context.get() is None or _in_control_field.get() or not result:
				return result
			items_cfg = tagger._enabled_items()
			if not items_cfg:
				return result
			try:
				reason = _argument(args, kwargs, 0, "reason")
				if reason is None:
					# getPropertiesSpeech defaults to OutputReason.QUERY.
					try:
						import controlTypes
						reason = controlTypes.OutputReason.QUERY
					except Exception:
						reason = None
				table = schemeLabels.properties_label_table(kwargs, reason)
				name = kwargs.get("name")
				start = 1 if name and result and result[0] == name else 0
				return _insert_label_markers(result, table, items_cfg, start=start)
			except Exception:
				log.debug("ClassicSpeech schemes: property labels failed", exc_info=True)
				return result

		return wrapped

	# -- text speech -------------------------------------------------------
	def _wrap_get_text_info_speech(self, original):
		tagger = self

		@functools.wraps(original)
		def wrapped(*args, **kwargs):
			if not tagger._enabled_items():
				return (yield from original(*args, **kwargs))
			collector = []
			generator = original(*args, **kwargs)
			while True:
				token = _text_collector.set(collector)
				try:
					try:
						sequence = next(generator)
					except StopIteration as stop:
						return stop.value
				finally:
					_text_collector.reset(token)
				try:
					if isinstance(sequence, list):
						sequence.insert(0, TextStartMarker(collector))
				except Exception:
					log.debug("ClassicSpeech schemes: text start marker failed", exc_info=True)
				collector = []
				yield sequence

		return wrapped

	def _wrap_get_control_field_speech(self, original):
		tagger = self

		@functools.wraps(original)
		def wrapped(*args, **kwargs):
			collector = _text_collector.get()
			if collector is None:
				return original(*args, **kwargs)
			items_cfg = tagger._enabled_items()
			if not items_cfg or not _interested(items_cfg, _CONTROL_FIELD_PREFIXES):
				return original(*args, **kwargs)
			token = _in_control_field.set(True)
			try:
				result = original(*args, **kwargs)
			finally:
				_in_control_field.reset(token)
			try:
				return tagger._tag_control_field(result, args, kwargs, items_cfg, collector)
			except Exception:
				log.debug("ClassicSpeech schemes: control field tagging failed", exc_info=True)
				return result

		return wrapped

	def _tag_control_field(self, result, args, kwargs, items_cfg, collector):
		attrs = _argument(args, kwargs, 0, "attrs")
		if attrs is None:
			return result
		ancestors = _argument(args, kwargs, 1, "ancestorAttrs", [])
		field_type = str(_argument(args, kwargs, 2, "fieldType", "") or "")
		format_config = _argument(args, kwargs, 3, "formatConfig")
		extra_detail = _argument(args, kwargs, 4, "extraDetail", False)
		reason = _argument(args, kwargs, 5, "reason")
		output = list(result or ())
		if output:
			table = schemeLabels.control_field_label_table(attrs, reason)
			output = _insert_label_markers(output, table, items_cfg)
		voice_items = _voice_items(items_cfg)
		range_items = [item_id for item_id in schemeLabels.element_range_items(attrs) if item_id in voice_items]
		if not range_items:
			return output
		key = id(attrs)
		if field_type in ("start_inControlFieldStack", "start_addedToControlFieldStack"):
			# These elements contain all text of this speech sequence. The text
			# speech wrapper marks them at the start of the sequence instead of
			# changing NVDA's field speech (which decides blank-line reporting).
			if self._is_presented(attrs, ancestors, format_config, reason, extra_detail):
				collector.append((key, tuple(range_items)))
		elif field_type == "start_relative":
			if self._is_presented(attrs, ancestors, format_config, reason, extra_detail):
				output.insert(0, ElementStartMarker(key, range_items))
		elif field_type == "end_relative":
			output.insert(0, ElementEndMarker(key))
		return output

	@staticmethod
	def _is_presented(attrs, ancestors, format_config, reason, extra_detail):
		try:
			if not format_config:
				import config
				format_config = config.conf["documentFormatting"]
			category = attrs.getPresentationCategory(ancestors or [], format_config, reason=reason, extraDetail=extra_detail)
		except Exception:
			return True
		layout = getattr(attrs, "PRESCAT_LAYOUT", "layout")
		return bool(category) and category != layout

	def _wrap_get_format_field_speech(self, original):
		tagger = self

		@functools.wraps(original)
		def wrapped(*args, **kwargs):
			if _text_collector.get() is None:
				return original(*args, **kwargs)
			items_cfg = tagger._enabled_items()
			if not items_cfg or not _interested(items_cfg, _FORMAT_FIELD_PREFIXES):
				return original(*args, **kwargs)
			attrs = _argument(args, kwargs, 0, "attrs")
			cache = _argument(args, kwargs, 1, "attrsCache")
			try:
				old = dict(cache) if cache is not None else {}
			except Exception:
				old = {}
			result = original(*args, **kwargs)
			try:
				return tagger._tag_format_field(result, attrs, old, args, kwargs, items_cfg)
			except Exception:
				log.debug("ClassicSpeech schemes: format field tagging failed", exc_info=True)
				return result

		return wrapped

	def _tag_format_field(self, result, attrs, old, args, kwargs, items_cfg):
		if attrs is None:
			return result
		extra_detail = _argument(args, kwargs, 5, "extraDetail", False)
		initial = bool(_argument(args, kwargs, 6, "initialFormat", False))
		output = list(result or ())
		if output:
			table = schemeLabels.format_field_label_table(attrs, old, extra_detail=extra_detail)
			output = _insert_label_markers(output, table, items_cfg)
		voice_items = _voice_items(items_cfg)
		if not voice_items:
			return output
		new_range = [item_id for item_id in schemeLabels.format_range_items(attrs) if item_id in voice_items]
		old_range = [item_id for item_id in schemeLabels.format_range_items(old) if item_id in voice_items]
		if new_range != old_range or (initial and new_range):
			output.append(FormatMarker(new_range))
		return output

	def _wrap_get_indentation_speech(self, original):
		tagger = self

		@functools.wraps(original)
		def wrapped(*args, **kwargs):
			result = original(*args, **kwargs)
			if _text_collector.get() is None or not result:
				return result
			items_cfg = tagger._enabled_items()
			if "fmt.lineIndentation" not in items_cfg:
				return result
			try:
				output = []
				for entry in result:
					if isinstance(entry, str) and entry.strip():
						output.append(LabelMarker(["fmt.lineIndentation"]))
					output.append(entry)
				return output
			except Exception:
				return result

		return wrapped
