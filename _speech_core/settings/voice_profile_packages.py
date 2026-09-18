"""Share Voice Profiles as a single file.

A voice profiles file is JSON with the extension ``.classicspeech-voices``::

	{
		"format": "ClassicSpeech voice profiles",
		"version": 1,
		"synthesizers": {
			"espeak": {
				"focusNavigation": {"baseline": {...}, "overrides": {...}},
				"mouse": {"baseline": {...}, "overrides": {...}}
			}
		}
	}

Voice Profiles are kept per synthesizer, so importing a file changes only the
synthesizers and categories it contains. Document and web formatting voices
belong to Speech and Sound Schemes and travel in a scheme package instead.
"""
from __future__ import annotations

import json
import os
import tempfile

from ..schemes.packages import clean_voice_record
from .voice_profiles_config import PROFILE_ROWS

VOICES_EXTENSION = ".classicspeech-voices"
VOICES_FORMAT = "ClassicSpeech voice profiles"
MAX_FILE_BYTES = 2 * 1024 * 1024
_PROFILE_IDS = frozenset(row.profile_id for row in PROFILE_ROWS)
_MAX_SYNTH_NAME_LENGTH = 200


class VoiceProfilesFileError(Exception):
	"""A file that cannot be read as ClassicSpeech voice profiles."""


def shareable_profiles(registry) -> dict:
	"""Return ``{synthesizer: {category: record}}`` with only known categories and plain values."""
	result = {}
	if not isinstance(registry, dict):
		return result
	for synth_name, profiles in registry.items():
		if not isinstance(synth_name, str) or len(synth_name) > _MAX_SYNTH_NAME_LENGTH or not isinstance(profiles, dict):
			continue
		kept = {}
		for profile_id, record in profiles.items():
			if profile_id in _PROFILE_IDS:
				record = clean_voice_record(record)
				if record:
					kept[profile_id] = record
		if kept:
			result[synth_name] = kept
	return result


def write_voice_profiles(path, registry) -> dict:
	"""Write every synthesizer's Voice Profiles to ``path``; return what was written."""
	synthesizers = shareable_profiles(registry)
	payload = {"format": VOICES_FORMAT, "version": 1, "synthesizers": synthesizers}
	folder = os.path.dirname(os.path.abspath(path))
	handle, temporary = tempfile.mkstemp(prefix=".classicspeech-", suffix=".tmp", dir=folder)
	try:
		with os.fdopen(handle, "w", encoding="utf-8") as stream:
			json.dump(payload, stream, ensure_ascii=False, indent="\t")
		os.replace(temporary, path)
	except BaseException:
		try:
			os.remove(temporary)
		except OSError:
			pass
		raise
	return synthesizers


def read_voice_profiles(path) -> dict:
	"""Return ``{synthesizer: {category: record}}`` from a voice profiles file.

	Raises VoiceProfilesFileError when ``path`` is not a ClassicSpeech voice
	profiles file or holds no profiles.
	"""
	try:
		if os.path.getsize(path) > MAX_FILE_BYTES:
			raise VoiceProfilesFileError("The file is too large to be ClassicSpeech voice profiles.")
		with open(path, encoding="utf-8") as stream:
			payload = json.load(stream)
	except (OSError, ValueError, UnicodeDecodeError) as error:
		raise VoiceProfilesFileError("The file is not ClassicSpeech voice profiles.") from error
	if not isinstance(payload, dict) or payload.get("format") != VOICES_FORMAT:
		raise VoiceProfilesFileError("The file is not ClassicSpeech voice profiles.")
	synthesizers = shareable_profiles(payload.get("synthesizers"))
	if not synthesizers:
		raise VoiceProfilesFileError("The file has no voice profiles.")
	return synthesizers
