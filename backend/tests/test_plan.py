import logging

import pytest
from fastapi.testclient import TestClient

from app.api import plan
from main import app


@pytest.mark.parametrize("failure_stage", ["initialization", "generation"])
def test_plan_failure_hides_exception_details_and_logs_traceback(
    monkeypatch, caplog, failure_stage
):
    error = RuntimeError("private internal details")

    def fail(*args, **kwargs):
        raise error

    if failure_stage == "initialization":
        monkeypatch.setattr(plan, "get_plan_engine", fail)
    else:
        engine = plan.PlanEngine([])
        monkeypatch.setattr(engine, "generate_plan", fail)
        monkeypatch.setattr(plan, "get_plan_engine", lambda: engine)

    with caplog.at_level(logging.ERROR, logger=plan.__name__):
        response = TestClient(app).post(
            "/api/plan",
            json={
                "parameters": {
                    "scene": "daily", "style": "natural", "intensity": "light"
                }
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "success": False,
        "steps": [],
        "totalDuration": 0,
        "omittedCount": 0,
        "message": "方案生成失败",
    }
    records = [record for record in caplog.records if record.name == plan.__name__]
    assert len(records) == 1
    assert records[0].exc_info[1] is error
