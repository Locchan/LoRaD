class GenericPlayer:
    name_tech = ""
    name_readable = ""
    currently_playing = ""
    running = False
    looping = False

    def start(self):
        pass

    def stop(self):
        pass

    def list_sources(self, cached=False):
        return {}

    def current_source(self):
        return None

    def switch_source(self, source_id):
        pass

    def supports_next_track(self) -> bool:
        return False
