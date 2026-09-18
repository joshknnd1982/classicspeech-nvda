"""Cached focus ancestry for ClassicSpeech's per-sequence context checks.

ClassicSpeech inspects the focus ancestry several times for every speech
sequence: menu context, dialog detection, position containers and literal
review guards. Walking ``obj.parent`` creates a new NVDAObject for each level,
which is a slow cross-process call in UIA (Windows Explorer, file dialogs) and
IAccessible2 (Chromium) applications.

NVDA already keeps the complete focus ancestry in ``api.getFocusAncestors()``
whenever focus changes. This module reuses that list and remembers ancestor
roles until the focus object changes, so repeated checks cost almost nothing.
Objects other than the focus fall back to a bounded ``parent`` walk.
"""
from __future__ import annotations

import api

_MAX_LINEAGE = 40


class _LineageCache:
	__slots__ = ("focus", "ancestors", "ancestorCount", "lineage", "roles", "memo", "objectMemo")

	def __init__(self):
		self.focus = None
		self.ancestors = None
		self.ancestorCount = -1
		self.lineage = ()
		self.roles = {}
		self.memo = {}
		#: id(ancestor) -> (ancestor, {key: value}) for values tied to one ancestor.
		self.objectMemo = {}


_cache = _LineageCache()
_MISSING = object()


def reset_cache() -> None:
	"""Forget the cached lineage; the next lookup rebuilds it."""
	global _cache
	_cache = _LineageCache()


def _get_focus():
	try:
		return api.getFocusObject()
	except Exception:
		return None


def _get_focus_ancestors():
	getter = getattr(api, "getFocusAncestors", None)
	if not callable(getter):
		return None
	try:
		ancestors = getter()
	except Exception:
		return None
	if ancestors is None:
		return None
	try:
		len(ancestors)
	except Exception:
		return None
	return ancestors


def _safe_parent(obj):
	try:
		return getattr(obj, "parent", None)
	except Exception:
		return None


def _walk_parents(obj, max_depth: int):
	lineage = []
	current = obj
	while current is not None and len(lineage) < max_depth:
		lineage.append(current)
		current = _safe_parent(current)
	return tuple(lineage)


def focus_lineage():
	"""Return ``(focus, parent, grandparent, ...)`` for the current focus.

	Uses NVDA's cached focus ancestors when available. The result is cached
	until the focus object or NVDA's ancestor list changes.
	"""
	focus = _get_focus()
	if focus is None:
		if _cache.focus is not None:
			reset_cache()
		return ()
	ancestors = _get_focus_ancestors()
	count = len(ancestors) if ancestors is not None else -1
	if (
		_cache.focus is focus
		and _cache.ancestors is ancestors
		and _cache.ancestorCount == count
		and _cache.lineage
	):
		return _cache.lineage
	# NVDA keeps the same ancestor objects while focus moves inside them (for
	# example between items of one list), so their roles and remembered
	# per-object values carry over to the new lineage.
	previousRoles = {id(entry[0]): entry for entry in _cache.roles.values()}
	previousObjectMemo = _cache.objectMemo
	reset_cache()
	if ancestors is not None:
		nearestFirst = [obj for obj in reversed(list(ancestors)) if obj is not None]
		lineage = (focus,) + tuple(nearestFirst[: _MAX_LINEAGE - 1])
	else:
		lineage = _walk_parents(focus, _MAX_LINEAGE)
	_cache.focus = focus
	_cache.ancestors = ancestors
	_cache.ancestorCount = count
	_cache.lineage = lineage
	for index in range(1, len(lineage)):
		obj = lineage[index]
		entry = previousRoles.get(id(obj))
		if entry is not None and entry[0] is obj:
			_cache.roles[index] = entry
		memo = previousObjectMemo.get(id(obj))
		if memo is not None and memo[0] is obj:
			_cache.objectMemo[id(obj)] = memo
	return lineage


def is_focus(obj) -> bool:
	"""True when ``obj`` is the current focus object itself (identity only).

	NVDAObject equality can call into the application, so it is never used here.
	"""
	lineage = focus_lineage()
	return bool(lineage) and lineage[0] is obj


def lineage_for(obj, max_depth: int):
	"""Return up to ``max_depth`` objects starting with ``obj`` and its ancestors."""
	if obj is None or max_depth <= 0:
		return ()
	lineage = focus_lineage()
	if lineage and lineage[0] is obj:
		return lineage[:max_depth]
	return _walk_parents(obj, max_depth)


def _role_of(obj):
	try:
		return getattr(obj, "role", None)
	except Exception:
		return None


def role_at(lineage, index: int):
	"""Return the role of ``lineage[index]``.

	Ancestor roles of the current focus are remembered until focus changes;
	the focus object itself is always read fresh because its role can change
	while it stays focused.
	"""
	obj = lineage[index]
	if index == 0 or _cache.focus is None or not _cache.lineage or lineage[0] is not _cache.focus:
		return _role_of(obj)
	cached = _cache.roles.get(index, _MISSING)
	if cached is not _MISSING and cached[0] is obj:
		return cached[1]
	role = _role_of(obj)
	_cache.roles[index] = (obj, role)
	return role


def memoized_for_ancestor(obj, key, compute):
	"""Remember a value for one ancestor of the focus across focus changes.

	Only objects in the current focus lineage (other than the focus itself)
	are remembered; anything else is computed directly.
	"""
	lineage = focus_lineage()
	if obj is None or not any(entry is obj for entry in lineage[1:]):
		return compute()
	entry = _cache.objectMemo.get(id(obj))
	if entry is None or entry[0] is not obj:
		entry = (obj, {})
		_cache.objectMemo[id(obj)] = entry
	values = entry[1]
	value = values.get(key, _MISSING)
	if value is _MISSING:
		value = compute()
		values[key] = value
	return value


def memoized_for_focus(key, compute):
	"""Remember a value derived only from the current focus's ancestors."""
	lineage = focus_lineage()
	if not lineage:
		return compute()
	value = _cache.memo.get(key, _MISSING)
	if value is _MISSING:
		value = compute()
		_cache.memo[key] = value
	return value
