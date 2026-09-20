"""Identify NVDA's own announcement strings for Speech and Sound Scheme items.

NVDA builds formatting, element, role and state announcements in
``speech.speech``. ClassicSpeech never calls those builders twice (several of
them update NVDA's table and tree-level state). Instead it computes the exact
localized strings NVDA uses for the values it was given, and tags the matching
strings in NVDA's own output. A string that does not match is simply left
untagged, so an NVDA wording change can only disable a scheme item, never alter
speech.

Strings are translated with NVDA's core catalog (``builtins._``), which is what
``speech.speech`` itself uses; ClassicSpeech's own ``_`` is add-on specific.
"""
from __future__ import annotations

import builtins

from .catalog import (
	font_name_item_id,
	font_size_item_id,
	heading_level_item_id,
	landmark_item_id,
	role_item_id,
	state_item_id,
	style_name_item_id,
)


def _nv(message: str) -> str:
	translate = builtins.__dict__.get("_")
	if callable(translate):
		try:
			return translate(message)
		except Exception:
			pass
	return message


def _nvn(singular: str, plural: str, count) -> str:
	translate = builtins.__dict__.get("ngettext")
	if callable(translate):
		try:
			return translate(singular, plural, count)
		except Exception:
			pass
	try:
		return singular if int(count) == 1 else plural
	except Exception:
		return plural


def _display(member) -> str:
	try:
		return str(getattr(member, "displayString", "") or "")
	except Exception:
		return ""


def _color_text(value) -> str:
	name = getattr(value, "name", None)
	if isinstance(name, str) and name:
		return name
	return str(value)


class LabelTable:
	"""Ordered mapping of announcement text to scheme item ids (first wins)."""

	__slots__ = ("labels",)

	def __init__(self):
		self.labels = {}

	def add(self, text, *item_ids):
		if not isinstance(text, str) or not text.strip():
			return
		if text in self.labels:
			return
		items = tuple(item_id for item_id in item_ids if item_id)
		if items:
			self.labels[text] = items

	def get(self, text):
		return self.labels.get(text)

	def __bool__(self):
		return bool(self.labels)


# ---------------------------------------------------------------------------
# Roles and states
# ---------------------------------------------------------------------------

def _role(value):
	try:
		import controlTypes
		return controlTypes.Role(value)
	except Exception:
		return value


def role_items(role, *, name=None, level=None, landmark=None, content=None):
	"""Return item ids describing an object or element role, most specific first."""
	items = []
	role = _role(role)
	role_name = getattr(role, "name", "")
	if role_name == "HEADING" and level:
		try:
			items.append(heading_level_item_id(int(level)))
		except (TypeError, ValueError):
			pass
	if role_name == "LANDMARK" and landmark:
		items.append(landmark_item_id(landmark))
	if role_name == "GRAPHIC" and not (name or content):
		items.append("object.unlabeledGraphic")
	if role_name:
		items.append(role_item_id(role))
	return items


def add_state_labels(table: LabelTable, role, real_states, reason, states=None, negative_states=None):
	"""Tag NVDA's state labels exactly as ``processAndLabelStates`` produces them."""
	try:
		import controlTypes
		process = controlTypes.processAndLabelStates
		all_states = list(controlTypes.State)
	except Exception:
		return
	if states is None and not negative_states:
		return
	positive_sentinels = {state: f"\x01+{state.name}" for state in all_states}
	negative_sentinels = {state: f"\x01-{state.name}" for state in all_states}
	try:
		role = _role(role)
		real_states = set(real_states or ())
		positive = set(states or ())
		negative = set(negative_states or ())
		sentinels = process(role, real_states, reason, positive, negative, positive_sentinels, negative_sentinels)
		labels = process(role, real_states, reason, positive, negative)
	except Exception:
		return
	for sentinel, label in zip(sentinels, labels):
		if not isinstance(sentinel, str) or not sentinel.startswith("\x01"):
			continue
		negative_state = sentinel[1] == "-"
		state_name = sentinel[2:]
		table.add(label, state_item_id(state_name, negative=negative_state))


