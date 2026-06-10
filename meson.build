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
#   uv run ninja -C builddir mypy-strict.txt        # Type check: mypy strict (+ any-exprs, lineprecision, linecount, linecoverage, html, txt, xml, cobertura, junit, jsonl)
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

# ── Helper: wrapper script that runs pytest and captures artifacts ─────────

wrapper = files('scripts' / 'meson_pytest_wrapper.sh')

# ── Test type definitions ─────────────────────────────────────────────────
# Each entry: {'args': [pytest_args], 'timeout': seconds, 'suites': [suites]}

test_defs = {
  'unit': {'args': ['tests/'], 'timeout': 60, 'suites': ['tests', 'fast']},
}

default_types = ['unit']

# ── Generate test targets ─────────────────────────────────────────────────

default_test_targets = []

foreach name, def : test_defs
  pytest_args = def['args']

  # custom_target: produces build artifacts (junit xml, coverage, log)
  t = custom_target(
    'test-' + name,
    output: ['pytest-junit-' + name + '.xml', 'pytest-' + name + '.log'],
    command: [
      bash, wrapper,
      src_root,
      build_root,
      name,
      pytest_args,
    ],
    build_always_stale: true,
    console: true,
    build_by_default: default_types.contains(name),
  )
  if default_types.contains(name)
    default_test_targets += t
  endif

  # test(): meson test integration (meson test --suite unit, --list, etc.)
  test(
    name,
    bash, args: [wrapper, src_root, build_root, name] + pytest_args,
    suite: def['suites'],
    timeout: def['timeout'],
    workdir: src_root,
  )
endforeach

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
# Generates the main pass/fail log plus every mypy coverage-style report:
#   mypy-strict.txt              — stdout (errors/notes/summary)
#   mypy-strict.jsonl            — -O json line-delimited results
#   mypy-strict.junit.xml        — JUnit XML
#   mypy-strict-html/            — browsable HTML coverage
#   mypy-strict-txt/             — text coverage
#   mypy-strict-xml/             — raw XML coverage
#   mypy-strict-cobertura/       — Cobertura XML (CI coverage tools, diff-cover)
#   mypy-strict-linecoverage/    — line-level type-coverage JSON
#   mypy-strict-lineprecision/   — per-line precision (any/imprecise/empty/precise)
#   mypy-strict-linecount/       — annotated vs total line counts
#   mypy-strict-any-exprs/       — count of `Any` expressions per file

custom_target(
  'mypy-strict',
  output: [
    'mypy-strict.txt', 'mypy-strict.jsonl', 'mypy-strict.junit.xml',
    'mypy-strict-html', 'mypy-strict-txt', 'mypy-strict-xml',
    'mypy-strict-cobertura', 'mypy-strict-linecoverage',
    'mypy-strict-lineprecision', 'mypy-strict-linecount', 'mypy-strict-any-exprs',
  ],
  command: [
    bash, '-c',
    '''cd @0@
d="@1@"
rm -rf "$d"/mypy-strict*
uv run mypy src/ --junit-xml "$d/mypy-strict.junit.xml" --html-report "$d/mypy-strict-html" --txt-report "$d/mypy-strict-txt" --xml-report "$d/mypy-strict-xml" --cobertura-xml-report "$d/mypy-strict-cobertura" --linecoverage-report "$d/mypy-strict-linecoverage" --lineprecision-report "$d/mypy-strict-lineprecision" --linecount-report "$d/mypy-strict-linecount" --any-exprs-report "$d/mypy-strict-any-exprs" > "$d/mypy-strict.txt"; echo "  mypy strict: exit $?"; ls -l "$d/mypy-strict.txt"
uv run mypy src/ -O json > "$d/mypy-strict.jsonl"; echo "  mypy strict json: exit $?"; ls -l "$d/mypy-strict.jsonl"
cat "$d/mypy-strict.txt"
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
  bash, args: ['-c', 'cd @0@ && uv run basedpyright src/ || true'.format(src_root)],
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
    # Run from build_root with a relative --output-file so the command-line
    # uv embeds in the header matches scripts/regen_requirements.py and the
    # dependabot-regen workflow byte-for-byte (absolute paths and stdout
    # redirection both produce different headers). uv walks up to find
    # pyproject.toml in src_root.
    '''cd @1@
uv export --format requirements-txt --no-emit-project --no-dev --output-file requirements.txt
uv export --format requirements-txt --no-emit-project          --output-file requirements-dev.txt
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
    '''rm -f @0@/ruff-*.txt @0@/ruff-*.json @0@/ty-*.txt @0@/mypy-*.txt @0@/pyright-*.txt
rm -f @0@/pytest-junit-*.xml @0@/pytest-*.log
rm -rf @0@/coverage @0@/mutmut
'''.format(build_root),
  ],
)
