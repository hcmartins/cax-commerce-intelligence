// Commerce Intelligence — the Container App itself. Deploy infra/base.bicep
// first (once; re-run only when infra changes); deploy this one every time a
// new image is pushed. See infra/base.bicep for why these are split.
//
// Deploy:
//   az deployment group create -g <resource-group> -f infra/app.bicep \
//     -p infra/app.parameters.dev.json

@description('Short environment name — must match what base.bicep was deployed with.')
param environmentName string = 'dev'

@description('Azure region.')
param location string = resourceGroup().location

@description('Name prefix — must match what base.bicep was deployed with.')
param namePrefix string = 'commerce'

@description('Container image tag to deploy. Build and push it to the ACR from base.bicep first (see README.md).')
param imageTag string = 'latest'

@description('Container App min replicas. 1 avoids cold starts on health checks/demos; 0 saves more but adds latency on the first request after idle.')
param minReplicas int = 1

@description('Container App max replicas.')
param maxReplicas int = 3

@description('Suffix for globally-unique resource names — must match the value base.bicep was deployed with (see its uniqueSuffix parameter description).')
@minLength(5)
@maxLength(13)
param uniqueSuffix string = uniqueString(resourceGroup().id)

@description('Must match the acrNameOverride base.bicep was deployed with, if any. Leave empty otherwise.')
param acrNameOverride string = ''

@description('Tags applied to the resource.')
param tags object = {
  project: 'commerce-intelligence'
  environment: environmentName
}
var acrName = empty(acrNameOverride) ? toLower('${namePrefix}acr${uniqueSuffix}') : acrNameOverride
var keyVaultName = toLower('kv-${namePrefix}-${uniqueSuffix}')
var containerAppEnvName = 'cae-${namePrefix}-${environmentName}'
var identityName = 'id-${namePrefix}-api-${environmentName}'
var containerAppName = 'ca-${namePrefix}-api-${environmentName}'

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: acrName
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource databaseUrlSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' existing = {
  parent: keyVault
  name: 'database-url'
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

// Environment-level telemetry export to App Insights (Container Apps' own
// OTel collector, not an app-side SDK) is a separate, still-evolving preview
// API surface (`az containerapp env telemetry app-insights set`). Left as a
// documented post-deploy step in README.md rather than encoded here, since
// its ARM schema isn't stable enough yet to pin confidently in this template.

output containerAppName string = containerApp.name
output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn
