# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Concurrent core-status callers share one probe run; the result is reused until the TTL ends."""

import threading
import time

from app.services.admin_core_status import SingleFlightCache


def test_concurrent_callers_share_one_computation():
    cache = SingleFlightCache(ttl_s=5)
    calls = []

    def compute():
        calls.append(1)
        time.sleep(0.2)
        return []

    threads = [threading.Thread(target=cache.get, args=(compute,)) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(calls) == 1


def test_value_is_recomputed_after_ttl():
    cache = SingleFlightCache(ttl_s=0.05)
    calls = []
    cache.get(lambda: calls.append(1) or [])
    time.sleep(0.1)
    cache.get(lambda: calls.append(1) or [])
    assert len(calls) == 2
