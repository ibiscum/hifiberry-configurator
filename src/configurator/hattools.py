#!/usr/bin/env python3
"""HAT (Hardware Attached on Top) information retrieval tool.

Provides functions to read and display HAT EEPROM information including
vendor, product name, and UUID.
"""

import argparse
import logging
import sys
from typing import Dict, Optional

# Import from the hateeprom module in the eeprom package
try:
    from hateeprom import HatEEPROM  # type: ignore
except ImportError:
    # Fallback if hateeprom is not available
    HatEEPROM = None  # type: ignore

# Default values for missing HAT information
DEFAULT_VENDOR: str = "no vendor"
"""Default vendor string when vendor is not found."""
DEFAULT_PRODUCT: str = "no product"
"""Default product string when product is not found."""
DEFAULT_UUID: str = "unknown"
"""Default UUID string when UUID is not found."""


def _normalize_hat_field(value: object) -> Optional[str]:
    """Normalize a HAT metadata field to optional string value."""
    if not isinstance(value, str):
        return None
    return None if value == 'Unknown' else value

def get_hat_info(verbose: bool = False) -> Dict[str, Optional[str]]:
    """
    Return a dictionary with keys 'vendor', 'product', and 'uuid'.
    If a value is not found, its value is set to None.

    This function now uses the hateeprom module from the eeprom package.

    Args:
        verbose: If True, log warning and error messages
    """
    if HatEEPROM is None:
        if verbose:
            logging.warning("hateeprom module not available, returning default values")
        return {"vendor": None, "product": None, "uuid": None}

    empty_info: Dict[str, Optional[str]] = {"vendor": None, "product": None, "uuid": None}

    try:
        # Initialize HAT EEPROM interface
        hat = HatEEPROM()  # type: ignore

        # Get HAT information using the short_info method
        info = hat.short_info(debug=False)  # type: ignore

        if not isinstance(info, dict):
            if verbose:
                logging.error("Invalid HAT EEPROM response type")
            return empty_info

        if info.get('success'):
            return {
                "vendor": _normalize_hat_field(info.get('vendor')),
                "product": _normalize_hat_field(info.get('product')),
                "uuid": _normalize_hat_field(info.get('uuid'))
            }
        else:
            # Return None values if reading failed
            return empty_info

    except Exception as e:
        if verbose:
            logging.error(f"Error reading HAT information: {e}")
        return empty_info

def main() -> int:
    """Retrieve and display HAT information via command-line interface.

    Reads HAT EEPROM data and outputs vendor, product, and UUID information.
    Supports different output formats and verbose logging.

    Returns:
        Exit code (always 0)
    """
    # Configure logging to send messages to stderr
    # Set to ERROR level to only show critical errors, not warnings
    logging.basicConfig(level=logging.ERROR, stream=sys.stderr)

    parser = argparse.ArgumentParser(description="Retrieve HAT information")
    parser.add_argument("-a", "--all", action="store_true",
                        help="Display vendor, product, and UUID")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose error messages")
    args = parser.parse_args()

    # Adjust logging level based on verbose flag
    if args.verbose:
        logging.getLogger().setLevel(logging.WARNING)

    info = get_hat_info(verbose=args.verbose)

    # Convert None values to default strings in main
    vendor_value = info.get("vendor")
    product_value = info.get("product")
    uuid_value = info.get("uuid")
    vendor: str = vendor_value if isinstance(vendor_value, str) else DEFAULT_VENDOR
    product: str = product_value if isinstance(product_value, str) else DEFAULT_PRODUCT
    uuid: str = uuid_value if isinstance(uuid_value, str) else DEFAULT_UUID

    if args.all:
        print(f"{vendor}:{product}:{uuid}")
    else:
        print(f"{vendor}:{product}")

    return 0

if __name__ == "__main__":
    sys.exit(main())

