# Isolation Verification Agent

A `custom-api` AMP agent deployed to verify that AMP's workload isolation
guarantees hold for a running agent, on the author's own local AMP
quick-start install. Every check is read-only and reports reachability or
permission level only -- it never returns secret values.

Call `GET /verify` after deployment to run all checks:

1. Filesystem permissions -- process user ID, whether the root filesystem is
   writable, whether a container-runtime socket is present, whether host
   process info is visible.
2. Kubernetes API reachability via the pod's own mounted service-account
   token, and what that token is authorized to do.
3. Whether any files or environment variables not belonging to this agent
   are visible from within it.
4. Direct pod-to-pod network reachability to internal services (database,
   secret store, Kubernetes API, a metadata-style address) -- this checks
   the network layer directly, separate from the control plane's own
   outbound-request guard.
5. What the platform-injected agent identity credential is authorized to do
   against the real AMP API.

A resource-limit check and a build-parameter containment check were
considered but are handled separately/manually rather than as endpoints
here, to avoid any risk to a shared cluster.
