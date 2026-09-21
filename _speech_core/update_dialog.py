"""The dialog that offers a ClassicSpeech update, with its release notes to read.

A message box speaks its whole text once and there is nothing to move through
afterwards, so the "What's new" section of a release went by in one breath.
Here the notes are a read-only multiline edit box: NVDA treats it as text, so
it can be read line by line, word by word or character by character with the
arrow keys, reviewed, selected and copied, and it scrolls for a long release.

The box is read-only, so nothing the user types can change what will be
installed. Focus starts in it, and Tab reaches the buttons.
"""
from __future__ import annotations

import wx

import gui
import logHandler
from gui import guiHelper

from .localization import _

log = logHandler.log

#: Wide and tall enough for a paragraph of release notes without scrolling.
NOTES_SIZE = (620, 260)


class UpdateOfferDialog(wx.Dialog):
	"""What is available, what is new in it, and what happens next."""

	def __init__(self, parent, title, summary, notes, question="", install_label="", close_label=""):
		super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._offers_install = bool(install_label)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		contents = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		if summary:
			contents.addItem(self._paragraph(summary))
		self.notes = contents.addLabeledControl(
			# Translators: The label of the read-only box holding a release's notes.
			_("&What's new:"),
			wx.TextCtrl,
			value=notes or "",
			style=wx.TE_MULTILINE | wx.TE_READONLY,
			size=NOTES_SIZE,
		)
		if question:
			contents.addItem(self._paragraph(question))

		buttons = wx.BoxSizer(wx.HORIZONTAL)
		self.installButton = None
		if self._offers_install:
			self.installButton = wx.Button(self, id=wx.ID_YES, label=install_label)
			buttons.Add(self.installButton, flag=wx.RIGHT, border=8)
		self.closeButton = wx.Button(self, id=wx.ID_CANCEL, label=close_label or _("&Close"))
		buttons.Add(self.closeButton)
		contents.addItem(buttons)

		mainSizer.Add(contents.sizer, flag=wx.ALL | wx.EXPAND, border=guiHelper.BORDER_FOR_DIALOGS, proportion=1)
		self.SetSizer(mainSizer)
		mainSizer.Fit(self)
		self.CentreOnScreen()

		if self.installButton is not None:
			self.installButton.SetDefault()
			self.installButton.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_YES))
		self.closeButton.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_CANCEL))
		self.Bind(wx.EVT_CHAR_HOOK, self.onCharHook)
		# The notes are the reason the dialog is here, so reading can start at once.
		self.notes.SetFocus()
		self.notes.SetInsertionPoint(0)

	def _paragraph(self, text):
		"""A line of explanation, wrapped to the width of the notes box."""
		label = wx.StaticText(self, label=text)
		try:
			label.Wrap(NOTES_SIZE[0])
		except Exception:
			log.debug("ClassicSpeech update dialog: could not wrap a label", exc_info=True)
		return label

	def onCharHook(self, event):
		if event.GetKeyCode() == wx.WXK_ESCAPE:
			self.EndModal(wx.ID_CANCEL)
			return
		event.Skip()


def show_update_offer(title, summary, notes, question="", install_label="", close_label=""):
	"""Show the dialog and return the button the user chose.

	Runs from wx's own event loop, never inside NVDA's core queue: it waits for
	the user, and NVDA's queue does not run again until it returns.
	"""
	parent = gui.mainFrame
	parent.prePopup()
	try:
		dialog = UpdateOfferDialog(
			parent, title, summary, notes,
			question=question,
			install_label=install_label,
			close_label=close_label,
		)
		try:
			return dialog.ShowModal()
		finally:
			dialog.Destroy()
	finally:
		parent.postPopup()
