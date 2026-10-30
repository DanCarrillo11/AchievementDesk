"""Windows x64 Steam client adapter.

Altered Python adaptation of the interface layouts and connection approach in
SAM.API, https://github.com/gibbed/SteamAchievementManager (Rick, 2024).
This is not SAM or an official Valve product. See THIRD_PARTY_NOTICES.txt.

Copyright (c) 2024 Rick (rick 'at' gibbed 'dot' us)
This software is provided 'as-is', without any express or implied
warranty. In no event will the authors be held liable for any damages
arising from the use of this software.
Permission is granted to anyone to use this software for any purpose,
including commercial applications, and to alter it and redistribute it
freely, subject to the following restrictions:
1. The origin of this software must not be misrepresented; you must not
   claim that you wrote the original software. If you use this software
   in a product, an acknowledgment in the product documentation would
   be appreciated but is not required.
2. Altered source versions must be plainly marked as such, and must not
   be misrepresented as being the original software.
3. This notice may not be removed or altered from any source distribution.
"""
import ctypes as C
import os
import re
import struct
import sys
import time
from domain import Achievement
from library import steam_path

P, I, U, Q, B, S = C.c_void_p, C.c_int32, C.c_uint32, C.c_uint64, C.c_bool, C.c_char_p


class Callback(C.Structure):
    _fields_ = [("user", I), ("id", I), ("data", P), ("size", I)]


def method(pointer, slot, result, *args):
    if not pointer:
        raise RuntimeError("Steam returned a missing interface.")
    table = C.cast(pointer, C.POINTER(C.POINTER(P))).contents
    # Windows x64 uses one common ABI for member functions and C exports.
    return C.CFUNCTYPE(result, P, *args)(table[slot])


