"""Marker commands that carry Speech and Sound Scheme information through NVDA.

The tagging wrappers insert these markers while NVDA builds speech for output.
ClassicSpeech's speech filter converts them into sounds and voice changes, or
strips them, before any other code sees the final sequence.

Markers subclass NVDA's ``BaseCallbackCommand`` so NVDA's sequence validators
accept them. If one ever reached NVDA's speech manager, it would become an
index whose callback does nothing.
"""
from __future__ import annotations

try:
	from speech.commands import BaseCallbackCommand as _MarkerBase
except Exception:  # Outside NVDA (test harnesses).
	_MarkerBase = object


class SchemeMarker(_MarkerBase):
	"""Base class for all ClassicSpeech scheme markers."""

	def run(self):
		# Deliberately empty: markers are converted by the speech filter.
		return None

	def __repr__(self):
		fields = ", ".join(f"{name}={value!r}" for name, value in sorted(vars(self).items()))
		return f"{type(self).__name__}({fields})"


class LabelMarker(SchemeMarker):
	"""The next string is NVDA's announcement for ``items`` (most specific first)."""

	def __init__(self, items):
		self.items = tuple(items)


class ObjectMarker(SchemeMarker):
	"""The following speech describes one object; ``items`` apply to all of it."""

	def __init__(self, items):
		self.items = tuple(items)


class FormatMarker(SchemeMarker):
	"""Formatting items whose voice applies to the following document text."""

	def __init__(self, items):
		self.items = tuple(items)


class ElementStartMarker(SchemeMarker):
	"""Entering a document or web element; ``items`` apply to its text."""

	def __init__(self, key, items):
		self.key = key
		self.items = tuple(items)


class ElementEndMarker(SchemeMarker):
	"""Leaving the element that started with the same ``key``."""

	def __init__(self, key):
		self.key = key


class TextStartMarker(SchemeMarker):
	"""Start of one text speech sequence (caret, review, say all, browse mode).

	``elements`` holds ``(key, items)`` pairs for elements that already contain
	the text, so their voice continues on the next line.
	"""

	def __init__(self, elements=()):
		self.elements = tuple(elements)


def is_marker(item) -> bool:
	return isinstance(item, SchemeMarker)


def has_markers(sequence) -> bool:
	try:
		return any(isinstance(item, SchemeMarker) for item in sequence)
	except TypeError:
		return False


def strip_markers(sequence) -> list:
	return [item for item in sequence if not isinstance(item, SchemeMarker)]
