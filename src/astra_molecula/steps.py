"""Stateless CLI step for Argo Workflows (ADR 0012 P3).

    python -m astra_molecula.steps generate --work-dir /work    # CPU only

## Why this exists: `generate` was running inside the API process

`api/routers/smiles.py:95` did `asyncio.create_task(task_processor.process_task(task))` —
SMILES generation ran in the uvicorn worker that serves every other request. Measured
runtime spans **0.1 s to ~50 minutes** and cannot be predicted from the request, so one
pathological input could pin the API's p99 for the better part of an hour. The returned
Task was never awaited or stored, so a pod restart lost the run and left the row stuck.

Now it is an Argo step: its own pod, its own CPU quota, and — critically — an
`activeDeadlineSeconds`, which it never had.

## It also fixes the "only the first request is computed" bug

`task_processor.py:193-247` accepted a `generateRequestList` of N, collected every
`varSmiles` into `all_var_smiles`… and then threw the list away
(`var_smiles_str = all_var_smiles[0]`), calling the runner exactly once. N-1 requests were
silently dropped. This step runs the generator once per request and concatenates. For the
overwhelmingly common N=1 case the behaviour and the output shape are identical, so the
front-end sees no change.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("generate-step")


def _requests_from(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalise both payload shapes the API has ever accepted."""
    if params.get("generateRequestList"):
        return list(params["generateRequestList"])

    # Legacy flat shape (task_processor.py:216-231).
    var = params.get("varSmiles") or params.get("fromVarSMILES") or []
    if isinstance(var, str):
        var = [var]
    if not var:
        return []
    return [
        {
            "constSmiles": params.get("constSmiles") or params.get("constantSMILES", ""),
            "varSmiles": v,
            "mainCls": params.get("mainCls", params.get("main_cls", "activity")),
            "minorCls": params.get("minorCls", params.get("minor_cls", "IC50")),
            "deltaValue": params.get("deltaValue", params.get("Delta_Value", "(-inf, -10.5]")),
            "num": params.get("num", params.get("num_samples", 3)),
        }
        for v in var
    ]


def stage_generate(work_dir: Path, params: Dict[str, Any]) -> None:
    from astra_molecula.utils.tools import run_generate_runner

    reqs = _requests_from(params)
    if not reqs:
        raise ValueError("no generate requests in input.json")

    molecules: List[Any] = []
    for i, req in enumerate(reqs, 1):
        const = req.get("constSmiles", "")
        var = req.get("varSmiles", "")
        if not const:
            raise ValueError(f"request {i}/{len(reqs)}: constSmiles is required")
        if not var:
            raise ValueError(f"request {i}/{len(reqs)}: varSmiles is required")

        logger.info("request %d/%d: const=%s var=%s", i, len(reqs), const, var)
        out = run_generate_runner(
            const_smiles=const,
            var_smiles=var,
            main_cls=req.get("mainCls", "activity"),
            minor_cls=req.get("minorCls", "IC50"),
            delta_value=req.get("deltaValue", "(-inf, -10.5]"),
            num_samples=int(req.get("num", 3)),
        )
        molecules.extend(out)
        logger.info("request %d/%d produced %d molecule(s)", i, len(reqs), len(out))

    out_dir = work_dir / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    # `publish` maps /work/output/output.json → {job_dir}/output.json (the job ROOT), which
    # is where GET /tasks/{id}/geneRes reads it from. Do not move it into an output/ dir.
    (out_dir / "output.json").write_text(
        json.dumps(molecules, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("generated %d molecule(s) from %d request(s)", len(molecules), len(reqs))


STAGES = {"generate": stage_generate}


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    p = argparse.ArgumentParser(prog="astra_molecula.steps")
    p.add_argument("stage", choices=sorted(STAGES))
    p.add_argument("--work-dir", default="/work")
    args = p.parse_args()

    work_dir = Path(args.work_dir)
    params = json.loads((work_dir / "params.json").read_text())
    logger.info("stage=%s work_dir=%s", args.stage, work_dir)

    try:
        STAGES[args.stage](work_dir, params)
    except Exception as e:
        print(f"FATAL [{args.stage}] {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
