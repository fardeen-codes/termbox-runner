"""Tests for benchmark template catalog and template launcher endpoints."""

import pytest
from httpx import AsyncClient
from termbox_runner.templates_catalog import get_benchmark_template, list_benchmark_templates


def test_template_catalog_definitions():
    templates = list_benchmark_templates()
    assert len(templates) >= 5
    ids = [t.id for t in templates]
    assert "humaneval-py" in ids
    assert "swe-mini" in ids
    assert "memory-stress" in ids
    assert "wallclock-timeout" in ids

    tmpl = get_benchmark_template("humaneval-py")
    assert tmpl is not None
    assert "solution.py" in tmpl.task.files


@pytest.mark.asyncio
async def test_template_api_endpoints(async_client: AsyncClient):
    # List templates
    res = await async_client.get("/templates")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 5

    # Get specific template
    res_one = await async_client.get("/templates/humaneval-py")
    assert res_one.status_code == 200
    assert res_one.json()["id"] == "humaneval-py"

    # Launch template
    res_launch = await async_client.post("/templates/humaneval-py/launch")
    assert res_launch.status_code == 201
    run = res_launch.json()
    assert run["run_id"].startswith("run_")

    # 404 for invalid template
    res_404 = await async_client.get("/templates/nonexistent_template")
    assert res_404.status_code == 404


def test_new_multilang_templates():
    from termbox_runner.templates_catalog import get_benchmark_template, get_templates_by_category
    
    assert get_benchmark_template("nodejs-jest") is not None
    assert get_benchmark_template("rust-cargo") is not None
    assert get_benchmark_template("bash-script") is not None

    js_templates = get_templates_by_category("javascript")
    assert len(js_templates) >= 1
    assert js_templates[0].id == "nodejs-jest"


def test_templates_part3_additions():
    from termbox_runner.templates_catalog import get_benchmark_template, search_templates_by_tag

    assert get_benchmark_template("ts-vitest") is not None
    assert get_benchmark_template("dotnet-xunit") is not None
    assert get_benchmark_template("rego-opa") is not None

    matches = search_templates_by_tag("Python")
    assert len(matches) >= 1

def test_swebench_and_security_templates():
    from termbox_runner.templates_catalog import TEMPLATES, filter_templates_by_timeout_range
    assert "django-orm" in TEMPLATES
    assert "sklearn-pipeline" in TEMPLATES
    assert "security-sqli" in TEMPLATES
    assert "network-ping" in TEMPLATES
    filtered = filter_templates_by_timeout_range(10.0, 30.0)
    assert len(filtered) > 5

def test_ruby_and_rust_templates():
    from termbox_runner.templates_catalog import TEMPLATES
    assert "ruby-rspec" in TEMPLATES
    assert "go-cpu-profile" in TEMPLATES
    assert "rust-clippy" in TEMPLATES

def test_functional_and_systems_templates():
    from termbox_runner.templates_catalog import TEMPLATES
    assert "haskell-cabal" in TEMPLATES
    assert "ocaml-dune" in TEMPLATES
    assert "zig-test" in TEMPLATES

def test_web_and_db_templates_batch1():
    from termbox_runner.templates_catalog import TEMPLATES, list_template_categories
    assert "express-api" in TEMPLATES
    assert "spring-boot" in TEMPLATES
    assert "security-jwt" in TEMPLATES
    assert "alembic-mig" in TEMPLATES
    assert len(list_template_categories()) >= 6

def test_systems_and_devops_templates_batch2():
    from termbox_runner.templates_catalog import TEMPLATES
    assert "lisp-sbcl" in TEMPLATES
    assert "fsharp-test" in TEMPLATES
    assert "nim-nimble" in TEMPLATES
    assert "openapi-validate" in TEMPLATES
    assert "terraform-validate" in TEMPLATES

def test_data_science_and_wasm_templates_batch3():
    from termbox_runner.templates_catalog import TEMPLATES
    assert "racket-test" in TEMPLATES
    assert "wasm-wasmtime" in TEMPLATES
    assert "duckdb-sql" in TEMPLATES
    assert "polars-df" in TEMPLATES
    assert "clickhouse-local" in TEMPLATES
