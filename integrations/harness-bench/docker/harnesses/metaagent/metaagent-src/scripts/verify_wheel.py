"""Install the built wheel into a new environment with locked kernel dependencies."""

import os
import subprocess
from pathlib import Path
from uuid import uuid4


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    wheels = sorted((root / "dist").glob("meta_agent-*.whl"))
    if len(wheels) != 1:
        raise SystemExit("Expected one meta_agent wheel in dist/. Run check.py --build first.")
    environment = root / ".artifacts" / f"wheel-{uuid4().hex}"
    env = dict(os.environ, UV_PROJECT_ENVIRONMENT=str(environment))
    subprocess.run(
        ["uv", "sync", "--locked", "--no-install-project", "--no-editable", "--no-dev"],
        cwd=root,
        env=env,
        check=True,
    )
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    # All kernel dependencies were installed from uv.lock above. Only our wheel
    # is installed without resolving again, preserving the pinned Git override.
    subprocess.run(
        ["uv", "pip", "install", "--python", str(python), "--no-deps", str(wheels[0])],
        cwd=root,
        env=env,
        check=True,
    )
    subprocess.run(["uv", "pip", "check", "--python", str(python)], cwd=root, env=env, check=True)
    subprocess.run(
        [
            str(python),
            "-I",
            "-c",
            "import pathlib, sys, meta_agent, meta_agent_adapter, agentworker; "
            "assert all(pathlib.Path(m.__file__).is_relative_to(sys.prefix) "
            "for m in (meta_agent, meta_agent_adapter, agentworker)); "
            "print('Installed wheel:', meta_agent.__version__)",
        ],
        cwd=environment,
        env=env,
        check=True,
    )
    subprocess.run(
        [str(python), "-I", str(root / "examples" / "kernel_smoke.py")],
        cwd=environment,
        env=env,
        check=True,
    )
    # This script imports only the installed MetaAgent package; its local model
    # is registered at the external-model boundary by the example itself.
    subprocess.run(
        [
            str(python),
            "-I",
            str(root / "examples" / "minimal_agent" / "run.py"),
            "--stream",
            "--output-dir",
            str(environment / "minimal-agent-demo"),
        ],
        cwd=environment,
        env=env,
        check=True,
    )
    subprocess.run(
        [
            str(python),
            "-I",
            str(root / "examples" / "refund_fastpath" / "run.py"),
            "--output-dir",
            str(environment / "refund-demo"),
        ],
        cwd=environment,
        env=env,
        check=True,
    )
    subprocess.run(
        [
            str(python),
            "-I",
            str(root / "examples" / "durable_effects" / "run.py"),
            "--output-dir",
            str(environment / "durable-effects-demo"),
        ],
        cwd=environment,
        env=env,
        check=True,
    )
    subprocess.run(
        [
            str(python),
            "-I",
            str(root / "examples" / "recoverable_agent" / "run.py"),
            "--output-dir",
            str(environment / "recoverable-agent-demo"),
        ],
        cwd=environment,
        env=env,
        check=True,
    )
    for fallback in (False, True):
        subprocess.run(
            [
                str(python),
                "-I",
                str(root / "examples" / "recoverable_agent" / "run.py"),
                "--fastpath",
                *(["--fallback"] if fallback else []),
                "--output-dir",
                str(environment / ("fastpath-fallback-demo" if fallback else "fastpath-demo")),
            ],
            cwd=environment,
            env=env,
            check=True,
        )
    worker = python.parent / ("meta-agent-worker.exe" if os.name == "nt" else "meta-agent-worker")
    subprocess.run([str(worker), "--help"], cwd=environment, env=env, check=True)
    subprocess.run(
        [
            str(python),
            "-X",
            "utf8",
            "-I",
            str(root / "examples" / "http_agent" / "run.py"),
            "--smoke",
            "--state-dir",
            str(environment / "http-demo"),
        ],
        cwd=environment,
        env=env,
        check=True,
    )
    subprocess.run(
        [
            str(python),
            "-X",
            "utf8",
            "-I",
            str(root / "examples" / "team_demo" / "run.py"),
            "--state-dir",
            str(environment / "team-demo"),
        ],
        cwd=environment,
        env=env,
        check=True,
    )
    subprocess.run(
        [
            str(python),
            "-X",
            "utf8",
            "-I",
            str(root / "examples" / "harness_demo" / "run.py"),
            "--state-dir",
            str(environment / "harness-demo"),
        ],
        cwd=environment,
        env=env,
        check=True,
    )
    subprocess.run(
        [
            str(python),
            "-X",
            "utf8",
            "-I",
            str(root / "examples/platform_demo/run.py"),
            "--state-dir",
            str(environment / "platform-demo"),
        ],
        cwd=environment,
        env=env,
        check=True,
    )
    subprocess.run(
        [
            str(python),
            "-X",
            "utf8",
            "-I",
            str(root / "examples/a2a_worker/run.py"),
            "--state-dir",
            str(environment / "a2a-demo"),
        ],
        cwd=environment,
        env=env,
        check=True,
    )
    subprocess.run(
        [
            str(python),
            "-X",
            "utf8",
            "-I",
            str(root / "examples/plugin_updates/run.py"),
            "--state-dir",
            str(environment / "plugin-updates"),
        ],
        cwd=environment,
        env=env,
        check=True,
    )
    subprocess.run(
        [
            str(python),
            "-X",
            "utf8",
            "-I",
            str(root / "examples/observability/run.py"),
            "--state-dir",
            str(environment / "observability"),
        ],
        cwd=environment,
        env=env,
        check=True,
    )
    subprocess.run(
        [
            str(python),
            "-X",
            "utf8",
            "-I",
            str(root / "examples/skill_evolution/run.py"),
            "--state-dir",
            str(environment / "skill-evolution"),
        ],
        cwd=environment,
        env=env,
        check=True,
    )
    subprocess.run(
        [
            str(python),
            "-X",
            "utf8",
            "-I",
            str(root / "examples/memory_skills/run.py"),
            "--state-dir",
            str(environment / "memory-skills"),
        ],
        cwd=environment,
        env=env,
        check=True,
    )
    subprocess.run(
        [
            str(python),
            "-X",
            "utf8",
            "-I",
            str(root / "examples/team_recovery/run.py"),
            "--state-dir",
            str(environment / "team-recovery"),
        ],
        cwd=environment,
        env=env,
        check=True,
    )
    for mode in ([], ["--single"]):
        subprocess.run(
            [
                str(python),
                "-X",
                "utf8",
                "-I",
                str(root / "examples/team_worker/run.py"),
                "--state-dir",
                str(environment / "team-worker"),
                *mode,
            ],
            cwd=environment,
            env=env,
            check=True,
        )
    subprocess.run(
        [
            str(python),
            "-X",
            "utf8",
            "-I",
            str(root / "examples/team_worker/recovery.py"),
            "--state-dir",
            str(environment / "team-worker-recovery"),
        ],
        cwd=environment,
        env=env,
        check=True,
    )
    print(f"Wheel verified in {environment}")


if __name__ == "__main__":
    main()
