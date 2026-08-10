"""Security probe agent.

Self-tests AMP's isolation boundaries from inside its own deployed pod. Every
probe reports what it observed -- none attempt to exploit, persist, or
exfiltrate data beyond confirming reachability/permission level. One probe
answers one question about one specific isolation boundary.

This is intentionally a *read-only* diagnostic tool, not an attack script:
- No secret *values* are ever returned, only names/counts/reachability.
- No writes outside a single self-cleaning test file.
- No attempts to modify, delete, or exfiltrate anything belonging to another
  tenant/agent -- only to observe whether it *would have been reachable*.
"""

from __future__ import annotations

import os
import shutil
import socket
from pathlib import Path
from typing import Any

import requests
from fastapi import FastAPI

app = FastAPI(title="Security Probe Agent")

SA_DIR = Path("/var/run/secrets/kubernetes.io/serviceaccount")

KNOWN_RUNTIME_SOCKETS = [
    "/var/run/docker.sock",
    "/run/containerd/containerd.sock",
    "/var/run/containerd/containerd.sock",
    "/var/run/crio/crio.sock",
]

NETWORK_TARGETS = {
    "k8s-api": ("kubernetes.default.svc", 443),
    "cloud-metadata-style-ip": ("169.254.169.254", 80),
    "postgres-guess-1": ("amp-postgresql", 5432),
    "postgres-guess-2": ("postgresql", 5432),
    "secret-manager-guess": ("secretmanagersvc", 8080),
}


def probe_container_host_escape() -> dict[str, Any]:
    result: dict[str, Any] = {"uid": os.getuid(), "running_as_root": os.getuid() == 0}

    test_path = Path("/.probe_write_test")
    try:
        test_path.write_text("probe")
        test_path.unlink()
        result["root_fs_writable"] = True
    except Exception as e:
        result["root_fs_writable"] = False
        result["root_fs_write_error"] = str(e)

    result["runtime_sockets_present"] = [p for p in KNOWN_RUNTIME_SOCKETS if os.path.exists(p)]

    try:
        result["proc1_status_readable"] = os.access("/proc/1/status", os.R_OK)
    except Exception:
        result["proc1_status_readable"] = False

    try:
        total, _used, _free = shutil.disk_usage("/")
        result["root_fs_size_gb"] = round(total / 1e9, 1)
    except Exception:
        result["root_fs_size_gb"] = None

    return result


def probe_k8s_api_via_service_account() -> dict[str, Any]:
    result: dict[str, Any] = {"service_account_mounted": SA_DIR.exists()}
    if not SA_DIR.exists():
        return result

    try:
        token = (SA_DIR / "token").read_text().strip()
        namespace = (SA_DIR / "namespace").read_text().strip()
        ca_path = str(SA_DIR / "ca.crt")
        result["own_namespace"] = namespace

        headers = {"Authorization": f"Bearer {token}"}
        base = "https://kubernetes.default.svc"
        checks = {
            "list_pods_own_namespace": f"{base}/api/v1/namespaces/{namespace}/pods",
            "list_secrets_own_namespace": f"{base}/api/v1/namespaces/{namespace}/secrets",
            "list_secrets_all_namespaces": f"{base}/api/v1/secrets",
            "list_all_namespaces": f"{base}/api/v1/namespaces",
        }
        result["api_checks"] = {}
        for name, url in checks.items():
            try:
                r = requests.get(url, headers=headers, verify=ca_path, timeout=3)
                item_count = None
                if r.status_code == 200:
                    try:
                        item_count = len(r.json().get("items", []))
                    except Exception:
                        item_count = None
                result["api_checks"][name] = {"status": r.status_code, "item_count": item_count}
            except Exception as e:
                result["api_checks"][name] = {"error": str(e)}
    except Exception as e:
        result["error"] = str(e)

    return result


def probe_cross_agent_secret_reachability() -> dict[str, Any]:
    result: dict[str, Any] = {"env_var_names": sorted(os.environ.keys())}

    found: dict[str, Any] = {}
    for d in ["/var/run/secrets", "/etc/secrets", "/mnt/secrets"]:
        p = Path(d)
        if p.exists():
            try:
                found[d] = [str(x) for x in p.rglob("*") if x.is_file()]
            except Exception as e:
                found[d] = f"error: {e}"
    result["secret_files_found"] = found

    return result


def probe_internal_network_reachability() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, (host, port) in NETWORK_TARGETS.items():
        try:
            with socket.create_connection((host, port), timeout=2):
                result[name] = {"host": host, "port": port, "reachable": True}
        except Exception as e:
            result[name] = {"host": host, "port": port, "reachable": False, "error": str(e)}
    return result


