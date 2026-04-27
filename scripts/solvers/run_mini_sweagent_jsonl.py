#!/usr/bin/env python3
"""Run mini-SWE-agent on a local JSON/JSONL dataset file.

This is a thin wrapper around mini-SWE-agent's SWEBench batch runner that
accepts a local JSONL file (one row per instance) as the data source.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import time
from pathlib import Path

from rich.live import Live

from minisweagent.config import get_config_from_spec
from minisweagent.run.benchmarks.swebench import DEFAULT_CONFIG_FILE, process_instance
from minisweagent.run.benchmarks.utils.batch_progress import RunBatchProgressManager
from minisweagent.utils.log import add_file_handler, logger
from minisweagent.utils.serialize import UNSET, recursive_merge


def _load_instances(dataset_path: Path) -> list[dict]:
    text = dataset_path.read_text().strip()
    if not text:
        return []

    if text[0] == "[":
        payload = json.loads(text)
        if not isinstance(payload, list):
            raise ValueError(f"Expected JSON list in {dataset_path}")
        return payload

    instances: list[dict] = []
    with dataset_path.open() as f:
        for idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                instances.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON at line {idx} in {dataset_path}: {e}") from e
    return instances


def _filter_instances(
    instances: list[dict],
    *,
    filter_spec: str,
    slice_spec: str,
    shuffle: bool,
) -> list[dict]:
    filtered = instances
    if shuffle:
        filtered = sorted(filtered.copy(), key=lambda x: x["instance_id"])
        # Match mini-SWE-agent benchmark shuffle behavior.
        import random

        random.seed(42)
        random.shuffle(filtered)

    if filter_spec:
        filtered = [instance for instance in filtered if re.match(filter_spec, instance["instance_id"])]

    if slice_spec:
        values = [int(x) if x else None for x in slice_spec.split(":")]
        filtered = filtered[slice(*values)]

    return filtered


def _process_futures(futures: dict[concurrent.futures.Future, str], progress_manager: RunBatchProgressManager) -> None:
    for future in concurrent.futures.as_completed(futures):
        try:
            future.result()
        except concurrent.futures.CancelledError:
            pass
        except Exception as e:
            instance_id = futures[future]
            logger.error(f"Error in future for instance {instance_id}: {e}", exc_info=True)
            progress_manager.on_uncaught_exception(instance_id, e)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-jsonl", type=Path, required=True)
    parser.add_argument("--filter", type=str, default="")
    parser.add_argument("--slice", dest="slice_spec", type=str, default="")
    parser.add_argument("--shuffle", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--redo-existing", action="store_true")
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--model-class", type=str, default=None)
    parser.add_argument("--environment-class", type=str, default=None)
    parser.add_argument("-c", "--config", action="append", default=[])
    args = parser.parse_args()

    if not args.dataset_jsonl.exists():
        raise FileNotFoundError(f"Dataset file not found: {args.dataset_jsonl}")

    output_path = args.output
    output_path.mkdir(parents=True, exist_ok=True)
    add_file_handler(output_path / "minisweagent.log")
    logger.info(f"Results will be saved to {output_path}")
    logger.info(f"Loading local dataset from {args.dataset_jsonl}")

    instances = _load_instances(args.dataset_jsonl)
    instances = _filter_instances(
        instances,
        filter_spec=args.filter,
        slice_spec=args.slice_spec,
        shuffle=args.shuffle,
    )

    if not args.redo_existing and (output_path / "preds.json").exists():
        existing_instances = list(json.loads((output_path / "preds.json").read_text()).keys())
        logger.info(f"Skipping {len(existing_instances)} existing instances")
        instances = [instance for instance in instances if instance["instance_id"] not in existing_instances]

    logger.info(f"Running on {len(instances)} instances")

    config_specs = args.config if args.config else [str(DEFAULT_CONFIG_FILE)]
    logger.info(f"Building agent config from specs: {config_specs}")
    configs = [get_config_from_spec(spec) for spec in config_specs]
    configs.append(
        {
            "environment": {"environment_class": args.environment_class or UNSET},
            "model": {"model_name": args.model or UNSET, "model_class": args.model_class or UNSET},
        }
    )
    config = recursive_merge(*configs)

    progress_manager = RunBatchProgressManager(len(instances), output_path / f"exit_statuses_{time.time()}.yaml")

    with Live(progress_manager.render_group, refresh_per_second=4):
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(process_instance, instance, output_path, config, progress_manager): instance[
                    "instance_id"
                ]
                for instance in instances
            }
            try:
                _process_futures(futures, progress_manager)
            except KeyboardInterrupt:
                logger.info("Cancelling all pending jobs. Press ^C again to exit immediately.")
                for future in futures:
                    if not future.running() and not future.done():
                        future.cancel()
                _process_futures(futures, progress_manager)


if __name__ == "__main__":
    main()
