"""Shared mesh import/export feedback: phase progress and a timestamped log.

Ported from the ZZtaii fork (SF6 mode labels removed).

Progress is phase-based, not a time estimate. It does not turn Blender's
synchronous import/export into a cancellable background task.

The outermost tracked operation (or operation_scope) owns the console and the
window-manager progress bar. On Windows the system console is shown only if it
is hidden, and hidden again only if this operation showed it and the operation
succeeded, so a failure leaves the details on screen and an already open
console is never closed. Everything is a no-op in background mode and on
other platforms, apart from the console log lines.
"""
from contextlib import contextmanager
from functools import wraps
import os
import sys
import time
import traceback

_stack = []


def _bpy():
	# Keep the module importable outside Blender (pure-python tests).
	try:
		import bpy
		return bpy
	except ImportError:
		return None


def _addon_preferences(bpy):
	# This module lives in <addon>/modules/mesh.
	addonName = (__package__ or "").rsplit(".", 2)[0]
	addon = bpy.context.preferences.addons.get(addonName)
	return addon.preferences if addon is not None else None


class WindowsConsole:
	"""Only hide a console this operation opened, and only on success."""
	def __init__(self):
		self.handle = None
		self.opened = False
		self.user32 = None

	def open(self):
		bpy = _bpy()
		if bpy is None or bpy.app.background or sys.platform != "win32":
			return
		try:
			preferences = _addon_preferences(bpy)
			if preferences is None or not getattr(preferences, "showConsole", False):
				return
			import ctypes
			from ctypes import wintypes
			kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
			user32 = ctypes.WinDLL("user32", use_last_error=True)
			kernel32.GetConsoleWindow.argtypes = []
			kernel32.GetConsoleWindow.restype = wintypes.HWND
			user32.IsWindowVisible.argtypes = [wintypes.HWND]
			user32.IsWindowVisible.restype = wintypes.BOOL
			user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
			user32.ShowWindow.restype = wintypes.BOOL
			handle = kernel32.GetConsoleWindow()
			wasVisible = bool(handle and user32.IsWindowVisible(handle))
			if not handle:
				# No console exists yet. Only this known state permits a toggle.
				bpy.ops.wm.console_toggle()
				handle = kernel32.GetConsoleWindow()
			elif not wasVisible:
				user32.ShowWindow(handle, 4)  # SW_SHOWNOACTIVATE
			self.handle, self.user32 = handle, user32
			self.opened = bool(handle and not wasVisible and user32.IsWindowVisible(handle))
		except Exception:
			# UI feedback must never block an otherwise valid mesh operation.
			# Do not blindly toggle on an unknown console state.
			self.opened = False

	def close(self, success):
		if success and self.opened and self.handle and self.user32:
			try:
				self.user32.ShowWindow(self.handle, 0)  # SW_HIDE
			except Exception:
				pass
		self.opened = False


class OperationProgress:
	def __init__(self, label):
		self.label = label
		self.console = WindowsConsole()
		self.started = time.perf_counter()
		self.root = not _stack
		self.wm = None
		self.ownsProgressBar = False
		self.last_value = 0

	def begin(self):
		if self.root:
			self.console.open()
			bpy = _bpy()
			if bpy is not None and not bpy.app.background:
				try:
					self.wm = bpy.context.window_manager
					self.wm.progress_begin(0, 100)
					self.ownsProgressBar = True
				except Exception:
					self.wm = None
		else:
			# Nested operations (multi-file import, batch export) drive the
			# outer progress bar but never touch the console.
			self.wm = _stack[-1].wm
		_stack.append(self)
		self.stage("Started", 0)

	def stage(self, message, value=None):
		elapsed = time.perf_counter() - self.started
		try:
			print(f"[RE Mesh | {self.label} | {elapsed:.1f}s] {message}", flush=True)
		except (OSError, ValueError):
			pass
		if self.wm is not None and value is not None:
			self.last_value = max(self.last_value, min(100, max(0, value)))
			try:
				self.wm.progress_update(self.last_value)
			except Exception:
				pass

	def finish(self, success):
		self.stage("Finished" if success else "FAILED - see the error above", 100 if success else None)
		if self.ownsProgressBar and self.wm is not None:
			try:
				self.wm.progress_end()
			except Exception:
				pass
		if _stack and _stack[-1] is self:
			_stack.pop()
		elif self in _stack:
			_stack.remove(self)
		if self.root:
			self.console.close(success)


def stage(message, value=None):
	if _stack:
		_stack[-1].stage(message, value)


@contextmanager
def operation_scope(label):
	"""Group several tracked operations under one console/progress owner.

	Yields a dict; set result["success"] = False to keep the console open.
	An exception also counts as failure.
	"""
	progress = OperationProgress(label)
	result = {"success": True}
	progress.begin()
	try:
		yield result
	except Exception:
		result["success"] = False
		raise
	finally:
		progress.finish(bool(result.get("success")))


def tracked_operation(kind):
	def decorate(function):
		@wraps(function)
		def wrapped(filePath, options):
			progress = OperationProgress(f"{kind} / {os.path.basename(str(filePath))}")
			success = False
			progress.begin()
			try:
				result = function(filePath, options)
				success = result is not False
				if kind == "Import" and isinstance(result, tuple) and len(result) == 2:
					success = not result[1]
				return result
			except Exception:
				traceback.print_exc()
				raise
			finally:
				progress.finish(success)
		return wrapped
	return decorate
