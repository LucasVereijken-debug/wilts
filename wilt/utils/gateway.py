import base64
import json
import os
import random
import string
import time
import uuid
from typing import Any, Optional

API_BASE = "https://discord.com/api/v9"
GATEWAY_URL = "wss://gateway.discord.gg/?v=9&encoding=json&compress=zlib-stream"
GATEWAY_URL_JSON = "wss://gateway.discord.gg/?v=9&encoding=json"

BUILD = int(os.environ.get("CLIENT_BUILD_NUMBER", "641004") or 641004)
CHROME = os.environ.get("CHROME_VERSION", "155.0.8059.80")
ELECTRON = os.environ.get("ELECTRON_VERSION", "36.2.0")
DISCORD_VER = os.environ.get("DISCORD_CLIENT_VERSION", "1.0.9262")
NATIVE_BUILD = int(os.environ.get("NATIVE_BUILD_NUMBER", "94186") or 94186)
LOCALE = os.environ.get("SYSTEM_LOCALE", "en-US")

CAP_LAZY_USER_NOTES = 1 << 0
CAP_NO_AFFINE_USER_IDS = 1 << 1
CAP_VERSIONED_READ_STATES = 1 << 2
CAP_VERSIONED_USER_GUILD_SETTINGS = 1 << 3
CAP_DEDUPE_USER_GUILD_SETTINGS = 1 << 4
CAP_PRIORITIZED_READY = 1 << 5
CAP_MULTIPLE_GUILD_EXPERIMENT = 1 << 6
CAP_NON_CHANNEL_NOTIFICATION = 1 << 7
CAP_AUTH_TOKEN_REFRESH = 1 << 8
CAP_USER_SETTINGS_PROTO = 1 << 9
CAP_CLIENT_STATE_V2 = 1 << 12
CAP_PASSIVE_GUILD_UPDATE = 1 << 13

CLIENT_CAPABILITIES_DESKTOP = 30717  # observed desktop client
DEFAULT_CAPABILITIES = (
    CAP_LAZY_USER_NOTES
    | CAP_NO_AFFINE_USER_IDS
    | CAP_VERSIONED_READ_STATES
    | CAP_VERSIONED_USER_GUILD_SETTINGS
    | CAP_DEDUPE_USER_GUILD_SETTINGS
    | CAP_PRIORITIZED_READY
    | CAP_MULTIPLE_GUILD_EXPERIMENT
    | CAP_NON_CHANNEL_NOTIFICATION
    | CAP_AUTH_TOKEN_REFRESH
    | CAP_USER_SETTINGS_PROTO
    | CAP_CLIENT_STATE_V2
    | CAP_PASSIVE_GUILD_UPDATE
)


def _stable_id(name: str, prefix: str) -> str:
    path = os.environ.get("WILT_STATE_DIR") or os.path.join(os.getcwd(), ".wilt_state")
    try:
        os.makedirs(path, exist_ok=True)
        fp = os.path.join(path, name + ".txt")
        if os.path.isfile(fp):
            with open(fp, encoding="utf-8") as f:
                val = (f.read() or "").strip()
                if val:
                    return val
        val = _rid(prefix)
        with open(fp, "w", encoding="utf-8") as f:
            f.write(val)
        return val
    except Exception:
        return _rid(prefix)

def _rid(prefix="wilt"):
    return "%s-%s" % (prefix, uuid.uuid4().hex[:12])

def _ua_desktop():
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) discord/%s Chrome/%s Electron/%s Safari/537.36"
        % (DISCORD_VER, CHROME, ELECTRON)
    )

def _ua_web():
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/%s Safari/537.36" % CHROME
    )

def _ua_android():
    return (
        "Discord-Android/250014;Android 14;Google Pixel 8 Pro;"
        "Mobile;okhttp/4.12.0"
    )

