# -*- coding: UTF-8 -*-
from __future__ import annotations

from typing import Optional
import re

import controlTypes
import logHandler

from . import focus_ancestry

log = logHandler.log

_cached_dialog_key = None
_cached_default_name = ""


def clean_default_button_label(label: str) -> str:
	"""Return a raw button label safe for default-button query speech.

	ClassicSpeech may inject a speakable ``default`` state token into focus
	speech.  Manual query paths must never feed that decorated speech back as
	the button name, otherwise Insert+E can say things like
	``Default button OK default``.
	"""
	text = str(label or "").replace("&", "").strip()
	# Be conservative: only remove a final standalone state/role suffix.
	text = re.sub(r"\s+default(?:\s+button)?\s*$", "", text, flags=re.IGNORECASE).strip()
	return text


def get_object_name(obj) -> str:
	try:
		name = getattr(obj, "name", None)
		if name:
			return clean_default_button_label(name)
	except Exception:
		pass
	return ""


def _find_dialog_in_lineage(lineage, start=0):
	for index in range(start, len(lineage)):
		try:
			if focus_ancestry.role_at(lineage, index) == controlTypes.Role.DIALOG:
				return lineage[index]
		except Exception:
			continue
	return None


def get_dialog_ancestor(obj):
	"""Return the nearest dialog containing ``obj`` (``obj`` included).

	For the focus object this reads NVDA's cached focus ancestors and
	remembers the answer until focus moves, instead of creating up to twenty
	parent objects for every speech sequence.
	"""
	if not obj:
		return None
	lineage = focus_ancestry.lineage_for(obj, 20)
	if not lineage:
		return None
	if focus_ancestry.is_focus(obj):
		# The focus itself may be a dialog; check it fresh, then reuse the
		# remembered ancestor answer.
		try:
			if getattr(obj, "role", None) == controlTypes.Role.DIALOG:
				return obj
		except Exception:
			pass
		return focus_ancestry.memoized_for_focus(
			"dialogAncestor",
			lambda: _find_dialog_in_lineage(lineage, start=1),
		)
	return _find_dialog_in_lineage(lineage)


def object_is_in_dialog(obj) -> bool:
	return get_dialog_ancestor(obj) is not None


def iter_dialog_children(container):
	if not container:
		return []
	try:
		children = getattr(container, "children", None)
		if children:
			return list(children)
	except Exception:
		pass
	return []


def _default_button_scan_skips(obj) -> bool:
	"""Return True for containers that never hold a dialog's default button.

	File dialogs expose Explorer's item list, navigation tree and preview
	document inside the dialog. Enumerating those children is slow and can
	touch hundreds of cross-process objects, so the default-button scan does
	not descend into them.
	"""
	try:
		role = getattr(obj, "role", None)
		return role in _DEFAULT_BUTTON_SCAN_SKIP_ROLES
	except Exception:
		return False


def _default_button_scan_skip_roles():
	names = (
		"LIST", "LISTITEM", "TREEVIEW", "TREEVIEWITEM", "TABLE", "TABLEROW",
		"TABLECELL", "DOCUMENT", "EDITABLETEXT", "MENU", "MENUBAR", "POPUPMENU",
		"DATAGRID", "DATAITEM", "TERMINAL", "RICHEDIT",
	)
	roles = set()
	for name in names:
		role = getattr(controlTypes.Role, name, None)
		if role is not None:
			roles.add(role)
	return frozenset(roles)


_DEFAULT_BUTTON_SCAN_SKIP_ROLES = _default_button_scan_skip_roles()


