from __future__ import annotations

import ctypes
import logging
import os
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Sequence

logger = logging.getLogger("musical_scumme.input_backend")


class InputBackend(Protocol):
    available: bool
    name: str

    def key_down(self, key: str) -> None: ...
    def key_up(self, key: str) -> None: ...
    def send_batch(self, events: Sequence[tuple[str, str]]) -> None: ...
    def release_all(self) -> None: ...


KEY_ALIASES = {
    "CTRL": "LCTRL",
    "CONTROL": "LCTRL",
    "SHIFT": "LSHIFT",
    "ALT": "LALT",
    "RETURN": "ENTER",
    "ESCAPE": "ESC",
    "LEFTCMD": "LWIN",
    "LEFTCOMMAND": "LWIN",
    "LCMD": "LWIN",
    "CMD": "LWIN",
    "COMMAND": "LWIN",
    "WIN": "LWIN",
    "WINDOWS": "LWIN",
    "LEFTWIN": "LWIN",
    "LEFTWINDOWS": "LWIN",
    "LEFTMETA": "LWIN",
    "LMETA": "LWIN",
    "RIGHTCMD": "RWIN",
    "RIGHTCOMMAND": "RWIN",
    "RCMD": "RWIN",
    "RIGHTWIN": "RWIN",
    "RIGHTWINDOWS": "RWIN",
    "RIGHTMETA": "RWIN",
    "RMETA": "RWIN",
}

SPECIAL_VK = {
    "BACKSPACE": 0x08,
    "TAB": 0x09,
    "ENTER": 0x0D,
    "LSHIFT": 0xA0,
    "RSHIFT": 0xA1,
    "LCTRL": 0xA2,
    "RCTRL": 0xA3,
    "LALT": 0xA4,
    "RALT": 0xA5,
    "LWIN": 0x5B,
    "RWIN": 0x5C,
    "ESC": 0x1B,
    "SPACE": 0x20,
    "PAGEUP": 0x21,
    "PAGEDOWN": 0x22,
    "END": 0x23,
    "HOME": 0x24,
    "LEFT": 0x25,
    "UP": 0x26,
    "RIGHT": 0x27,
    "DOWN": 0x28,
    "INSERT": 0x2D,
    "DELETE": 0x2E,
}

EXTENDED_KEYS = {
    "RCTRL",
    "RALT",
    "LWIN",
    "RWIN",
    "INSERT",
    "DELETE",
    "HOME",
    "END",
    "PAGEUP",
    "PAGEDOWN",
    "LEFT",
    "RIGHT",
    "UP",
    "DOWN",
}


def normalize_key_name(key: str) -> str:
    normalized = str(key).strip().upper().replace(" ", "")
    return KEY_ALIASES.get(normalized, normalized)


def key_name_to_vk(key: str) -> int:
    key = normalize_key_name(key)
    if len(key) == 1 and ("A" <= key <= "Z" or "0" <= key <= "9"):
        return ord(key)
    if key in SPECIAL_VK:
        return SPECIAL_VK[key]
    if key.startswith("F") and key[1:].isdigit():
        number = int(key[1:])
        if 1 <= number <= 24:
            return 0x70 + number - 1
    punctuation = {
        ";": 0xBA,
        "=": 0xBB,
        ",": 0xBC,
        "-": 0xBD,
        ".": 0xBE,
        "/": 0xBF,
        "`": 0xC0,
        "[": 0xDB,
        "\\": 0xDC,
        "]": 0xDD,
        "'": 0xDE,
    }
    if key in punctuation:
        return punctuation[key]
    raise ValueError(f"Unsupported key name: {key}")