def _ua_ios():
    return (
        "Discord/%s CFNetwork/1496.0.7 Darwin/23.5.0" % DISCORD_VER
    )

PLATFORM_PRESETS = {
    "desktop": {
        "os": "Windows",
        "browser": "Discord Client",
        "device": "",
        "browser_user_agent": _ua_desktop(),
        "browser_version": DISCORD_VER,
        "client_version": DISCORD_VER,
        "os_version": "10.0.22631",
        "os_arch": "x64",
        "app_arch": "x64",
        "release_channel": "stable",
        "client_build_number": BUILD,
    },
    "windows": {
        "os": "Windows",
        "browser": "Discord Client",
        "device": "",
        "browser_user_agent": _ua_desktop(),
        "browser_version": DISCORD_VER,
        "client_version": DISCORD_VER,
        "os_version": "10.0.22631",
        "os_arch": "x64",
        "app_arch": "x64",
        "release_channel": "stable",
        "client_build_number": BUILD,
    },
    "macos": {
        "os": "Mac OS X",
        "browser": "Discord Client",
        "device": "",
        "browser_user_agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) discord/%s Chrome/%s Electron/${ELECTRON} Safari/537.36"
            % (DISCORD_VER, CHROME)
        ),
        "browser_version": DISCORD_VER,
        "client_version": DISCORD_VER,
        "os_version": "23.5.0",
        "os_arch": "arm64",
        "app_arch": "arm64",
        "release_channel": "stable",
        "client_build_number": BUILD,
    },
    "linux": {
        "os": "Linux",
        "browser": "Discord Client",
        "device": "",
        "browser_user_agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) discord/%s Chrome/%s Electron/${ELECTRON} Safari/537.36"
            % (DISCORD_VER, CHROME)
        ),
        "browser_version": DISCORD_VER,
        "client_version": DISCORD_VER,
        "os_version": "6.8.0",
        "os_arch": "x64",
        "app_arch": "x64",
        "release_channel": "stable",
        "client_build_number": BUILD,
    },
    "web": {
        "os": "Windows",
        "browser": "Chrome",
        "device": "",
        "browser_user_agent": _ua_web(),
        "browser_version": CHROME.split(".")[0] + ".0.0.0",
        "client_version": CHROME,
        "os_version": "10",
        "os_arch": "x64",
        "app_arch": "x64",
        "release_channel": "stable",
        "client_build_number": BUILD,
    },
    "mobile": {
        "os": "Android",
        "browser": "Discord Android",
        "device": "Pixel 8 Pro",
        "browser_user_agent": _ua_android(),
        "browser_version": "250014",
        "client_version": "250014",
        "os_version": "34",
        "os_arch": "arm64",
        "app_arch": "arm64",
        "release_channel": "stable",
        "client_build_number": BUILD,
    },
    "android": {
        "os": "Android",
        "browser": "Discord Android",
        "device": "Pixel 8 Pro",
        "browser_user_agent": _ua_android(),
        "browser_version": "250014",
        "client_version": "250014",
        "os_version": "34",
        "os_arch": "arm64",
        "app_arch": "arm64",
        "release_channel": "stable",
        "client_build_number": BUILD,
    },
    "ios": {
        "os": "iOS",
        "browser": "Discord iOS",
        "device": "iPhone 15 Pro",
        "browser_user_agent": _ua_ios(),
        "browser_version": DISCORD_VER,
        "client_version": DISCORD_VER,
        "os_version": "17.5",
        "os_arch": "arm64",
        "app_arch": "arm64",
        "release_channel": "stable",
        "client_build_number": BUILD,
    },
    "vr": {
        "os": "Windows",
        "browser": "Discord Client",
        "device": "Oculus Quest",
        "browser_user_agent": _ua_desktop(),
        "browser_version": DISCORD_VER,
        "client_version": DISCORD_VER,
        "os_version": "10.0.22631",
        "os_arch": "x64",
        "app_arch": "x64",
        "release_channel": "stable",
        "client_build_number": BUILD,
    },
    "quest": {
        "os": "Android",
        "browser": "Discord Android",
        "device": "Quest 3",
        "browser_user_agent": _ua_android(),
        "browser_version": "250014",
        "client_version": "250014",
        "os_version": "12",
        "os_arch": "arm64",
        "app_arch": "arm64",
        "release_channel": "stable",
        "client_build_number": BUILD,
    },
    "console": {
        "os": "Windows",
        "browser": "Discord Embedded App",
        "device": "PlayStation 5",
        "browser_user_agent": _ua_desktop(),
        "browser_version": DISCORD_VER,
        "client_version": DISCORD_VER,
        "os_version": "10.0.22631",
        "os_arch": "x64",
        "app_arch": "x64",
        "release_channel": "stable",
        "client_build_number": BUILD,
    },
    "xbox": {
        "os": "Windows",
        "browser": "Discord Embedded App",
        "device": "Xbox Series X",
        "browser_user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; Xbox; Xbox Series X) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/46.0.2486.0 Safari/537.36 Edge/13.10586"
        ),
        "browser_version": DISCORD_VER,
        "client_version": DISCORD_VER,
        "os_version": "10.0.22631",
        "os_arch": "x64",
        "app_arch": "x64",
        "release_channel": "stable",
        "client_build_number": BUILD,
    },
}

