"""Tasks NVDA runs when ClassicSpeech is installed or removed.

When ClassicSpeech is removed, NVDA runs ``onUninstall`` the next time it
starts, before any add-on runs. It puts back the NVDA settings ClassicSpeech
changed and deletes every ClassicSpeech setting: the ClassicSpeech folder in
NVDA's user configuration folder (settings.ini, the speech and sound schemes
and the backup of NVDA's settings) and any ``[classicSpeech]`` section an
earlier version left in nvda.ini. Then NVDA's configuration is saved.

NVDA also runs ``onUninstall`` for the old copy when a new ClassicSpeech
replaces it, and for a copy that is discarded before it was ever installed.
Settings are kept in both cases.
"""
import importlib.util
import os

ADDON_NAME = "ClassicSpeech"
PENDING_INSTALL_SUFFIX = ".pendingInstall"


def _addon_folder():
	return os.path.dirname(os.path.abspath(__file__))


def _is_replaced_or_discarded(addon_folder):
	"""True when NVDA is updating ClassicSpeech rather than removing it."""
	pending = os.path.join(os.path.dirname(addon_folder), ADDON_NAME + PENDING_INSTALL_SUFFIX)
	if os.path.normcase(addon_folder) == os.path.normcase(os.path.abspath(pending)):
		# This copy was never installed; NVDA discards it before restarting.
		return True
	if os.path.isdir(pending):
		# A new ClassicSpeech is waiting to be installed in place of this one.
		return True
	try:
		import addonHandler
		from addonStore.models.status import AddonStateCategory

		return ADDON_NAME in addonHandler.state[AddonStateCategory.PENDING_INSTALL]
	except Exception:
		return False


def _load_settings_backup(addon_folder):
	"""Load ClassicSpeech's settings backup module on its own; no add-on code runs yet."""
	path = os.path.join(addon_folder, "globalPlugins", "_speech_core", "nvda_settings_backup.py")
	spec = importlib.util.spec_from_file_location("classicSpeechUninstallSettingsBackup", path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def onUninstall():
	from logHandler import log

	addon_folder = _addon_folder()
	if _is_replaced_or_discarded(addon_folder):
		log.info("ClassicSpeech: keeping its settings for the ClassicSpeech that replaces this copy")
		return
	backup = _load_settings_backup(addon_folder)
	result = backup.reset_all(save=True)
	log.info(
		"ClassicSpeech: removed its settings; restored NVDA settings %s; kept NVDA settings changed since %s",
		result["restored"],
		result["kept"],
	)
	if result.get("notDeleted"):
		log.error("ClassicSpeech: could not delete all of %s; delete it yourself", result["notDeleted"])
