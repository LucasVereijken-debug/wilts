import asyncio
import base64
import json
import random
import time
import uuid

import aiohttp
import discord
from discord.ext import commands

from . import state as S

GAMES_CDN = "https://cdn.discordapp.com/detectables/games.json"
SCIENCE_URL = "https://discord.com/api/v9/science"
ME_ANALYTICS = "https://discord.com/api/v9/users/@me?with_analytics_token=true"
BATCH = 40

FALLBACK_GAMES = [
    ("356875220204089344", "League of Legends", "LeagueClientUx.exe"),
    ("356833217536000000", "Counter-Strike 2", "cs2.exe"),
    ("401518684763586560", "Fortnite", "FortniteClient-Win64-Shipping.exe"),
    ("356875476870463500", "Minecraft", "javaw.exe"),
    ("432980957394370572", "Roblox", "RobloxPlayerBeta.exe"),
    ("363444185328156672", "Grand Theft Auto V", "GTA5.exe"),
    ("438122941302703104", "VALORANT", "VALORANT-Win64-Shipping.exe"),
    ("356870059756322816", "Overwatch 2", "Overwatch.exe"),
    ("356875220204089345", "Apex Legends", "r5apex.exe"),
    ("401518684763586561", "Call of Duty", "cod.exe"),
]


def _ua():
    return getattr(S, "USER_AGENT", None) or (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) discord/1.0.9262 Chrome/155.0.0.0 Electron/36.0.0 Safari/537.36"
    )


def _xsp():
    x = getattr(S, "X_SUPER_PROPERTIES", None) or ""
    if x:
        return x
    props = {
        "os": "Windows",
        "browser": "Discord Client",
        "device": "",
        "system_locale": "en-US",
        "browser_user_agent": _ua(),
        "browser_version": "1.0.9262",
        "os_version": "10",
        "release_channel": "stable",
        "client_build_number": 630444,
        "client_event_source": None,
    }
    return base64.b64encode(json.dumps(props, separators=(",", ":")).encode()).decode()


def _headers(token, cookie=""):
    h = {
        "Authorization": token,
        "Content-Type": "application/json",
        "User-Agent": _ua(),
        "X-Super-Properties": _xsp(),
        "Origin": "https://discord.com",
        "Referer": "https://discord.com/channels/@me",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Discord-Locale": "en-US",
    }
    if cookie:
        h["Cookie"] = cookie
    return h