def client_properties(override=None, platform: str = "desktop"):
    base = {
        "os": "Windows",
        "browser": "Discord Client",
        "device": "",
        "system_locale": LOCALE,
        "has_client_mods": False,
        "browser_user_agent": _ua_desktop(),
        "browser_version": DISCORD_VER,
        "os_version": "10.0.22631",
        "referrer": "",
        "referring_domain": "",
        "referrer_current": "",
        "referring_domain_current": "",
        "release_channel": "stable",
        "client_build_number": BUILD,
        "client_event_source": None,
        "client_launch_id": os.environ.get("CLIENT_LAUNCH_ID") or _stable_id("launch_id", "launch"),
        "launch_signature": os.environ.get("LAUNCH_SIGNATURE") or _stable_id("launch_sig", "sig"),
        "client_heartbeat_session_id": os.environ.get("CLIENT_HB_SESSION") or _stable_id("hb_session", "hb"),
        "installation_id": os.environ.get("INSTALLATION_ID") or _stable_id("installation_id", "install"),
        "client_app_state": "focused",
        "os_arch": "x64",
        "app_arch": "x64",
        "native_build_number": NATIVE_BUILD,
        "os_sdk_version": "22631",
        "client_version": DISCORD_VER,
    }
    key = (platform or "desktop").lower().strip()
    if key in PLATFORM_PRESETS:
        base.update(PLATFORM_PRESETS[key])
    if isinstance(override, dict):
        base.update(override)
    base["has_client_mods"] = False
    base["system_locale"] = base.get("system_locale") or LOCALE
    base["client_build_number"] = int(base.get("client_build_number") or BUILD)
    return base

def encode_super_properties(props=None) -> str:
    props = props or client_properties()
    raw = json.dumps(props, separators=(",", ":"), ensure_ascii=False)
    return base64.b64encode(raw.encode("utf-8")).decode("ascii")

def decode_super_properties(b64: str) -> dict:
    try:
        pad = "=" * (-len(b64) % 4)
        return json.loads(base64.b64decode(b64 + pad).decode("utf-8"))
    except Exception:
        return {}

