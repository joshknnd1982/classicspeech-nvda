"""NVDA's own sounds in Speech and Sound Schemes (the NVDA sounds category).

A scheme can give each sound in NVDA's waves folder a sound of its own, kept
in the scheme's folder. While schemes are on, NVDA plays that sound instead of
its own; without one, or with a missing file, NVDA's sound plays as always.
NVDA plays its start sound before add-ons load, so for a start sound
ClassicSpeech takes over NVDA's start and exit sounds and gives them back when
the scheme no longer has one. These tests use a temporary NVDA program folder
and configuration folder; they never touch NVDA's real files.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
	sys.path.insert(0, str(ROOT / "tests"))

import classic_speech_nvda_master_harness as nvda_harness  # noqa: E402
import config  # noqa: E402
import globalPluginHandler  # noqa: E402
import speech  # noqa: E402

NVDA_WAVES = nvda_harness.NVDA_SOURCE / "waves"


class NvdaSoundsHarnessBase(unittest.TestCase):
	def setUp(self):
		nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
		config.conf["general"] = {"playStartAndExitSounds": True}
		self.section = config.conf.profiles[0].setdefault("classicSpeech", {})
		self.temp = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp.cleanup)
		temp = Path(self.temp.name)
		# NVDA's program folder, with the waves NVDA master ships.
		self.appDir = temp / "NVDA"
		shutil.copytree(NVDA_WAVES, self.appDir / "waves")
		self.configDir = temp / "config"
		self.configDir.mkdir()
		self.played = []
		self._saved = {name: sys.modules.get(name) for name in ("globalVars", "nvwave")}
		sys.modules["globalVars"] = types.SimpleNamespace(
			appDir=str(self.appDir),
			appArgs=types.SimpleNamespace(minimal=False, secure=False, configPath=str(self.configDir)),
		)
		nvwave = types.ModuleType("nvwave")

		def playWaveFile(fileName, asynchronous=True, isSpeechWaveFileCommand=False):
			self.played.append((fileName, asynchronous))

		nvwave.playWaveFile = playWaveFile
		self.nvdaPlayWaveFile = playWaveFile
		sys.modules["nvwave"] = nvwave
		self.nvwave = nvwave
		self.module = nvda_harness._import_classic_speech_like_nvda()
		from globalPlugins._speech_core import nvda_settings_backup
		from globalPlugins._speech_core.schemes import catalog, nvda_sounds, runtime, store

		self.backup = nvda_settings_backup
		self.catalog = catalog
		self.sounds = nvda_sounds
		self.runtime = runtime
		self.store = store
		nvda_settings_backup._CONFIG_FOLDER_OVERRIDE = str(self.configDir)
		self.addCleanup(setattr, nvda_settings_backup, "_CONFIG_FOLDER_OVERRIDE", None)
		self.root = str(self.configDir / "ClassicSpeech" / "Schemes")
		store._ROOT_OVERRIDE = self.root
		self.addCleanup(setattr, store, "_ROOT_OVERRIDE", None)
		self.section["schemeData"] = "{}"
		store.invalidate_runtime_cache()
		self.plugin = None

	def tearDown(self):
		try:
			if self.plugin is not None:
				self.plugin.terminate()
		finally:
			globalPluginHandler.runningPlugins.clear()
			speech.extensions.filter_speechSequence.callbacks.clear()
			nvda_harness._reset_global_plugin_imports()
			for name, module in self._saved.items():
				if module is None:
					sys.modules.pop(name, None)
				else:
					sys.modules[name] = module

	# -- helpers -------------------------------------------------------------
	def start_plugin(self):
		self.plugin = self.module.GlobalPlugin()
		globalPluginHandler.runningPlugins.append(self.plugin)
		return self.plugin

	def nvda_wave(self, name):
		return str(self.appDir / "waves" / f"{name}.wav")

	def outside_sound(self, name="custom.wav"):
		path = Path(self.temp.name) / "Downloads" / name
		path.parent.mkdir(exist_ok=True)
		path.write_bytes(b"RIFF" + name.encode())
		return str(path)

	def give(self, sounds, enabled=True):
		"""Give NVDA sounds scheme sounds through the schemes dialog's store, then press OK."""
		editor = self.store.SchemeStore(self.section, self.root)
		for name, path in sounds.items():
			if path:
				editor.set_item(self.catalog.nvda_sound_item_id(name), {"sound": path})
			else:
				editor.clear_item(self.catalog.nvda_sound_item_id(name))
		editor.enabled = enabled
		editor.apply()
		editor.mark_applied()
		return editor

	def scheme_sound(self, name):
		"""The sound file the active scheme keeps for NVDA's sound ``name``."""
		return self.store.active_nvda_sounds().get(name.lower())

	def nvda_plays(self, *args, **kwargs):
		"""NVDA plays one of its sounds; return the file actually played."""
		self.played.clear()
		self.nvwave.playWaveFile(*args, **kwargs)
		return self.played[-1][0]

	def option(self):
		return config.conf["general"]["playStartAndExitSounds"]


