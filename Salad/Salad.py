from .Node import Node
from .Player import Player
from .Track import Track
from typing import Optional, List, Dict, Any
import asyncio
import urllib.parse
import weakref

DEFAULT_CONFIGS = {
  'host': '127.0.0.1',
  'port': 50166,
  'auth': 'manialwaysforgettoupdatethisongithub',
  'ssl': False
}

EMPTY_TRACKS_RESPONSE = {
  'loadType': 'empty',
  'exception': None,
  'playlistInfo': None,
  'pluginInfo': {},
  'tracks': []
}

class Salad:
  def __init__(self, client, nodes, opts=None):
    if not client or not nodes:
      return
    self.nodes = []
    self.client = client
    self.players = {}
    self.initiated = False
    self.clientId = None
    self.started = False
    self.opts = opts or {}

  async def start(self, nodes, userId):
    if self.started:
      return self

    self.clientId = userId
    self.nodes = [Node(self, nc, self.opts) for nc in nodes]

    for node in self.nodes:
      node.updateClientId(userId)

    connTasks = [asyncio.create_task(n.connect()) for n in self.nodes]
    await asyncio.gather(*connTasks, return_exceptions=True)
    await asyncio.sleep(2.0)

    connNodes = [n for n in self.nodes if n.connected and n.sessionId]
    if connNodes:
      self.started = True

    return self

  async def createPlayer(self, node, opts=None):
    opts = opts or {}
    gid = opts.get('guildId')

    if gid in self.players:
      return self.players[gid]

    player = Player(self, node, opts)
    self.players[gid] = player
    node.players[gid] = player
    await player.connect(opts)
    return player

  async def createConnection(self, opts):
    if not self.started:
      return None
    gid = opts.get('guildId')
    if gid in self.players:
      return self.players[gid]

    for node in self.nodes:
      if node.connected and node.sessionId:
        return await self.createPlayer(node, opts)
    return None

  async def stop(self):
    for node in self.nodes:
      await node._cleanup()
      if hasattr(node, 'rest') and hasattr(node.rest, 'close'):
        await node.rest.close()
    self.started = False

  def _getReqNode(self, nodes=None):
    if nodes:
      for node in nodes:
        if node.connected:
          return node
    else:
      for node in self.nodes:
        if node.connected:
          return node
    return None

  def _formatQuery(self, query, source='ytsearch'):
    return f"{source}:{query}" if source in ('ytsearch', 'ytmsearch', 'scsearch') else query

  def _makeTrack(self, data, requester, node):
    return Track(data, requester) if isinstance(data, dict) else None

  async def resolve(self, query, source='ytsearch', requester=None, nodes=None):
    if not self.started:
      raise Exception('Salad not initialized')

    node = self._getReqNode(nodes)
    if not node:
      raise Exception('No nodes available')

    formatted = self._formatQuery(query, source)
    endpoint = f"/v4/loadtracks?identifier={urllib.parse.quote(formatted)}"

    try:
      resp = await node.rest.makeRequest('GET', endpoint)
      if not resp or resp.get('loadType') in ('empty', 'NO_MATCHES'):
        return EMPTY_TRACKS_RESPONSE
      return self._constructResp(resp, requester, node)
    except Exception as e:
      if hasattr(e, 'name') and e.name == 'AbortError':
        raise Exception('Request timeout')
      raise Exception(f"Resolve failed: {str(e)}")

  def _constructResp(self, resp, requester, node):
    loadType = resp.get('loadType', 'empty')
    data = resp.get('data')
    rootPlugin = resp.get('pluginInfo', {})

    base = {
      'loadType': loadType,
      'exception': None,
      'playlistInfo': None,
      'pluginInfo': rootPlugin or {},
      'tracks': []
    }

    if loadType in ('error', 'LOAD_FAILED'):
      base['exception'] = data or resp.get('exception')
      return base

    if loadType == 'track' and data:
      base['pluginInfo'] = data.get('info', {}).get('pluginInfo', data.get('pluginInfo', base['pluginInfo']))
      track = self._makeTrack(data, requester, node)
      if track and track.track:
        base['tracks'].append(track)
    elif loadType == 'playlist' and data:
      info = data.get('info')
      if info:
        thumb = (data.get('pluginInfo', {}).get('artworkUrl') or
                (data.get('tracks', [{}])[0].get('info', {}).get('artworkUrl') if data.get('tracks') else None))
        base['playlistInfo'] = {
          'name': info.get('name') or info.get('title'),
          'thumbnail': thumb,
          **info
        }
      base['pluginInfo'] = data.get('pluginInfo', base['pluginInfo'])
      if 'tracks' in data and isinstance(data['tracks'], list):
        for td in data['tracks']:
          track = self._makeTrack(td, requester, node)
          if track and track.track:
            base['tracks'].append(track)
    elif loadType == 'search' and data and isinstance(data, list):
      for td in data:
        track = self._makeTrack(td, requester, node)
        if track and track.track:
          base['tracks'].append(track)

    return base