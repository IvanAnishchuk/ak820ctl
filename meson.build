# Meson build file for test orchestration with Ninja
#
# Setup:
#   uv run meson setup builddir          # Configure (once)
#
# Tests:
#   uv run ninja -C builddir             # Run default targets (test + lint + typecheck)
#   uv run meson test -C builddir --list            # List all tests
#   uv run meson test -C builddir --suite fast      # Run fast suite
#   uv run meson test -C builddir unit -v           # Single test, verbose
#
# Reports (cached, flat outputs in builddir/):
#   uv run ninja -C builddir pytest-junit.xml       # Test results + coverage
#   uv run ninja -C builddir ruff-check.txt         # Lint: all formats
#   uv run ninja -C builddir ruff-security.txt      # Lint: S+BLE rules only
#   uv run ninja -C builddir ruff-format.log        # Lint: format check
#   uv run ninja -C builddir ty-check.txt           # Type check: ty
#   uv run ninja -C builddir mypy-strict.txt        # Type check: mypy strict
#   uv run ninja -C builddir pyright-recommended.txt # Type check: basedpyright
#   uv run ninja -C builddir requirements           # Lock export + SBOM
#
# Mutation testing:
#   uv run ninja -C builddir mutmut                 # Run mutmut

project(
  'ak820ctl-tests',
  version: '0.1.0',
  meson_version: '>= 1.1.0',
)

src_root = meson.project_source_root()
build_root = meson.project_build_root()

uv = find_program('uv')
bash = find_program('bash')

# ── Tests ──────────────────────────────────────────────────────────────────

custom_target(
  'test-unit',
  output: ['pytest-junit.xml', 'pytest.log'],
  command: [
    bash, '-c',
    '''cd @0@
uv run pytest tests/ -v \
  --junitxml=@1@/pytest-junit.xml \
  --cov=ak820ctl \
  --cov-config=pyproject.toml \
  --cov-report=term-missing \
  --cov-report=xml:@1@/coverage.xml \
  2>&1 | tee @1@/pytest.log
'''.format(src_root, build_root),
  ],
  build_always_stale: true,
  console: true,
)

test(
  'unit',
  bash, args: ['-c', 'cd @0@ && uv run pytest tests/ -v --no-cov'.format(src_root)],
  suite: ['tests', 'fast'],
  timeout: 60,
  workdir: src_root,
)

# ── Lint: ruff check ───────────────────────────────────────────────────────

custom_target(
  'ruff-check',
  output: [
    'ruff-check.txt',
    'ruff-check.json',
    'ruff-check.sarif.json',
  ],
  command: [
    bash, '-c',
    '''cd @0@
uv run ruff check --output-format=concise src/ tests/ > @1@/ruff-check.txt 2>&1; rc=$?
uv run ruff check --output-format=json    src/ tests/ > @1@/ruff-check.json 2>&1 || true
uv run ruff check --output-format=sarif   src/ tests/ > @1@/ruff-check.sarif.json 2>&1 || true
cat @1@/ruff-check.txt
exit $rc
'''.format(src_root, build_root),
  ],
  build_always_stale: true,
  console: true,
)

test(
  'ruff',
  bash, args: ['-c', 'cd @0@ && uv run ruff check src/ tests/'.format(src_root)],
  suite: ['lint', 'fast'],
  timeout: 30,
  workdir: src_root,
)

# ── Lint: ruff security rules ──────────────────────────────────────────────

custom_target(
  'ruff-security',
  output: [
    'ruff-security.txt',
    'ruff-security.json',
    'ruff-security.sarif.json',
  ],
  command: [
    bash, '-c',
    '''cd @0@
uv run ruff check --select S,BLE,TRY --output-format=concise src/ > @1@/ruff-security.txt 2>&1; rc=$?
uv run ruff check --select S,BLE,TRY --output-format=json    src/ > @1@/ruff-security.json 2>&1 || true
uv run ruff check --select S,BLE,TRY --output-format=sarif   src/ > @1@/ruff-security.sarif.json 2>&1 || true
cat @1@/ruff-security.txt
exit $rc
'''.format(src_root, build_root),
  ],
  console: true,
  build_by_default: false,
)

# ── Lint: ruff format ──────────────────────────────────────────────────────