def object_state_items(states):
	"""Scheme items for the states an object is in, whether NVDA says them or not.

	NVDA never speaks some of the states it knows about: it drops Focusable,
	Checkable and Selectable always, and Visited outside a link, among others.
	A user who gives one of those a sound or a voice still means "an object in
	this state", so the object marker carries the states the object is actually
	in. A negated state such as "not checked" stays with NVDA's announcement,
	which is the only place its absence means anything.
	"""
	items = []
	for state in sorted(states or (), key=lambda member: str(getattr(member, "name", member))):
		name = str(getattr(state, "name", "") or "")
		if name:
			items.append(state_item_id(name))
	return items


def add_table_cell_labels(table: LabelTable, values):
	"""Tag row/column numbers and header text that NVDA speaks for table cells."""
	row = values.get("rowNumber")
	column = values.get("columnNumber")
	if values.get("cellCoordsText"):
		table.add(values.get("cellCoordsText"), "fmt.tableCellCoords")
	if row:
		table.add(_nv("row %s") % row, "fmt.tableCellCoords")
	if column:
		table.add(_nv("column %s") % column, "fmt.tableCellCoords")
	for key in ("rowHeaderText", "columnHeaderText"):
		text = values.get(key)
		if isinstance(text, str) and text.strip():
			table.add(text, "fmt.tableHeaders")


def properties_label_table(property_values, reason) -> LabelTable:
	"""Labels for one ``getPropertiesSpeech`` call used for object speech."""
	table = LabelTable()
	if "role" in property_values:
		role = _role(property_values.get("role"))
		level = property_values.get("positionInfo_level")
		items = role_items(role, name=property_values.get("name"), level=level)
		role_text = property_values.get("roleText") or _display(role)
		table.add(role_text, *items)
		if getattr(role, "name", "") == "HEADING" and level:
			table.add(_nv("level %s") % level, *items)
	states = property_values.get("states")
	negative_states = property_values.get("negativeStates", set())
	if states is not None or negative_states:
		state_role = property_values.get("role", property_values.get("_role"))
		real_states = property_values.get("_states", states)
		add_state_labels(table, state_role, real_states, reason, states, negative_states)
	add_table_cell_labels(table, property_values)
	return table


def control_field_label_table(attrs, reason) -> LabelTable:
	"""Labels for one ``getControlFieldSpeech`` call (document and web elements)."""
	table = LabelTable()
	try:
		import controlTypes
		role = _role(attrs.get("role", controlTypes.Role.UNKNOWN))
	except Exception:
		return table
	landmark = attrs.get("landmark")
	level = attrs.get("level")
	items = role_items(role, name=attrs.get("name"), level=level, landmark=landmark, content=attrs.get("content"))
	role_text = attrs.get("roleText")
	if role_text:
		table.add(role_text, *items)
	elif getattr(role, "name", "") == "LANDMARK" and landmark:
		try:
			import aria
			table.add(f"{aria.landmarkRoles[landmark]} {_display(role)}", *items)
		except Exception:
			pass
	else:
		table.add(_display(role), *items)
	if getattr(role, "name", "") == "HEADING" and level:
		table.add(_nv("level %s") % level, *items)
	child_count = attrs.get("_childcontrolcount")
	if getattr(role, "name", "") == "LIST" and child_count:
		try:
			count = int(child_count)
			table.add(_nvn("with %s item", "with %s items", count) % count, *items)
		except (TypeError, ValueError):
			pass
	if getattr(role, "name", "") == "TABLE":
		try:
			from speech import speech as speechModule
			rows = attrs.get("table-rowcount-presentational") or attrs.get("table-rowcount")
			columns = attrs.get("table-columncount-presentational") or attrs.get("table-columncount")
			table.add(speechModule._rowAndColumnCountText(rows, columns), "role.TABLE")
		except Exception:
			pass
	states = attrs.get("states", set())
	add_state_labels(table, role, states, reason, states, set())
	add_table_cell_labels(
		table,
		{
			"rowNumber": attrs.get("table-rownumber-presentational") or attrs.get("table-rownumber"),
			"columnNumber": attrs.get("table-columnnumber-presentational") or attrs.get("table-columnnumber"),
			"rowHeaderText": attrs.get("table-rowheadertext"),
			"columnHeaderText": attrs.get("table-columnheadertext"),
		},
	)
	return table


