#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."
DB=$(mktemp /tmp/smartstudy-cli-demo-XXXXXX.db)
trap 'rm -f "$DB"' EXIT
clear
printf 'SmartStudy | REAL CLI EXECUTION (synthetic demonstration data)\n'
printf 'All commands below execute the actual Python application.\n\n'
sleep 2
run() {
    printf '\n$ python -m smartstudy --db DEMO.db %s\n' "$*"
    python -m smartstudy --db "$DB" "$@"
    sleep 2
}
run course add EECS3311 'Software Design'
run course list
run task add 1 'Project review' --due '2026-11-20 20:00' --minutes 120 --importance 5
run task add 1 'Quiz preparation' --due '2026-11-19 18:00' --minutes 90 --importance 4
run task rank --strategy deadline
run block add 'Work shift' '2026-11-16 13:00' '2026-11-16 17:00'
run availability set 9 21
run plan week 2026-11-16
run plan week 2026-11-16 --approve
run task progress 1 60
run status
run export /tmp/smartstudy-demonstration.csv
run remind settings --enabled yes --lead-hours 48
run remind check
printf '\nDONE: this is a locally captured CLI run, not a hosted submission.\n'
sleep 25
