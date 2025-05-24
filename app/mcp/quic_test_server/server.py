from mcp.server.fastmcp import FastMCP
import os
import time
import subprocess
import dotenv
import json
import asyncio
from dataclasses import dataclass
from typing import List, Dict
from app.logger import logger

# 导入QUIC客户端函数
from .quic_file_client import run_quic_client

dotenv.load_dotenv()

# 创建 MCP 服务器
mcp = FastMCP("QUIC 网络测试服务器")

@dataclass
class QuicTestResult:
    download_times: List[float]
    throughput_list: List[float]
    average_download_time: float
    average_throughput: float
    config_path: str
    file_name: str

@mcp.tool()
async def run_quic_test(
    config_path: str,
    file_name: str,
    save_name: str,
    rtt: int,
    loss: float
) -> str:
    """运行 QUIC 传输测试，模拟特定网络环境进行性能测试

    Args:
        config_path: 客户端 QUIC 配置文件路径（绝对路径）
        file_name: 要下载的测试文件路径
        save_name: 下载文件的保存名称
        rtt: 模拟的网络往返时延，单位ms，范围0-1000
        loss: 模拟的网络丢包率，单位%，范围0-100

    Returns:
        str: 包含测试结果的格式化字符串，包括:
            - 平均下载时间(秒)
            - 平均吞吐量(MB/s) 
            - 每次测试的具体数据
    """

    # 加载配置文件
    try:
        with open(config_path, 'r') as f:
            config_dict = json.load(f)
    except Exception as e:
        return f"[ERROR] 无法加载配置文件 {config_path}: {e}"

    # 服务器信息
    host = "118.89.124.177"  # 默认服务器地址
    port = 4433  # 默认端口

    # 1. 设置网络模拟 (RTT + 丢包)
    os.system("sudo tc qdisc del dev eth0 root 2>/dev/null || true")  # 清除旧规则
    os.system(f"sudo tc qdisc add dev eth0 root netem delay {rtt}ms loss {loss}%")

    download_time_list = []
    for i in range(10):
        # 2. 运行一次下载测试，失败时重试直到成功
        logger.info(f"\n第{i+1}次下载开始")
        
        # 重试机制：失败时重新尝试直到成功
        download_success = False
        retry_count = 0
        
        while not download_success:
            if retry_count > 0:
                logger.info(f"第{i+1}次下载重试第{retry_count}次")
            
            start_time = time.time()
            
            # 直接调用QUIC客户端函数而不是subprocess
            try:
                success = await run_quic_client(
                    host=host,
                    port=port,
                    action="download",
                    file_path=file_name,
                    save_path=save_name,
                    config_dict=config_dict
                )
                if success:
                    download_success = True
                    end_time = time.time()
                    # 3. 计算下载时间
                    download_time = end_time - start_time
                    logger.info(f"第{i+1}次下载成功，下载时间: {download_time:.3f}s")
                    if retry_count > 0:
                        logger.info(f"经过{retry_count}次重试后成功")
                    download_time_list.append(download_time)
                else:
                    logger.error(f"第{i+1}次下载失败，准备重试...")
                    retry_count += 1
                    # 清理可能存在的不完整文件
                    if os.path.exists(save_name):
                        os.remove(save_name)
                    # 短暂等待后重试
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"第{i+1}次下载时发生错误: {e}，准备重试...")
                retry_count += 1
                # 清理可能存在的不完整文件
                if os.path.exists(save_name):
                    os.remove(save_name)
                # 短暂等待后重试
                await asyncio.sleep(1)

    average_download_time = sum(download_time_list) / len(download_time_list)

    # 4. 获取文件大小（MB）
    if os.path.exists(save_name):
        file_size = os.path.getsize(save_name) / (1024 * 1024)  # 转换为 MB
        throughput_list = []
        for download_time in download_time_list:
            throughput = file_size / download_time  # 计算吞吐率 MB/s
            throughput_list.append(throughput)
        average_throughput = sum(throughput_list) / len(throughput_list)
        #删除下载的文件
        os.remove(save_name)
    else:
        return "[ERROR] 下载文件不存在，可能下载失败"

    # 5. 清除网络模拟规则
    os.system("sudo tc qdisc del dev eth0 root")

    result = QuicTestResult(
        download_times=download_time_list,
        throughput_list=throughput_list,
        average_download_time=average_download_time,
        average_throughput=average_throughput,
        config_path=config_path,
        file_name=file_name
    )

    return f"""
测试完成:
- 配置文件: {result.config_path}
- 下载文件: {result.file_name}
- 平均下载时间: {result.average_download_time:.3f}s
- 平均吞吐量: {result.average_throughput:.3f} MB/s
- 每次下载时间: {result.download_times}
- 每次吞吐量: {result.throughput_list}
"""

@mcp.resource("quic://test/config")
def get_default_config() -> str:
    """获取默认的QUIC测试配置"""
    return """
默认QUIC测试配置:
- 配置文件: Quic_default_config.json
- 测试文件: testfile_1M
- RTT: 200ms
- 丢包率: 10%
"""

if __name__ == "__main__":
    mcp.run(transport='stdio') 