"""Accessible item browser and editor for Speech and Sound Schemes.

The same panel is used by the Speech and Sound Schemes dialog (sounds and
voices for every item) and by the Voice Profiles "Document and web formatting"
category (voices for formatting and element items only).

Tab order:

* Search box and a "Show" filter (all items, or only items with a sound or voice).
* A tree of categories and items. Each item's label ends with what is set,
  for example "Bold (sound, voice)".
* Buttons to add fonts, font sizes and window classes, and to remove them.
* The selected item's details and editor: sound file and behavior, custom
  voice, synthesizer, voice settings, voice preview and reset.
"""
from __future__ import annotations

import os

import wx
import logHandler

from ..localization import _
from ..nvda_settings_backup import recording_nvda_change
from ..schemes import catalog as schemeCatalog
from ..voice_profile_trigger import keep_settings_out_of_nvda_config
from .voice_profile_controls import VoiceProfileControls
from .voice_profiles_config import (
	get_synth_id,
	new_voice_record,
	set_voice_record_value,
	voice_record_preview_snapshot,
	voice_record_snapshot,
)

log = logHandler.log

SOUND_MODE_CHOICES = (
	(False, _("Also speak the announcement")),
	(True, _("Do not speak the announcement (sound only)")),
)
SHOW_ALL = 0
SHOW_CUSTOMIZED = 1

#: Installed synthesizers as ``[(name, description)]``; discovered on request
#: because discovery imports every synthesizer driver.
_synth_list_cache = None


def load_editing_synthesizer(engine):
	"""Load another synthesizer only to edit and preview its voices.

	The dialog changes this copy's settings freely, so it must never save them
	as the user's NVDA voice settings, which NVDA would otherwise do when it
	saves its configuration and when the copy is unloaded. Loading a
	synthesizer NVDA has never used adds its default settings to NVDA's
	configuration; that is recorded, so resetting ClassicSpeech removes them.
	"""
	import synthDriverHandler

	with recording_nvda_change(("speech",), engine):
		probe = synthDriverHandler.getSynthInstance(engine)
	keep_settings_out_of_nvda_config(probe)
	return probe


def _installed_font_names():
	try:
		names = wx.FontEnumerator.GetFacenames()
	except Exception:
		return []
	return sorted({str(name) for name in names if name and not str(name).startswith("@")}, key=str.lower)


def discover_synthesizers():
	global _synth_list_cache
	if _synth_list_cache is None:
		try:
			import synthDriverHandler
			_synth_list_cache = [(str(name), str(description)) for name, description in synthDriverHandler.getSynthList()]
		except Exception:
			log.debug("ClassicSpeech schemes: synthesizer list unavailable", exc_info=True)
			_synth_list_cache = []
	return list(_synth_list_cache)


def _item_status_text(summary) -> str:
	parts = []
	if summary.get("sound"):
		parts.append(_("sound only") if summary.get("soundOnly") else _("sound"))
	if summary.get("voice"):
		engine = summary.get("engine")
		parts.append(_("voice on {engine}").format(engine=engine) if engine else _("voice"))
	return ", ".join(parts)


def _active_driver():
	try:
		import synthDriverHandler
		return synthDriverHandler.getSynth()
	except Exception:
		return None


