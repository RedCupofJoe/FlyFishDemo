"""Reject model prose that introduces numbers the tools did not return."""

from __future__ import annotations

import re

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def prose_is_grounded(prose: str, source_text: str) -> bool:
    for number in _NUMBER.findall(prose):
        if number in source_text:
            continue
        if "." in number:
            whole = number.split(".", 1)[0]
            if whole in source_text:
                continue
        return False
    return True
