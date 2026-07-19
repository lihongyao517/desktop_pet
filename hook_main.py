from __future__ import annotations

import argparse

from codex_traffic_light.hook_bridge import run_hook
from codex_traffic_light.integration import install_hooks, uninstall_hooks


def main() -> int:
    parser = argparse.ArgumentParser(description="Codex Desktop Pet hook bridge")
    parser.add_argument("--hook", action="store_true", help="Read one Codex hook event from stdin")
    parser.add_argument("--install-hooks", action="store_true", help="Merge monitor hooks into Codex config")
    parser.add_argument("--uninstall-hooks", action="store_true", help="Remove only monitor-owned hooks")
    args = parser.parse_args()
    if args.install_hooks:
        print(install_hooks())
        return 0
    if args.uninstall_hooks:
        print(uninstall_hooks())
        return 0
    return run_hook()


if __name__ == "__main__":
    raise SystemExit(main())
