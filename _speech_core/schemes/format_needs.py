"""Document formatting NVDA must fetch for the configured Speech and Sound Scheme items.

NVDA only fetches the document formatting it has been asked to *announce*. A
user who turned "Font attributes" off in Document Formatting still gets no
``underline`` attribute in NVDA's format fields, so a scheme item for underlined
text could never be marked. NVDA also skips looking for formatting changes after
the cursor unless "Report formatting changes after the cursor" is on, so a line,
sentence, paragraph or Say All chunk is described with the formatting of its
first character only.

``requirements`` turns the configured items into the smallest set of
``documentFormatting`` values that make NVDA *fetch* what a scheme needs. The
tagging wrappers hand that enriched configuration to NVDA's text speech and give
NVDA's own announcement builders the user's real settings back, so what NVDA
says is exactly what the user configured it to say.
"""
from __future__ import annotations

#: Keys that would make ``getTextInfoSpeech`` itself speak more, so a scheme
#: never forces them on.
UNSAFE_KEYS = frozenset({"reportClickable", "reportLineIndentation"})

#: ``item id`` -> documentFormatting keys NVDA needs for that item.
_ITEM_KEYS = {
	"fmt.bold": ("fontAttributeReporting",),
	"fmt.italic": ("fontAttributeReporting",),
	"fmt.underline": ("fontAttributeReporting",),
	"fmt.strikethrough": ("fontAttributeReporting",),
	"fmt.doubleStrikethrough": ("fontAttributeReporting",),
	"fmt.hidden": ("fontAttributeReporting",),
	"fmt.strong": ("reportEmphasis",),
	"fmt.emphasised": ("reportEmphasis",),
	"fmt.marked": ("reportHighlight",),
	"fmt.highlightColor": ("reportHighlight",),
	"fmt.superscript": ("reportSuperscriptsAndSubscripts",),
	"fmt.subscript": ("reportSuperscriptsAndSubscripts",),
	"fmt.comment": ("reportComments",),
	"fmt.comment.draft": ("reportComments",),
	"fmt.comment.resolved": ("reportComments",),
	"fmt.bookmark": ("reportBookmarks",),
	"fmt.inserted": ("reportRevisions",),
	"fmt.deleted": ("reportRevisions",),
	"fmt.revised": ("reportRevisions",),
	"fmt.spellingError": ("reportSpellingErrors",),
	"fmt.grammarError": ("reportSpellingErrors",),
	"fmt.lineSpacing": ("reportLineSpacing",),
	"fmt.lineNumber": ("reportLineNumber",),
	"fmt.page": ("reportPage",),
	"fmt.tableCellCoords": ("reportTables", "reportTableCellCoords"),
	"fmt.tableHeaders": ("reportTables", "reportTableHeaders"),
	"role.LINK": ("reportLinks",),
	"role.TABLE": ("reportTables",),
	"role.LIST": ("reportLists",),
	"role.LISTITEM": ("reportLists",),
	"role.BLOCKQUOTE": ("reportBlockQuotes",),
	"role.GROUPING": ("reportGroupings",),
	"role.FRAME": ("reportFrames",),
	"role.INTERNALFRAME": ("reportFrames",),
	"role.FIGURE": ("reportFigures",),
	"role.ARTICLE": ("reportArticles",),
	"role.GRAPHIC": ("reportGraphics",),
	"object.unlabeledGraphic": ("reportGraphics",),
}

#: ``item id`` prefix -> documentFormatting keys, for the user's own entries.
_PREFIX_KEYS = (
	("fmt.fontName.", ("reportFontName",)),
	("fmt.fontSize.", ("reportFontSize",)),
	("fmt.styleName.", ("reportStyle",)),
	("fmt.align.", ("reportAlignment",)),
	("fmt.color", ("reportColor",)),
	("fmt.backgroundColor", ("reportColor",)),
	("role.HEADING", ("reportHeadings",)),
	("landmark.", ("reportLandmarks",)),
)

#: Keys whose "on" value is not ``True``; used only when the user's value is off.
_ON_VALUES = {
	# 0 off, 1 speech, 2 braille, 3 both. Fetching needs any non-zero value.
	"fontAttributeReporting": 3,
	# 0 off, 1 rows and columns.
	"reportTableHeaders": 1,
}

#: Item ids that describe a run of text, so formatting changes inside a line,
#: sentence, paragraph or Say All chunk have to be detected.
_RANGE_PREFIXES = ("fmt.", "role.HEADING")
_RANGE_ITEMS = frozenset({"role.LINK"})


def _keys_for(item_id: str):
	keys = _ITEM_KEYS.get(item_id)
	if keys:
		return keys
	for prefix, prefix_keys in _PREFIX_KEYS:
		if item_id.startswith(prefix):
			return prefix_keys
	return ()


def _is_range_item(item_id: str) -> bool:
	return item_id in _RANGE_ITEMS or item_id.startswith(_RANGE_PREFIXES)


def requirements(items_cfg):
	"""Return ``(keys, detect_after_cursor)`` for the configured items.

	``keys`` are the ``documentFormatting`` names NVDA must have on to fetch the
	information these items describe. ``detect_after_cursor`` is True when an
	item describes a run of text, so NVDA has to look past the start of the
	range it is speaking.
	"""
	keys = set()
	detect = False
	for item_id in items_cfg or ():
		for key in _keys_for(item_id):
			if key not in UNSAFE_KEYS:
				keys.add(key)
		if not detect and _is_range_item(item_id):
			detect = True
	return frozenset(keys), detect


def as_dict(format_config):
	"""A plain, writable copy of one of NVDA's configuration sections.

	``config.conf["documentFormatting"]`` is an ``AggregatedSection``, not a
	mapping: ``dict()`` on it raises, so its own ``copy`` is used, exactly as
	``getTextInfoSpeech`` does before it adds to it.
	"""
	if format_config is None:
		return None
	copy = getattr(format_config, "copy", None)
	if callable(copy):
		try:
			copied = copy()
		except Exception:
			copied = None
		if isinstance(copied, dict):
			return copied
	try:
		return dict(format_config)
	except Exception:
		return None


def enrich(format_config, keys, detect_after_cursor):
	"""Return a copy of ``format_config`` with what a scheme needs turned on.

	Returns ``None`` when nothing has to change, so NVDA keeps its own object.
	"""
	if not keys and not detect_after_cursor:
		return None
	enriched = as_dict(format_config)
	if enriched is None:
		return None
	changed = False
	for key in keys:
		if key not in enriched:
			# NVDA does not know this setting; leave its configuration alone.
			continue
		if not enriched[key]:
			enriched[key] = _ON_VALUES.get(key, True)
			changed = True
	if detect_after_cursor and not enriched.get("detectFormatAfterCursor"):
		enriched["detectFormatAfterCursor"] = True
		changed = True
	return enriched if changed else None