class SchemeItemsPanel(wx.Panel):
	"""Tree of scheme items plus the editor for the selected item."""

	def __init__(
		self,
		parent,
		store,
		*,
		formatting_only=False,
		show_sounds=True,
		on_change=None,
		focus_class_name="",
	):
		super().__init__(parent)
		self.store = store
		self.formattingOnly = bool(formatting_only)
		self.showSounds = bool(show_sounds)
		self._onChange = on_change
		self._focusClassName = str(focus_class_name or "")
		self._installedFonts = _installed_font_names()
		self._nodesByItem = {}
		self._itemsById = {}
		self._currentItemId = None
		self._currentCategoryKind = ""
		self._voiceControls = None
		self._voiceDriver = None
		self._probes = {}
		self._searchTimer = None
		self._loading = False
		self._rebuilding = False
		self._synthValues = [""]

		mainSizer = wx.BoxSizer(wx.VERTICAL)
		self._buildFilters(mainSizer)
		self._buildTree(mainSizer)
		self._buildCustomEntryButtons(mainSizer)
		self._buildEditor(mainSizer)
		self.SetSizer(mainSizer)
		self.rebuildTree()

	# -- construction ------------------------------------------------------
	def _buildFilters(self, sizer):
		row = wx.BoxSizer(wx.HORIZONTAL)
		row.Add(wx.StaticText(self, label=_("&Search items:")), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
		self.searchText = wx.TextCtrl(self)
		self.searchText.SetName(_("Search items"))
		row.Add(self.searchText, 1, wx.EXPAND | wx.RIGHT, 12)
		row.Add(wx.StaticText(self, label=_("&List:")), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
		self.showChoice = wx.Choice(self, choices=[_("All items"), _("Only items with a sound or voice")])
		self.showChoice.SetName(_("List"))
		self.showChoice.SetSelection(SHOW_ALL)
		row.Add(self.showChoice, 0)
		sizer.Add(row, 0, wx.EXPAND | wx.ALL, 4)
		self.searchText.Bind(wx.EVT_TEXT, self.onSearchText)
		self.showChoice.Bind(wx.EVT_CHOICE, lambda evt: self.rebuildTree())

	def _buildTree(self, sizer):
		label = _("Document and web formatting &items:") if self.formattingOnly else _("Scheme &items:")
		sizer.Add(wx.StaticText(self, label=label), 0, wx.LEFT | wx.RIGHT | wx.TOP, 4)
		self.tree = wx.TreeCtrl(
			self,
			style=wx.TR_HAS_BUTTONS | wx.TR_HIDE_ROOT | wx.TR_SINGLE | wx.TR_LINES_AT_ROOT,
			size=(-1, 240),
		)
		self.tree.SetName(label.replace("&", "").rstrip(":"))
		sizer.Add(self.tree, 1, wx.EXPAND | wx.ALL, 4)
		self.tree.Bind(wx.EVT_TREE_SEL_CHANGED, self.onTreeSelection)

	def _buildCustomEntryButtons(self, sizer):
		row = wx.BoxSizer(wx.HORIZONTAL)
		self.addFontButton = wx.Button(self, label=_("Add font &name..."))
		self.addFontSizeButton = wx.Button(self, label=_("Add font si&ze..."))
		self.addStyleButton = wx.Button(self, label=_("Add style name..."))
		row.Add(self.addFontButton, 0, wx.RIGHT, 4)
		row.Add(self.addFontSizeButton, 0, wx.RIGHT, 4)
		row.Add(self.addStyleButton, 0, wx.RIGHT, 4)
		self.addClassButton = None
		if not self.formattingOnly:
			self.addClassButton = wx.Button(self, label=_("Add window &class..."))
			row.Add(self.addClassButton, 0, wx.RIGHT, 4)
			self.addClassButton.Bind(wx.EVT_BUTTON, lambda evt: self.onAddCustomEntry("classes"))
		self.removeEntryButton = wx.Button(self, label=_("Remove adde&d entry"))
		row.Add(self.removeEntryButton, 0)
		sizer.Add(row, 0, wx.ALL, 4)
		self.addFontButton.Bind(wx.EVT_BUTTON, lambda evt: self.onAddCustomEntry("fonts"))
		self.addFontSizeButton.Bind(wx.EVT_BUTTON, lambda evt: self.onAddCustomEntry("fontSizes"))
		self.addStyleButton.Bind(wx.EVT_BUTTON, lambda evt: self.onAddCustomEntry("styles"))
		self.removeEntryButton.Bind(wx.EVT_BUTTON, self.onRemoveCustomEntry)
		self.removeEntryButton.Disable()

	def _buildEditor(self, sizer):
		box = wx.StaticBoxSizer(wx.VERTICAL, self, label=_("Selected item"))
		parent = box.GetStaticBox()

		box.Add(wx.StaticText(parent, label=_("Item details:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 4)
		self.itemDetails = wx.TextCtrl(parent, style=wx.TE_READONLY | wx.TE_MULTILINE | wx.TE_NO_VSCROLL, size=(-1, 54))
		self.itemDetails.SetName(_("Item details"))
		box.Add(self.itemDetails, 0, wx.EXPAND | wx.ALL, 4)

		if self.showSounds:
			soundRow = wx.BoxSizer(wx.HORIZONTAL)
			soundRow.Add(wx.StaticText(parent, label=_("Sound &file:")), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
			self.soundPath = wx.TextCtrl(parent, style=wx.TE_READONLY)
			self.soundPath.SetName(_("Sound file"))
			soundRow.Add(self.soundPath, 1, wx.EXPAND)
			box.Add(soundRow, 0, wx.EXPAND | wx.ALL, 4)
			buttons = wx.BoxSizer(wx.HORIZONTAL)
			self.browseSoundButton = wx.Button(parent, label=_("&Browse for sound..."))
			self.playSoundButton = wx.Button(parent, label=_("&Play sound"))
			self.removeSoundButton = wx.Button(parent, label=_("Remove so&und"))
			for button in (self.browseSoundButton, self.playSoundButton, self.removeSoundButton):
				buttons.Add(button, 0, wx.RIGHT, 4)
			box.Add(buttons, 0, wx.ALL, 4)
			modeRow = wx.BoxSizer(wx.HORIZONTAL)
			modeRow.Add(wx.StaticText(parent, label=_("When playin&g the sound:")), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
			self.soundModeChoice = wx.Choice(parent, choices=[label for _value, label in SOUND_MODE_CHOICES])
			self.soundModeChoice.SetName(_("When playing the sound"))
			modeRow.Add(self.soundModeChoice, 1, wx.EXPAND)
			box.Add(modeRow, 0, wx.EXPAND | wx.ALL, 4)
			self.browseSoundButton.Bind(wx.EVT_BUTTON, self.onBrowseSound)
			self.playSoundButton.Bind(wx.EVT_BUTTON, self.onPlaySound)
			self.removeSoundButton.Bind(wx.EVT_BUTTON, self.onRemoveSound)
			self.soundModeChoice.Bind(wx.EVT_CHOICE, self.onSoundMode)

		self.voiceCheckBox = wx.CheckBox(parent, label=_("Use a custom &voice for this item"))
		box.Add(self.voiceCheckBox, 0, wx.ALL, 4)
		synthRow = wx.BoxSizer(wx.HORIZONTAL)
		synthRow.Add(wx.StaticText(parent, label=_("S&ynthesizer:")), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
		self.synthChoice = wx.Choice(parent, choices=[])
		self.synthChoice.SetName(_("Synthesizer"))
		synthRow.Add(self.synthChoice, 1, wx.EXPAND)
		box.Add(synthRow, 0, wx.EXPAND | wx.ALL, 4)
		self.engineNote = wx.StaticText(
			parent,
			label=_(
				"The active synthesizer switches voices fastest. Another synthesizer is loaded each time "
				"this item is spoken and unloaded afterwards, which adds a noticeable delay."
			),
		)
		box.Add(self.engineNote, 0, wx.EXPAND | wx.ALL, 4)
		self.voicePanel = wx.Panel(parent)
		self.voicePanelSizer = wx.BoxSizer(wx.VERTICAL)
		self.voicePanel.SetSizer(self.voicePanelSizer)
		box.Add(self.voicePanel, 0, wx.EXPAND | wx.ALL, 4)
		actions = wx.BoxSizer(wx.HORIZONTAL)
		self.previewVoiceButton = wx.Button(parent, label=_("Spea&k a voice preview"))
		self.resetItemButton = wx.Button(parent, label=_("&Reset this item"))
		actions.Add(self.previewVoiceButton, 0, wx.RIGHT, 4)
		actions.Add(self.resetItemButton, 0)
		box.Add(actions, 0, wx.ALL, 4)
		sizer.Add(box, 0, wx.EXPAND | wx.ALL, 4)

		self.voiceCheckBox.Bind(wx.EVT_CHECKBOX, self.onVoiceToggled)
		self.synthChoice.Bind(wx.EVT_CHOICE, self.onSynthChanged)
		self.previewVoiceButton.Bind(wx.EVT_BUTTON, self.onPreviewVoice)
		self.resetItemButton.Bind(wx.EVT_BUTTON, self.onResetItem)

	# -- tree ------------------------------------------------------------------
	def _categories(self):
		categories = schemeCatalog.build_categories(self.store.custom_entries(), self._installedFonts)
		if self.formattingOnly:
			categories = [category for category in categories if category.formatting]
		return categories

	def rebuildTree(self, select_item_id=None):
		"""Rebuild the tree for the current search and show filter."""
		select_item_id = select_item_id or self._currentItemId
		query = self.searchText.GetValue().strip().lower()
		customizedOnly = self.showChoice.GetSelection() == SHOW_CUSTOMIZED
		configured = self.store.configured_item_ids()
		nodeToSelect = None
		firstItemNode = None
		# Deleting and adding items sends selection events; they are handled
		# once, after the new tree is complete.
		self._rebuilding = True
		self.tree.Freeze()
		try:
			self.tree.DeleteAllItems()
			root = self.tree.AddRoot("root")
			self._nodesByItem = {}
			self._itemsById = {}
			for category in self._categories():
				items = []
				for item in category.items:
					if query and query not in item.label.lower() and query not in category.label.lower():
						continue
					if customizedOnly and item.item_id not in configured:
						continue
					items.append(item)
				if (query or customizedOnly) and not items:
					continue
				categoryNode = self.tree.AppendItem(root, category.label)
				self.tree.SetItemData(categoryNode, ("category", category.category_id, category.custom_kind))
				for item in items:
					self._itemsById.setdefault(item.item_id, item)
					node = self.tree.AppendItem(categoryNode, self._itemLabel(item))
					self.tree.SetItemData(node, ("item", item.item_id, category.custom_kind))
					self._nodesByItem.setdefault(item.item_id, []).append(node)
					if firstItemNode is None:
						firstItemNode = node
					if nodeToSelect is None and item.item_id == select_item_id:
						nodeToSelect = node
				if query or customizedOnly:
					self.tree.Expand(categoryNode)
		finally:
			self.tree.Thaw()
			self._rebuilding = False
		if nodeToSelect is None and (query or customizedOnly):
			nodeToSelect = firstItemNode
		if nodeToSelect is None:
			first, _cookie = self.tree.GetFirstChild(self.tree.GetRootItem())
			nodeToSelect = first if first.IsOk() else None
		if nodeToSelect is not None:
			self.tree.SelectItem(nodeToSelect)
			self.tree.EnsureVisible(nodeToSelect)
		self._showSelection()

	def _itemLabel(self, item):
		status = _item_status_text(self.store.item_summary(item.item_id))
		return f"{item.label} ({status})" if status else item.label

	def _refreshItemLabels(self, item_id):
		item = self._itemsById.get(item_id)
		if item is None:
			return
		label = self._itemLabel(item)
		for node in self._nodesByItem.get(item_id, ()):
			try:
				self.tree.SetItemText(node, label)
			except Exception:
				pass

	def _selectedData(self):
		node = self.tree.GetSelection()
		if not node or not node.IsOk():
			return None
		try:
			return self.tree.GetItemData(node)
		except Exception:
			return None

	def _showSelection(self):
		data = self._selectedData()
		if data and data[0] == "item":
			self._showItem(data[1], data[2])
		else:
			self._showItem(None, data[2] if data else "")

	def onSearchText(self, event):
		if self._searchTimer is not None:
			try:
				self._searchTimer.Stop()
			except Exception:
				pass
		self._searchTimer = wx.CallLater(300, self.rebuildTree)

	def onTreeSelection(self, event):
		# Selection events also arrive while the tree is rebuilt or destroyed.
		if self._rebuilding:
			return
		try:
			if not self or self.IsBeingDeleted() or not self.tree or self.tree.IsBeingDeleted():
				return
		except RuntimeError:
			return
		self._showSelection()

	# -- editor -----------------------------------------------------------------
	def _showItem(self, item_id, category_kind=""):
		self._loading = True
		try:
			self._currentItemId = item_id
			self._currentCategoryKind = category_kind or ""
			self.removeEntryButton.Enable(bool(item_id) and self._isCustomEntry(category_kind, item_id))
			enabled = item_id is not None
			item = self._itemsById.get(item_id) if item_id else None
			if item is None:
				self.itemDetails.SetValue(_("Select an item in the tree to change its sound or voice."))
			else:
				scope = {
					schemeCatalog.SCOPE_TEXT: _("A voice applies to the announcement and to the formatted text or element content."),
					schemeCatalog.SCOPE_OBJECT: _("A voice applies to everything spoken about the object."),
				}.get(item.voice_scope, _("A voice applies to the announcement."))
				self.itemDetails.SetValue(" ".join(part for part in (item.label + ".", item.description, scope) if part))
			settings = self.store.get_item(item_id) if item_id else {}
			if self.showSounds:
				sound = settings.get("sound", "")
				self.soundPath.SetValue(sound)
				self.soundModeChoice.SetSelection(1 if settings.get("soundOnly") else 0)
				self.browseSoundButton.Enable(enabled)
				self.playSoundButton.Enable(enabled and bool(sound))
				self.removeSoundButton.Enable(enabled and bool(sound))
				self.soundModeChoice.Enable(enabled and bool(sound))
			voice = settings.get("voice") or {}
			self.voiceCheckBox.Enable(enabled)
			self.voiceCheckBox.SetValue(bool(voice.get("enabled")))
			self.resetItemButton.Enable(enabled and bool(settings))
			self._loadSynthChoices(voice.get("engine", ""))
			self._rebuildVoiceControls()
		finally:
			self._loading = False
		self.Layout()

	def _isCustomEntry(self, kind, item_id):
		if not kind or not item_id:
			return False
		for value in self.store.custom_entries().get(kind, []):
			try:
				if schemeCatalog.custom_entry_item_id(kind, value) == item_id:
					return True
			except KeyError:
				return False
		return False

	def _loadSynthChoices(self, engine):
		driver = _active_driver()
		activeName = get_synth_id(driver) if driver is not None else ""
		activeDescription = str(getattr(driver, "description", "") or activeName)
		values = [""]
		labels = [_("Active synthesizer ({name})").format(name=activeDescription)]
		known = _synth_list_cache
		if known is None and engine and engine != activeName:
			known = discover_synthesizers()
		if known is not None:
			for name, description in known:
				if name in (activeName, "silence") or name in values:
					continue
				values.append(name)
				labels.append(description)
			if engine and engine != activeName and engine not in values:
				values.append(engine)
				labels.append(engine)
		else:
			values.append(None)
			labels.append(_("Other synthesizers..."))
		self._synthValues = values
		self.synthChoice.SetItems(labels)
		selected = engine if engine and engine != activeName else ""
		self.synthChoice.SetSelection(values.index(selected) if selected in values else 0)
		voiceEnabled = self._currentItemId is not None and self.voiceCheckBox.GetValue()
		self.synthChoice.Enable(voiceEnabled)

	def _currentEngine(self):
		index = self.synthChoice.GetSelection()
		if index < 0 or index >= len(self._synthValues):
			return ""
		return self._synthValues[index] or ""

	def _driverForEngine(self, engine):
		active = _active_driver()
		if not engine or (active is not None and get_synth_id(active) == engine):
			return active
		probe = self._probes.get(engine)
		if probe is not None:
			return probe
		try:
			probe = load_editing_synthesizer(engine)
		except Exception:
			log.error("ClassicSpeech schemes: could not load synthesizer %s", engine, exc_info=True)
			wx.MessageBox(
				_("ClassicSpeech could not load the {engine} synthesizer. The item keeps using the active synthesizer.").format(engine=engine),
				_("Speech and Sound Schemes"),
				wx.OK | wx.ICON_ERROR,
				self,
			)
			return None
		self._probes[engine] = probe
		return probe

	def _clearVoiceControls(self):
		self.voicePanelSizer.Clear(delete_windows=True)
		self._voiceControls = None
		self._voiceDriver = None

	def _rebuildVoiceControls(self):
		self._clearVoiceControls()
		item_id = self._currentItemId
		enabled = item_id is not None and self.voiceCheckBox.GetValue()
		self.previewVoiceButton.Enable(enabled)
		self.engineNote.Show(enabled)
		if not enabled:
			self.voicePanel.Layout()
			return
		engine = self._currentEngine()
		driver = self._driverForEngine(engine)
		if driver is None and engine:
			# The chosen synthesizer cannot be loaded; keep the item on the active one.
			settings = self.store.get_item(item_id)
			if isinstance(settings.get("voice"), dict):
				settings["voice"]["engine"] = ""
				self.store.set_item(item_id, settings)
			self._loadSynthChoices("")
			engine = ""
			driver = _active_driver()
		if driver is None:
			self.voicePanel.Layout()
			return
		settings = self.store.get_item(item_id)
		voice = settings.get("voice")
		if not isinstance(voice, dict):
			voice = {"enabled": True, "engine": engine, "bySynth": {}}
			settings["voice"] = voice
		synthName = get_synth_id(driver)
		record = (voice.setdefault("bySynth", {})).get(synthName)
		if not isinstance(record, dict) or "baseline" not in record:
			record = new_voice_record(driver)
			voice["bySynth"][synthName] = record
			voice["enabled"] = True
			voice["engine"] = engine
			self.store.set_item(item_id, settings)
		self._voiceDriver = driver
		self._voiceControls = VoiceProfileControls(
			driver,
			voice_record_snapshot(record),
			lambda setting_id, value: self._voiceValueChanged(setting_id, value),
		)
		if self._voiceControls.settings:
			self._voiceControls.build(self.voicePanel, self.voicePanelSizer)
		else:
			self.voicePanelSizer.Add(
				wx.StaticText(self.voicePanel, label=_("This synthesizer exposes no editable settings.")), 0, wx.ALL, 4
			)
		self.voicePanel.Layout()

	def _voiceValueChanged(self, setting_id, value):
		item_id = self._currentItemId
		driver = self._voiceDriver
		if item_id is None or driver is None or self._loading:
			return
		settings = self.store.get_item(item_id)
		voice = settings.get("voice")
		if not isinstance(voice, dict):
			voice = {"enabled": True, "engine": self._currentEngine(), "bySynth": {}}
			settings["voice"] = voice
		synthName = get_synth_id(driver)
		record = voice.setdefault("bySynth", {}).setdefault(synthName, new_voice_record(driver))
		set_voice_record_value(record, driver, setting_id, value)
		voice["enabled"] = True
		self.store.set_item(item_id, settings)
		if setting_id in ("voice", "variant") and self._voiceControls is not None:
			self._voiceControls.snapshot = voice_record_snapshot(record)
			self._voiceControls.refresh_snapshot_values(skip_setting_id=setting_id)
		self._changed(item_id)

	def _changed(self, item_id):
		self._refreshItemLabels(item_id)
		self.resetItemButton.Enable(bool(self.store.get_item(item_id)))
		if callable(self._onChange):
			self._onChange()

	# -- sound events ---------------------------------------------------------------
	def _wavesDirectory(self):
		try:
			import globalVars
			return os.path.join(globalVars.appDir, "waves")
		except Exception:
			return ""

	def onBrowseSound(self, event):
		item_id = self._currentItemId
		if item_id is None:
			return
		current = self.store.get_item(item_id).get("sound", "")
		directory = os.path.dirname(current) if current else self._wavesDirectory()
		with wx.FileDialog(
			self,
			_("Choose a sound for {item}").format(item=self._itemsById[item_id].label),
			defaultDir=directory or "",
			wildcard=_("Wave files (*.wav)|*.wav"),
			style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
		) as dialog:
			if dialog.ShowModal() != wx.ID_OK:
				return
			path = dialog.GetPath()
		settings = self.store.get_item(item_id)
		settings["sound"] = path
		settings.setdefault("soundOnly", False)
		self.store.set_item(item_id, settings)
		self.soundPath.SetValue(path)
		self.playSoundButton.Enable(True)
		self.removeSoundButton.Enable(True)
		self.soundModeChoice.Enable(True)
		self._changed(item_id)
		self.browseSoundButton.SetFocus()

	def onPlaySound(self, event):
		path = self.soundPath.GetValue().strip()
		if not path:
			return
		if not os.path.isfile(path):
			wx.MessageBox(
				_("The sound file could not be found:\n{path}").format(path=path),
				_("Speech and Sound Schemes"),
				wx.OK | wx.ICON_WARNING,
				self,
			)
			return
		try:
			import nvwave
			nvwave.playWaveFile(path, asynchronous=True)
		except Exception:
			log.error("ClassicSpeech schemes: could not play %s", path, exc_info=True)

	def onRemoveSound(self, event):
		item_id = self._currentItemId
		if item_id is None:
			return
		settings = self.store.get_item(item_id)
		settings.pop("sound", None)
		settings.pop("soundOnly", None)
		self.store.set_item(item_id, settings)
		self.soundPath.SetValue("")
		self.playSoundButton.Disable()
		self.removeSoundButton.Disable()
		self.soundModeChoice.Disable()
		self._changed(item_id)
		self.browseSoundButton.SetFocus()

	def onSoundMode(self, event):
		item_id = self._currentItemId
		if item_id is None or self._loading:
			return
		settings = self.store.get_item(item_id)
		if not settings.get("sound"):
			return
		settings["soundOnly"] = self.soundModeChoice.GetSelection() == 1
		self.store.set_item(item_id, settings)
		self._changed(item_id)

	# -- voice events -----------------------------------------------------------
	def onVoiceToggled(self, event):
		item_id = self._currentItemId
		if item_id is None or self._loading:
			return
		enabled = self.voiceCheckBox.GetValue()
		settings = self.store.get_item(item_id)
		voice = settings.get("voice")
		if not isinstance(voice, dict):
			voice = {"enabled": enabled, "engine": "", "bySynth": {}}
			settings["voice"] = voice
		voice["enabled"] = enabled
		self.store.set_item(item_id, settings)
		self._loadSynthChoices(voice.get("engine", ""))
		self._rebuildVoiceControls()
		self._changed(item_id)
		self.Layout()

	def onSynthChanged(self, event):
		item_id = self._currentItemId
		if item_id is None or self._loading:
			return
		index = self.synthChoice.GetSelection()
		if 0 <= index < len(self._synthValues) and self._synthValues[index] is None:
			# "Other synthesizers..." discovers the installed synthesizers once.
			discover_synthesizers()
			self._loadSynthChoices("")
			self.synthChoice.SetFocus()
			return
		engine = self._currentEngine()
		settings = self.store.get_item(item_id)
		voice = settings.get("voice")
		if not isinstance(voice, dict):
			voice = {"enabled": True, "engine": "", "bySynth": {}}
			settings["voice"] = voice
		voice["engine"] = engine
		voice["enabled"] = True
		self.store.set_item(item_id, settings)
		self._rebuildVoiceControls()
		self._changed(item_id)
		self.Layout()
		self.synthChoice.SetFocus()

	def onPreviewVoice(self, event):
		item_id = self._currentItemId
		driver = self._voiceDriver
		if item_id is None or driver is None:
			return
		settings = self.store.get_item(item_id)
		record = ((settings.get("voice") or {}).get("bySynth") or {}).get(get_synth_id(driver))
		snapshot = voice_record_preview_snapshot(record)
		text = self._itemsById[item_id].label
		try:
			active = _active_driver()
			if active is not None and driver is not active:
				preview_with_loaded_synthesizer(driver, snapshot, text)
			else:
				preview_with_active_synthesizer(item_id, driver, snapshot, text)
		except Exception:
			log.error("ClassicSpeech schemes: voice preview failed", exc_info=True)

	def onResetItem(self, event):
		item_id = self._currentItemId
		if item_id is None:
			return
		if self.showSounds:
			self.store.clear_item(item_id)
		else:
			# Voice Profiles shows only voices, so keep a sound chosen in Speech and Sound Schemes.
			settings = self.store.get_item(item_id)
			settings.pop("voice", None)
			self.store.set_item(item_id, settings)
		self._showItem(item_id, self._currentCategoryKind)
		self._changed(item_id)
		self.tree.SetFocus()

	# -- custom catalog entries ---------------------------------------------------
	def onAddCustomEntry(self, kind):
		prompts = {
			"fonts": (_("Font name to add:"), _("Add font name"), ""),
			"fontSizes": (_("Font size in points to add (for example 13 or 10.5):"), _("Add font size"), ""),
			"styles": (_("Style name to add, as NVDA reports it (for example Heading 1 or Quote):"), _("Add style name"), ""),
			"classes": (_("Window class name to add:"), _("Add window class"), self._focusClassName),
		}
		prompt, title, default = prompts[kind]
		with wx.TextEntryDialog(self, prompt, title, value=default) as dialog:
			if dialog.ShowModal() != wx.ID_OK:
				return
			value = dialog.GetValue().strip()
		if kind == "fontSizes":
			value = schemeCatalog.normalize_font_size(value)
		if not value:
			return
		self.store.add_custom_entry(kind, value)
		item_id = schemeCatalog.custom_entry_item_id(kind, value)
		self.searchText.ChangeValue("")
		self.showChoice.SetSelection(SHOW_ALL)
		self.rebuildTree(select_item_id=item_id)
		if callable(self._onChange):
			self._onChange()
		self.tree.SetFocus()

	def onRemoveCustomEntry(self, event):
		data = self._selectedData()
		if not data or data[0] != "item" or not data[2]:
			return
		kind, item_id = data[2], data[1]
		for value in self.store.custom_entries().get(kind, []):
			if schemeCatalog.custom_entry_item_id(kind, value) == item_id:
				self.store.remove_custom_entry(kind, value)
				self.store.clear_item(item_id)
				break
		self._currentItemId = None
		self.rebuildTree()
		if callable(self._onChange):
			self._onChange()
		self.tree.SetFocus()

	# -- lifetime -------------------------------------------------------------------
	def cleanup(self):
		"""Unload synthesizers that were loaded only to edit their voices."""
		self._clearVoiceControls()
		for name, probe in list(self._probes.items()):
			try:
				probe.cancel()
			except Exception:
				pass
			try:
				probe.terminate()
			except Exception:
				log.debug("ClassicSpeech schemes: could not unload %s", name, exc_info=True)
		self._probes = {}


def _bypass_classic_speech_once():
	from .config_core import _get_running_classic_speech_plugin

	plugin = _get_running_classic_speech_plugin()
	if plugin is not None:
		try:
			plugin.processor._bypass_next_sequence = True
		except Exception:
			pass


def preview_with_active_synthesizer(item_id, driver, snapshot, text):
	"""Speak ``text`` with the working voice through a queue-safe profile trigger."""
	import config
	import speech

	_bypass_classic_speech_once()
	speech.cancelSpeech()
	if not snapshot:
		speech.speak([text])
		return
	from speech.commands import ConfigProfileTriggerCommand

	from ..voice_profile_runtime import make_voice_profile_overlay_trigger

	trigger = make_voice_profile_overlay_trigger(f"schemePreview:{item_id}", config.conf, driver, snapshot)
	speech.speak([ConfigProfileTriggerCommand(trigger, True), text, ConfigProfileTriggerCommand(trigger, False)])


def preview_with_loaded_synthesizer(driver, snapshot, text):
	"""Speak ``text`` directly through the synthesizer loaded for editing.

	That instance is private to the dialog, so its settings can be applied
	directly; NVDA's active synthesizer and speech queue are not switched.
	"""
	import speech

	speech.cancelSpeech()
	try:
		driver.cancel()
	except Exception:
		pass
	ordered = [setting_id for setting_id in ("voice", "variant") if setting_id in snapshot]
	ordered.extend(setting_id for setting_id in snapshot if setting_id not in ("voice", "variant"))
	for setting_id in ordered:
		try:
			setattr(driver, setting_id, snapshot[setting_id])
		except Exception:
			log.debug("ClassicSpeech schemes: preview could not set %s", setting_id, exc_info=True)
	driver.speak([text])
