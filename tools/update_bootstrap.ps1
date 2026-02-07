param(
    [int]$RecentCommitCount = 12,
    [int]$RecentFileCount = 25,
    [string]$OutputMarkdown = "PROJECT_BOOTSTRAP.md",
    [string]$OutputJson = "artifacts/project_bootstrap.json"
)

$ErrorActionPreference = "Stop"

function Get-GitLines {
    param([string[]]$CommandArgs)
    $result = & git @CommandArgs 2>$null
    if ($LASTEXITCODE -ne 0) {
        return @()
    }
    if ($null -eq $result) {
        return @()
    }
    return @($result)
}

function Read-PatternLines {
    param(
        [string]$Path,
        [string]$Pattern
    )
    if (-not (Test-Path -Path $Path)) {
        return @()
    }
    return @(Select-String -Path $Path -Pattern $Pattern | ForEach-Object { $_.Line.Trim() -replace "^- ", "" })
}

$repoRoot = (Resolve-Path ".").Path
$generatedAt = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssK")

$branch = (Get-GitLines @("branch", "--show-current") | Select-Object -First 1)
if ([string]::IsNullOrWhiteSpace($branch)) {
    $branch = "(detached)"
}

$head = (Get-GitLines @("rev-parse", "--short", "HEAD") | Select-Object -First 1)
if ([string]::IsNullOrWhiteSpace($head)) {
    $head = "(unknown)"
}

$statusLines = @(Get-GitLines @("status", "--short"))
$dirty = $statusLines.Count -gt 0

$commitLines = @(Get-GitLines @("log", "--date=short", "--pretty=format:%h|%ad|%s", "-n", "$RecentCommitCount"))
$recentCommits = @()
foreach ($line in $commitLines) {
    $parts = $line -split "\|", 3
    if ($parts.Count -lt 3) {
        continue
    }
    $recentCommits += [pscustomobject]@{
        hash = $parts[0]
        date = $parts[1]
        subject = $parts[2]
    }
}

