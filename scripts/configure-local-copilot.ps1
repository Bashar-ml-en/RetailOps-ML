[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string]$Model,

    [ValidateRange(1, 5000)]
    [int]$PerRunBudgetCents = 25,

    [ValidateRange(1, 50000)]
    [int]$MonthlyBudgetCents = 1000,

    [Parameter(Mandatory)]
    [switch]$ApproveNoProviderStorage
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($PerRunBudgetCents -gt $MonthlyBudgetCents) {
    throw "PerRunBudgetCents cannot exceed MonthlyBudgetCents."
}

$secureKey = Read-Host -Prompt "Paste a newly rotated OpenAI API key (input is hidden)" -AsSecureString
$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
    if ([string]::IsNullOrWhiteSpace($plainKey)) {
        throw "An OpenAI API key is required."
    }
    $randomBytes = [byte[]]::new(32)
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($randomBytes)
    $operatorToken = [Convert]::ToBase64String($randomBytes)

    $settings = @{
        "OPENAI_API_KEY" = $plainKey
        "RETAILOPS_ENABLE_PLANNER_COPILOT" = "true"
        "RETAILOPS_OPENAI_MODEL" = $Model
        "RETAILOPS_COPILOT_OPERATOR_TOKEN" = $operatorToken
        "RETAILOPS_COPILOT_PER_RUN_BUDGET_CENTS" = $PerRunBudgetCents.ToString()
        "RETAILOPS_COPILOT_MONTHLY_BUDGET_CENTS" = $MonthlyBudgetCents.ToString()
        "RETAILOPS_COPILOT_MAX_OUTPUT_TOKENS" = "800"
        "RETAILOPS_COPILOT_MAX_TOOL_CALLS" = "3"
        "RETAILOPS_COPILOT_NO_PROVIDER_STORAGE_APPROVED" = "true"
    }
    foreach ($entry in $settings.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, "User")
    }
}
finally {
    if ($keyPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
    }
    $plainKey = $null
}

Write-Host "RetailOps local Planner Copilot settings were saved for your Windows user."
Write-Host "Close and reopen API/worker terminals so they inherit the new environment."
Write-Host "The API key and operator token were not written to this repository or displayed."
