__author__ = 'nhumrich'


class Container:

    def __init__(self, id=None, labels=None, image=None):
        self.id = id
        self.labels = labels or {}
        self.image = image


class Log:

    def __init__(self, timestamp=None, message=None):
        self.timestamp = timestamp
        self.message = message