def element_range_items(attrs):
	"""Items whose voice applies to the text inside a document/web element."""
	try:
		import controlTypes
		role = _role(attrs.get("role", controlTypes.Role.UNKNOWN))
	except Exception:
		return []
	items = role_items(
		role,
		name=attrs.get("name"),
		level=attrs.get("level"),
		landmark=attrs.get("landmark"),
		content=attrs.get("content"),
	)
	# An unlabeled graphic has no text to speak in a voice.
	return [item for item in items if item != "object.unlabeledGraphic"]


# ---------------------------------------------------------------------------
# Format fields
# ---------------------------------------------------------------------------

_SECTION_BREAKS = (
	"continuous section break",
	"new column section break",
	"new page section break",
	"even pages section break",
	"odd pages section break",
)

_TOGGLE_ATTRIBUTES = (
	# (attribute, on text, on item, off text, off item)
	("marked", "marked", "fmt.marked", "not marked", "fmt.marked.off"),
	("strong", "strong", "fmt.strong", "not strong", "fmt.strong.off"),
	("emphasised", "emphasised", "fmt.emphasised", "not emphasised", "fmt.emphasised.off"),
	("bold", "bold", "fmt.bold", "no bold", "fmt.bold.off"),
	("italic", "italic", "fmt.italic", "no italic", "fmt.italic.off"),
	("underline", "underlined", "fmt.underline", "not underlined", "fmt.underline.off"),
	("hidden", "hidden", "fmt.hidden", "not hidden", "fmt.hidden.off"),
	("revision-insertion", "inserted", "fmt.inserted", "not inserted", "fmt.inserted.off"),
	("revision-deletion", "deleted", "fmt.deleted", "not deleted", "fmt.deleted.off"),
)


def _add_table_info_labels(table: LabelTable, attrs, old, extra_detail):
	table_info = attrs.get("table-info")
	if table_info is None:
		return
	try:
		from speech import speech as speechModule
		texts = speechModule.getTableInfoSpeech(table_info, old.get("table-info"), extraDetail=extra_detail)
	except Exception:
		return
	old_info = old.get("table-info")
	new_table = not old_info or table_info.get("table-id") != old_info.get("table-id")
	for index, text in enumerate(texts or ()):
		if index == 0 and new_table:
			table.add(text, "role.TABLE")
		else:
			table.add(text, "fmt.tableCellCoords")


def _add_color_labels(table: LabelTable, attrs, old):
	color = attrs.get("color")
	background = attrs.get("background-color")
	background2 = attrs.get("background-color2")
	background_text = _color_text(background) if background is not None else ""
	if background2:
		background_text = _nv("{color1} to {color2}").format(color1=background_text, color2=_color_text(background2))
	if color and background:
		table.add(
			_nv("{color} on {backgroundColor}").format(color=_color_text(color), backgroundColor=background_text),
			"fmt.color",
			"fmt.backgroundColor",
		)
	if color:
		table.add(_nv("{color}").format(color=_color_text(color)), "fmt.color")
	if background:
		table.add(_nv("{backgroundColor} background").format(backgroundColor=background_text), "fmt.backgroundColor")
	pattern = attrs.get("background-pattern")
	if pattern or old.get("background-pattern") is not None:
		table.add(_nv("background pattern {pattern}").format(pattern=pattern or _nv("none")), "fmt.backgroundPattern")


def _add_alignment_labels(table: LabelTable):
	try:
		from controlTypes import TextAlign, VerticalTextAlign
	except Exception:
		try:
			from controlTypes.formatFields import TextAlign, VerticalTextAlign
		except Exception:
			return
	specific = {"LEFT": "fmt.align.left", "CENTER": "fmt.align.center", "RIGHT": "fmt.align.right", "JUSTIFY": "fmt.align.justify"}
	for member in TextAlign:
		if member.name == "UNDEFINED":
			continue
		table.add(_display(member), specific.get(member.name, "fmt.align.other"))
	for member in VerticalTextAlign:
		if member.name == "UNDEFINED":
			continue
		table.add(_display(member), "fmt.verticalAlign")


