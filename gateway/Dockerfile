# Pin to an immutable digest before production deployments; tag shown for demonstration.
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY gateway.py memdb.py memcli.py mcp_stdio.py knowledge.py ./
# Seed the volume with a file so fresh Docker volumes preserve directory ownership.
RUN mkdir -p /data /documents && touch /data/.volume-init && chown -R 10001:10001 /data /app
USER 10001:10001
EXPOSE 8000
CMD ["python", "gateway.py"]
