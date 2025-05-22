from app.tool.base import BaseTool
from typing import Optional
from app.logger import logger
from app.config import PROJECT_ROOT
from app.schema import AgentState
import json

_HANDOFF_DESCRIPTION = """在完成当前任务并需要将工作交给下一个智能体时使用此工具。
通过此工具传递你的工作成果、发现和建议，以便下一个智能体能够接着你的工作继续。
"""


class Handoff(BaseTool):
    name: str = "handoff"
    description: str = _HANDOFF_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "from_agent": {
                "type": "string",
                "description": "当前智能体的ID"
            },
            "to_agent": {
                "type": "string",
                "description": "下一个智能体的ID"
            },
            "content": {
                "type": "string",
                "description": "要传递给下一个智能体的信息，包括工作成果、发现和建议"
            }
        },
        "required": ["from_agent", "to_agent", "content"],
    }


    async def execute(self, from_agent: str, to_agent: str, content: str) -> str:
        """执行交接操作，将工作从当前智能体传递给下一个智能体"""
        # 记录交接信息到文件
        handoff_info = {
            "from_agent": from_agent, 
            "to_agent": to_agent, 
            "content": content,
        }
        
        try:
            with open(f"{PROJECT_ROOT}/handoff.json", "w", encoding="utf-8") as f:
                f.write(json.dumps(handoff_info, ensure_ascii=False, indent=2) + "\n")
            logger.info(f"交接信息已保存到 {PROJECT_ROOT}/handoff.json")
        except Exception as e:
            logger.error(f"保存交接信息时出错: {str(e)}")
                        
        return f"已将任务从 {from_agent} 交接给 {to_agent}"