def default_headers(token: str, props=None, *, platform: str = "desktop") -> dict:
    props = props or client_properties(platform=platform)
    xsp = encode_super_properties(props)
    ua = props.get("browser_user_agent") or _ua_desktop()
    chrome_major = (CHROME.split(".")[0] if CHROME else "155")
    mobile = (platform or "").lower() in ("mobile", "android", "ios")
    os_name = props.get("os") or "Windows"
    return {
        "Authorization": token,
        "User-Agent": ua,
        "X-Super-Properties": xsp,
        "X-Discord-Locale": props.get("system_locale") or LOCALE,
        "X-Discord-Timezone": os.environ.get("TZ_NAME", "America/New_York"),
        "X-Debug-Options": "bugReporterEnabled",
        "Accept": "*/*",
        "Accept-Language": "%s,en;q=0.9" % (props.get("system_locale") or LOCALE),
        "Origin": "https://discord.com",
        "Referer": "https://discord.com/channels/@me",
        "Sec-Ch-Ua": '"Not;A=Brand";v="99", "Chromium";v="%s"' % chrome_major,
        "Sec-Ch-Ua-Mobile": "?1" if mobile else "?0",
        "Sec-Ch-Ua-Platform": '"%s"' % os_name,
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Content-Type": "application/json",
    }


def api_headers(token: str, props=None, **kw) -> dict:
    return default_headers(token, props, **kw)

def build_identify(
    token: str,
    *,
    props=None,
    capabilities: int = None,
    status: str = "online",
    activities=None,
    afk: bool = False,
    compress: bool = True,
    presence: dict = None,
):
    props = props or client_properties()
    if capabilities is None:
        capabilities = int(os.environ.get("DISCORD_CAPABILITIES", str(DEFAULT_CAPABILITIES)))
    if presence is None:
        presence = {
            "status": status or "online",
            "since": 0,
            "activities": list(activities or []),
            "afk": bool(afk),
        }
    return {
        "op": 2,
        "d": {
            "token": token,
            "capabilities": capabilities,
            "properties": props,
            "presence": presence,
            "compress": bool(compress),
            "client_state": {
                "guild_versions": {},
                "highest_last_message_id": "0",
                "read_state_version": 0,
                "user_guild_settings_version": -1,
                "user_settings_version": -1,
                "private_channels_version": "0",
                "api_code_version": 0,
                "initial_guild_id": None,
            },
        },
    }

def build_resume(token: str, session_id: str, seq: int):
    return {
        "op": 6,
        "d": {
            "token": token,
            "session_id": session_id,
            "seq": seq,
        },
    }

def build_heartbeat(seq=None):
    return {"op": 1, "d": seq}

def apply_http_headers(bot, props=None) -> bool:
    http = getattr(bot, "http", None)
    if http is None:
        return False
    props = props or client_properties()
    xsp = encode_super_properties(props)
    ua = props.get("browser_user_agent") or _ua_desktop()
    chrome_major = (CHROME.split(".")[0] if CHROME else "155")
    try:
        hdrs = getattr(http, "headers", None)
        if isinstance(hdrs, dict):
            hdrs["User-Agent"] = ua
            hdrs["X-Super-Properties"] = xsp
            hdrs["X-Discord-Locale"] = props.get("system_locale") or LOCALE
            hdrs["X-Discord-Timezone"] = os.environ.get("TZ_NAME", "America/New_York")
            hdrs["X-Debug-Options"] = "bugReporterEnabled"
            hdrs["Accept-Language"] = "%s,en;q=0.9" % (props.get("system_locale") or LOCALE)
            hdrs["Origin"] = "https://discord.com"
            hdrs["Referer"] = "https://discord.com/channels/@me"
            hdrs["Sec-Ch-Ua"] = '"Not;A=Brand";v="99", "Chromium";v="%s"' % chrome_major
            hdrs["Sec-Ch-Ua-Mobile"] = "?0"
            hdrs["Sec-Ch-Ua-Platform"] = '"%s"' % (props.get("os") or "Windows")
        for attr, val in (
            ("_super_properties", props),
            ("super_properties", props),
            ("encoded_super_properties", xsp),
            ("_super_properties_b64", xsp),
            ("user_agent", ua),
        ):
            if hasattr(http, attr):
                try:
                    setattr(http, attr, val)
                except Exception:
                    pass
        return True
    except Exception as e:
        print("[gateway] apply_http_headers:", e)
        return False

