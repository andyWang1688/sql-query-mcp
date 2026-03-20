# ==============================================================
# 第一阶段：构建阶段（编译安装依赖，产出安装好的 Python 包）
# 这个阶段的产物只有 /install 目录会被带到下一阶段，
# 其余所有内容（gcc 编译器、头文件等）都会被丢弃，不会出现在最终镜像中。
# ==============================================================
FROM python:3.13-slim AS builder

# 设置构建阶段的工作目录
WORKDIR /build

# 安装编译期依赖：
#   gcc      - C 编译器，psycopg 的 C 扩展需要用它来编译
#   libpq-dev - PostgreSQL 客户端开发库（头文件），编译 psycopg 时需要
# 安装完成后清理 apt 缓存，减小这一层的体积
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# 拷贝项目定义文件和源码到构建目录
COPY pyproject.toml ./
COPY sql_query_mcp/ sql_query_mcp/

# 用 pip 安装项目及其所有依赖到 /install 目录
# --no-cache-dir  不缓存下载的包，减小体积
# --prefix=/install  安装到独立目录，方便后续只拷贝这个目录到运行阶段
RUN pip install --no-cache-dir --prefix=/install .


# ==============================================================
# 第二阶段：运行阶段（最终镜像，只包含运行时必需的内容）
# 这里重新 FROM 一个干净的 python:3.13-slim，
# 第一阶段的 gcc、头文件等编译工具不会带进来，所以最终镜像很小。
# ==============================================================
FROM python:3.13-slim

# 镜像元数据标签
LABEL maintainer="andyWang1688"
LABEL org.opencontainers.image.source="https://github.com/andyWang1688/sql-query-mcp"
LABEL org.opencontainers.image.description="A general-purpose MCP server that lets AI work with multiple databases within clear boundaries."

# 安装运行时依赖：
#   libpq5 - PostgreSQL 客户端运行时库，psycopg 连接数据库时需要
#   注意：这里不需要 gcc 和 libpq-dev 了，因为编译已经在第一阶段完成
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/*

# 从第一阶段（builder）拷贝已安装好的 Python 包到系统目录
# 这一行就是多阶段构建的核心：只取编译产物，丢弃编译工具
COPY --from=builder /install /usr/local

# 设置运行阶段的工作目录
WORKDIR /app

# 拷贝应用源码和示例配置文件
COPY sql_query_mcp/ sql_query_mcp/
COPY config/connections.example.json config/connections.example.json

# 创建非 root 用户 mcp（uid=1000），用该用户运行服务
# 目的：即使容器被攻破，攻击者也不是 root，减少安全风险
RUN groupadd --gid 1000 mcp && \
    useradd --uid 1000 --gid mcp --shell /bin/false mcp && \
    mkdir -p /app/logs && \
    chown -R mcp:mcp /app

# 切换到非 root 用户
USER mcp

# 配置文件路径，可以通过以下两种方式覆盖：
#   1. 挂载卷：-v /your/connections.json:/app/config/connections.json:ro
#   2. 环境变量：-e SQL_QUERY_MCP_CONFIG=/custom/path.json
ENV SQL_QUERY_MCP_CONFIG=/app/config/connections.json

# 容器启动时执行的命令（即 pyproject.toml 中定义的 console script）
ENTRYPOINT ["sql-query-mcp"]
