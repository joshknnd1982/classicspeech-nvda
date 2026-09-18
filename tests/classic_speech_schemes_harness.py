"""Speech and Sound Schemes regression harness.

Covers the scheme store, the item catalog, NVDA label identification, the
speech-builder tagging wrappers and the runtime that turns markers into sounds
and voice changes. NVDA modules are replaced by small fakes with the same
call shapes as NVDA 2026.2.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
import zipfile
from enum import Enum
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
	sys.path.insert(0, str(ROOT / "tests"))

import classic_speech_nvda_master_harness as nvda_harness  # noqa: E402
import config  # noqa: E402
import controlTypes  # noqa: E402
import globalPluginHandler  # noqa: E402
import speech  # noqa: E402
import speech.commands as commands  # noqa: E402


# ---------------------------------------------------------------------------
# Richer NVDA stubs for this harness
# ---------------------------------------------------------------------------

_ROLE_LABELS = {
	"BUTTON": "button", "LINK": "link", "HEADING": "heading", "GRAPHIC": "graphic",
	"LIST": "list", "LISTITEM": "list item", "EDITABLETEXT": "edit", "CHECKBOX": "check box",
	"UNKNOWN": "unknown", "LANDMARK": "landmark", "TABLE": "table", "DIALOG": "dialog",
	"COMBOBOX": "combo box", "MENUITEM": "menu item", "MENU": "menu", "MENUBAR": "menu bar",
	"TREEVIEW": "tree view", "TREEVIEWITEM": "tree view item", "TABLECELL": "cell",
	"TAB": "tab", "TABCONTROL": "tab control", "DOCUMENT": "document", "STATICTEXT": "text",
	"RADIOBUTTON": "radio button", "BLOCKQUOTE": "block quote", "REGION": "region",
}
_STATE_LABELS = {
	"CHECKED": "checked", "SELECTED": "selected", "VISITED": "visited", "COLLAPSED": "collapsed",
	"EXPANDED": "expanded", "PRESSED": "pressed", "INTERNAL_LINK": "same page", "CLICKABLE": "clickable",
	"HALFCHECKED": "half checked", "ON": "on", "DEFAULT": "default", "INDETERMINATE": "indeterminate",
}
_NEGATIVE_LABELS = {"CHECKED": "not checked", "SELECTED": "not selected", "PRESSED": "not pressed", "ON": "off"}


class Role(Enum):
	BUTTON = 1
	COMBOBOX = 2
	CHECKBOX = 3
	RADIOBUTTON = 4
	MENUITEM = 5
	EDITABLETEXT = 6
	STATICTEXT = 7
	LIST = 8
	LISTITEM = 9
	TREEVIEW = 10
	TREEVIEWITEM = 11
	MENU = 12
	MENUBAR = 13
	TABLE = 14
	TABLECELL = 15
	TAB = 16
	TABCONTROL = 17
	DIALOG = 18
	DOCUMENT = 19
	UNKNOWN = 20
	LINK = 21
	HEADING = 22
	GRAPHIC = 23
	LANDMARK = 24
	BLOCKQUOTE = 25
	REGION = 26

	@property
	def displayString(self):
		return _ROLE_LABELS[self.name]


class State(Enum):
	COLLAPSED = 1
	EXPANDED = 2
	CHECKED = 3
	HALFCHECKED = 4
	PRESSED = 5
	SELECTED = 6
	ON = 7
	INDETERMINATE = 8
	VISITED = 9
	INTERNAL_LINK = 10
	CLICKABLE = 11
	DEFAULT = 12

	@property
	def displayString(self):
		return _STATE_LABELS[self.name]

	@property
	def negativeDisplayString(self):
		return _NEGATIVE_LABELS.get(self.name, "not " + self.displayString)

	def __lt__(self, other):
		return self.value < other.value


def processAndLabelStates(role, states, reason, positiveStates=None, negativeStates=None, positiveStateLabelDict={}, negativeStateLabelDict={}):
	positive = set(positiveStates if positiveStates is not None else states)
	negative = set(negativeStates or ())
	if role == Role.CHECKBOX and State.CHECKED not in states and not negativeStates:
		negative.add(State.CHECKED)
	labels = []
	for state in sorted(positive | negative):
		if state in positive:
			labels.append(positiveStateLabelDict.get(state, state.displayString))
		else:
			labels.append(negativeStateLabelDict.get(state, state.negativeDisplayString))
	return labels


controlTypes.Role = Role
controlTypes.State = State
controlTypes.processAndLabelStates = processAndLabelStates
controlTypes.role._roleLabels = {member: member.displayString for member in Role}
controlTypes.state._stateLabels = {member: member.displayString for member in State}
controlTypes.state._negativeStateLabels = {State[name]: text for name, text in _NEGATIVE_LABELS.items()}


class SpeechCommand:
	pass


class BaseCallbackCommand(SpeechCommand):
	def run(self):
		return None


class WaveFileCommand(BaseCallbackCommand):
	def __init__(self, fileName):
		self.fileName = fileName

	def __repr__(self):
		return f"WaveFileCommand({self.fileName!r})"


class ConfigProfileTriggerCommand(SpeechCommand):
	def __init__(self, trigger, enter=True):
		self.trigger = trigger
		self.enter = enter

	def __repr__(self):
		return f"ConfigProfileTriggerCommand({getattr(self.trigger, 'spec', self.trigger)!r}, {self.enter})"


class _Prosody(SpeechCommand):
	settingName = ""

	def __init__(self, offset=0, multiplier=1):
		self.offset = offset
		self.multiplier = multiplier

	def __repr__(self):
		return f"{type(self).__name__}(offset={self.offset})"


class PitchCommand(_Prosody):
	settingName = "pitch"


class RateCommand(_Prosody):
	settingName = "rate"


class VolumeCommand(_Prosody):
	settingName = "volume"


commands.SpeechCommand = SpeechCommand
commands.BaseCallbackCommand = BaseCallbackCommand
commands.WaveFileCommand = WaveFileCommand
commands.ConfigProfileTriggerCommand = ConfigProfileTriggerCommand
commands.PitchCommand = PitchCommand
commands.RateCommand = RateCommand
commands.VolumeCommand = VolumeCommand


class Setting:
	def __init__(self, setting_id):
		self.id = setting_id


class FakeSynth:
	name = "fakeSynth"
	supportedSettings = (Setting("voice"), Setting("variant"), Setting("rate"), Setting("pitch"), Setting("volume"))

	def __init__(self):
		self.voice = "alice"
		self.variant = "standard"
		self.rate = 50
		self.pitch = 50
		self.volume = 80


SYNTH = FakeSynth()
synth_driver_handler = types.ModuleType("synthDriverHandler")
synth_driver_handler.getSynth = lambda: SYNTH
sys.modules["synthDriverHandler"] = synth_driver_handler

say_all_state = {"running": False}
speech.sayAll.SayAllHandler = types.SimpleNamespace(isRunning=lambda: say_all_state["running"])


def _voice_record(**overrides):
	baseline = {"voice": "alice", "variant": "standard", "rate": 50, "pitch": 50, "volume": 80}
	return {"baseline": baseline, "overrides": dict(overrides)}


class SchemeHarnessBase(unittest.TestCase):
	def setUp(self):
		nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
		config.conf["speech"] = {"fakeSynth": {"voice": "alice", "variant": "standard", "rate": 50, "pitch": 50, "volume": 80}}
		self.section = config.conf.profiles[0].setdefault("classicSpeech", {})
		self.module = nvda_harness._import_classic_speech_like_nvda()
		from globalPlugins._speech_core.schemes import catalog, labels, markers, runtime, store, tagging

		self.catalog = catalog
		self.labels = labels
		self.markers = markers
		self.runtime = runtime
		self.store = store
		self.tagging = tagging
		store.invalidate_runtime_cache()
		runtime.reset_carried_state()
		runtime.clear_sound_cache()
		say_all_state["running"] = False
		self.sound_dir = tempfile.TemporaryDirectory()
		self.addCleanup(self.sound_dir.cleanup)

	def tearDown(self):
		globalPluginHandler.runningPlugins.clear()
		speech.extensions.filter_speechSequence.callbacks.clear()
		nvda_harness._reset_global_plugin_imports()

	def sound(self, name="beep.wav"):
		path = Path(self.sound_dir.name) / name
		path.write_bytes(b"RIFF")
		return str(path)

	def configure(self, items, enabled=True, **extra):
		data = {"enabled": enabled, "activeScheme": "Default", "schemes": {"Default": {"items": items}}}
		data.update(extra)
		self.section["schemeData"] = json.dumps(data)
		self.store.invalidate_runtime_cache()


# ---------------------------------------------------------------------------
# Store and catalog
# ---------------------------------------------------------------------------

class SchemeStoreTests(SchemeHarnessBase):
	def test_empty_data_has_one_enabled_default_scheme(self):
		data = self.store.load_scheme_data("{}")
		self.assertTrue(data["enabled"])
		self.assertEqual(data["activeScheme"], "Default")
		self.assertEqual(data["schemes"], {"Default": {"items": {}}})
		self.assertEqual(self.store.load_scheme_data("not json")["activeScheme"], "Default")

	def test_unconfigured_items_are_dropped_and_disabled_voices_kept(self):
		data = self.store.load_scheme_data({
			"schemes": {"Default": {"items": {
				"role.LINK": {},
				"role.BUTTON": {"voice": {"enabled": False, "bySynth": {"fakeSynth": _voice_record(pitch=70)}}},
			}}},
		})
		items = data["schemes"]["Default"]["items"]
		self.assertNotIn("role.LINK", items)
		self.assertFalse(items["role.BUTTON"]["voice"]["enabled"])
		self.assertFalse(self.store.item_is_configured(items["role.BUTTON"]))

	def test_apply_and_cancel_are_transactional(self):
		section = {"schemeData": "{}"}
		editor = self.store.SchemeStore(section)
		editor.set_item("fmt.bold", {"sound": "C:/bold.wav", "soundOnly": True})
		self.assertTrue(editor.is_dirty())
		editor.apply()
		editor.mark_applied()
		saved = json.loads(section["schemeData"])
		self.assertEqual(saved["schemes"]["Default"]["items"]["fmt.bold"], {"sound": "C:/bold.wav", "soundOnly": True})
		editor.set_item("fmt.italic", {"sound": "C:/italic.wav"})
		editor.cancel()
		self.assertNotIn("fmt.italic", json.loads(section["schemeData"])["schemes"]["Default"]["items"])
		self.assertEqual(editor.configured_item_ids(), {"fmt.bold"})

	def test_named_schemes_can_be_added_renamed_deleted_and_cycled(self):
		section = {"schemeData": "{}"}
		editor = self.store.SchemeStore(section)
		editor.set_item("role.LINK", {"sound": "C:/link.wav"})
		name = editor.add_scheme("Proofreading", copy_from="Default")
		self.assertEqual(name, "Proofreading")
		self.assertEqual(editor.active_scheme, "Proofreading")
		self.assertIn("role.LINK", editor.configured_item_ids())
		self.assertEqual(editor.add_scheme("Proofreading"), "Proofreading 2")
		self.assertEqual(editor.rename_scheme("Proofreading 2", "Web"), "Web")
		self.assertTrue(editor.delete_scheme("Web"))
		self.assertFalse(editor.delete_scheme("Nope"))
		editor.set_active_scheme("Default")
		editor.apply()
		self.section["schemeData"] = section["schemeData"]
		self.assertEqual(self.store.cycle_active_scheme(), "Proofreading")
		self.assertEqual(self.store.cycle_active_scheme(), "Default")

	def test_runtime_cache_follows_the_stored_json(self):
		self.configure({"role.LINK": {"sound": "C:/link.wav"}})
		first = self.store.runtime_data()
		self.assertTrue(first.enabled)
		self.assertIn("role.LINK", self.store.active_items())
		self.configure({"role.LINK": {"sound": "C:/link.wav"}}, enabled=False)
		self.assertEqual(self.store.active_items(), {})
		self.assertTrue(self.store.set_schemes_enabled(True))
		self.assertIn("role.LINK", self.store.active_items())

	def test_voice_only_reset_keeps_a_sound_the_panel_does_not_show(self):
		from globalPlugins._speech_core.settings import schemes_panel

		editor = self.store.SchemeStore({"schemeData": "{}"})
		sound = self.sound()
		voice = {"enabled": True, "engine": "", "bySynth": {"fakeSynth": _voice_record(pitch=70)}}
		editor.set_item("fmt.bold", {"sound": sound, "voice": voice})
		panel = types.SimpleNamespace(
			_currentItemId="fmt.bold",
			_currentCategoryKind=None,
			showSounds=False,
			store=editor,
			_showItem=lambda *args: None,
			_changed=lambda *args: None,
			tree=types.SimpleNamespace(SetFocus=lambda: None),
		)
		# Voice Profiles shows only voices: its Reset this item keeps the scheme sound.
		schemes_panel.SchemeItemsPanel.onResetItem(panel, None)
		self.assertEqual(editor.get_item("fmt.bold"), {"sound": sound, "soundOnly": False})
		# Speech and Sound Schemes shows both, and resets both.
		editor.set_item("fmt.bold", {"sound": sound, "voice": voice})
		panel.showSounds = True
		schemes_panel.SchemeItemsPanel.onResetItem(panel, None)
		self.assertEqual(editor.get_item("fmt.bold"), {})


class SchemeCatalogTests(SchemeHarnessBase):
	def test_catalog_lists_every_role_state_and_formatting_group(self):
		categories = self.catalog.build_categories({"fonts": ["Georgia"], "fontSizes": ["13"], "classes": ["Button"]}, ("Arial",))
		ids = {item.item_id for category in categories for item in category.items}
		for role in Role:
			self.assertIn(f"role.{role.name}", ids)
		for state in State:
			self.assertIn(f"state.{state.name}", ids)
		self.assertIn("state.CHECKED.off", ids)
		for item_id in ("fmt.bold", "fmt.italic", "fmt.underline", "fmt.spellingError", "fmt.page",
				"fmt.lineIndentation", "fmt.tableCellCoords", "role.HEADING.3", "landmark.main",
				"object.unlabeledGraphic", "fmt.fontName.arial", "fmt.fontName.georgia",
				"fmt.fontSize.13", "class.Button"):
			self.assertIn(item_id, ids)
		labels = [category.label for category in categories]
		self.assertEqual(len(labels), len(set(labels)))
		formatting = [category.category_id for category in categories if category.formatting]
		self.assertEqual(formatting[0], "font")
		self.assertNotIn("roles", formatting)

	def test_font_sizes_are_numeric_and_sorted(self):
		self.assertEqual(self.catalog.normalize_font_size("12 pt"), "12")
		self.assertEqual(self.catalog.normalize_font_size("10.50pt"), "10.5")
		self.assertEqual(self.catalog.normalize_font_size("small"), "")
		sizes = [category for category in self.catalog.build_categories() if category.category_id == "fontSizes"][0]
		values = [float(item.item_id.split(".", 2)[2]) for item in sizes.items]
		self.assertEqual(values, sorted(values))


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

class SchemeLabelTests(SchemeHarnessBase):
	def test_format_labels_identify_nvda_announcements(self):
		table = self.labels.format_field_label_table(
			{"bold": True, "font-name": "Arial", "font-size": "12 pt", "invalid-spelling": True, "page-number": 4},
			{},
		)
		self.assertEqual(table.get("bold"), ("fmt.bold",))
		self.assertEqual(table.get("no bold"), ("fmt.bold.off",))
		self.assertEqual(table.get("Arial"), ("fmt.fontName.arial", "fmt.fontName"))
		self.assertEqual(table.get("12 pt"), ("fmt.fontSize.12", "fmt.fontSize"))
		self.assertEqual(table.get("spelling error"), ("fmt.spellingError",))
		self.assertEqual(table.get("page 4"), ("fmt.page",))
		self.assertIsNone(table.get("ordinary document text"))

	def test_named_styles_are_labelled_and_used_for_text(self):
		table = self.labels.format_field_label_table({"style": "Heading 1"}, {})
		self.assertEqual(table.get("style Heading 1"), ("fmt.styleName.heading 1", "fmt.style"))
		self.assertIn("fmt.styleName.heading 1", self.labels.format_range_items({"style": "Heading 1"}))
		categories = self.catalog.build_categories({"styles": ["Heading 1"]})
		styles = [category for category in categories if category.category_id == "styles"][0]
		self.assertEqual([item.item_id for item in styles.items], ["fmt.styleName.heading 1"])
		self.assertTrue(styles.formatting)

	def test_format_range_items_are_most_specific_first(self):
		items = self.labels.format_range_items(
			{"heading-level": 2, "bold": True, "italic": True, "font-name": "Arial", "font-size": "12 pt"}
		)
		self.assertEqual(
			items,
			["role.HEADING.2", "role.HEADING", "fmt.bold", "fmt.italic", "fmt.fontName.arial", "fmt.fontSize.12"],
		)

	def test_control_field_labels_cover_heading_level_and_states(self):
		table = self.labels.control_field_label_table(
			{"role": Role.HEADING, "level": 2, "states": set()}, None
		)
		self.assertEqual(table.get("heading"), ("role.HEADING.2", "role.HEADING"))
		self.assertEqual(table.get("level 2"), ("role.HEADING.2", "role.HEADING"))
		links = self.labels.control_field_label_table({"role": Role.LINK, "states": {State.VISITED}}, None)
		self.assertEqual(links.get("visited"), ("state.VISITED",))
		self.assertEqual(links.get("link"), ("role.LINK",))

	def test_negative_states_are_identified_through_nvda_label_order(self):
		table = self.labels.properties_label_table({"role": Role.CHECKBOX, "states": set(), "_states": set()}, None)
		self.assertEqual(table.get("check box"), ("role.CHECKBOX",))
		self.assertEqual(table.get("not checked"), ("state.CHECKED.off",))

	def test_unlabeled_graphics_are_identified(self):
		self.assertEqual(self.labels.role_items(Role.GRAPHIC, name=""), ["object.unlabeledGraphic", "role.GRAPHIC"])
		self.assertEqual(self.labels.role_items(Role.GRAPHIC, name="Logo"), ["role.GRAPHIC"])


# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------

class SchemeRuntimeTests(SchemeHarnessBase):
	def test_disabled_schemes_strip_markers_and_keep_native_sequences(self):
		native = ["Home", "link"]
		self.assertIs(self.runtime.apply_schemes(native), native)
		marked = [self.markers.LabelMarker(["role.LINK"]), "link"]
		self.assertEqual(self.runtime.apply_schemes(marked), ["link"])

	def test_label_sound_plays_before_the_announcement(self):
		path = self.sound("link.wav")
		self.configure({"role.LINK": {"sound": path}})
		output = self.runtime.apply_schemes(["Home", self.markers.LabelMarker(["role.LINK"]), "link"])
		self.assertEqual(output[0], "Home")
		self.assertIsInstance(output[1], self.runtime.SchemeSoundCommand)
		self.assertEqual(output[1].fileName, path)
		self.assertEqual(output[2], "link")

	def test_sound_instead_of_speech_removes_only_the_announcement(self):
		self.configure({"role.LINK": {"sound": self.sound(), "soundOnly": True}})
		output = self.runtime.apply_schemes(["Home", self.markers.LabelMarker(["role.LINK"]), "link"])
		self.assertEqual([entry for entry in output if isinstance(entry, str)], ["Home"])
		self.assertTrue(any(isinstance(entry, self.runtime.SchemeSoundCommand) for entry in output))

	def test_object_sound_plays_once_and_still_replaces_the_role_word(self):
		self.configure({"role.BUTTON": {"sound": self.sound(), "soundOnly": True}})
		output = self.runtime.apply_schemes([
			self.markers.ObjectMarker(["role.BUTTON"]), "OK", self.markers.LabelMarker(["role.BUTTON"]), "button",
		])
		sounds = [entry for entry in output if isinstance(entry, self.runtime.SchemeSoundCommand)]
		self.assertEqual(len(sounds), 1)
		self.assertEqual([entry for entry in output if isinstance(entry, str)], ["OK"])

	def test_missing_sound_file_is_ignored(self):
		self.configure({"role.LINK": {"sound": str(Path(self.sound_dir.name) / "missing.wav"), "soundOnly": True}})
		output = self.runtime.apply_schemes([self.markers.LabelMarker(["role.LINK"]), "link"])
		self.assertEqual(output, ["link"])

	def test_prosody_voice_applies_to_formatted_text_only(self):
		self.configure({"fmt.bold": {"voice": {"enabled": True, "bySynth": {"fakeSynth": _voice_record(pitch=70)}}}})
		output = self.runtime.apply_schemes([
			"plain ", self.markers.FormatMarker(["fmt.bold"]), "strong words", self.markers.FormatMarker([]), " plain again",
		])
		kinds = [type(entry).__name__ if not isinstance(entry, str) else entry for entry in output]
		self.assertEqual(kinds, ["plain ", "PitchCommand", "strong words", "PitchCommand", " plain again"])
		self.assertEqual(output[1].offset, 20)
		self.assertEqual(output[3].offset, 0)

	def test_voice_or_variant_change_uses_a_profile_trigger(self):
		self.configure({"role.HEADING": {"voice": {"enabled": True, "bySynth": {"fakeSynth": _voice_record(variant="deep")}}}})
		created = []
		from globalPlugins._speech_core import voice_profile_runtime

		original = voice_profile_runtime.make_voice_profile_overlay_trigger
		voice_profile_runtime.make_voice_profile_overlay_trigger = (
			lambda profile_id, manager, driver, snapshot, profile_factory=None: created.append((profile_id, snapshot)) or types.SimpleNamespace(spec=profile_id)
		)
		try:
			output = self.runtime.apply_schemes([self.markers.LabelMarker(["role.HEADING"]), "heading", "Intro"])
		finally:
			voice_profile_runtime.make_voice_profile_overlay_trigger = original
		# Only the marked announcement is in the heading voice; unmarked text
		# after it stays in the normal voice.
		self.assertIsInstance(output[0], ConfigProfileTriggerCommand)
		self.assertTrue(output[0].enter)
		self.assertEqual(output[1], "heading")
		self.assertIsInstance(output[2], ConfigProfileTriggerCommand)
		self.assertFalse(output[2].enter)
		self.assertIs(output[0].trigger, output[2].trigger)
		self.assertEqual(output[3:], ["Intro"])
		self.assertEqual(created[0][0], "scheme:role.HEADING")
		self.assertEqual(created[0][1]["variant"], "deep")

	def test_another_synthesizer_uses_a_cross_synth_trigger(self):
		self.configure({"role.LINK": {"voice": {"enabled": True, "engine": "espeak", "bySynth": {
			"espeak": {"baseline": {"voice": "en-us", "rate": 40}, "overrides": {"pitch": 60}},
		}}}})
		output = self.runtime.apply_schemes([self.markers.LabelMarker(["role.LINK"]), "link"])
		from globalPlugins._speech_core.voice_profile_trigger import CrossSynthProfileTrigger

		self.assertIsInstance(output[0].trigger, CrossSynthProfileTrigger)
		self.assertEqual(output[0].trigger.spec, "classicSpeech:scheme:role.LINK:espeak")
		self.assertEqual(output[0].trigger._settings, {"voice": "en-us", "pitch": 60})

	def test_cross_synth_trigger_pushes_and_pops_an_in_memory_profile(self):
		from globalPlugins._speech_core.voice_profile_trigger import CrossSynthProfileTrigger

		refreshed = []
		manager = types.SimpleNamespace(profiles=[{"speech": {"synth": "fakeSynth"}}])
		manager._handleProfileSwitch = lambda shouldNotify=True: refreshed.append(shouldNotify)
		trigger = CrossSynthProfileTrigger("role.LINK", "espeak", {"voice": "en-us"}, config_manager=manager, profile_factory=dict)
		trigger.enter()
		self.assertEqual(manager.profiles[-1]["speech"], {"synth": "espeak", "espeak": {"voice": "en-us"}})
		trigger.exit()
		self.assertEqual(len(manager.profiles), 1)
		self.assertEqual(refreshed, [False, False])

	def test_element_voice_follows_start_and_end_markers(self):
		self.configure({"role.LINK": {"voice": {"enabled": True, "bySynth": {"fakeSynth": _voice_record(rate=70)}}}})
		output = self.runtime.apply_schemes([
			"Click ", self.markers.ElementStartMarker(7, ["role.LINK"]), "here", self.markers.ElementEndMarker(7), " to continue",
		])
		kinds = [type(entry).__name__ if not isinstance(entry, str) else entry for entry in output]
		self.assertEqual(kinds, ["Click ", "RateCommand", "here", "RateCommand", " to continue"])

	def test_text_start_restores_containing_elements_and_resets_state(self):
		self.configure({"role.BLOCKQUOTE": {"voice": {"enabled": True, "bySynth": {"fakeSynth": _voice_record(volume=60)}}}})
		output = self.runtime.apply_schemes([
			self.markers.FormatMarker(["fmt.bold"]),
			self.markers.TextStartMarker([(1, ("role.BLOCKQUOTE",))]),
			"quoted line",
		])
		kinds = [type(entry).__name__ if not isinstance(entry, str) else entry for entry in output]
		self.assertEqual(kinds, ["VolumeCommand", "quoted line", "VolumeCommand"])

	def test_say_all_carries_formatting_across_a_sentence_split(self):
		self.configure({"fmt.italic": {"voice": {"enabled": True, "bySynth": {"fakeSynth": _voice_record(pitch=30)}}}})
		say_all_state["running"] = True
		first = self.runtime.apply_schemes([self.markers.TextStartMarker(), self.markers.FormatMarker(["fmt.italic"]), "One sentence."])
		second = self.runtime.apply_schemes([" still italic", self.markers.TextStartMarker(), "next line"])
		self.assertEqual(type(first[0]).__name__, "PitchCommand")
		self.assertEqual([type(entry).__name__ if not isinstance(entry, str) else entry for entry in second],
			["PitchCommand", " still italic", "PitchCommand", "next line"])
		say_all_state["running"] = False
		self.runtime.apply_schemes(["done"])
		self.assertIsNone(self.runtime._carried_state)

	def test_profile_triggers_in_the_sequence_disable_inline_prosody(self):
		self.configure({"fmt.bold": {"voice": {"enabled": True, "bySynth": {"fakeSynth": _voice_record(pitch=70)}}}})
		outer = ConfigProfileTriggerCommand(types.SimpleNamespace(spec="outer"), True)
		from globalPlugins._speech_core import voice_profile_runtime

		original = voice_profile_runtime.make_voice_profile_overlay_trigger
		voice_profile_runtime.make_voice_profile_overlay_trigger = lambda *args, **kwargs: types.SimpleNamespace(spec="scheme")
		try:
			output = self.runtime.apply_schemes([outer, self.markers.FormatMarker(["fmt.bold"]), "bold"])
		finally:
			voice_profile_runtime.make_voice_profile_overlay_trigger = original
		self.assertFalse(any(isinstance(entry, PitchCommand) for entry in output))
		self.assertEqual(sum(isinstance(entry, ConfigProfileTriggerCommand) for entry in output), 3)


# ---------------------------------------------------------------------------
# Tagging wrappers
# ---------------------------------------------------------------------------

def _install_fake_speech_builders():
	speech_module = types.ModuleType("speech.speech")

	def getPropertiesSpeech(reason=None, **values):
		output = []
		if values.get("name"):
			output.append(values["name"])
		if "role" in values:
			output.append(values["role"].displayString)
		states = values.get("states")
		if states is not None:
			role = values.get("role", values.get("_role", Role.UNKNOWN))
			output.extend(processAndLabelStates(role, values.get("_states", states), reason, states, values.get("negativeStates", set())))
		return output

	def getObjectPropertiesSpeech(obj, reason=None, _prefixSpeechCommand=None, **allowed):
		return speech_module.getPropertiesSpeech(reason=reason, name=obj.name, role=obj.role, states=set(obj.states), _states=set(obj.states))

	def getObjectSpeech(obj, reason=None, _prefixSpeechCommand=None):
		return speech_module.getObjectPropertiesSpeech(obj, reason)

	def speakObject(obj, reason=None, _prefixSpeechCommand=None, priority=None):
		speech_module.spoken.append(speech_module.getObjectSpeech(obj, reason))

	def speakObjectProperties(obj, reason=None, _prefixSpeechCommand=None, priority=None, **allowed):
		speech_module.spoken.append(speech_module.getObjectPropertiesSpeech(obj, reason, **allowed))

	def getControlFieldSpeech(attrs, ancestorAttrs, fieldType, formatConfig=None, extraDetail=False, reason=None):
		if fieldType in ("start_relative", "start_addedToControlFieldStack"):
			roleSequence = speech_module.getPropertiesSpeech(reason=reason, role=attrs["role"])
			stateSequence = speech_module.getPropertiesSpeech(reason=reason, states=attrs.get("states", set()), _role=attrs["role"])
			output = stateSequence + roleSequence
			if attrs.get("level"):
				output.append(f"level {attrs['level']}")
			return output
		return []

	def getFormatFieldSpeech(attrs, attrsCache=None, formatConfig=None, reason=None, unit=None, extraDetail=False, initialFormat=False):
		old = attrsCache if attrsCache is not None else {}
		output = []
		if attrs.get("font-name") and attrs.get("font-name") != old.get("font-name"):
			output.append(attrs["font-name"])
		if bool(attrs.get("bold")) != bool(old.get("bold")) and (attrs.get("bold") or "bold" in old):
			output.append("bold" if attrs.get("bold") else "no bold")
		if attrsCache is not None:
			attrsCache.clear()
			attrsCache.update(attrs)
		return output

	def getIndentationSpeech(indentation, formatConfig):
		return [f"{len(indentation)} space"] if indentation else []

	def getTextInfoSpeech(info, useCache=True, formatConfig=None, unit=None, reason=None, _prefixSpeechCommand=None, onlyInitialFields=False, suppressBlanks=False):
		sequence = []
		cache = {}
		for field in info.initialFields:
			sequence.extend(speech.getControlFieldSpeech(field, [], "start_addedToControlFieldStack", formatConfig, False, reason))
		sequence.extend(speech_module.getIndentationSpeech(info.indentation, formatConfig))
		for command in info.commands:
			kind = command[0]
			if kind == "text":
				sequence.append(command[1])
			elif kind == "format":
				sequence.extend(speech.getFormatFieldSpeech(attrs=command[1], attrsCache=cache, formatConfig=formatConfig, reason=reason, unit=unit))
			elif kind == "start":
				sequence.extend(speech.getControlFieldSpeech(command[1], [], "start_relative", formatConfig, False, reason))
			elif kind == "end":
				sequence.extend(speech.getControlFieldSpeech(command[1], [], "end_relative", formatConfig, False, reason))
		yield sequence
		return True

	speech_module.spoken = []
	for function in (
		getPropertiesSpeech, getObjectPropertiesSpeech, getObjectSpeech, speakObject, speakObjectProperties,
		getControlFieldSpeech, getFormatFieldSpeech, getIndentationSpeech, getTextInfoSpeech,
	):
		setattr(speech_module, function.__name__, function)
		setattr(speech, function.__name__, function)
	speech.speech = speech_module
	sys.modules["speech.speech"] = speech_module
	return speech_module


class Field(dict):
	PRESCAT_LAYOUT = "layout"

	def getPresentationCategory(self, ancestors, formatConfig, reason=None, extraDetail=False):
		return self.get("presCat", "container")


class FakeObject:
	def __init__(self, name, role, states=(), windowClassName="Button"):
		self.name = name
		self.role = role
		self.states = set(states)
		self.windowClassName = windowClassName


class SchemeTaggingTests(SchemeHarnessBase):
	def setUp(self):
		super().setUp()
		self.speech_module = _install_fake_speech_builders()
		self.tagger = self.tagging.SchemeTagger(is_active=lambda: True)
		self.tagger.install()
		self.addCleanup(self.tagger.uninstall)

	def test_object_speech_is_marked_only_while_nvda_speaks_it(self):
		self.configure({
			"role.CHECKBOX": {"sound": self.sound()},
			"state.CHECKED.off": {"sound": self.sound("off.wav")},
			"class.Button": {"sound": self.sound("class.wav")},
		})
		obj = FakeObject("Remember me", Role.CHECKBOX)
		speech.speakObject(obj)
		spoken = self.speech_module.spoken[-1]
		self.assertIsInstance(spoken[0], self.markers.ObjectMarker)
		self.assertEqual(spoken[0].items, ("class.Button", "role.CHECKBOX"))
		labels = [(entry.items, spoken[index + 1]) for index, entry in enumerate(spoken) if isinstance(entry, self.markers.LabelMarker)]
		self.assertEqual(labels, [(("role.CHECKBOX",), "check box"), (("state.CHECKED.off",), "not checked")])
		# The spelled/copied NVDA+Tab result builds speech without speaking it.
		self.assertEqual(speech.getObjectSpeech(obj), ["Remember me", "check box", "not checked"])

	def test_text_speech_marks_formatting_elements_and_indentation(self):
		self.configure({
			"fmt.bold": {"sound": self.sound(), "voice": {"enabled": True, "bySynth": {"fakeSynth": _voice_record(pitch=70)}}},
			"role.HEADING.2": {"voice": {"enabled": True, "bySynth": {"fakeSynth": _voice_record(rate=60)}}},
			"fmt.lineIndentation": {"sound": self.sound("indent.wav")},
		})
		heading = Field(role=Role.HEADING, level=2, states=set())
		info = types.SimpleNamespace(
			initialFields=[heading],
			indentation="    ",
			commands=[("format", {"bold": True}), ("text", "Title "), ("format", {"bold": False}), ("text", "rest")],
		)
		sequence = next(speech.getTextInfoSpeech(info))
		self.assertIsInstance(sequence[0], self.markers.TextStartMarker)
		self.assertEqual(sequence[0].elements, ((id(heading), ("role.HEADING.2",)),))
		label_targets = [sequence[index + 1] for index, entry in enumerate(sequence) if isinstance(entry, self.markers.LabelMarker)]
		self.assertEqual(label_targets, ["heading", "level 2", "4 space", "bold"])
		formats = [entry.items for entry in sequence if isinstance(entry, self.markers.FormatMarker)]
		self.assertEqual(formats, [("fmt.bold",), ()])

	def test_relative_elements_get_start_and_end_markers(self):
		self.configure({"role.LINK": {"voice": {"enabled": True, "bySynth": {"fakeSynth": _voice_record(rate=70)}}}})
		link = Field(role=Role.LINK, states=set())
		info = types.SimpleNamespace(initialFields=[], indentation="", commands=[("text", "Go "), ("start", link), ("text", "home"), ("end", link)])
		sequence = next(speech.getTextInfoSpeech(info))
		starts = [entry for entry in sequence if isinstance(entry, self.markers.ElementStartMarker)]
		ends = [entry for entry in sequence if isinstance(entry, self.markers.ElementEndMarker)]
		self.assertEqual([(entry.key, entry.items) for entry in starts], [(id(link), ("role.LINK",))])
		self.assertEqual([entry.key for entry in ends], [id(link)])

	def test_formatting_report_outside_text_speech_is_unchanged(self):
		self.configure({"fmt.bold": {"sound": self.sound()}})
		self.assertEqual(speech.getFormatFieldSpeech(attrs={"bold": True}, attrsCache={}), ["bold"])

	def test_nothing_is_marked_when_no_item_is_configured(self):
		self.configure({})
		obj = FakeObject("OK", Role.BUTTON)
		speech.speakObject(obj)
		self.assertEqual(self.speech_module.spoken[-1], ["OK", "button"])
		info = types.SimpleNamespace(initialFields=[], indentation="", commands=[("format", {"bold": True}), ("text", "x")])
		self.assertEqual(next(speech.getTextInfoSpeech(info)), ["bold", "x"])

	def test_inactive_speech_hook_disables_tagging(self):
		self.tagger.uninstall()
		tagger = self.tagging.SchemeTagger(is_active=lambda: False)
		tagger.install()
		self.addCleanup(tagger.uninstall)
		self.configure({"role.BUTTON": {"sound": self.sound()}})
		speech.speakObject(FakeObject("OK", Role.BUTTON))
		self.assertEqual(self.speech_module.spoken[-1], ["OK", "button"])

	def test_uninstall_restores_nvda_functions(self):
		wrapped = speech.speakObject
		self.tagger.uninstall()
		self.assertIsNot(speech.speakObject, wrapped)
		self.assertIs(speech.speakObject, self.speech_module.speakObject)
		self.assertEqual(speech.speakObject.__name__, "speakObject")


# ---------------------------------------------------------------------------
# Plugin integration
# ---------------------------------------------------------------------------

class SchemePluginIntegrationTests(SchemeHarnessBase):
	def _plugin(self):
		plugin = self.module.GlobalPlugin()
		globalPluginHandler.runningPlugins.append(plugin)
		self.addCleanup(plugin.terminate)
		return plugin

	def test_filter_converts_markers_on_native_paths(self):
		plugin = self._plugin()
		self.configure({"role.LINK": {"sound": self.sound(), "soundOnly": True}})
		plugin.processor._bypass_next_sequence = True
		output = plugin._filterSpeechSequence([self.markers.LabelMarker(["role.LINK"]), "link", "Home"])
		self.assertIsInstance(output[0], self.runtime.SchemeSoundCommand)
		self.assertEqual([entry for entry in output if isinstance(entry, str)], ["Home"])
		self.assertFalse(any(isinstance(entry, self.markers.SchemeMarker) for entry in output))

	def test_filter_never_leaks_markers_when_schemes_are_disabled(self):
		plugin = self._plugin()
		self.configure({"role.LINK": {"sound": self.sound()}}, enabled=False)
		plugin.processor._bypass_next_sequence = True
		output = plugin._filterSpeechSequence([self.markers.ObjectMarker(["role.LINK"]), "Home", self.markers.LabelMarker(["role.LINK"]), "link"])
		self.assertEqual(output, ["Home", "link"])

	def test_semantic_focus_speech_marks_the_final_role_token(self):
		plugin = self._plugin()
		self.configure({"role.BUTTON": {"sound": self.sound("button.wav")}})
		import api

		focus = types.SimpleNamespace(role=Role.BUTTON, name="OK", parent=None, treeInterceptor=None, value="", states=set())
		api.getFocusObject = lambda: focus
		self.addCleanup(lambda: setattr(api, "getFocusObject", lambda: None))
		output = plugin._filterSpeechSequence(["OK", self.markers.LabelMarker(["role.BUTTON"]), "button"])
		strings = [entry for entry in output if isinstance(entry, str)]
		self.assertEqual(strings, ["OK", "button"])
		sound_index = next(index for index, entry in enumerate(output) if isinstance(entry, self.runtime.SchemeSoundCommand))
		self.assertEqual(output[sound_index + 1:].index("button"), next(
			offset for offset, entry in enumerate(output[sound_index + 1:]) if isinstance(entry, str) and entry == "button"
		))
		self.assertFalse(any(isinstance(entry, self.markers.SchemeMarker) for entry in output))


# ---------------------------------------------------------------------------
# Scheme folders and packages
# ---------------------------------------------------------------------------

class SchemeFolderHarnessBase(SchemeHarnessBase):
	"""Keep schemes in a temporary folder, as NVDA keeps them in its configuration folder."""

	def setUp(self):
		super().setUp()
		self.root_dir = tempfile.TemporaryDirectory()
		self.addCleanup(self.root_dir.cleanup)
		self.root = str(Path(self.root_dir.name) / "Schemes")
		self.store._ROOT_OVERRIDE = self.root
		self.addCleanup(setattr, self.store, "_ROOT_OVERRIDE", None)
		self.section["schemeData"] = "{}"
		self.store.invalidate_runtime_cache()

	def folders(self):
		return sorted(entry.name for entry in Path(self.root).iterdir() if entry.is_dir())

	def scheme_json(self, folder):
		return json.loads((Path(self.root) / folder / "scheme.json").read_text(encoding="utf-8"))

	def saved(self, editor):
		editor.apply()
		editor.mark_applied()


class SchemeFolderTests(SchemeFolderHarnessBase):
	def test_a_default_scheme_folder_is_created(self):
		self.assertEqual(self.store.prepare_scheme_folders(self.section), self.root)
		self.assertEqual(self.folders(), ["Default"])
		self.assertEqual(self.scheme_json("Default")["name"], "Default")
		self.assertEqual(self.scheme_json("Default")["items"], {})

	def test_plugin_start_prepares_the_schemes_folder(self):
		plugin = self.module.GlobalPlugin()
		self.addCleanup(plugin.terminate)
		self.assertEqual(self.folders(), ["Default"])

	def test_schemes_kept_in_the_config_move_into_their_own_folders(self):
		link = self.sound("link.wav")
		self.configure({"role.LINK": {"sound": link}}, custom={"fonts": ["Arial"]})
		data = json.loads(self.section["schemeData"])
		data["schemes"]["Web: news"] = {"items": {"fmt.bold": {"sound": link, "soundOnly": True}}}
		data["activeScheme"] = "Web: news"
		self.section["schemeData"] = json.dumps(data)
		self.store.prepare_scheme_folders(self.section)
		self.assertEqual(self.folders(), ["Default", "Web_ news"])
		default = self.scheme_json("Default")
		self.assertEqual(default["items"]["role.LINK"]["sound"], "Sounds/link.wav")
		self.assertTrue((Path(self.root) / "Default" / "Sounds" / "link.wav").is_file())
		self.assertEqual(default["custom"]["fonts"], ["Arial"])
		self.assertEqual(self.scheme_json("Web_ news")["name"], "Web: news")
		self.assertEqual(
			json.loads(self.section["schemeData"]),
			{"version": 2, "enabled": True, "activeScheme": "Web: news"},
		)
		# Speech now reads the active scheme from its folder.
		self.assertEqual(
			self.store.active_items()["fmt.bold"]["sound"],
			str(Path(self.root) / "Web_ news" / "Sounds" / "link.wav"),
		)
		# Moving again changes nothing.
		self.store.prepare_scheme_folders(self.section)
		self.assertEqual(self.folders(), ["Default", "Web_ news"])

	def test_saving_writes_renames_and_deletes_scheme_folders(self):
		editor = self.store.SchemeStore(self.section)
		self.assertEqual(editor.root, self.root)
		self.assertEqual(editor.scheme_names, ["Default"])
		editor.add_scheme("Proofreading")
		editor.set_item("fmt.bold", {"sound": self.sound("bold.wav")})
		self.saved(editor)
		self.assertEqual(self.folders(), ["Default", "Proofreading"])
		self.assertEqual(self.scheme_json("Proofreading")["items"]["fmt.bold"]["sound"], "Sounds/bold.wav")
		# After saving, the sound is the scheme's own copy.
		self.assertEqual(
			editor.get_item("fmt.bold")["sound"],
			str(Path(self.root) / "Proofreading" / "Sounds" / "bold.wav"),
		)
		editor.rename_scheme("Proofreading", "Word/Docs")
		self.saved(editor)
		self.assertEqual(self.folders(), ["Default", "Word_Docs"])
		self.assertEqual(self.scheme_json("Word_Docs")["name"], "Word/Docs")
		self.assertTrue((Path(self.root) / "Word_Docs" / "Sounds" / "bold.wav").is_file())
		editor.set_active_scheme("Word/Docs")
		self.assertTrue(editor.delete_scheme("Word/Docs"))
		self.saved(editor)
		self.assertEqual(self.folders(), ["Default"])

	def test_a_copy_keeps_the_sounds_of_a_scheme_deleted_in_the_same_save(self):
		editor = self.store.SchemeStore(self.section)
		editor.add_scheme("Old")
		editor.set_item("role.LINK", {"sound": self.sound("link.wav")})
		self.saved(editor)
		editor.add_scheme("Old copy", copy_from="Old")
		editor.delete_scheme("Old")
		# A new scheme may take the deleted scheme's name.
		self.assertEqual(editor.add_scheme("Old"), "Old")
		self.saved(editor)
		self.assertEqual(self.folders(), ["Default", "Old", "Old copy"])
		self.assertTrue((Path(self.root) / "Old copy" / "Sounds" / "link.wav").is_file())
		self.assertEqual(self.scheme_json("Old")["items"], {})

	def test_cancel_leaves_the_folders_alone(self):
		editor = self.store.SchemeStore(self.section)
		editor.add_scheme("Draft")
		editor.set_item("role.LINK", {"sound": self.sound()})
		editor.cancel()
		self.assertEqual(self.folders(), ["Default"])
		self.assertEqual(editor.scheme_names, ["Default"])
		self.assertFalse(editor.is_dirty())

	def test_added_entries_belong_to_each_scheme(self):
		editor = self.store.SchemeStore(self.section)
		self.assertTrue(editor.add_custom_entry("fonts", "Arial"))
		editor.add_scheme("Plain")
		# A new scheme starts with the active scheme's added entries.
		self.assertEqual(editor.custom_entries()["fonts"], ["Arial"])
		self.assertTrue(editor.add_custom_entry("styles", "Quote"))
		editor.set_active_scheme("Default")
		self.assertEqual(editor.custom_entries()["styles"], [])
		self.saved(editor)
		self.assertEqual(self.scheme_json("Plain")["custom"]["styles"], ["Quote"])
		self.assertEqual(self.scheme_json("Default")["custom"]["fonts"], ["Arial"])

	def test_folder_names_are_safe_on_windows(self):
		name_for = self.store.folder_name_for
		self.assertEqual(name_for("News: today?"), "News_ today_")
		self.assertEqual(name_for("CON"), "_CON")
		self.assertEqual(name_for("lpt1.old"), "_lpt1.old")
		self.assertEqual(name_for(" trailing. "), "trailing")
		self.assertEqual(name_for("..."), "Scheme")

	def test_switch_commands_use_the_scheme_folders(self):
		editor = self.store.SchemeStore(self.section)
		editor.add_scheme("Web")
		editor.set_item("role.LINK", {"sound": self.sound()})
		editor.set_active_scheme("Default")
		self.saved(editor)
		self.assertEqual(self.store.active_items(), {})
		self.assertEqual(self.store.cycle_active_scheme(), "Web")
		self.assertIn("role.LINK", self.store.active_items())
		self.assertFalse(self.store.set_schemes_enabled(False))
		self.assertEqual(self.store.active_items(), {})
		self.assertEqual(
			json.loads(self.section["schemeData"]),
			{"version": 2, "enabled": False, "activeScheme": "Web"},
		)


class SchemePackageTests(SchemeFolderHarnessBase):
	def package_path(self, name="Shared"):
		return str(Path(self.root_dir.name) / f"{name}.classicspeech-scheme")

	def test_export_and_import_carry_sounds_voices_and_added_entries(self):
		from globalPlugins._speech_core.schemes import packages

		editor = self.store.SchemeStore(self.section)
		editor.add_custom_entry("fonts", "Arial")
		editor.set_item("fmt.fontName.arial", {"sound": self.sound("arial.wav"), "soundOnly": True})
		editor.set_item("role.LINK", {"voice": {"enabled": True, "bySynth": {"fakeSynth": _voice_record(pitch=70)}}})
		package = self.package_path()
		self.assertEqual(editor.export_scheme("Default", package), [])
		with zipfile.ZipFile(package) as archive:
			self.assertEqual(sorted(archive.namelist()), ["Sounds/arial.wav", packages.MANIFEST_NAME])
		receiver = self.store.SchemeStore(self.section)
		self.assertEqual(receiver.import_package(package), "Default 2")
		self.assertEqual(receiver.active_scheme, "Default 2")
		self.assertEqual(receiver.custom_entries()["fonts"], ["Arial"])
		self.assertTrue(receiver.get_item("fmt.fontName.arial")["soundOnly"])
		self.assertEqual(receiver.get_item("role.LINK")["voice"]["bySynth"]["fakeSynth"]["overrides"], {"pitch": 70})
		# Nothing is saved before Apply.
		self.assertEqual(self.folders(), ["Default"])
		self.saved(receiver)
		self.assertEqual(self.folders(), ["Default", "Default 2"])
		self.assertTrue((Path(self.root) / "Default 2" / "Sounds" / "arial.wav").is_file())

	def test_cancelled_import_leaves_no_files(self):
		editor = self.store.SchemeStore(self.section)
		editor.set_item("role.LINK", {"sound": self.sound()})
		package = self.package_path()
		editor.export_scheme("Default", package)
		receiver = self.store.SchemeStore(self.section)
		receiver.import_package(package)
		staging = receiver._staging[0]
		self.assertTrue(os.path.isdir(staging))
		receiver.cancel()
		self.assertFalse(os.path.isdir(staging))
		self.assertEqual(self.folders(), ["Default"])

	def test_export_leaves_out_missing_sounds_and_names_them(self):
		from globalPlugins._speech_core.schemes import packages

		editor = self.store.SchemeStore(self.section)
		missing = str(Path(self.sound_dir.name) / "gone.wav")
		editor.set_item("role.LINK", {
			"sound": missing,
			"voice": {"enabled": True, "bySynth": {"fakeSynth": _voice_record(rate=70)}},
		})
		package = self.package_path("Partial")
		self.assertEqual(editor.export_scheme("Default", package), [missing])
		with zipfile.ZipFile(package) as archive:
			manifest = json.loads(archive.read(packages.MANIFEST_NAME))
		self.assertNotIn("sound", manifest["items"]["role.LINK"])
		self.assertTrue(manifest["items"]["role.LINK"]["voice"]["enabled"])

	def test_other_files_and_unsafe_package_contents_are_refused(self):
		from globalPlugins._speech_core.schemes import packages

		base = Path(self.root_dir.name)
		editor = self.store.SchemeStore(self.section)
		not_a_zip = base / "notes.classicspeech-scheme"
		not_a_zip.write_text("hello", encoding="utf-8")
		with self.assertRaises(packages.PackageError):
			editor.import_package(str(not_a_zip))
		foreign = base / "foreign.classicspeech-scheme"
		with zipfile.ZipFile(foreign, "w") as archive:
			archive.writestr(packages.MANIFEST_NAME, json.dumps({"format": "something else"}))
		with self.assertRaises(packages.PackageError):
			editor.import_package(str(foreign))
		sneaky = base / "sneaky.classicspeech-scheme"
		manifest = {"format": packages.PACKAGE_FORMAT, "name": "Sneaky", "items": {
			"role.LINK": {"sound": "Sounds/../../evil.wav", "soundOnly": True},
			"role.BUTTON": {"sound": "Sounds/run.exe"},
			"role.CHECKBOX": {"sound": "C:/Windows/evil.wav"},
			"state.CHECKED": {"sound": "Sounds/ok.wav"},
			"python.code": {"sound": "Sounds/ok.wav"},
		}}
		with zipfile.ZipFile(sneaky, "w") as archive:
			archive.writestr(packages.MANIFEST_NAME, json.dumps(manifest))
			archive.writestr("Sounds/../../evil.wav", b"RIFF")
			archive.writestr("Sounds/run.exe", b"MZ")
			archive.writestr("Sounds/ok.wav", b"RIFF")
		self.assertEqual(editor.import_package(str(sneaky)), "Sneaky")
		self.assertEqual(editor.configured_item_ids(), {"state.CHECKED"})
		staging = Path(editor._staging[-1])
		self.assertEqual(sorted(path.name for path in staging.rglob("*") if path.is_file()), ["ok.wav"])
		self.assertFalse((base / "evil.wav").exists())
		editor.cancel()

	def test_import_button_adds_the_scheme_and_waits_for_apply(self):
		from globalPlugins._speech_core.settings import schemes_dialog

		editor = self.store.SchemeStore(self.section)
		editor.set_item("role.LINK", {"sound": self.sound()})
		package = self.package_path("Friend")
		editor.export_scheme("Default", package)
		calls = []
		messages = []
		dialog = types.SimpleNamespace(
			store=self.store.SchemeStore(self.section),
			_loadSchemeChoice=lambda: calls.append("choices"),
			itemsPanel=types.SimpleNamespace(rebuildTree=lambda *args: calls.append("tree")),
			_markDirty=lambda: calls.append("dirty"),
			_message=lambda text, title, icon=None: messages.append(text),
			schemeChoice=types.SimpleNamespace(SetFocus=lambda: calls.append("focus")),
		)
		original = schemes_dialog.choose_import_path
		schemes_dialog.choose_import_path = lambda *args, **kwargs: package
		try:
			schemes_dialog.SpeechSoundSchemesDialog.onImportScheme(dialog, None)
		finally:
			schemes_dialog.choose_import_path = original
		self.assertEqual(calls, ["choices", "tree", "dirty", "focus"])
		self.assertEqual(dialog.store.active_scheme, "Default 2")
		self.assertEqual(
			messages,
			["Imported the scheme Default 2. It is now the active scheme. Press OK or Apply to keep it."],
		)
		dialog.store.cancel()


if __name__ == "__main__":
	unittest.main(verbosity=2)