@dataclass(slots=True)
class DryRunBackend:
    name: str = "Dry run"
    available: bool = True
    pressed: set[str] = field(default_factory=set)
    history: list[tuple[str, str]] = field(default_factory=list)

    def key_down(self, key: str) -> None:
        key = normalize_key_name(key)
        self.pressed.add(key)
        self.history.append(("down", key))

    def key_up(self, key: str) -> None:
        key = normalize_key_name(key)
        self.pressed.discard(key)
        self.history.append(("up", key))

    def send_batch(self, events: Sequence[tuple[str, str]]) -> None:
        for action, key in events:
            if action == "down":
                self.key_down(key)
            elif action == "up":
                self.key_up(key)
            else:
                raise ValueError(f"Unsupported key action: {action}")

    def release_all(self) -> None:
        for key in sorted(self.pressed):
            self.history.append(("up", key))
        self.pressed.clear()


# Win32 ABI structures used by SendInput. These are defined explicitly instead
# of relying on host-native C integer sizes so the layout matches winuser.h.
# INPUT's union must include mouse, keyboard, and hardware members: defining only
# KEYBDINPUT makes ctypes.sizeof(INPUT) too small and causes ERROR_INVALID_PARAMETER
# (87) from SendInput on Windows.
WORD = ctypes.c_uint16
DWORD = ctypes.c_uint32
LONG = ctypes.c_int32
ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", LONG),
        ("dy", LONG),
        ("mouseData", DWORD),
        ("dwFlags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", WORD),
        ("wScan", WORD),
        ("dwFlags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", DWORD),
        ("wParamL", WORD),
        ("wParamH", WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _anonymous_ = ("union",)
    _fields_ = [("type", DWORD), ("union", _INPUTUNION)]


def sendinput_abi_sizes() -> tuple[int, int]:
    """Return (actual, expected) INPUT sizes for the current pointer width."""
    expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
    return ctypes.sizeof(INPUT), expected


class WindowsSendInputBackend:
    INPUT_KEYBOARD = 1
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_SCANCODE = 0x0008
    MAPVK_VK_TO_VSC = 0

    def __init__(self, mode: str = "scan_code") -> None:
        self.mode = mode
        self.name = "SendInput scan codes" if mode == "scan_code" else "SendInput virtual keys"
        self.available = os.name == "nt"
        self._pressed: set[str] = set()
        self._resolved_keys: dict[str, tuple[int, int, int]] = {}
        if self.available:
            actual_size, expected_size = sendinput_abi_sizes()
            if actual_size != expected_size:
                raise RuntimeError(
                    f"Invalid Windows INPUT ABI layout: got {actual_size} bytes, "
                    f"expected {expected_size}."
                )
            self.user32 = ctypes.WinDLL("user32", use_last_error=True)
            self.user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
            self.user32.SendInput.restype = wintypes.UINT
            self.user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
            self.user32.MapVirtualKeyW.restype = wintypes.UINT

    def _packet(self, key: str, key_up: bool) -> tuple[str, INPUT]:
        if not self.available:
            raise RuntimeError("Windows SendInput is only available on Windows.")
        normalized = normalize_key_name(key)
        resolved = self._resolved_keys.get(normalized)
        if resolved is None:
            vk = key_name_to_vk(normalized)
            scan = 0
            base_flags = self.KEYEVENTF_EXTENDEDKEY if normalized in EXTENDED_KEYS else 0
            if self.mode == "scan_code":
                scan = int(self.user32.MapVirtualKeyW(vk, self.MAPVK_VK_TO_VSC))
                if not scan:
                    raise RuntimeError(f"Windows could not resolve a scan code for {normalized}.")
                base_flags |= self.KEYEVENTF_SCANCODE
            resolved = (vk, scan, base_flags)
            self._resolved_keys[normalized] = resolved
        vk, scan, base_flags = resolved
        flags = self.KEYEVENTF_KEYUP if key_up else 0
        flags |= base_flags

        if self.mode == "scan_code":
            keyboard = KEYBDINPUT(0, scan, flags, 0, 0)
        else:
            keyboard = KEYBDINPUT(vk, 0, flags, 0, 0)
        packet = INPUT(type=self.INPUT_KEYBOARD, ki=keyboard)
        return normalized, packet

    def _send(self, key: str, key_up: bool) -> None:
        self.send_batch([("up" if key_up else "down", key)])

    def send_batch(self, events: Sequence[tuple[str, str]]) -> None:
        if not events:
            return
        normalized_events: list[tuple[str, str]] = []
        packets: list[INPUT] = []
        for action, key in events:
            if action not in {"down", "up"}:
                raise ValueError(f"Unsupported key action: {action}")
            normalized, packet = self._packet(key, action == "up")
            normalized_events.append((action, normalized))
            packets.append(packet)
        packet_array = (INPUT * len(packets))(*packets)
        ctypes.set_last_error(0)
        sent = int(self.user32.SendInput(len(packets), packet_array, ctypes.sizeof(INPUT)))
        for action, normalized in normalized_events[:sent]:
            if action == "down":
                self._pressed.add(normalized)
            else:
                self._pressed.discard(normalized)
        if sent != len(packets):
            error = ctypes.get_last_error()
            if error:
                raise OSError(error, f"SendInput sent {sent}/{len(packets)} keyboard events")
            raise RuntimeError(
                f"SendInput accepted {sent}/{len(packets)} keyboard events. Windows can block synthetic "
                "input when the target runs at a higher privilege level; run both SCUM "
                "and MusicalScumme at the same privilege level."
            )

    def key_down(self, key: str) -> None:
        self._send(key, False)

    def key_up(self, key: str) -> None:
        self._send(key, True)

    def release_all(self) -> None:
        failed: list[str] = []
        for key in tuple(sorted(self._pressed)):
            try:
                self._send(key, True)
            except Exception:
                # _send()/send_batch only removes a key from _pressed after
                # Windows confirms that its key-up was accepted.  Keep failed
                # releases in the set so the next safety cleanup can retry them
                # instead of forgetting potentially stuck physical state.
                failed.append(key)
                logger.exception("Could not release SCUM key %s", key)
        if failed:
            logger.warning(
                "SCUM key cleanup left %d key(s) pending retry: %s",
                len(failed),
                ", ".join(failed),
            )


def create_backend(mode: str) -> InputBackend:
    if mode == "dry_run" or os.name != "nt":
        return DryRunBackend()
    if mode == "virtual_key":
        return WindowsSendInputBackend("virtual_key")
    return WindowsSendInputBackend("scan_code")


def _is_scum_window_identity(title: str, process_name: str) -> bool:
    process = process_name.lower()
    title_lower = title.lower().strip()
    known_process = process in {"scum.exe", "scum-win64-shipping.exe"}
    # Process lookup can fail under restricted permissions. SCUM normally uses
    # the plain window title "SCUM", so retain a conservative title fallback.
    known_title = (
        title_lower == "scum"
        or title_lower.startswith("scum ")
        or title_lower.endswith(" - scum")
    )
    return known_process or known_title


@dataclass(frozen=True, slots=True)
class ForegroundWindowInfo:
    title: str
    process_name: str
    process_path: str

    @property
    def is_scum(self) -> bool:
        return _is_scum_window_identity(self.title, self.process_name)


_FOREGROUND_LOCK = threading.Lock()
_LAST_FOREGROUND_HWND: int | None = None
_LAST_FOREGROUND_TIME: float = 0.0
_LAST_FOREGROUND_INFO: ForegroundWindowInfo | None = None
_PID_PROCESS_CACHE: dict[int, str] = {}


def foreground_window_info(cache_ttl_s: float = 0.25) -> ForegroundWindowInfo:
    if os.name != "nt":
        return ForegroundWindowInfo("Unsupported platform", "", "")

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ForegroundWindowInfo("", "", "")

    now = time.monotonic()
    global _LAST_FOREGROUND_HWND, _LAST_FOREGROUND_TIME, _LAST_FOREGROUND_INFO
    with _FOREGROUND_LOCK:
        if (
            _LAST_FOREGROUND_HWND == hwnd
            and _LAST_FOREGROUND_INFO is not None
            and (now - _LAST_FOREGROUND_TIME) < cache_ttl_s
        ):
            return _LAST_FOREGROUND_INFO

    user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD

    length = user32.GetWindowTextLengthW(hwnd)
    title_buffer = ctypes.create_unicode_buffer(max(1, length + 1))
    user32.GetWindowTextW(hwnd, title_buffer, len(title_buffer))
    title_str = title_buffer.value

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    pid_val = pid.value

    # Check PID process cache first
    process_name = ""
    with _FOREGROUND_LOCK:
        if pid_val in _PID_PROCESS_CACHE:
            process_name = _PID_PROCESS_CACHE[pid_val]

    # If not in cache, resolve via OpenProcess (unless window title is already SCUM)
    title_lower = title_str.lower()
    is_known_scum_title = (
        title_lower == "scum"
        or title_lower.startswith("scum ")
        or title_lower.endswith(" - scum")
    )

    if not process_name and pid_val > 0:
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        )
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid_val)
        path = ""
        if handle:
            try:
                size = wintypes.DWORD(32768)
                path_buffer = ctypes.create_unicode_buffer(size.value)
                if kernel32.QueryFullProcessImageNameW(handle, 0, path_buffer, ctypes.byref(size)):
                    path = path_buffer.value
            finally:
                kernel32.CloseHandle(handle)
        process_name = Path(path).name if path else ""
        if process_name or is_known_scum_title:
            with _FOREGROUND_LOCK:
                if len(_PID_PROCESS_CACHE) > 64:
                    _PID_PROCESS_CACHE.clear()
                _PID_PROCESS_CACHE[pid_val] = process_name

    info = ForegroundWindowInfo(title_str, process_name, "")
    with _FOREGROUND_LOCK:
        _LAST_FOREGROUND_HWND = hwnd
        _LAST_FOREGROUND_TIME = now
        _LAST_FOREGROUND_INFO = info
    return info