class SteamSession:
    def __init__(self, app_id, *, library_mode=False):
        if sys.platform != "win32" or C.sizeof(P) != 8:
            raise RuntimeError("This build requires Windows and a 64-bit Python/runtime.")
        if type(app_id) is not int or not (0 < app_id < 2**32 or library_mode and app_id == 0):
            raise ValueError("Enter a valid numeric Steam App ID.")
        if library_mode and app_id != 0:
            raise ValueError("Library scans must not select a game context.")
        self.library_mode = library_mode
        self.app_id, self.pipe, self.user = app_id, 0, 0
        if library_mode:
            os.environ.pop("SteamAppId", None)
            os.environ.pop("SteamGameId", None)
        else:
            os.environ["SteamAppId"] = str(app_id)
            os.environ["SteamGameId"] = str(app_id)
        root = steam_path()
        self._dirs = [os.add_dll_directory(str(p)) for p in (root, root / "bin") if p.is_dir()]
        self.dll = C.CDLL(str(root / "steamclient64.dll"))
        create = self.dll.CreateInterface
        create.argtypes, create.restype = [S, P], P
        self.client = create(b"SteamClient018", None)
        self.get_callback = self.dll.Steam_BGetCallback
        self.get_callback.argtypes = [I, C.POINTER(Callback), C.POINTER(Q)]
        self.get_callback.restype = B
        self.free_callback = self.dll.Steam_FreeLastCallback
        self.free_callback.argtypes, self.free_callback.restype = [I], None
        try:
            self.pipe = self.call(self.client, 0, I)
            if not self.pipe:
                raise RuntimeError("Steam could not open a connection. Start Steam first.")
            self.user = self.call(self.client, 2, I, (I,), self.pipe)
            if not self.user:
                raise RuntimeError("Sign in to Steam and try again.")
            self.utils = self.call(self.client, 9, P, (I, S), self.pipe, b"SteamUtils005")
            if self.call(self.utils, 9, U) != app_id:
                raise RuntimeError("Steam connected to a different App ID. No changes are allowed.")
            self.steam_user = self.interface(5, b"SteamUser012")
            if not self.call(self.steam_user, 1, B):
                raise RuntimeError("Steam is offline. Connect before reading or applying achievements.")
            identity = Q()
            self.call(self.steam_user, 2, None, (C.POINTER(Q),), C.byref(identity))
            self.account_id = identity.value
            if not self.account_id:
                raise RuntimeError("Steam did not return an account identity.")
            self.apps = self.interface(15, b"STEAMAPPS_INTERFACE_VERSION008")
            if not library_mode and not self.call(self.apps, 6, B, (U,), app_id):
                raise RuntimeError("This Steam account does not have access to that game.")
            if not library_mode:
                self.stats = self.interface(13, b"STEAMUSERSTATS_INTERFACE_VERSION013")
        except BaseException:
            self.close()
            raise

    @staticmethod
    def call(pointer, slot, result, types=(), *values):
        return method(pointer, slot, result, *types)(pointer, *values)

    def interface(self, slot, version):
        return self.call(self.client, slot, P, (I, I, S), self.user, self.pipe, version)

    def drain(self, wanted=None, timeout=0):
        deadline = time.monotonic() + timeout
        while True:
            message, call = Callback(), Q()
            while self.get_callback(self.pipe, C.byref(message), C.byref(call)):
                try:
                    if message.id == wanted and message.size >= 12:
                        data = C.string_at(message.data, message.size)
                        game, result = struct.unpack_from("<Qi", data)
                        if game & 0xFFFFFF == self.app_id:
                            if wanted == 1101:
                                # CSteamID is 4-byte aligned in this Windows callback;
                                # the payload can include tail padding to 24 bytes.
                                offset = 12
                                if len(data) < offset + 8 or struct.unpack_from("<Q", data, offset)[0] != self.account_id:
                                    continue
                            if result != 1:
                                raise RuntimeError(f"Steam rejected the request (result {result}).")
                            return
                finally:
                    self.free_callback(self.pipe)
            if not wanted:
                return
            if time.monotonic() >= deadline:
                raise TimeoutError("Steam did not confirm the request within 20 seconds.")
            time.sleep(0.03)

    def read(self):
        self.require_game()
        self.verify_identity()
        self.drain()
        handle = self.call(self.stats, 15, Q, (Q,), self.account_id)
        if not handle:
            raise RuntimeError("Steam refused to request achievement data.")
        self.drain(1101, 20)
        count = self.call(self.stats, 13, U)
        if count > 10000:
            raise RuntimeError("Unexpected achievement count. Steam interface may have changed.")
        rows = []
        for index in range(count):
            raw = self.call(self.stats, 14, S, (U,), index)
            if not raw:
                raise RuntimeError("Steam returned an invalid achievement identifier.")
            key = raw.decode("utf-8", "strict")
            state, timestamp = B(), U()
            ok = self.call(self.stats, 8, B, (S, C.POINTER(B), C.POINTER(U)), raw, C.byref(state), C.byref(timestamp))
            if not ok:
                raise RuntimeError(f"Could not read achievement {key}. Reload the game.")
            def attr(name):
                value = self.call(self.stats, 11, S, (S, S), raw, name)
                return value.decode("utf-8", "replace") if value else ""
            rows.append(Achievement(key, attr(b"name") or key, attr(b"desc"), bool(state.value), timestamp.value, attr(b"hidden") == "1"))
        return rows

    def set_state(self, key, state):
        self.require_game()
        self.verify_identity()
        return bool(self.call(self.stats, 6 if state else 7, B, (S,), key.encode("utf-8")))

    def store(self):
        self.require_game()
        self.verify_identity()
        self.drain()
        if not self.call(self.stats, 9, B):
            raise RuntimeError("Steam refused to submit changes. Local cached changes may still persist later.")
        self.drain(1102, 20)

    def require_game(self):
        if self.library_mode:
            raise RuntimeError("Library discovery cannot read or modify achievements.")

    def verify_identity(self):
        identity = Q()
        self.call(self.steam_user, 2, None, (C.POINTER(Q),), C.byref(identity))
        if identity.value != self.account_id or not self.call(self.steam_user, 1, B):
            raise RuntimeError("Steam account or connection changed. Reopen the game.")
        if self.call(self.utils, 9, U) != self.app_id:
            raise RuntimeError("Steam App ID changed. Reopen the game.")

    def close(self):
        if self.pipe and self.user:
            self.call(self.client, 4, None, (I, I), self.pipe, self.user)
            self.user = 0
        if self.pipe:
            self.call(self.client, 1, B, (I,), self.pipe)
            self.pipe = 0


class SteamLibrarySession(SteamSession):
    """App ID 0: ownership/metadata queries, with no per-game stats interface."""
    def __init__(self):
        super().__init__(0, library_mode=True)
        try:
            self.metadata = self.interface(15, b"STEAMAPPS_INTERFACE_VERSION001")
        except BaseException:
            self.close()
            raise

    def owns(self, app_id):
        return bool(self.call(self.apps, 6, B, (U,), app_id))

    def app_data(self, app_id, key):
        buffer = C.create_string_buffer(4096)
        size = self.call(self.metadata, 0, I, (U, S, P, I), app_id, key, buffer, len(buffer))
        return buffer.value.decode("utf-8", "replace").strip() if size > 0 else ""

    def app_name(self, app_id):
        return self.app_data(app_id, b"name")

    def app_icon(self, app_id):
        value = self.app_data(app_id, b"icon")
        return value.lower() if re.fullmatch(r"[a-fA-F0-9]{40}", value) else ""
