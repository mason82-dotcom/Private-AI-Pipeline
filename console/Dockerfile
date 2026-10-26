FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Source archives can contain overly restrictive UNIX modes. Ensure the
# non-root runtime user can read both the server and its static assets.
COPY --chmod=0644 server.py ./server.py
COPY static/ ./static/
RUN chmod -R a+rX /app

USER 10001:10001
# Fail the image build if the runtime user cannot read required files.
RUN python -c "from pathlib import Path; Path('/app/server.py').read_bytes(); Path('/app/static/index.html').read_bytes()"

EXPOSE 8085
CMD ["python", "server.py"]
