import aiohttp
import discord
from discord.ext import commands
from . import state as S


def _snowflake_ts(uid):
    from datetime import datetime
    try:
        ts = ((int(uid) >> 22) + 1420070400000) / 1000
        return datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M UTC')
    except Exception:
        return '?'


def _av(uid, av, size=512):
    if not av:
        return 'none'
    ext = 'gif' if str(av).startswith('a_') else 'png'
    return f'https://cdn.discordapp.com/avatars/{uid}/{av}.{ext}?size={size}'


def _banner(uid, banner, size=512):
    if not banner:
        return 'none'
    ext = 'gif' if str(banner).startswith('a_') else 'png'
    return f'https://cdn.discordapp.com/banners/{uid}/{banner}.{ext}?size={size}'


def _flag_names(value: int):
    flags = {
        1 << 0: 'staff',
        1 << 1: 'partner',
        1 << 2: 'hypesquad_events',
        1 << 3: 'bug_hunter',
        1 << 6: 'bravery',
        1 << 7: 'brilliance',
        1 << 8: 'balance',
        1 << 9: 'early_supporter',
        1 << 10: 'team_user',
        1 << 14: 'bug_hunter_gold',
        1 << 16: 'verified_bot',
        1 << 17: 'early_verified_bot_dev',
        1 << 18: 'certified_mod',
        1 << 19: 'bot_http_interactions',
        1 << 22: 'active_developer',
    }
    out = [name for bit, name in flags.items() if value & bit]
    return out or ['none']


def _ms_to_hours(ms):
    try:
        return float(ms) / 3600000.0
    except Exception:
        return None


def _fmt_hours(h):
    if h is None:
        return '?'
    if h >= 1000:
        return '%.0fh' % h
    if h >= 10:
        return '%.1fh' % h
    return '%.2fh' % h


def _parse_badge_progress(badges):
    rows = []
    gametime_h = None
    stream_h = None
    variety_n = None
    for b in badges or []:
        if not isinstance(b, dict):
            continue
        bid = str(b.get('id') or b.get('description') or '').lower()
        desc = str(b.get('description') or '')
        meta = b.get('metadata') if isinstance(b.get('metadata'), dict) else {}
        # common keys seen on leveled activity badges
        hours = None
        for key in ('hours', 'play_time_hours', 'total_hours', 'value', 'count'):
            if key in meta and meta[key] is not None:
                try:
                    hours = float(meta[key])
                    break
                except Exception:
                    pass
        if hours is None:
            for key in ('duration_ms', 'play_time_ms', 'total_ms', 'milliseconds'):
                if key in meta and meta[key] is not None:
                    hours = _ms_to_hours(meta[key])
                    if hours is not None:
                        break
        # id heuristics
        is_game = any(x in bid for x in ('game_time', 'gametime', 'play_time', 'played'))
        is_stream = any(x in bid for x in ('stream', 'streaming', 'broadcast'))
        is_variety = any(x in bid for x in ('variety', 'game_variety', 'diverse'))
        is_quest = 'quest' in bid
        label = bid or desc or 'badge'
        if is_game:
            gametime_h = hours if hours is not None else gametime_h
            extra = (' %s' % _fmt_hours(hours)) if hours is not None else ''
            rows.append('game_time%s' % extra)
        elif is_stream:
            stream_h = hours if hours is not None else stream_h
            extra = (' %s' % _fmt_hours(hours)) if hours is not None else ''
            rows.append('streaming%s' % extra)
        elif is_variety:
            variety_n = hours if hours is not None else variety_n
            extra = (' %s' % (int(hours) if hours is not None else '?')) if hours is not None else ''
            rows.append('variety%s' % extra)
        elif is_quest:
            rows.append('quest:%s' % (desc[:40] or bid))
        else:
            if desc:
                rows.append(desc[:48])
            elif bid:
                rows.append(bid[:48])
    return rows, gametime_h, stream_h, variety_n