def _add_text_position_labels(table: LabelTable):
	try:
		from controlTypes import TextPosition
	except Exception:
		return
	items = {"SUPERSCRIPT": "fmt.superscript", "SUBSCRIPT": "fmt.subscript", "BASELINE": "fmt.baseline"}
	for member in TextPosition:
		item = items.get(member.name)
		if item:
			table.add(_display(member), item)


def format_field_label_table(attrs, old, extra_detail=False) -> LabelTable:
	"""Labels for one ``getFormatFieldSpeech`` call.

	``old`` is a copy of the attribute cache from before NVDA's call, which
	``getFormatFieldSpeech`` updates in place.
	"""
	table = LabelTable()
	get = attrs.get
	_add_table_info_labels(table, attrs, old, extra_detail)
	page = get("page-number")
	if page:
		table.add(_nv("page %s") % page, "fmt.page")
	section = get("section-number")
	if section:
		table.add(_nv("section %s") % section, "fmt.section")
	column_count = get("text-column-count")
	column_number = get("text-column-number")
	if column_number and column_count:
		table.add(_nv("column {0} of {1}").format(column_number, column_count), "fmt.textColumn")
	if column_count:
		try:
			table.add(_nvn("%s column", "%s columns", column_count) % column_count, "fmt.textColumn")
		except Exception:
			pass
	if column_number:
		table.add(_nv("column {columnNumber}").format(columnNumber=column_number), "fmt.textColumn")
	for text in _SECTION_BREAKS:
		table.add(_nv(text), "fmt.sectionBreak")
	table.add(_nv("column break"), "fmt.columnBreak")
	heading_level = get("heading-level")
	if heading_level:
		try:
			table.add(_nv("heading level %d") % int(heading_level), heading_level_item_id(heading_level), "role.HEADING")
		except (TypeError, ValueError):
			pass
	if get("collapsed"):
		try:
			import controlTypes
			table.add(_display(controlTypes.State.COLLAPSED), "state.COLLAPSED")
		except Exception:
			pass
	style = get("style")
	if style:
		table.add(_nv("style %s") % style, style_name_item_id(style), "fmt.style")
	table.add(_nv("default style"), "fmt.style.default", "fmt.style")
	border = get("border-style")
	if border:
		table.add(str(border), "fmt.cellBorders")
	table.add(_nv("no border lines"), "fmt.cellBorders")
	for key in ("font-family", "font-name"):
		value = get(key)
		if value:
			table.add(str(value), font_name_item_id(value), "fmt.fontName")
	size = get("font-size")
	if size:
		table.add(str(size), font_size_item_id(size), "fmt.fontSize")
	_add_color_labels(table, attrs, old)
	line_number = get("line-number")
	if line_number is not None:
		table.add(_nv("line %s") % line_number, "fmt.lineNumber")
	for attribute, on_text, on_item, off_text, off_item in _TOGGLE_ATTRIBUTES:
		table.add(_nv(on_text), on_item)
		table.add(_nv(off_text), off_item)
	revision = get("revision")
	if revision:
		table.add(_nv("revised %s") % revision, "fmt.revised")
	old_revision = old.get("revision")
	if old_revision:
		table.add(_nv("no revised %s") % old_revision, "fmt.revised.off")
	highlight = get("highlight-color")
	if highlight:
		table.add(_nv("highlighted in {color}").format(color=_color_text(highlight)), "fmt.highlightColor")
	table.add(_nv("not highlighted"), "fmt.highlightColor.off")
	table.add(_nv("double strikethrough"), "fmt.doubleStrikethrough")
	table.add(_nv("strikethrough"), "fmt.strikethrough")
	table.add(_nv("no strikethrough"), "fmt.strikethrough.off")
	_add_text_position_labels(table)
	_add_alignment_labels(table)
	for attribute, label, no_label in (
		("left-indent", "left indent", "no left indent"),
		("right-indent", "right indent", "no right indent"),
		("hanging-indent", "hanging indent", "no hanging indent"),
		("first-line-indent", "first line indent", "no first line indent"),
	):
		value = get(attribute)
		if value:
			table.add("%s %s" % (_nv(label), value), "fmt.paragraphIndent")
		table.add(_nv(no_label), "fmt.paragraphIndent")
	line_spacing = get("line-spacing")
	if line_spacing:
		table.add(_nv("line spacing %s") % line_spacing, "fmt.lineSpacing")
	table.add(_nv("link"), "role.LINK")
	table.add(_nv("has draft comment"), "fmt.comment.draft", "fmt.comment")
	table.add(_nv("has resolved comment"), "fmt.comment.resolved", "fmt.comment")
	table.add(_nv("has comment"), "fmt.comment")
	table.add(_nv("out of comment"), "fmt.comment.off")
	table.add(_nv("bookmark"), "fmt.bookmark")
	table.add(_nv("out of bookmark"), "fmt.bookmark.off")
	table.add(_nv("spelling error"), "fmt.spellingError")
	table.add(_nv("out of spelling error"), "fmt.spellingError.off")
	table.add(_nv("grammar error"), "fmt.grammarError")
	table.add(_nv("out of grammar error"), "fmt.grammarError.off")
	line_prefix = get("line-prefix")
	if line_prefix:
		table.add(str(line_prefix), "fmt.linePrefix")
	return table


