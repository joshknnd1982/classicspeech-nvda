# _speech_core/cancelable.py
"""Helpers for NVDA's focus-scoped speech cancellation markers.

NVDA attaches a ``_CancellableSpeechCommand`` to every focus announcement. Its
contract is "drop this utterance if the focus event that produced it has
expired", and NVDA's speech manager honours it by removing that utterance *and
everything still queued before it* (``SpeechManager._checkForCancellations``).

That contract belongs to the utterance NVDA built. Whenever ClassicSpeech keeps
part of a sequence and speaks it again later, or merges it into the
announcement of a different object, the marker no longer describes the speech it
travels with: it can expire and take the current announcement down with it. Such
a sequence is re-emitted without its markers.
"""

import logHandler

log = logHandler.log


def _cancelable_class():
	"""Return NVDA's cancellable speech command class, or None."""
	try:
		from speech.commands import _CancellableSpeechCommand

		return _CancellableSpeechCommand
	except ImportError:
		pass
	try:
		# Older/other NVDA builds exposed it under this name.
		from speech.commands import CancellableSpeech

		return CancellableSpeech
	except ImportError:
		return None


def is_cancelable(item) -> bool:
	"""Return True for one of NVDA's focus cancellation markers."""
	cls = _cancelable_class()
	if cls is not None and isinstance(item, cls):
		return True
	# Duck typing keeps this working if NVDA renames the class again.
	return hasattr(item, "cancelUtterance") and hasattr(item, "isCancelled")


def strip_cancelable(sequence):
	"""Return ``sequence`` without NVDA's focus cancellation markers."""
	try:
		return [item for item in sequence if not is_cancelable(item)]
	except Exception:
		log.debug("ClassicSpeech: failed to strip cancellable speech commands", exc_info=True)
		return list(sequence)


def unwrap_cancelable(sequence):
	"""Recursively unwrap wrapper objects while preserving inner content.

	NVDA's own marker carries no inner sequence, so it is left in place here:
	dropping it inside the processor would disable NVDA's expired-focus
	cancellation for ordinary focus speech.
	"""
	out = []

	for item in sequence:
		inner = getattr(item, "sequence", None) if is_cancelable(item) else None
		if inner:
			try:
				log.debug(f"Unwrapping CancellableSpeech: {inner}")
				out.extend(unwrap_cancelable(inner))
				continue
			except Exception as e:
				log.error(f"Error unwrapping CancellableSpeech: {e}")
		out.append(item)

	return out
