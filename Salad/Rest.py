import aiohttp
import orjson

class Rest:
  def __init__(self, salad, nodes):
    self.node = nodes
    self.salad = salad
    self.auth = nodes.auth
    self.ssl = nodes.ssl
    self.baseUrl = f"http{'s' if self.ssl else ''}://{nodes.host}:{nodes.port}"
    self.apiVer = 'v4'
    self.session = None
    self.headers = {
      'Authorization': str(self.auth),
      'Accept-Encoding': 'gzip, deflate, br',
      'Accept': 'application/json, */*;q=0.5',
      'User-Agent': 'Salad/v1.0.0'
    }

  async def makeRequest(self, method, endpoint, body=None):
    if not self.session or self.session.closed:
      self.session = aiohttp.ClientSession()

    url = f"{self.baseUrl}{endpoint}"
    headers = self.headers.copy()

    try:
      if method.upper() == 'GET':
        async with self.session.get(url, headers=headers) as resp:
          return await resp.json() if resp.status == 200 else None
      else:
        payload = orjson.dumps(body) if body is not None else None
        async with self.session.request(method, url, data=payload, headers=headers) as resp:
          return await resp.json() if resp.status == 200 else None
    except Exception:
      return None

  async def close(self):
    if self.session and not self.session.closed:
      await self.session.close()