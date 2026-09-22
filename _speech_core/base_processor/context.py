import api
import browseMode
import logHandler

from .debug import should_debug_log

from .. import focus_ancestry
from ..dialog_helpers import object_is_in_dialog

log = logHandler.log

QUERY_SAFE_STATE_NAMES = {
	"selected",
	"checked",
	"halfchecked",
	"pressed",
	"half_pressed",
	"on",
	"expanded",
	"collapsed",
	"readonly",
	"required",
	"invalid_entry",
	"protected",
	"autocomplete",
	"multiline",
}

ROLE_ALIASES = {
	"edit combo": "editcombo",
	"editable combo": "editcombo",
	"list view": "list",
	"listview": "list",
	"tree view": "treeview",
	"tree view item": "treeviewitem",
	"treeview item": "treeviewitem",
	"menu item": "menuitem",
	"popup menu": "menu",
	"popupmenu": "menu",
	"tab control": "tabcontrol",
	"combo box": "combobox",
	"combo-box": "combobox",
	"toggle button": "togglebutton",
	"toggle": "togglebutton",
	"check box": "checkbox",
	"check-box": "checkbox",
	"radio button": "radiobutton",
	"radio-button": "radiobutton",
	"editable text": "editabletext",
	"edit": "editabletext",
	"cell": "tablecell",
}

# Parent spoken role -> compatible focused child roles
ROLE_COMPATIBILITY = {
	"editcombo": {"editabletext"},
	"combobox": {"editabletext"},
	"window": {"editabletext"},
	"list": {"listitem"},
	"treeview": {"treeviewitem"},
	# Do not treat root menu as a normal role compatibility case.
	# Menu is a navigation/container marker; menu items still process normally.
	"table": {"tablecell"},
	"tabcontrol": {"tab"},
	"propertypage": {
		"editabletext",
		"combobox",
		"checkbox",
		"radiobutton",
		"button",
		"list",
		"listitem",
		"treeview",
		"treeviewitem",
		"tabcontrol",
		"tab",
		"slider",
		"spinbutton",
	},
}


MENU_CONTEXT_ROLE_KEYS = {
	"menu",
	"menubar",
	"menuitem",
	"checkmenuitem",
	"radiomenuitem",
}

ROOT_MENU_NAV_MARKER_ROLES = {"menu"}

FORM_CONTROL_ROLE_KEYS = {
	"checkbox",
	"radiobutton",
	"editcombo",
	"combobox",
	"editabletext",
	"button",
	"togglebutton",
	"slider",
	"spinbutton",
}

#: Roles whose focused object *is* the item the user moved to, so the first
#: spoken string is that item's own name rather than a container label. A tree
#: view or list can hold items named after NVDA's own vocabulary; ClassicSpeech's
#: Speech and Sound Schemes tree is entirely made of them ("menu", "selected",
#: "tree view"). Those names must survive as names.
ITEM_CONTROL_ROLE_KEYS = {
	"treeviewitem",
	"listitem",
	"menuitem",
	"checkmenuitem",
	"radiomenuitem",
	"tab",
	"tablecell",
	"tablerow",
	"dataitem",
}

#: Every role whose accessible name is protected from role/state classification.
NAMED_CONTROL_ROLE_KEYS = FORM_CONTROL_ROLE_KEYS | ITEM_CONTROL_ROLE_KEYS


