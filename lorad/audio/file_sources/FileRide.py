class FileRide:
    def __init__(self):
        self.initialized = False

    def initialize(self):
        pass

    def get_current_track(self):
        pass

    def next_track(self):
        pass

    def switch_station(self, station_id):
        raise RuntimeError("This source has no stations.")

    def supports_next_track(self) -> bool:
        return False

    def prefetch_next(self):
        return None

    def promote_next(self):
        pass

    def notify_playing(self):
        pass

    def notify_played(self, played_seconds: float, skipped: bool = False):
        pass
