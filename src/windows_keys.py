"""Read the physical Windows Right Ctrl key without intercepting shortcuts."""
import ctypes
import logging
import threading
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
user32.GetAncestor.restype = wintypes.HWND
user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
user32.SetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_long)
user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
user32.IsWindowVisible.argtypes = (wintypes.HWND,)
user32.SetWindowPos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                               ctypes.c_int, ctypes.c_int, wintypes.UINT)

VK_RCONTROL = 0xA3
VK_ESCAPE = 0x1B
LLKHF_INJECTED = 0x10


class KeyEvent(ctypes.Structure):
    _fields_ = [("vk", wintypes.DWORD), ("scan", wintypes.DWORD),
                ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("extra", ctypes.c_size_t)]


class RightControl:
    def __init__(self, start, stop, cancel):
        self.start, self.stop, self.cancel = start, stop, cancel
        self.held = False

    def handle(self, vk, flags, down):
        if flags & LLKHF_INJECTED:
            return
        if vk == VK_RCONTROL:
            if down and not self.held:
                self.held = True
                self.start()
            elif not down and self.held:
                self.held = False
                self.stop()
        elif down and vk == VK_ESCAPE:
            self.cancel(False)
        elif down and self.held:
            self.cancel(True)

    def install(self):
        ready = threading.Event()
        errors = []
        procedure = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int,
                                       wintypes.WPARAM, wintypes.LPARAM)
        user32.SetWindowsHookExW.argtypes = (ctypes.c_int, procedure, wintypes.HINSTANCE, wintypes.DWORD)
        user32.SetWindowsHookExW.restype = wintypes.HANDLE
        user32.CallNextHookEx.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        user32.CallNextHookEx.restype = ctypes.c_ssize_t
        user32.UnhookWindowsHookEx.argtypes = (wintypes.HANDLE,)
        user32.GetMessageW.argtypes = (ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE

        @procedure
        def callback(code, message, address):
            try:
                if code == 0:
                    event = ctypes.cast(address, ctypes.POINTER(KeyEvent)).contents
                    self.handle(event.vk, event.flags, message in (0x100, 0x104))
            except Exception:
                logging.exception("Windows 快捷鍵處理失敗")
            return user32.CallNextHookEx(None, code, message, address)

        def listen():
            handle = user32.SetWindowsHookExW(13, callback, kernel32.GetModuleHandleW(None), 0)
            if not handle:
                errors.append(ctypes.WinError(ctypes.get_last_error()))
            ready.set()
            if handle:
                message = wintypes.MSG()
                while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                    pass
                user32.UnhookWindowsHookEx(handle)

        threading.Thread(target=listen, daemon=True).start()
        ready.wait()
        if errors:
            raise errors[0]
