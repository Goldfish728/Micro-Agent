from run_mcp import MCPRunner
import asyncio
import sys
import json
from app.logger import logger
from app.utils.visualize_record import save_record_to_json, generate_visualization_html

async def run_agent(task_name: str, prompt: str) -> None:
    """
    执行特定任务的智能体的主入口点。
    
    参数:
        task_name: 任务名称，用于生成JSON和HTML文件名
        prompt: 任务的prompt
    """
    agent_name = f'{task_name.replace("_", " ").capitalize()} Agent'
    runner = MCPRunner(agent_name)
    result = ""
    try:
        await runner.initialize("stdio", None)
        result = await runner.agent.run(prompt)
        result = json.dumps(result, ensure_ascii=False, indent=4)
        # 保存JSON记录文件
        save_record_to_json(task_name, result)
            
        # 生成可视化HTML文件
        generate_visualization_html(task_name)
        
        logger.info(f"已完成 {task_name} 任务，结果已保存")

    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"运行MCPAgent时出错: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    # from app.prompt.task import CODE_ANALYSIS_PROMPT, SERVICE_PACKAGING_PROMPT, REMOTE_DEPLOY_PROMPT

    # task_name = ["code_analysis", "service_packaging", "remote_deploy"]
    # prompt = [CODE_ANALYSIS_PROMPT, SERVICE_PACKAGING_PROMPT, REMOTE_DEPLOY_PROMPT]

    # for task, prompt in zip(task_name, prompt):
    #     asyncio.run(run_agent(task, prompt))

    prompt = """quic协议是一个传输层协议，aioquic是该协议的python实现。

    项目文件路径是/app/quic_project，内有两个文件夹/client和/ai_generate。
    client文件夹内含两个文件，quic客户端是文件quic_file_client.py，它默认加载Quic_default_config.json文件作为配置参数。
    你生成的文件请放在/ai_generate文件夹下。

    测试任务是quic客户端从quic服务器下载文件,文件名为testfile_10M，quic服务器运行在118.89.124.177:4433。
    现在模拟到服务器单向时延100ms，丢包率10%，你需要根据网络和应用特点，确定该场景下的配置文件，使得下载速度优于默认参数。
    请给出你的推理过程，并给出最终的配置参数。请注意，禁止阅读aioquic源码。
"""
    asyncio.run(run_agent("quic_download", prompt))

