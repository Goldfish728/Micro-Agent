import os
from app.logger import logger

from app.config import TEMPLATE_ROOT, VISUALIZATION_ROOT

def save_record_to_json(task_name: str, record: str) -> None:
    """
    将记录保存到JSON文件中

    参数:
        task_name: 任务名称，用于生成JSON文件名
        record: 记录内容，JSON字符串
    """
    # 确保visualization目录存在
    os.makedirs(VISUALIZATION_ROOT, exist_ok=True)

    json_path = VISUALIZATION_ROOT / f'{task_name}_record.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        f.write(record)

def generate_visualization_html(task_name: str) -> None:
    """
    根据任务名生成可视化HTML文件，将record.html作为模板
    
    参数:
        task_name: 任务名称，用于生成HTML文件名和JSON文件名
    """
    # 确保visualization目录存在
    os.makedirs(VISUALIZATION_ROOT, exist_ok=True)
    
    # 定义文件路径
    template_path = TEMPLATE_ROOT / 'record.html'
    json_path = VISUALIZATION_ROOT / f'{task_name}_record.json'
    output_html_path = VISUALIZATION_ROOT / f'{task_name}.html'
    
    # 检查模板文件是否存在
    if not os.path.exists(template_path):
        logger.error(f"模板文件 {template_path} 不存在")
        return
    
    # 读取模板文件内容
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    # 修改模板中的JSON文件路径
    modified_content = template_content.replace(
        "const response = await fetch('record.json');",
        f"const response = await fetch('{task_name}_record.json');"
    )
    
    # 更新页面标题
    modified_content = modified_content.replace(
        "<title>Agent执行过程可视化</title>",
        f"<title>{task_name.replace('_', ' ').capitalize()} Agent执行过程可视化</title>"
    )
    
    modified_content = modified_content.replace(
        "<h1 class=\"display-4\">Agent执行过程可视化</h1>",
        f"<h1 class=\"display-4\">{task_name.replace('_', ' ').capitalize()} Agent执行过程可视化</h1>"
    )
    
    # 写入新的HTML文件
    with open(output_html_path, 'w', encoding='utf-8') as f:
        f.write(modified_content)
    
    logger.info(f"成功生成可视化HTML文件: {output_html_path}")

def generate_multi_agent_visualization_html(task_name: str) -> None:
    """
    为多智能体交互生成可视化HTML文件
    
    该函数与generate_visualization_html不同，处理的是多智能体交互的嵌套JSON结构，
    并确保每个步骤能够展示对应的agent_name
    
    参数:
        task_name: 任务名称，用于生成HTML文件名和JSON文件名
    """
    # 确保visualization目录存在
    os.makedirs(VISUALIZATION_ROOT, exist_ok=True)
    
    # 定义文件路径
    template_path = TEMPLATE_ROOT / 'record.html'
    json_path = VISUALIZATION_ROOT / f'{task_name}_record.json'
    output_html_path = VISUALIZATION_ROOT / f'{task_name}.html'
    
    # 检查文件是否存在
    if not os.path.exists(template_path):
        logger.error(f"模板文件 {template_path} 不存在")
        return
    
    if not os.path.exists(json_path):
        logger.error(f"JSON文件 {json_path} 不存在")
        return
    
    # 读取模板文件内容
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    # 准备多智能体数据处理的JavaScript代码
    multi_agent_js = f"""
    document.addEventListener('DOMContentLoaded', async function() {{
        try {{
            // 获取执行记录数据
            const response = await fetch('{task_name}_record.json');
            if (!response.ok) {{
                throw new Error('无法加载记录数据');
            }}
            const originalData = await response.json();
            
            // 将嵌套数据结构转换为扁平的步骤数组
            const recordData = [];
            for (const iteration of originalData) {{
                if (iteration.output && Array.isArray(iteration.output)) {{
                    const agentName = iteration.agent_name || '未知智能体';
                    for (const step of iteration.output) {{
                        // 将智能体名称添加到每个步骤
                        step.agent_name = agentName;
                        recordData.push(step);
                    }}
                }}
            }}
            
            // 渲染统计面板
            renderStatistics(recordData);
            
            // 渲染步骤导航
            renderNavigation(recordData);
            
            // 渲染所有步骤
            renderSteps(recordData);
            
            // 设置进度条宽度
            updateProgressBar(100);
            
            // 添加导航点击事件
            setupNavigation();

        }} catch (error) {{
            console.error('加载数据时出错:', error);
            document.getElementById('steps-container').innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i> 
                    加载数据失败: ${{error.message}}
                </div>`;
        }}
    }});
    """
    
    # 修改页面标题
    modified_content = template_content.replace(
        "<title>Agent执行过程可视化</title>",
        f"<title>{task_name.replace('_', ' ').capitalize()} Agent执行过程可视化</title>"
    ).replace(
        "<h1 class=\"display-4\">Agent执行过程可视化</h1>",
        f"<h1 class=\"display-4\">{task_name.replace('_', ' ').capitalize()} Agent执行过程可视化</h1>"
    )
    
    # 添加智能体名称到步骤标题
    modified_content = modified_content.replace(
        '<div class="step-heading mb-3">\n                        <h4>步骤 ${step.step}</h4>',
        '<div class="step-heading mb-3">\n                        <h4>步骤 ${step.step} <small class="text-muted">${step.agent_name || "未知智能体"}</small></h4>'
    )
    
    # 替换原始的DOMContentLoaded事件处理程序
    script_start = modified_content.find('<script>')
    if script_start != -1:
        script_end = modified_content.find('</script>', script_start)
        if script_end != -1:
            # 找到DOMContentLoaded事件的开始和结束位置
            dom_content_loaded_start = modified_content.find("document.addEventListener('DOMContentLoaded'", script_start, script_end)
            if dom_content_loaded_start != -1:
                function_render_statistics_start = modified_content.find("function renderStatistics", dom_content_loaded_start, script_end)
                if function_render_statistics_start != -1:
                    # 用我们的多智能体处理代码替换原始的DOMContentLoaded事件处理程序
                    modified_content = modified_content[:dom_content_loaded_start] + multi_agent_js + modified_content[function_render_statistics_start:]
    
    # 写入新的HTML文件
    with open(output_html_path, 'w', encoding='utf-8') as f:
        f.write(modified_content)
    
    logger.info(f"成功生成多智能体可视化HTML文件: {output_html_path}")