class NvdaSoundCatalogTests(NvdaSoundsHarnessBase):
	def test_every_sound_nvda_ships_is_listed_with_its_event(self):
		categories = self.catalog.build_categories()
		nvda = next(category for category in categories if category.category_id == "nvdaSounds")
		named = {item.item_id: item for item in nvda.items}
		for wave in sorted(NVDA_WAVES.glob("*.wav")):
			item_id = self.catalog.nvda_sound_item_id(wave.stem)
			self.assertIn(item_id, named, f"NVDA's {wave.name} has no item")
			item = named[item_id]
			self.assertNotIn(".wav", item.label, f"{wave.name} is not described by its event")
			self.assertTrue(item.description, wave.name)
			self.assertEqual(item.voice_scope, self.catalog.SCOPE_NVDA_SOUND)
		self.assertFalse(nvda.formatting, "NVDA sounds must not appear in Voice Profiles")

	def test_a_sound_a_later_nvda_adds_is_listed_by_file_name(self):
		(self.appDir / "waves" / "newThing.wav").write_bytes(b"RIFF")
		nvda = next(c for c in self.catalog.build_categories() if c.category_id == "nvdaSounds")
		labels = {item.item_id: item.label for item in nvda.items}
		self.assertEqual(labels["nvdaSound.newThing"], "NVDA sound newThing.wav")

	def test_the_catalog_names_the_file_each_item_replaces(self):
		self.assertEqual(self.catalog.nvda_sound_file_name("nvdaSound.browseMode"), "browseMode.wav")
		self.assertTrue(self.catalog.is_nvda_sound_item("nvdaSound.start"))
		self.assertFalse(self.catalog.is_nvda_sound_item("role.LINK"))
		self.assertEqual(self.catalog.describe_item_id("nvdaSound.focusMode"), "Switching to focus mode")