def format_range_items(attrs):
	"""Items describing text with these format attributes, most specific first."""
	if not attrs:
		return []
	get = attrs.get
	items = []
	heading_level = get("heading-level")
	if heading_level:
		try:
			items.append(heading_level_item_id(heading_level))
		except (TypeError, ValueError):
			pass
		items.append("role.HEADING")
	if get("link"):
		items.append("role.LINK")
	comment = get("comment")
	if comment:
		comment_name = str(getattr(comment, "name", comment)).upper()
		if comment_name == "DRAFT":
			items.append("fmt.comment.draft")
		elif comment_name == "RESOLVED":
			items.append("fmt.comment.resolved")
		items.append("fmt.comment")
	for attribute, item in (
		("bookmark", "fmt.bookmark"),
		("revision-insertion", "fmt.inserted"),
		("revision-deletion", "fmt.deleted"),
		("revision", "fmt.revised"),
		("invalid-spelling", "fmt.spellingError"),
		("invalid-grammar", "fmt.grammarError"),
		("marked", "fmt.marked"),
		("highlight-color", "fmt.highlightColor"),
		("strong", "fmt.strong"),
		("emphasised", "fmt.emphasised"),
		("bold", "fmt.bold"),
		("italic", "fmt.italic"),
	):
		if get(attribute):
			items.append(item)
	strike = get("strikethrough")
	if strike:
		items.append("fmt.doubleStrikethrough" if strike == "double" else "fmt.strikethrough")
	if get("underline"):
		items.append("fmt.underline")
	if get("hidden"):
		items.append("fmt.hidden")
	position = str(getattr(get("text-position"), "value", get("text-position")) or "")
	if position == "super":
		items.append("fmt.superscript")
	elif position == "sub":
		items.append("fmt.subscript")
	align = str(getattr(get("text-align"), "value", get("text-align")) or "")
	if align in ("left", "center", "right", "justify"):
		items.append(f"fmt.align.{align}")
	elif align and align != "undefined":
		items.append("fmt.align.other")
	style = get("style")
	if style:
		items.append(style_name_item_id(style))
		items.append("fmt.style")
	for key in ("font-name", "font-family"):
		value = get(key)
		if value:
			items.append(font_name_item_id(value))
			break
	size = get("font-size")
	if size:
		items.append(font_size_item_id(size))
	# Colors come last: any more specific formatting on the same text wins.
	if get("color"):
		items.append("fmt.color")
	if get("background-color"):
		items.append("fmt.backgroundColor")
	return items
