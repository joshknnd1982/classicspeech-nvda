"""File choosers for exporting and importing ClassicSpeech files.

Exports start in the Documents folder and imports in Downloads, where shared
files usually arrive, instead of NVDA's program folder.
"""
from __future__ import annotations

import wx


def _standard_folder(downloads=False) -> str:
	try:
		paths = wx.StandardPaths.Get()
		if downloads:
			return paths.GetUserDir(wx.StandardPaths.Dir_Downloads)
		return paths.GetDocumentsDir()
	except Exception:
		return ""


def _wildcard(description, extension) -> str:
	return f"{description} (*{extension})|*{extension}"


def choose_export_path(parent, title, description, extension, default_name) -> str:
	"""Ask where to save a file; return its path with ``extension``, or "" when cancelled."""
	with wx.FileDialog(
		parent,
		title,
		defaultDir=_standard_folder(),
		defaultFile=f"{default_name}{extension}",
		wildcard=_wildcard(description, extension),
		style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
	) as dialog:
		if dialog.ShowModal() != wx.ID_OK:
			return ""
		path = dialog.GetPath()
	if not path:
		return ""
	if not path.lower().endswith(extension.lower()):
		path += extension
	return path


def choose_import_path(parent, title, description, extension) -> str:
	"""Ask for a file to import; return its path, or "" when cancelled."""
	with wx.FileDialog(
		parent,
		title,
		defaultDir=_standard_folder(downloads=True) or _standard_folder(),
		wildcard=_wildcard(description, extension),
		style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
	) as dialog:
		if dialog.ShowModal() != wx.ID_OK:
			return ""
		return dialog.GetPath()
