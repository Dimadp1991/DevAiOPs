import time
from prometheus_client import start_http_server, Gauge, Info
import pynvml

# Define Prometheus metrics
GPU_INFO = Info('gpu_device_info', 'Static information about the NVIDIA GPU')
GPU_UTIL = Gauge('custom_gpu_utilization_percent', 'GPU utilization percentage')
GPU_MEM_USED = Gauge('custom_gpu_memory_used_bytes', 'GPU memory used in bytes')
GPU_MEM_TOTAL = Gauge('custom_gpu_memory_total_bytes', 'GPU memory total in bytes')
GPU_TEMP = Gauge('custom_gpu_temperature_celsius', 'GPU temperature in Celsius')
GPU_POWER = Gauge('custom_gpu_power_usage_watts', 'GPU power usage in watts')


def collect_metrics():
    pynvml.nvmlInit()
    handle = pynvml.nvmlDeviceGetHandleByIndex(0)  # Primary GPU

    # 1. Fetch static GPU name once on startup
    gpu_name = pynvml.nvmlDeviceGetName(handle)
    # Handle byte strings across different nvidia-ml-py versions
    if isinstance(gpu_name, bytes):
        gpu_name = gpu_name.decode('utf-8')
    GPU_INFO.info({'model': gpu_name})
    print(f"Detected GPU: {gpu_name}")

    try:
        while True:
            # 2. Utilization
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            GPU_UTIL.set(util.gpu)

            # 3. Memory
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            GPU_MEM_USED.set(mem.used)
            GPU_MEM_TOTAL.set(mem.total)

            # 4. Temperature (Celsius)
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            GPU_TEMP.set(temp)

            # 5. Power Usage (Milliwatts converted to Watts)
            try:
                power_mw = pynvml.nvmlDeviceGetPowerUsage(handle)
                GPU_POWER.set(power_mw / 1000.0)
            except pynvml.NVMLError:
                pass  # Some laptop/virtualized GPUs might not expose power telemetry

            time.sleep(5)
    finally:
        pynvml.nvmlShutdown()


if __name__ == '__main__':
    start_http_server(9400)
    print("Enhanced Custom GPU Exporter started on port 9400...")
    collect_metrics()