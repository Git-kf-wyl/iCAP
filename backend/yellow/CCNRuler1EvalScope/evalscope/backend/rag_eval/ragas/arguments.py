# Private iCAP Yellow implementation. Do not publish.
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

@dataclass
class TestsetGenerationArguments:
    docs: List[str] = field(default_factory=list)
    test_size: int = 10
    output_file: str = 'outputs/testset.json'
    knowledge_graph: str = 'outputs/knowledge_graph.json'
    '\n    For local LLM support, you can use the following fields:\n        model_name_or_path: str\n        model_revision: str = "master"\n        generation_config: Optional[Dict]\n\n    For API LLM support, you can use the following fields:\n        model_name="gpt-4o-mini"\n        api_base: str = "",\n        api_key: Optional[str] = None\n    '
    generator_llm: Dict = field(default_factory=dict)
    embeddings: Dict = field(default_factory=dict)
    language: str = 'english'

@dataclass
class EvaluationArguments:
    testset_file: str
    critic_llm: Dict = field(default_factory=dict)
    embeddings: Dict = field(default_factory=dict)
    metrics: List[str] = field(default_factory=lambda: ['answer_relevancy', 'faithfulness'])
    language: str = 'english'
