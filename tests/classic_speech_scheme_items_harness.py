"""Every Speech and Sound Scheme item, against NVDA's own control types.

The tree view is built from NVDA's roles, states, landmarks and document
formatting, so it holds several hundred items. An item a user configures has to
do something: this harness loads NVDA master's real ``controlTypes`` so the
catalog is the one the user actually sees, and then checks every item twice.

* **Marked**: one of the producers ClassicSpeech uses while NVDA builds speech
  can emit that item id. An item whose voice applies to text or to a whole
  object must be emitted by a range or object producer, not only by an
  announcement label, because the announcement depends on NVDA's Document
  Formatting settings and may never be spoken.
* **Heard**: ``apply_schemes`` turns that marker into the voice and the sound
  the user configured. It is the Speech *and Sounds* Manager, so both are
  checked for every item.
"""
from __future__ import annotations

import builtins
import json
import sys
import tempfile
import types
import typing
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
	sys.path.insert(0, str(ROOT / "tests"))


def _install_real_control_types():
	"""Replace the stub ``controlTypes`` with NVDA master's own module.

	NVDA's roles and states are what the scheme catalog is built from, so the
	stub's short lists would hide most of the tree. NVDA's package is written
	for the Python NVDA ships; the two shims below are what an older Python
	needs to import it, and neither changes its behaviour.
	"""
	import classic_speech_core_harness as core_harness

	core_harness._install_nvda_stubs()
	import classic_speech_nvda_master_harness as nvda_harness

	if not hasattr(typing, "Self"):
		typing.Self = typing.Any
	if not hasattr(builtins, "_"):
		builtins._ = lambda text: text
	if not hasattr(builtins, "pgettext"):
		builtins.pgettext = lambda context, text: text
	for name in [n for n in sys.modules if n == "controlTypes" or n.startswith("controlTypes.")]:
		del sys.modules[name]
	source = str(nvda_harness.NVDA_SOURCE)
	if source not in sys.path:
		sys.path.insert(0, source)
	import controlTypes

	return nvda_harness, controlTypes


nvda_harness, controlTypes = _install_real_control_types()

import config  # noqa: E402
import speech  # noqa: E402,F401
from speech.commands import PitchCommand, RateCommand, VolumeCommand  # noqa: E402
import globalPluginHandler  # noqa: E402

Role = controlTypes.Role
State = controlTypes.State
OutputReason = controlTypes.OutputReason


class Setting:
	def __init__(self, setting_id):
		self.id = setting_id


class FakeSynth:
	name = "fakeSynth"
	supportedSettings = (Setting("voice"), Setting("variant"), Setting("rate"), Setting("pitch"), Setting("volume"))
	supportedCommands = frozenset({PitchCommand, RateCommand, VolumeCommand})

	def __init__(self):
		self.voice = "alice"
		self.variant = "standard"
		self.rate = 50
		self.pitch = 50
		self.volume = 80


SYNTH = FakeSynth()
_synth_driver_handler = types.ModuleType("synthDriverHandler")
_synth_driver_handler.getSynth = lambda: SYNTH
sys.modules["synthDriverHandler"] = _synth_driver_handler


class Field(dict):
	"""A control field, as NVDA hands one to ``getControlFieldSpeech``."""

	PRESCAT_LAYOUT = "layout"

	def getPresentationCategory(self, ancestors, formatConfig, reason=None, extraDetail=False):
		return self.get("presCat", "container")


class FakeObject:
	def __init__(self, name, role, states=(), windowClassName="Button"):
		self.name = name
		self.role = role
		self.states = set(states)
		self.windowClassName = windowClassName


