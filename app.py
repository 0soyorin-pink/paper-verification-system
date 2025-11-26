import os
import sys
import json
import asyncio
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 加载环境变量
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# 获取当前文件所在目录的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.join(current_dir, 'frontend')

app = Flask(__name__, static_folder=frontend_dir, static_url_path='')
CORS(app)  # 允许前端跨域访问

# 全局工作流实例
workflow = None

def initialize_workflow():
    """初始化工作流"""
    global workflow
    try:
        # 检查必要的 API 密钥
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY 环境变量未设置")
        
        from workflows.verification_workflow import VerificationWorkflow
        workflow = VerificationWorkflow()
        print("✅ 工作流初始化成功")
        return True
    except Exception as e:
        print(f"❌ 工作流初始化失败: {e}")
        return False

def get_workflow():
    """获取工作流实例，如果未初始化则进行初始化"""
    global workflow
    if workflow is None:
        if not initialize_workflow():
            raise RuntimeError("工作流初始化失败")
    return workflow

@app.route('/')
def serve_frontend():
    """服务前端主页面"""
    print("🔍 请求根路径，尝试提供 index.html")
    try:
        return send_from_directory(frontend_dir, 'index.html')
    except Exception as e:
        print(f"❌ 无法提供 index.html: {e}")
        return jsonify({"error": "前端文件未找到", "details": str(e)}), 404

@app.route('/<path:path>')
def serve_static_files(path):
    """服务前端静态文件"""
    print(f"🔍 请求静态文件: {path}")
    try:
        return send_from_directory(frontend_dir, path)
    except Exception as e:
        print(f"❌ 无法提供静态文件 {path}: {e}")
        return jsonify({"error": f"文件未找到: {path}"}), 404

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    try:
        # 检查工作流是否正常初始化
        workflow_initialized = initialize_workflow()
        
        return jsonify({
            "status": "healthy" if workflow_initialized else "degraded",
            "workflow_initialized": workflow_initialized,
            "required_apis": {
                "deepseek": bool(os.getenv("OPENAI_API_KEY")),
                "semantic_scholar": bool(os.getenv("SEMANTIC_SCHOLAR_API_KEY")),
                "baidu": bool(os.getenv("BAIDU_API_KEY"))
            },
            "frontend_directory": frontend_dir,
            "frontend_exists": os.path.exists(frontend_dir)
        })
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500

@app.route('/api/verify-single', methods=['POST'])
def verify_single():
    """
    单条验证接口 - 同步版本
    """
    try:
        data = request.get_json()
        if not data or 'reference' not in data:
            return jsonify({
                "success": False,
                "error": "缺少 'reference' 字段"
            }), 400
        
        reference = data['reference'].strip()
        if not reference:
            return jsonify({
                "success": False,
                "error": "引用内容不能为空"
            }), 400
        
        print(f"🔍 开始验证单条引用: {reference[:50]}...")
        
        # 获取工作流实例
        workflow_instance = get_workflow()
        
        # 使用同步方式处理异步函数
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(workflow_instance.run(reference))
            
            # 格式化响应
            response = {
                "success": True,
                "reference": reference,
                "result": result
            }
            
            print(f"✅ 单条验证完成: {result['status']}")
            return jsonify(response)
            
        finally:
            loop.close()
        
    except Exception as e:
        print(f"❌ 单条验证出错: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"验证过程出错: {str(e)}"
        }), 500