class NvdaSoundReplacementTests(NvdaSoundsHarnessBase):
	def test_without_scheme_sounds_nvda_plays_its_own(self):
		self.start_plugin()
		self.assertEqual(self.nvda_plays(self.nvda_wave("browseMode")), self.nvda_wave("browseMode"))

	def test_a_scheme_sound_plays_instead_and_lives_in_the_scheme_folder(self):
		self.give({"browseMode": self.outside_sound("browse.wav")})
		self.start_plugin()
		stored = self.scheme_sound("browseMode")
		self.assertTrue(stored.startswith(self.root), stored)
		self.assertTrue(os.path.isfile(stored))
		self.assertEqual(self.nvda_plays(self.nvda_wave("browseMode")), stored)
		# Only that sound: NVDA's other sounds are its own.
		self.assertEqual(self.nvda_plays(self.nvda_wave("focusMode")), self.nvda_wave("focusMode"))

	def test_every_way_nvda_names_a_sound_is_replaced(self):
		self.give({"textError": self.outside_sound("oops.wav"), "clipboardReceive": self.outside_sound("clip.wav")})
		self.start_plugin()
		# Speech: WaveFileCommand(r"waves\textError.wav"), relative to NVDA's program folder.
		self.assertEqual(
			self.nvda_plays("waves\\textError.wav", asynchronous=True, isSpeechWaveFileCommand=True),
			self.scheme_sound("textError"),
		)
		# Remote Access plays a sound by keyword.
		self.assertEqual(
			self.nvda_plays(fileName=self.nvda_wave("clipboardReceive"), asynchronous=True),
			self.scheme_sound("clipboardReceive"),
		)
		self.assertEqual(self.nvda_plays(self.nvda_wave("TEXTERROR")), self.scheme_sound("textError"))

	def test_removing_the_sound_brings_nvdas_sound_back(self):
		self.give({"focusMode": self.outside_sound("focus.wav")})
		self.start_plugin()
		self.assertNotEqual(self.nvda_plays(self.nvda_wave("focusMode")), self.nvda_wave("focusMode"))
		self.give({"focusMode": None})
		self.assertEqual(self.nvda_plays(self.nvda_wave("focusMode")), self.nvda_wave("focusMode"))

	def test_turning_schemes_off_brings_nvdas_sounds_back(self):
		self.give({"error": self.outside_sound("error.wav")})
		self.start_plugin()
		self.store.set_schemes_enabled(False)
		self.assertEqual(self.nvda_plays(self.nvda_wave("error")), self.nvda_wave("error"))
		self.store.set_schemes_enabled(True)
		self.assertEqual(self.nvda_plays(self.nvda_wave("error")), self.scheme_sound("error"))

	def test_a_missing_or_outside_file_leaves_nvdas_sound(self):
		self.give({"connected": self.outside_sound("connected.wav")})
		self.start_plugin()
		os.remove(self.scheme_sound("connected"))
		self.assertEqual(self.nvda_plays(self.nvda_wave("connected")), self.nvda_wave("connected"))
		outside = self.outside_sound("elsewhere.wav")
		scheme = json.loads(Path(self.root, "Default", "scheme.json").read_text(encoding="utf-8"))
		scheme["items"]["nvdaSound.connected"] = {"sound": outside, "soundOnly": False}
		Path(self.root, "Default", "scheme.json").write_text(json.dumps(scheme), encoding="utf-8")
		self.store.invalidate_runtime_cache()
		self.assertEqual(self.scheme_sound("connected"), outside)
		self.assertEqual(self.nvda_plays(self.nvda_wave("connected")), self.nvda_wave("connected"))

	def test_a_sound_nvda_cannot_play_falls_back_to_nvdas_own(self):
		self.give({"browseMode": self.outside_sound("broken.wav")})
		self.start_plugin()
		stored = self.scheme_sound("browseMode")
		tried = []

		def nvda_player(fileName, asynchronous=True, isSpeechWaveFileCommand=False):
			tried.append(fileName)
			if fileName == stored:
				raise EOFError("not a WAV file NVDA can read")

		self.plugin.terminate()
		self.nvwave.playWaveFile = nvda_player
		self.plugin = self.module.GlobalPlugin()
		self.nvwave.playWaveFile(self.nvda_wave("browseMode"))
		self.assertEqual(tried, [stored, self.nvda_wave("browseMode")])

	def test_other_sounds_are_never_replaced(self):
		self.give({"browseMode": self.outside_sound("browse.wav")})
		self.start_plugin()
		for path in (self.scheme_sound("browseMode"), self.outside_sound("browseMode.wav")):
			self.assertEqual(self.nvda_plays(path), path)

	def test_the_play_sound_button_plays_exactly_the_file(self):
		self.give({"browseMode": self.outside_sound("browse.wav")})
		self.start_plugin()
		self.played.clear()
		self.sounds.play_sound_file(self.nvda_wave("browseMode"))
		self.assertEqual(self.played, [(self.nvda_wave("browseMode"), True)])

	def test_nvda_sounds_never_reach_speech(self):
		self.give({"browseMode": self.outside_sound("browse.wav")})
		self.assertEqual(self.store.active_items(), {})
		self.assertFalse(self.store.schemes_active())
		sequence = ["link", "Home"]
		self.assertIs(self.runtime.apply_schemes(sequence), sequence)

	def test_removing_classicspeech_gives_nvda_its_player_back(self):
		self.start_plugin()
		self.assertIsNot(self.nvwave.playWaveFile, self.nvdaPlayWaveFile)
		self.plugin.terminate()
		self.plugin = None
		self.assertIs(self.nvwave.playWaveFile, self.nvdaPlayWaveFile)

	def test_while_nvda_exits_its_exit_sound_is_still_replaced(self):
		self.give({"exit": self.outside_sound("bye.wav")})
		plugin = self.start_plugin()
		stored = self.scheme_sound("exit")
		core = types.ModuleType("core")
		core._hasShutdownBeenTriggered = True
		saved_core = sys.modules.get("core")
		sys.modules["core"] = core
		try:
			plugin.terminate()
		finally:
			sys.modules["core"] = saved_core
		self.plugin = None
		# NVDA plays its exit sound last, after ClassicSpeech has stopped.
		self.section["schemeData"] = "{}"
		self.store.invalidate_runtime_cache()
		self.assertEqual(self.nvda_plays(self.nvda_wave("exit"), asynchronous=False), stored)
		self.sounds.uninstall()

	def test_shared_schemes_keep_their_nvda_sounds(self):
		editor = self.give({"screenCurtainOn": self.outside_sound("curtain.wav")})
		package = str(Path(self.temp.name) / "shared.classicspeech-scheme")
		self.assertEqual(editor.export_scheme("Default", package), [])
		editor.import_package(package)
		imported = editor.get_item("nvdaSound.screenCurtainOn")
		self.assertTrue(imported.get("sound"))
		editor.cleanup()


