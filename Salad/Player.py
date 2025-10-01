from .Queue import Queue
import asyncio

class Player:
  def __init__(self, salad, nodes, opts=None):
    opts = opts or {}
    self.salad = salad
    self.nodes = nodes
    self.guildId = opts.get('guildId')
    self.voiceChannel = opts.get('voiceChannel')
    self.textChannel = opts.get('textChannel')
    self.mute = opts.get('mute', False)
    self.deaf = opts.get('deaf', True)
    self.playing = False
    self.destroyed = False
    self.current = None
    self.currentTrackObj = None
    self.position = 0
    self.timestamp = 0
    self.ping = 0
    self.connected = False
    self.volume = opts.get('volume', 100)
    self._voiceState = {'voice': {}}
    self._lastVoiceUpdate = {}
    self.paused = False
    self.queue = Queue(self)
    self._playLock = asyncio.Lock()

  async def connect(self, opts=None):
    if self.destroyed:
      return
    opts = opts or {}
    vc = opts.get('vc', self.voiceChannel)
    if not vc:
      return
    self.destroyed = False

  async def handleVoiceStateUpdate(self, data):
    if self.destroyed:
      return
    cid = data.get('channel_id')
    sid = data.get('session_id')
    if sid:
      self._voiceState['voice']['session_id'] = sid
    self.voiceChannel = cid if cid else None

  async def handleVoiceServerUpdate(self, data):
    self._voiceState['voice']['token'] = data['token']
    self._voiceState['voice']['endpoint'] = data['endpoint']
    await self._dispatchVoiceUpdate()

  async def _dispatchVoiceUpdate(self):
    data = self._voiceState['voice']
    sid = data.get('session_id')
    token = data.get('token')
    endpoint = data.get('endpoint')

    if not (sid and token and endpoint):
      return
    if (self._lastVoiceUpdate.get('session_id') == sid and
        self._lastVoiceUpdate.get('token') == token and
        self._lastVoiceUpdate.get('endpoint') == endpoint):
      return
    if not self.nodes.sessionId:
      return

    req = {
      'voice': {
        'sessionId': sid,
        'token': token,
        'endpoint': endpoint
      },
      'volume': self.volume
    }

    try:
      await self.nodes._updatePlayer(self.guildId, data=req)
      self.connected = True
      self._lastVoiceUpdate = {'session_id': sid, 'token': token, 'endpoint': endpoint}
    except Exception:
      self.connected = False

  async def play(self):
    async with self._playLock:
      if self.destroyed:
        return

      if len(self.queue) == 0:
        self.playing = False
        return

      vd = self._voiceState['voice']
      if not (vd.get('session_id') and vd.get('token') and vd.get('endpoint')):
        return
      if not self.connected:
        return

      item = self.queue.getNext()
      if not item:
        self.playing = False
        return

      try:
        self.currentTrackObj = item
        if hasattr(item, 'track') and item.track:
          self.current = item.track
        elif hasattr(item, 'resolve'):
          self.current = item.resolve(self.salad)
        else:
          return

        if not self.current:
          return

        playData = {
          'encodedTrack': self.current,
          'position': 0,
          'volume': self.volume,
          'paused': False
        }

        await self.nodes._updatePlayer(self.guildId, data=playData)

        self.position = 0
        self.playing = True
        self.paused = False

      except Exception as e:
        self.playing = False
        if item and self.queue.loop != 'track':
          self.queue.insert(item, 0)

  def addToQueue(self, item):
    return self.queue.add(item)

  async def skip(self):
    if self.destroyed:
      return

    try:
      await self.nodes._updatePlayer(self.guildId, data={'encodedTrack': None})
    except Exception:
      pass

    self.current = None
    self.currentTrackObj = None
    self.position = 0
    self.playing = False

    if len(self.queue) > 0:
      await self.play()

  async def stop(self):
    if self.destroyed:
      return

    try:
      await self.nodes._updatePlayer(self.guildId, data={'encodedTrack': None})
    except Exception:
      pass

    self.queue.clear()
    self.current = None
    self.currentTrackObj = None
    self.position = 0
    self.playing = False
    self.paused = False

  async def pause(self):
    if self.destroyed or not self.playing:
      return
    try:
      await self.nodes._updatePlayer(self.guildId, data={'paused': True})
      self.paused = True
    except Exception:
      pass

  async def resume(self):
    if self.destroyed or not self.paused:
      return
    try:
      await self.nodes._updatePlayer(self.guildId, data={'paused': False})
      self.paused = False
    except Exception:
      pass

  async def setVolume(self, vol):
    if self.destroyed:
      return
    vol = max(0, min(1000, vol))
    self.volume = vol
    try:
      await self.nodes._updatePlayer(self.guildId, data={'volume': vol})
    except Exception:
      pass

  async def destroy(self):
    if self.destroyed:
      return
    await self.stop()
    self.destroyed = True
    self.connected = False
    if hasattr(self.nodes, 'players') and self.guildId in self.nodes.players:
      del self.nodes.players[self.guildId]