#: One document format field per formatting item, as NVDA reports it.
FORMAT_ATTRS = {
	"fmt.bold": {"bold": True},
	"fmt.italic": {"italic": True},
	"fmt.underline": {"underline": True},
	"fmt.strikethrough": {"strikethrough": True},
	"fmt.doubleStrikethrough": {"strikethrough": "double"},
	"fmt.hidden": {"hidden": True},
	"fmt.superscript": {"text-position": controlTypes.TextPosition.SUPERSCRIPT},
	"fmt.subscript": {"text-position": controlTypes.TextPosition.SUBSCRIPT},
	"fmt.baseline": {"text-position": controlTypes.TextPosition.BASELINE},
	"fmt.strong": {"strong": True},
	"fmt.emphasised": {"emphasised": True},
	"fmt.marked": {"marked": True},
	"fmt.highlightColor": {"highlight-color": "yellow"},
	"fmt.style": {"style": "Quotation"},
	"fmt.style.default": {"style": None},
	"fmt.color": {"color": "red"},
	"fmt.backgroundColor": {"background-color": "blue"},
	"fmt.backgroundPattern": {"background-pattern": "diagonal"},
	"fmt.fontName": {"font-name": "Calibri"},
	"fmt.fontSize": {"font-size": "12pt"},
	"fmt.comment": {"comment": "note"},
	"fmt.bookmark": {"bookmark": True},
	"fmt.inserted": {"revision-insertion": True},
	"fmt.deleted": {"revision-deletion": True},
	"fmt.revised": {"revision": "Jo"},
	"fmt.spellingError": {"invalid-spelling": True},
	"fmt.grammarError": {"invalid-grammar": True},
	"fmt.align.left": {"text-align": controlTypes.TextAlign.LEFT},
	"fmt.align.center": {"text-align": controlTypes.TextAlign.CENTER},
	"fmt.align.right": {"text-align": controlTypes.TextAlign.RIGHT},
	"fmt.align.justify": {"text-align": controlTypes.TextAlign.JUSTIFY},
	"fmt.align.other": {"text-align": controlTypes.TextAlign.DISTRIBUTE},
	"fmt.verticalAlign": {"vertical-align": controlTypes.VerticalTextAlign.TOP},
	"fmt.page": {"page-number": "2"},
	"fmt.section": {"section-number": "3"},
	"fmt.textColumn": {"text-column-number": "1", "text-column-count": "2"},
	"fmt.sectionBreak": {"section-break": "new page section break"},
	"fmt.columnBreak": {"column-break": "column break"},
	"fmt.lineNumber": {"line-number": 4},
	"fmt.lineSpacing": {"line-spacing": "double"},
	"fmt.paragraphIndent": {"first-line-indent": 10},
	"fmt.linePrefix": {"line-prefix": "*"},
	"fmt.cellBorders": {"border-style": "solid"},
	"fmt.lineIndentation": {},
	"fmt.tableCellCoords": {},
	"fmt.tableHeaders": {},
}

#: Formatting NVDA only mentions when it stops, with the field it comes from.
FORMAT_OFF = {
	"fmt.bold.off": ({"bold": True}, {"bold": False}),
	"fmt.italic.off": ({"italic": True}, {"italic": False}),
	"fmt.underline.off": ({"underline": True}, {"underline": False}),
	"fmt.strikethrough.off": ({"strikethrough": True}, {"strikethrough": False}),
	"fmt.hidden.off": ({"hidden": True}, {"hidden": False}),
	"fmt.strong.off": ({"strong": True}, {"strong": False}),
	"fmt.emphasised.off": ({"emphasised": True}, {"emphasised": False}),
	"fmt.marked.off": ({"marked": True}, {"marked": False}),
	"fmt.highlightColor.off": ({"highlight-color": "yellow"}, {"highlight-color": None}),
	"fmt.inserted.off": ({"revision-insertion": True}, {"revision-insertion": False}),
	"fmt.deleted.off": ({"revision-deletion": True}, {"revision-deletion": False}),
	"fmt.revised.off": ({"revision": "Jo"}, {"revision": None}),
	"fmt.comment.off": ({"comment": "note"}, {"comment": None}),
	"fmt.bookmark.off": ({"bookmark": True}, {"bookmark": False}),
	"fmt.spellingError.off": ({"invalid-spelling": True}, {"invalid-spelling": False}),
	"fmt.grammarError.off": ({"invalid-grammar": True}, {"invalid-grammar": False}),
	"fmt.style.default": ({"style": "Quotation"}, {"style": None}),
}

#: A comment NVDA classifies; textInfos.CommentType is what it puts in the field.
import enum  # noqa: E402


class CommentType(enum.Enum):
	"""Mirrors ``textInfos.CommentType``; textInfos itself needs all of NVDA."""

	GENERAL = "general"
	DRAFT = "draft"
	RESOLVED = "resolved"


FORMAT_ATTRS["fmt.comment.draft"] = {"comment": CommentType.DRAFT}
FORMAT_ATTRS["fmt.comment.resolved"] = {"comment": CommentType.RESOLVED}


