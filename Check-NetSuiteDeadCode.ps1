[CmdletBinding()]
param(
    [string]$ProjectRoot = (Get-Location).Path
)

$ErrorActionPreference = 'SilentlyContinue'
$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$excluded = '[\\/](\.git|node_modules|\.venv|venv|__pycache__|dist|build|coverage)([\\/]|$)'
$extensions = @('.py', '.js', '.jsx', '.ts', '.tsx', '.json', '.md', '.yml', '.yaml')

$files = @(Get-ChildItem -LiteralPath $root -Recurse -File |
    Where-Object {
        $_.Extension.ToLowerInvariant() -in $extensions -and
        $_.FullName -notmatch $excluded
    })

Write-Host "Project root: $root" -ForegroundColor Cyan
Write-Host "Source files scanned: $($files.Count)" -ForegroundColor Cyan
Write-Host ""

$viewClasses = @(
    'NetSuiteCustomersView',
    'NetSuiteCustomerDetailView',
    'NetSuiteEmployeesView',
    'NetSuiteEmployeeDetailView',
    'NetSuiteVendorsView',
    'NetSuiteVendorDetailView',
    'NetSuiteItemsView',
    'NetSuiteItemDetailView',
    'NetSuiteSalesOrdersView',
    'NetSuiteSalesOrderDetailView',
    'NetSuitePurchaseOrderView',
    'NetSuitePurchaseOrderDetailView',
    'NetSuiteInvoicesView',
    'NetSuiteInvoiceDetailView',
    'NetSuiteConnectionListCreateView'
)

Write-Host '=== View class references outside backend/netsuite/views.py ===' -ForegroundColor Yellow
foreach ($name in $viewClasses) {
    $hits = @(
        foreach ($file in $files) {
            if ($file.FullName -match '[\\/]backend[\\/]netsuite[\\/]views\.py$') { continue }
            Select-String -LiteralPath $file.FullName -SimpleMatch -Pattern $name |
                ForEach-Object {
                    [pscustomobject]@{
                        Target = $name
                        File = $_.Path.Substring($root.Length).TrimStart('\', '/')
                        Line = $_.LineNumber
                        Text = $_.Line.Trim()
                    }
                }
        }
    )
    if ($hits.Count -eq 0) {
        Write-Host "NO EXTERNAL SOURCE REFERENCE: $name" -ForegroundColor DarkYellow
    } else {
        foreach ($hit in $hits) {
            Write-Host ("{0} | {1}:{2} | {3}" -f $hit.Target, $hit.File, $hit.Line, $hit.Text)
        }
    }
}

Write-Host ""
Write-Host '=== URL route entries for these view classes/endpoints ===' -ForegroundColor Yellow
$urlFile = Join-Path $root 'backend/netsuite/urls.py'
if (Test-Path -LiteralPath $urlFile) {
    Select-String -LiteralPath $urlFile -Pattern 'customers|employees|vendors|items|sales-orders|purchase-orders|invoices|connections/' |
        ForEach-Object {
            Write-Host ("{0}:{1} | {2}" -f $_.Path.Substring($root.Length).TrimStart('\', '/'), $_.LineNumber, $_.Line.Trim())
        }
} else {
    Write-Host 'Could not find backend/netsuite/urls.py from the supplied ProjectRoot.' -ForegroundColor Red
}

Write-Host ""
Write-Host '=== Direct frontend calls of candidate API helpers (excluding the helper-definition file) ===' -ForegroundColor Yellow
$callPattern = 'netsuiteApi\.(listConnections|getEmployees|getEmployee|getInvoices|getInvoice)\s*\('
$callHits = @(
    foreach ($file in $files) {
        if ($file.FullName -match '[\\/]frontend[\\/]src[\\/]services[\\/]netsuite\.js$') { continue }
        Select-String -LiteralPath $file.FullName -Pattern $callPattern |
            ForEach-Object {
                [pscustomobject]@{
                    File = $_.Path.Substring($root.Length).TrimStart('\', '/')
                    Line = $_.LineNumber
                    Text = $_.Line.Trim()
                }
            }
    }
)
if ($callHits.Count -eq 0) {
    Write-Host 'No direct frontend calls of listConnections/getEmployees/getEmployee/getInvoices/getInvoice found.' -ForegroundColor Green
} else {
    foreach ($hit in $callHits) {
        Write-Host ("{0}:{1} | {2}" -f $hit.File, $hit.Line, $hit.Text)
    }
}

Write-Host ""
Write-Host '=== Interpretation ===' -ForegroundColor Cyan
Write-Host 'A view referenced by backend/netsuite/urls.py is an exposed HTTP API, even if the current React UI has no caller.'
Write-Host 'Removing its URL route can break external clients, Postman collections, integrations, bookmarks, tests, or future UI code.'
Write-Host 'This is a static source scan; it cannot prove that nobody outside this repository calls an endpoint.'
