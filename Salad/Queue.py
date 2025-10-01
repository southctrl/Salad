from collections import deque
from random import shuffle as randomShuffle

class Queue:
  def __init__(self, player):
    self.player = player
    self._q = deque()
    self.loop = 'none'

  def __len__(self):
    return len(self._q)

  def __getitem__(self, idx):
    return self._q[idx]

  def __iter__(self):
    return iter(self._q)

  @property
  def queue(self):
    return list(self._q)

  def add(self, item):
    if self.player.destroyed:
      return False
    self._q.append(item)
    return True

  def pop(self, idx=0):
    if idx < 0 or idx >= len(self._q):
      return None
    if idx == 0:
      return self._q.popleft()
    temp = list(self._q)
    item = temp.pop(idx)
    self._q = deque(temp)
    return item

  def remove(self, idx):
    return self.pop(idx)

  def clear(self):
    self._q.clear()

  def shuffle(self):
    temp = list(self._q)
    randomShuffle(temp)
    self._q = deque(temp)

  def getNext(self):
    if not self._q:
      if self.loop == 'track' and self.player.currentTrackObj:
        return self.player.currentTrackObj
      return None

    if self.loop == 'track' and self.player.currentTrackObj:
      return self.player.currentTrackObj

    track = self._q.popleft()

    if self.loop == 'queue':
      self._q.append(track)

    return track

  def insert(self, item, idx=0):
    if idx <= 0:
      self._q.appendleft(item)
    elif idx >= len(self._q):
      self._q.append(item)
    else:
      temp = list(self._q)
      temp.insert(idx, item)
      self._q = deque(temp)
    return True

  def move(self, fromIdx, toIdx):
    if fromIdx < 0 or fromIdx >= len(self._q):
      return False
    if toIdx < 0 or toIdx >= len(self._q):
      return False
    temp = list(self._q)
    item = temp.pop(fromIdx)
    temp.insert(toIdx, item)
    self._q = deque(temp)
    return True
  def length(self):
    return len(self._q)