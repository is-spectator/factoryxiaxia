"""空空 OpenClaw 运行时管理。"""
import datetime
import json
import os
import pathlib
import re
import secrets
import subprocess
import time
import urllib.parse


OPENCLAW_GATEWAY_PORT = 18789
DEFAULT_OPENCLAW_IMAGE = "ghcr.io/openclaw/openclaw:latest"


def _env(key, default=""):
    return (os.environ.get(key) or default).strip()


def get_runtime_mode():
    configured = _env("KONGKONG_RUNTIME_MODE", "")
    if configured in ("docker", "mock"):
        return configured
    app_env = _env("APP_ENV", "development").lower()
    if app_env == "test":
        return "mock"
    return "mock"


def is_runtime_enabled():
    return get_runtime_mode() == "docker"


def get_public_base_url():
    return _env("PUBLIC_BASE_URL", "http://localhost:10088")


def get_public_origin():
    parsed = urllib.parse.urlparse(get_public_base_url())
    scheme = parsed.scheme or "http"
    if parsed.netloc:
        return f"{scheme}://{parsed.netloc}"
    hostname = parsed.hostname or "localhost"
    if parsed.port:
        return f"{scheme}://{hostname}:{parsed.port}"
    return f"{scheme}://{hostname}"


def get_openclaw_image():
    return _env("OPENCLAW_IMAGE", DEFAULT_OPENCLAW_IMAGE)


def get_runtime_base_dir():
    configured = _env("KONGKONG_BASE_DIR", "") or _env("KONGKONG_HOST_BASE_DIR", "")
    if configured:
        return pathlib.Path(configured)
    return pathlib.Path(__file__).resolve().parents[2] / "runtime" / "kongkong"


def get_runtime_network():
    return _env("KONGKONG_DOCKER_NETWORK", "xiaxia-platform")


def get_proxy_path_prefix():
    prefix = _env("KONGKONG_PROXY_PATH_PREFIX", "/kongkong").strip()
    if not prefix:
        return "/kongkong"
    return "/" + prefix.strip("/")


def should_expose_debug_ports():
    configured = _env("KONGKONG_EXPOSE_DEBUG_PORTS", "")
    if configured:
        return configured.lower() in ("1", "true", "yes", "on")
    return _env("APP_ENV", "development").lower() != "production"


def generate_gateway_token():
    return secrets.token_urlsafe(24)


def slugify_instance_name(name, deployment_id):
    slug = re.sub(r"[^a-z0-9]+", "-", str(name or "").strip().lower()).strip("-")
    slug = slug or "kongkong"
    return f"{slug[:48]}-{deployment_id}"


def get_instance_root(instance):
    return get_runtime_base_dir() / instance.instance_slug


def build_runtime_paths(instance):
    root = get_instance_root(instance)
    config_dir = root / "config"
    workspace_dir = root / "workspace"
    logs_dir = root / "logs"
    config_file = config_dir / "openclaw.json"
    return {
        "root": root,
        "workspace_dir": workspace_dir,
        "config_dir": config_dir,
        "logs_dir": logs_dir,
        "config_file": config_file,
    }


def get_dashscope_base_url():
    return _env("DASHSCOPE_COMPATIBLE_BASE_URL", "") or "https://dashscope.aliyuncs.com/compatible-mode/v1"


def render_openclaw_config(instance):
    model_id = instance.model_name or "qwen-max"
    provider_name = instance.model_provider or "dashscope"
    control_ui = {
        "allowedOrigins": [get_public_origin()],
        # 空空通过平台代理交付，浏览器侧没有稳定设备身份链路；
        # 这里改为仅依赖 gateway token，避免用户再做 OpenClaw pairing。
        "dangerouslyDisableDeviceAuth": True,
    }
    if should_expose_debug_ports():
        control_ui["dangerouslyAllowHostHeaderOriginFallback"] = True
    return {
        "gateway": {
            "mode": "local",
            "controlUi": control_ui,
        },
        "models": {
            "providers": {
                provider_name: {
                    "api": "openai-completions",
                    "baseUrl": get_dashscope_base_url(),
                    "apiKey": "${DASHSCOPE_API_KEY}",
                    "models": [
                        {
                            "id": model_id,
                            "name": "Qwen Max",
                        }
                    ],
                }
            }
        },
        "agents": {
            "defaults": {
                "model": {
                    "primary": f"{provider_name}/{model_id}"
                }
            }
        },
    }


