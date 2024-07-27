# 使用 Python 官方的 Docker 镜像作为基础镜像
FROM python:3.13-alpine

# 设置环境变量
ARG NAME

ENV NAME=${NAME}
ENV PIP_SOURCE "https://pypi.tuna.tsinghua.edu.cn/simple"

# 设置工作目录
WORKDIR /app

# 复制应用代码到镜像中的 /app 目录
COPY . /app

# 安装应用依赖
RUN apk add --update musl-dev gcc cargo
RUN pip install -i ${PIP_SOURCE} --no-cache-dir -r requirements.txt
RUN pip install -i ${PIP_SOURCE} gunicorn
RUN pip install -i ${PIP_SOURCE} gevent

EXPOSE 5000

# 设置启动命令
CMD ["gunicorn", "-c", "gunicorn.config.py" ,"app:app"]