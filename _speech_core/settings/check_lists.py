"""NVDA-style check lists.

NVDA presents a setting that is really several independent choices as a labeled
list of checkboxes rather than a combo box with one entry per combination: the
Document Formatting panel does this for "Spelling or grammar errors", where the
stored value is a bitwise combination of Speech, Sound and Braille.

The control is ``gui.nvdaControls.CustomCheckListBox``, NVDA's accessibility
enhanced check list, which reports the checked state as the user arrows through
it. ClassicSpeech uses the same control everywhere it offers that kind of
setting, so the experience matches NVDA's own.
"""
from __future__ import annotations

import wx

try:
	from gui import nvdaControls
except Exception:  # pragma: no cover - only when NVDA's gui package is absent
	nvdaControls = None


def check_list_class():
	"""Return NVDA's accessible check list, or plain wx outside NVDA."""
	return nvdaControls.CustomCheckListBox if nvdaControls is not None else wx.CheckListBox


def make_check_list(parent, name, choices):
	"""Create a named check list with ``choices`` as its rows."""
	control = check_list_class()(parent, choices=list(choices))
	control.SetName(name)
	return control


def checked_indices(control) -> list:
	"""Return the checked row numbers of a check list."""
	if hasattr(control, "GetCheckedItems"):
		checked = control.GetCheckedItems()
	elif hasattr(control, "CheckedItems"):
		checked = control.CheckedItems
	else:
		checked = []
	out = []
	for index in checked or []:
		try:
			out.append(int(index))
		except Exception:
			continue
	return out


def set_checked_indices(control, indices) -> None:
	"""Check exactly ``indices`` and select the first row, as NVDA does."""
	indices = [int(index) for index in indices or []]
	if hasattr(control, "SetCheckedItems"):
		control.SetCheckedItems(indices)
	elif hasattr(control, "CheckedItems"):
		control.CheckedItems = indices
	elif hasattr(control, "Check"):
		for index in indices:
			control.Check(index, True)
	if hasattr(control, "Select"):
		control.Select(0)
