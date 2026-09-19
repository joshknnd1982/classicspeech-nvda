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

One ``getTextInfoSpeech`` call can yield more than one sequence: NVDA speaks a
single character by yielding its fields first and the spelled character after,
and Say All flattens every sequence of a reading chunk into one list. Each
sequence therefore starts with the formatting and elements that were in force
when it began, so an item's voice and sound keep applying whichever reading
command produced the speech.

NVDA also only fetches the document formatting it was asked to announce, and by
default looks no further than the first character of the range it is speaking.
``format_needs`` turns the configured items into the settings NVDA needs to
fetch them; NVDA's own announcement builders are given the user's real settings
back, so what NVDA says never changes.
"""
from __future__ import annotations

import functools
import weakref
from contextvars import ContextVar

import logHandler

from . import format_needs
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
#: The ``_TextCallState`` of the ``getTextInfoSpeech`` call that is running.
_text_state = ContextVar("classicSpeechSchemeTextState", default=None)
#: True while NVDA builds control field (element) speech.
_in_control_field = ContextVar("classicSpeechSchemeControlField", default=False)

_WRAPPED_MARK = "_classicSpeechSchemeWrapper"

#: NVDA units that make ``getTextInfoSpeech`` ask for extra detail. For those it
#: does not repeat the elements that already contain the text, so the element
#: stack has to be carried over from the previous call for the same object.
_EXTRA_DETAIL_UNITS = ("character", "word")


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


def _marking_items(items_cfg):
	"""Items whose voice or sound applies to a run of text or a whole element."""
	marking = set()
	for item_id, settings in items_cfg.items():
		voice = settings.get("voice")
		if isinstance(voice, dict) and voice.get("enabled"):
			marking.add(item_id)
		elif settings.get("sound"):
			marking.add(item_id)
	return marking


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


def _replace_argument(args, kwargs, index, name, value):
	"""Return ``(args, kwargs)`` with one argument replaced, however it was passed."""
	if name in kwargs:
		kwargs = dict(kwargs)
		kwargs[name] = value
		return args, kwargs
	if len(args) > index:
		args = list(args)
		args[index] = value
		return tuple(args), kwargs
	kwargs = dict(kwargs)
	kwargs[name] = value
	return args, kwargs


class _TextCallState:
	"""What one ``getTextInfoSpeech`` call has marked so far."""

	__slots__ = (
		"items_cfg", "marking_items", "real_format_config", "enriched_format_config",
		"extra_detail", "stack", "removed", "relative", "format_range", "format_delivered",
	)

	def __init__(self, items_cfg, marking_items, real_format_config, enriched_format_config, extra_detail):
		self.items_cfg = items_cfg
		self.marking_items = marking_items
		self.real_format_config = real_format_config
		self.enriched_format_config = enriched_format_config
		self.extra_detail = extra_detail
		#: ``[key, items, presented]`` for every control field containing the text.
		self.stack = []
		#: Control fields NVDA reported leaving before it described this text.
		self.removed = 0
		#: ``(key, items)`` for elements opened inside the text and still open.
		self.relative = []
		#: The scheme items describing the text being spoken right now.
		self.format_range = ()
		#: True once a sequence carrying that formatting has been handed to NVDA.
		self.format_delivered = False

	def marking_config(self, format_config):
		"""The configuration that decides what a scheme may mark."""
		return self.enriched_format_config or format_config or self.real_format_config

	def element_markers(self):
		"""``(key, items)`` pairs for every element the next sequence starts inside."""
		elements = [(key, items) for key, items, presented in self.stack if presented and items]
		elements.extend(self.relative)
		return elements


class SchemeTagger:
	"""Installs and removes the speech-builder wrappers."""

	def __init__(self, is_active=None):
		self._is_active = is_active or (lambda: True)
		self._patches = []
		#: ``(weak reference to the object, stack)`` from the last text call.
		self._element_stack_cache = None

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
		self._element_stack_cache = None

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
	@staticmethod
	def _document_format_config():
		try:
			import config
			return config.conf["documentFormatting"]
		except Exception:
			return None

	def _new_text_state(self, args, kwargs, items_cfg):
		"""Build the call state and the arguments NVDA should run with."""
		unit = str(_argument(args, kwargs, 3, "unit", "") or "")
		extra_detail = unit in _EXTRA_DETAIL_UNITS
		base_config = _argument(args, kwargs, 2, "formatConfig") or self._document_format_config()
		enriched = None
		try:
			keys, detect = format_needs.requirements(items_cfg)
			enriched = format_needs.enrich(base_config, keys, detect)
		except Exception:
			log.debug("ClassicSpeech schemes: format requirements failed", exc_info=True)
			enriched = None
		real_config = None
		if enriched is not None:
			args, kwargs = _replace_argument(args, kwargs, 2, "formatConfig", enriched)
			# What NVDA would have built for itself, to hand back to its own
			# announcement builders. NVDA adds extraDetail to its copy the same
			# way, so they see exactly the configuration they would have seen.
			real_config = format_needs.as_dict(base_config)
			if real_config is not None and extra_detail:
				real_config["extraDetail"] = True
		state = _TextCallState(
			items_cfg,
			_marking_items(items_cfg),
			real_config,
			enriched,
			extra_detail,
		)
		return state, args, kwargs

	def _cached_element_stack(self, obj):
		cache = self._element_stack_cache
		if not cache or obj is None:
			return []
		reference, stack = cache
		try:
			cached_obj = reference()
		except Exception:
			return []
		if cached_obj is None or cached_obj is not obj:
			return []
		return [list(entry) for entry in stack]

	def _store_element_stack(self, obj, stack):
		if obj is None:
			self._element_stack_cache = None
			return
		try:
			self._element_stack_cache = (weakref.ref(obj), [tuple(entry) for entry in stack])
		except Exception:
			self._element_stack_cache = None

	def _resolve_element_stack(self, state, obj):
		"""The full element stack, including the part NVDA did not repeat.

		Reading by character or word asks NVDA for extra detail, and it then
		leaves out the elements the caret was already inside. Those elements
		still contain the text, so they come from the previous call for the same
		object, minus the ones NVDA reported leaving.
		"""
		if not state.extra_detail:
			return state.stack
		cached = self._cached_element_stack(obj)
		if not cached:
			return state.stack
		kept = cached[: max(0, len(cached) - state.removed)]
		return kept + state.stack

	def _wrap_get_text_info_speech(self, original):
		tagger = self

		@functools.wraps(original)
		def wrapped(*args, **kwargs):
			items_cfg = tagger._enabled_items()
			if not items_cfg:
				return (yield from original(*args, **kwargs))
			try:
				state, args, kwargs = tagger._new_text_state(args, kwargs, items_cfg)
			except Exception:
				log.debug("ClassicSpeech schemes: text call state failed", exc_info=True)
				return (yield from original(*args, **kwargs))
			try:
				obj = getattr(_argument(args, kwargs, 0, "info", None), "obj", None)
			except Exception:
				obj = None
			generator = original(*args, **kwargs)
			while True:
				token = _text_state.set(state)
				try:
					try:
						sequence = next(generator)
					except StopIteration as stop:
						return stop.value
				finally:
					_text_state.reset(token)
				try:
					state.stack = tagger._resolve_element_stack(state, obj)
					state.removed = 0
					tagger._store_element_stack(obj, state.stack)
					if isinstance(sequence, list):
						tagger._start_sequence(sequence, state)
				except Exception:
					log.debug("ClassicSpeech schemes: text start marker failed", exc_info=True)
				yield sequence

		return wrapped

	@staticmethod
	def _start_sequence(sequence, state):
		"""Give ``sequence`` the formatting and elements it starts inside.

		NVDA can split one reading command into several sequences: the fields of
		a character and then the spelled character, or a Say All chunk that is
		flattened into one list. It also drops a sequence that holds nothing but
		fields, which is exactly what happens when a single character is spelled.
		Every sequence therefore repeats the state it starts in, so the second
		and later ones are marked exactly like the first.
		"""
		carries_format = any(isinstance(entry, FormatMarker) for entry in sequence)
		prefix = [TextStartMarker(state.element_markers())]
		if not carries_format and state.format_range:
			# The item's sound belongs to the first sequence that reaches the
			# listener, not to every repeat of the same formatting.
			prefix.append(FormatMarker(state.format_range, restate=state.format_delivered))
			carries_format = True
		sequence[0:0] = prefix
		if carries_format:
			state.format_delivered = True

	def _wrap_get_control_field_speech(self, original):
		tagger = self

		@functools.wraps(original)
		def wrapped(*args, **kwargs):
			state = _text_state.get()
			if state is None:
				return original(*args, **kwargs)
			marking_config = state.marking_config(_argument(args, kwargs, 3, "formatConfig"))
			if state.real_format_config is not None:
				# NVDA decides what to say from the user's own settings, never
				# from the settings a scheme needed turned on to fetch fields.
				args, kwargs = _replace_argument(args, kwargs, 3, "formatConfig", state.real_format_config)
			items_cfg = state.items_cfg
			if not items_cfg or not _interested(items_cfg, _CONTROL_FIELD_PREFIXES):
				return tagger._track_control_field(original(*args, **kwargs), args, kwargs, state, marking_config)
			token = _in_control_field.set(True)
			try:
				result = original(*args, **kwargs)
			finally:
				_in_control_field.reset(token)
			try:
				return tagger._tag_control_field(result, args, kwargs, state, marking_config)
			except Exception:
				log.debug("ClassicSpeech schemes: control field tagging failed", exc_info=True)
				return result

		return wrapped

	@staticmethod
	def _field_entry(attrs, state, marking_config, ancestors, extra_detail, reason):
		items = tuple(
			item_id
			for item_id in schemeLabels.element_range_items(attrs)
			if item_id in state.marking_items
		)
		presented = SchemeTagger._is_presented(attrs, ancestors, marking_config, reason, extra_detail)
		return [id(attrs), items, presented]

	def _track_control_field(self, result, args, kwargs, state, marking_config):
		"""Keep the element stack accurate even when nothing about it is marked."""
		try:
			field_type = str(_argument(args, kwargs, 2, "fieldType", "") or "")
			if field_type == "end_removedFromControlFieldStack":
				state.removed += 1
			elif field_type in ("start_inControlFieldStack", "start_addedToControlFieldStack"):
				attrs = _argument(args, kwargs, 0, "attrs")
				if attrs is not None:
					state.stack.append(self._field_entry(
						attrs,
						state,
						marking_config,
						_argument(args, kwargs, 1, "ancestorAttrs", []),
						_argument(args, kwargs, 4, "extraDetail", False),
						_argument(args, kwargs, 5, "reason"),
					))
		except Exception:
			log.debug("ClassicSpeech schemes: element stack tracking failed", exc_info=True)
		return result

	def _tag_control_field(self, result, args, kwargs, state, marking_config):
		attrs = _argument(args, kwargs, 0, "attrs")
		if attrs is None:
			return result
		items_cfg = state.items_cfg
		ancestors = _argument(args, kwargs, 1, "ancestorAttrs", [])
		field_type = str(_argument(args, kwargs, 2, "fieldType", "") or "")
		extra_detail = _argument(args, kwargs, 4, "extraDetail", False)
		reason = _argument(args, kwargs, 5, "reason")
		output = list(result or ())
		if output:
			table = schemeLabels.control_field_label_table(attrs, reason)
			output = _insert_label_markers(output, table, items_cfg)
		key, range_items, presented = self._field_entry(attrs, state, marking_config, ancestors, extra_detail, reason)
		if field_type == "end_removedFromControlFieldStack":
			state.removed += 1
			return output
		if field_type in ("start_inControlFieldStack", "start_addedToControlFieldStack"):
			# These elements contain all text of this speech sequence. The text
			# speech wrapper marks them at the start of the sequence instead of
			# changing NVDA's field speech (which decides blank-line reporting).
			state.stack.append([key, range_items, presented])
			return output
		if not range_items:
			return output
		if field_type == "start_relative":
			if presented:
				output.insert(0, ElementStartMarker(key, range_items))
				state.relative.append((key, range_items))
		elif field_type == "end_relative":
			output.insert(0, ElementEndMarker(key))
			for index in range(len(state.relative) - 1, -1, -1):
				if state.relative[index][0] == key:
					del state.relative[index]
					break
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
			state = _text_state.get()
			if state is None:
				return original(*args, **kwargs)
			if state.real_format_config is not None:
				args, kwargs = _replace_argument(args, kwargs, 2, "formatConfig", state.real_format_config)
			items_cfg = state.items_cfg
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
				return tagger._tag_format_field(result, attrs, old, args, kwargs, state)
			except Exception:
				log.debug("ClassicSpeech schemes: format field tagging failed", exc_info=True)
				return result

		return wrapped

	def _tag_format_field(self, result, attrs, old, args, kwargs, state):
		if attrs is None:
			return result
		items_cfg = state.items_cfg
		extra_detail = _argument(args, kwargs, 5, "extraDetail", False)
		output = list(result or ())
		if output:
			table = schemeLabels.format_field_label_table(attrs, old, extra_detail=extra_detail)
			output = _insert_label_markers(output, table, items_cfg)
		if not state.marking_items:
			return output
		new_range = tuple(
			item_id
			for item_id in schemeLabels.format_range_items(attrs)
			if item_id in state.marking_items
		)
		# The scheme follows the formatting of the text itself, not whether NVDA
		# announced a change, so a user who turned an announcement off still gets
		# the voice and sound they configured for that formatting.
		if new_range != state.format_range:
			state.format_range = new_range
			output.append(FormatMarker(new_range))
		return output

	def _wrap_get_indentation_speech(self, original):
		tagger = self

		@functools.wraps(original)
		def wrapped(*args, **kwargs):
			state = _text_state.get()
			if state is None:
				return original(*args, **kwargs)
			if state.real_format_config is not None:
				args, kwargs = _replace_argument(args, kwargs, 1, "formatConfig", state.real_format_config)
			result = original(*args, **kwargs)
			if not result or "fmt.lineIndentation" not in state.items_cfg:
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