def install_ws_identify_patch(props=None, capabilities: int = None) -> bool:
    props = props or client_properties()
    if capabilities is None:
        capabilities = int(os.environ.get("DISCORD_CAPABILITIES", str(DEFAULT_CAPABILITIES)))
    try:
        from discord.gateway import DiscordWebSocket as WS
    except Exception as e:
        print("[gateway] no DiscordWebSocket:", e)
        return False

    WS._wilt_fixed_props = props
    WS._wilt_fixed_caps = capabilities

    if getattr(WS, "_wilt_gw_patch_v2", False):
        return True

    for meth_name in ("send_as_json", "send_json"):
        orig = getattr(WS, meth_name, None)
        if orig is None:
            continue

        def _make(o):
            async def _wrapped(self, data, *a, **k):
                try:
                    if isinstance(data, dict) and data.get("op") in (2, "2"):
                        d = data.get("d")
                        if isinstance(d, dict):
                            fixed = getattr(type(self), "_wilt_fixed_props", None) or getattr(WS, "_wilt_fixed_props", None)
                            caps = getattr(type(self), "_wilt_fixed_caps", None)
                            if caps is None:
                                caps = getattr(WS, "_wilt_fixed_caps", None)
                            if isinstance(fixed, dict):
                                cur = d.get("properties")
                                if not isinstance(cur, dict):
                                    cur = {}
                                merged = dict(cur)
                                merged.update(fixed)
                                merged.setdefault("is_fast_connect", False)
                                merged.setdefault("gateway_connect_reasons", "AppSkeleton")
                                merged["has_client_mods"] = False
                                if "installation_id" not in merged:
                                    merged["installation_id"] = fixed.get("installation_id") or _stable_id("installation_id", "install")
                                d["properties"] = merged
                            if caps is not None:
                                d["capabilities"] = int(caps)
                            if "client_state" not in d or not isinstance(d.get("client_state"), dict):
                                d["client_state"] = {
                                    "guild_versions": {},
                                    "highest_last_message_id": "0",
                                    "read_state_version": 0,
                                    "user_guild_settings_version": -1,
                                    "user_settings_version": -1,
                                    "private_channels_version": "0",
                                    "api_code_version": 0,
                                }
                            data["d"] = d
                except Exception as e:
                    print("[gateway] identify patch:", e)
                return await o(self, data, *a, **k)

            return _wrapped

        try:
            setattr(WS, meth_name, _make(orig))
        except Exception as e:
            print("[gateway] wrap", meth_name, e)

    WS._wilt_gw_patch = True
    WS._wilt_gw_patch_v2 = True
    WS._wilt_gw_patch_v3 = True
    WS._wilt_gw_patch_v4 = True
    print("[gateway] IDENTIFY patch v4")
    return True

def install_from_spoofer_preset(preset: dict) -> bool:
    if not isinstance(preset, dict):
        return False
    props = client_properties(override=preset)
    return install_ws_identify_patch(props)

async def probe_gateway_ws(timeout: float = 10.0):
    try:
        import websockets
    except Exception:
        return None
    try:
        async with websockets.connect(
            GATEWAY_URL_JSON,
            additional_headers={"User-Agent": _ua_desktop(), "Origin": "https://discord.com"},
            open_timeout=timeout,
            close_timeout=2,
        ) as ws:
            raw = await ws.recv()
            data = json.loads(raw)
            if data.get("op") == 10:
                return "hello hb=%s" % data.get("d", {}).get("heartbeat_interval")
            return "op=%s" % data.get("op")
    except Exception as e:
        return "probe fail: %s" % e

def merge_props(*parts):
    out = {}
    for p in parts:
        if isinstance(p, dict):
            out.update(p)
    return out
