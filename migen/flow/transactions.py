class Token:
    def __init__(self, endpoint, value=None, idle_wait=False):
        self.endpoint = endpoint
        self.value = value
        self.idle_wait = idle_wait
