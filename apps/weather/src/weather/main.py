import sys


def main():
    try:
        import setproctitle
        setproctitle.setproctitle("weather")
    except ImportError:
        pass
    
    from .app import app
    
    print("FastAPI Demo 应用")
    print("用法: python -m weather")
    print("然后访问: http://localhost:8000")
    print("API文档: http://localhost:8000/docs")
    
    try:
        import uvicorn
        uvicorn.run(app=app, host="0.0.0.0", port=8000)
    except ImportError:
        print("错误: 未安装 uvicorn", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
