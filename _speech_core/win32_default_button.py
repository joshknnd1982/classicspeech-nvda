# -*- coding: UTF-8 -*-
"""Find the default push button of a Windows dialog from its window handles.

A standard Windows dialog (window class ``#32770``: Open and Save As, message
boxes, property sheets and most classic dialogs) keeps its default button
itself: ``DM_GETDEFID`` returns that button's control ID whichever control has
focus.

Other Windows toolkits (wxWidgets, WinForms, Delphi and the like) only mark the
default button with the default push-button style. While a push button has
focus, Windows and these toolkits move that style to the focused button, so the
style names the dialog's own default only while focus is on another kind of
control. Callers must treat a focused button's default style as temporary.

Everything here reads window classes, styles and text, or sends the read-only
``DM_GETDEFID`` message with a short timeout. Nothing is created, focused or
changed. The Windows calls go through ``get_api()``, which tests replace with
a fake.
"""
from __future__ import annotations

import sys

DIALOG_CLASS = "#32770"

DM_GETDEFID = 0x0400  # WM_USER + 0, defined by the dialog manager for #32770.
DC_HASDEFID = 0x534B
SMTO_ABORTIFHUNG = 0x0002
#: Milliseconds to wait for a dialog to answer DM_GETDEFID.
SEND_TIMEOUT_MS = 250

GA_PARENT = 1
GA_ROOT = 2
GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_EX_DLGMODALFRAME = 0x00000001

BS_TYPEMASK = 0x000F
BS_PUSHBUTTON = 0x0
BS_DEFPUSHBUTTON = 0x1
BS_OWNERDRAW = 0xB
BS_SPLITBUTTON = 0xC
BS_DEFSPLITBUTTON = 0xD
BS_COMMANDLINK = 0xE
BS_DEFCOMMANDLINK = 0xF

#: Button styles that make a push button: plain, split and command link, in
#: both their normal and default forms, plus owner-drawn buttons.
PUSH_BUTTON_TYPES = frozenset(
	{
		BS_PUSHBUTTON,
		BS_DEFPUSHBUTTON,
		BS_OWNERDRAW,
		BS_SPLITBUTTON,
		BS_DEFSPLITBUTTON,
		BS_COMMANDLINK,
		BS_DEFCOMMANDLINK,
	}
)
#: The default forms: the button Enter activates.
DEFAULT_BUTTON_TYPES = frozenset({BS_DEFPUSHBUTTON, BS_DEFSPLITBUTTON, BS_DEFCOMMANDLINK})

#: Most child windows one search reads. Dialogs have far fewer; a file dialog
#: has about a hundred.
MAX_WINDOWS = 600
_MAX_PARENT_DEPTH = 40


