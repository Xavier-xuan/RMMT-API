# 使用 Python 官方的 Docker 镜像作为基础镜像
FROM python:3.10-slim-bookworm

# 设置环境变量
ARG NAME

ENV NAME=${NAME}
ENV PIP_SOURCE="https://pypi.tuna.tsinghua.edu.cn/simple"

# 设置工作目录
WORKDIR /app

# 提前复制 requirements.txt（用于利用缓存）
COPY requirements.txt ./

# 安装应用依赖
RUN pip install -i ${PIP_SOURCE} --no-cache-dir -r requirements.txt
RUN pip install -i ${PIP_SOURCE} gunicorn
RUN pip install -i ${PIP_SOURCE} gevent
RUN export HF_ENDPOINT=https://hf-mirror.com
RUN pip uninstall -y text2vec
RUN pip install -U text2vec

# 复制应用代码到镜像中的 /app 目录
COPY . /app

EXPOSE 5000

# 设置入口点
ENTRYPOINT ["sh", "-c"]

# 设置启动命令
CMD ["echo 'Starting app...'&& python models.py && gunicorn -c gunicorn.config.py app:app"]