class _TreeObject:
	"""A tree view row, as NVDA exposes one to the speech hook."""

	def __init__(self, role_name, name, parent=None):
		self.role = getattr(controlTypes.Role, role_name, None) or types.SimpleNamespace(name=role_name)
		self.name = name
		self.parent = parent
		self.states = set()
		self.value = ""
		self.windowHandle = 4242
		self.IAccessibleChildID = 0
		self.treeInterceptor = None


class SchemeItemHarnessBase(unittest.TestCase):
	def setUp(self):
		nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
		config.conf["speech"] = {
			"fakeSynth": {"voice": "alice", "variant": "standard", "rate": 50, "pitch": 50, "volume": 80},
		}
		# NVDA's own state processor reads these while it labels states.
		config.conf.setdefault("presentation", {}).setdefault("reportMultiSelect", True)
		document_formatting = config.conf.setdefault("documentFormatting", {})
		document_formatting.setdefault("reportClickable", True)
		document_formatting.setdefault("reportLinkType", True)
		self.section = config.conf.profiles[0].setdefault("classicSpeech", {})
		self.module = nvda_harness._import_classic_speech_like_nvda()
		from globalPlugins._speech_core.schemes import catalog, labels, markers, runtime, store

		self.catalog = catalog
		self.labels = labels
		self.markers = markers
		self.runtime = runtime
		self.store = store
		store.invalidate_runtime_cache()
		runtime.reset_carried_state()
		runtime.clear_sound_cache()
		self.sound_dir = tempfile.TemporaryDirectory()
		self.addCleanup(self.sound_dir.cleanup)
		self.categories = catalog.build_categories()
		# NVDA's own sounds are not speech; classic_speech_nvda_sounds_harness covers them.
		self.items = {
			item_id: item
			for item_id, item in catalog.item_index(self.categories).items()
			if not catalog.is_nvda_sound_item(item_id)
		}

	def tearDown(self):
		globalPluginHandler.runningPlugins.clear()
		nvda_harness._reset_global_plugin_imports()

	def sound(self, name="beep.wav"):
		path = Path(self.sound_dir.name) / name
		path.write_bytes(b"RIFF")
		return str(path)

	def configure(self, items):
		data = {"enabled": True, "activeScheme": "Default", "schemes": {"Default": {"items": items}}}
		self.section["schemeData"] = json.dumps(data)
		self.store.invalidate_runtime_cache()

	# -- what ClassicSpeech would mark for one item -------------------------
	def _format_attrs(self, item_id):
		if item_id in FORMAT_ATTRS:
			return FORMAT_ATTRS[item_id]
		for prefix, key, suffix in (
			("fmt.fontSize.", "font-size", "pt"),
			("fmt.fontName.", "font-name", ""),
			("fmt.styleName.", "style", ""),
		):
			if item_id.startswith(prefix):
				return {key: item_id[len(prefix):] + suffix}
		return None

	def _control_field(self, item_id):
		if item_id.startswith("role.HEADING."):
			try:
				return Field(role=Role.HEADING, level=int(item_id.rsplit(".", 1)[1]), states=set())
			except ValueError:
				return None
		if item_id.startswith("landmark."):
			return Field(role=Role.LANDMARK, landmark=item_id[len("landmark."):], states=set())
		if item_id.startswith("role.") and item_id.count(".") == 1:
			member = getattr(Role, item_id[len("role."):], None)
			if member is not None:
				return Field(role=member, states=set(), name="Example")
		return None

	def range_items_for(self, item_id):
		"""Item ids ClassicSpeech marks on the text itself for this item."""
		attrs = self._format_attrs(item_id)
		if attrs:
			found = self.labels.format_range_items(attrs)
			if item_id in found:
				return found
		field = self._control_field(item_id)
		if field is not None:
			found = self.labels.element_range_items(field)
			if item_id in found:
				return found
		return None

	def object_items_for(self, item_id):
		"""Item ids ClassicSpeech marks on a whole object for this item."""
		if item_id == "object.unlabeledGraphic":
			found = self.labels.role_items(Role.GRAPHIC, name=None)
			return found if item_id in found else None
		if item_id.startswith("class."):
			return [item_id]
		if item_id.startswith("role.HEADING."):
			try:
				level = int(item_id.rsplit(".", 1)[1])
			except ValueError:
				return None
			found = self.labels.role_items(Role.HEADING, name="Example", level=level)
			return found if item_id in found else None
		if item_id.startswith("landmark."):
			found = self.labels.role_items(Role.LANDMARK, name="Example", landmark=item_id[len("landmark."):])
			return found if item_id in found else None
		if item_id.startswith("role.") and item_id.count(".") == 1:
			member = getattr(Role, item_id[len("role."):], None)
			if member is not None:
				found = self.labels.role_items(member, name="Example")
				return found if item_id in found else None
		if item_id.startswith("state."):
			return self._object_state_items(item_id)
		return None

	def _object_state_items(self, item_id):
		"""The object marker for an object that is (or is not) in this state."""
		member, negative = self._state_member(item_id)
		if member is None:
			return None
		if negative:
			# The absence of a state only means something in NVDA's own
			# announcement, so a negated item is marked there.
			return None
		found = self.labels.object_state_items({member})
		return found if item_id in found else None

	@staticmethod
	def _state_member(item_id):
		name = item_id[len("state."):]
		negative = name.endswith(".off")
		if negative:
			name = name[: -len(".off")]
		return getattr(State, name, None), negative

	@staticmethod
	def _state_scenarios(member, negative):
		"""Objects NVDA would report this state for (controlTypes.processAndLabelStates)."""
		if not negative:
			return [
				(Role.LINK, {member}, OutputReason.FOCUS),
				(Role.LISTITEM, {member}, OutputReason.FOCUS),
				(Role.UNKNOWN, {member}, OutputReason.FOCUS),
			]
		# NVDA speaks a negated state only where its absence means something.
		return {
			State.CHECKED: [(Role.CHECKBOX, set(), OutputReason.FOCUS)],
			State.PRESSED: [(Role.TOGGLEBUTTON, set(), OutputReason.FOCUS)],
			State.ON: [(Role.SWITCH, set(), OutputReason.FOCUS)],
			State.SELECTED: [
				(Role.LISTITEM, {State.SELECTABLE, State.FOCUSABLE}, OutputReason.FOCUS),
			],
			# Reported only when the object stops being a drop target or sorted.
			State.DROPTARGET: [(Role.LISTITEM, {State.FOCUSED}, OutputReason.CHANGE)],
			State.SORTED: [(Role.TABLECOLUMNHEADER, {State.FOCUSED}, OutputReason.CHANGE)],
		}.get(member, [(Role.UNKNOWN, set(), OutputReason.FOCUS)])

	def label_items_for(self, item_id):
		"""Item ids ClassicSpeech marks on NVDA's announcement for this item."""
		for old, new in self._format_label_tries(item_id):
			table = self.labels.format_field_label_table(new, old, extra_detail=False)
			for items in table.labels.values():
				if item_id in items:
					return list(items)
		field = self._control_field(item_id)
		if field is not None:
			table = self.labels.control_field_label_table(field, OutputReason.CARET)
			for items in table.labels.values():
				if item_id in items:
					return list(items)
		if item_id.startswith("state."):
			items = self._state_label_items(item_id)
			if items:
				return items
		if item_id in ("fmt.tableCellCoords", "fmt.tableHeaders"):
			table = self.labels.LabelTable()
			self.labels.add_table_cell_labels(table, {
				"rowNumber": 1, "columnNumber": 2, "cellCoordsText": "A1",
				"rowHeaderText": "Name", "columnHeaderText": "Value",
			})
			for items in table.labels.values():
				if item_id in items:
					return list(items)
		if item_id == "fmt.lineIndentation":
			# The indentation wrapper marks NVDA's indentation speech directly.
			return [item_id]
		return None

	def _format_label_tries(self, item_id):
		tries = []
		attrs = self._format_attrs(item_id)
		if attrs is not None:
			tries.append(({}, attrs))
		pair = FORMAT_OFF.get(item_id)
		if pair is not None:
			tries.append(pair)
		return tries

	def _state_label_items(self, item_id):
		member, negative = self._state_member(item_id)
		if member is None:
			return None
		changed = {State.DROPTARGET: {State.DROPTARGET}, State.SORTED: {State.SORTED_ASCENDING}}
		for role, states, reason in self._state_scenarios(member, negative):
			negative_states = set()
			if negative:
				negative_states = changed.get(member, {member}) if reason is OutputReason.CHANGE else {member}
			table = self.labels.LabelTable()
			self.labels.add_state_labels(
				table,
				role,
				states,
				reason,
				states=set() if negative else {member},
				negative_states=negative_states,
			)
			for items in table.labels.values():
				if item_id in items:
					return list(items)
		return None


