"""Native Verifiers + MCP integration check with a scripted local model endpoint.

This is an oracle reference workflow, not an LLM baseline or training result.
"""

import argparse
import asyncio
import json
import socket
import time
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from metis.taskset import load_metis_workspace


def reference_answer(task_id: str, purchased: dict) -> str:
    """Compute the six smoke answers from purchased observations, never gold answers."""
    match task_id:
        case "revenue-in-euros":
            return str(
                Decimal(str(purchased["filings"]["revenue"]))
                * Decimal(str(purchased["fx-spot"]["rate"]))
            )
        case "venue-rainfall":
            return str(
                sum(
                    Decimal(str(hour["rainfall_mm"]))
                    for hour in purchased["weather"]["hours"]
                )
            )
        case "parcel-arrival":
            return purchased["parcel"]["expected_delivery"]
        case "import-duty-euros":
            return str(
                Decimal(str(purchased["parcel"]["declared_value"]))
                * Decimal(str(purchased["tariff"]["duty_rate"]))
                * Decimal(str(purchased["fx-spot"]["rate"]))
            )
        case "stay-in-dollars":
            cheapest = min(
                option["total_with_fees"] for option in purchased["hotel"]["options"]
            )
            return str(
                Decimal(str(cheapest)) * Decimal(str(purchased["fx-spot"]["rate"]))
            )
        case "venue-transit":
            return str(purchased["transit"]["fare"])
        case _:
            raise ValueError(f"No scripted reference solver for task {task_id}")


def scripted_model_app() -> FastAPI:
    """A local OpenAI streaming fixture that drives actual discovered MCP tools."""
    document = load_metis_workspace()
    records = {record.prompt: record for record in document.tasks}
    resources = {resource.id: resource for resource in document.resources}
    app = FastAPI()

    @app.post("/v1/chat/completions")
    async def complete(request: Request):
        body = await request.json()
        messages = body["messages"]
        observation = json.loads(
            next(m["content"] for m in messages if m["role"] == "user")
        )
        record = records[observation["task"]]
        results = [message for message in messages if message["role"] == "tool"]
        plan = record.reference_purchases
        if len(results) < 2 * len(plan):
            step = plan[len(results) // 2]
            resource = resources[step.resource_id]
            if len(results) % 2 == 0:
                name = "metis_search_resources"
                arguments = {
                    "query": resource.name,
                    "category": resource.category,
                    "limit": 20,
                }
            else:
                discovered = json.loads(results[-1]["content"])
                assert any(row["id"] == resource.id for row in discovered["matches"])
                name, arguments = "metis_purchase", {"resource_id": resource.id}
        else:
            purchased = {}
            for step, result in zip(plan, results[1::2], strict=True):
                paid = json.loads(result["content"])
                assert paid["result"]["status"] == "ok", paid
                purchased[step.resource_id] = paid["result"]["data"]
            name = "metis_finish"
            arguments = {"answer": reference_answer(record.id, purchased)}
        assert name in {tool["function"]["name"] for tool in body["tools"]}
        chunk = {
            "id": f"chatcmpl-{uuid4().hex}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "metis-scripted-reference",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "tool_calls",
                    "delta": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": f"call_{uuid4().hex}",
                                "type": "function",
                                "function": {
                                    "name": name,
                                    "arguments": json.dumps(arguments),
                                },
                            }
                        ],
                    },
                }
            ],
        }
        return StreamingResponse(
            iter([f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n"]),
            media_type="text/event-stream",
        )

    return app


async def run_metis_smoke(output_dir: Path) -> Path:
    """Run six real harness/MCP rollouts without GPUs, external APIs, or credentials."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(scripted_model_app(), log_level="warning"))
    serving = asyncio.create_task(server.serve(sockets=[sock]))
    run_name = f"scripted-{uuid4().hex[:8]}"
    process: asyncio.subprocess.Process | None = None
    try:
        async with asyncio.timeout(15):
            while not server.started:
                await asyncio.sleep(0.01)
        process = await asyncio.create_subprocess_exec(
            "vf-run",
            "metis",
            "-m",
            "metis-scripted-reference",
            "-n",
            "6",
            "-r",
            "1",
            "--env.agent.runtime.type",
            "subprocess",
            "--client.base-url",
            f"http://127.0.0.1:{port}/v1",
            "--client.api-key-var",
            "METIS_SMOKE_UNUSED_KEY",
            "--max-concurrent",
            "2",
            "--output-dir",
            str(output_dir),
            "--run.name",
            run_name,
        )
        async with asyncio.timeout(240):
            code = await process.wait()
        if code != 0:
            raise RuntimeError(f"Metis native smoke run failed with exit code {code}")
    finally:
        if process is not None and process.returncode is None:
            process.terminate()
            await process.wait()
        server.should_exit = True
        await serving
        sock.close()
    run_dir = output_dir / run_name
    episodes = [
        json.loads(line) for line in (run_dir / "traces.jsonl").read_text().splitlines()
    ]
    assert len(episodes) == 6
    for episode in episodes:
        assert episode["ok"], episode
        trace = episode["traces"][0]
        assert trace["metrics"]["success"] == 1, trace.get("errors")
        assert (
            trace["info"]["metis"]["spent_units"]
            <= trace["info"]["metis"]["initial_budget_units"]
        )
        assert trace["info"]["metis"]["actions"]
        assert trace["calls"], "Native model-call recording was not exercised"
    print(f"6 scripted reference rollouts passed: {run_dir}")
    print("This verifies infrastructure, not model capability or learning.")
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/metis-smoke"))
    args = parser.parse_args()
    asyncio.run(run_metis_smoke(args.output_dir))


if __name__ == "__main__":
    main()
