# -*- coding: utf-8 -*-
"""Helpers for Korail mobile anti-bot request headers."""

import base64
import secrets
import time

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad


DYNAPATH_PATHS = (
    "/classes/com.korail.mobile.certification.TicketReservation",
    "/classes/com.korail.mobile.nonMember.NonMemTicket",
    "/classes/com.korail.mobile.seatMovie.ScheduleView",
    "/classes/com.korail.mobile.seatMovie.ScheduleViewSpecial",
    "/classes/com.korail.mobile.trn.prcFare.do",
    "/classes/com.korail.mobile.login.Login",
)


class DynaPathMasterEngine(object):
    APP_ID = "com.korail.talk"
    AS_VALUE = "%5B38ff229cb34c7dda8e28220a2d750cce%5D"
    DEVICE_MODEL = "SM-S928N"
    OS_TYPE = "Android"
    SDK_VERSION = "v1"

    def __init__(self):
        self.table = "3FE9jgRD4KdCyuawklqGJYmvfMn15P7US8XbxeLQtWT6OicBAopINs2Vh0HZrz"
        self.i8 = 161
        self.i9 = 30
        self.i10 = 2
        self.app_start_ts = str(int(time.time() * 1000))

    def _string_to_units(self, text):
        units = []
        index = 0
        while index < len(text):
            cp = ord(text[index])
            index += 1
            if cp < 128:
                units.append(cp)
            elif cp < 2048:
                units.append(128 | ((cp >> 7) & 15))
                units.append(cp & 127)
            elif cp >= 262144:
                units.append(160)
                units.append((cp >> 14) & 127)
                units.append((cp >> 7) & 127)
                units.append(cp & 127)
            elif (63488 & cp) != 55296:
                units.append(((cp >> 14) & 15) | 144)
                units.append((cp >> 7) & 127)
                units.append(cp & 127)
        return units

    def _make_key(self, text):
        total = 0
        for char in text:
            cp = ord(char)
            hi_bit = 32768
            for _ in range(16):
                if hi_bit & cp:
                    break
                hi_bit >>= 1
            total = (total * (hi_bit << 1)) + cp
        return total

    def _next_char(self, base_table, remainder, current):
        seen = 0
        for char in base_table:
            if char not in current:
                if seen == remainder:
                    return char
                seen += 1
        return " "

    def _make_encode_table(self, num, encode_size, base_table):
        chars = []
        value = num
        for index in range(encode_size):
            divisor = encode_size - index
            remainder = value % divisor
            chars.append(self._next_char(base_table, remainder, "".join(chars)))
            value //= divisor
        return "".join(chars)

    def _encode(self, text, table, i8=None, i9=None, i10=None):
        base_i8 = self.i8 if i8 is None else i8
        base_i9 = self.i9 if i9 is None else i9
        base_i10 = self.i10 if i10 is None else i10
        units = self._string_to_units(text)
        encoded = []
        tmp = [0] * (base_i10 + 1)
        index = 0
        tail = len(units) % base_i10
        stop = len(units) - tail

        while index < stop:
            value = 0
            for _ in range(base_i10):
                value = (value * base_i8) + units[index]
                index += 1
            for pos in range(base_i10 + 1):
                tmp[pos] = value % base_i9
                value //= base_i9
            for pos in range(base_i10, -1, -1):
                encoded.append(table[tmp[pos]])

        if tail > 0:
            value = 0
            for _ in range(tail):
                value = (value * base_i8) + units[index]
                index += 1
            for pos in range(tail + 1):
                tmp[pos] = value % base_i9
                value //= base_i9
            while tail >= 0:
                encoded.append(table[tmp[tail]])
                tail -= 1

        return "".join(encoded)

    def generate_token(self, device_id, ts, nonce):
        payload = (
            "ai={app_id}&di={device_id}&as={as_value}&"
            "su=false&dbg=false&emu=false&hk=false&it={app_start_ts}&"
            "ts={ts}&rt=0&os=13&dm={device_model}&st={os_type}&sv={sdk_version}"
        ).format(
            app_id=self.APP_ID,
            device_id=device_id,
            as_value=self.AS_VALUE,
            app_start_ts=self.app_start_ts,
            ts=ts,
            device_model=self.DEVICE_MODEL,
            os_type=self.OS_TYPE,
            sdk_version=self.SDK_VERSION,
        )

        dynamic_key = "v1+{nonce}+{ts}".format(nonce=nonce, ts=ts)
        encoded_key = self._encode(dynamic_key, self.table)
        custom_table = self._make_encode_table(
            self._make_key(dynamic_key),
            self.i9,
            self.table,
        )
        encoded_body = self._encode(payload, custom_table)
        return "bEeEP{prefix}{key}{body}".format(
            prefix=self.table[len(encoded_key)],
            key=encoded_key,
            body=encoded_body,
        )


class KorailAntiBotHelper(object):
    def __init__(
        self,
        engine=None,
        device="AD",
        version="250601002",
        sid_key=b"2485dd54d9deaa36",
        device_id="558a4f02041657ea",
    ):
        self.engine = engine or DynaPathMasterEngine()
        self.device = device
        self.version = version
        self.sid_key = sid_key
        self.device_id = device_id

    def needs_token(self, url):
        return any(path in url for path in DYNAPATH_PATHS)

    def generate_sid(self, ts):
        plaintext = "{device}{ts}".format(device=self.device, ts=ts).encode("utf-8")
        cipher = AES.new(self.sid_key, AES.MODE_CBC, iv=self.sid_key)
        token = cipher.encrypt(pad(plaintext, 16))
        return base64.b64encode(token).decode("utf-8") + "\n"

    def build(self, url):
        headers = {}
        data = {}
        if not self.needs_token(url):
            return headers, data

        timestamp = int(time.time() * 1000)
        nonce = "".join(secrets.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(4))
        headers["x-dynapath-m-token"] = self.engine.generate_token(
            self.device_id,
            timestamp,
            nonce,
        )
        data["Sid"] = self.generate_sid(timestamp)
        return headers, data