class NvdaStartAndExitSoundTests(NvdaSoundsHarnessBase):
	def test_a_start_sound_takes_over_nvdas_start_and_exit_sounds(self):
		self.give({"start": self.outside_sound("hello.wav")})
		self.assertFalse(self.option(), "NVDA would play its own start sound before ClassicSpeech loads")
		self.assertTrue(self.sounds.classicspeech_plays_start_and_exit_sounds())
		self.played.clear()
		self.start_plugin()
		self.assertEqual(self.played, [(self.scheme_sound("start"), True)])

	def test_without_a_start_sound_nvda_keeps_its_option_and_classicspeech_plays_nothing(self):
		self.give({"exit": self.outside_sound("bye.wav")})
		self.assertTrue(self.option())
		self.played.clear()
		self.start_plugin()
		self.assertEqual(self.played, [])

	def test_removing_the_start_sound_gives_the_sounds_back_to_nvda(self):
		self.give({"start": self.outside_sound("hello.wav")})
		self.start_plugin()
		self.give({"start": None})
		self.assertTrue(self.option())
		self.assertFalse(self.sounds.classicspeech_plays_start_and_exit_sounds())

	def test_turning_schemes_off_gives_the_sounds_back_to_nvda(self):
		self.give({"start": self.outside_sound("hello.wav")})
		self.start_plugin()
		self.store.set_schemes_enabled(False)
		self.assertTrue(self.option())
		self.store.set_schemes_enabled(True)
		self.assertFalse(self.option())

	def test_nvdas_option_off_means_no_start_or_exit_sound_at_all(self):
		config.conf["general"]["playStartAndExitSounds"] = False
		self.give({"start": self.outside_sound("hello.wav")})
		self.assertFalse(self.sounds.classicspeech_plays_start_and_exit_sounds())
		self.played.clear()
		self.start_plugin()
		self.assertEqual(self.played, [])

	def test_nvdas_option_turned_back_on_is_taken_over_again_without_a_second_start_sound(self):
		self.give({"start": self.outside_sound("hello.wav")})
		config.conf["general"]["playStartAndExitSounds"] = True  # Checked again in NVDA's settings.
		self.played.clear()
		self.start_plugin()
		self.assertEqual(self.played, [], "NVDA already played its own start sound")
		self.assertFalse(self.option())

	def test_nvda_exit_plays_the_exit_sound_classicspeech_took_over(self):
		self.give({"start": self.outside_sound("hello.wav")})
		plugin = self.start_plugin()
		self.played.clear()
		self.exit_nvda(plugin)
		self.assertEqual(self.played, [(self.nvda_wave("exit"), False)])
		self.assertFalse(self.option(), "NVDA saves its configuration after ClassicSpeech stops")

	def test_nvda_exit_plays_the_schemes_exit_sound(self):
		self.give({"start": self.outside_sound("hello.wav"), "exit": self.outside_sound("bye.wav")})
		plugin = self.start_plugin()
		stored = self.scheme_sound("exit")
		self.played.clear()
		self.exit_nvda(plugin)
		self.assertEqual(self.played, [(stored, False)])

	def test_disabling_or_removing_classicspeech_gives_the_sounds_back(self):
		for state in ("isPendingDisable", "isPendingRemove"):
			config.conf["general"]["playStartAndExitSounds"] = True
			self.section["nvdaStartExitSoundsState"] = ""
			self.give({"start": self.outside_sound("hello.wav")})
			plugin = self.start_plugin()
			self.played.clear()
			self.exit_nvda(plugin, addon=types.SimpleNamespace(**{state: True}, path=str(self.appDir), name="ClassicSpeech"))
			self.assertTrue(self.option(), state)
			self.assertEqual(self.played, [], "NVDA plays its own exit sound once its option is back")

	def test_updating_classicspeech_keeps_the_sounds(self):
		self.give({"start": self.outside_sound("hello.wav")})
		plugin = self.start_plugin()
		addons = Path(self.temp.name) / "addons"
		(addons / "ClassicSpeech.pendingInstall").mkdir(parents=True)
		addon = types.SimpleNamespace(isPendingRemove=True, path=str(addons / "ClassicSpeech"), name="ClassicSpeech")
		self.exit_nvda(plugin, addon=addon)
		self.assertFalse(self.option())

	def test_windows_sign_out_plays_the_exit_sound_classicspeech_took_over(self):
		self.give({"start": self.outside_sound("hello.wav")})
		self.start_plugin()
		self.played.clear()
		self.sounds.handle_windows_session_end()
		self.assertEqual(self.played, [(self.nvda_wave("exit"), False)])

	def test_reset_all_classicspeech_settings_gives_the_option_back(self):
		self.give({"start": self.outside_sound("hello.wav")})
		self.assertFalse(self.option())
		self.backup.reset_all(save=False)
		self.assertTrue(self.option())

	def test_reloading_plugins_does_not_play_the_start_sound_again(self):
		self.give({"start": self.outside_sound("hello.wav")})
		state = types.ModuleType("NVDAState")
		state._TrackNVDAInitialization = types.SimpleNamespace(isInitializationComplete=lambda: True)
		saved = sys.modules.get("NVDAState")
		sys.modules["NVDAState"] = state
		self.addCleanup(lambda: sys.modules.pop("NVDAState", None) if saved is None else sys.modules.__setitem__("NVDAState", saved))
		self.played.clear()
		self.start_plugin()
		self.assertEqual(self.played, [])

	def test_minimal_start_plays_nothing(self):
		self.give({"start": self.outside_sound("hello.wav")})
		sys.modules["globalVars"].appArgs.minimal = True
		self.played.clear()
		self.start_plugin()
		self.assertEqual(self.played, [])

	def test_secure_screens_never_change_nvdas_option(self):
		sys.modules["globalVars"].appArgs.secure = True
		self.give({"start": self.outside_sound("hello.wav")})
		self.assertTrue(self.option())

	def exit_nvda(self, plugin, addon=None):
		core = types.ModuleType("core")
		core._hasShutdownBeenTriggered = True
		addon_handler = types.ModuleType("addonHandler")
		addon_handler.getCodeAddon = lambda *args, **kwargs: addon or types.SimpleNamespace(
			isPendingDisable=False, isPendingRemove=False, path=str(self.appDir), name="ClassicSpeech",
		)
		saved = {name: sys.modules.get(name) for name in ("core", "addonHandler")}
		sys.modules.update({"core": core, "addonHandler": addon_handler})
		try:
			plugin.terminate()
		finally:
			for name, module in saved.items():
				if module is None:
					sys.modules.pop(name, None)
				else:
					sys.modules[name] = module
			globalPluginHandler.runningPlugins.clear()
			self.plugin = None
			self.sounds.uninstall()


