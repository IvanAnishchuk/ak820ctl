#!/usr/bin/env bash
# Wrapper for meson custom_target: runs pytest with coverage + JUnit artifacts.
#
# Usage: meson_pytest_wrapper.sh <src_root> <build_root> <name> [pytest_args...]
#
# Produces (meson-tracked outputs in build_root, matching custom_target output:):
#   <build_root>/pytest-junit-<name>.xml       -- JUnit XML
#   <build_root>/pytest-<name>.log             -- Full output log
# Additional artifacts (not tracked by meson):
#   <build_root>/coverage/coverage-db.<name>   -- Coverage data (binary)
#   <build_root>/coverage/coverage-<name>.xml  -- Coverage XML (Cobertura)

set -euo pipefail

src_root="$1"; shift
build_root="$1"; shift
name="$1"; shift
# Remaining args are pytest args

coverage_dir="$build_root/coverage"
mkdir -p "$coverage_dir"

# Meson expects outputs directly in build_root (matching output: declaration)
junit_xml="$build_root/pytest-junit-$name.xml"
log_file="$build_root/pytest-$name.log"
cov_file="$coverage_dir/coverage-db.$name"

echo "──────────────────────────────────────────────────────────"
echo "  $name"
echo "──────────────────────────────────────────────────────────"

export COVERAGE_FILE="$cov_file"

cd "$src_root"
uv run pytest \
    --override-ini="addopts=" \
    -q --tb=short \
    --cov=ak820ctl \
    --cov-report="xml:$coverage_dir/coverage-$name.xml" \
    --cov-report=term-missing \
    --cov-fail-under=0 \
    --junitxml="$junit_xml" \
    "$@" \
    2>&1 | tee "$log_file"

exit_code=${PIPESTATUS[0]}

echo ""
echo "  Artifacts:"
echo "    JUnit XML:  $junit_xml"
echo "    Coverage:   $cov_file"
echo "    Log:        $log_file"
echo "    Cov XML:    $coverage_dir/coverage-$name.xml"

exit $exit_code