class _User32:
	"""The user32 calls the search needs, through ctypes prototypes of its own.

	The prototypes are made on a private ``WinDLL`` instance, so setting their
	argument types never changes the shared ``ctypes.windll.user32`` functions
	that NVDA and other add-ons use.
	"""

	def __init__(self):
		import ctypes
		from ctypes import wintypes

		self._ctypes = ctypes
		self._wintypes = wintypes
		dll = ctypes.WinDLL("user32")
		HWND = wintypes.HWND
		UINT = wintypes.UINT
		BOOL = wintypes.BOOL
		INT = ctypes.c_int
		LONG = wintypes.LONG

		def proto(name, restype, *argtypes):
			return ctypes.WINFUNCTYPE(restype, *argtypes)((name, dll))

		self._enumProc = ctypes.WINFUNCTYPE(BOOL, HWND, wintypes.LPARAM)
		self._GetAncestor = proto("GetAncestor", HWND, HWND, UINT)
		self._GetClassName = proto("GetClassNameW", INT, HWND, wintypes.LPWSTR, INT)
		self._InternalGetWindowText = proto("InternalGetWindowText", INT, HWND, wintypes.LPWSTR, INT)
		self._GetWindowLong = proto("GetWindowLongW", LONG, HWND, INT)
		self._IsWindow = proto("IsWindow", BOOL, HWND)
		self._IsWindowVisible = proto("IsWindowVisible", BOOL, HWND)
		self._IsWindowEnabled = proto("IsWindowEnabled", BOOL, HWND)
		self._IsChild = proto("IsChild", BOOL, HWND, HWND)
		self._GetDlgCtrlID = proto("GetDlgCtrlID", INT, HWND)
		self._GetDlgItem = proto("GetDlgItem", HWND, HWND, INT)
		self._GetWindowThreadProcessId = proto(
			"GetWindowThreadProcessId", wintypes.DWORD, HWND, ctypes.POINTER(wintypes.DWORD)
		)
		self._EnumChildWindows = proto("EnumChildWindows", BOOL, HWND, self._enumProc, wintypes.LPARAM)
		self._GetForegroundWindow = proto("GetForegroundWindow", HWND)
		self._GetPhysicalCursorPos = proto("GetPhysicalCursorPos", BOOL, ctypes.POINTER(wintypes.POINT))
		self._SendMessageTimeout = proto(
			"SendMessageTimeoutW",
			wintypes.LPARAM,
			HWND,
			UINT,
			wintypes.WPARAM,
			wintypes.LPARAM,
			UINT,
			UINT,
			ctypes.POINTER(ctypes.c_size_t),
		)

	@staticmethod
	def _handle(value):
		return int(value or 0)

	def root(self, hwnd):
		return self._handle(self._GetAncestor(hwnd, GA_ROOT))

	def parent(self, hwnd):
		return self._handle(self._GetAncestor(hwnd, GA_PARENT))

	def class_name(self, hwnd):
		buffer = self._ctypes.create_unicode_buffer(256)
		self._GetClassName(hwnd, buffer, 255)
		return buffer.value

	def text(self, hwnd):
		buffer = self._ctypes.create_unicode_buffer(512)
		self._InternalGetWindowText(hwnd, buffer, 511)
		return buffer.value

	def style(self, hwnd):
		return int(self._GetWindowLong(hwnd, GWL_STYLE))

	def ex_style(self, hwnd):
		return int(self._GetWindowLong(hwnd, GWL_EXSTYLE))

	def exists(self, hwnd):
		return bool(self._IsWindow(hwnd))

	def visible(self, hwnd):
		return bool(self._IsWindowVisible(hwnd))

	def enabled(self, hwnd):
		return bool(self._IsWindowEnabled(hwnd))

	def is_descendant(self, parent, child):
		return bool(self._IsChild(parent, child))

	def control_id(self, hwnd):
		return int(self._GetDlgCtrlID(hwnd))

	def dialog_item(self, dialog, control_id):
		return self._handle(self._GetDlgItem(dialog, control_id))

	def foreground(self):
		return self._handle(self._GetForegroundWindow())

	def cursor(self):
		point = self._wintypes.POINT()
		if not self._GetPhysicalCursorPos(self._ctypes.byref(point)):
			return None
		return (int(point.x), int(point.y))

	def process_id(self, hwnd):
		pid = self._wintypes.DWORD()
		self._GetWindowThreadProcessId(hwnd, self._ctypes.byref(pid))
		return int(pid.value)

	def descendants(self, hwnd, limit=MAX_WINDOWS):
		found = []

		def collect(child, _lParam):
			found.append(int(child or 0))
			return len(found) < limit

		callback = self._enumProc(collect)
		self._EnumChildWindows(hwnd, callback, 0)
		return [child for child in found if child]

	def default_id(self, dialog):
		"""Return the dialog's default control ID, or None."""
		result = None
		try:
			import watchdog

			result = watchdog.cancellableSendMessage(
				dialog,
				DM_GETDEFID,
				0,
				0,
				flags=SMTO_ABORTIFHUNG,
				timeout=SEND_TIMEOUT_MS,
			)
		except ImportError:
			value = self._ctypes.c_size_t()
			if self._SendMessageTimeout(
				dialog,
				DM_GETDEFID,
				0,
				0,
				SMTO_ABORTIFHUNG,
				SEND_TIMEOUT_MS,
				self._ctypes.byref(value),
			):
				result = value.value
		except Exception:
			# watchdog.CallCancelled, or a dialog that went away.
			return None
		if not result:
			return None
		result = int(result)
		if (result >> 16) & 0xFFFF != DC_HASDEFID:
			return None
		return result & 0xFFFF


_api = None


def get_api():
	"""Return the Windows API used here, or None outside Windows and NVDA."""
	global _api
	if _api is None:
		_api = _load_api()
	return _api or None


def _load_api():
	if sys.platform != "win32":
		return False
	try:
		import os

		import globalVars

		# Only a running NVDA sets appPid to its own process. The harnesses use
		# made-up window handles and must never reach real windows.
		if getattr(globalVars, "appPid", 0) != os.getpid():
			return False
	except Exception:
		return False
	try:
		return _User32()
	except Exception:
		return False


def set_api(api) -> None:
	"""Install ``api`` (a fake in tests). False turns the Windows calls off; None loads them again."""
	global _api
	_api = api


def _call(api, method, *args, default=None):
	try:
		return getattr(api, method)(*args)
	except Exception:
		return default


#: Button classes whose names do not contain "button": Delphi's bitmap button.
_OTHER_BUTTON_CLASSES = frozenset({"tbitbtn"})


def is_button_class(name) -> bool:
	"""True for Windows' Button class and the toolkit classes built on it."""
	name = str(name or "").lower()
	return "button" in name or name in _OTHER_BUTTON_CLASSES


def is_push_button_window(hwnd, api=None) -> bool:
	"""True for a push, split or command link button window."""
	api = api or get_api()
	if not api or not hwnd:
		return False
	if not is_button_class(_call(api, "class_name", hwnd, default="")):
		return False
	style = _call(api, "style", hwnd, default=None)
	if style is None:
		return False
	return (style & BS_TYPEMASK) in PUSH_BUTTON_TYPES