def _voice(**overrides):
	return {
		"enabled": True,
		"engine": "",
		"bySynth": {
			"fakeSynth": {
				"baseline": {"voice": "alice", "variant": "standard", "rate": 50, "pitch": 50, "volume": 80},
				"overrides": dict(overrides),
			},
		},
	}


class SchemeItemCoverageTests(SchemeItemHarnessBase):
	"""Every item in the tree view can be marked."""

	def test_the_tree_view_is_built_from_nvdas_own_control_types(self):
		roles = next(category for category in self.categories if category.category_id == "roles")
		role_items = {item.item_id for item in roles.items}
		self.assertGreater(len(list(Role)), 100, "NVDA master's roles were not loaded")
		self.assertEqual(len(role_items), len(list(Role)))
		self.assertGreaterEqual(len(self.items), 300)

	def test_every_item_can_be_marked(self):
		missing = []
		for item_id in sorted(self.items):
			if not (
				self.range_items_for(item_id)
				or self.object_items_for(item_id)
				or self.label_items_for(item_id)
			):
				missing.append(item_id)
		self.assertEqual(missing, [], f"{len(missing)} items can never be marked: {missing}")

	def test_every_item_is_marked_where_its_voice_applies(self):
		"""An item whose voice covers text or an object needs a range or object mark.

		An announcement mark is not enough for those: NVDA only announces
		formatting and elements the user asked it to announce, so the item would
		do nothing for everybody else.
		"""
		wrong = []
		for item_id, item in sorted(self.items.items()):
			if item.voice_scope == self.catalog.SCOPE_TEXT and not self.range_items_for(item_id):
				wrong.append((item_id, "text scope, no range mark"))
			elif item.voice_scope == self.catalog.SCOPE_OBJECT and not self.object_items_for(item_id):
				wrong.append((item_id, "object scope, no object mark"))
		self.assertEqual(wrong, [], f"{len(wrong)} items: {wrong}")


