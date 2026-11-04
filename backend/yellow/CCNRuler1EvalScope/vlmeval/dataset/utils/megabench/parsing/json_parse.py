# Private iCAP Yellow implementation. Do not publish.
from .common.parsers import parse_json
from .common.utils import evaluate_as_string

class JsonParse:
    """Load the response as a JSON object."""

    @staticmethod
    def parse(response: str):
        """Parse the JSON object, including nested JSON strings."""
        parsed_res = parse_json(response)
        if isinstance(parsed_res, dict):
            for key, val in parsed_res.items():
                parsed_res[key] = evaluate_as_string(val)
        return parsed_res
