# GitOps Demo con ArgoCD e Kargo

Questa demo mostra un flusso GitOps completo per la gestione di deployment multi-tenant attraverso ambienti dev e qa, utilizzando **ArgoCD** per la sincronizzazione continua e **Kargo** per l'orchestrazione delle promozioni.

## Architettura

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Hub                                │
│                   andycpx/kargodemo:vX.X.X                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     KARGO (Warehouse)                            │
│              Monitora nuove immagini Docker                      │
│                    Crea "Freight" (vX.X.X)                       │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌──────────────────────┐         ┌──────────────────────┐
│   tenant-a-dev       │         │   tenant-b-dev       │
└──────────────────────┘         └──────────────────────┘
              │                               │
              ▼                               ▼
┌──────────────────────┐         ┌──────────────────────┐
│   tenant-a-qa        │         │   tenant-b-qa        │
└──────────────────────┘         └──────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         ARGOCD                                   │
│         Sincronizza Git → Kubernetes (auto-sync)                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      KUBERNETES                                  │
│    ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐ │
│    │tenant-a-dev│  │tenant-a-qa │  │tenant-b-dev│  │tenant-b-qa│ │
│    └────────────┘  └────────────┘  └────────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Componenti

| Componente | Ruolo |
|------------|-------|
| **ArgoCD** | Sincronizza lo stato Git → Kubernetes. Rileva drift e auto-corregge |
| **Kargo** | Orchestratore di promozioni. Gestisce il flusso dev → qa |
| **Warehouse** | Monitora Docker Hub per nuove immagini |
| **Freight** | "Pacchetto" che rappresenta una versione deployabile |
| **Stage** | Ambiente target (dev, qa) con regole di promozione |

## Struttura Repository

```
.
├── Dockerfile                    # Immagine dell'applicazione
├── main.py                       # Applicazione Flask
├── requirements.txt              # Dipendenze Python
└── gitops/
    ├── argocd/
    │   └── applicationset.yaml   # Genera 4 app (2 tenant × 2 env)
    ├── kargo/
    │   ├── project.yaml          # Progetto Kargo
    │   ├── warehouse.yaml        # Monitora Docker Hub
    │   ├── stages-tenant-a.yaml  # Pipeline: dev → qa
    │   └── stages-tenant-b.yaml  # Pipeline: dev → qa
    ├── base/
    │   ├── deployment.yaml       # Deployment base
    │   ├── service.yaml          # Service base
    │   ├── configmap.yaml        # ConfigMap base
    │   └── kustomization.yaml
    ├── stages/
    │   ├── dev/                  # Overlay ambiente dev
    │   │   ├── kustomization.yaml
    │   │   └── deployment-patch.yaml
    │   └── qa/                   # Overlay ambiente qa
    │       ├── kustomization.yaml
    │       └── deployment-patch.yaml
    └── tenants/
        ├── tenant-a/
        │   ├── dev/              # tenant-a dev config
        │   └── qa/               # tenant-a qa config
        └── tenant-b/
            ├── dev/              # tenant-b dev config
            └── qa/               # tenant-b qa config
```

## Prerequisiti

- Minikube (o altro cluster Kubernetes)
- kubectl
- Helm
- Docker

## Setup

### 1. Avvia Minikube

```bash
minikube start --cpus=4 --memory=8192
```

### 2. Installa ArgoCD

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl wait --for=condition=available deployment/argocd-server -n argocd --timeout=300s
```

### 3. Installa Kargo

```bash
# Genera password e signing key
ADMIN_PASSWORD="your-secure-password"
HASHED_PASS=$(htpasswd -nbBC 10 "" "$ADMIN_PASSWORD" | tr -d ':\n' | sed 's/$2y/$2a/')
SIGNING_KEY=$(openssl rand -base64 32)

# Installa con Helm
helm install kargo \
  oci://ghcr.io/akuity/kargo-charts/kargo \
  --namespace kargo \
  --create-namespace \
  --set api.adminAccount.passwordHash="$HASHED_PASS" \
  --set api.adminAccount.tokenSigningKey="$SIGNING_KEY" \
  --set controller.argocd.integrationEnabled=true \
  --set controller.argocd.namespace=argocd \
  --wait
```

### 4. Applica le configurazioni GitOps

```bash
# ArgoCD ApplicationSet
kubectl apply -f gitops/argocd/applicationset.yaml

# Kargo resources
kubectl apply -f gitops/kargo/project.yaml
kubectl apply -f gitops/kargo/warehouse.yaml
kubectl apply -f gitops/kargo/stages-tenant-a.yaml
kubectl apply -f gitops/kargo/stages-tenant-b.yaml
```

### 5. Accedi alle UI

```bash
# ArgoCD UI
kubectl port-forward svc/argocd-server -n argocd 8080:443 &

# Password ArgoCD
kubectl get secret argocd-initial-admin-secret -n argocd \
  -o jsonpath='{.data.password}' | base64 -d && echo

