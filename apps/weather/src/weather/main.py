import uvicorn


def main():
    from .app import app
    
    print("FastAPI Demo 应用")
    print("用法: python -m weather")
    print("然后访问: http://localhost:8000")
    print("API文档: http://localhost:8000/docs")
    
    uvicorn.run(app=app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