def probe_sibling_service_reachability() -> dict[str, Any]:
    """Kubernetes injects <NAME>_SERVICE_HOST/_PORT env vars for every Service
    in the same namespace into every pod by default. That's an information
    disclosure on its own (see probe 3) -- this probe checks whether it's
    also a *reachability* finding by actually attempting a connection.
    """
    skip_prefixes = ("KUBERNETES", "ISOLATION_CHECK")
    siblings: dict[str, dict[str, str]] = {}
    for key, value in os.environ.items():
        if key.endswith("_SERVICE_HOST") and not key.startswith(skip_prefixes):
            name = key[: -len("_SERVICE_HOST")]
            siblings.setdefault(name, {})["host"] = value
        elif key.endswith("_SERVICE_PORT") and not key.startswith(skip_prefixes):
            name = key[: -len("_SERVICE_PORT")]
            siblings.setdefault(name, {})["port"] = value

    result: dict[str, Any] = {}
    for name, addr in siblings.items():
        host = addr.get("host")
        port_raw = addr.get("port")
        if not host or not port_raw:
            result[name] = {"error": "incomplete env vars", "addr": addr}
            continue
        try:
            port = int(port_raw)
        except ValueError:
            result[name] = {"error": f"non-numeric port: {port_raw}"}
            continue

        entry: dict[str, Any] = {"host": host, "port": port}
        try:
            with socket.create_connection((host, port), timeout=2):
                entry["tcp_reachable"] = True
        except Exception as e:
            entry["tcp_reachable"] = False
            entry["tcp_error"] = str(e)

        if entry.get("tcp_reachable"):
            try:
                r = requests.get(f"http://{host}:{port}/", timeout=2)
                entry["http_status"] = r.status_code
                entry["http_content_length"] = len(r.content)
            except Exception as e:
                entry["http_error"] = str(e)

        result[name] = entry

    return result


API_CHECK_PATHS = {
    "own_project_list": "/api/v1/orgs/default/projects",
    "org_list": "/api/v1/orgs",
}

# The internal AMP control-plane API address, reached via the api-platform
# gateway -- the only address the SandboxTemplate egress NetworkPolicy
# permits for AMP API traffic (port 22893, namespaces labeled
# amp.wso2.com/api-platform-gateway=true). api.amp.localhost:8080 only
# resolves on a developer's own machine, never from inside a pod.
INTERNAL_API_GATEWAY_HOST = (
    "api-platform-default-default-gateway-gateway-runtime.default-default.svc.cluster.local:22893"
)


def _get_with_scheme_fallback(path: str, **kwargs: Any) -> tuple[str, Any]:
    """Try http first, then https, distinguishing a connection-level failure
    (wrong scheme/address) from an application-level response (right address,
    auth rejected or accepted)."""
    last_exc: Exception | None = None
    for scheme in ("http", "https"):
        url = f"{scheme}://{INTERNAL_API_GATEWAY_HOST}{path}"
        try:
            return url, requests.get(url, timeout=3, **kwargs)
        except Exception as e:
            last_exc = e
            continue
    raise last_exc  # type: ignore[misc]


def probe_injected_identity_scope() -> dict[str, Any]:
    result: dict[str, Any] = {}

    # --- Step A: real OAuth2 client-credentials exchange -----------------
    client_id = os.environ.get("AMP_AGENTID_CLIENT_ID", "")
    client_secret = os.environ.get("AMP_AGENTID_CLIENT_SECRET", "")
    token_endpoint = os.environ.get("AMP_AGENTID_TOKEN_ENDPOINT", "")
    scopes = os.environ.get("AMP_AGENTID_SCOPES", "")

    oauth_exchange: dict[str, Any] = {
        "attempted": bool(client_id and client_secret and token_endpoint)
    }
    access_token: str | None = None
    if oauth_exchange["attempted"]:
        try:
            form = {"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret}
            if scopes:
                form["scope"] = scopes
            r = requests.post(token_endpoint, data=form, timeout=3)
            oauth_exchange["status"] = r.status_code
            if r.status_code == 200:
                body = r.json()
                access_token = body.get("access_token")
                oauth_exchange["success"] = access_token is not None
                oauth_exchange["granted_scope"] = body.get("scope")
            else:
                oauth_exchange["success"] = False
        except Exception as e:
            oauth_exchange["success"] = False
            oauth_exchange["error"] = str(e)
    result["oauth_exchange"] = oauth_exchange

    # --- Step B: use the real token against the internal control-plane API
    oauth_api_checks: dict[str, Any] = {}
    if access_token:
        headers = {"Authorization": f"Bearer {access_token}"}
        for label, path in API_CHECK_PATHS.items():
            try:
                url, r = _get_with_scheme_fallback(path, headers=headers)
                oauth_api_checks[label] = {"url_scheme": url.split(":")[0], "status": r.status_code}
            except Exception as e:
                oauth_api_checks[label] = {"error": str(e)}
    result["oauth_token_api_checks"] = oauth_api_checks

    # --- Step C: AMP_AGENT_API_KEY tested on its own terms (X-API-Key) ---
    agent_api_key = os.environ.get("AMP_AGENT_API_KEY", "")
    agent_api_key_checks: dict[str, Any] = {}
    if agent_api_key:
        headers = {"X-API-Key": agent_api_key}
        for label, path in API_CHECK_PATHS.items():
            try:
                url, r = _get_with_scheme_fallback(path, headers=headers)
                agent_api_key_checks[label] = {"url_scheme": url.split(":")[0], "status": r.status_code}
            except Exception as e:
                agent_api_key_checks[label] = {"error": str(e)}
    result["agent_api_key_checks"] = agent_api_key_checks

    return result


@app.get("/verify")
def run_checks() -> dict[str, Any]:
    return {
        "1_filesystem_permissions": probe_container_host_escape(),
        "2_k8s_api_via_service_account": probe_k8s_api_via_service_account(),
        "3_cross_agent_visibility": probe_cross_agent_secret_reachability(),
        "4_internal_network_reachability": probe_internal_network_reachability(),
        "5_injected_identity_scope": probe_injected_identity_scope(),
        "6_sibling_service_reachability": probe_sibling_service_reachability(),
    }


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "checks_endpoint": "/verify"}