def is_usable(hwnd, api=None) -> bool:
	api = api or get_api()
	if not api or not hwnd:
		return False
	return bool(
		_call(api, "exists", hwnd, default=False)
		and _call(api, "visible", hwnd, default=False)
		and _call(api, "enabled", hwnd, default=False)
	)


def root_window(hwnd, api=None):
	api = api or get_api()
	if not api or not hwnd:
		return 0
	return _call(api, "root", hwnd, default=0) or 0


def dialog_windows(hwnd, api=None):
	"""Return the ``#32770`` windows from ``hwnd`` up to its top-level window.

	The top-level dialog comes first: Windows sends Enter to the dialog that the
	message loop handles, which is the top-level one. Dialogs nested in another
	window, such as a form view, follow, nearest first.
	"""
	api = api or get_api()
	if not api or not hwnd:
		return []
	root = root_window(hwnd, api)
	nested = []
	current = hwnd
	for _ in range(_MAX_PARENT_DEPTH):
		if not current:
			break
		if current != root and _call(api, "class_name", current, default="") == DIALOG_CLASS:
			nested.append(current)
		if current == root:
			break
		parent = _call(api, "parent", current, default=0)
		if not parent or parent == current:
			break
		current = parent
	result = []
	if root and _call(api, "class_name", root, default="") == DIALOG_CLASS:
		result.append(root)
	result.extend(nested)
	return result


def _find_button_with_id(dialog, control_id, api):
	button = _call(api, "dialog_item", dialog, control_id, default=0)
	if button and is_push_button_window(button, api):
		return button
	# Some dialogs, such as task dialogs, keep their buttons inside other windows.
	for child in _call(api, "descendants", dialog, MAX_WINDOWS, default=[]) or []:
		child_id = _call(api, "control_id", child, default=0) or 0
		if (child_id & 0xFFFF) == control_id and is_push_button_window(child, api):
			return child
	return 0


def dialog_default_button(hwnd, api=None):
	"""Return the button a standard dialog names with DM_GETDEFID, or 0.

	The answer does not depend on which control has focus.
	"""
	api = api or get_api()
	if not api or not hwnd:
		return 0
	for dialog in dialog_windows(hwnd, api):
		control_id = _call(api, "default_id", dialog, default=None)
		if control_id is None:
			continue
		button = _find_button_with_id(dialog, control_id, api)
		if button and is_usable(button, api):
			return button
	return 0


def default_styled_buttons(hwnd, api=None):
	"""Return the usable buttons with a default style in ``hwnd``'s top-level window."""
	api = api or get_api()
	if not api or not hwnd:
		return []
	root = root_window(hwnd, api)
	if not root:
		return []
	found = []
	for child in _call(api, "descendants", root, MAX_WINDOWS, default=[]) or []:
		style = _call(api, "style", child, default=None)
		if style is None or (style & BS_TYPEMASK) not in DEFAULT_BUTTON_TYPES:
			continue
		# Other window classes use these low style bits for other things.
		if not is_button_class(_call(api, "class_name", child, default="")):
			continue
		if is_usable(child, api):
			found.append(child)
	return found


def nearest_button(hwnd, buttons, api=None):
	"""Return the button in ``buttons`` that shares the closest parent window with ``hwnd``."""
	api = api or get_api()
	if not buttons:
		return 0
	if len(buttons) == 1 or not api:
		return buttons[0]
	current = hwnd
	for _ in range(_MAX_PARENT_DEPTH):
		if not current:
			break
		for button in buttons:
			if button == current or _call(api, "is_descendant", current, button, default=False):
				return button
		parent = _call(api, "parent", current, default=0)
		if not parent or parent == current:
			break
		current = parent
	return buttons[0]


def looks_like_dialog(hwnd, api=None) -> bool:
	"""True when ``hwnd``'s top-level window is a dialog by class or frame style."""
	api = api or get_api()
	root = root_window(hwnd, api)
	if not root:
		return False
	if _call(api, "class_name", root, default="") == DIALOG_CLASS:
		return True
	ex_style = _call(api, "ex_style", root, default=0) or 0
	return bool(ex_style & WS_EX_DLGMODALFRAME)


def button_text(hwnd, api=None) -> str:
	api = api or get_api()
	if not api or not hwnd:
		return ""
	return _call(api, "text", hwnd, default="") or ""


def process_id(hwnd, api=None):
	api = api or get_api()
	if not api or not hwnd:
		return None
	return _call(api, "process_id", hwnd, default=None)


def foreground_window(api=None):
	api = api or get_api()
	if not api:
		return 0
	return _call(api, "foreground", default=0) or 0


def cursor_position(api=None):
	"""Return the mouse pointer's ``(x, y)`` in physical screen pixels, or None."""
	api = api or get_api()
	if not api:
		return None
	return _call(api, "cursor", default=None)
