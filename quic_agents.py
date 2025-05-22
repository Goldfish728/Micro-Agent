from typing import Dict, Any, Optional, List
import asyncio
import os
import json
import sys
from app.logger import logger
from app.utils.visualize_record import save_record_to_json, generate_visualization_html, generate_multi_agent_visualization_html
from app.agent.mcp import MCPAgent
from app.schema import Message, AgentState
from run_mcp import MCPRunner
from app.config import PROJECT_ROOT

class MultiAgentSystem:
    """多智能体系统，管理多个MCPAgent智能体之间的协作"""
    def __init__(self):
        self.agents: Dict[str, MCPAgent] = {}
        self.agent_prompt: Dict[str, str] = {}
        self.agent_memories: Dict[str, List[Message]] = {}  # 存储每个智能体的历史记忆
        self.workflow_history: List[Dict[str, Any]] = []
        self.handoff_info: Dict[str, Any] = {}  # 存储智能体之间传递的信息，从handoff.json文件读取
        self.current_agent_name: Optional[str] = None
        
    def register_agent(self, agent: MCPAgent, prompt: str):
        """注册智能体"""
        self.agents[agent.name] = agent
        self.agent_prompt[agent.name] = prompt
        self.agent_memories[agent.name] = []  # 初始化智能体记忆
        
    def _extract_last_thought(self, result: Any) -> str:
        """从智能体的结果中提取最后一个思考内容"""
        if isinstance(result, list) and result:
            last_step = result[-1]
            if isinstance(last_step, dict):
                thought = last_step.get("thought", "")
                return thought
        return str(result)
    
    def _save_agent_memory(self, agent_name: str):
        """保存智能体的记忆"""
        if agent_name in self.agents:
            agent = self.agents[agent_name]
            if hasattr(agent, 'memory') and agent.memory:
                # 保存当前记忆
                self.agent_memories[agent_name] = agent.memory.messages.copy()
                logger.info(f"已保存智能体 {agent_name} 的记忆，共 {len(self.agent_memories[agent_name])} 条消息")
    
    def _restore_agent_memory(self, agent_name: str):
        """恢复智能体的记忆"""
        if agent_name in self.agents and agent_name in self.agent_memories:
            agent = self.agents[agent_name]
            # 恢复前，确保智能体有系统提示
            has_system_prompt = False
            if agent.memory.messages and len(agent.memory.messages) > 0 and agent.memory.messages[0].role == "system":
                has_system_prompt = True
                system_prompt = agent.memory.messages[0].content
            
            # 恢复记忆
            if self.agent_memories[agent_name]:
                agent.memory.messages = self.agent_memories[agent_name].copy()
                logger.info(f"已恢复智能体 {agent_name} 的记忆，共 {len(agent.memory.messages)} 条消息")
                
                # 如果没有系统提示，但之前保存了，则添加
                if not has_system_prompt and len(agent.memory.messages) > 0 and agent.memory.messages[0].role != "system" and agent.system_prompt:
                    agent.memory.messages.insert(0, Message.system_message(agent.system_prompt))
        
    def _read_handoff_file(self):
        """从handoff.json文件读取交接信息"""
        try:
            handoff_file = f"{PROJECT_ROOT}/handoff.json"
            if os.path.exists(handoff_file):
                with open(handoff_file, "r", encoding="utf-8") as f:
                    self.handoff_info = json.load(f)
                    logger.info(f"从文件加载交接信息: {self.handoff_info}")
        except Exception as e:
            logger.error(f"读取交接文件时出错: {str(e)}")
    
    async def run_workflow(self, initial_agent_name: str, initial_input: Optional[str] = None, max_iterations: int = 10):
        """运行工作流"""
        if initial_agent_name not in self.agents:
            raise ValueError(f"找不到初始智能体: {initial_agent_name}")
            
        try:
            current_agent_name = initial_agent_name
            iteration = 0
            
            # 工作流开始前先读取可能存在的交接文件
            self._read_handoff_file()
            
            while current_agent_name and iteration < max_iterations:
                # 获取当前智能体
                current_agent = self.agents[current_agent_name]
                
                # 更新当前智能体名称
                self.current_agent_name = current_agent_name
                
                # 首先恢复智能体的记忆状态
                self._restore_agent_memory(current_agent_name)
                
                logger.info(f"第 {iteration+1} 轮: {current_agent_name} 智能体开始工作，记忆条数: {len(current_agent.memory.messages)}")
                
                # 如果有交接信息，添加为用户消息
                if self.handoff_info and self.handoff_info.get("to_agent") == current_agent_name:
                    from_agent = self.handoff_info.get("from_agent", "Unknown")
                    handoff_content = self.handoff_info.get("content", "")
                    user_message = f"【来自 {from_agent} 的交接信息】\n\n{handoff_content}"
                    current_agent.memory.add_message(Message.user_message(user_message))
                
                # 清除前一个智能体可能留下的状态
                if current_agent.state == AgentState.FINISHED:
                    current_agent.state = AgentState.IDLE
                
                # 运行当前智能体
                start_time = asyncio.get_event_loop().time()
                # 如果是第一个智能体的第一次运行，使用initial_input
                prompt = initial_input if iteration == 0 and current_agent_name == initial_agent_name and initial_input else self.agent_prompt[current_agent_name]
                result = await current_agent.run(prompt)
                end_time = asyncio.get_event_loop().time()
                
                # 保存智能体的当前记忆
                self._save_agent_memory(current_agent_name)
                
                # 智能体执行完成后立即读取可能更新的交接文件
                self._read_handoff_file()
                
                # 记录执行历史
                step_record = {
                    "iteration": iteration,
                    "agent_name": current_agent_name,
                    "memory_size": len(current_agent.memory.messages),
                    "handoff_info": self.handoff_info.copy() if self.handoff_info else None,
                    "output": result,
                    "execution_time": end_time - start_time
                }
                self.workflow_history.append(step_record)
                
                # 检查智能体状态
                if current_agent.state == AgentState.FINISHED:
                    logger.info(f"智能体 {current_agent_name} 已完成任务，状态为 FINISHED")
                    
                    # 检查交接信息中是否有下一个智能体
                    if self.handoff_info and self.handoff_info.get("from_agent") == current_agent_name:
                        next_agent_name = self.handoff_info.get("to_agent")
                        if next_agent_name and next_agent_name in self.agents:
                            # 更新迭代和当前智能体
                            current_agent_name = next_agent_name
                        else:
                            logger.info(f"工作流结束: 没有找到下一个智能体 {next_agent_name}")
                            current_agent_name = None
                    else:
                        logger.info("工作流结束: 智能体已完成并且没有指定下一个智能体")
                        current_agent_name = None
                else:
                    # 确定下一个智能体
                    next_agent_name = self._determine_next_agent(current_agent_name)
                    
                    # 更新迭代和当前智能体
                    current_agent_name = next_agent_name
                
                iteration += 1
                
                # 如果没有下一个智能体，结束工作流
                if not current_agent_name:
                    logger.info("工作流完成")
                    break
                
            return self.workflow_history
        except Exception as e:
            logger.error(f"运行工作流时出错: {str(e)}", exc_info=True)
            raise
    
    def _determine_next_agent(self, current_agent_name: str) -> Optional[str]:
        """确定下一个执行的智能体"""
        # 先从文件中读取最新的交接信息
        self._read_handoff_file()
        
        # 检查handoff信息中的下一个智能体
        if self.handoff_info and self.handoff_info.get("from_agent") == current_agent_name:
            next_agent = self.handoff_info.get("to_agent")
            if next_agent and next_agent in self.agents:
                return next_agent
            
        return None

