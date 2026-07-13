# Demo Scenarios

Eight intentionally broken Kubernetes workloads that exercise different failure modes.

## Quick start

```bash
bash scenarios/setup.sh
```

This starts minikube (if not running), creates the `triage-demo` namespace, and applies all scenarios.

## Scenario index

| # | Pod/Resource | Failure Mode | What breaks |
|---|-------------|-------------|-------------|
| 01 | `imagepull-fail` | `ImagePullBackOff` | Non-existent image tag |
| 02 | `oom-victim` | `OOMKilled` (exit 137) | Memory limit 10Mi, stress needs 50Mi |
| 03 | `missing-config` | `CreateContainerConfigError` | References ConfigMap that doesn't exist |
| 04 | `liveness-looper` | Restart loop | Liveness probe hits `/healthz` on nginx (404) |
| 05 | `crashloop-demo` | `CrashLoopBackOff` | Container always exits 1 |
| 06 | `resource-hog` | `Pending` / Unschedulable | Requests 1000 CPU cores |
| 07 | `backend-svc` | Service has no endpoints | Selector `app=backend` doesn't match pod label `app=backend-v2` |
| 08 | `stuck-rollout` | Deployment rollout stuck | Rolling update with bad image, `maxUnavailable: 0` |

## Teardown

```bash
kubectl delete namespace triage-demo
```