def iter_dialog_descendants(container, max_depth=8, max_objects=150):
	"""Yield descendants of a dialog without trusting one flat child list.

	Some toolkits expose buttons under panels/property pages rather than as direct
	children of the dialog.  Keep this bounded because accessibility trees can be
	weird little hedge mazes.
	"""
	if not container:
		return
	queue = [(child, 1) for child in iter_dialog_children(container)]
	seen = set()
	count = 0
	while queue and count < max_objects:
		obj, depth = queue.pop(0)
		try:
			key = (getattr(obj, "windowHandle", None), getattr(obj, "IAccessibleChildID", None), id(obj))
		except Exception:
			key = id(obj)
		if key in seen:
			continue
		seen.add(key)
		count += 1
		yield obj
		if depth >= max_depth or _default_button_scan_skips(obj):
			continue
		try:
			children = iter_dialog_children(obj)
		except Exception:
			children = []
		for child in children:
			queue.append((child, depth + 1))


def is_button(obj) -> bool:
	try:
		return getattr(obj, "role", None) == controlTypes.Role.BUTTON
	except Exception:
		return False


def _has_explicit_default_state(obj) -> bool:
	try:
		states = getattr(obj, "states", set()) or set()
	except Exception:
		states = set()

	for state_name in ("DEFAULT", "DEFBUTTON", "DEFAULT_BUTTON"):
		state = getattr(controlTypes.State, state_name, None)
		if state is not None and state in states:
			return True

	try:
		iaStates = getattr(obj, "IAccessibleStates", 0)
		STATE_SYSTEM_DEFAULT = 0x100
		if iaStates & STATE_SYSTEM_DEFAULT:
			return True
	except Exception:
		pass

	return False


def is_same_object(a, b) -> bool:
	if not a or not b:
		return False

	def _sig(obj):
		try:
			return (
				getattr(obj, "windowHandle", None),
				getattr(obj, "IAccessibleChildID", None),
				getattr(obj, "role", None),
				get_object_name(obj),
				getattr(obj, "location", None),
			)
		except Exception:
			return None

	sig_a = _sig(a)
	sig_b = _sig(b)

	if sig_a is not None and sig_b is not None:
		return sig_a == sig_b

	return False



def _strip_label(label: str) -> str:
	return clean_default_button_label(label)


def get_dialog_key(obj):
	"""Return a stable-ish key for the current dialog.

	For wx dialogs, prefer the real wx top-level handle because it remains stable
	when NVDA focus moves between child controls.  Otherwise use the NVDA dialog
	ancestor identity.
	"""
	try:
		import wx
		focusWin = wx.Window.FindFocus()
		if focusWin:
			top = wx.GetTopLevelParent(focusWin)
			if isinstance(top, wx.Dialog):
				try:
					handle = int(top.GetHandle())
				except Exception:
					handle = id(top)
				return ("wx", handle, _strip_label(top.GetTitle()))
	except Exception:
		pass

	dialog = get_dialog_ancestor(obj)
	if not dialog:
		return None
	try:
		return (
			"nvda",
			getattr(dialog, "windowHandle", None),
			getattr(dialog, "IAccessibleChildID", None),
			getattr(dialog, "role", None),
			get_object_name(dialog),
		)
	except Exception:
		return ("nvda", id(dialog), get_object_name(dialog))


#: Seconds an empty default-button scan stays valid for one dialog. A dialog
#: without an exposed default button is otherwise rescanned on every keypress.
NEGATIVE_DEFAULT_SCAN_SECONDS = 10.0
_cached_scan_time = 0.0


def _monotonic():
	try:
		import time
		return time.monotonic()
	except Exception:
		return 0.0


def get_cached_default_button_name(obj) -> str:
	global _cached_dialog_key, _cached_default_name
	key = get_dialog_key(obj)
	if key is not None and key == _cached_dialog_key:
		return _cached_default_name or ""
	return ""


def _get_cached_default_button_lookup(obj):
	"""Return ``(found, name)`` from the dialog cache, including recent misses."""
	key = get_dialog_key(obj)
	if key is None:
		return True, ""
	if key != _cached_dialog_key:
		return False, ""
	if _cached_default_name:
		return True, _cached_default_name
	if _monotonic() - _cached_scan_time < NEGATIVE_DEFAULT_SCAN_SECONDS:
		return True, ""
	return False, ""


