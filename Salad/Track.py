class Track:
  def __init__(self, data, requester=None):
    self.track = data.get('track') or data.get('encoded')
    info = data.get('info', {})
    self.identifier = info.get('identifier') or data.get('identifier', '')
    self.isSeekable = info.get('isSeekable', data.get('isSeekable', True))
    self.author = info.get('author') or data.get('author', '')
    self.length = info.get('length') or data.get('length', 0)
    self.isStream = info.get('isStream', data.get('isStream', False))
    self.title = info.get('title') or data.get('title', '')
    self.uri = info.get('uri') or data.get('uri', '')
    self.sourceName = info.get('sourceName') or data.get('sourceName', '')
    self.requester = requester

  def resolve(self, salad):
    return self.track

  def __str__(self):
    return f"{self.title} by {self.author}"

  def __repr__(self):
    return f"Track(title='{self.title}', author='{self.author}', length={self.length})"