class InformationCog(commands.Cog, name='information'):

    def __init__(self, bot):
        self.bot = bot

    def _headers(self):
        try:
            from utils.gateway import default_headers, client_properties
            return default_headers(S._get_token(), client_properties(platform='desktop'))
        except Exception:
            return {
                'Authorization': S._get_token(),
                'User-Agent': getattr(S, 'USER_AGENT', 'Mozilla/5.0'),
                'X-Super-Properties': getattr(S, 'X_SUPER_PROPERTIES', '') or '',
                'Origin': 'https://discord.com',
                'Referer': 'https://discord.com/channels/@me',
            }

    async def _profile_api(self, uid, guild_id=None):
        h = self._headers()
        params = {
            'with_mutual_guilds': 'true',
            'with_mutual_friends': 'true',
            'with_mutual_friends_count': 'true',
        }
        if guild_id:
            params['guild_id'] = str(guild_id)
        urls = [
            f'https://discord.com/api/v9/users/{uid}/profile',
            f'https://discord.com/api/v9/users/{uid}',
        ]
        async with aiohttp.ClientSession() as s:
            for url in urls:
                for attempt in range(3):
                    try:
                        async with s.get(url, headers=h, params=params if 'profile' in url else None) as r:
                            if r.status == 200:
                                return await r.json(content_type=None), r.status, url
                            if r.status == 429:
                                try:
                                    data = await r.json(content_type=None)
                                    wait = float(data.get('retry_after', 1.5 + attempt))
                                except Exception:
                                    wait = 1.5 + attempt
                                import asyncio
                                await asyncio.sleep(min(wait, 10))
                                continue
                            if 'profile' not in url:
                                body = await r.text()
                                return {'raw_error': body[:120], 'status': r.status}, r.status, url
                            break
                    except Exception:
                        continue
        return None, 0, ''

    def _devices_from_member(self, m):
        devices = []
        if m is None:
            return devices
        for attr, label in (
            ('desktop_status', 'desktop'),
            ('mobile_status', 'mobile'),
            ('web_status', 'web'),
        ):
            st = getattr(m, attr, None)
            if st is not None:
                val = getattr(st, 'name', None) or str(st)
                if val and val != 'offline':
                    devices.append('%s:%s' % (label, val))
        cs = getattr(m, 'client_status', None)
        if isinstance(cs, dict):
            for k, v in cs.items():
                if v and str(v) != 'offline':
                    devices.append('%s:%s' % (k, v))
        return devices

    @commands.command(name='userinfo', aliases=['ui', 'whois'], brief='Full user profile + badge hours')
    async def userinfo(self, ctx, user: discord.User = None, user_id: str = None):
        uid = None
        uobj = user
        if user is not None:
            uid = user.id
        elif user_id:
            try:
                uid = int(user_id.strip())
            except Exception:
                return await S.safe_edit(ctx.message, S.ui_err('usage: userinfo [@user|id]'))
        else:
            uobj = ctx.author
            uid = ctx.author.id

        if uobj is None:
            uobj = self.bot.get_user(uid) or ctx.author

        gid = ctx.guild.id if ctx.guild else None
        data, status, used = await self._profile_api(uid, gid)

        rows = []
        if data and status == 200:
            u = data.get('user') if isinstance(data.get('user'), dict) else data
            if not isinstance(u, dict):
                u = {}
            prof = data.get('user_profile') or data.get('profile') or {}
            if not isinstance(prof, dict):
                prof = {}
            badges_raw = data.get('badges') or []
            badge_labels, gt_h, st_h, var_n = _parse_badge_progress(badges_raw)
            connected = []
            for acc in data.get('connected_accounts') or []:
                if isinstance(acc, dict):
                    connected.append('%s:%s' % (acc.get('type', '?'), acc.get('name', '?')))
            mutual = data.get('mutual_guilds') or []
            mutual_friends = data.get('mutual_friends') or []
            mf_count = data.get('mutual_friends_count')
            if mf_count is None:
                mf_count = len(mutual_friends) if isinstance(mutual_friends, list) else 0

            rows.extend([
                f'  {S.DIM}username{S.RESET}    {u.get("username") or getattr(uobj, "name", "?")}',
                f'  {S.DIM}global{S.RESET}      {u.get("global_name") or "-"}',
                f'  {S.DIM}id{S.RESET}          {uid}',
                f'  {S.DIM}created{S.RESET}     {_snowflake_ts(uid)}',
                f'  {S.DIM}bot{S.RESET}         {("yes" if u.get("bot") or getattr(uobj, "bot", False) else "no")}',
            ])
            flags_val = u.get('public_flags')
            if flags_val is None and hasattr(uobj, 'public_flags'):
                flags_val = getattr(uobj.public_flags, 'value', 0)
            rows.append(f'  {S.DIM}flags{S.RESET}       {", ".join(_flag_names(int(flags_val or 0)))}')
            bio = (prof.get('bio') or u.get('bio') or '')[:120] or '-'
            rows.append(f'  {S.DIM}bio{S.RESET}         {bio}')
            rows.append(f'  {S.DIM}pronouns{S.RESET}    {prof.get("pronouns") or "-"}')
            nitro = data.get('premium_since') or data.get('premium_type') or u.get('premium_type')
            rows.append(f'  {S.DIM}nitro{S.RESET}       {("yes · type " + str(data.get("premium_type") or u.get("premium_type") or "?") if nitro else "no")}')
            rows.append(f'  {S.DIM}badges{S.RESET}      {(", ".join(badge_labels) if badge_labels else "none")}')
            if gt_h is not None:
                rows.append(f'  {S.DIM}gametime{S.RESET}    {_fmt_hours(gt_h)}')
            if st_h is not None:
                rows.append(f'  {S.DIM}streamtime{S.RESET}  {_fmt_hours(st_h)}')
            if var_n is not None:
                rows.append(f'  {S.DIM}variety{S.RESET}     {int(var_n)} games')
            # legacy/legacy legacy fields some clients still send
            for key, label in (
                ('legacy_username', 'legacy'),
                ('game_played_hours', 'gametime'),
                ('stream_hours', 'streamtime'),
            ):
                if key in data and data[key] is not None and label not in str(rows):
                    rows.append(f'  {S.DIM}{label}{S.RESET}     {data[key]}')
            for key in ('legacy_username',):
                if key in u and u[key]:
                    rows.append(f'  {S.DIM}legacy{S.RESET}      {u[key]}')
            rows.append(f'  {S.DIM}mutual_srv{S.RESET}  {len(mutual) if isinstance(mutual, list) else 0}')
            rows.append(f'  {S.DIM}mutual_fr{S.RESET}   {mf_count}')
            if connected:
                rows.append(f'  {S.DIM}connections{S.RESET} {", ".join(connected[:8])}')
            av = u.get('avatar') or getattr(getattr(uobj, 'avatar', None), 'key', None)
            rows.append(f'  {S.DIM}avatar{S.RESET}      {_av(uid, av) if av else (str(getattr(uobj, "display_avatar", "") or "none"))}')
            ban = u.get('banner') or prof.get('banner')
            rows.append(f'  {S.DIM}banner{S.RESET}      {_banner(uid, ban) if ban else "none"}')
            accent = u.get('accent_color') or prof.get('accent_color')
            if accent is not None:
                rows.append(f'  {S.DIM}accent{S.RESET}      #{int(accent):06X}')
            pg = u.get('primary_guild') or data.get('primary_guild')
            if isinstance(pg, dict) and pg.get('tag'):
                rows.append(f'  {S.DIM}server_tag{S.RESET}  [{pg.get("tag")}] guild={pg.get("identity_guild_id")}')
        else:
            rows.extend([
                f'  {S.DIM}username{S.RESET}    {getattr(uobj, "name", "?")}',
                f'  {S.DIM}id{S.RESET}          {uid}',
                f'  {S.DIM}created{S.RESET}     {_snowflake_ts(uid)}',
                f'  {S.DIM}note{S.RESET}        profile api {status or "fail"} — partial from cache',
            ])
            if hasattr(uobj, 'public_flags'):
                rows.append(f'  {S.DIM}flags{S.RESET}       {", ".join(_flag_names(getattr(uobj.public_flags, "value", 0)))}')

        m = None
        if ctx.guild:
            m = ctx.guild.get_member(uid)
            if m is None:
                try:
                    m = await ctx.guild.fetch_member(uid)
                except Exception:
                    m = None
            if m:
                if m.nick:
                    rows.append(f'  {S.DIM}nick{S.RESET}        {m.nick}')
                if m.joined_at:
                    rows.append(f'  {S.DIM}joined{S.RESET}      {m.joined_at.strftime("%Y-%m-%d %H:%M")}')
                if m.premium_since:
                    rows.append(f'  {S.DIM}boosting{S.RESET}    {m.premium_since.strftime("%Y-%m-%d")}')
                roles = [r.name for r in getattr(m, 'roles', []) if r.name != '@everyone']
                if roles:
                    rows.append(f'  {S.DIM}roles{S.RESET}       {", ".join(roles[:12])}')
                devices = self._devices_from_member(m)
                if devices:
                    rows.append(f'  {S.DIM}devices{S.RESET}     {", ".join(devices)}')
                else:
                    st = getattr(m, 'status', None)
                    rows.append(f'  {S.DIM}status{S.RESET}      {getattr(st, "name", st) or "unknown"}')
                acts = getattr(m, 'activities', None) or []
                if acts:
                    labels = []
                    for a in list(acts)[:4]:
                        nm = getattr(a, 'name', None) or str(a)
                        tp = getattr(a, 'type', None)
                        labels.append('%s:%s' % (getattr(tp, 'name', tp), nm) if tp is not None else nm)
                    rows.append(f'  {S.DIM}activity{S.RESET}    {"; ".join(labels)[:120]}')

        if uid == getattr(getattr(self.bot, 'user', None), 'id', None):
            try:
                h = self._headers()
                async with aiohttp.ClientSession() as s:
                    async with s.get('https://discord.com/api/v9/users/@me/sessions', headers=h) as r:
                        if r.status == 200:
                            sessions = await r.json(content_type=None)
                            if isinstance(sessions, list):
                                devs = []
                                for sess in sessions[:8]:
                                    if not isinstance(sess, dict):
                                        continue
                                    client_info = sess.get('client_info') or {}
                                    devs.append(
                                        '%s/%s/%s'
                                        % (
                                            client_info.get('os', '?'),
                                            client_info.get('platform', '?'),
                                            client_info.get('client', '?'),
                                        )
                                    )
                                if devs:
                                    rows.append(f'  {S.DIM}sessions{S.RESET}    {", ".join(devs)}')
            except Exception:
                pass

        await S.safe_edit(ctx.message, S.ui_box('user info', rows))

    @commands.command(name='avatar', aliases=['av', 'pfp'], brief='Show user avatar')
    async def avatar(self, ctx, user: discord.User = None):
        u = user or ctx.author
        url = str(u.display_avatar.url) if u.display_avatar else 'no avatar'
        await S.safe_edit(ctx.message, url)

    @commands.command(name='serverinfo', aliases=['si'], brief='Server information')
    @commands.guild_only()
    async def serverinfo(self, ctx):
        g = ctx.guild
        rows = [
            f'  {S.DIM}name{S.RESET}     {g.name}',
            f'  {S.DIM}id{S.RESET}       {g.id}',
            f'  {S.DIM}owner{S.RESET}    {g.owner}',
            f'  {S.DIM}members{S.RESET}  {g.member_count}',
            f'  {S.DIM}channels{S.RESET} {len(g.channels)}',
            f'  {S.DIM}roles{S.RESET}    {len(g.roles)}',
            f'  {S.DIM}created{S.RESET}  {_snowflake_ts(g.id)}',
            f'  {S.DIM}boost{S.RESET}    {g.premium_subscription_count} boosts (tier {g.premium_tier})',
        ]
        await S.safe_edit(ctx.message, S.ui_box('server info', rows))

    @commands.command(name='checkname', brief='Check username availability')
    async def checkname(self, ctx, username: str = ''):
        if not username:
            return await S.safe_edit(ctx.message, S.ui_err('usage: checkname <username>'))
        h = self._headers()
        async with aiohttp.ClientSession() as s:
            async with s.post(
                'https://discord.com/api/v9/users/@me/pomelo-attempt',
                headers=h,
                json={'username': username},
            ) as r:
                if r.status == 200:
                    d = await r.json()
                    taken = d.get('taken', True)
                    msg = S.ui_ok(f'`{username}` is available') if not taken else S.ui_err(f'`{username}` is taken')
                else:
                    msg = S.ui_err(f'check failed ({r.status})')
        await S.safe_edit(ctx.message, msg)


async def setup(bot):
    if 'information' in bot.cogs:
        await bot.remove_cog('information')
    await bot.add_cog(InformationCog(bot))
