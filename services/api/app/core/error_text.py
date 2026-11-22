# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""One sanitiser for every error string that may reach a sysadmin screen (or a log line shown there):
URL credentials removed, SQL text and bound parameters cut off, first line only, length capped."""

import re

# "://user:pass@" up to the FIRST "@", so a password containing "/" is covered too.
_URL_CREDENTIALS = re.compile(r"://[^\s@]*@")
_SQL_MARKERS = ("[SQL:", "[parameters:")


def sanitize_error_text(value: object, limit: int) -> str:
    text = _URL_CREDENTIALS.sub("://***@", str(value))
    for marker in _SQL_MARKERS:
        text = text.split(marker, 1)[0]
    lines = text.strip().splitlines()
    return (lines[0].strip() if lines else "")[:limit]
