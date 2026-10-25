import aiohttp
import discord
from discord.ext import commands
from . import state as S

WIDGET_TYPES = {
    'favorite': 'favorite_games',
    'fav': 'favorite_games',
    'current': 'current_games',
    'rotation': 'current_games',
    'played': 'played_games',
    'like': 'played_games',
    'want': 'want_to_play_games',
    'wishlist': 'want_to_play_games',
    'app': 'application',
    'application': 'application',
}

TAGS = {
    'noob', 'learning_the_ropes', 'casual', 'getting_good', 'intermediate',
    'expert', 'better_than_you', 'obsessed', 'love_it', 'kind_of_love_it',
    'kind_of_hate_it', 'rage_quitting', 'like_it', 'frustrated', 'too_easy',
    'looking_for_group', 'open_to_play', 'looking_for_tips', 'open_to_teach',
    'looking_to_discuss',
}

KNOWN_GAMES = {
    'roblox': '963434583335854120',
    'minecraft': '356321645352747010',
    'valorant': '516027391621562368',
    'league': '401518684763586560',
    'lol': '401518684763586560',
    'fortnite': '432980957394370572',
    'gta': '356875221078446080',
    'gtav': '356875221078446080',
    'cs2': '1086371000000000000',
    'csgo': '356043266677602006',
    'apex': '465338396480143360',
    'overwatch': '356875332539113472',
    'ow2': '356875332539113472',
    'rocketleague': '356878237789552640',
    'r6': '356875221078446080',
    'cod': '356875221078446080',
    'osu': '367827983903490050',
    'spotify': 'spotify:1',
}


