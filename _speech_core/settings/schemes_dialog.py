"""ClassicSpeech Speech and Sound Schemes dialog.

A JAWS-style Speech and Sounds Manager for NVDA: named schemes, and for every
item (object roles, states, window classes, document formatting and web
elements) an optional WAV sound and an optional voice. Nothing changes until
OK or Apply; Cancel and Close restore the saved schemes.
"""
from __future__ import annotations

import wx
import logHandler
from wx.lib import scrolledpanel

from ..localization import _
from ..schemes import store as schemeStore
from .schemes_panel import SchemeItemsPanel

log = logHandler.log


class SpeechSoundSchemesDialog(wx.Dialog):
	"""Edit Speech and Sound Schemes transactionally."""

	def __init__(self, parent, focus_class_name=""):
		super().__init__(
			parent,
			title=_("ClassicSpeech Speech and Sound Schemes"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX,
		)
		self.SetName("ClassicSpeechSpeechSoundSchemesDialog")
		self.store = schemeStore.SchemeStore()
		outer = wx.BoxSizer(wx.VERTICAL)

		intro = wx.StaticText(
			self,
			label=_(
				"Choose sounds and voices for object types, object states, window classes, document formatting "
				"and web elements. Items without a sound or voice keep NVDA's normal speech. Search for an item "
				"by name, or list only the items you have changed."
			),
		)
		outer.Add(intro, 0, wx.EXPAND | wx.ALL, 8)

		self.enableCheckBox = wx.CheckBox(self, label=_("&Enable speech and sound schemes"))
		self.enableCheckBox.SetValue(self.store.enabled)
		outer.Add(self.enableCheckBox, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

		schemeRow = wx.BoxSizer(wx.HORIZONTAL)
		schemeRow.Add(wx.StaticText(self, label=_("Active sc&heme:")), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
		self.schemeChoice = wx.Choice(self, choices=[])
		self.schemeChoice.SetName(_("Active scheme"))
		schemeRow.Add(self.schemeChoice, 1, wx.EXPAND | wx.RIGHT, 8)
		self.newSchemeButton = wx.Button(self, label=_("Ne&w scheme..."))
		self.copySchemeButton = wx.Button(self, label=_("C&opy scheme..."))
		self.renameSchemeButton = wx.Button(self, label=_("Rena&me scheme..."))
		self.deleteSchemeButton = wx.Button(self, label=_("Dele&te scheme"))
		for button in (self.newSchemeButton, self.copySchemeButton, self.renameSchemeButton, self.deleteSchemeButton):
			schemeRow.Add(button, 0, wx.RIGHT, 4)
		outer.Add(schemeRow, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

		self.scroller = scrolledpanel.ScrolledPanel(self, style=wx.TAB_TRAVERSAL | wx.BORDER_THEME)
		scrollerSizer = wx.BoxSizer(wx.VERTICAL)
		self.itemsPanel = SchemeItemsPanel(
			self.scroller,
			self.store,
			formatting_only=False,
			show_sounds=True,
			on_change=self._markDirty,
			focus_class_name=focus_class_name,
		)
		scrollerSizer.Add(self.itemsPanel, 1, wx.EXPAND)
		self.scroller.SetSizer(scrollerSizer)
		self.scroller.SetupScrolling(scroll_x=False)
		outer.Add(self.scroller, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

		buttons = wx.StdDialogButtonSizer()
		self.okButton = wx.Button(self, wx.ID_OK, label=_("OK"))
		self.cancelButton = wx.Button(self, wx.ID_CANCEL, label=_("Cancel"))
		self.applyButton = wx.Button(self, wx.ID_APPLY, label=_("&Apply"))
		buttons.AddButton(self.okButton)
		buttons.AddButton(self.cancelButton)
		buttons.AddButton(self.applyButton)
		buttons.Realize()
		self.okButton.SetDefault()
		outer.Add(buttons, 0, wx.ALIGN_RIGHT | wx.ALL, 8)
		self.SetSizer(outer)
		self.SetEscapeId(wx.ID_CANCEL)
		self.SetMinSize((820, 600))
		self.SetSize((1000, 760))
		self.CentreOnParent()

		self._loadSchemeChoice()
		self.applyButton.Disable()
		self.enableCheckBox.Bind(wx.EVT_CHECKBOX, self.onEnableChanged)
		self.schemeChoice.Bind(wx.EVT_CHOICE, self.onSchemeChanged)
		self.newSchemeButton.Bind(wx.EVT_BUTTON, lambda evt: self.onAddScheme(copy_current=False))
		self.copySchemeButton.Bind(wx.EVT_BUTTON, lambda evt: self.onAddScheme(copy_current=True))
		self.renameSchemeButton.Bind(wx.EVT_BUTTON, self.onRenameScheme)
		self.deleteSchemeButton.Bind(wx.EVT_BUTTON, self.onDeleteScheme)
		self.okButton.Bind(wx.EVT_BUTTON, self.onOK)
		self.cancelButton.Bind(wx.EVT_BUTTON, self.onCancel)
		self.applyButton.Bind(wx.EVT_BUTTON, self.onApply)
		self.Bind(wx.EVT_CLOSE, self.onClose)
		wx.CallAfter(self.enableCheckBox.SetFocus)

	# -- schemes ----------------------------------------------------------------
	def _loadSchemeChoice(self):
		names = self.store.scheme_names
		self.schemeChoice.SetItems(names)
		self.schemeChoice.SetSelection(names.index(self.store.active_scheme))
		self.deleteSchemeButton.Enable(len(names) > 1)

	def _markDirty(self):
		self.applyButton.Enable()

	def onEnableChanged(self, event):
		self.store.enabled = self.enableCheckBox.GetValue()
		self._markDirty()

	def onSchemeChanged(self, event):
		index = self.schemeChoice.GetSelection()
		names = self.store.scheme_names
		if 0 <= index < len(names):
			self.store.set_active_scheme(names[index])
			self.itemsPanel.rebuildTree()
			self._markDirty()

	def _askSchemeName(self, title, default=""):
		with wx.TextEntryDialog(self, _("Scheme name:"), title, value=default) as dialog:
			if dialog.ShowModal() != wx.ID_OK:
				return ""
			return dialog.GetValue().strip()

	def onAddScheme(self, copy_current):
		title = _("Copy scheme") if copy_current else _("New scheme")
		default = _("{name} copy").format(name=self.store.active_scheme) if copy_current else ""
		name = self._askSchemeName(title, default)
		if not name:
			return
		self.store.add_scheme(name, copy_from=self.store.active_scheme if copy_current else None)
		self._loadSchemeChoice()
		self.itemsPanel.rebuildTree()
		self._markDirty()
		self.schemeChoice.SetFocus()

	def onRenameScheme(self, event):
		old = self.store.active_scheme
		name = self._askSchemeName(_("Rename scheme"), old)
		if not name or name == old:
			return
		self.store.rename_scheme(old, name)
		self._loadSchemeChoice()
		self._markDirty()
		self.schemeChoice.SetFocus()

	def onDeleteScheme(self, event):
		name = self.store.active_scheme
		if len(self.store.scheme_names) <= 1:
			return
		answer = wx.MessageBox(
			_("Delete the scheme {name} and all of its sounds and voices?").format(name=name),
			_("Delete scheme"),
			wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
			self,
		)
		if answer != wx.YES:
			return
		self.store.delete_scheme(name)
		self._loadSchemeChoice()
		self.itemsPanel.rebuildTree()
		self._markDirty()
		self.schemeChoice.SetFocus()

	# -- transaction -----------------------------------------------------------
	def onApply(self, event=None):
		try:
			self.store.apply()
			self.store.mark_applied()
			self.applyButton.Disable()
			return True
		except Exception:
			log.exception("ClassicSpeech Speech and Sound Schemes apply failed")
			wx.MessageBox(
				_("The schemes could not be saved. See the NVDA log for details."),
				_("Speech and Sound Schemes"),
				wx.OK | wx.ICON_ERROR,
				self,
			)
			return False

	def onOK(self, event):
		if self.onApply():
			self._finish()

	def onCancel(self, event):
		self.store.cancel()
		self._finish()

	def onClose(self, event):
		self.store.cancel()
		self.itemsPanel.cleanup()
		event.Skip()

	def _finish(self):
		self.itemsPanel.cleanup()
		self.Destroy()
