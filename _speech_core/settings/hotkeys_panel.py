from ..localization import _

import wx
import logHandler

from .accessibility import _set_panel_description
from .check_lists import checked_indices, make_check_list, set_checked_indices
from .hotkeys_config import (
	_get_hotkey_dialog_access_key_only,
	_get_hotkey_format,
	_get_hotkey_mode,
	_get_hotkey_types,
	_set_hotkey_dialog_access_key_only,
	_set_hotkey_format,
	_set_hotkey_mode,
	_set_hotkey_types,
	hotkey_mode_checked_rows,
	hotkey_mode_from_checked_rows,
	hotkey_types_checked_rows,
	hotkey_types_from_checked_rows,
)
from .constants import (
	HOTKEY_FORMAT_CHOICES,
	HOTKEY_FORMAT_NATIVE,
	HOTKEY_MODE_BOTH,
	HOTKEY_MODE_FLAGS,
	HOTKEY_MODE_OFF,
	HOTKEY_TYPES_BOTH,
	HOTKEY_TYPES_FLAGS,
)

log = logHandler.log

class HotkeysPanel(wx.Panel):
	def __init__(self, parent):
		super().__init__(parent)

		self.hotkeyMode = _get_hotkey_mode()
		self.hotkeyFormat = _get_hotkey_format()
		self.hotkeyTypes = _get_hotkey_types()
		self.dialogAccessKeyOnly = _get_hotkey_dialog_access_key_only()
		self._description = (
			_("Hotkey speech is separate from verbosity profiles. "
			"Choose where ClassicSpeech should announce keyboard shortcuts and how extracted shortcuts should be spoken. "
			"Object query always includes the shortcut when NVDA exposes one.")
		)
		_set_panel_description(self, _("Hotkeys"), self._description)

		mainSizer = wx.BoxSizer(wx.VERTICAL)

		mainSizer.Add(
			wx.StaticText(self, label=self._description),
			0,
			wx.ALL | wx.EXPAND,
			8,
		)

		grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
		grid.AddGrowableCol(1, 1)
		grid.Add(wx.StaticText(self, label=_("Speak hotkeys &in:")), 0, wx.ALIGN_TOP)
		self.hotkeyModeList = make_check_list(
			self,
			_("Speak hotkeys in"),
			[label for label, _value in HOTKEY_MODE_FLAGS],
		)
		grid.Add(self.hotkeyModeList, 1, wx.EXPAND)

		grid.Add(wx.StaticText(self, label=_("Shortcut formatting:")), 0, wx.ALIGN_CENTER_VERTICAL)
		self.hotkeyFormatChoice = wx.Choice(
			self,
			choices=[label for label, _value in HOTKEY_FORMAT_CHOICES],
		)
		self.hotkeyFormatChoice.SetName(_("Shortcut formatting"))
		grid.Add(self.hotkeyFormatChoice, 1, wx.EXPAND)

		grid.Add(wx.StaticText(self, label=_("Which shortcuts to &speak:")), 0, wx.ALIGN_TOP)
		self.hotkeyTypesList = make_check_list(
			self,
			_("Which shortcuts to speak"),
			[label for label, _value in HOTKEY_TYPES_FLAGS],
		)
		grid.Add(self.hotkeyTypesList, 1, wx.EXPAND)
		mainSizer.Add(grid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		self.dialogAccessKeyOnlyCheck = wx.CheckBox(
			self,
			label=_("For simple dialog Alt shortcuts, speak only the access key letter"),
		)
		mainSizer.Add(self.dialogAccessKeyOnlyCheck, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)
		self.SetSizer(mainSizer)

		self._loadControlsFromConfig()
		self._syncDependentControlsAvailability()
		# CustomCheckListBox reports a checked state change through
		# EVT_CHECKLISTBOX for both keyboard and mouse.
		self.hotkeyModeList.Bind(wx.EVT_CHECKLISTBOX, self.onCheckListChanged)
		self.hotkeyTypesList.Bind(wx.EVT_CHECKLISTBOX, self.onCheckListChanged)
		self.hotkeyFormatChoice.Bind(wx.EVT_CHOICE, self.onInlineChanged)
		self.dialogAccessKeyOnlyCheck.Bind(wx.EVT_CHECKBOX, self.onInlineChanged)

	def _loadControlsFromConfig(self):
		set_checked_indices(
			self.hotkeyModeList,
			hotkey_mode_checked_rows(self.hotkeyMode or HOTKEY_MODE_BOTH),
		)

		format_value = str(self.hotkeyFormat or HOTKEY_FORMAT_NATIVE)
		for index, (_label, value) in enumerate(HOTKEY_FORMAT_CHOICES):
			if value == format_value:
				self.hotkeyFormatChoice.SetSelection(index)
				break
		else:
			self.hotkeyFormatChoice.SetSelection(0)

		set_checked_indices(
			self.hotkeyTypesList,
			hotkey_types_checked_rows(self.hotkeyTypes or HOTKEY_TYPES_BOTH),
		)

		self.dialogAccessKeyOnlyCheck.SetValue(bool(self.dialogAccessKeyOnly))

	def _getModeFromChoice(self):
		return hotkey_mode_from_checked_rows(checked_indices(self.hotkeyModeList))

	def _getFormatFromChoice(self):
		selection = self.hotkeyFormatChoice.GetSelection()
		if selection < 0 or selection >= len(HOTKEY_FORMAT_CHOICES):
			return HOTKEY_FORMAT_NATIVE
		return HOTKEY_FORMAT_CHOICES[selection][1]

	def _getTypesFromChoice(self):
		return hotkey_types_from_checked_rows(checked_indices(self.hotkeyTypesList))

	def onCheckListChanged(self, evt=None):
		# Let NVDA's check list announce the new checked state first.
		if evt is not None and hasattr(evt, "Skip"):
			evt.Skip()
		self.onInlineChanged()

	def onInlineChanged(self, evt=None):
		try:
			self.hotkeyMode = self._getModeFromChoice()
			self._syncDependentControlsAvailability()
			self.hotkeyFormat = self._getFormatFromChoice()
			self.hotkeyTypes = self._getTypesFromChoice()
			self.dialogAccessKeyOnly = self.dialogAccessKeyOnlyCheck.GetValue()
			self.apply_live(save=False)
			dlg = wx.GetTopLevelParent(self)
			if hasattr(dlg, "_markDirty"):
				dlg._markDirty()
		except Exception:
			log.exception("ClassicSpeech hotkey settings live apply failed")

	def _syncDependentControlsAvailability(self):
		enabled = self._getModeFromChoice() != HOTKEY_MODE_OFF
		for control in (
			self.hotkeyFormatChoice,
			self.hotkeyTypesList,
			self.dialogAccessKeyOnlyCheck,
		):
			control.Enable(enabled)

	def apply_live(self, save=True):
		self.hotkeyMode = self._getModeFromChoice()
		self.hotkeyFormat = self._getFormatFromChoice()
		self.hotkeyTypes = self._getTypesFromChoice()
		self.dialogAccessKeyOnly = self.dialogAccessKeyOnlyCheck.GetValue()
		_set_hotkey_mode(self.hotkeyMode)
		_set_hotkey_format(self.hotkeyFormat)
		_set_hotkey_types(self.hotkeyTypes)
		_set_hotkey_dialog_access_key_only(self.dialogAccessKeyOnly)

	def get_working_hotkey_config(self):
		self.hotkeyMode = self._getModeFromChoice()
		self.hotkeyFormat = self._getFormatFromChoice()
		self.hotkeyTypes = self._getTypesFromChoice()
		self.dialogAccessKeyOnly = self.dialogAccessKeyOnlyCheck.GetValue()
		return {
			"mode": self.hotkeyMode,
			"format": self.hotkeyFormat,
			"types": self.hotkeyTypes,
			"dialogAccessKeyOnly": bool(self.dialogAccessKeyOnly),
		}

	def get_working_hotkey_mode(self):
		return self.get_working_hotkey_config()["mode"]
