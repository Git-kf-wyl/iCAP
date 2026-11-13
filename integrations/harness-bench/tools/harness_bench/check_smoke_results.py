"""Check actual selected task statuses, independently of runner's exit code."""
import argparse
import json
from pathlib import Path


def evaluate(path):
    try:
        data = json.loads(Path(path).read_text())
        tasks = [item for item in data['tasks'] if item.get('status') != 'not_selected']
    except (OSError, ValueError, KeyError, TypeError):
        print('INFRASTRUCTURE ERROR: missing or invalid summary')
        return 2
    if not tasks:
        print('INFRASTRUCTURE ERROR: no selected task results')
        return 2
    infra = False
    failed = False
    for item in tasks:
        status = item.get('status')
        passed = status == 'completed' and item.get('task_success') is True
        print(f"{item['task_id']}: status={status}, task_success={item.get('task_success')}, score={item.get('outcome_score')}")
        infra |= status in {'infrastructure_error', 'queued', 'running'}
        failed |= not passed
    return 2 if infra else 1 if failed else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('summary', type=Path)
    args = parser.parse_args()
    raise SystemExit(evaluate(args.summary))