def foreground_scum_window_rect() -> tuple[int, int, int, int] | None:
    """Return the current SCUM foreground window rectangle in native screen pixels."""

    if os.name != "nt" or not foreground_window_info(cache_ttl_s=0.0).is_scum:
        return None
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    rect = wintypes.RECT()
    user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user32.GetWindowRect.restype = wintypes.BOOL
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    if rect.right <= rect.left or rect.bottom <= rect.top:
        return None
    return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)


def focus_scum_window() -> bool:
    """Bring SCUM's main top-level window to the foreground on Windows.

    The user invokes this from Play, so Windows normally permits the foreground
    transfer. The lookup uses both SCUM's executable names and its conservative
    window-title fallback, matching :class:`ForegroundWindowInfo`.
    """

    if os.name != "nt":
        return False

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = (callback_type, wintypes.LPARAM)
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.IsIconic.argtypes = (wintypes.HWND,)
    user32.IsIconic.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.ShowWindow.restype = wintypes.BOOL
    user32.BringWindowToTop.argtypes = (wintypes.HWND,)
    user32.BringWindowToTop.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.AttachThreadInput.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)
    user32.AttachThreadInput.restype = wintypes.BOOL

    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    )
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    matches: list[tuple[int, bool]] = []

    @callback_type
    def enum_proc(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True

        length = user32.GetWindowTextLengthW(hwnd)
        title_buffer = ctypes.create_unicode_buffer(max(1, length + 1))
        user32.GetWindowTextW(hwnd, title_buffer, len(title_buffer))
        title = title_buffer.value

        process_name = ""
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value:
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
            if handle:
                try:
                    size = wintypes.DWORD(32768)
                    path_buffer = ctypes.create_unicode_buffer(size.value)
                    if kernel32.QueryFullProcessImageNameW(handle, 0, path_buffer, ctypes.byref(size)):
                        process_name = Path(path_buffer.value).name
                finally:
                    kernel32.CloseHandle(handle)

        if _is_scum_window_identity(title, process_name):
            # Prefer an executable-verified window over a title-only fallback.
            verified_process = process_name.lower() in {"scum.exe", "scum-win64-shipping.exe"}
            matches.append((int(hwnd), verified_process))
        return True

    user32.EnumWindows(enum_proc, 0)
    if not matches:
        return False

    matches.sort(key=lambda item: item[1], reverse=True)
    hwnd = wintypes.HWND(matches[0][0])
    SW_RESTORE = 9
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)

    def focused_now() -> bool:
        return foreground_window_info(cache_ttl_s=0.0).is_scum

    # The direct path succeeds when Play was invoked from the foreground app,
    # which is the common case. Verify the actual foreground window rather than
    # trusting SetForegroundWindow's return value alone.
    for _ in range(2):
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.025)
        if focused_now():
            return True

    # Windows can reject a foreground transfer because the caller is not tied
    # to the current foreground input queue. Temporarily joining that queue is
    # a conventional Win32 fallback and does not synthesize keyboard/mouse input.
    foreground_hwnd = user32.GetForegroundWindow()
    current_thread = int(kernel32.GetCurrentThreadId())
    foreground_thread = 0
    if foreground_hwnd:
        foreground_thread = int(user32.GetWindowThreadProcessId(foreground_hwnd, None))
    attached = False
    if foreground_thread and foreground_thread != current_thread:
        attached = bool(user32.AttachThreadInput(current_thread, foreground_thread, True))
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.04)
        return focused_now()
    finally:
        if attached:
            user32.AttachThreadInput(current_thread, foreground_thread, False)