class SchemeItemEffectTests(SchemeItemHarnessBase):
	"""Every item that is marked is also heard: its voice and its sound."""

	def _apply(self, marker, item_id, settings):
		self.configure({item_id: settings})
		sequence = [marker, "example text"]
		return self.runtime.apply_schemes(sequence)

	def _markers_for(self, item_id):
		"""The marker ClassicSpeech would put in NVDA's speech for this item."""
		markers = []
		range_items = self.range_items_for(item_id)
		if range_items is not None:
			if item_id.startswith(("role.", "landmark.")):
				markers.append(("element", self.markers.ElementStartMarker(1, range_items)))
			else:
				markers.append(("format", self.markers.FormatMarker(range_items)))
		object_items = self.object_items_for(item_id)
		if object_items is not None:
			markers.append(("object", self.markers.ObjectMarker(object_items)))
		label_items = self.label_items_for(item_id)
		if label_items is not None:
			markers.append(("label", self.markers.LabelMarker(label_items)))
		return markers

	def test_every_item_can_be_heard_as_a_voice(self):
		failures = []
		for item_id in sorted(self.items):
			for kind, marker in self._markers_for(item_id):
				output = self._apply(marker, item_id, {"voice": _voice(pitch=70)})
				if not any(isinstance(entry, PitchCommand) for entry in output):
					failures.append((item_id, kind, "no voice change"))
				if any(self.markers.is_marker(entry) for entry in output):
					failures.append((item_id, kind, "marker leaked"))
		self.assertEqual(failures, [], f"{len(failures)} failures: {failures[:20]}")

	def test_every_item_can_be_heard_as_a_voice_and_a_sound_together(self):
		"""Choosing both is the normal case: it is the Speech and Sounds Manager."""
		failures = []
		path = self.sound("both.wav")
		for item_id in sorted(self.items):
			for kind, marker in self._markers_for(item_id):
				output = self._apply(marker, item_id, {"voice": _voice(pitch=70), "sound": path})
				if not any(isinstance(entry, PitchCommand) for entry in output):
					failures.append((item_id, kind, "no voice change"))
				if not any(isinstance(entry, self.runtime.SchemeSoundCommand) for entry in output):
					failures.append((item_id, kind, "no sound"))
				if not any(isinstance(entry, str) and entry.strip() for entry in output):
					failures.append((item_id, kind, "text lost"))
				if any(self.markers.is_marker(entry) for entry in output):
					failures.append((item_id, kind, "marker leaked"))
		self.assertEqual(failures, [], f"{len(failures)} failures: {failures[:20]}")

	def test_a_sound_instead_of_speech_replaces_only_the_announcement(self):
		"""Sound instead of speech is an announcement choice, never a text one."""
		path = self.sound("instead.wav")
		settings = {"sound": path, "soundOnly": True}
		for item_id in sorted(self.items):
			for kind, marker in self._markers_for(item_id):
				output = self._apply(marker, item_id, settings)
				spoken = [entry for entry in output if isinstance(entry, str) and entry.strip()]
				sounds = [entry for entry in output if isinstance(entry, self.runtime.SchemeSoundCommand)]
				self.assertTrue(sounds, (item_id, kind))
				if kind == "label":
					# The marked announcement is replaced by the sound.
					self.assertEqual(spoken, [], (item_id, kind))
				else:
					# Formatted text and objects keep their words.
					self.assertEqual(spoken, ["example text"], (item_id, kind))

	def test_every_item_can_be_heard_as_a_sound(self):
		failures = []
		path = self.sound()
		for item_id in sorted(self.items):
			for kind, marker in self._markers_for(item_id):
				output = self._apply(marker, item_id, {"sound": path})
				if not any(isinstance(entry, self.runtime.SchemeSoundCommand) for entry in output):
					failures.append((item_id, kind, "no sound"))
		self.assertEqual(failures, [], f"{len(failures)} failures: {failures[:20]}")


