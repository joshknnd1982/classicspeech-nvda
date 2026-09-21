"""Share Speech and Sound Schemes as single package files.

A scheme package is a ZIP file with the extension ``.classicspeech-scheme``::

	classicspeech-scheme.json    the scheme: name, items and added catalog entries
	Sounds/<file>.wav            every sound the scheme uses

Sound paths in the JSON are ``Sounds/<file>.wav``. Reading a package accepts
only such paths, only WAV files, and only files within size limits, so a
package cannot write outside the folder it is read into or fill the disk.
Voice settings are reduced to plain values.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import zipfile

from .store import normalize_custom, normalize_item_settings

PACKAGE_EXTENSION = ".classicspeech-scheme"
PACKAGE_FORMAT = "ClassicSpeech scheme package"
MANIFEST_NAME = "classicspeech-scheme.json"
SOUNDS_PREFIX = "Sounds/"
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_SOUND_BYTES = 25 * 1024 * 1024
MAX_TOTAL_SOUND_BYTES = 250 * 1024 * 1024
MAX_NAME_LENGTH = 100
MAX_CUSTOM_ENTRIES = 500
_ITEM_PREFIXES = ("role.", "state.", "landmark.", "object.", "class.", "fmt.", "nvdaSound.")
_SAFE_SOUND_NAME = re.compile(r"[^<>:\"/\\|?*\x00-\x1f]+\.wav", re.IGNORECASE)
_MAX_VALUE_LENGTH = 200


class PackageError(Exception):
	"""A file that cannot be read as a ClassicSpeech scheme package."""


def _plain_value(value):
	"""Return ``value`` if it is a short plain setting value, otherwise None."""
	if isinstance(value, bool) or value is None:
		return value
	if isinstance(value, (int, float)):
		return value
	if isinstance(value, str) and len(value) <= _MAX_VALUE_LENGTH:
		return value
	return None


def _plain_settings(settings) -> dict:
	if not isinstance(settings, dict):
		return {}
	clean = {}
	for key, value in settings.items():
		if isinstance(key, str) and len(key) <= _MAX_VALUE_LENGTH:
			value = _plain_value(value)
			if value is not None or settings.get(key) is None:
				clean[key] = value
	return clean


def clean_voice_record(record) -> dict:
	"""Return a voice record from a shared file with only plain setting values."""
	if not isinstance(record, dict):
		return {}
	if isinstance(record.get("baseline"), dict) or isinstance(record.get("overrides"), dict):
		return {"baseline": _plain_settings(record.get("baseline")), "overrides": _plain_settings(record.get("overrides"))}
	# Older flat records hold the settings directly.
	return _plain_settings(record)


def _clean_item(settings) -> dict:
	clean = normalize_item_settings(settings)
	voice = clean.get("voice")
	if voice:
		by_synth = {}
		for synth_name, record in voice.get("bySynth", {}).items():
			record = clean_voice_record(record)
			if record and len(synth_name) <= _MAX_VALUE_LENGTH:
				by_synth[synth_name] = record
		voice["bySynth"] = by_synth
		voice["engine"] = str(voice.get("engine") or "")[:_MAX_VALUE_LENGTH]
		clean = normalize_item_settings(clean)
	return clean


def _member_name(source, used) -> str:
	base, _extension = os.path.splitext(os.path.basename(source))
	base = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "_", base).strip(" .") or "sound"
	candidate = f"{SOUNDS_PREFIX}{base}.wav"
	counter = 2
	while candidate.lower() in used:
		candidate = f"{SOUNDS_PREFIX}{base} {counter}.wav"
		counter += 1
	used.add(candidate.lower())
	return candidate


def write_scheme_package(path, name, scheme) -> list:
	"""Write ``scheme`` and its sounds to package ``path``.

	Returns the sound files that could not be found; their items keep only
	their voices. The package is written to a temporary file first, so a
	failure leaves any existing file at ``path`` unchanged.
	"""
	members = {}
	used = set()
	missing = []
	items = {}
	for item_id, settings in (scheme.get("items") or {}).items():
		clean = normalize_item_settings(settings)
		sound = clean.get("sound")
		if sound:
			if sound not in members:
				if os.path.isfile(sound):
					members[sound] = _member_name(sound, used)
				else:
					members[sound] = None
					missing.append(sound)
			if members[sound] is None:
				clean.pop("sound", None)
				clean.pop("soundOnly", None)
				clean = normalize_item_settings(clean)
			else:
				clean["sound"] = members[sound]
		if clean:
			items[str(item_id)] = clean
	manifest = {
		"format": PACKAGE_FORMAT,
		"version": 1,
		"name": str(name),
		"items": items,
		"custom": normalize_custom(scheme.get("custom")),
	}
	folder = os.path.dirname(os.path.abspath(path))
	handle, temporary = tempfile.mkstemp(prefix=".classicspeech-", suffix=".tmp", dir=folder)
	os.close(handle)
	try:
		with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
			archive.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent="\t"))
			for source, member in members.items():
				if member:
					archive.write(source, member)
		os.replace(temporary, path)
	except BaseException:
		try:
			os.remove(temporary)
		except OSError:
			pass
		raise
	return missing


def _copy_limited(source, destination, limit) -> int:
	copied = 0
	while True:
		chunk = source.read(64 * 1024)
		if not chunk:
			return copied
		copied += len(chunk)
		if copied > limit:
			raise PackageError("A sound in the package is larger than it claims.")
		destination.write(chunk)


def read_scheme_package(path, folder):
	"""Read package ``path``, extracting its sounds into ``folder``.

	Returns ``(name, scheme)`` with absolute sound paths inside ``folder``.
	Raises PackageError when ``path`` is not a ClassicSpeech scheme package.
	Items with unsafe or oversized sounds keep only their voices.
	"""
	try:
		archive = zipfile.ZipFile(path)
	except (OSError, zipfile.BadZipFile) as error:
		raise PackageError("The file is not a ClassicSpeech scheme package.") from error
	with archive:
		try:
			info = archive.getinfo(MANIFEST_NAME)
		except KeyError as error:
			raise PackageError("The file is not a ClassicSpeech scheme package.") from error
		if info.file_size > MAX_MANIFEST_BYTES:
			raise PackageError("The package description is too large.")
		try:
			manifest = json.loads(archive.read(info).decode("utf-8"))
		except (ValueError, UnicodeDecodeError) as error:
			raise PackageError("The package description is damaged.") from error
		if not isinstance(manifest, dict) or manifest.get("format") != PACKAGE_FORMAT:
			raise PackageError("The file is not a ClassicSpeech scheme package.")
		members = {member.filename: member for member in archive.infolist()}
		sounds_folder = os.path.join(folder, "Sounds")
		extracted = {}
		targets = set()
		total = 0
		items = {}
		raw_items = manifest.get("items") if isinstance(manifest.get("items"), dict) else {}
		for item_id, settings in raw_items.items():
			item_id = str(item_id)
			if len(item_id) > _MAX_VALUE_LENGTH or not item_id.startswith(_ITEM_PREFIXES):
				continue
			clean = _clean_item(settings)
			sound = clean.get("sound")
			if sound:
				if sound not in extracted:
					target = ""
					member = members.get(sound)
					file_name = sound[len(SOUNDS_PREFIX):] if sound.startswith(SOUNDS_PREFIX) else ""
					if (
						member is not None
						and _SAFE_SOUND_NAME.fullmatch(file_name)
						and not file_name.startswith(".")
						and member.file_size <= MAX_SOUND_BYTES
						and total + member.file_size <= MAX_TOTAL_SOUND_BYTES
					):
						os.makedirs(sounds_folder, exist_ok=True)
						base, extension = os.path.splitext(file_name)
						target = os.path.join(sounds_folder, file_name)
						counter = 2
						# Windows file names ignore case, so a.wav and A.wav must not share a file.
						while target.lower() in targets:
							target = os.path.join(sounds_folder, f"{base} {counter}{extension}")
							counter += 1
						targets.add(target.lower())
						with archive.open(member) as source, open(target, "wb") as destination:
							total += _copy_limited(source, destination, MAX_SOUND_BYTES)
					extracted[sound] = target
				if extracted[sound]:
					clean["sound"] = extracted[sound]
				else:
					clean.pop("sound", None)
					clean.pop("soundOnly", None)
					clean = normalize_item_settings(clean)
			if clean:
				items[item_id] = clean
	name = " ".join(str(manifest.get("name") or "").split())[:MAX_NAME_LENGTH]
	if not name:
		name = os.path.splitext(os.path.basename(path))[0][:MAX_NAME_LENGTH] or "Imported scheme"
	custom = {
		kind: [value for value in values if len(value) <= _MAX_VALUE_LENGTH][:MAX_CUSTOM_ENTRIES]
		for kind, values in normalize_custom(manifest.get("custom")).items()
	}
	return name, {"items": items, "custom": custom}