_ASYNC_USER32 = ctypes.WinDLL("user32", use_last_error=True) if os.name == "nt" else None
if _ASYNC_USER32 is not None:
    _ASYNC_USER32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
    _ASYNC_USER32.GetAsyncKeyState.restype = ctypes.c_short

_PREVIOUS_KEY_STATES: dict[int, bool] = {}
_KEY_STATE_LOCK = threading.Lock()


def is_virtual_key_down(vk: int) -> bool:
    """Return whether the physical key is currently held down (high-order bit)."""
    if _ASYNC_USER32 is None:
        return False
    # Most significant bit indicates the key is physically pressed down.
    return bool(_ASYNC_USER32.GetAsyncKeyState(vk) & 0x8000)


def is_control_down() -> bool:
    """Return True if any Control key (VK_CONTROL 0x11) is currently held down."""
    return is_virtual_key_down(0x11)


def emergency_stop_pressed() -> bool:
    """Return True if F8 is currently held down."""
    return is_virtual_key_down(0x77)


def function_key_pressed(function_key: int) -> bool:
    """Return whether F1-F24 experienced a new press edge (transitioned from up to down)."""
    if not 1 <= function_key <= 24:
        return False
    return check_key_pressed_edge(0x6F + function_key)


def numpad_key_pressed(digit: int) -> bool:
    """Return whether Numpad 0-9 experienced a new press edge (transitioned from up to down)."""
    if not 0 <= digit <= 9:
        return False
    return check_key_pressed_edge(0x60 + digit)


def numpad_divide_pressed() -> bool:
    """Return whether Numpad / (VK_DIVIDE 0x6F) experienced a new press edge."""
    return check_key_pressed_edge(0x6F)


def virtual_key_pressed(vk: int) -> bool:
    """Return whether the virtual key experienced a new press edge (transitioned from up to down)."""
    return check_key_pressed_edge(vk)


def check_key_pressed_edge(vk: int) -> bool:
    """Thread-safe detection of key press transition (rising edge: was up, now down)."""
    is_down = is_virtual_key_down(vk)
    with _KEY_STATE_LOCK:
        was_down = _PREVIOUS_KEY_STATES.get(vk, False)
        _PREVIOUS_KEY_STATES[vk] = is_down
        return is_down and not was_down


