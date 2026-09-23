import api

from ..dialog_helpers import focused_button_default_status
from ..localization import pgettext
from ..tokens import TOKEN_ROLE, TOKEN_STATE, token

#: Role tokens a default button can have, by NVDA role name so any language works.
_BUTTON_ROLE_KEYS = frozenset({"button", "splitbutton"})
#: English role labels, for a role token without an NVDA role name.
_BUTTON_ROLE_LABELS = frozenset({"button", "split button"})


def _is_button_role_token(tok) -> bool:
	if getattr(tok, "kind", None) != TOKEN_ROLE:
		return False
	raw = getattr(tok, "raw", None)
	if isinstance(raw, str) and raw.strip().lower() in _BUTTON_ROLE_KEYS:
		return True
	try:
		return tok.text().strip().lower() in _BUTTON_ROLE_LABELS
	except Exception:
		return False


def _default_state_label() -> str:
	# Translators: spoken with a dialog's default button when focus reaches it,
	# as in "OK, default, button" (Announce default button in dialogs).
	return pgettext("default button", "default")


class DefaultButtonTokenInserter:
	def __init__(self, owner):
		self.owner = owner

	def __getattr__(self, name):
		return getattr(self.owner, name)

	def _role_order_index_for_default_token(self):
		try:
			profile = self.verbosity.get_profile_config()
			order = profile.get("order", []) if isinstance(profile, dict) else []
			if TOKEN_ROLE in order:
				return int(order.index(TOKEN_ROLE))
		except Exception:
			pass
		return 1

	def _insert_focused_default_button_token(self, semantic_tokens, focus=None):
		"""Insert a speakable default-state token before role for the focused default button.

		This intentionally announces only when focus lands on the default button:
		``OK, default, button``, or ``Open, default, split button`` in the
		Windows file dialog.  It does not announce the dialog default merely
		because a dialog opened.
		"""
		try:
			if not bool(getattr(self.verbosity, "announce_default_button", False)):
				return semantic_tokens
		except Exception:
			return semantic_tokens

		# Only decorate actual focused-button description sequences.
		# Action-only messages such as ``pressed`` arrive while focus is still
		# on the default button, but they should not become ``default pressed``.
		# Check the cheap token shape first: the dialog default-button lookup
		# is expensive and is only needed for a spoken button role.
		if not any(_is_button_role_token(tok) for tok in semantic_tokens or []):
			return semantic_tokens

		# Avoid duplicate default tokens if a future NVDA/core sequence exposes one.
		label = _default_state_label()
		for tok in semantic_tokens or []:
			if getattr(tok, "kind", None) != TOKEN_STATE:
				continue
			try:
				if getattr(tok, "raw", None) == "default" or tok.text().strip().lower() in {"default", label.lower()}:
					return semantic_tokens
			except Exception:
				continue

		focus = focus or api.getFocusObject()
		try:
			is_button, is_default, _default_name = focused_button_default_status(focus)
		except Exception:
			return semantic_tokens

		if not is_button or not is_default:
			return semantic_tokens

		default_tok = token(
			TOKEN_STATE,
			raw="default",
			spoken=label,
			source=[],
			meta={
				"orderIndex": self._role_order_index_for_default_token(),
				"suppressRename": True,
				"suppressProfileLabelMute": True,
			},
		)

		result = []
		inserted = False
		for tok in semantic_tokens:
			if not inserted and getattr(tok, "kind", None) == TOKEN_ROLE:
				result.append(default_tok)
				inserted = True
			result.append(tok)

		return result

	# -------------------------
	# Main processing
	# -------------------------