async def run_quic_multi_agent_system():
    """运行QUIC多智能体系统示例"""
    try:
        # 创建多智能体系统
        system = MultiAgentSystem()
        
        # 智能体的提示词
        work_dir = f"{PROJECT_ROOT}/quic_project"
        
        team_description = f"""
        这是一个包含两个智能体的团队，分别是quic_developer和quic_tester。
        
        团队任务：给出quic客户端配置方案，使得在100ms时延，10%丢包率下，下载性能优于默认配置文件。
        
        背景信息：
        - quic协议是一个传输层协议，aioquic是该协议的python实现
        - 项目文件路径是{work_dir}， 生成的文件需放在{work_dir}文件夹下
        - quic客户端是文件quic_file_client.py，它默认加载Quic_default_config.json文件作为配置参数
        - 测试任务是quic客户端从quic服务器下载文件，文件名为testfile_1M，quic服务器运行在118.89.124.177:4433
        - 测试时模拟时延100ms，丢包率10%
        
        注意：禁止阅读aioquic源码
        """
        
        developer_description = """
        你是团队的quic_developer，需要根据团队的任务，给出quic客户端的配置方案（使用json_saver保存为.json文件）。当你收到quic_tester的反馈时，如果不满足要求，需要再次进行优化。
        """
        
        tester_description = """
        你是团队的quic_tester，当你收到quic_developer给出的配置方案后，需要对方案进行性能测试，并把测试结果反馈给quic_developer。
        """
        
        # 创建开发者智能体
        developer_runner = MCPRunner("quic_developer")
        await developer_runner.add_server(
            connection_type="stdio",
            server_url=None,
            command=None,
            args=None,
            server_id="developer_stdio_built_in"
        )
        
        # 创建测试者智能体
        tester_runner = MCPRunner("quic_tester")
        await tester_runner.add_server(
            connection_type="stdio",
            server_url=None,
            command=None,
            args=None,
            server_id="tester_stdio_built_in"
        )
        
        # 设置智能体名称
        developer_agent = developer_runner.agent
        developer_agent.name = "quic_developer"
        
        tester_agent = tester_runner.agent
        tester_agent.name = "quic_tester"
        
        # 注册智能体
        system.register_agent(developer_agent, team_description + "\n\n" + developer_description)
        system.register_agent(tester_agent, team_description + "\n\n" + tester_description)
        
        # 设置初始输入
        work_dir = f"{PROJECT_ROOT}/quic_project"
        
        # 运行工作流
        logger.info("启动QUIC多智能体系统工作流")
        history = await system.run_workflow("quic_developer")
        
        # 保存结果
        task_name = "quic_multi_agent"
        result = json.dumps(history, ensure_ascii=False, indent=4)
        save_record_to_json(task_name, result)
        generate_multi_agent_visualization_html(task_name)
        
        logger.info(f"已完成 {task_name} 任务，结果已保存")
        
        # 清理资源
        await developer_runner.cleanup()
        await tester_runner.cleanup()
        
        #删除交接信息
        os.remove(f"{PROJECT_ROOT}/handoff.json")
        
        return history
    except Exception as e:
        logger.error(f"运行多智能体系统时出错: {str(e)}", exc_info=True)
        sys.exit(1)

