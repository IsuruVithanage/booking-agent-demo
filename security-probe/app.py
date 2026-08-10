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


def probe_injected_identity_scope() -> dict[str, Any]:
    candidate_names = [
        k for k in os.environ if any(t in k.upper() for t in ("TOKEN", "IDENTITY", "API_KEY"))
    ]
    result: dict[str, Any] = {"candidate_identity_env_vars": candidate_names}

    api_base = os.environ.get("AMP_API_URL", "http://api.amp.localhost:8080")
    checks: dict[str, Any] = {}
    for var in candidate_names:
        token = os.environ.get(var, "")
        if not token:
            continue
        headers = {"Authorization": f"Bearer {token}"}
        for label, path in [
            ("own_project_list", "/api/v1/orgs/default/projects"),
            ("org_list", "/api/v1/orgs"),
        ]:
            try:
                r = requests.get(f"{api_base}{path}", headers=headers, timeout=3)
                checks[f"{var}:{label}"] = r.status_code
            except Exception as e:
                checks[f"{var}:{label}"] = f"error: {e}"
    result["api_checks"] = checks

    return result


@app.get("/verify")
def run_checks() -> dict[str, Any]:
    return {
        "1_filesystem_permissions": probe_container_host_escape(),
        "2_k8s_api_via_service_account": probe_k8s_api_via_service_account(),
        "3_cross_agent_visibility": probe_cross_agent_secret_reachability(),
        "4_internal_network_reachability": probe_internal_network_reachability(),
        "5_injected_identity_scope": probe_injected_identity_scope(),
    }


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "checks_endpoint": "/verify"}
