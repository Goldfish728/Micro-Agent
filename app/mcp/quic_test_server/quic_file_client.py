import asyncio
import json
import os
import logging
import ssl
import argparse
from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration
import time
import dotenv
#禁用代理
# os.environ.pop('http_proxy', None)
# os.environ.pop('https_proxy', None)

dotenv.load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("quic_file_client")

async def list_files(connection):
    """获取服务器上的文件列表"""
    try:
        stream = await connection.create_stream()
        if stream is None:
            logger.error("无法创建流")
            return None
            
        reader, writer = stream
        
        # 发送列表请求
        request = {
            "command": "list"
        }
        writer.write(json.dumps(request).encode())
        await writer.drain()
        
        # 接收响应
        response_data = await reader.read(8192)
        response = json.loads(response_data.decode())
        
        if response.get("status") == "success":
            files = response.get("files", [])
            logger.info(f"获取到 {len(files)} 个文件")
            return files
        else:
            logger.error(f"获取文件列表失败: {response.get('message')}")
            return None
    except Exception as e:
        logger.error(f"获取文件列表时发生错误: {e}", exc_info=True)
        return None

async def upload_file(connection, file_path):
    """上传文件到服务器"""
    try:
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return False
            
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        stream = await connection.create_stream()
        if stream is None:
            logger.error("无法创建流")
            return False
            
        reader, writer = stream
        
        # 发送上传请求
        request = {
            "command": "upload",
            "file_name": file_name,
            "file_size": file_size
        }
        writer.write(json.dumps(request).encode())
        await writer.drain()
        
        # 等待服务器准备好接收
        response_data = await reader.read(1024)
        response = json.loads(response_data.decode())
        
        if response.get("status") != "ready":
            logger.error(f"服务器未准备好接收文件: {response.get('message')}")
            return False
        
        # 发送文件数据
        logger.info(f"开始上传文件: {file_name}, 大小: {file_size} 字节")
        sent_size = 0
        
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(8192)  # 每次读取8KB
                if not chunk:
                    break
                writer.write(chunk)
                await writer.drain()
                sent_size += len(chunk)
                logger.debug(f"已发送: {sent_size}/{file_size} 字节")
        
        # 接收上传结果
        result_data = await reader.read(1024)
        result = json.loads(result_data.decode())
        
        if result.get("status") == "success":
            logger.info(f"文件 {file_name} 上传成功")
            return True
        else:
            logger.error(f"文件上传失败: {result.get('message')}")
            return False
    except Exception as e:
        logger.error(f"上传文件时发生错误: {e}", exc_info=True)
        return False

async def download_file(connection, file_name, save_path=None):
    """从服务器下载文件"""
    try:
        stream = await connection.create_stream()
        if stream is None:
            logger.error("无法创建流")
            return False
            
        reader, writer = stream
        
        # 发送下载请求
        request = {
            "command": "download",
            "file_name": file_name
        }
        writer.write(json.dumps(request).encode())
        await writer.drain()
        
        # 接收文件信息
        info_data = await reader.read(1024)
        info = json.loads(info_data.decode())
        
        if info.get("status") != "ready":
            logger.error(f"下载文件失败: {info.get('message')}")
            return False
        
        file_size = info.get("file_size")
        logger.info(f"准备下载文件: {file_name}, 大小: {file_size} 字节")
        
        # 确定保存路径
        if save_path is None:
            save_path = file_name
        
        # 告诉服务器准备好接收
        writer.write(json.dumps({"status": "ready"}).encode())
        await writer.drain()
        
        # 接收文件数据
        received_size = 0
        
        with open(save_path, "wb") as f:
            while received_size < file_size:
                chunk = await reader.read(8192)  # 每次读取8KB
                if not chunk:
                    break
                f.write(chunk)
                received_size += len(chunk)
                logger.debug(f"已接收: {received_size}/{file_size} 字节")
        
        if received_size == file_size:
            logger.info(f"文件 {file_name} 下载完成，保存为 {save_path}")
            return True
        else:
            logger.error(f"文件下载不完整: {received_size}/{file_size} 字节")
            return False
    except Exception as e:
        logger.error(f"下载文件时发生错误: {e}", exc_info=True)
        return False

async def run_quic_client(host, port, action, file_path=None, save_path=None, config_dict=None):
    """运行QUIC客户端"""
    configuration = QuicConfiguration(is_client=True)
    
    # 如果传入了配置，则应用所有可配置的参数
    if config_dict:
        # 遍历配置字典中的所有参数
        for key, value in config_dict.items():
            # 跳过注释和空值
            if key.startswith('#') or value is None:
                continue
            # 检查参数是否存在于 QuicConfiguration 中
            if hasattr(configuration, key):
                try:
                    setattr(configuration, key, value)
                    logger.debug(f"设置配置参数 {key} = {value}")
                except Exception as e:
                    logger.warning(f"设置配置参数 {key} 失败: {e}")
    
    configuration.load_verify_locations(os.getenv("WORK_DIR") + "/cert.pem")
    try:
        async with connect(host, port, configuration=configuration) as connection:
            if action == "list":
                files = await list_files(connection)
                if files:
                    print("\n服务器上的文件列表:")
                    for i, file in enumerate(files, 1):
                        print(f"{i}. {file['name']} - {file['size']} 字节")
                    return True
                return False
            elif action == "upload":
                if not file_path:
                    logger.error("上传操作需要指定文件路径")
                    return False
                return await upload_file(connection, file_path)
            elif action == "download":
                if not file_path:
                    logger.error("下载操作需要指定文件名")
                    return False
                return await download_file(connection, file_path, save_path)
            else:
                logger.error(f"未知操作: {action}")
                return False
    except Exception as e:
        logger.error(f"QUIC客户端错误: {e}", exc_info=True)
        return False

def main():
    parser = argparse.ArgumentParser(description="QUIC文件传输客户端")
    parser.add_argument("--host", default="118.89.124.177", help="服务器主机名或IP地址")
    parser.add_argument("--port", type=int, default=4433, help="服务器端口")
    parser.add_argument("action", choices=["list", "upload", "download"], help="要执行的操作")
    parser.add_argument("--file", help="要上传的文件路径或要下载的文件名")
    parser.add_argument("--save", default="download_file", help="下载文件的保存路径")
    parser.add_argument("--config", default="quic_default_config.json", help="配置文件路径")
    
    args = parser.parse_args()
    config = json.load(open(args.config))
    success = asyncio.run(run_quic_client(
        args.host, 
        args.port, 
        args.action, 
        args.file, 
        args.save, 
        config
    ))
    
    if success:
        print("操作成功完成")
    else:
        print("操作失败")
        exit(1)

if __name__ == "__main__":
    #记录开始时间
    start_time = time.time()    
    main() 
    #记录结束时间
    end_time = time.time()
    print(f"运行时间: {end_time - start_time} 秒")