async def run_code_multi_agent_system():
    """运行代码多智能体系统示例"""
    try:
        # 创建多智能体系统
        system = MultiAgentSystem()
        
        # 创建开发者智能体
        developer_runner = MCPRunner("代码开发智能体")
        await developer_runner.add_server(
            connection_type="stdio",    
            server_url=None,
            command=None,
            args=None,
            server_id="developer_stdio_built_in"
        )
        
        # 创建测试者智能体
        tester_runner = MCPRunner("代码测试智能体") 
        await tester_runner.add_server(
            connection_type="stdio",
            server_url=None,
            command=None,
            args=None,
            server_id="tester_stdio_built_in"
        )
        
        # 智能体的提示词
        team_description = """
        这是一个包含两个智能体的团队，团队成员分别是developer_agent和tester_agent。你们要合作完成编程任务。任务是：题目：计算第 n 个斐波那契数（从 0 或 1 开始）。示例：输入：n = 10 输出：55。
        """
        
        developer_description = """
        你是团队的developer_agent，需要根据团队的任务，给出python代码实现。当你完成代码编写后，需要交给tester_agent进行测试。如果你收到tester_agent的修改建议，需要根据建议进行修改。
        """

        tester_description = """
        你是团队的tester_agent，当你收到developer_agent给出的代码实现后，需要对代码进行健壮性和时空复杂度测试。如果代码不能通过测试，或存在优化空间，需要给出修改建议，并交给developer_agent来修改。
        """
        # 设置智能体名称
        developer_agent = developer_runner.agent
        developer_agent.name = "developer_agent"
        
        tester_agent = tester_runner.agent
        tester_agent.name = "tester_agent"
        
        # 注册智能体

        system.register_agent(developer_agent, team_description + "\n\n" + developer_description)
        system.register_agent(tester_agent, team_description + "\n\n" + tester_description)
        
        # 运行工作流
        logger.info("启动代码多智能体系统工作流")
        history = await system.run_workflow("developer_agent")   
        
        # 保存结果
        task_name = "code_multi_agent_modhtml"
        result = json.dumps(history, ensure_ascii=False, indent=4)
        save_record_to_json(task_name, result)
        generate_multi_agent_visualization_html(task_name)  
        
        logger.info(f"已完成 {task_name} 任务，结果已保存")
        
        # 清理资源
        await developer_runner.cleanup()
        await tester_runner.cleanup()
        #删除交接信息
        os.remove(f"{PROJECT_ROOT}/handoff.json")
        return history
    except Exception as e:
        logger.error(f"运行代码多智能体系统时出错: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_quic_multi_agent_system())