def prepare_instance_files(instance):
    paths = build_runtime_paths(instance)
    for path in [paths["root"], paths["workspace_dir"], paths["config_dir"], paths["logs_dir"]]:
        path.mkdir(parents=True, exist_ok=True)
    config_payload = render_openclaw_config(instance)
    paths["config_file"].write_text(
        json.dumps(config_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    instance.workspace_path = str(paths["workspace_dir"])
    instance.config_path = str(paths["config_file"])
    instance.logs_path = str(paths["logs_dir"])
    return paths


def _load_existing_config_payload(config_file):
    if not config_file.exists():
        return None
    try:
        return json.loads(config_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def instance_runtime_config_needs_sync(instance):
    if not is_runtime_enabled() or is_mock_runtime_record(instance):
        return False
    paths = build_runtime_paths(instance)
    existing_payload = _load_existing_config_payload(paths["config_file"])
    desired_payload = render_openclaw_config(instance)
    if existing_payload != desired_payload:
        return True
    if (instance.entry_url or "") != _build_proxy_entry_url(instance):
        return True
    if not (instance.workspace_path and instance.config_path and instance.logs_path):
        return True
    return False


def reconcile_instance_runtime(instance, restart_if_running=False):
    if not instance_runtime_config_needs_sync(instance):
        return False
    prepare_instance_files(instance)
    instance.entry_url = _build_proxy_entry_url(instance)
    if restart_if_running and instance.container_name and _inspect_container_status(instance.container_name) == "running":
        restart_instance_runtime(instance)
    return True


def _run_command(args):
    return subprocess.run(args, capture_output=True, text=True, check=False)


def _load_runtime_meta(instance):
    raw = getattr(instance, "runtime_meta_json", "") or ""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def is_mock_runtime_record(instance):
    runtime_meta = _load_runtime_meta(instance)
    if runtime_meta.get("mode") == "mock":
        return True
    if str(getattr(instance, "container_name", "") or "").startswith("mock-"):
        return True
    return "/kongkong/mock/" in str(getattr(instance, "entry_url", "") or "")


def _reset_instance_runtime_state(instance):
    instance.container_name = ""
    instance.container_id = ""
    instance.host_port = None
    instance.entry_url = ""
    instance.error_message = ""
    instance.runtime_meta_json = ""


def _parse_host_port(port_output):
    raw = (port_output or "").strip()
    if ":" not in raw:
        return None
    host_port = raw.rsplit(":", 1)[-1].strip()
    try:
        return int(host_port)
    except (TypeError, ValueError):
        return None


def _public_host_for_port(port):
    base_url = get_public_base_url()
    parsed = urllib.parse.urlparse(base_url)
    scheme = parsed.scheme or "http"
    hostname = parsed.hostname or "localhost"
    return f"{scheme}://{hostname}:{port}/"


def _build_proxy_entry_url(instance):
    return f"{get_public_base_url().rstrip('/')}{get_proxy_path_prefix()}/{instance.instance_slug}/"


def _build_launch_bootstrap_url(instance):
    base = get_public_base_url().rstrip("/")
    slug = urllib.parse.quote(instance.instance_slug, safe="")
    token = urllib.parse.quote(instance.gateway_token or "", safe="")
    return f"{base}/kongkong-launch.html?slug={slug}#token={token}"


def _ensure_network_exists():
    network_name = get_runtime_network()
    inspect_result = _run_command(["docker", "network", "inspect", network_name])
    if inspect_result.returncode == 0:
        return network_name
    create_result = _run_command(["docker", "network", "create", network_name])
    if create_result.returncode != 0:
        raise RuntimeError((create_result.stderr or create_result.stdout or "docker network create 失败").strip()[:240])
    return network_name


def _find_existing_container(name):
    result = _run_command(["docker", "ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}"])
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def _inspect_container_status(name):
    result = _run_command(["docker", "inspect", "-f", "{{.State.Status}}", name])
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def _inspect_container_details(name):
    result = _run_command(["docker", "inspect", name])
    if result.returncode != 0:
        return {}
    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return {}
    return payload[0] if payload else {}


def _get_container_logs(name):
    result = _run_command(["docker", "logs", "--tail", "40", name])
    return (result.stderr or result.stdout or "").strip()


def _wait_for_container_ready(name):
    timeout_seconds = float(_env("KONGKONG_READY_TIMEOUT_SECONDS", "20"))
    deadline = time.time() + timeout_seconds
    last_details = {}
    stable_running_polls = 0
    required_stable_polls = int(_env("KONGKONG_STABLE_RUNNING_POLLS", "10"))
    while time.time() < deadline:
        details = _inspect_container_details(name)
        last_details = details
        state = details.get("State") or {}
        status = (state.get("Status") or "").strip()
        health = ((state.get("Health") or {}).get("Status") or "").strip()
        restart_count = int(details.get("RestartCount") or 0)
        if status == "running" and restart_count == 0:
            stable_running_polls += 1
            if health in ("", "healthy") or stable_running_polls >= required_stable_polls:
                return details
        else:
            stable_running_polls = 0
        time.sleep(1)

    state = last_details.get("State") or {}
    status = (state.get("Status") or "").strip() or "unknown"
    health = ((state.get("Health") or {}).get("Status") or "").strip() or "unknown"
    restart_count = int(last_details.get("RestartCount") or 0)
    log_excerpt = _get_container_logs(name)
    raise RuntimeError(
        (
            f"OpenClaw 容器未就绪，status={status}, health={health}, restarts={restart_count}. "
            f"{log_excerpt}"
        ).strip()[:240]
    )


def provision_instance_runtime(instance):
    prepare_instance_files(instance)
    if not instance.gateway_token:
        instance.gateway_token = generate_gateway_token()

    if not is_runtime_enabled():
        instance.status = "running"
        instance.container_name = f"mock-{instance.instance_slug}"
        instance.container_id = ""
        instance.host_port = None
        instance.entry_url = (
            f"{get_public_base_url().rstrip('/')}/kongkong/mock/{instance.instance_slug}/"
        )
        instance.started_at = datetime.datetime.utcnow()
        instance.error_message = ""
        instance.runtime_meta_json = json.dumps({
            "mode": "mock",
            "image": get_openclaw_image(),
        }, ensure_ascii=False)
        return instance

    dashscope_api_key = _env("DASHSCOPE_API_KEY", "")
    if not dashscope_api_key:
        raise RuntimeError("DASHSCOPE_API_KEY 未配置，无法为空空实例注入 OpenClaw 模型密钥")

    if not instance.container_name:
        instance.container_name = f"kongkong-{instance.instance_slug}"
    elif str(instance.container_name).startswith("mock-"):
        instance.container_name = f"kongkong-{instance.instance_slug}"

    _ensure_network_exists()
    existing_container = _find_existing_container(instance.container_name)
    if existing_container:
        _run_command(["docker", "rm", "-f", instance.container_name])

    runtime_paths = build_runtime_paths(instance)
    command = [
        "docker", "run", "-d",
        "--name", instance.container_name,
        "--restart", "unless-stopped",
        "--network", get_runtime_network(),
        "--network-alias", instance.container_name,
        "--cpus", str(float(instance.cpu_limit or 1.0)),
        "--memory", f"{int(instance.memory_limit_mb or 2048)}m",
        "--pids-limit", _env("KONGKONG_PIDS_LIMIT", "256"),
        "-e", "HOME=/home/node",
        "-e", "NODE_ENV=production",
        "-e", "TERM=xterm-256color",
        "-e", "XDG_CONFIG_HOME=/home/node/.openclaw",
        "-e", f"OPENCLAW_GATEWAY_TOKEN={instance.gateway_token}",
        "-e", f"DASHSCOPE_API_KEY={dashscope_api_key}",
        "-v", f"{runtime_paths['config_dir']}:/home/node/.openclaw",
        "-v", f"{instance.workspace_path}:/home/node/.openclaw/workspace",
        "-v", f"{instance.logs_path}:/logs",
    ]
    if should_expose_debug_ports():
        command.extend(["-p", f"127.0.0.1::{OPENCLAW_GATEWAY_PORT}"])
    command.extend([
        get_openclaw_image(),
        "node", "dist/index.js", "gateway", "--bind", "lan", "--port", str(OPENCLAW_GATEWAY_PORT),
    ])
    run_result = _run_command(command)
    if run_result.returncode != 0:
        raise RuntimeError((run_result.stderr or run_result.stdout or "docker run 失败").strip()[:240])

    instance.container_id = (run_result.stdout or "").strip()
    _wait_for_container_ready(instance.container_name)

    host_port = None
    debug_entry_url = ""
    if should_expose_debug_ports():
        port_result = _run_command(["docker", "port", instance.container_name, f"{OPENCLAW_GATEWAY_PORT}/tcp"])
        host_port = _parse_host_port(port_result.stdout)
        if host_port:
            debug_entry_url = _public_host_for_port(host_port)

    instance.host_port = host_port
    instance.entry_url = _build_proxy_entry_url(instance)
    instance.status = "running"
    instance.started_at = datetime.datetime.utcnow()
    instance.error_message = ""
    instance.runtime_meta_json = json.dumps({
        "mode": "docker",
        "image": get_openclaw_image(),
        "network": get_runtime_network(),
        "gateway_port": OPENCLAW_GATEWAY_PORT,
        "proxy_entry_url": instance.entry_url,
        "debug_entry_url": debug_entry_url,
    }, ensure_ascii=False)
    return instance


def start_instance_runtime(instance):
    if not is_runtime_enabled():
        instance.status = "running"
        instance.started_at = instance.started_at or datetime.datetime.utcnow()
        instance.stopped_at = None
        return instance
    if not instance.container_name or is_mock_runtime_record(instance):
        _reset_instance_runtime_state(instance)
        return provision_instance_runtime(instance)
    result = _run_command(["docker", "start", instance.container_name])
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "docker start 失败").strip()[:240])
    _wait_for_container_ready(instance.container_name)
    instance.status = "running"
    instance.stopped_at = None
    instance.started_at = instance.started_at or datetime.datetime.utcnow()
    return instance


def stop_instance_runtime(instance, suspend=False):
    if not is_runtime_enabled():
        instance.status = "suspended" if suspend else "stopped"
        instance.stopped_at = datetime.datetime.utcnow()
        return instance
    if instance.container_name:
        result = _run_command(["docker", "stop", instance.container_name])
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "docker stop 失败").strip()[:240])
    instance.status = "suspended" if suspend else "stopped"
    instance.stopped_at = datetime.datetime.utcnow()
    return instance


