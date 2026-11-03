# AKS deployment

CPU-only, one replica per component. **AKS control-plane and node costs dominate LLM/search costs** — do not leave a cluster idle without a budget alert.

## Prerequisites

- Azure CLI, `kubectl`, Helm 3
- Container images pushed to a registry you control
- Secrets: Azure OpenAI, Tavily (LangSmith optional)

## Build and push

```bash
docker build -f docker/Dockerfile.backend -t "$REGISTRY/engknowledge-backend:0.1.0" .
docker build -f docker/Dockerfile.frontend -t "$REGISTRY/engknowledge-frontend:0.1.0" .
docker push "$REGISTRY/engknowledge-backend:0.1.0"
docker push "$REGISTRY/engknowledge-frontend:0.1.0"
```

## Install

```bash
helm upgrade --install eka deploy/helm/engineering-knowledge-assistant \
  --set image.backendRepository="$REGISTRY/engknowledge-backend" \
  --set image.frontendRepository="$REGISTRY/engknowledge-frontend" \
  --set image.tag=0.1.0 \
  --set secrets.azureOpenAIApiKey="$AZURE_OPENAI_API_KEY" \
  --set secrets.azureOpenAIEndpoint="$AZURE_OPENAI_ENDPOINT" \
  --set secrets.tavilyApiKey="$TAVILY_API_KEY" \
  --set ingress.enabled=true \
  --set ingress.host=eka.example.com
```

## Smoke test

```bash
kubectl rollout status deploy/engineering-knowledge-assistant-backend
curl -sS "https://eka.example.com/health"
curl -sS -X POST "https://eka.example.com/api/ask" \
  -H 'content-type: application/json' \
  -d '{"question":"What timeout thresholds are specified in the sample architecture?","retrieval_mode":"local"}'
```

## Cost controls

1. Create an Azure budget + alert on the subscription/resource group.
2. Use a small node pool (e.g. one `Standard_B2s`) and stop/deallocate when idle.
3. Prefer local Docker Compose for demos that do not need AKS.
4. Teardown: `helm uninstall eka` then delete the cluster / node pool.

## Stop / start

```bash
# stop compute
az aks stop --resource-group "$RG" --name "$CLUSTER"
# start later
az aks start --resource-group "$RG" --name "$CLUSTER"
```
