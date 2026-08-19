// Commerce Intelligence — base Azure infrastructure (everything except the
// Container App itself). Split from app.bicep deliberately: the Container
// App needs an image to already exist in the registry this template creates,
// so "create the registry" and "deploy the app into it" can't be one
// deployment on a first-ever run. Deploy this once (and again only when
// infra itself changes); deploy app.bicep every time the app image changes.
//
// Reproduces exactly what was verified by hand for DEV in August 2026 (see
// README.md's "Deploying to Azure" section for the narrative version). No
// application code changes — this only stands up infrastructure and wires
// the same env vars the app already reads via app/config.py's Settings.
//
// Deploy (resource group must already exist):
//   az deployment group create -g <resource-group> -f infra/base.bicep \
//     -p infra/base.parameters.dev.json \
//     postgresAdminPassword='<generate-a-strong-password-do-not-commit-it>'
//
// PROD is not defined here yet — see README.md's "Deploying to Azure (PROD)"
// for the pattern (private Postgres, purge-protected Key Vault, promoted
// images, CI/CD) it would need on top of this template once that's needed.

@description('Short environment name, used in resource names and tags (e.g. "dev").')
param environmentName string = 'dev'

@description('Azure region for every resource.')
param location string = resourceGroup().location

@description('Name prefix for all resources.')
param namePrefix string = 'commerce'

@description('PostgreSQL administrator username.')
param postgresAdminUser string = 'aiadmin'

@description('PostgreSQL administrator password. Pass at deploy time — never store this in a parameters file.')
@secure()
param postgresAdminPassword string

@description('Database name the app connects to (matches DATABASE_URL in app/config.py defaults).')
param databaseName string = 'ai_commerce'

@description('Suffix for globally-unique resource names (ACR, Key Vault, Postgres). Defaults to a hash of the resource group, but pin it explicitly to adopt/update resources an earlier deployment already created under a different suffix — mismatching this creates parallel duplicates instead of updating in place.')
@minLength(5)
@maxLength(13)
param uniqueSuffix string = uniqueString(resourceGroup().id)

@description('Override the computed ACR name entirely, to adopt a registry an earlier deployment created under a name that does not follow this template\'s naming pattern. Leave empty to use the computed name.')
param acrNameOverride string = ''

@description('Override the computed AcrPull role assignment name/GUID, to adopt one created outside this template. Azure rejects creating a second assignment for the same principal/role/scope, so this must be set to the existing assignment\'s GUID when one already exists. Leave empty to compute one deterministically.')
param acrPullAssignmentNameOverride string = ''

@description('Same as acrPullAssignmentNameOverride, for the Key Vault Secrets User role assignment.')
param keyVaultRbacAssignmentNameOverride string = ''

@description('Tags applied to every resource.')
param tags object = {
  project: 'commerce-intelligence'
  environment: environmentName
}

// app.bicep independently recomputes these same names (via `existing`
// resource lookups, given the same namePrefix/environmentName/uniqueSuffix)
// without any output-passing between the two deployments.
var acrName = empty(acrNameOverride) ? toLower('${namePrefix}acr${uniqueSuffix}') : acrNameOverride
var keyVaultName = toLower('kv-${namePrefix}-${uniqueSuffix}')
var postgresServerName = toLower('psql-${namePrefix}-${uniqueSuffix}')
var logAnalyticsName = 'log-${namePrefix}-${environmentName}'
var appInsightsName = 'appi-${namePrefix}-${environmentName}'
var containerAppEnvName = 'cae-${namePrefix}-${environmentName}'
var identityName = 'id-${namePrefix}-api-${environmentName}'

var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    IngestionMode: 'LogAnalytics'
  }
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
  }
}

resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2023-06-01-preview' = {
  name: postgresServerName
  location: location
  tags: tags
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '16'
    administratorLogin: postgresAdminUser
    administratorLoginPassword: postgresAdminPassword
    storage: {
      storageSizeGB: 32
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
  }
}

resource postgresDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-06-01-preview' = {
  parent: postgresServer
  name: databaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

// "Allow Azure services" — not the open internet. Never widen this to a
// public IP range; PROD should replace it with VNet integration instead
// (see README.md's "Deploying to Azure (PROD)").
resource postgresAllowAzureServices 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-06-01-preview' = {
  parent: postgresServer
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
  tags: tags
}

resource acrPullAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: empty(acrPullAssignmentNameOverride) ? guid(acr.id, identity.id, acrPullRoleId) : acrPullAssignmentNameOverride
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource keyVaultSecretsUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: empty(keyVaultRbacAssignmentNameOverride) ? guid(keyVault.id, identity.id, keyVaultSecretsUserRoleId) : keyVaultRbacAssignmentNameOverride
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// The only value the app treats as sensitive (app/config.py's DATABASE_URL).
// Depends on the role assignment so the identity can read it once app.bicep
// references it.
resource databaseUrlSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'database-url'
  properties: {
    value: 'postgresql+psycopg://${postgresAdminUser}:${postgresAdminPassword}@${postgresServer.properties.fullyQualifiedDomainName}:5432/${databaseName}?sslmode=require'
  }
  dependsOn: [
    keyVaultSecretsUserAssignment
  ]
}

resource containerAppEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerAppEnvName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

output acrName string = acr.name
output acrLoginServer string = acr.properties.loginServer
output keyVaultName string = keyVault.name
output identityName string = identity.name
output containerAppEnvName string = containerAppEnv.name
output postgresServerFqdn string = postgresServer.properties.fullyQualifiedDomainName
output logAnalyticsWorkspaceName string = logAnalytics.name
output appInsightsConnectionString string = appInsights.properties.ConnectionString
