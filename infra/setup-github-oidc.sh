#!/usr/bin/env bash
# One-time setup: lets .github/workflows/ci-cd.yml authenticate to Azure via
# OIDC (azure/login) — no client secret stored anywhere, GitHub and Azure AD
# trust each other's tokens directly for this one app registration.
#
# rg-commerce-dev is a SHARED resource group (commerce-operations-api and its
# own infra live in it too), so this deliberately grants the narrowest scope
# that works: Reader on the resource group (needed for Bicep `existing`
# lookups and `az deployment group show`), Container Apps Contributor scoped
# to just this app's own Container App (not the whole environment or any
# other service's), and AcrPush on the shared registry (push-only, and the
# registry has no per-repository scoping to narrow further). This identity
# can never touch commerce-operations-api, the shared Postgres server, Key
# Vault, or storage account.
#
# Run once per repo, after the GitHub repository exists (the federated
# credentials below are scoped to its exact owner/name — plus their stable
# numeric IDs, which GitHub's OIDC subject claim now includes alongside the
# current slug, e.g. "repo:owner@12345/repo@67890:ref:...", not just
# "repo:owner/repo:ref:..."; requires `gh` authenticated to look those IDs
# up, since the wrong subject is the most common cause of a federated-login
# failure and there's no way to derive them from the slug alone).
#
# Usage:
#   GITHUB_OWNER=<org-or-user> GITHUB_REPO=<repo-name> \
#   RESOURCE_GROUP=rg-commerce-dev ACR_NAME=acrcommercedevzqbs3z \
#   CONTAINER_APP_NAME=commerce-intelligence-api \
#   ./infra/setup-github-oidc.sh

set -euo pipefail

# On Git Bash for Windows, MSYS auto-converts leading-slash arguments (like
# Azure resource IDs — "/subscriptions/...") into Windows paths before az.cmd
# ever sees them, silently corrupting every --scope value below and making
# `az role assignment create` fail with a confusing "MissingSubscription"
# error. Harmless no-op on Linux/macOS bash and real MSYS builds of bash.
export MSYS_NO_PATHCONV=1

: "${GITHUB_OWNER:?Set GITHUB_OWNER (the GitHub org or user that owns the repo)}"
: "${GITHUB_REPO:?Set GITHUB_REPO (repo name only, no owner prefix)}"
: "${RESOURCE_GROUP:?Set RESOURCE_GROUP (e.g. rg-commerce-dev)}"
: "${ACR_NAME:?Set ACR_NAME (e.g. acrcommercedevzqbs3z)}"
CONTAINER_APP_NAME="${CONTAINER_APP_NAME:-commerce-intelligence-api}"

command -v gh >/dev/null || { echo "gh CLI is required (used to look up the repo's stable numeric IDs for the OIDC subject) — install it and run 'gh auth login' first." >&2; exit 1; }

APP_NAME="commerce-intelligence-github-actions"
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)

echo "=== Resolving GitHub owner/repo IDs ==="
GH_IDS=$(gh api "repos/${GITHUB_OWNER}/${GITHUB_REPO}" --jq '"\(.owner.id) \(.id)"')
GITHUB_OWNER_ID=$(echo "$GH_IDS" | cut -d' ' -f1)
GITHUB_REPO_ID=$(echo "$GH_IDS" | cut -d' ' -f2)
OIDC_OWNER="${GITHUB_OWNER}@${GITHUB_OWNER_ID}"
OIDC_REPO="${GITHUB_REPO}@${GITHUB_REPO_ID}"
echo "  ${GITHUB_OWNER}/${GITHUB_REPO} -> ${OIDC_OWNER}/${OIDC_REPO}"

echo "=== App registration ==="
APP_ID=$(az ad app list --display-name "$APP_NAME" --query "[0].appId" -o tsv)
if [ -z "$APP_ID" ]; then
  APP_ID=$(az ad app create --display-name "$APP_NAME" --query appId -o tsv)
  az ad sp create --id "$APP_ID" >/dev/null
  echo "Created app $APP_ID"
else
  echo "Reusing existing app $APP_ID"
fi