custom_target(
  'ruff-format',
  output: ['ruff-format.log'],
  command: [
    bash, '-c',
    '''cd @0@
uv run ruff format --check --diff src/ tests/ 2>&1 | tee @1@/ruff-format.log
'''.format(src_root, build_root),
  ],
  build_always_stale: true,
  console: true,
)

test(
  'ruff-format',
  bash, args: ['-c', 'cd @0@ && uv run ruff format --check src/ tests/'.format(src_root)],
  suite: ['lint', 'fast'],
  timeout: 30,
  workdir: src_root,
)

# ── Type check: ty ─────────────────────────────────────────────────────────

custom_target(
  'ty-check',
  output: ['ty-check.txt'],
  command: [
    bash, '-c',
    '''cd @0@
uv run ty check 2>&1 | tee @1@/ty-check.txt
'''.format(src_root, build_root),
  ],
  build_always_stale: true,
  console: true,
)

test(
  'ty',
  bash, args: ['-c', 'cd @0@ && uv run ty check'.format(src_root)],
  suite: ['typecheck', 'fast'],
  timeout: 60,
  workdir: src_root,
)

# ── Type check: mypy ──────────────────────────────────────────────────────

custom_target(
  'mypy-strict',
  output: ['mypy-strict.txt'],
  command: [
    bash, '-c',
    '''cd @0@
uv run mypy src/ 2>&1 | tee @1@/mypy-strict.txt
'''.format(src_root, build_root),
  ],
  build_always_stale: true,
  console: true,
)

test(
  'mypy',
  bash, args: ['-c', 'cd @0@ && uv run mypy src/'.format(src_root)],
  suite: ['typecheck', 'fast'],
  timeout: 60,
  workdir: src_root,
)

# ── Type check: basedpyright ──────────────────────────────────────────────

custom_target(
  'pyright-recommended',
  output: ['pyright-recommended.txt'],
  command: [
    bash, '-c',
    '''cd @0@
uv run basedpyright src/ 2>&1 | tee @1@/pyright-recommended.txt
'''.format(src_root, build_root),
  ],
  build_always_stale: true,
  console: true,
)

test(
  'basedpyright',
  bash, args: ['-c', 'cd @0@ && uv run basedpyright src/'.format(src_root)],
  suite: ['typecheck', 'fast'],
  timeout: 60,
  workdir: src_root,
)

# ── Mutation testing ──────────────────────────────────────────────────────

custom_target(
  'mutmut-artifacts',
  output: ['mutmut'],
  command: [
    bash, '-c',
    '''cd @0@
d="@1@/mutmut"
rm -rf "$d"
mkdir -p "$d"
uv run mutmut run --max-children 4 2>&1 | tee "$d/run.log"; echo "  mutmut: exit ${PIPESTATUS[0]}"
uv run mutmut results --all true > "$d/results-all.txt" 2>&1 || true
uv run mutmut results > "$d/results-survived.txt" 2>&1 || true
cat "$d/results-survived.txt"
echo ""
echo "mutmut artifacts in $d/"
'''.format(src_root, build_root),
  ],
  console: true,
  build_by_default: false,
)

test(
  'mutmut',
  bash, args: ['-c', 'cd @0@ && uv run mutmut run --max-children 4'.format(src_root)],
  suite: ['mutation'],
  timeout: 600,
  is_parallel: false,
  workdir: src_root,
)

# ── Requirements export + SBOM ─────────────────────────────────────────────

custom_target(
  'requirements',
  output: [
    'requirements.txt',
    'requirements-dev.txt',
  ],
  command: [
    bash, '-c',
    '''cd @0@
uv export --format requirements-txt --no-emit-project --no-dev > @1@/requirements.txt
uv export --format requirements-txt --no-emit-project          > @1@/requirements-dev.txt
echo "Exported requirements to @1@/"
'''.format(src_root, build_root),
  ],
  console: true,
  build_by_default: false,
)

# ── Clean reports ──────────────────────────────────────────────────────────

run_target(
  'clean-reports',
  command: [
    bash, '-c',
    'rm -f @0@/ruff-*.txt @0@/ruff-*.json @0@/ty-*.txt @0@/mypy-*.txt @0@/pyright-*.txt @0@/pytest-*.xml @0@/pytest.log @0@/coverage.xml'.format(build_root),
  ],
)
