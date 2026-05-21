param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $ScriptArgs
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$Candidates = @()

$PyLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($PyLauncher) {
    $Candidates += @{
        Exe = $PyLauncher.Source
        Args = @("-3")
        Env = @{}
        Label = "py -3"
    }
}

$PythonCommands = Get-Command python -All -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Source -and
        $_.Source -notlike "*\WindowsApps\python.exe" -and
        $_.Source -notlike "*\WindowsApps\python3.exe"
    }

foreach ($Command in $PythonCommands) {
    $Candidates += @{
        Exe = $Command.Source
        Args = @()
        Env = @{}
        Label = $Command.Source
    }
}

$MysqlWorkbenchPath = "C:\Program Files\MySQL\MySQL Workbench 8.0"
$MysqlPythonHome = Join-Path $MysqlWorkbenchPath "python"
$MysqlPython = Join-Path $MysqlWorkbenchPath "python.exe"
if (Test-Path -LiteralPath $MysqlPython) {
    $Candidates += @{
        Exe = $MysqlPython
        Args = @()
        Env = @{ PYTHONHOME = $MysqlPythonHome }
        Label = $MysqlPython
    }
}

function Get-ArgValue {
    param(
        [string[]] $ArgsList,
        [string] $Name,
        [string] $Default
    )

    for ($Index = 0; $Index -lt $ArgsList.Count; $Index++) {
        if ($ArgsList[$Index] -eq $Name -and ($Index + 1) -lt $ArgsList.Count) {
            return $ArgsList[$Index + 1]
        }
        if ($ArgsList[$Index].StartsWith("$Name=")) {
            return $ArgsList[$Index].Substring($Name.Length + 1)
        }
    }

    return $Default
}

function Remove-OutputArgs {
    param([string[]] $ArgsList)

    $Clean = @()
    for ($Index = 0; $Index -lt $ArgsList.Count; $Index++) {
        if ($ArgsList[$Index] -eq "--output") {
            $Index++
            continue
        }
        if ($ArgsList[$Index].StartsWith("--output=")) {
            continue
        }
        $Clean += $ArgsList[$Index]
    }
    return $Clean
}

function Test-WorkbookLocked {
    param([string] $Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }

    try {
        $Stream = [System.IO.File]::Open($Path, "Open", "ReadWrite", "None")
        $Stream.Close()
        return $false
    } catch {
        return $true
    }
}

