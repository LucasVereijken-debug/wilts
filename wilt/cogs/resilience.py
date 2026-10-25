import asyncio
import time
import aiohttp
import discord
from discord.ext import commands
from . import state as S


class ResilienceCog(commands.Cog, name='resilience'):

    def __init__(self, bot):
        self.bot = bot
        self._hb_task = None
        self._session_task = None

    async def cog_load(self):
        if not hasattr(S, '_auto_reconnect'):
            S._auto_reconnect = True
        if not hasattr(S, '_reconnect_count'):
            S._reconnect_count = 0
        if not hasattr(S, '_rate_limit_events'):
            S._rate_limit_events = []
        if not hasattr(S, '_last_resume'):
            S._last_resume = 0
        if not hasattr(S, '_session_keep'):
            S._session_keep = True
        try:
            self._hb_task = asyncio.create_task(self._presence_keepalive())
        except Exception:
            pass

    async def cog_unload(self):
        for t in (self._hb_task, self._session_task):
            if t and not t.done():
                t.cancel()

    async def _presence_keepalive(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await asyncio.sleep(240)
                if not getattr(S, '_session_keep', True):
                    continue
                if self.bot.is_closed():
                    break
                # soft presence poke keeps gateway warm without spam
                try:
                    ws = getattr(self.bot, 'ws', None)
                    if ws is not None and hasattr(ws, 'sequence'):
                        pass
                except Exception:
                    pass
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(30)

    @commands.Cog.listener()
    async def on_disconnect(self):
        S._reconnect_count = getattr(S, '_reconnect_count', 0) + 1
        print('[resilience] disconnected (#%s)' % S._reconnect_count)

    @commands.Cog.listener()
    async def on_resumed(self):
        S._last_resume = time.time()
        print('[resilience] resumed session')

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            from utils.gateway import apply_http_headers, client_properties
            apply_http_headers(self.bot, client_properties(platform='desktop'))
        except Exception:
            pass

    @commands.command(name='gwstatus', aliases=['sessionmon', 'sessstatus'], brief='Gateway/session status')
    async def gwstatus(self, ctx):
        ws = getattr(self.bot, 'ws', None)
        lat = round(self.bot.latency * 1000) if self.bot.latency else -1
        hist = getattr(S, '_latency_history', []) or []
        avg = ('%dms' % (sum(hist) / len(hist))) if hist else '-'
        rows = [
            f'  {S.DIM}latency{S.RESET}     {lat}ms',
            f'  {S.DIM}avg{S.RESET}         {avg}',
            f'  {S.DIM}ws{S.RESET}          {(type(ws).__name__ if ws else "None")}',
            f'  {S.DIM}guilds{S.RESET}      {len(self.bot.guilds)}',
            f'  {S.DIM}closed{S.RESET}      {self.bot.is_closed()}',
            f'  {S.DIM}reconnects{S.RESET}  {getattr(S, "_reconnect_count", 0)}',
            f'  {S.DIM}session_keep{S.RESET} {getattr(S, "_session_keep", True)}',
            f'  {S.DIM}last_resume{S.RESET} {(int(time.time() - S._last_resume) if getattr(S, "_last_resume", 0) else "-")}s ago',
        ]
        await S.safe_edit(ctx.message, S.ui_box('gateway', rows))

    @commands.command(name='sessionkeep', brief='Toggle session keep-alive')
    async def sessionkeep(self, ctx, toggle: str = ''):
        cur = getattr(S, '_session_keep', True)
        if toggle:
            S._session_keep = toggle.lower() not in ('off', '0', 'false', 'disable')
        else:
            S._session_keep = not cur
        await S.safe_edit(ctx.message, S.ui_ok('sessionkeep → %s' % ('on' if S._session_keep else 'off')))

    @commands.command(name='authsessions', aliases=['devicesessions', 'logins'], brief='List auth sessions')
    async def authsessions(self, ctx):
        h = {
            'Authorization': S._get_token(),
            'User-Agent': getattr(S, 'USER_AGENT', 'Mozilla/5.0'),
            'X-Super-Properties': getattr(S, 'X_SUPER_PROPERTIES', '') or '',
        }
        rows = []
        async with aiohttp.ClientSession() as s:
            for url in (
                'https://discord.com/api/v9/auth/sessions',
                'https://discord.com/api/v9/users/@me/sessions',
            ):
                try:
                    async with s.get(url, headers=h) as r:
                        if r.status != 200:
                            continue
                        data = await r.json(content_type=None)
                        sessions = data.get('user_sessions') if isinstance(data, dict) else data
                        if not isinstance(sessions, list):
                            sessions = data if isinstance(data, list) else []
                        for i, sess in enumerate(sessions[:12]):
                            if not isinstance(sess, dict):
                                continue
                            info = sess.get('client_info') or sess.get('approx_last_used_time') or {}
                            if isinstance(info, dict):
                                label = '%s/%s/%s' % (
                                    info.get('os') or info.get('platform') or '?',
                                    info.get('platform') or info.get('client') or '?',
                                    info.get('location') or info.get('ip') or '',
                                )
                            else:
                                label = str(sess.get('id_hash') or sess.get('session_id') or i)
                            rows.append(f'  {S.GREY}*{S.RESET} {label[:60]}')
                        if rows:
                            break
                except Exception:
                    continue
        if not rows:
            rows = [f'  {S.DIM}none visible via api{S.RESET}']
        await S.safe_edit(ctx.message, S.ui_box('auth sessions', rows))

    @commands.command(name='autoreconnect', brief='Toggle auto-reconnect flag')
    async def autoreconnect(self, ctx, toggle: str = ''):
        if not hasattr(S, '_auto_reconnect'):
            S._auto_reconnect = True
        if toggle:
            S._auto_reconnect = toggle.lower() not in ('off', 'disable', '0', 'false')
        else:
            S._auto_reconnect = not S._auto_reconnect
        await S.safe_edit(ctx.message, S.ui_ok('autoreconnect → %s' % ('on' if S._auto_reconnect else 'off')))


async def setup(bot):
    if 'resilience' in bot.cogs:
        await bot.remove_cog('resilience')
    await bot.add_cog(ResilienceCog(bot))