class BadgeCog(commands.Cog, name="badge"):
    def __init__(self, bot):
        self.bot = bot
        self._games = []
        self._analytics = None
        self._seq = 0
        self._hb_session = str(uuid.uuid4())
        self._launch_sig = str(uuid.uuid4())
        self._busy = False

    def _token(self):
        return S._get_token() if hasattr(S, "_get_token") else getattr(S, "TOKEN", "") or ""

    def _cookie(self):
        import os
        return (os.environ.get("DISCORD_COOKIE") or os.environ.get("CF_CLEARANCE") or "").strip()

    def _next_seq(self):
        self._seq += 1
        return self._seq

    async def _fetch_analytics(self, session):
        async with session.get(ME_ANALYTICS, headers=_headers(self._token(), self._cookie())) as r:
            if r.status != 200:
                return None
            data = await r.json()
            return data.get("analytics_token")

    async def _load_games(self, session):
        try:
            async with session.get(GAMES_CDN, headers={"User-Agent": "Mozilla/5.0"}) as r:
                if r.status != 200:
                    return list(FALLBACK_GAMES)
                data = await r.json()
        except Exception:
            return list(FALLBACK_GAMES)
        out = []
        seen = set()
        for entry in data:
            gid = str(entry.get("id") or "")
            if not gid.isdigit() or gid in seen:
                continue
            exe = "game.exe"
            for e in entry.get("executables") or []:
                if e.get("os") == "win32" and e.get("name"):
                    exe = e["name"]
                    break
            else:
                continue
            seen.add(gid)
            out.append((gid, entry.get("name") or "Unknown", exe))
        return out or list(FALLBACK_GAMES)

    def _launch_event(self, gid, name, exe):
        now = int(time.time() * 1000)
        props = {
            "client_track_timestamp": now,
            "client_heartbeat_session_id": self._hb_session,
            "event_sequence_number": self._next_seq(),
            "game": name,
            "game_id": gid,
            "verified": True,
            "elevated": False,
            "is_launcher": False,
            "game_platform": "desktop",
            "detection_method": "verified_game",
            "is_overlay_enabled": False,
            "is_overlay_game_enabled": True,
            "is_overlay_game_source": "OOP_DEFAULT_DATABASE",
            "fullscreen_type": "UNKNOWN",
            "hardware_display_count": 1,
            "overlay_method": "Disabled",
            "activity_status_enabled": True,
            "activity_status_shared_guilds": [],
            "current_user_status": "online",
            "game_detection_enabled": True,
            "executable_path": exe,
            "voice_channel_id": None,
            "voice_channel_type": None,
            "voice_channel_bitrate": None,
            "voice_channel_guild_id": None,
            "hidden_by_distributor": False,
            "game_metadata": None,
            "client_performance_cpu": None,
            "client_performance_memory": None,
            "cpu_core_count": None,
            "accessibility_features": 0,
            "rendered_locale": "en-US",
            "launch_signature": self._launch_sig,
            "client_rtc_state": None,
            "client_app_state": "focused",
            "client_send_timestamp": now,
        }
        return {"type": "launch_game", "properties": props}

    def _hb_event(self, gid, name, exe, duration_ms, sid, initial, final, ts=None):
        ts = int(time.time() * 1000) if ts is None else ts
        return {
            "type": "running_game_heartbeat",
            "properties": {
                "client_track_timestamp": ts,
                "client_heartbeat_session_id": self._hb_session,
                "event_sequence_number": self._next_seq(),
                "game_id": gid,
                "game_name": name,
                "game_metadata": None,
                "game_executable": exe,
                "game_detection_enabled": True,
                "initial_heartbeat": initial,
                "final_heartbeat": final,
                "game_session_id": sid,
                "duration_tracked_ms": duration_ms,
                "rtc_connection_id": None,
                "media_session_id": None,
                "launch_signature": self._launch_sig,
                "client_app_state": "focused",
                "client_send_timestamp": ts,
            },
        }

    def _session_events(self, gid, name, exe, duration_ms):
        sid = str(uuid.uuid4())
        now = int(time.time() * 1000)
        start = max(0, now - duration_ms)
        return [
            self._hb_event(gid, name, exe, 0, sid, True, False, start),
            self._launch_event(gid, name, exe),
            self._hb_event(gid, name, exe, duration_ms, sid, False, True, now),
        ]

    async def _post_science(self, session, events):
        if not self._analytics:
            return 0
        payload = {"token": self._analytics, "events": events}
        try:
            async with session.post(
                SCIENCE_URL,
                headers=_headers(self._token(), self._cookie()),
                json=payload,
            ) as r:
                return r.status
        except Exception:
            return 0


    def _stream_events(self, duration_ms: int, guild_id: str = "0", channel_id: str = "0"):
        now = int(time.time() * 1000)
        media_session = str(uuid.uuid4())
        rtc_id = str(uuid.uuid4())
        stream_key = "guild:%s:%s:%s" % (guild_id or "0", channel_id or "0", str(getattr(getattr(self.bot, "user", None), "id", 0) or 0))
        start = {
            "type": "video_stream_started",
            "properties": {
                "client_track_timestamp": now - duration_ms,
                "client_heartbeat_session_id": self._hb_session,
                "event_sequence_number": self._next_seq(),
                "media_session_id": media_session,
                "rtc_connection_id": rtc_id,
                "stream_key": stream_key,
                "context": "STREAM",
                "connection_type": "guild",
                "stream_type": "screen",
                "application_id": None,
                "game_name": None,
                "game_id": None,
            },
        }
        finish = {
            "type": "screenshare_finished",
            "properties": {
                "client_track_timestamp": now,
                "client_heartbeat_session_id": self._hb_session,
                "event_sequence_number": self._next_seq(),
                "media_session_id": media_session,
                "rtc_connection_id": rtc_id,
                "stream_key": stream_key,
                "context": "STREAM",
                "duration_ms": int(duration_ms),
                "screenshare_frames": max(1, int(duration_ms / 33)),
                "total_frames": max(1, int(duration_ms / 33)),
                "desktop_capturer_type": "DXGI",
                "soundshare_session": False,
                "application_id": None,
                "game_name": None,
                "game_id": None,
            },
        }
        # alternate name some builds use
        stream_end = {
            "type": "stream_ended",
            "properties": {
                "client_track_timestamp": now,
                "client_heartbeat_session_id": self._hb_session,
                "event_sequence_number": self._next_seq(),
                "media_session_id": media_session,
                "duration_ms": int(duration_ms),
                "stream_key": stream_key,
                "viewer_count": 1,
                "context": "STREAM",
            },
        }
        return [start, finish, stream_end]


    async def _ensure_ready(self, session):
        if not self._token():
            return False, "no token"
        if not self._analytics:
            self._analytics = await self._fetch_analytics(session)
            if not self._analytics:
                return False, "analytics_token failed (check token)"
        if not self._games:
            self._games = await self._load_games(session)
        if not self._games:
            return False, "no games catalog"
        self._hb_session = str(uuid.uuid4())
        self._launch_sig = str(uuid.uuid4())
        self._seq = 0
        return True, "ok"

    @commands.command(name="playas", aliases=["gameas"])
    async def playas(self, ctx, *, name: str = ""):
        if not name:
            return await S.safe_edit(ctx.message, S.ui_err("playas <name>"))
        try:
            await self.bot.change_presence(activity=discord.Game(name=name[:120]))
            await S.safe_edit(ctx.message, S.ui_ok("playing %s" % name[:80]))
        except Exception as e:
            await S.safe_edit(ctx.message, S.ui_err(str(e)[:120]))

    @commands.command(name="watchas")
    async def watchas(self, ctx, *, name: str = ""):
        if not name:
            return await S.safe_edit(ctx.message, S.ui_err("watchas <name>"))
        try:
            act = discord.Activity(type=discord.ActivityType.watching, name=name[:120])
            await self.bot.change_presence(activity=act)
            await S.safe_edit(ctx.message, S.ui_ok("watching %s" % name[:80]))
        except Exception as e:
            await S.safe_edit(ctx.message, S.ui_err(str(e)[:120]))

    @commands.command(name="listenas")
    async def listenas(self, ctx, *, name: str = ""):
        if not name:
            return await S.safe_edit(ctx.message, S.ui_err("listenas <name>"))
        try:
            act = discord.Activity(type=discord.ActivityType.listening, name=name[:120])
            await self.bot.change_presence(activity=act)
            await S.safe_edit(ctx.message, S.ui_ok("listening %s" % name[:80]))
        except Exception as e:
            await S.safe_edit(ctx.message, S.ui_err(str(e)[:120]))

    @commands.command(name="clearactivity", aliases=["clract"])
    async def clearactivity(self, ctx):
        await self.bot.change_presence(activity=None)
        await S.safe_edit(ctx.message, S.ui_ok("activity cleared"))

    @commands.command(name="gametime", aliases=["gtbadge", "gtclaim"])
    async def gametime(self, ctx, hours: float = 10.0, games: int = 25):
        if self._busy:
            return await S.safe_edit(ctx.message, S.ui_err("badge job already running"))
        hours = max(0.1, min(float(hours), 20000000000.0))
        games = max(1, min(int(games), 20000000000))
        self._busy = True
        await S.safe_edit(ctx.message, S.ui_info("gametime %sh across %d games..." % (hours, games)))
        try:
            async with aiohttp.ClientSession() as session:
                ok, msg = await self._ensure_ready(session)
                if not ok:
                    return await S.safe_edit(ctx.message, S.ui_err(msg))
                n = min(max(games, 1), max(len(self._games) * 50, 1))
                pick = []
                while len(pick) < n:
                    batch = list(self._games)
                    random.shuffle(batch)
                    pick.extend(batch)
                pick = pick[:n]
                ms_each = max(1000, int((hours * 3600 * 1000) / max(1, len(pick))))
                sent = 0
                fail = 0
                for i in range(0, len(pick), BATCH):
                    chunk = pick[i : i + BATCH]
                    events = []
                    for gid, name, exe in chunk:
                        events.extend(self._session_events(gid, name, exe, ms_each))
                    status = await self._post_science(session, events)
                    if status == 204:
                        sent += len(chunk)
                    else:
                        fail += len(chunk)
                        if status in (401, 403):
                            return await S.safe_edit(
                                ctx.message,
                                S.ui_err("science %s — set DISCORD_COOKIE=cf_clearance if needed" % status),
                            )
                    await asyncio.sleep(0.12 if len(pick) > 200 else 0.35)
                await S.safe_edit(
                    ctx.message,
                    S.ui_ok(
                        "gametime claimed ~%sh · ok=%d fail=%d · badge may lag 1-2 days"
                        % (hours, sent, fail)
                    ),
                )
        except Exception as e:
            await S.safe_edit(ctx.message, S.ui_err(str(e)[:160]))
        finally:
            self._busy = False

    @commands.command(name="gamevariety", aliases=["gvariety", "gamesplayed"])
    async def gamevariety(self, ctx, count: int = 50):
        if self._busy:
            return await S.safe_edit(ctx.message, S.ui_err("badge job already running"))
        count = max(1, min(int(count), 20000000000))
        self._busy = True
        await S.safe_edit(ctx.message, S.ui_info("gamevariety %d titles..." % count))
        try:
            async with aiohttp.ClientSession() as session:
                ok, msg = await self._ensure_ready(session)
                if not ok:
                    return await S.safe_edit(ctx.message, S.ui_err(msg))
                if not self._games:
                    return await S.safe_edit(ctx.message, S.ui_err("no games catalog"))
                pick = []
                while len(pick) < count:
                    need = count - len(pick)
                    batch = list(self._games)
                    random.shuffle(batch)
                    pick.extend(batch[:need])
                pick = pick[:count]
                ms_each = 60 * 1000
                sent = 0
                fail = 0
                for i in range(0, len(pick), BATCH):
                    chunk = pick[i : i + BATCH]
                    events = []
                    for gid, name, exe in chunk:
                        events.extend(self._session_events(gid, name, exe, ms_each))
                    status = await self._post_science(session, events)
                    if status == 204:
                        sent += len(chunk)
                    else:
                        fail += len(chunk)
                        if status in (401, 403):
                            return await S.safe_edit(
                                ctx.message,
                                S.ui_err("science %s — set DISCORD_COOKIE if needed" % status),
                            )
                    await asyncio.sleep(0.12 if len(pick) > 200 else 0.35)
                await S.safe_edit(
                    ctx.message,
                    S.ui_ok("variety claimed %d · ok=%d fail=%d · lag 1-2 days" % (count, sent, fail)),
                )
        except Exception as e:
            await S.safe_edit(ctx.message, S.ui_err(str(e)[:160]))
        finally:
            self._busy = False

    @commands.command(name="streamtime", aliases=["stbadge", "streamclaim"])
    async def streamtime(self, ctx, hours: float = 5.0, chunks: int = 8):
        if self._busy:
            return await S.safe_edit(ctx.message, S.ui_err("badge job already running"))
        hours = max(0.1, min(float(hours), 20000000000.0))
        chunks = max(1, min(int(chunks), 20000000000))
        self._busy = True
        await S.safe_edit(ctx.message, S.ui_info("streamtime %sh across %d sessions..." % (hours, chunks)))
        try:
            async with aiohttp.ClientSession() as session:
                ok, msg = await self._ensure_ready(session)
                if not ok:
                    return await S.safe_edit(ctx.message, S.ui_err(msg))
                total_ms = int(hours * 3600 * 1000)
                per = max(60_000, total_ms // chunks)
                sent = 0
                fail = 0
                gid = str(getattr(getattr(ctx, "guild", None), "id", 0) or 0)
                cid = str(getattr(getattr(ctx, "channel", None), "id", 0) or 0)
                for i in range(chunks):
                    events = self._stream_events(per, gid, cid)
                    status = await self._post_science(session, events)
                    if status == 204:
                        sent += 1
                    else:
                        fail += 1
                        if status in (401, 403):
                            return await S.safe_edit(
                                ctx.message,
                                S.ui_err("science %s — set DISCORD_COOKIE if needed" % status),
                            )
                    await asyncio.sleep(0.4)
                await S.safe_edit(
                    ctx.message,
                    S.ui_ok(
                        "stream claimed ~%sh · ok=%d fail=%d · needs real viewers sometimes · lag 1-2d"
                        % (hours, sent, fail)
                    ),
                )
        except Exception as e:
            await S.safe_edit(ctx.message, S.ui_err(str(e)[:160]))
        finally:
            self._busy = False

    @commands.command(name="badgeall", aliases=["claimallbadges"])
    async def badgeall(self, ctx, hours: float = 20.0, games: int = 50):
        if self._busy:
            return await S.safe_edit(ctx.message, S.ui_err("badge job already running"))
        await S.safe_edit(ctx.message, S.ui_info("badgeall: variety + gametime + stream..."))
        try:
            await self.gamevariety(ctx, count=max(int(games), 30))
            await self.gametime(ctx, hours=float(hours), games=max(int(games), 10))
            await self.streamtime(ctx, hours=max(float(hours) * 0.5, 1.0), chunks=6)
        except Exception as e:
            await S.safe_edit(ctx.message, S.ui_err(str(e)[:160]))




    @commands.command(name="badgestats", aliases=["bstats", "mybadges", "badgestat"])
    async def badgestats(self, ctx, user: discord.User = None):
        uid = (user.id if user else ctx.author.id)
        token = S._get_token()
        if not token:
            return await S.safe_edit(ctx.message, S.ui_err("no token"))
        try:
            from utils.gateway import default_headers, client_properties
            headers = default_headers(token, client_properties(platform="desktop"))
        except Exception:
            headers = {
                "Authorization": token,
                "User-Agent": getattr(S, "USER_AGENT", "Mozilla/5.0"),
                "X-Super-Properties": getattr(S, "X_SUPER_PROPERTIES", "") or "",
            }
        profile = None
        async with aiohttp.ClientSession() as session:
            for attempt in range(3):
                try:
                    async with session.get(
                        "https://discord.com/api/v9/users/%s/profile" % uid,
                        headers=headers,
                        params={"with_mutual_guilds": "true"},
                    ) as r:
                        if r.status == 200:
                            profile = await r.json(content_type=None)
                            break
                        if r.status == 429:
                            try:
                                data = await r.json(content_type=None)
                                wait = float(data.get("retry_after", 1.5 + attempt))
                            except Exception:
                                wait = 1.5 + attempt
                            await asyncio.sleep(min(wait, 12))
                            continue
                        if r.status in (401, 403, 404):
                            return await S.safe_edit(
                                ctx.message,
                                S.ui_err("profile %s — mutual server needed for others" % r.status),
                            )
                        break
                except Exception as e:
                    if attempt == 2:
                        return await S.safe_edit(ctx.message, S.ui_err(str(e)[:140]))
                    await asyncio.sleep(1)
        if not isinstance(profile, dict):
            return await S.safe_edit(ctx.message, S.ui_err("no profile data"))

        u = profile.get("user") if isinstance(profile.get("user"), dict) else {}
        badges = profile.get("badges") or []
        rows = []
        # account age
        try:
            created_ms = ((int(uid) >> 22) + 1420070400000)
            age_days = max(0, (time.time() * 1000 - created_ms) / 86400000.0)
            age_years = age_days / 365.25
            rows.append("  %sage%s        %.1f years (%.0f days)" % (S.DIM, S.RESET, age_years, age_days))
        except Exception:
            rows.append("  %sage%s        ?" % (S.DIM, S.RESET))

        nitro = profile.get("premium_since") or profile.get("premium_type") or u.get("premium_type")
        rows.append(
            "  %snitro%s      %s"
            % (S.DIM, S.RESET, ("yes · type %s" % (profile.get("premium_type") or u.get("premium_type") or "?")) if nitro else "no")
        )

        gt_h = st_h = var_n = None
        other = []
        for b in badges:
            if not isinstance(b, dict):
                continue
            bid = str(b.get("id") or "").lower()
            desc = str(b.get("description") or b.get("id") or "badge")
            meta = b.get("metadata") if isinstance(b.get("metadata"), dict) else {}
            val = None
            for k in ("hours", "play_time_hours", "total_hours", "value", "count", "games"):
                if meta.get(k) is not None:
                    try:
                        val = float(meta[k])
                        break
                    except Exception:
                        pass
            if val is None:
                for k in ("duration_ms", "play_time_ms", "total_ms", "milliseconds"):
                    if meta.get(k) is not None:
                        try:
                            val = float(meta[k]) / 3600000.0
                            break
                        except Exception:
                            pass
            if any(x in bid for x in ("game_time", "gametime", "play_time", "played")):
                gt_h = val if val is not None else gt_h
            elif any(x in bid for x in ("stream", "streaming", "broadcast")):
                st_h = val if val is not None else st_h
            elif any(x in bid for x in ("variety", "game_variety", "diverse")):
                var_n = val if val is not None else var_n
            else:
                extra = ""
                if val is not None:
                    extra = " · %s" % (int(val) if val == int(val) else "%.2f" % val)
                other.append("%s%s" % (desc[:40], extra))

        def fmt_h(h):
            if h is None:
                return "unknown (not on profile yet)"
            if h >= 1000:
                return "%.0fh" % h
            return "%.2fh" % h

        rows.append("  %sgametime%s   %s" % (S.DIM, S.RESET, fmt_h(gt_h)))
        rows.append("  %sstream%s     %s" % (S.DIM, S.RESET, fmt_h(st_h)))
        rows.append(
            "  %svariety%s    %s"
            % (S.DIM, S.RESET, ("%s games" % int(var_n)) if var_n is not None else "unknown")
        )
        if other:
            rows.append("  %sother%s      %s" % (S.DIM, S.RESET, ", ".join(other[:10])))
        else:
            rows.append("  %sother%s      none listed" % (S.DIM, S.RESET))

        rows.append("")
        rows.append("  %stiers gt%s   1 / 5 / 20 / 75 / 150 / 300 / 500 / 1k / 2k / 5k h" % (S.DIM, S.RESET))
        rows.append("  %stiers st%s   1 / 5 / 20 / 75 / 150 / 300 / 500 / 1k / 2k / 5k h" % (S.DIM, S.RESET))
        rows.append("  %sclaim%s     .gametime / .gamevariety / .streamtime / .badgeall" % (S.DIM, S.RESET))
        await S.safe_edit(ctx.message, S.ui_box("badge stats", rows))

    @commands.command(name="badgestop", aliases=["gtstop", "badgecancel"])
    async def badgestop(self, ctx):
        self._busy = False
        await S.safe_edit(ctx.message, S.ui_ok("badge job flag cleared (in-flight requests may finish)"))

    @commands.command(name="badgetiers", aliases=["badgesinfo"])
    async def badgetiers(self, ctx):
        rows = [
            "  stats       .badgestats [@user]",
            "  game time   .gametime <hours> [games]",
            "  variety     .gamevariety [count]",
            "  streaming   .streamtime <hours> [chunks]",
            "  all three   .badgeall [hours] [games]",
            "  stop        .badgestop",
            "  hypesquad   .hypesquad <bravery|brilliance|balance|leave>",
            "  tiers gt    1/5/20/75/150/300/500/1k/2k/5k h",
            "  tiers stream 1/5/20/75/150/300/500/1k/2k/5k h",
            "  cap         hours/count up to 20e9",
            "  note        stream badge may need real viewers",
            "  optional    DISCORD_COOKIE=cf_clearance",
        ]
        await S.safe_edit(ctx.message, S.ui_box("badges", rows))


async def setup(bot):
    if "badge" in bot.cogs:
        await bot.remove_cog("badge")
    await bot.add_cog(BadgeCog(bot))
