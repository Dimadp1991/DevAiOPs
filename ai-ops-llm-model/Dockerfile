
FROM docker.io/vllm/vllm-openai:v0.6.3

# Set environment variables
ENV HUGGINGFACE_HUB_CACHE=/root/.cache/huggingface
ENV PYTHONUNBUFFERED=1


EXPOSE 8080

ENTRYPOINT ["python3", "-m", "vllm.entrypoints.openai.api_server"]
CMD [ \
  "--model", "/models/qwen2.5-coder-1.5b-instruct", \
  "--host", "0.0.0.0", \
  "--port", "8080" \
]