# Check the DAX measures in the open Power BI report against the SQL pipeline.
#
#   1. Open powerbi\report\CardPortfolioTracker.pbip in Power BI Desktop.
#   2. Run:  .\powerbi\verify_dax.ps1            (add -Refresh to reload the CSV data first)
#
# Power BI Desktop runs a local Analysis Services engine while a report is open. This
# script connects to it, evaluates the measures for every scenario x tier x tenure
# combination a slicer can produce, and compares them with expected_values.csv, which
# is exported by the SQL pipeline. The result is written to docs\proof\powerbi_dax_check.txt.

param(
    [switch]$Refresh,
    [double]$Tolerance = 0.01
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$desktopBin = "C:\Program Files\Microsoft Power BI Desktop\bin"

$portFile = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\Power BI Desktop\AnalysisServicesWorkspaces" `
    -Recurse -Filter msmdsrv.port.txt -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $portFile) { throw "Power BI Desktop is not running with a report open." }
$port = ([System.IO.File]::ReadAllText($portFile.FullName, [System.Text.Encoding]::Unicode)).Trim()

Add-Type -Path "$desktopBin\Microsoft.PowerBI.AdomdClient.dll"
$con = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$port")
$con.Open()
$database = $con.GetSchemaDataSet("DBSCHEMA_CATALOGS", $null).Tables[0].Rows[0]["CATALOG_NAME"]
$con.ChangeDatabase($database)

function Invoke-Dax([string]$query) {
    $cmd = $con.CreateCommand()
    $cmd.CommandTimeout = 600
    $cmd.CommandText = $query
    $reader = $cmd.ExecuteReader()
    $row = [ordered]@{}
    if ($reader.Read()) {
        for ($i = 0; $i -lt $reader.FieldCount; $i++) {
            $row[$reader.GetName($i).Trim('[', ']')] = $reader.GetValue($i)
        }
    }
    $reader.Close()
    return $row
}

if ($Refresh) {
    $cmd = $con.CreateCommand()
    $cmd.CommandTimeout = 600
    $cmd.CommandText = '{"refresh": {"type": "full", "objects": [{"database": "' + $database + '"}]}}'
    [void]$cmd.ExecuteNonQuery()
    Write-Host "Model refreshed from the CSV files"
}

# expected_values.csv column -> measure
$numeric = [ordered]@{
    customers_q1           = "Customers Q1"
    customers_q4           = "Customers Q4"
    spend_q1               = "Spend Q1"
    spend_q4               = "Spend Q4"
    spend_change           = "Spend Change"
    spend_change_pct       = "Spend Change %"
    active_rate_q1         = "Active Rate Q1"
    active_rate_q4         = "Active Rate Q4"
    txns_per_active_q1     = "Txns per Active Q1"
    txns_per_active_q4     = "Txns per Active Q4"
    avg_ticket_q1          = "Avg Ticket Q1"
    avg_ticket_q4          = "Avg Ticket Q4"
    effect_customers       = "Effect Customers"
    effect_active_rate     = "Effect Active Rate"
    effect_txns_per_active = "Effect Txns per Active"
    effect_avg_ticket      = "Effect Avg Ticket"
}
$columns = ($numeric.GetEnumerator() | ForEach-Object { '"' + $_.Key + '", [' + $_.Value + ']' }) -join ", "
$columns += ', "dominant_driver", [Dominant Driver], "method", [Decomposition Method]'
$columns += ', "effect_check", [Effect Check], "bridge_total", [Bridge Value], "is_low_n", [Is Low N]'

$expected = Import-Csv (Join-Path $PSScriptRoot "expected_values.csv")
$culture = [System.Globalization.CultureInfo]::InvariantCulture
$worst = 0.0
$worstWhere = ""
$failures = @()
$checked = 0

