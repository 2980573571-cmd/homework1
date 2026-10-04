@echo off
chcp 65001 >nul
rem ============================================================
rem  Code Explanation Agent - 网页版一键启动脚本
rem  双击本文件即可启动服务并自动打开浏览器
rem ============================================================
cd /d "%~dp0"

rem 后台等待 2 秒后打开浏览器（此时服务已就绪）
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8000"

rem 使用虚拟环境里的 Python 启动服务
".venv\Scripts\python.exe" app.py

rem 服务退出后暂停，便于查看报错信息
echo.
echo 服务已停止。若上面出现报错，请检查 .env 是否配置了 LLM_API_KEY。
pause
