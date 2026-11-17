$ErrorActionPreference = "Stop"

function Invoke-Check {
    param([string[]]$Invocation)

    $program = $Invocation[0]
    $arguments = $Invocation | Select-Object -Skip 1
    & $program @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$($Invocation -join ' ') falló con código $LASTEXITCODE"
    }
}

Invoke-Check @('python', '-B', '-m', 'ruff', 'check', 'app', 'tests', 'main.py')
Invoke-Check @('python', '-B', '-m', 'ruff', 'format', '--check', 'app', 'tests', 'main.py')
Invoke-Check @('python', '-B', '-m', 'coverage', 'run', '-m', 'pytest', 'tests', '-q', '-p', 'no:cacheprovider')
Invoke-Check @('python', '-B', '-m', 'coverage', 'report')
Invoke-Check @('python', '-B', '-m', 'alembic', 'heads')

Push-Location frontend
try {
    Invoke-Check @('npm', 'run', 'typecheck')
    Invoke-Check @('npm', 'run', 'lint')
    Invoke-Check @('npm', 'run', 'test')
    Invoke-Check @('npm', 'run', 'build')
} finally {
    Pop-Location
}
