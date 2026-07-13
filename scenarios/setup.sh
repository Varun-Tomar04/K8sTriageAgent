#!/usr/bin/env bash
# Deploy all broken scenarios to minikube for k8s-triage-agent demo.
# Run this from the repo root: bash scenarios/setup.sh

set -euo pipefail

NAMESPACE="triage-demo"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Checking minikube..."
if ! minikube status --format='{{.Host}}' 2>/dev/null | grep -q "Running"; then
  echo "    minikube not running — starting with docker driver..."
  minikube start --driver=docker
else
  echo "    minikube is running."
fi

echo ""
echo "==> Enabling metrics-server addon (needed for kubectl top)..."
minikube addons enable metrics-server 2>/dev/null || true

echo ""
echo "==> Creating namespace '${NAMESPACE}'..."
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

echo ""
echo "==> Deploying scenarios..."
for f in "${SCRIPT_DIR}"/0*.yaml; do
  scenario=$(basename "$f")
  echo "    Applying ${scenario}..."
  kubectl apply -f "$f" -n "${NAMESPACE}"
done

echo ""
echo "==> Waiting a few seconds for pods to reach their failure states..."
sleep 10

echo ""
echo "==> Current state of triage-demo namespace:"
kubectl get pods -n "${NAMESPACE}" -o wide

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Scenarios deployed! Run the agent:"
echo ""
echo "  # Diagnose the whole namespace (agent picks unhealthy pods):"
echo "  python agent.py diagnose --namespace triage-demo"
echo ""
echo "  # Diagnose a specific scenario:"
echo "  python agent.py diagnose --pod crashloop-demo --namespace triage-demo"
echo "  python agent.py diagnose --pod imagepull-fail --namespace triage-demo"
echo "  python agent.py diagnose --pod oom-victim --namespace triage-demo"
echo ""
echo "  # Use Claude instead of Gemini:"
echo "  python agent.py diagnose --namespace triage-demo --llm-provider claude"
echo ""
echo "  # Get structured JSON output:"
echo "  python agent.py diagnose --namespace triage-demo --json"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
