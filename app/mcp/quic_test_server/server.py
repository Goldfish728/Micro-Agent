from mcp.server.fastmcp import FastMCP
import os
import time
import subprocess
import dotenv
from dataclasses import dataclass
from typing import List, Dict
from app.logger import logger

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

    # 服务器信息
    CLIENT_CMD = f"python {os.getenv('WORK_DIR')}/quic_file_client.py download --file {file_name} --save {save_name} --config {config_path}"

    # 1. 设置网络模拟 (RTT + 丢包)
    os.system("sudo tc qdisc del dev eth0 root 2>/dev/null || true")  # 清除旧规则
    os.system(f"sudo tc qdisc add dev eth0 root netem delay {rtt}ms loss {loss}%")

    download_time_list = []
    for i in range(10):
        # 2. 运行一次下载测试
        start_time = time.time()
        process = subprocess.run(CLIENT_CMD, shell=True, capture_output=True, text=True)
        logger.info(process.stdout)
        logger.info(process.stderr)
        end_time = time.time()

        # 3. 计算下载时间
        download_time = end_time - start_time
        download_time_list.append(download_time)

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