@app.route('/api/verify-batch', methods=['POST'])
def verify_batch():
    """
    批量验证接口 - 同步版本，避免异步问题
    """
    try:
        data = request.get_json()
        if not data or 'references' not in data:
            return jsonify({
                "success": False,
                "error": "缺少 'references' 字段"
            }), 400
        
        references = data['references']
        if not isinstance(references, list):
            return jsonify({
                "success": False,
                "error": "'references' 必须是数组"
            }), 400
        
        if len(references) == 0:
            return jsonify({
                "success": False,
                "error": "引用列表不能为空"
            }), 400
        
        print(f"🔍 开始批量验证 {len(references)} 条引用")
        
        # 获取工作流实例
        workflow_instance = get_workflow()
        
        # 使用同步方式处理
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            results = []
            for i, reference in enumerate(references):
                try:
                    print(f"📖 处理第 {i+1}/{len(references)} 条: {reference[:50]}...")
                    
                    # 同步调用异步函数
                    result = loop.run_until_complete(workflow_instance.run(reference.strip()))
                    
                    # 提取关键信息用于前端展示
                    simplified_result = {
                        "id": i,
                        "reference": reference,
                        "status": result.get("status"),
                        "type": result.get("parsed_data", {}).get("type", "unknown"),
                        "is_real": result.get("raw_data", {}).get("is_real", False),
                        "confidence": result.get("raw_data", {}).get("confidence", 0),
                        "source": result.get("raw_data", {}).get("source", ""),
                        "title": result.get("raw_data", {}).get("title", ""),
                        "authors": result.get("raw_data", {}).get("authors", ""),
                        "reason": result.get("raw_data", {}).get("reason", ""),
                        "details": result  # 包含完整详情
                    }
                    
                    results.append(simplified_result)
                    print(f"✅ 第 {i+1} 条验证完成")
                    
                except Exception as e:
                    print(f"❌ 第 {i+1} 条验证失败: {e}")
                    import traceback
                    traceback.print_exc()
                    
                    error_result = {
                        "id": i,
                        "reference": reference,
                        "status": "error",
                        "type": "unknown",
                        "is_real": False,
                        "confidence": 0,
                        "source": "",
                        "title": "",
                        "authors": "",
                        "reason": f"验证失败: {str(e)}",
                        "error": True
                    }
                    results.append(error_result)
            
            response = {
                "success": True,
                "total_count": len(references),
                "processed_count": len(results),
                "results": results
            }
            
            print(f"✅ 批量验证完成，成功处理 {len(results)} 条引用")
            return jsonify(response)
            
        finally:
            loop.close()
        
    except Exception as e:
        print(f"❌ 批量验证出错: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"批量验证过程出错: {str(e)}"
        }), 500

@app.route('/api/parse-reference', methods=['POST'])
async def parse_reference():
    """
    仅解析引用信息（不进行完整验证）
    用于测试解析器
    """
    try:
        data = request.get_json()
        if not data or 'reference' not in data:
            return jsonify({
                "success": False,
                "error": "缺少 'reference' 字段"
            }), 400
        
        reference = data['reference'].strip()
        
        # 直接使用 ParserAgent 进行解析
        from agents.parser_agent import ParserAgent
        parser = ParserAgent()
        parsed_data = parser.parse(reference)
        
        return jsonify({
            "success": True,
            "reference": reference,
            "parsed_data": parsed_data
        })
        
    except Exception as e:
        print(f"❌ 解析引用出错: {e}")
        return jsonify({
            "success": False,
            "error": f"解析过程出错: {str(e)}"
        }), 500

# 错误处理
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "error": "接口不存在"
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "success": False,
        "error": "服务器内部错误"
    }), 500

# 应用启动时的初始化
@app.before_request
def before_request():
    """在每个请求前确保工作流已初始化"""
    if workflow is None:
        initialize_workflow()

if __name__ == '__main__':
    # 初始化工作流
    try:
        if initialize_workflow():
            print("🚀 论文验证系统 API 启动成功")
            print("📍 服务地址: http://localhost:5000")
        else:
            print("⚠️ 工作流初始化失败，但服务仍将启动")
    except Exception as e:
        print(f"❌ 服务启动失败: {e}")
        sys.exit(1)
    
    # 开发模式运行
    app.run(host='0.0.0.0', port=5000, debug=True)  # 开启 debug 模式以便查看更多信息