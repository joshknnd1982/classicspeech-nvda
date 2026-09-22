"""Find and open the ClassicSpeech user guide.

The guide is ``doc/<language>/readme.html`` inside the installed add-on, which
the manifest's ``docFileName`` names. NVDA's Add-on Store Help action opens the
same file, so both routes always show the same guide.
"""
from __future__ import annotations

import os

import logHandler

from .localization import _

log = logHandler.log

USER_GUIDE_FILE_NAME = "readme.html"
# This module is installed as <add-on>/globalPlugins/_speech_core/user_guide.py.
_ADDON_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def guide_languages(language: str) -> list[str]:
	"""Return the documentation folders to try, in NVDA's order: xx_YY, xx, en."""
	language = str(language or "en")
	languages = [language]
	if "_" in language:
		language = language.split("_", 1)[0]
		languages.append(language)
	if language != "en":
		languages.append("en")
	return languages


def find_user_guide_in(addon_root: str, language: str, file_name: str = USER_GUIDE_FILE_NAME) -> str | None:
	"""Return the guide under ``addon_root`` for ``language``, or None."""
	for folder in guide_languages(language):
		path = os.path.join(addon_root, "doc", folder, file_name)
		if os.path.isfile(path):
			return path
	return None


def find_user_guide() -> str | None:
	"""Return the guide the Add-on Store Help action would open, or None."""
	try:
		import addonHandler

		path = addonHandler.getCodeAddon().getDocFilePath()
		if path:
			return path
	except Exception:
		log.debug("ClassicSpeech: add-on documentation lookup failed", exc_info=True)
	try:
		import languageHandler

		language = languageHandler.getLanguage()
	except Exception:
		language = "en"
	return find_user_guide_in(_ADDON_ROOT, language)


def open_user_guide(startfile=None) -> bool:
	"""Open the guide with its default Windows program, or say why it cannot."""
	from .message_priority import speak_message

	path = find_user_guide()
	if not path:
		speak_message(_("The ClassicSpeech user guide could not be found."))
		return False
	try:
		(startfile or os.startfile)(path)
	except Exception:
		log.exception("ClassicSpeech: failed to open the user guide")
		speak_message(_("The ClassicSpeech user guide could not be opened."))
		return False
	return True
