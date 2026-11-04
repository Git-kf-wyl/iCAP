# Private iCAP Yellow implementation. Do not publish.
class DummyParse:

    @staticmethod
    def parse(response: str, *args, **kwargs) -> dict:
        """return the raw string without doing anything"""
        return response.strip()
