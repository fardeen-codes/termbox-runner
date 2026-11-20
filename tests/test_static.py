"""Tests for static asset serving and UI assets."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_static_css_and_js_served(async_client: AsyncClient):
    res_css = await async_client.get("/static/css/theme.css")
    assert res_css.status_code == 200
    assert "--bg:" in res_css.text

    res_js = await async_client.get("/static/js/api.js")
    assert res_js.status_code == 200
    assert "TermboxAPI" in res_js.text
