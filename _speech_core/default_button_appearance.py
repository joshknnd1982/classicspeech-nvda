# -*- coding: UTF-8 -*-
"""Pick a dialog's default button by how it looks, when nothing else can tell.

Dialogs draw their default button differently from their other buttons, so
that sighted users can see it. WinUI dialogs, and many web dialogs, fill it
with the accent color; Windows and WPF dialogs give it an accent-colored
border. When neither Windows nor the application reports a default button,
NVDA+E compares the dialog's buttons on screen and names one only when it
alone is colored while the others are gray, white or black.

This reads pixels of the screen, so it needs the dialog on screen: it does
nothing while NVDA's Screen Curtain is on, and focus speech never uses it.
Nothing is saved; the pixels are compared and dropped.
"""
from __future__ import annotations

import controlTypes
import logHandler

from . import win32_default_button as win32

log = logHandler.log

MIN_BUTTONS = 2
MAX_BUTTONS = 16
MIN_BUTTON_SIZE = 8
#: Larger "buttons" are cards or panes, not a dialog's buttons.
MAX_BUTTON_WIDTH = 600
MAX_BUTTON_HEIGHT = 200
#: Chroma (largest minus smallest of red, green and blue) of a colored surface.
ACCENT_CHROMA = 60
#: Every other button must stay below this chroma: gray, white or black.
NEUTRAL_CHROMA = 30
#: How far the colored button's color must be from every other button's.
MIN_COLOR_DISTANCE = 60
#: Edge rings measured, from the outside in, to find a colored border.
EDGE_RINGS = 3


class AppearanceResult:
	__slots__ = ("button", "screenCurtainBlocked")

	def __init__(self, button=None, *, screenCurtainBlocked=False):
		self.button = button
		self.screenCurtainBlocked = bool(screenCurtainBlocked)


def screen_curtain_active() -> bool:
	"""True while NVDA's Screen Curtain hides the screen."""
	try:
		import screenCurtain  # NVDA 2026.1 and later.
	except ImportError:
		screenCurtain = None
	except Exception:
		return False
	if screenCurtain is not None:
		controller = getattr(screenCurtain, "screenCurtain", None)
		return bool(controller is not None and getattr(controller, "enabled", False))
	try:
		# NVDA 2025: the Screen Curtain is a vision enhancement provider.
		import vision
		from visionEnhancementProviders.screenCurtain import ScreenCurtainProvider

		providerInfo = vision.handler.getProviderInfo(ScreenCurtainProvider.getSettings().getId())
		return bool(providerInfo and vision.handler.getProviderInstance(providerInfo))
	except Exception:
		return False


#: Most pixels read for one button; a larger button is read scaled down.
MAX_SAMPLE_PIXELS = 12000


def _capture_screen(left, top, width, height):
	"""Return the screen's pixels in the rectangle as rows of ``(red, green, blue)``."""
	import screenBitmap

	scale = min(1.0, (MAX_SAMPLE_PIXELS / float(width * height)) ** 0.5)
	sampleWidth = max(MIN_BUTTON_SIZE, int(width * scale))
	sampleHeight = max(MIN_BUTTON_SIZE, int(height * scale))
	bitmap = screenBitmap.ScreenBitmap(sampleWidth, sampleHeight)
	pixels = bitmap.captureImage(left, top, width, height)
	return [[(pixel.rgbRed, pixel.rgbGreen, pixel.rgbBlue) for pixel in row] for row in pixels]


_capture = None


def set_capture(capture) -> None:
	"""Install ``capture(left, top, width, height)`` (a fake in tests); None restores the screen."""
	global _capture
	_capture = capture


def _get_capture():
	return _capture or _capture_screen


def _hidden_states():
	states = set()
	for name in ("INVISIBLE", "OFFSCREEN", "UNAVAILABLE"):
		state = getattr(controlTypes.State, name, None)
		if state is not None:
			states.add(state)
	return frozenset(states)


#: A button in one of these states cannot be the one Enter activates.
_HIDDEN_STATES = _hidden_states()


def _button_rect(obj):
	try:
		states = getattr(obj, "states", set()) or set()
	except Exception:
		states = set()
	if any(state in states for state in _HIDDEN_STATES):
		return None
	try:
		left, top, width, height = (int(value) for value in obj.location)
	except Exception:
		return None
	if not (MIN_BUTTON_SIZE <= width <= MAX_BUTTON_WIDTH and MIN_BUTTON_SIZE <= height <= MAX_BUTTON_HEIGHT):
		return None
	return (left, top, width, height)


def _chroma(color) -> int:
	return max(color) - min(color)


