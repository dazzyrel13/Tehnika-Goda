# Backup Postgres from the running Docker DB container (Windows PowerShell).
# Usage:  .\scripts\backup.ps1
#         .\scripts\backup.ps1 -BackupMedia
param(
    [string]$DbContainer = "tehnikagoda_db",
    [string]$WebContainer = "tehnikagoda_web",
    [string]$BackupDir = "",
    [int]$KeepDays = 14,
    [switch]$BackupMedia
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not $BackupDir) { $BackupDir = Join-Path $Root "backups" }
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$PgDb = (docker exec $DbContainer printenv POSTGRES_DB).Trim()
$PgUser = (docker exec $DbContainer printenv POSTGRES_USER).Trim()
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Dump = Join-Path $BackupDir "pg_${PgDb}_${Stamp}.sql.gz"

Write-Host "Dumping $PgDb from $DbContainer -> $Dump"
# Write gzip inside the container so PowerShell cannot re-encode the dump.
docker exec $DbContainer sh -c "pg_dump -U `"$PgUser`" -d `"$PgDb`" --no-owner --no-acl | gzip -c > /tmp/tg_backup.sql.gz"
docker cp "${DbContainer}:/tmp/tg_backup.sql.gz" $Dump
docker exec $DbContainer rm -f /tmp/tg_backup.sql.gz

if ($BackupMedia) {
    $mediaTar = Join-Path $BackupDir "media_$Stamp.tar.gz"
    $mediaPath = Join-Path $Root "media"
    if (Test-Path $mediaPath) {
        tar -czf $mediaTar -C $Root media
        Write-Host "Archived media -> $mediaTar"
    } else {
        Write-Host "media/ not on host; copying from $WebContainer volume"
        docker run --rm --volumes-from $WebContainer -v "${BackupDir}:/backup" alpine:3.20 `
            tar -czf "/backup/media_$Stamp.tar.gz" -C /usr/src/app media
        Write-Host "Archived media -> $mediaTar"
    }
}

Get-ChildItem $BackupDir -File | Where-Object {
    ($_.Name -like 'pg_*.sql*' -or $_.Name -like 'media_*.tar*') -and
    $_.LastWriteTime -lt (Get-Date).AddDays(-$KeepDays)
} | Remove-Item -Force

Write-Host "Done. Restore: gunzip -c $Dump | docker exec -i $DbContainer psql -U $PgUser -d $PgDb"