# Kargo UI
kubectl port-forward svc/kargo-api -n kargo 8443:443 &
```

- **ArgoCD**: https://localhost:8080 (user: `admin`)
- **Kargo**: https://localhost:8443 (user: `admin`)

## Demo: Flusso di Promozione

### 1. Verifica stato attuale

```bash
# Applicazioni ArgoCD
kubectl get applications -n argocd

# Stages Kargo
kubectl get stages -n env-service

# Freight disponibili
kubectl get freight -n env-service
```

### 2. Crea e pusha una nuova versione

```bash
# Build
docker build -t andycpx/kargodemo:v4.0.0 .

# Push
docker push andycpx/kargodemo:v4.0.0

# Forza refresh del Warehouse
kubectl annotate warehouse env-service -n env-service \
  kargo.akuity.io/refresh="$(date -u +%Y-%m-%dT%H:%M:%SZ)" --overwrite

# Verifica nuovo freight
kubectl get freight -n env-service
```

### 3. Promuovi via Kargo UI

1. Apri Kargo UI (https://localhost:8443)
2. Seleziona progetto `env-service`
3. Visualizza il nuovo freight (v4.0.0)
4. Clicca "Promote" su `tenant-a-dev`
5. Osserva:
   - Kargo aggiorna `gitops/stages/dev/kustomization.yaml`
   - Committa e pusha su Git
   - ArgoCD rileva il cambiamento e sincronizza
   - Il pod viene aggiornato

### 4. Promuovi a QA

1. Dopo verifica su dev, promuovi a `tenant-a-qa`
2. Stesso flusso: Git commit → ArgoCD sync → Pod update

### 5. Verifica l'applicazione

```bash
# Port-forward al servizio
kubectl port-forward svc/env-service -n tenant-a-dev 9000:80 &

# Test
curl http://localhost:9000
# Output: {"stage": "dev", "tenant": "tenant-a"}
```

## Pipeline di Promozione

```
┌─────────────┐     ┌─────────────┐
│  Warehouse  │────▶│   dev       │────▶  (promozione manuale)
│  (v4.0.0)   │     │  verified   │
└─────────────┘     └─────────────┘
                          │
                          ▼
                    ┌─────────────┐
                    │   qa        │
                    │  verified   │
                    └─────────────┘
```

**Flusso Kargo per ogni promozione:**
1. `git-clone` - Clona il repository
2. `kustomize-set-image` - Aggiorna il tag dell'immagine
3. `git-commit` - Committa le modifiche
4. `git-push` - Pusha su Git
5. `argocd-update` - Triggera sync ArgoCD

## Comandi Utili

```bash
# Stato completo
kubectl get applications -n argocd
kubectl get stages,freight -n env-service

# Logs ArgoCD
kubectl logs -n argocd deployment/argocd-server

# Logs Kargo
kubectl logs -n kargo deployment/kargo-controller

# Pod per namespace
kubectl get pods -n tenant-a-dev
kubectl get pods -n tenant-a-qa
kubectl get pods -n tenant-b-dev
kubectl get pods -n tenant-b-qa

# Refresh manuale Warehouse
kubectl annotate warehouse env-service -n env-service \
  kargo.akuity.io/refresh="$(date -u +%Y-%m-%dT%H:%M:%SZ)" --overwrite

# Sync manuale ArgoCD
kubectl patch application <app-name> -n argocd --type merge \
  -p '{"operation":{"sync":{}}}'
```

## Vantaggi GitOps

| Approccio Tradizionale | GitOps |
|------------------------|--------|
| Script imperativi | Configurazione dichiarativa |
| "Chi ha fatto cosa?" | Audit trail completo in Git |
| Rollback manuale | `git revert` + auto-sync |
| Accesso diretto al cluster | Solo ArgoCD accede al cluster |
| Promozioni manuali | Pipeline controllate con Kargo |

## Troubleshooting

### ArgoCD Application OutOfSync
```bash
# Forza sync
kubectl patch application <app-name> -n argocd --type merge \
  -p '{"operation":{"sync":{}}}'
```

### Kargo Promotion fallisce
```bash
# Verifica logs
kubectl logs -n kargo deployment/kargo-controller | grep -i error

# Verifica annotazioni ArgoCD
kubectl get application <app-name> -n argocd \
  -o jsonpath='{.metadata.annotations}'
```

### Warehouse non rileva nuove immagini
```bash
# Forza refresh
kubectl annotate warehouse env-service -n env-service \
  kargo.akuity.io/refresh="$(date -u +%Y-%m-%dT%H:%M:%SZ)" --overwrite

# Verifica stato
kubectl describe warehouse env-service -n env-service
```

## Risorse

- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [Kargo Documentation](https://docs.kargo.io/)
- [Kustomize Documentation](https://kustomize.io/)
