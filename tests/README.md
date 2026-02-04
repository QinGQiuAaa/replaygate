# Pytest API Suite

## Windows PowerShell 快速开始

1) 创建虚拟环境并安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r tests\requirements.txt
```

2) 设置 API 地址（可选）

```powershell
$env:RG_API_BASE="http://localhost:8080"
$env:RG_GATEWAY_BASE="http://localhost:8000"
$env:RG_GATEWAY_DOCKER_URL="http://flashsale-gateway:8000"
```

3) 运行测试

```powershell
pytest -q tests\api
```

并发执行（可选）：

```powershell
pytest -q -n auto tests\api
```
