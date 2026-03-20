import json
from types import SimpleNamespace

from services import kongkong_runtime_service as runtime_service


class DummyResult:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _build_instance():
    return SimpleNamespace(
        instance_slug="kongkong-1",
        gateway_token="gateway-token-1",
        container_name="",
        container_id="",
        cpu_limit=1.0,
        memory_limit_mb=2048,
        workspace_path="",
        config_path="",
        logs_path="",
        model_provider="dashscope",
        model_name="qwen-max",
        host_port=None,
        entry_url="",
        status="provisioning",
        started_at=None,
        stopped_at=None,
        error_message="",
        runtime_meta_json="",
    )


def test_provision_instance_runtime_docker_uses_proxy_entry_url_and_debug_port(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("KONGKONG_RUNTIME_MODE", "docker")
    monkeypatch.setenv("KONGKONG_BASE_DIR", str(tmp_path))
    monkeypatch.setenv("KONGKONG_DOCKER_NETWORK", "xiaxia-platform")
    monkeypatch.setenv("KONGKONG_EXPOSE_DEBUG_PORTS", "1")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://app.xiaxia.factory")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-dashscope-key")
    monkeypatch.setattr(runtime_service.time, "sleep", lambda *_args, **_kwargs: None)

    commands = []

    def fake_run(args):
        commands.append(args)
        if args[:4] == ["docker", "network", "inspect", "xiaxia-platform"]:
            return DummyResult(returncode=1, stderr="not found")
        if args[:4] == ["docker", "network", "create", "xiaxia-platform"]:
            return DummyResult(stdout="xiaxia-platform\n")
        if args[:4] == ["docker", "ps", "-a", "--filter"]:
            return DummyResult(stdout="")
        if args[:3] == ["docker", "run", "-d"]:
            return DummyResult(stdout="container-123\n")
        if args[:2] == ["docker", "inspect"] and len(args) == 3:
            return DummyResult(stdout=json.dumps([{
                "State": {"Status": "running", "Health": {"Status": "starting"}},
                "RestartCount": 0,
            }]))
        if args[:3] == ["docker", "inspect", "-f"]:
            return DummyResult(stdout="running\n")
        if args[:3] == ["docker", "port", "kongkong-kongkong-1"]:
            return DummyResult(stdout="127.0.0.1:39123\n")
        raise AssertionError(f"Unexpected command: {args}")

    monkeypatch.setattr(runtime_service, "_run_command", fake_run)

    instance = _build_instance()
    runtime_service.provision_instance_runtime(instance)

    assert instance.container_name == "kongkong-kongkong-1"
    assert instance.status == "running"
    assert instance.entry_url == "https://app.xiaxia.factory/kongkong/kongkong-1/"
    assert instance.host_port == 39123

    meta = json.loads(instance.runtime_meta_json)
    assert meta["network"] == "xiaxia-platform"
    assert meta["proxy_entry_url"] == "https://app.xiaxia.factory/kongkong/kongkong-1/"
    assert meta["debug_entry_url"] == "https://app.xiaxia.factory:39123/"

    run_command = next(args for args in commands if args[:3] == ["docker", "run", "-d"])
    assert "--network" in run_command
    assert "xiaxia-platform" in run_command
    assert "-p" in run_command
    assert "127.0.0.1::18789" in run_command


def test_build_launch_payload_prefers_proxy_entry_url_over_debug_port(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("KONGKONG_RUNTIME_MODE", "docker")

    instance = _build_instance()
    instance.entry_url = "https://app.xiaxia.factory/kongkong/kongkong-1/"
    instance.runtime_meta_json = json.dumps({
        "mode": "docker",
        "debug_entry_url": "https://app.xiaxia.factory:39123/",
    }, ensure_ascii=False)

    payload = runtime_service.build_launch_payload(instance)

    assert payload["launch_url"] == "https://app.xiaxia.factory/kongkong/kongkong-1/#token=gateway-token-1"
    assert payload["entry_url"] == "https://app.xiaxia.factory/kongkong/kongkong-1/"
    assert payload["debug_launch_url"] == "https://app.xiaxia.factory:39123/"


def test_collect_runtime_config_errors_requires_kongkong_docker_envs(app_module):
    errors = app_module.collect_runtime_config_errors(
        app_env="production",
        env_map={
            "DB_PASS": "prod-db-pass-123456",
            "JWT_SECRET": "prod-jwt-secret-abcdefghijklmnopqrstuvwxyz",
            "PUBLIC_BASE_URL": "https://app.xiaxia.factory",
            "ALLOWED_ORIGINS": "https://app.xiaxia.factory",
            "KONGKONG_RUNTIME_MODE": "docker",
        },
    )
    assert "KONGKONG_BASE_DIR 缺失" in "\n".join(errors)
    assert "KONGKONG_DOCKER_NETWORK 缺失" in "\n".join(errors)


def test_start_instance_runtime_reprovisions_mock_instance_in_docker_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("KONGKONG_RUNTIME_MODE", "docker")
    monkeypatch.setenv("KONGKONG_BASE_DIR", str(tmp_path))
    monkeypatch.setenv("KONGKONG_DOCKER_NETWORK", "xiaxia-platform")
    monkeypatch.setenv("KONGKONG_EXPOSE_DEBUG_PORTS", "1")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://app.xiaxia.factory")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-dashscope-key")
    monkeypatch.setattr(runtime_service.time, "sleep", lambda *_args, **_kwargs: None)

    def fake_run(args):
        if args[:4] == ["docker", "network", "inspect", "xiaxia-platform"]:
            return DummyResult(stdout="[]")
        if args[:4] == ["docker", "ps", "-a", "--filter"]:
            return DummyResult(stdout="")
        if args[:3] == ["docker", "run", "-d"]:
            return DummyResult(stdout="container-456\n")
        if args[:2] == ["docker", "inspect"] and len(args) == 3:
            return DummyResult(stdout=json.dumps([{
                "State": {"Status": "running", "Health": {"Status": "starting"}},
                "RestartCount": 0,
            }]))
        if args[:3] == ["docker", "port", "kongkong-kongkong-1"]:
            return DummyResult(stdout="127.0.0.1:40123\n")
        raise AssertionError(f"Unexpected command: {args}")

    monkeypatch.setattr(runtime_service, "_run_command", fake_run)

    instance = _build_instance()
    instance.container_name = "mock-kongkong-1"
    instance.entry_url = "https://app.xiaxia.factory/kongkong/mock/kongkong-1/"
    instance.runtime_meta_json = json.dumps({"mode": "mock"}, ensure_ascii=False)

    runtime_service.start_instance_runtime(instance)

    assert instance.container_name == "kongkong-kongkong-1"
    assert instance.container_id == "container-456"
    assert instance.entry_url == "https://app.xiaxia.factory/kongkong/kongkong-1/"
    assert instance.host_port == 40123