def cache_default_button_name(obj, name: str, *, allow_clear=False) -> str:
	global _cached_dialog_key, _cached_default_name, _cached_scan_time
	key = get_dialog_key(obj)
	if key is None:
		if allow_clear:
			_cached_dialog_key = None
			_cached_default_name = ""
		return ""
	clean = _strip_label(name)
	_cached_scan_time = _monotonic()
	# Do not let one failed/empty scan wipe a known-good default for the same dialog.
	if not clean and not allow_clear and key == _cached_dialog_key and _cached_default_name:
		return _cached_default_name
	_cached_dialog_key = key
	_cached_default_name = clean
	return _cached_default_name


def refresh_default_button_cache(obj, *, allow_clear=False) -> str:
	name = _scan_default_button_name(obj)
	return cache_default_button_name(obj, name, allow_clear=allow_clear)


def get_wx_default_button_name() -> str:
	"""Return the real wx default button label for NVDA-owned dialogs.

	This catches ClassicSpeech/NVDA settings dialogs where Enter still activates
	the default button but accessibility stops exposing an explicit default state
	after a child modal closes.
	"""
	try:
		import wx
		focusWin = wx.Window.FindFocus()
		if not focusWin:
			return ""
		top = wx.GetTopLevelParent(focusWin)
		if not isinstance(top, wx.Dialog):
			return ""
		defaultItem = top.GetDefaultItem()
		if not defaultItem:
			return ""
		if not defaultItem.IsEnabled():
			return ""
		try:
			label = defaultItem.GetLabelText()
		except Exception:
			label = defaultItem.GetLabel()
		return str(label or "").replace("&", "").strip()
	except Exception:
		try:
			log.debugWarning("ClassicSpeech: wx default button lookup failed", exc_info=True)
		except Exception:
			pass
		return ""


def _scan_default_button_name(obj) -> str:
	wx_name = get_wx_default_button_name()
	if wx_name:
		return wx_name

	button = find_default_button(obj)
	if button is None:
		return ""
	return get_object_name(button)


def get_default_button_name(obj, *, use_negative_cache=True) -> str:
	# Prefer the dialog cache so focus speech does not reclassify every focused
	# button as default when a toolkit exposes bogus DEFAULT state on all buttons.
	if use_negative_cache:
		found, cached = _get_cached_default_button_lookup(obj)
		if found:
			return cached
	else:
		cached = get_cached_default_button_name(obj)
		if cached:
			return cached
	return refresh_default_button_cache(obj)


def focused_button_default_status(obj):
	"""Return (isButton, isDefault, defaultName) for the focused object.

	Focused-button classification is intentionally cache/name based.  Some
	toolkits/drivers expose DEFAULT state on too many buttons; using that state
	directly on the focused object makes every button sound default.

	The dialog scan only runs when focus is actually on a button. Focus speech
	for list items, edit fields and other controls never pays for it.
	"""
	if not is_button(obj):
		return False, False, ""
	default_name = get_default_button_name(obj)
	name = get_object_name(obj)
	return True, bool(name and default_name and name.lower() == default_name.lower()), default_name


def find_default_button(obj) -> Optional[object]:
	dialog = get_dialog_ancestor(obj)
	if not dialog:
		return None

	candidates = []
	# First pass: direct children.  This preserves the old behavior for simple
	# dialogs and avoids diving into larger trees unless needed.
	for child in iter_dialog_children(dialog):
		if is_button(child) and _has_explicit_default_state(child):
			candidates.append(child)

	if candidates:
		return candidates[0]

	# Second pass: descendants.  wx and UIA often hide the real buttons under
	# panels or property pages.
	for child in iter_dialog_descendants(dialog):
		if is_button(child) and _has_explicit_default_state(child):
			candidates.append(child)

	if candidates:
		return candidates[0]

	return None


def format_default_button_announcement(obj) -> str:
	return "default button"
