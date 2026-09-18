"""Offline scalar-kernel example: python -m grepbit --db ... --request ... --output ..."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .contracts import FactRequest, KernelError, MAX_REQUEST_BYTES
from .kernel import execute_facts


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise KernelError("invalid_request", "Duplicate JSON fields are not allowed.")
        result[key] = value
    return result


def _request(path: Path) -> FactRequest:
    with path.open("rb") as source:
        raw = source.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        raise KernelError("invalid_request", "Request exceeds the 16384-byte input limit.")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_object)
    except (ValueError, UnicodeError) as exc:
        raise KernelError("invalid_request", "Request is not valid UTF-8 JSON.") from exc
    return FactRequest.from_mapping(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Exclusive-create Fact Pack or failure evidence")
    args = parser.parse_args()
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as output:
            output.write('{"status":"incomplete"}\n')
            output.flush()
            try:
                result = execute_facts(args.db, _request(args.request)).to_dict()
                exit_code = 0
            except KernelError as exc:
                result = {"status": "failed", "error": {"code": exc.code, "message": str(exc)}}
                print(json.dumps(result), file=sys.stderr)
                exit_code = 1
            except OSError:
                result = {"status": "failed", "error": {
                    "code": "file_error", "message": "Could not read the local request file.",
                }}
                print(json.dumps(result), file=sys.stderr)
                exit_code = 1
            output.seek(0)
            output.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            output.truncate()
        return exit_code
    except OSError:
        print('{"status":"failed","error":{"code":"file_error",'
              '"message":"Could not exclusively create or finish the output file."}}', file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
