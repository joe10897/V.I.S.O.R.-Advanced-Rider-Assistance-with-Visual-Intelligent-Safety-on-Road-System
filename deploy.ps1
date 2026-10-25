# V.I.S.O.R. 一鍵程式碼與腳本快速同步工具 (Windows PowerShell SSH Push)
param (
    [string]$pi_host = "192.168.4.1"
)

$pi_user = "pi5"
$pi_dir  = "/home/pi5/motorcycle_assist"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "   V.I.S.O.R. 快速程式碼推播 (SSH Push -> $pi_host)" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. 確保遠端目錄存在
Write-Host "[1/3] 檢查遠端目錄結構..." -ForegroundColor Yellow
ssh -o StrictHostKeyChecking=no "$pi_user@$pi_host" "mkdir -p $pi_dir/scripts $pi_dir/vision $pi_dir/hud $pi_dir/communication $pi_dir/YOLOv26_DEMO"

# 2. 推播更新腳本與程式碼
Write-Host "[2/3] 正在推播最新版啟動腳本、鏡頭驅動與主控程式..." -ForegroundColor Yellow
$dest = "$pi_user@$pi_host`:$pi_dir/"

scp -o StrictHostKeyChecking=no run.sh ${dest}
scp -o StrictHostKeyChecking=no visor.service ${dest}
scp -o StrictHostKeyChecking=no config.json ${dest}
scp -o StrictHostKeyChecking=no main_controller.py ${dest}
scp -o StrictHostKeyChecking=no vision/frame_reader.py ${dest}vision/
scp -o StrictHostKeyChecking=no scripts/diag_dual_usb.py ${dest}scripts/
scp -o StrictHostKeyChecking=no scripts/install_service.sh ${dest}scripts/
scp -o StrictHostKeyChecking=no YOLOv26_DEMO/engine_cv_lane.py ${dest}YOLOv26_DEMO/
scp -o StrictHostKeyChecking=no YOLOv26_DEMO/spatial_fusion.py ${dest}YOLOv26_DEMO/

# 3. 設定權限並重啟服務
Write-Host "[3/3] 設定執行權限並重啟 visor.service..." -ForegroundColor Yellow
ssh -o StrictHostKeyChecking=no "$pi_user@$pi_host" "chmod +x $pi_dir/run.sh $pi_dir/scripts/diag_dual_usb.py $pi_dir/scripts/install_service.sh && sudo systemctl daemon-reload && sudo systemctl restart visor.service && sudo systemctl status visor.service --no-pager -n 12"

Write-Host "==================================================" -ForegroundColor Green
Write-Host "   [SUCCESS] 最新腳本已全部推播完成，服務已重啟！" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
