# Whisper Workspace

集中管理 Whisper STT 备份服务相关的部署脚本、文档与测试，保持主项目根目录干净。

## 目录概览
- `modal/`: Whisper 模型 + FastAPI WebSocket wrapper（`modal_whisper_stt.py`）。
- `tests/`: 专门的 Whisper 服务与降级逻辑验证脚本。
- `docs/`: 运行步骤（`DEPLOYMENT_GUIDE.md`）、启动说明、实现总结（`SYSTEM_STARTUP_GUIDE.md`、`WHISPER_STT_IMPLEMENTATION_SUMMARY.md`）。

## 典型流程
1. `modal deploy modal_whisper_stt.py` 部署 Whisper 服务并记录返回的 `/ws/stt` URL。
2. 更新根目录 `.env` 的 `WHISPER_SERVICE_URL`+`WHISPER_API_KEY`。
3. 主后端通过 `backend/stt` 路由按顺序使用 AssemblyAI → Whisper。
4. 文档（`docs/DEPLOYMENT_GUIDE.md`）中包含触发条件、注意事项与监控点。