def _distance(a, b) -> float:
	return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _dominant(pixels):
	"""Return the average of the most common color among ``pixels``."""
	counts = {}
	for pixel in pixels:
		key = (pixel[0] >> 4, pixel[1] >> 4, pixel[2] >> 4)
		entry = counts.get(key)
		if entry is None:
			counts[key] = [1, pixel[0], pixel[1], pixel[2]]
		else:
			entry[0] += 1
			entry[1] += pixel[0]
			entry[2] += pixel[1]
			entry[3] += pixel[2]
	if not counts:
		return None
	count, red, green, blue = max(counts.values(), key=lambda entry: entry[0])
	return (red // count, green // count, blue // count)


def _fill_color(rows):
	"""The button's surface: the middle, away from the border; the label covers only part of it."""
	height = len(rows)
	width = len(rows[0]) if rows else 0
	insetX = max(2, width // 10)
	insetY = max(2, height // 5)
	pixels = [pixel for row in rows[insetY : height - insetY] for pixel in row[insetX : width - insetX]]
	return _dominant(pixels)


def _ring(rows, inset):
	height = len(rows)
	width = len(rows[0]) if rows else 0
	if width - 2 * inset < 3 or height - 2 * inset < 3:
		return []
	top = rows[inset][inset : width - inset]
	bottom = rows[height - 1 - inset][inset : width - inset]
	sides = []
	for row in rows[inset + 1 : height - 1 - inset]:
		sides.append(row[inset])
		sides.append(row[width - 1 - inset])
	return list(top) + list(bottom) + sides


def _edge_color(rows):
	"""The button's border: the most colored of its outermost rings of pixels."""
	colors = [color for color in (_dominant(_ring(rows, inset)) for inset in range(EDGE_RINGS)) if color]
	if not colors:
		return None
	return max(colors, key=_chroma)


def _unique_accent(colors):
	"""Return the index of the only colored entry among gray ones, or None."""
	if len(colors) < MIN_BUTTONS or any(color is None for color in colors):
		return None
	accented = [index for index, color in enumerate(colors) if _chroma(color) >= ACCENT_CHROMA]
	if len(accented) != 1:
		return None
	index = accented[0]
	others = [color for position, color in enumerate(colors) if position != index]
	if any(_chroma(color) >= NEUTRAL_CHROMA for color in others):
		return None
	if min(_distance(colors[index], color) for color in others) < MIN_COLOR_DISTANCE:
		return None
	return index


def _is_black(color) -> bool:
	return color is None or max(color) < 16


def _contains(rect, point) -> bool:
	if not point:
		return False
	left, top, width, height = rect
	x, y = point
	return left <= x < left + width and top <= y < top + height


def _dialog_on_top(obj) -> bool:
	"""True unless another window is in front of the dialog that holds ``obj``."""
	hwnd = 0
	try:
		hwnd = int(getattr(obj, "windowHandle", 0) or 0)
	except Exception:
		pass
	if not hwnd or not win32.get_api():
		return True
	foreground = win32.foreground_window()
	if not foreground:
		return True
	return win32.root_window(foreground) == win32.root_window(hwnd)


def pick_default_button(buttons, *, focusIsButton=False) -> AppearanceResult:
	"""Return the one button in ``buttons`` drawn as a default button, if there is one.

	A colored surface counts whatever has focus. A colored border counts only
	while focus is not on a button, because Windows and WPF also draw the
	focused button with one. The button under the mouse pointer is never
	chosen, because pointing at a button can color it too.
	"""
	candidates = []
	for obj in buttons:
		rect = _button_rect(obj)
		if rect is not None:
			candidates.append((obj, rect))
		if len(candidates) >= MAX_BUTTONS:
			break
	if len(candidates) < MIN_BUTTONS:
		return AppearanceResult()
	if screen_curtain_active():
		return AppearanceResult(screenCurtainBlocked=True)
	if not _dialog_on_top(candidates[0][0]):
		return AppearanceResult()
	capture = _get_capture()
	fills = []
	edges = []
	for _obj, rect in candidates:
		try:
			rows = capture(*rect)
		except Exception:
			log.debugWarning("ClassicSpeech: could not read a button's pixels", exc_info=True)
			return AppearanceResult()
		if not rows or not rows[0]:
			return AppearanceResult()
		fills.append(_fill_color(rows))
		edges.append(_edge_color(rows))
	if all(_is_black(fill) and _is_black(edge) for fill, edge in zip(fills, edges)):
		# Nothing to see: the screen is blank or hidden.
		return AppearanceResult()
	index = _unique_accent(fills)
	if index is None and not focusIsButton:
		index = _unique_accent(edges)
	if index is None:
		return AppearanceResult()
	if _contains(candidates[index][1], win32.cursor_position()):
		return AppearanceResult()
	return AppearanceResult(candidates[index][0])