function Remove-ExcelFilterMetadata {
    param([string] $Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem

    $FullPath = (Resolve-Path -LiteralPath $Path).Path
    $TempPath = [System.IO.Path]::Combine(
        [System.IO.Path]::GetDirectoryName($FullPath),
        "." + [System.IO.Path]::GetFileNameWithoutExtension($FullPath) + ".cleaning.xlsx"
    )

    if (Test-Path -LiteralPath $TempPath) {
        Remove-Item -LiteralPath $TempPath -Force
    }

    $Source = [System.IO.Compression.ZipFile]::OpenRead($FullPath)
    $Target = [System.IO.Compression.ZipFile]::Open($TempPath, [System.IO.Compression.ZipArchiveMode]::Create)

    try {
        foreach ($Entry in $Source.Entries) {
            $NewEntry = $Target.CreateEntry($Entry.FullName, [System.IO.Compression.CompressionLevel]::Optimal)

            $InputStream = $Entry.Open()
            $OutputStream = $NewEntry.Open()

            try {
                $NeedsXmlCleanup = (
                    $Entry.FullName -eq "xl/workbook.xml" -or
                    ($Entry.FullName -like "xl/worksheets/*.xml")
                )

                if ($NeedsXmlCleanup) {
                    $Reader = New-Object System.IO.StreamReader($InputStream, [System.Text.Encoding]::UTF8)
                    $Content = $Reader.ReadToEnd()
                    $Reader.Close()

                    if ($Entry.FullName -eq "xl/workbook.xml") {
                        $Content = [Regex]::Replace(
                            $Content,
                            '<definedName\b[^>]*_FilterDatabase[^>]*>.*?</definedName>',
                            '',
                            [System.Text.RegularExpressions.RegexOptions]::Singleline
                        )
                        $Content = [Regex]::Replace(
                            $Content,
                            '<definedNames>\s*</definedNames>',
                            ''
                        )
                    } else {
                        $Content = [Regex]::Replace(
                            $Content,
                            '<autoFilter\b[^>]*/>',
                            ''
                        )
                    }

                    $Bytes = [System.Text.Encoding]::UTF8.GetBytes($Content)
                    $OutputStream.Write($Bytes, 0, $Bytes.Length)
                } else {
                    $InputStream.CopyTo($OutputStream)
                }
            } finally {
                $InputStream.Dispose()
                $OutputStream.Dispose()
            }
        }
    } finally {
        $Source.Dispose()
        $Target.Dispose()
    }

    Move-Item -LiteralPath $TempPath -Destination $FullPath -Force
}

function Convert-CsvToWorkbook {
    param(
        [string] $CsvPath,
        [string] $WorkbookPath
    )

    $Excel = $null
    $Workbook = $null
    $ExcelProcessId = $null
    $ExistingExcelIds = @(
        Get-Process EXCEL -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty Id
    )
    try {
        $Excel = New-Object -ComObject Excel.Application
        $Excel.Visible = $false
        $Excel.DisplayAlerts = $false
        try {
            $ExcelProcessId = (
                Get-Process EXCEL -ErrorAction SilentlyContinue |
                Where-Object { $_.MainWindowHandle -eq $Excel.Hwnd } |
                Select-Object -First 1 -ExpandProperty Id
            )
        } catch {
            $ExcelProcessId = $null
        }

        if (Test-Path -LiteralPath $WorkbookPath) {
            Remove-ExcelFilterMetadata -Path $WorkbookPath
            $Workbook = $Excel.Workbooks.Open((Resolve-Path -LiteralPath $WorkbookPath).Path)
            $Worksheet = $Workbook.Worksheets.Item(1)
        } else {
            $Workbook = $Excel.Workbooks.Add()
            $Worksheet = $Workbook.Worksheets.Item(1)
            $Worksheet.Name = "Precos"
            $Worksheet.Rows.Item(1).Font.Bold = $true
            $Worksheet.Rows.Item(1).Font.Color = 16777215
            $Worksheet.Rows.Item(1).Interior.Color = 0
            $Worksheet.Application.ActiveWindow.SplitRow = 1
            $Worksheet.Application.ActiveWindow.FreezePanes = $true
        }

        $Rows = @(Import-Csv -Delimiter ';' -Encoding UTF8 -LiteralPath $CsvPath)
        $Headers = @()
        if ($Rows.Count -gt 0) {
            $Headers = $Rows[0].PSObject.Properties.Name
        } else {
            $FirstLine = Get-Content -LiteralPath $CsvPath -First 1 -Encoding UTF8
            $Headers = $FirstLine -split ';'
        }

        $RowCount = [Math]::Max(1, $Rows.Count + 1)
        $ColumnCount = $Headers.Count
        $UsedRows = [Math]::Max($Worksheet.UsedRange.Rows.Count, $RowCount)
        $UsedColumns = [Math]::Max($Worksheet.UsedRange.Columns.Count, $ColumnCount)
        $Worksheet.Range($Worksheet.Cells.Item(1, 1), $Worksheet.Cells.Item($UsedRows, $UsedColumns)).ClearContents()

        $Data = New-Object 'object[,]' $RowCount, $ColumnCount
        for ($Column = 0; $Column -lt $ColumnCount; $Column++) {
            $Data[0, $Column] = $Headers[$Column]
        }

        for ($Row = 0; $Row -lt $Rows.Count; $Row++) {
            for ($Column = 0; $Column -lt $ColumnCount; $Column++) {
                $Value = $Rows[$Row].($Headers[$Column])
                if ($Value -match '^\d+$') {
                    $Data[($Row + 1), $Column] = [int64]$Value
                } else {
                    $Data[($Row + 1), $Column] = $Value
                }
            }
        }

        $Target = $Worksheet.Range($Worksheet.Cells.Item(1, 1), $Worksheet.Cells.Item($RowCount, $ColumnCount))
        $Worksheet.Columns.Item(4).NumberFormat = "@"
        $Worksheet.Columns.Item(5).NumberFormat = "@"
        $Worksheet.Columns.Item(6).NumberFormat = "@"
        $Worksheet.Columns.Item(7).NumberFormat = "@"
        $Worksheet.Columns.Item(8).NumberFormat = "@"
        $Target.Value2 = $Data
        $Worksheet.Range($Worksheet.Cells.Item(1, 1), $Worksheet.Cells.Item(1, $ColumnCount)).EntireColumn.AutoFit() | Out-Null
        foreach ($Name in @($Workbook.Names)) {
            if ($Name.Name -like "*_FilterDatabase*") {
                try {
                    $Name.Delete() | Out-Null
                } catch {
                }
            }
        }

        if (Test-Path -LiteralPath $WorkbookPath) {
            $Workbook.Save() | Out-Null
        } else {
            $Workbook.SaveAs((Join-Path $ProjectRoot $WorkbookPath), 51) | Out-Null
        }
    } finally {
        if ($Workbook) {
            $Workbook.Close($true) | Out-Null
        }
        if ($Excel) {
            $Excel.Quit() | Out-Null
        }
        if ($Target) {
            [System.Runtime.InteropServices.Marshal]::ReleaseComObject($Target) | Out-Null
        }
        if ($Worksheet) {
            [System.Runtime.InteropServices.Marshal]::ReleaseComObject($Worksheet) | Out-Null
        }
        if ($Workbook) {
            [System.Runtime.InteropServices.Marshal]::ReleaseComObject($Workbook) | Out-Null
        }
        if ($Excel) {
            [System.Runtime.InteropServices.Marshal]::ReleaseComObject($Excel) | Out-Null
        }
        [GC]::Collect()
        [GC]::WaitForPendingFinalizers()
        Start-Sleep -Milliseconds 500
        if ($ExcelProcessId) {
            Stop-Process -Id $ExcelProcessId -Force -ErrorAction SilentlyContinue
        }
        Get-Process EXCEL -ErrorAction SilentlyContinue |
            Where-Object {
                $ExistingExcelIds -notcontains $_.Id -and
                -not $_.MainWindowTitle
            } |
            Stop-Process -Force -ErrorAction SilentlyContinue
    }
}

if (-not $Candidates) {
    Write-Host "Nenhum Python valido encontrado."
    Write-Host "Instale o Python 3 em https://www.python.org/downloads/ e marque 'Add Python to PATH'."
    exit 1
}

$WorkbookOutput = Get-ArgValue -ArgsList $ScriptArgs -Name "--output" -Default "reports\albion_api_prices.xlsx"
$DataOutput = "reports\.albion_api_prices_data.csv"
$PythonArgs = Remove-OutputArgs -ArgsList $ScriptArgs

if ([IO.Path]::GetExtension($WorkbookOutput).ToLowerInvariant() -ne ".xlsx") {
    $DataOutput = $WorkbookOutput
}

if ([IO.Path]::GetExtension($WorkbookOutput).ToLowerInvariant() -eq ".xlsx" -and (Test-WorkbookLocked -Path $WorkbookOutput)) {
    Write-Host "A planilha esta aberta ou travada: $WorkbookOutput"
    Write-Host "Feche o arquivo no Excel e rode o atualizador novamente."
    exit 1
}

foreach ($Candidate in $Candidates) {
    Write-Host "Tentando atualizar com: $($Candidate.Label)"

    $OldPythonHome = $env:PYTHONHOME
    if ($Candidate.Env.ContainsKey("PYTHONHOME")) {
        $env:PYTHONHOME = $Candidate.Env.PYTHONHOME
    } else {
        Remove-Item Env:\PYTHONHOME -ErrorAction SilentlyContinue
    }

    & $Candidate.Exe @($Candidate.Args) "gerar_planilha_api.py" @PythonArgs "--output" $DataOutput
    $ExitCode = $LASTEXITCODE

    if ($null -ne $OldPythonHome) {
        $env:PYTHONHOME = $OldPythonHome
    } else {
        Remove-Item Env:\PYTHONHOME -ErrorAction SilentlyContinue
    }

    if ($ExitCode -eq 0) {
        if ([IO.Path]::GetExtension($WorkbookOutput).ToLowerInvariant() -eq ".xlsx") {
            Convert-CsvToWorkbook -CsvPath $DataOutput -WorkbookPath $WorkbookOutput
            Remove-Item -LiteralPath $DataOutput -Force -ErrorAction SilentlyContinue
            Write-Host "Planilha XLSX atualizada: $WorkbookOutput"
        }
        exit 0
    }

    Write-Host "Falhou com codigo $ExitCode. Tentando proximo Python..."
}

Write-Host "Nao foi possivel atualizar a planilha com os Pythons encontrados."
exit 1