def restart_instance_runtime(instance):
    if not is_runtime_enabled():
        instance.status = "running"
        instance.stopped_at = None
        instance.started_at = datetime.datetime.utcnow()
        return instance
    if not instance.container_name or is_mock_runtime_record(instance):
        _reset_instance_runtime_state(instance)
        return provision_instance_runtime(instance)
    result = _run_command(["docker", "restart", instance.container_name])
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "docker restart 失败").strip()[:240])
    _wait_for_container_ready(instance.container_name)
    instance.status = "running"
    instance.stopped_at = None
    instance.started_at = datetime.datetime.utcnow()
    return instance


def destroy_instance_runtime(instance):
    if is_runtime_enabled() and instance.container_name:
        result = _run_command(["docker", "rm", "-f", instance.container_name])
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "docker rm 失败").strip()[:240])
    instance.status = "destroyed"
    instance.stopped_at = datetime.datetime.utcnow()
    instance.entry_url = ""
    instance.host_port = None
    return instance


def build_launch_payload(instance):
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=5)
    runtime_meta = _load_runtime_meta(instance)
    debug_launch_url = runtime_meta.get("debug_entry_url", "")
    launch_url = instance.entry_url or debug_launch_url
    if get_runtime_mode() == "docker" and instance.entry_url and instance.gateway_token:
        launch_url = _build_launch_bootstrap_url(instance)
    return {
        "mode": get_runtime_mode(),
        "launch_url": launch_url,
        "entry_url": instance.entry_url,
        "debug_launch_url": debug_launch_url,
        "gateway_token": instance.gateway_token,
        "expires_at": expires_at.isoformat(),
    }
