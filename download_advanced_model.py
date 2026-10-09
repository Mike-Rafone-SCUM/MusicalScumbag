"""Fetch only the pinned YourMT3+ inference source and one verified checkpoint."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import urllib.request
from pathlib import Path, PurePosixPath

REVISION = "5e66c1ea173a8186e0d20432b841d3180cc015b5"
MODEL = "amt/logs/2024/mc13_256_g4_all_v7_mt3f_sqr_rms_moe_wf4_n8k2_silu_rope_rp_b36_nops/checkpoints/last.ckpt"
MODEL_SHA256 = "ae38e415c79efd5592dcb9b658cdb99ddb11d4c4e1eaa364cab04a052473fc25"
BASE = f"https://huggingface.co/spaces/mimbres/YourMT3/resolve/{REVISION}/"


def selected_path(path: str) -> bool:
    relative = PurePosixPath(path)
    if relative.is_absolute() or ".." in relative.parts or "\\" in path:
        return False
    if path in {"model_helper.py", "README.md", MODEL}:
        return True
    return (
        path.startswith(("amt/src/model/", "amt/src/config/", "amt/src/utils/"))
        and path.endswith(".py")
        and not path.startswith(("amt/src/utils/preprocess/", "amt/src/utils/mirdata_dev/"))
    )


def git_digest(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def download(root: Path) -> None:
    url = f"https://huggingface.co/api/spaces/mimbres/YourMT3/tree/{REVISION}?recursive=true"
    with urllib.request.urlopen(url, timeout=60) as response:
        tree = json.load(response)
    entries = [entry for entry in tree if entry["type"] == "file" and selected_path(entry["path"])]
    if not any(entry["path"] == MODEL for entry in entries):
        raise RuntimeError("The pinned checkpoint is missing from the source manifest.")

    def fetch(entry):
        target = root / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        model = entry["path"] == MODEL
        if model and entry.get("lfs", {}).get("oid") != MODEL_SHA256:
            raise RuntimeError("Upstream checkpoint digest differs from the pinned model.")

        def matches(path):
            if not path.is_file():
                return False
            if model:
                with path.open("rb") as handle:
                    return hashlib.file_digest(handle, "sha256").hexdigest() == MODEL_SHA256
            return git_digest(path.read_bytes()) == entry["oid"]

        if matches(target):
            return
        partial = target.with_suffix(target.suffix + ".download")
        try:
            with urllib.request.urlopen(BASE + entry["path"], timeout=90) as response, partial.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if not matches(partial):
                raise RuntimeError(f"Downloaded file failed verification: {entry['path']}")
            partial.replace(target)
            print(f"Verified {entry['path']}", flush=True)
        finally:
            partial.unlink(missing_ok=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch, entries))
    (root / "source-manifest.json").write_text(json.dumps({"revision": REVISION, "files": entries}, indent=2), encoding="utf-8")
    (root / "UPSTREAM-NOTICE.txt").write_text(
        "YourMT3+ by the YourMT3 authors. Inference sources are downloaded unchanged.\n"
        "Preserve the copyright and Apache-2.0 notices in the individual source files.\n"
        "Project repository and GPL-3.0 license: https://github.com/mimbres/YourMT3\n"
        "Source and checkpoint: https://huggingface.co/spaces/mimbres/YourMT3\n"
        f"Pinned source revision: {REVISION}\n"
        "Paper: https://arxiv.org/abs/2407.04822\n", encoding="utf-8")
    print("Pinned YourMT3+ source and checkpoint verified.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    download(parser.parse_args().runtime_dir / "vendor")
