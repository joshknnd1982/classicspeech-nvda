import api
import config
import logHandler

from .debug import should_debug_log

from .. import focus_ancestry
from ..settings import POSITION_MODE_EACH, POSITION_MODE_FIRST, POSITION_MODE_OFF
from ..tokens import TOKEN_POSITION

log = logHandler.log


class PositionModeFilter:
	def __init__(self, owner):
		self.owner = owner
		self._last_position_container = None

	def __getattr__(self, name):
		return getattr(self.owner, name)

	def _get_position_mode(self):
		try:
			mode = str(
				config.conf["classicSpeech"].get("positionMode", POSITION_MODE_EACH)
			).strip().lower()
		except Exception:
			mode = POSITION_MODE_EACH

		if mode not in {POSITION_MODE_OFF, POSITION_MODE_EACH, POSITION_MODE_FIRST}:
			return POSITION_MODE_EACH
		return mode

	def _object_signature(self, obj):
		if not obj:
			return None

		app_name = ""
		try:
			app_module = self._safe_obj_attr(obj, "appModule", None)
			app_name = self._safe_obj_str_attr(app_module, "appName", "")
		except Exception:
			pass

		role_key = self._get_object_role_key(obj)
		name = self._safe_obj_str_attr(obj, "name", "")
		handle = self._safe_obj_attr(obj, "windowHandle", None)
		child_id = self._safe_obj_attr(obj, "IAccessibleChildID", None)

		# Do not include obj.value in the signature. It is volatile and can throw
		# in some UIA-backed controls during focus/menu transitions.
		return (app_name, handle, child_id, role_key, name)

	_CONTAINER_ROLES = frozenset({
		"list",
		"treeview",
		"menu",
		"menubar",
		"tabcontrol",
		"table",
		"toolbar",
		"combobox",
		"listbox",
	})

	def _get_position_container_signature(self, focus):
		if not focus:
			return None

		lineage = focus_ancestry.lineage_for(focus, 8)
		if focus_ancestry.is_focus(focus):
			# The container is an ancestor of the focus; it cannot change while
			# focus stays on the same object, so compute its signature once.
			return focus_ancestry.memoized_for_focus(
				"positionContainerSignature",
				lambda: self._container_signature_from_lineage(focus, lineage),
			)
		return self._container_signature_from_lineage(focus, lineage)

	def _container_signature_from_lineage(self, focus, lineage):
		for index in range(1, len(lineage)):
			role_key = self._normalize_role_key_for_role(focus_ancestry.role_at(lineage, index))
			if role_key in self._CONTAINER_ROLES:
				return self._ancestor_signature(lineage[index])

		if len(lineage) > 1:
			return self._ancestor_signature(lineage[1])

		return self._object_signature(focus)

	def _ancestor_signature(self, container):
		# Moving between items keeps the same container object; its signature
		# (which reads the container name across processes) is fetched once.
		return focus_ancestry.memoized_for_ancestor(
			container, "positionSignature", lambda: self._object_signature(container)
		)

	def _apply_position_mode(self, semantic_tokens, mode_override=None):
		mode = mode_override if mode_override is not None else self._get_position_mode()

		if mode == POSITION_MODE_OFF:
			self._last_position_container = None
			return [
				token for token in semantic_tokens if token.kind != TOKEN_POSITION
			]

		focus = api.getFocusObject()
		try:
			current_container = self._get_position_container_signature(focus)
		except Exception as e:
			if should_debug_log():
				log.debug(f"Position mode: container signature lookup failed: {e}")
			current_container = None

		position_tokens = [
			token for token in semantic_tokens if token.kind == TOKEN_POSITION
		]

		if not position_tokens:
			# Keep remembered container while moving around inside the same container,
			# but clear it once focus genuinely leaves that container.
			if (
				self._last_position_container is not None
				and current_container != self._last_position_container
			):
				if should_debug_log():
					log.debug(
						f"Position mode: clearing remembered container "
						f"{self._last_position_container} -> {current_container}"
					)
				self._last_position_container = None
			return semantic_tokens

		if mode == POSITION_MODE_EACH:
			self._last_position_container = current_container
			return semantic_tokens

		if (
			current_container is not None
			and current_container == self._last_position_container
		):
			return [
				token for token in semantic_tokens if token.kind != TOKEN_POSITION
			]

		self._last_position_container = current_container
		return semantic_tokens

	# -------------------------
	# Hotkey mode
	# -------------------------