# Three federated credentials, matching the three distinct OIDC subject
# claims the workflow's jobs present: the build-and-push job (no
# `environment:`, so its subject is the branch ref) and the two deploy jobs
# (each declares `environment:`, which changes the subject to that
# environment's name instead of the branch ref) — getting a subject wrong
# here is the most common cause of "no matching federated identity record".
echo "=== Federated credentials ==="
# Checks the *subject* of an existing same-named credential, not just its
# presence — a name match with a stale subject (e.g. from before GitHub
# started including owner/repo IDs in the claim) is exactly as broken as no
# credential at all, and silently treating it as "done" is what caused a
# real login failure here. Delete-and-recreate rather than update in place,
# since federated credentials have no update-subject operation.
create_fic() {
  local name=$1 subject=$2
  local existing
  existing=$(az ad app federated-credential list --id "$APP_ID" --query "[?name=='$name'].{id:id, subject:subject}" -o json)
  local existing_subject
  existing_subject=$(echo "$existing" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['subject'] if d else '')" 2>/dev/null || echo "")

  if [ "$existing_subject" = "$subject" ]; then
    echo "  $name already correct"
    return
  fi

  if [ -n "$existing_subject" ]; then
    local existing_id
    existing_id=$(echo "$existing" | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['id'])")
    echo "  $name exists with a stale subject ($existing_subject) — recreating"
    az ad app federated-credential delete --id "$APP_ID" --federated-credential-id "$existing_id" >/dev/null
  fi

  az ad app federated-credential create --id "$APP_ID" --parameters "{
    \"name\": \"$name\",
    \"issuer\": \"https://token.actions.githubusercontent.com\",
    \"subject\": \"$subject\",
    \"audiences\": [\"api://AzureADTokenExchange\"]
  }" >/dev/null
  echo "  created $name ($subject)"
}
create_fic "main-branch"        "repo:${OIDC_OWNER}/${OIDC_REPO}:ref:refs/heads/main"
create_fic "dev-environment"    "repo:${OIDC_OWNER}/${OIDC_REPO}:environment:dev"
create_fic "prod-environment"   "repo:${OIDC_OWNER}/${OIDC_REPO}:environment:production"

echo "=== RBAC (scoped to this app only — rg-commerce-dev is shared) ==="
# --assignee-object-id + --assignee-principal-type (not --assignee <appId>) —
# the appId form routes through a Graph lookup that has proven unreliable
# from some shells/environments; resolving the SP's object id ourselves and
# passing it directly avoids that entirely.
SP_OBJECT_ID=$(az ad sp show --id "$APP_ID" --query id -o tsv)
RG_ID="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}"
ACR_ID=$(az acr show -g "$RESOURCE_GROUP" -n "$ACR_NAME" --query id -o tsv)
CONTAINER_APP_ID=$(az containerapp show -g "$RESOURCE_GROUP" -n "$CONTAINER_APP_NAME" --query id -o tsv)

# A real failure must surface, not just get swallowed as "must already
# exist" — only the specific RoleAssignmentExists condition is actually
# benign here.
assign_role() {
  local role=$1 scope=$2
  local output
  if output=$(az role assignment create --role "$role" --assignee-object-id "$SP_OBJECT_ID" --assignee-principal-type ServicePrincipal --scope "$scope" 2>&1); then
    echo "  granted $role"
  elif echo "$output" | grep -q "RoleAssignmentExists"; then
    echo "  $role already assigned"
  else
    echo "  FAILED to grant $role:" >&2
    echo "$output" >&2
    exit 1
  fi
}
assign_role "Reader" "$RG_ID"
assign_role "AcrPush" "$ACR_ID"
assign_role "Container Apps Contributor" "$CONTAINER_APP_ID"

ACR_LOGIN_SERVER=$(az acr show -g "$RESOURCE_GROUP" -n "$ACR_NAME" --query loginServer -o tsv)

cat <<EOF

=== Done. Now configure the GitHub repo ===

Settings -> Secrets and variables -> Actions -> Secrets:
  AZURE_CLIENT_ID        $APP_ID
  AZURE_TENANT_ID        $TENANT_ID
  AZURE_SUBSCRIPTION_ID  $SUBSCRIPTION_ID

Settings -> Secrets and variables -> Actions -> Variables:
  ACR_NAME               $ACR_NAME
  ACR_LOGIN_SERVER       $ACR_LOGIN_SERVER
  AZURE_RESOURCE_GROUP   $RESOURCE_GROUP

Settings -> Environments:
  "dev"          — no protection rules needed (auto-deploys on merge to main)
  "production"   — add required reviewers here; this is what turns
                   deploy-prod into a manual-approval gate. Leave
                   PROD_AZURE_RESOURCE_GROUP unset as a variable until PROD
                   infrastructure actually exists — deploy-prod skips
                   cleanly without it.
EOF
