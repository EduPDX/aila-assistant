from types import SimpleNamespace

from aila.core.infrastructure import _size_hint, build_infrastructure_snapshot
from aila.core.models import ModelInventory, ModelState


class _Snapshot:
    def __init__(self, value):
        self.value = value

    def snapshot(self):
        return self.value


def test_scale_is_logarithmic_and_bounded():
    assert 0.72 <= _size_hint("qwen:3b") < _size_hint("nemotron-550b") <= 1.48


def test_infrastructure_contains_local_and_configured_cloud_without_secrets():
    provider = SimpleNamespace(
        api_key="secret", enabled=True, model="nvidia/nemotron-3-ultra-550b-a55b", vision=False,
    )
    engine = SimpleNamespace(
        settings=SimpleNamespace(
            llm=SimpleNamespace(model="qwen2.5:7b"),
            providers=SimpleNamespace(items=lambda: [("nvidia", provider)]),
        ),
        llm=SimpleNamespace(default_model="qwen2.5:7b"),
        router=SimpleNamespace(providers={"ollama": object(), "nvidia": object()}),
        health=_Snapshot({"nvidia": {"state": "closed"}}),
        telemetry=_Snapshot({}),
    )
    inventory = ModelInventory(states=[ModelState(
        name="qwen2.5:7b", roles=["chat"], installed=True, loaded=True,
        vram_mb=4200, disk_mb=4700,
    )], ollama_ok=True, loaded_vram_mb=4200)

    result = build_infrastructure_snapshot(engine, inventory, active_provider="nvidia")

    assert len(result["racks"]) == 2
    assert next(r for r in result["racks"] if r["provider"] == "nvidia")["status"] == "active"
    assert "secret" not in repr(result)