class WidgetCog(commands.Cog, name='widget'):

    def __init__(self, bot):
        self.bot = bot

    def _headers(self):
        try:
            from utils.gateway import default_headers, client_properties
            h = default_headers(S._get_token(), client_properties(platform='desktop'))
        except Exception:
            h = {
                'Authorization': S._get_token(),
                'User-Agent': getattr(S, 'USER_AGENT', 'Mozilla/5.0'),
                'X-Super-Properties': getattr(S, 'X_SUPER_PROPERTIES', '') or '',
            }
        h = dict(h)
        h['Content-Type'] = 'application/json'
        h['Origin'] = 'https://discord.com'
        h['Referer'] = 'https://discord.com/channels/@me'
        return h

    def _resolve_game_id(self, raw: str) -> str:
        key = (raw or '').strip().lower()
        if key in KNOWN_GAMES:
            return KNOWN_GAMES[key]
        # strip non-digits for pure snowflakes
        digits = ''.join(c for c in key if c.isdigit())
        if digits:
            return digits
        return key

    async def _get_widgets(self, session):
        h = self._headers()
        uid = getattr(getattr(self.bot, 'user', None), 'id', None)
        if not uid:
            return []
        async with session.get(
            'https://discord.com/api/v9/users/%s/profile' % uid,
            headers=h,
            params={'with_mutual_guilds': 'false'},
        ) as r:
            if r.status != 200:
                return []
            data = await r.json(content_type=None)
            return data.get('widgets') or []

    async def _put_widgets(self, session, widgets):
        h = self._headers()
        clean = []
        for item in widgets or []:
            if not isinstance(item, dict):
                continue
            entry = {}
            if item.get('id'):
                entry['id'] = str(item['id'])
            data = item.get('data') if isinstance(item.get('data'), dict) else item
            if not isinstance(data, dict):
                continue
            entry['data'] = data
            clean.append(entry)
        async with session.put(
            'https://discord.com/api/v9/users/@me/widgets',
            headers=h,
            json={'widgets': clean},
        ) as r:
            text = await r.text()
            try:
                body = await r.json(content_type=None) if text else []
            except Exception:
                body = text[:300]
            return r.status, body

    async def _suggested(self, session):
        h = self._headers()
        try:
            async with session.get(
                'https://discord.com/api/v9/users/@me/widgets/suggested-games',
                headers=h,
            ) as r:
                if r.status == 200:
                    return await r.json(content_type=None)
        except Exception:
            pass
        return {}

    @commands.command(name='widgetlist', aliases=['widgets', 'wlist'], brief='List profile board widgets')
    async def widgetlist(self, ctx):
        async with aiohttp.ClientSession() as s:
            widgets = await self._get_widgets(s)
        if not widgets:
            return await S.safe_edit(ctx.message, S.ui_info('no widgets on profile'))
        rows = []
        for i, w in enumerate(widgets):
            if not isinstance(w, dict):
                continue
            data = w.get('data') or {}
            wtype = data.get('type', '?')
            games = data.get('games') or []
            app = data.get('application_id')
            if app:
                rows.append(f'  {S.DIM}{i}{S.RESET}  {wtype}  app={app}')
            else:
                gids = ', '.join(str(g.get('game_id')) for g in games if isinstance(g, dict))[:70]
                rows.append(f'  {S.DIM}{i}{S.RESET}  {wtype}  games=[{gids}]')
        await S.safe_edit(ctx.message, S.ui_box('widgets', rows or [f'  {S.DIM}empty{S.RESET}']))

    @commands.command(name='widgetadd', aliases=['wadd'], brief='Add game widget')
    async def widgetadd(self, ctx, wtype: str = '', game_id: str = '', tag: str = '', *, comment: str = ''):
        key = (wtype or '').lower().strip()
        if key not in WIDGET_TYPES or not game_id:
            return await S.safe_edit(
                ctx.message,
                S.ui_err('usage: widgetadd <favorite|current|played|want> <game_id|name> [tag] [comment]\nnames: roblox minecraft valorant league fortnite'),
            )
        dtype = WIDGET_TYPES[key]
        if dtype == 'application':
            return await S.safe_edit(ctx.message, S.ui_err('use .widgetapp <application_id>'))
        gid = self._resolve_game_id(game_id)
        if not gid.isdigit():
            return await S.safe_edit(ctx.message, S.ui_err('unknown game — use numeric app id or name: roblox/minecraft/valorant/league/fortnite'))
        tags = []
        if tag:
            tnorm = tag.lower().replace(' ', '_').replace('-', '_')
            if tnorm in TAGS:
                tags.append(tnorm)
            elif tag:
                comment = (tag + ' ' + comment).strip()
        game = {'game_id': gid}
        if tags:
            game['tags'] = tags
        if comment:
            game['comment'] = comment[:128]
        async with aiohttp.ClientSession() as s:
            widgets = await self._get_widgets(s)
            new_widgets = []
            replaced = False
            limits = {'favorite_games': 1, 'current_games': 5, 'played_games': 20, 'want_to_play_games': 20}
            for w in widgets:
                data = (w or {}).get('data') or {}
                if data.get('type') == dtype:
                    games = list(data.get('games') or [])
                    games = [g for g in games if str((g or {}).get('game_id')) != gid]
                    games.insert(0, game)
                    games = games[: limits.get(dtype, 5)]
                    entry = {'data': {'type': dtype, 'games': games}}
                    if w.get('id'):
                        entry['id'] = w['id']
                    new_widgets.append(entry)
                    replaced = True
                else:
                    new_widgets.append(w if isinstance(w, dict) else {'data': w})
            if not replaced:
                new_widgets.insert(0, {'data': {'type': dtype, 'games': [game]}})
            status, body = await self._put_widgets(s, new_widgets)
        if status in (200, 201, 204):
            await S.safe_edit(ctx.message, S.ui_ok(f'widget {dtype} · game {gid}'))
        else:
            err = body
            if isinstance(body, dict):
                err = body.get('message') or body.get('code') or str(body)[:160]
            tip = ''
            if status == 400:
                tip = ' — id not a Discord-detectable game; try .widgetgames or known names (roblox/minecraft/valorant)'
            await S.safe_edit(ctx.message, S.ui_err(f'widget put {status}: {err}{tip}'))

    @commands.command(name='widgetapp', aliases=['wapp'], brief='Add application widget by app id')
    async def widgetapp(self, ctx, app_id: str = ''):
        if not app_id:
            return await S.safe_edit(ctx.message, S.ui_err('usage: widgetapp <application_id>'))
        aid = self._resolve_game_id(app_id)
        if not str(aid).isdigit():
            return await S.safe_edit(ctx.message, S.ui_err('application_id must be numeric'))
        async with aiohttp.ClientSession() as s:
            widgets = await self._get_widgets(s)
            cleaned = []
            for w in widgets:
                data = (w or {}).get('data') or {}
                if data.get('type') == 'application' and str(data.get('application_id')) == str(aid):
                    continue
                cleaned.append(w)
            cleaned.insert(0, {'data': {'type': 'application', 'application_id': str(aid)}})
            status, body = await self._put_widgets(s, cleaned)
        if status in (200, 201, 204):
            await S.safe_edit(ctx.message, S.ui_ok(f'application widget {aid} set'))
        else:
            err = body if not isinstance(body, dict) else (body.get('message') or body)
            await S.safe_edit(ctx.message, S.ui_err(f'widget put {status}: {err}'))

    @commands.command(name='widgetclear', aliases=['wclear'], brief='Clear all profile widgets')
    async def widgetclear(self, ctx):
        async with aiohttp.ClientSession() as s:
            status, body = await self._put_widgets(s, [])
        if status in (200, 201, 204):
            await S.safe_edit(ctx.message, S.ui_ok('widgets cleared'))
        else:
            await S.safe_edit(ctx.message, S.ui_err(f'clear {status}: {body}'))

    @commands.command(name='widgetgames', aliases=['wgames', 'widgetids'], brief='Known + suggested game ids for widgets')
    async def widgetgames(self, ctx):
        rows = [f'  {S.DIM}{k}{S.RESET}  {v}' for k, v in sorted(KNOWN_GAMES.items()) if v.isdigit()]
        async with aiohttp.ClientSession() as s:
            sug = await self._suggested(s)
        sg = sug.get('suggested_games') or []
        if sg:
            rows.append('')
            rows.append(f'  {S.DIM}suggested by discord{S.RESET}')
            for gid in list(sg)[:12]:
                rows.append(f'  {gid}')
        await S.safe_edit(ctx.message, S.ui_box('widget games', rows))

    @commands.command(name='widgettags', aliases=['wtags'], brief='List valid widget skill tags')
    async def widgettags(self, ctx):
        rows = [f'  {S.DIM}*{S.RESET} {t}' for t in sorted(TAGS)]
        await S.safe_edit(ctx.message, S.ui_box('widget tags', rows))

    @commands.command(name='widgethelp', aliases=['whelp'], brief='Widget command help')
    async def widgethelp(self, ctx):
        rows = [
            f'  {S.DIM}list{S.RESET}     .widgetlist',
            f'  {S.DIM}add{S.RESET}      .widgetadd <favorite|current|played|want> <id|name> [tag] [comment]',
            f'  {S.DIM}app{S.RESET}      .widgetapp <application_id>',
            f'  {S.DIM}games{S.RESET}    .widgetgames',
            f'  {S.DIM}clear{S.RESET}    .widgetclear',
            f'  {S.DIM}tags{S.RESET}     .widgettags',
            f'  {S.DIM}names{S.RESET}    roblox · minecraft · valorant · league · fortnite',
            f'  {S.DIM}roblox{S.RESET}   963434583335854120',
            f'  {S.DIM}note{S.RESET}     board widgets = desktop/web only · id must be Discord game app',
        ]
        await S.safe_edit(ctx.message, S.ui_box('widget', rows))


async def setup(bot):
    if 'widget' in bot.cogs:
        await bot.remove_cog('widget')
    await bot.add_cog(WidgetCog(bot))