class SchemeTreeIsReadableTests(SchemeItemHarnessBase):
	"""Every row of the manager's tree has to be readable by the person using it.

	The tree is built from NVDA's own vocabulary, so its rows are named "menu",
	"selected", "tree view", "list"... ClassicSpeech used to classify such a row
	label as the role or state it looks like and then drop it, leaving the user
	arrowing over silence. The row name is the focused object's own name and
	must always be spoken.
	"""

	#: How NVDA announces a tree view row: name first, then what it knows about it.
	ROW_SHAPES = (
		("{label}", "1 of 20", "level 2"),
		("{label}", "level 2", "1 of 20"),
		("{label}",),
		("{label}", "collapsed", "1 of 13", "level 1"),
		("{label} (sound, voice)", "1 of 20", "level 2"),
	)

	def _tree_row(self, label):
		import api

		from globalPlugins._speech_core import focus_ancestry

		dialog = _TreeObject("DIALOG", "Speech and Sound Schemes")
		tree = _TreeObject("TREEVIEW", "Scheme items", dialog)
		row = _TreeObject("TREEVIEWITEM", label, tree)
		api.getFocusObject = lambda: row
		api.getFocusAncestors = lambda: [dialog, tree]
		focus_ancestry.reset_cache()
		return row

	def _plugin(self):
		plugin = self.module.GlobalPlugin()
		globalPluginHandler.runningPlugins.append(plugin)
		self.addCleanup(plugin.terminate)
		plugin.processor._safe_selected_text = lambda _focus: ""
		return plugin

	def _tree_labels(self):
		labels = []
		for category in self.categories:
			labels.append(category.label)
			labels.extend(item.label for item in category.items)
		return labels

	def test_every_row_of_the_tree_is_spoken_when_arrowed_over(self):
		plugin = self._plugin()
		silent = []
		for label in self._tree_labels():
			self._tree_row(label)
			for shape in self.ROW_SHAPES:
				sequence = [part.format(label=label) for part in shape]
				plugin._menuHints.reset()
				output = plugin._filterSpeechSequence(list(sequence))
				spoken = " ".join(
					entry for entry in output if isinstance(entry, str) and entry.strip()
				).lower()
				if label.lower() not in spoken:
					silent.append((label, sequence, output))
		self.assertEqual(silent, [], f"{len(silent)} rows are not read: {silent[:10]}")

	def test_a_row_named_after_its_own_container_is_not_held_back(self):
		"""A row called "tree view" is a row, not the tree that holds it."""
		plugin = self._plugin()
		for label in ("tree view", "list", "combo box", "table", "tool bar", "tab control"):
			self._tree_row(label)
			plugin._menuHints.reset()
			output = plugin._filterSpeechSequence([label])
			self.assertIn(label, output, label)
			self.assertIsNone(plugin._pendingContainerSequence, label)


if __name__ == "__main__":
	unittest.main(verbosity=2)
