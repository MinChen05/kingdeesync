Set-Location -LiteralPath 'D:\Kingdee'

openspec validate analyze-current-project
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

python -m unittest tests.test_dry_run_cleanup -v
exit $LASTEXITCODE
