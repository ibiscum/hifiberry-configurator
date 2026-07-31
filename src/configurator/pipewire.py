"""
pipewire.py - PipeWire volume control utility

Provides functions to get/set volume for a given control name and list all available volume controls.
"""
import subprocess
import logging
import math
import re
from typing import List, Optional


PW_CLI_TIMEOUT = 5.0
NAME_LINE_RE = re.compile(r'^\s*name\s*=\s*"([^"]+)"\s*$')
VOLUME_LINE_RE = re.compile(r'^\s*volume\s*=\s*([0-9]*\.?[0-9]+)\s*$')

def _run_pw_cli(args: List[str]) -> Optional[str]:
    try:
        result = subprocess.run(
            ["pw-cli"] + args,
            capture_output=True,
            text=True,
            check=True,
            timeout=PW_CLI_TIMEOUT,
        )
        return result.stdout
    except FileNotFoundError:
        logging.error("pw-cli command not found")
        return None
    except subprocess.TimeoutExpired:
        logging.error("pw-cli command timed out")
        return None
    except subprocess.CalledProcessError as e:
        logging.error(f"pw-cli command failed: {e.stderr.strip() if e.stderr else e}")
        return None
    except OSError as e:
        logging.error(f"pw-cli execution error: {e}")
        return None

def get_volume_controls() -> List[str]:
    """
    Returns a list of all PipeWire volume control names.
    """
    output = _run_pw_cli(["list", "Node"])
    if not output:
        return []
    controls = []
    for line in output.splitlines():
        match = NAME_LINE_RE.match(line)
        if match:
            controls.append(match.group(1))
    return controls

def get_volume(control_name: str) -> Optional[float]:
    """
    Gets the volume for the given PipeWire control name.
    Returns the volume as a float between 0.0 and 1.0, or None if not found.
    """
    output = _run_pw_cli(["info", control_name])
    if not output:
        return None
    for line in output.splitlines():
        match = VOLUME_LINE_RE.match(line)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
    return None

def set_volume(control_name: str, volume: float) -> bool:
    """
    Sets the volume for the given PipeWire control name.
    Volume should be a float between 0.0 and 1.0.
    Returns True if successful, False otherwise.
    """
    if not math.isfinite(volume) or volume < 0.0 or volume > 1.0:
        logging.error(f"Invalid volume value: {volume}")
        return False

    try:
        subprocess.run(
            ["pw-cli", "set", control_name, "volume", str(volume)],
            capture_output=True,
            text=True,
            check=True,
            timeout=PW_CLI_TIMEOUT,
        )
        return True
    except FileNotFoundError:
        logging.error("pw-cli command not found")
        return False
    except subprocess.TimeoutExpired:
        logging.error("pw-cli set command timed out")
        return False
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to set volume: {e.stderr.strip() if e.stderr else e}")
        return False
    except OSError as e:
        logging.error(f"pw-cli execution error: {e}")
        return False



def main():
    import sys
    def print_usage():
        print("Usage:")
        print("  config-pipewire list")
        print("  config-pipewire get <control_name>")
        print("  config-pipewire set <control_name> <volume>")
        print("  (volume must be between 0.0 and 1.0)")

    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "list":
        controls = get_volume_controls()
        for c in controls:
            print(c)
    elif cmd == "get" and len(sys.argv) == 3:
        vol = get_volume(sys.argv[2])
        if vol is None:
            print(f"Control '{sys.argv[2]}' not found or no volume info.")
            sys.exit(2)
        print(vol)
    elif cmd == "set" and len(sys.argv) == 4:
        try:
            volume = float(sys.argv[3])
        except ValueError:
            print("Volume must be a float between 0.0 and 1.0")
            sys.exit(3)
        if volume < 0.0 or volume > 1.0 or not math.isfinite(volume):
            print("Volume must be a float between 0.0 and 1.0")
            sys.exit(3)
        ok = set_volume(sys.argv[2], volume)
        if not ok:
            print(f"Failed to set volume for '{sys.argv[2]}'")
            sys.exit(4)
        print("OK")
    else:
        print_usage()
        sys.exit(1)

if __name__ == "__main__":
    main()