$excludePattern = "\\.git\\|\\.worktrees\\|__pycache__|\\.pytest_cache"
$recentFiles = Get-ChildItem -Recurse -File |
    Where-Object { $_.FullName -notmatch $excludePattern } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First $RecentFileCount |
    ForEach-Object {
        $relativePath = $_.FullName.Substring($repoRoot.Length).TrimStart("\", "/")
        [pscustomobject]@{
            path = $relativePath
            last_write = $_.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
        }
    }

$openTaskItems = Read-PatternLines -Path "TASKS.md" -Pattern "^- \[(todo|in-progress)\]"
$gapLines = Read-PatternLines -Path "REQUIREMENTS_BASELINE.md" -Pattern "^- GAP-"

$gapsById = @{}
foreach ($line in $gapLines) {
    if ($line -match "(GAP-\d+)") {
        $gapsById[$matches[1]] = $line
    }
}

$recentSubjects = (($recentCommits | ForEach-Object { $_.subject }) -join " || ")
$likelyClosed = [ordered]@{}

if ($recentSubjects -match "upsert") {
    if ($gapsById.ContainsKey("GAP-001")) {
        $likelyClosed["GAP-001"] = "Recent commit subjects indicate upsert conflict-ID fix landed."
    }
}
if ($recentSubjects -match "import run-meta lookup|connection lifecycle|import") {
    if ($gapsById.ContainsKey("GAP-002")) {
        $likelyClosed["GAP-002"] = "Recent commit subjects indicate /import connection-lifecycle bug fix landed."
    }
}
if ($recentSubjects -match "compare lap query params|compare") {
    if ($gapsById.ContainsKey("GAP-003")) {
        $likelyClosed["GAP-003"] = "Recent commit subjects indicate /compare explicit lap query support landed."
    }
}

$likelyClosedIds = @($likelyClosed.Keys)
$activeGaps = @()
foreach ($line in $gapLines) {
    $gapId = ""
    if ($line -match "(GAP-\d+)") {
        $gapId = $matches[1]
    }
    if ($gapId -and ($likelyClosedIds -contains $gapId)) {
        continue
    }
    $activeGaps += $line
}

$plannerEntrypoints = @(
    "PROJECT_BOOTSTRAP.md",
    "REQUIREMENTS_BASELINE.md",
    "TASKS.md",
    "PLANNER_PROMPT_TEMPLATE.md",
    "skills/planner-orchestrator/SKILL.md"
)

$md = @()
$md += "# Project Bootstrap Snapshot"
$md += ""
$md += "Generated: $generatedAt"
$md += "Purpose: Fast planner startup cache. Refresh with ``pwsh -File tools/update_bootstrap.ps1``."
$md += ""
$md += "## Repo State"
$md += "- Root: ``$repoRoot``"
$md += "- Branch: ``$branch``"
$md += "- HEAD: ``$head``"
$md += "- Dirty: ``$dirty``"
$md += ""

$md += "### Working Tree Changes"
if ($statusLines.Count -eq 0) {
    $md += "- none"
} else {
    foreach ($line in $statusLines) {
        $md += "- ``$line``"
    }
}
$md += ""

$md += "## Recently Modified Files"
if ($recentFiles.Count -eq 0) {
    $md += "- none"
} else {
    foreach ($file in $recentFiles) {
        $md += "- ``$($file.path)`` ($($file.last_write))"
    }
}
$md += ""

$md += "## Recent Commits"
if ($recentCommits.Count -eq 0) {
    $md += "- none"
} else {
    foreach ($commit in $recentCommits) {
        $md += "- ``$($commit.hash)`` $($commit.date) - $($commit.subject)"
    }
}
$md += ""

$md += "## Requirement Gap Snapshot"
if ($likelyClosed.Count -gt 0) {
    $md += "### Likely Closed (verify in baseline update)"
    foreach ($entry in $likelyClosed.GetEnumerator()) {
        $md += "- ``$($entry.Key)``: $($entry.Value)"
    }
    $md += ""
}

$md += "### Active Gaps"
if ($activeGaps.Count -eq 0) {
    $md += "- none"
} else {
    foreach ($gap in $activeGaps) {
        $md += "- $gap"
    }
}
$md += ""

$md += "## Open Task Items (`TASKS.md`)"
if ($openTaskItems.Count -eq 0) {
    $md += "- none"
} else {
    foreach ($task in $openTaskItems) {
        $md += "- $task"
    }
}
$md += ""

$md += "## Planner Entrypoints"
foreach ($entry in $plannerEntrypoints) {
    $md += "- ``$entry``"
}
$md += ""
$md += "## Incremental Update Protocol"
$md += "1. Refresh snapshot."
$md += "2. Read this file first."
$md += "3. Deep-read only files touched by new handoffs."
$md += "4. Re-run refresh after integration."
$md += ""

$mdDirectory = Split-Path -Path $OutputMarkdown -Parent
if ($mdDirectory) {
    New-Item -ItemType Directory -Path $mdDirectory -Force | Out-Null
}
Set-Content -Path $OutputMarkdown -Value $md -Encoding utf8

$jsonDirectory = Split-Path -Path $OutputJson -Parent
if ($jsonDirectory) {
    New-Item -ItemType Directory -Path $jsonDirectory -Force | Out-Null
}

$payload = [ordered]@{
    generated_at = $generatedAt
    repo = [ordered]@{
        root = $repoRoot
        branch = $branch
        head = $head
        dirty = $dirty
        status = @($statusLines)
    }
    recent_commits = $recentCommits
    recent_files = $recentFiles
    likely_closed_gaps = @($likelyClosed.GetEnumerator() | ForEach-Object {
        [ordered]@{
            id = $_.Key
            reason = $_.Value
        }
    })
    active_gaps = $activeGaps
    open_task_items = $openTaskItems
    planner_entrypoints = $plannerEntrypoints
}

$payload | ConvertTo-Json -Depth 6 | Set-Content -Path $OutputJson -Encoding utf8

Write-Output "Updated $OutputMarkdown and $OutputJson"