class ContextAnalyzer:
	def __init__(self, owner):
		self.owner = owner

	def __getattr__(self, name):
		return getattr(self.owner, name)

	def _normalize_role_key(self, value):
		if value is None:
			return None
		if isinstance(value, (list, tuple)):
			value = " ".join(str(v) for v in value if v is not None)
		key = str(value).strip().lower()
		if not key:
			return None
		key = key.replace("_", " ").replace("-", " ")
		key = " ".join(key.split())
		if key in ROLE_ALIASES:
			return ROLE_ALIASES[key]
		return key.replace(" ", "")

	def _normalize_accessible_label_text(self, text):
		if text is None:
			return ""
		try:
			value = str(text)
		except Exception:
			return ""
		value = value.replace("&", "")
		value = value.strip().rstrip(":")
		return " ".join(value.lower().split())

	def _should_protect_leading_control_name(self, tokens):
		"""Return True when the first spoken string is the focused control's own name.

		This prevents English names that also exist in NVDA's role and state map
		("Style", "Font name", "menu", "selected", ...) from being misclassified as
		a semantic role or state and then dropped or reordered. Keep this
		deliberately narrow: dialog controls and the items inside them, and only
		when the first string matches the focused object's accessible name or
		display text.
		"""
		focus = api.getFocusObject()
		if not focus:
			return False
		if self._get_object_role_key(focus) not in NAMED_CONTROL_ROLE_KEYS:
			return False
		try:
			if not object_is_in_dialog(focus):
				return False
		except Exception:
			return False

		first_text = ""
		for item in tokens:
			if isinstance(item, str) and item.strip():
				first_text = item
				break
		if not first_text:
			return False

		first_norm = self._normalize_accessible_label_text(first_text)
		if not first_norm:
			return False

		role_text = self._safe_role_text(focus)
		if first_norm == self._normalize_accessible_label_text(role_text):
			return False

		for attr_name in ("name", "displayText", "windowText"):
			label = self._safe_obj_str_attr(focus, attr_name, "")
			if label and first_norm == self._normalize_accessible_label_text(label):
				if should_debug_log():
					log.debug(f"Protecting leading control name from role classification: {first_text!r}")
				return True

		return False


	def _get_object_role_key(self, obj):
		if not obj:
			return None
		role = getattr(obj, "role", None)
		if role is None:
			return None
		role_name = getattr(role, "name", None)
		if role_name:
			return self._normalize_role_key(role_name)
		return self._normalize_role_key(role)

	def _get_focus_role_key(self):
		return self._get_object_role_key(api.getFocusObject())

	def _lineage_role_key(self, lineage, index):
		return self._normalize_role_key_for_role(focus_ancestry.role_at(lineage, index))

	def _normalize_role_key_for_role(self, role):
		if role is None:
			return None
		role_name = getattr(role, "name", None)
		if role_name:
			return self._normalize_role_key(role_name)
		return self._normalize_role_key(role)

	def _object_or_ancestor_has_role(self, obj, role_keys, max_depth=8):
		lineage = focus_ancestry.lineage_for(obj, max_depth)
		return any(
			self._lineage_role_key(lineage, index) in role_keys
			for index in range(len(lineage))
		)

	def _is_native_menu_context(self, obj, max_depth=8):
		"""Return True only for menu contexts that are not owned by a
		browse-mode document treeInterceptor. This keeps native app menus
		eligible while preventing ARIA/web menus from bypassing the browse
		mode guard.
		"""
		lineage = focus_ancestry.lineage_for(obj, max_depth)
		for index, current in enumerate(lineage):
			role_key = self._lineage_role_key(lineage, index)
			if role_key in MENU_CONTEXT_ROLE_KEYS:
				ti = self._safe_obj_attr(current, "treeInterceptor", None)
				if ti and isinstance(ti, browseMode.BrowseModeDocumentTreeInterceptor):
					return False
				return True
		return False

	def _roles_compatible(self, token_role_key, focus_role_key):
		if not token_role_key or not focus_role_key:
			return False
		if token_role_key == focus_role_key:
			return True
		return focus_role_key in ROLE_COMPATIBILITY.get(token_role_key, set())

	def _get_focus_context(self):
		"""
		Coarse context for hotkey handling.
		'menu' if focus or ancestor is menu-ish, otherwise 'dialog'.
		"""
		lineage = focus_ancestry.lineage_for(api.getFocusObject(), 8)
		for index in range(len(lineage)):
			if self._lineage_role_key(lineage, index) in MENU_CONTEXT_ROLE_KEYS:
				return "menu"
		return "dialog"

	# -------------------------
	# Spelling guard helpers
	# -------------------------
