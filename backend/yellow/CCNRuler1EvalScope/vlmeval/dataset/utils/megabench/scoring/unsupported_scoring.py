# Private iCAP Yellow implementation. Do not publish.
class UnsupportedScoring:
    """Unsupported scoring."""

    @staticmethod
    def match(response: str, correct_answer: str) -> int:
        """Default response for unimplemented metrics."""
        return -1