class _Control:
	"""A wx control double that remembers its value and whether it is enabled."""

	def __init__(self, value=""):
		self.value = value
		self.enabled = True
		self.items = []

	def SetValue(self, value):
		self.value = value

	def GetValue(self):
		return self.value

	def SetSelection(self, index):
		self.value = index

	def GetSelection(self):
		return self.value

	def SetItems(self, items):
		self.items = list(items)

	def Enable(self, enabled=True):
		self.enabled = bool(enabled)

	def Disable(self):
		self.enabled = False

	def __getattr__(self, name):
		return lambda *args, **kwargs: None


class NvdaSoundDialogTests(NvdaSoundsHarnessBase):
	def panel(self, item_id):
		from globalPlugins._speech_core.settings import schemes_panel

		editor = self.store.SchemeStore(self.section, self.root)
		panel = types.SimpleNamespace(
			store=editor,
			showSounds=True,
			_itemsById=self.catalog.item_index(self.catalog.build_categories()),
			_currentItemId=item_id,
			_currentCategoryKind="",
			_loading=False,
			_voiceControls=None,
			_voiceDriver=None,
			_probes={},
			_synthValues=[""],
			Layout=lambda: None,
		)
		for name in (
			"removeEntryButton", "itemDetails", "soundPath", "soundModeChoice", "browseSoundButton",
			"playSoundButton", "removeSoundButton", "voiceCheckBox", "resetItemButton", "synthChoice",
			"previewVoiceButton", "engineNote", "voicePanel", "voicePanelSizer",
		):
			setattr(panel, name, _Control())
		cls = schemes_panel.SchemeItemsPanel
		for method in ("_showItem", "_isCustomEntry", "_loadSynthChoices", "_rebuildVoiceControls", "_clearVoiceControls", "_currentEngine", "onPlaySound", "onVoiceToggled"):
			setattr(panel, method, getattr(cls, method).__get__(panel))
		return panel

	def test_an_nvda_sound_has_no_voice_and_no_speech_choice(self):
		panel = self.panel("nvdaSound.browseMode")
		panel._showItem("nvdaSound.browseMode")
		self.assertIn("browseMode.wav", panel.itemDetails.value)
		self.assertIn("Audio indication of focus and browse modes", panel.itemDetails.value)
		self.assertFalse(panel.voiceCheckBox.enabled)
		self.assertFalse(panel.soundModeChoice.enabled)
		self.assertTrue(panel.playSoundButton.enabled, "Play sound plays NVDA's own sound")
		self.assertFalse(panel.removeSoundButton.enabled)
		panel.voiceCheckBox.value = True
		panel.onVoiceToggled(None)
		self.assertEqual(panel.store.get_item("nvdaSound.browseMode"), {})

	def test_play_sound_without_a_scheme_sound_plays_nvdas_own(self):
		self.start_plugin()
		panel = self.panel("nvdaSound.focusMode")
		panel._showItem("nvdaSound.focusMode")
		self.played.clear()
		panel.onPlaySound(None)
		self.assertEqual(self.played, [(self.nvda_wave("focusMode"), True)])

	def test_a_speech_item_still_offers_its_voice(self):
		panel = self.panel("role.LINK")
		panel._showItem("role.LINK")
		self.assertTrue(panel.voiceCheckBox.enabled)
		self.assertFalse(panel.playSoundButton.enabled)


if __name__ == "__main__":
	unittest.main(verbosity=2)
