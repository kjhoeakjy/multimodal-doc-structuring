#!/bin/bash
# 이전 작업(풀 1) 종료 대기 후 순차 실행
PY=.venv/Scripts/python.exe
while tasklist //FI "IMAGENAME eq python.exe" //V 2>/dev/null | grep -q python && powershell -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | ? { \$_.CommandLine -like '*run_faa.py*' }).Count" | grep -qv '^0$'; do sleep 30; done
export PYTHONIOENCODING=utf-8
$PY poc/v6/run_nist.py ASBC > poc/v6/data/log_nist.txt 2>&1
$PY poc/v5/run_extract.py scan > poc/v5/data/scan_log2.txt 2>&1
$PY poc/v5/run_qa.py digital AC > poc/v6/data/log_zone_digital.txt 2>&1
$PY poc/v5/run_qa.py scan AC > poc/v6/data/log_zone_scan.txt 2>&1
echo CHAIN_DONE
