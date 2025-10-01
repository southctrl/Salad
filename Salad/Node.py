import aiohttp
import asyncio
from .Rest import Rest

WS_PATH = 'v4/websocket'

class Node:
  def __init__(self, salad, connOpts, opts=None):
    self.host = connOpts.get('host', '127.0.0.1')
    self.port = connOpts.get('port', 8000)
    self.auth = connOpts.get('auth', 'youshallnotpass')
    self.ssl = connOpts.get('ssl', False)
    self.wsUrl = f"ws{'s' if self.ssl else ''}://{self.host}:{self.port}/{WS_PATH}"
    self.rest = Rest(salad, self)
    self.opts = opts or {}
    self.connected = False
    self.info = None
    self.players = {}
    self.clientName = 'Salad/v1.0.0'
    self.sessionId = None
    self.session = None
    self.ws = None
    self.stats = None
    self._listenTask = None
    self.headers = {
      'Authorization': self.auth,
      'User-Id': '',
      'Client-Name': self.clientName
    }

  async def connect(self):
    try:
      self.session = aiohttp.ClientSession()
      self.ws = await self.session.ws_connect(
        self.wsUrl,
        headers=self.headers,
        autoclose=False,
        heartbeat=30
      )
      self.connected = True
      self._listenTask = asyncio.create_task(self._listenWs())

      for _ in range(50):
        if self.sessionId:
          break
        await asyncio.sleep(0.1)

      resp = await self.rest.makeRequest('GET', 'v4/info')
      if resp:
        self.info = resp
    except Exception:
      self.connected = False
      await self._cleanup()

  async def _listenWs(self):
    try:
      async for msg in self.ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
          try:
            await self._handleWsMsg(msg.json())
          except Exception:
            pass
        elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE):
          break
    except Exception:
      pass
    finally:
      self.connected = False

  async def _handleWsMsg(self, data):
    op = data.get('op')
    if op == 'ready':
      self.sessionId = data.get('sessionId')
    elif op == 'stats':
      self.stats = data
    elif op == 'playerUpdate':
      gid = data.get('guildId')
      state = data.get('state', {})
      if gid and gid in self.players:
        p = self.players[gid]
        p.position = state.get('position', 0)
        p.timestamp = state.get('time', 0)
    elif op == 'event':
      await self._handleEvent(data)

  async def _handleEvent(self, data):
    gid = data.get('guildId')
    evType = data.get('type')
    if not gid:
      return
    if isinstance(gid, str):
      try:
        gid = int(gid)
      except ValueError:
        return
    if gid not in self.players:
      return

    player = self.players[gid]

    if evType == 'TrackEndEvent':
      reason = data.get('reason', 'UNKNOWN')

      if reason in ('FINISHED', 'LOAD_FAILED'):
        player.current = None
        player.currentTrackObj = None
        player.playing = False
        player.position = 0

        if player.queue._q and not player.destroyed:
          try:
            await player.play()
          except Exception:
            pass
      elif reason == 'REPLACED':
        pass
      else:
        player.current = None
        player.currentTrackObj = None
        player.playing = False
    elif evType == 'TrackStartEvent':
      player.playing = True
      player.paused = False
    elif evType in ('TrackStuckEvent', 'TrackExceptionEvent'):
      player.current = None
      player.currentTrackObj = None
      player.playing = False
      if player.queue._q and not player.destroyed:
        try:
          await player.play()
        except Exception:
          pass

  def updateClientId(self, cid):
    self.headers['User-Id'] = str(cid)
    if self.rest:
      self.rest.headers.update(self.headers)

  async def _updatePlayer(self, gid, /, *, data, replace=False):
    noReplace = not replace
    scheme = 'https' if self.ssl else 'http'
    uri = f"{scheme}://{self.host}:{self.port}/v4/sessions/{self.sessionId}/players/{gid}?noReplace={str(noReplace).lower()}"

    if not self.session:
      self.session = aiohttp.ClientSession()

    async with self.session.patch(uri, json=data, headers=self.headers) as resp:
      if resp.status in (200, 201):
        try:
          return await resp.json()
        except Exception:
          return None
      if resp.status == 204:
        return None
      raise Exception(f"Player update failed: {resp.status}")

  async def _cleanup(self):
    if self._listenTask and not self._listenTask.done():
      self._listenTask.cancel()
    if self.ws and not self.ws.closed:
      await self.ws.close()
    if self.session and not self.session.closed:
      await self.session.close()