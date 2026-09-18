"""Catalog of every Speech and Sound Scheme item and the categories that organize them.

Item identifiers are stable strings stored in the scheme data:

* ``role.<ROLE>``                 NVDA object role (control type), e.g. ``role.LINK``
* ``role.HEADING.<level>``        one heading level
* ``landmark.<name>``             one ARIA landmark type, e.g. ``landmark.main``
* ``state.<STATE>``               an NVDA object state, e.g. ``state.CHECKED``
* ``state.<STATE>.off``           the negated state NVDA speaks, e.g. "not checked"
* ``object.unlabeledGraphic``     a graphic without a name
* ``class.<windowClassName>``     objects in a window class the user added
* ``fmt.<attribute>``             a document-formatting announcement
* ``fmt.fontName.<name>``         one specific font, lower case
* ``fmt.fontSize.<number>``       one specific font size
* ``fmt.styleName.<name>``        one specific document style, lower case

Categories mirror the groups of NVDA's Document Formatting panel first, then the
object categories, so an item can be found where a user expects it. An item may
be listed in more than one category (Links appear under Elements and under
Object types); both entries edit the same settings.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..localization import _

#: The voice applies only to the announcement word(s) for the item.
SCOPE_ANNOUNCEMENT = "announcement"
#: The voice applies to the announcement and the text that has the formatting
#: or belongs to the element (bold text, link text, heading text).
SCOPE_TEXT = "text"
#: The voice applies to the whole spoken description of the object.
SCOPE_OBJECT = "object"


@dataclass(frozen=True)
class SchemeItem:
	item_id: str
	label: str
	voice_scope: str = SCOPE_ANNOUNCEMENT
	description: str = ""


@dataclass
class SchemeCategory:
	category_id: str
	label: str
	items: list = field(default_factory=list)
	#: Shown in the Voice Profiles "Document and web formatting" view.
	formatting: bool = False
	#: Users may add their own entries (fonts, font sizes, window classes).
	custom_kind: str = ""


def _role_members():
	try:
		import controlTypes
		return list(controlTypes.Role)
	except Exception:
		return []


def _state_members():
	try:
		import controlTypes
		return list(controlTypes.State)
	except Exception:
		return []


def _member_display(member) -> str:
	text = ""
	try:
		text = str(getattr(member, "displayString", "") or "")
	except Exception:
		text = ""
	if text.strip():
		return text.strip()
	try:
		import controlTypes
		for module_name, table_name in (("role", "_roleLabels"), ("state", "_stateLabels")):
			table = getattr(getattr(controlTypes, module_name, None), table_name, None) or {}
			label = table.get(member)
			if label:
				return str(label)
	except Exception:
		pass
	return str(getattr(member, "name", member)).replace("_", " ").lower()


def _negative_display(member) -> str:
	try:
		text = str(getattr(member, "negativeDisplayString", "") or "")
		if text.strip():
			return text.strip()
	except Exception:
		pass
	try:
		import controlTypes
		labels = getattr(getattr(controlTypes, "state", None), "_negativeStateLabels", {}) or {}
		if member in labels:
			return str(labels[member])
	except Exception:
		pass
	return _("not {state}").format(state=_member_display(member))


#: States NVDA speaks in the negative (see controlTypes._negativeStateLabels).
NEGATED_STATE_NAMES = ("SELECTED", "PRESSED", "CHECKED", "DROPTARGET", "ON", "SORTED")

LANDMARK_LABELS = (
	("banner", _("Banner landmark")),
	("complementary", _("Complementary landmark")),
	("contentinfo", _("Content information landmark")),
	("form", _("Form landmark")),
	("main", _("Main landmark")),
	("navigation", _("Navigation landmark")),
	("search", _("Search landmark")),
)

#: Common font sizes, in points. Users may add others.
DEFAULT_FONT_SIZES = ("8", "9", "10", "10.5", "11", "12", "14", "16", "18", "20", "22", "24", "26", "28", "36", "48", "72")


def role_item_id(role) -> str:
	return f"role.{getattr(role, 'name', role)}"


def heading_level_item_id(level) -> str:
	return f"role.HEADING.{int(level)}"


def state_item_id(state, negative=False) -> str:
	suffix = ".off" if negative else ""
	return f"state.{getattr(state, 'name', state)}{suffix}"


def landmark_item_id(landmark: str) -> str:
	return f"landmark.{str(landmark).strip().lower()}"


def normalize_font_name(name) -> str:
	return " ".join(str(name or "").split()).strip().lower()


def font_name_item_id(name) -> str:
	return f"fmt.fontName.{normalize_font_name(name)}"


def normalize_font_size(text):
	"""Return the numeric part of a font size ("12 pt" -> "12", "10.50" -> "10.5")."""
	match = re.search(r"\d+(?:[.,]\d+)?", str(text or ""))
	if not match:
		return ""
	value = match.group(0).replace(",", ".")
	try:
		number = float(value)
	except ValueError:
		return ""
	if number.is_integer():
		return str(int(number))
	return ("%g" % number)


def font_size_item_id(size) -> str:
	return f"fmt.fontSize.{normalize_font_size(size)}"


def style_name_item_id(name) -> str:
	return f"fmt.styleName.{normalize_font_name(name)}"


def normalize_window_class(name) -> str:
	return str(name or "").strip()


def window_class_item_id(name) -> str:
	return f"class.{normalize_window_class(name)}"


def custom_entry_label(kind: str, value: str) -> str:
	if kind == "fonts":
		return _("Font: {name}").format(name=value)
	if kind == "fontSizes":
		return _("Font size {size}").format(size=value)
	if kind == "classes":
		return _("Window class {name}").format(name=value)
	if kind == "styles":
		return _("Style: {name}").format(name=value)
	return value


def custom_entry_item_id(kind: str, value: str) -> str:
	if kind == "fonts":
		return font_name_item_id(value)
	if kind == "fontSizes":
		return font_size_item_id(value)
	if kind == "classes":
		return window_class_item_id(value)
	if kind == "styles":
		return style_name_item_id(value)
	raise KeyError(kind)


def _fmt(item_id, label, scope=SCOPE_TEXT, description=""):
	return SchemeItem(item_id, label, scope, description)


def _announcement(item_id, label, description=""):
	return SchemeItem(item_id, label, SCOPE_ANNOUNCEMENT, description)


def _font_items():
	return [
		_fmt("fmt.fontName", _("Font name changes (any font)"), SCOPE_ANNOUNCEMENT,
			_("NVDA announces the new font name. Specific fonts are listed separately.")),
		_fmt("fmt.fontSize", _("Font size changes (any size)"), SCOPE_ANNOUNCEMENT,
			_("NVDA announces the new font size. Specific sizes are listed separately.")),
		_fmt("fmt.bold", _("Bold")),
		_announcement("fmt.bold.off", _("No longer bold")),
		_fmt("fmt.italic", _("Italic")),
		_announcement("fmt.italic.off", _("No longer italic")),
		_fmt("fmt.underline", _("Underlined")),
		_announcement("fmt.underline.off", _("No longer underlined")),
		_fmt("fmt.strikethrough", _("Strikethrough")),
		_fmt("fmt.doubleStrikethrough", _("Double strikethrough")),
		_announcement("fmt.strikethrough.off", _("No longer strikethrough")),
		_fmt("fmt.hidden", _("Hidden text")),
		_announcement("fmt.hidden.off", _("No longer hidden")),
		_fmt("fmt.superscript", _("Superscript")),
		_fmt("fmt.subscript", _("Subscript")),
		_announcement("fmt.baseline", _("Back to the baseline (not superscript or subscript)")),
		_fmt("fmt.strong", _("Strong (emphasis)")),
		_announcement("fmt.strong.off", _("No longer strong")),
		_fmt("fmt.emphasised", _("Emphasised")),
		_announcement("fmt.emphasised.off", _("No longer emphasised")),
		_fmt("fmt.marked", _("Highlighted (marked) text")),
		_announcement("fmt.marked.off", _("No longer marked")),
		_fmt("fmt.highlightColor", _("Highlighted in a color")),
		_announcement("fmt.highlightColor.off", _("No longer highlighted")),
		_fmt("fmt.style", _("Style changes (any style)")),
		_announcement("fmt.style.default", _("Default style")),
		_fmt("fmt.color", _("Text color changes")),
		_fmt("fmt.backgroundColor", _("Background color changes")),
		_announcement("fmt.backgroundPattern", _("Background pattern")),
	]


def _document_information_items():
	return [
		_fmt("fmt.comment", _("Comments")),
		_fmt("fmt.comment.draft", _("Draft comments")),
		_fmt("fmt.comment.resolved", _("Resolved comments")),
		_announcement("fmt.comment.off", _("Leaving a comment")),
		_fmt("fmt.bookmark", _("Bookmarks")),
		_announcement("fmt.bookmark.off", _("Leaving a bookmark")),
		_fmt("fmt.inserted", _("Inserted text (editor revision)")),
		_announcement("fmt.inserted.off", _("No longer inserted")),
		_fmt("fmt.deleted", _("Deleted text (editor revision)")),
		_announcement("fmt.deleted.off", _("No longer deleted")),
		_fmt("fmt.revised", _("Revised text")),
		_announcement("fmt.revised.off", _("No longer revised")),
		_fmt("fmt.spellingError", _("Spelling errors")),
		_announcement("fmt.spellingError.off", _("Leaving a spelling error")),
		_fmt("fmt.grammarError", _("Grammar errors")),
		_announcement("fmt.grammarError.off", _("Leaving a grammar error")),
	]


def _pages_and_spacing_items():
	return [
		_announcement("fmt.page", _("Page numbers")),
		_announcement("fmt.section", _("Section numbers")),
		_announcement("fmt.textColumn", _("Text columns")),
		_announcement("fmt.sectionBreak", _("Section breaks")),
		_announcement("fmt.columnBreak", _("Column breaks")),
		_announcement("fmt.lineNumber", _("Line numbers")),
		_announcement("fmt.lineIndentation", _("Line indentation")),
		_announcement("fmt.paragraphIndent", _("Paragraph indentation")),
		_announcement("fmt.lineSpacing", _("Line spacing")),
		_fmt("fmt.align.left", _("Alignment: left")),
		_fmt("fmt.align.center", _("Alignment: center")),
		_fmt("fmt.align.right", _("Alignment: right")),
		_fmt("fmt.align.justify", _("Alignment: justified")),
		_fmt("fmt.align.other", _("Alignment: other (distributed, fill, general)")),
		_announcement("fmt.verticalAlign", _("Vertical alignment")),
		_announcement("fmt.linePrefix", _("List bullets and numbers")),
	]


def _table_items():
	return [
		SchemeItem("role.TABLE", _("Tables"), SCOPE_TEXT),
		_announcement("fmt.tableCellCoords", _("Table cell coordinates (row and column numbers)")),
		_announcement("fmt.tableHeaders", _("Table row and column headers")),
		_announcement("fmt.cellBorders", _("Cell borders")),
	]


def _element_items():
	items = [
		SchemeItem("role.HEADING", _("Headings (all levels)"), SCOPE_TEXT),
	]
	items.extend(
		SchemeItem(heading_level_item_id(level), _("Heading level {level}").format(level=level), SCOPE_TEXT)
		for level in range(1, 7)
	)
	items.extend([
		SchemeItem("role.LINK", _("Links"), SCOPE_TEXT),
		SchemeItem("state.VISITED", _("Visited links"), SCOPE_ANNOUNCEMENT),
		SchemeItem("state.INTERNAL_LINK", _("Same page links"), SCOPE_ANNOUNCEMENT),
		SchemeItem("role.GRAPHIC", _("Graphics"), SCOPE_TEXT),
		SchemeItem("object.unlabeledGraphic", _("Graphics without a label"), SCOPE_ANNOUNCEMENT),
		SchemeItem("role.LIST", _("Lists"), SCOPE_TEXT),
		SchemeItem("role.LISTITEM", _("List items"), SCOPE_TEXT),
		SchemeItem("role.BLOCKQUOTE", _("Block quotes"), SCOPE_TEXT),
		SchemeItem("role.GROUPING", _("Groupings"), SCOPE_TEXT),
		SchemeItem("role.ARTICLE", _("Articles"), SCOPE_TEXT),
		SchemeItem("role.FRAME", _("Frames"), SCOPE_TEXT),
		SchemeItem("role.INTERNALFRAME", _("Inline frames"), SCOPE_TEXT),
		SchemeItem("role.FIGURE", _("Figures"), SCOPE_TEXT),
		SchemeItem("role.CAPTION", _("Captions"), SCOPE_TEXT),
		SchemeItem("state.CLICKABLE", _("Clickable"), SCOPE_ANNOUNCEMENT),
		SchemeItem("role.FORM", _("Forms"), SCOPE_TEXT),
		SchemeItem("role.MATH", _("Math"), SCOPE_ANNOUNCEMENT),
	])
	return items


def _landmark_items():
	items = [
		SchemeItem("role.LANDMARK", _("Landmarks (all types)"), SCOPE_TEXT),
		SchemeItem("role.REGION", _("Regions"), SCOPE_TEXT),
	]
	items.extend(SchemeItem(landmark_item_id(name), label, SCOPE_TEXT) for name, label in LANDMARK_LABELS)
	return items


def _role_items():
	items = []
	for role in _role_members():
		name = getattr(role, "name", "")
		if not name:
			continue
		label = _member_display(role)
		items.append(SchemeItem(role_item_id(role), label, SCOPE_OBJECT))
	items.sort(key=lambda item: item.label.lower())
	return items


def _state_items():
	items = []
	for state in _state_members():
		name = getattr(state, "name", "")
		if not name:
			continue
		items.append(SchemeItem(state_item_id(state), _member_display(state), SCOPE_ANNOUNCEMENT))
		if name in NEGATED_STATE_NAMES:
			items.append(SchemeItem(state_item_id(state, negative=True), _negative_display(state), SCOPE_ANNOUNCEMENT))
	items.sort(key=lambda item: item.label.lower())
	return items


def _special_object_items():
	unknown_label = _("Unknown objects")
	return [
		SchemeItem("role.UNKNOWN", unknown_label, SCOPE_OBJECT),
		SchemeItem("object.unlabeledGraphic", _("Graphics without a label"), SCOPE_ANNOUNCEMENT),
		SchemeItem("role.GRAPHIC", _("Graphics"), SCOPE_OBJECT),
	]


def build_categories(custom_entries=None, installed_fonts=()):
	"""Return the ordered category list.

	``custom_entries`` is the scheme store's ``{"fonts": [...], "fontSizes": [...],
	"classes": [...]}`` mapping. ``installed_fonts`` optionally lists font face names
	to offer without typing them.
	"""
	custom_entries = custom_entries or {}
	fonts = {}
	for name in list(installed_fonts or ()) + list(custom_entries.get("fonts", ())):
		key = normalize_font_name(name)
		if key and key not in fonts:
			fonts[key] = str(name).strip()
	sizes = []
	for size in list(DEFAULT_FONT_SIZES) + list(custom_entries.get("fontSizes", ())):
		value = normalize_font_size(size)
		if value and value not in sizes:
			sizes.append(value)
	sizes.sort(key=lambda value: float(value))
	classes = []
	for name in custom_entries.get("classes", ()):
		value = normalize_window_class(name)
		if value and value not in classes:
			classes.append(value)
	styles = {}
	for name in custom_entries.get("styles", ()):
		key = normalize_font_name(name)
		if key and key not in styles:
			styles[key] = str(name).strip()

	categories = [
		SchemeCategory("font", _("Font and text formatting"), _font_items(), formatting=True),
		SchemeCategory(
			"fontNames",
			_("Specific font names"),
			[
				SchemeItem(font_name_item_id(key), custom_entry_label("fonts", label), SCOPE_TEXT)
				for key, label in sorted(fonts.items(), key=lambda pair: pair[1].lower())
			],
			formatting=True,
			custom_kind="fonts",
		),
		SchemeCategory(
			"fontSizes",
			_("Specific font sizes"),
			[SchemeItem(font_size_item_id(size), custom_entry_label("fontSizes", size), SCOPE_TEXT) for size in sizes],
			formatting=True,
			custom_kind="fontSizes",
		),
		SchemeCategory(
			"styles",
			_("Specific styles"),
			[
				SchemeItem(style_name_item_id(key), custom_entry_label("styles", label), SCOPE_TEXT)
				for key, label in sorted(styles.items(), key=lambda pair: pair[1].lower())
			],
			formatting=True,
			custom_kind="styles",
		),
		SchemeCategory("documentInformation", _("Document information"), _document_information_items(), formatting=True),
		SchemeCategory("pagesAndSpacing", _("Pages and spacing"), _pages_and_spacing_items(), formatting=True),
		SchemeCategory("tables", _("Table information"), _table_items(), formatting=True),
		SchemeCategory("elements", _("Elements (documents and web pages)"), _element_items(), formatting=True),
		SchemeCategory("landmarks", _("Landmarks and regions"), _landmark_items(), formatting=True),
		SchemeCategory("roles", _("Object types (control types and roles)"), _role_items()),
		SchemeCategory("states", _("Object states"), _state_items()),
		SchemeCategory("specialObjects", _("Unknown and unlabeled objects"), _special_object_items()),
		SchemeCategory(
			"classes",
			_("Window classes"),
			[SchemeItem(window_class_item_id(name), custom_entry_label("classes", name), SCOPE_OBJECT) for name in classes],
			custom_kind="classes",
		),
	]
	return categories


def item_index(categories):
	"""Map item id to the first catalog entry that defines it."""
	index = {}
	for category in categories:
		for item in category.items:
			index.setdefault(item.item_id, item)
	return index


def describe_item_id(item_id: str) -> str:
	"""Return a readable label for an item id, even one not in the current catalog."""
	for category in build_categories():
		for item in category.items:
			if item.item_id == item_id:
				return item.label
	if item_id.startswith("fmt.fontName."):
		return custom_entry_label("fonts", item_id[len("fmt.fontName."):])
	if item_id.startswith("fmt.fontSize."):
		return custom_entry_label("fontSizes", item_id[len("fmt.fontSize."):])
	if item_id.startswith("class."):
		return custom_entry_label("classes", item_id[len("class."):])
	if item_id.startswith("fmt.styleName."):
		return custom_entry_label("styles", item_id[len("fmt.styleName."):])
	return item_id
