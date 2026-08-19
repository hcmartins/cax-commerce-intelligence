// Commerce Intelligence — deploys this repo's own Container App into the
// shared "commerce-platform" infrastructure that already exists in
// rg-commerce-dev (ACR, Key Vault, Postgres, the Container Apps environment,
// and this app's own managed identity — all provisioned and RBAC'd outside
// this repo, by whatever stood up the platform). This template only ever
// touches its own commerce-intelligence-api Container App; every other
// resource is referenced `existing`, never created or modified — this repo
// has no business owning shared infrastructure another service
// (commerce-operations-api, sitting in the same resource group) also
// depends on.
//
// Deploy:
//   az deployment group create -g rg-commerce-dev -f infra/app.bicep \
//     -p infra/app.parameters.dev.json imageTag=<tag>

@description('Azure region — must match the region the shared infrastructure runs in.')
param location string = resourceGroup().location

@description('Container image tag to deploy. Build and push it to the shared ACR first (see README.md).')
param imageTag string = 'latest'

@description('Container App min replicas. 1 avoids cold starts on health checks/demos; 0 saves more but adds latency on the first request after idle.')
param minReplicas int = 1

@description('Container App max replicas.')
param maxReplicas int = 3

@description('This Container App name — must already exist (the platform provisions it with a placeholder image; this template updates it in place, never creates it fresh).')
param containerAppName string = 'commerce-intelligence-api'

@description('Shared Container Apps environment name.')
param containerAppEnvName string = 'cae-commerce-dev'

@description('Shared Container Registry name.')
param acrName string = 'acrcommercedevzqbs3z'

@description('Shared Key Vault name.')
param keyVaultName string = 'kv-commerce-dev-zqbs3z'

@description('Key Vault secret holding this app DATABASE_URL — namespaced per-service since the Key Vault is shared (commerce-operations-api has its own alongside it).')
param databaseUrlSecretName string = 'commerce-intelligence-database-url'

@description('User-assigned managed identity name for this app — must already exist, with AcrPull + Key Vault Secrets User already granted by the platform.')
param identityName string = 'id-commerce-intelligence-api'

@description('Tags — matches what the platform already applies to this Container App, so this deployment does not drift them.')
param tags object = {
  application: 'commerce-platform'
  environment: 'dev'
  'managed-by': 'bicep'
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: acrName
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource databaseUrlSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' existing = {
  parent: keyVault
  name: databaseUrlSecretName
}

resource containerAppEnv 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: containerAppEnvName
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: identityName
}

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: acr.properties.loginServer
          identity: identity.id
        }
      ]
      secrets: [
        {
          name: 'database-url'
          keyVaultUrl: databaseUrlSecret.properties.secretUri
          identity: identity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: '${acr.properties.loginServer}/commerce-intelligence-api:${imageTag}'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'LOG_JSON', value: 'true' }
            { name: 'LOG_LEVEL', value: 'INFO' }
            { name: 'APP_ENV', value: 'dev-azure' }
            { name: 'AI_PROVIDER', value: 'mock' }
            { name: 'SEARCH_PROVIDER', value: 'mock' }
            { name: 'SUPPLIER_PROVIDER', value: 'mock' }
            { name: 'MARKETPLACE_PROVIDER', value: 'mock' }
            { name: 'WEB_CONCURRENCY', value: '1' }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 10
              periodSeconds: 15
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/ready'
                port: 8000
              }
              initialDelaySeconds: 10
              periodSeconds: 10
              failureThreshold: 3
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
}

output containerAppName string = containerApp.name
output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn
