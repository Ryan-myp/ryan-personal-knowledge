import asyncio

import pytest
from fastapi import HTTPException

from agents.ad_agent.api.context import read_request_body_limited


class _Request:
    def __init__(self, chunks):
        self.headers = {}
        self._chunks = list(chunks)

    async def stream(self):
        for chunk in self._chunks:
            yield chunk


def test_read_request_body_limited_accepts_body_at_limit():
    request = _Request([b"ab", b"cd"])

    result = asyncio.run(read_request_body_limited(request, max_bytes=4))

    assert result == b"abcd"


def test_read_request_body_limited_rejects_chunked_body_over_limit():
    request = _Request([b"abc", b"def"])

    with pytest.raises(HTTPException) as error:
        asyncio.run(read_request_body_limited(request, max_bytes=5))

    assert error.value.status_code == 413