foreach ($e in $expected) {
    $filters = @('dim_scenario[scenario_code] = "' + $e.scenario + '"')
    if ($e.tier -ne "All") { $filters += 'dim_tier[card_tier] = "' + $e.tier + '"' }
    if ($e.tenure -ne "All") { $filters += 'dim_tenure[tenure_band] = "' + $e.tenure + '"' }
    $actual = Invoke-Dax ("EVALUATE CALCULATETABLE ( ROW ( $columns ), " + ($filters -join ", ") + " )")
    $label = "$($e.scenario) / $($e.tier) / $($e.tenure)"

    foreach ($key in $numeric.Keys) {
        $want = [double]::Parse($e.$key, $culture)
        $got = if ($actual[$key] -is [DBNull] -or $null -eq $actual[$key]) { 0.0 } else { [double]$actual[$key] }
        $diff = [math]::Abs($got - $want)
        $checked++
        if ($diff -gt $worst) { $worst = $diff; $worstWhere = "$label, $($numeric[$key])" }
        if ($diff -gt $Tolerance) { $failures += "$label  $($numeric[$key]): Power BI $got, pipeline $want" }
    }
    if ($actual["dominant_driver"] -ne $e.dominant_driver) {
        $failures += "$label  Dominant Driver: Power BI '$($actual["dominant_driver"])', pipeline '$($e.dominant_driver)'"
    }
    $wantMethod = if ($e.decomposition_method -eq "lmdi") { "LMDI" } else { "Sequential fallback (a factor is zero)" }
    if ($actual["method"] -ne $wantMethod) { $failures += "$label  Decomposition Method: '$($actual["method"])'" }
    if ([math]::Abs([double]$actual["effect_check"]) -gt $Tolerance) { $failures += "$label  Effect Check is not zero" }
    if ([math]::Abs([double]$actual["bridge_total"] - [double]::Parse($e.spend_q4, $culture)) -gt $Tolerance) {
        $failures += "$label  Bridge total does not equal Q4 spend"
    }
    if ([string]$actual["is_low_n"] -ne [string]([bool]::Parse($e.is_low_n))) { $failures += "$label  Is Low N differs" }
    $checked += 5
}

# The attrition page: cohort view of scenario B, and the fallback for a cohort with no Q4 book.
$cohort = Invoke-Dax 'EVALUATE ROW (
    "existing", CALCULATE ( [Spend Change Exit Run-Rate], dim_customer[attrition_flag] = "Existing Customer" ),
    "attrited", CALCULATE ( [Spend Change Exit Run-Rate], dim_customer[attrition_flag] = "Attrited Customer" ),
    "total", [Spend Change Exit Run-Rate],
    "attrited_method", CALCULATE ( [Decomposition Method], dim_scenario[scenario_code] = "B", dim_customer[attrition_flag] = "Attrited Customer" ),
    "both_scenarios_spend_q1", CALCULATE ( [Spend Q1], ALL ( dim_scenario ) ),
    "attrition_rate", [Attrition Rate]
)'
$expectedB = $expected | Where-Object { $_.scenario -eq "B" -and $_.tier -eq "All" -and $_.tenure -eq "All" }
$expectedA = $expected | Where-Object { $_.scenario -eq "A" -and $_.tier -eq "All" -and $_.tenure -eq "All" }
if ([math]::Abs($cohort["existing"] + $cohort["attrited"] - $cohort["total"]) -gt $Tolerance) { $failures += "Cohort changes do not add up to the scenario B change" }
if ([math]::Abs($cohort["total"] - [double]::Parse($expectedB.spend_change, $culture)) -gt $Tolerance) { $failures += "Exit run-rate change differs from the pipeline" }
if ($cohort["attrited_method"] -notlike "Sequential fallback*") { $failures += "Attrited cohort in scenario B should use the sequential fallback" }
if ([math]::Abs($cohort["both_scenarios_spend_q1"] - [double]::Parse($expectedA.spend_q1, $culture)) -gt $Tolerance) { $failures += "Spend doubles when no single scenario is selected" }
$checked += 4
$con.Close()

$lines = @(
    "Power BI DAX check, written by powerbi/verify_dax.ps1",
    "Measures evaluated in Power BI Desktop against the SQL pipeline (powerbi/expected_values.csv).",
    "",
    "Slicer combinations checked: $($expected.Count) (2 scenarios x tier x tenure, including All)",
    "Values compared: $checked",
    "Largest absolute difference: $($worst.ToString('0.0000', $culture)) on $worstWhere",
    "Tolerance: $($Tolerance.ToString($culture)) (expected values are rounded to 2 decimals for dollars, 6 for ratios)",
    "Cohort view, exit run-rate: existing $([math]::Round($cohort['existing'])), attrited $([math]::Round($cohort['attrited'])), total $([math]::Round($cohort['total']))",
    "Attrited cohort under scenario B uses: $($cohort['attrited_method'])",
    "Spend Q1 with no single scenario selected: $([math]::Round($cohort['both_scenarios_spend_q1'])) (not doubled)",
    "",
    $(if ($failures.Count -eq 0) { "RESULT: PASS" } else { "RESULT: FAIL ($($failures.Count) problems)" })
) + $failures

$outDir = Join-Path $root "docs\proof"
New-Item -ItemType Directory -Force $outDir | Out-Null
[System.IO.File]::WriteAllText((Join-Path $outDir "powerbi_dax_check.txt"), (($lines -join "`n") + "`n"))
$lines | ForEach-Object { Write-Host $_ }
if ($failures.Count -gt 0) { exit 1 }
