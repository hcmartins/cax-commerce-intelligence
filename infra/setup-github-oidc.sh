#!/usr/bin/env bash
# One-time setup: lets .github/workflows/ci-cd.yml authenticate to Azure via
# OIDC (azure/login) — no client secret stored anywhere, GitHub and Azure AD
# trust each other's tokens directly for this one app registration.
#
# rg-commerce-dev is a SHARED resource group (commerce-operations-api and its
# own infra live in it too), so this deliberately grants the narrowest scope
# that works — four grants, none of them "Contributor" on the resource group:
#   - Reader on the resource group (Bicep `existing` lookups, `az deployment
#     group show`)
#   - AcrPush on the shared registry (push-only; ACR has no per-repository
#     scoping to narrow further)
#   - Container Apps Contributor scoped to just this app's own Container App
#     (not the whole environment or any other service's)
#   - a custom "Commerce Intelligence Deployment Submitter" role, because
#     none of the above actually covers submitting an ARM/Bicep deployment:
#     `Microsoft.Resources/deployments/write` is a distinct permission
#     surface from the resource writes inside it, and deploying
#     infra/app.bicep specifically also needs
#     `Microsoft.App/managedEnvironments/join/action` (attaching the
#     Container App to the shared environment) and
#     `Microsoft.ManagedIdentity/userAssignedIdentities/assign/action`
#     (attaching this app's own identity to it) — both "linked
#     authorization" checks Azure evaluates on the *referenced* resource,
#     not the one being written. Every one of these was found the hard way,
#     by actually running a deployment and reading what AuthorizationFailed/
#     LinkedAuthorizationFailed said was missing — this identity can still
#     never touch commerce-operations-api, the shared Postgres server, Key
#     Vault, or storage account.
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

echo "=== Custom role: deployment submission + linked-resource actions ==="
CUSTOM_ROLE_NAME="Commerce Intelligence Deployment Submitter"
ROLE_DEF_FILE=$(mktemp)
cat > "$ROLE_DEF_FILE" <<EOF
{
  "Name": "$CUSTOM_ROLE_NAME",
  "Description": "Lets a CI/CD identity submit ARM/Bicep deployments in this resource group, join the shared Container Apps environment, and assign this app's managed identity to its own Container App; actual resource writes are still governed by that identity's other, resource-scoped role assignments.",
  "Actions": [
    "Microsoft.Resources/deployments/write",
    "Microsoft.Resources/deployments/read",
    "Microsoft.Resources/deployments/delete",
    "Microsoft.Resources/deployments/validate/action",
    "Microsoft.Resources/deployments/operations/read",
    "Microsoft.Resources/deployments/exportTemplate/action",
    "Microsoft.App/managedEnvironments/join/action",
    "Microsoft.ManagedIdentity/userAssignedIdentities/assign/action"
  ],
  "NotActions": [],
  "AssignableScopes": ["$RG_ID"]
}
EOF
# On Git Bash, az.cmd is a native Windows program — it can't resolve a plain
# MSYS-style /tmp/... path (and MSYS_NO_PATHCONV above deliberately stops
# bash from auto-translating it). cygpath -w gives it the real Windows path
# instead; a no-op elsewhere, where the plain path already works.
if command -v cygpath >/dev/null; then
  ROLE_DEF_FILE_ARG=$(cygpath -w "$ROLE_DEF_FILE")
else
  ROLE_DEF_FILE_ARG="$ROLE_DEF_FILE"
fi

EXISTING_ROLE_ID=$(az role definition list --custom-role-only true --query "[?roleName=='$CUSTOM_ROLE_NAME'].id | [0]" -o tsv)
if [ -z "$EXISTING_ROLE_ID" ]; then
  ROLE_DEF_ID=$(az role definition create --role-definition "$ROLE_DEF_FILE_ARG" --query id -o tsv)
  echo "  created role definition"
else
  az role definition update --role-definition "$ROLE_DEF_FILE_ARG" >/dev/null
  ROLE_DEF_ID="$EXISTING_ROLE_ID"
  echo "  updated existing role definition"
fi
rm -f "$ROLE_DEF_FILE"
assign_role "$ROLE_DEF_ID" "$RG_ID"

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
